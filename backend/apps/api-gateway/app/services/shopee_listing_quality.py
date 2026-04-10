from __future__ import annotations

import base64
from datetime import datetime
import hashlib
import json
import logging
import os
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

from sqlalchemy.orm import Session, selectinload

from app.models import ShopeeListing, ShopeeListingImage, ShopeeListingQualityScore, ShopeeListingVariant


QUALITY_SCORER_ENABLED = os.getenv("QUALITY_SCORER_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
QUALITY_SCORER_VERSION = (os.getenv("QUALITY_SCORER_VERSION", "v1") or "v1").strip()
QUALITY_SCORER_PROVIDER = (os.getenv("QUALITY_SCORER_PROVIDER", "none") or "none").strip().lower()
QUALITY_SCORER_BASE_URL = (os.getenv("QUALITY_SCORER_BASE_URL", "") or "").strip().rstrip("/")
QUALITY_SCORER_API_KEY = (os.getenv("QUALITY_SCORER_API_KEY", "") or "").strip()
QUALITY_SCORER_MODEL = (os.getenv("QUALITY_SCORER_MODEL", "gpt-4.1-mini") or "gpt-4.1-mini").strip()
QUALITY_SCORER_TEXT_MODEL = (
    os.getenv("QUALITY_SCORER_TEXT_MODEL", QUALITY_SCORER_MODEL) or QUALITY_SCORER_MODEL
).strip()
QUALITY_SCORER_VISION_MODEL = (
    os.getenv("QUALITY_SCORER_VISION_MODEL", QUALITY_SCORER_TEXT_MODEL) or QUALITY_SCORER_TEXT_MODEL
).strip()
QUALITY_SCORER_VISION_ENABLED = os.getenv("QUALITY_SCORER_VISION_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
QUALITY_SCORER_TIMEOUT_MS = max(1000, int(os.getenv("QUALITY_SCORER_TIMEOUT_MS", "6000")))
QUALITY_SCORER_MAX_RETRIES = max(0, int(os.getenv("QUALITY_SCORER_MAX_RETRIES", "1")))
QUALITY_SCORER_OLLAMA_USE_NATIVE = os.getenv("QUALITY_SCORER_OLLAMA_USE_NATIVE", "true").strip().lower() in {"1", "true", "yes", "on"}
QUALITY_SCORER_IMAGE_BASE_URL = (os.getenv("QUALITY_SCORER_IMAGE_BASE_URL", "") or "").strip().rstrip("/")
QUALITY_SCORER_MAX_IMAGE_COUNT = max(1, int(os.getenv("QUALITY_SCORER_MAX_IMAGE_COUNT", "8")))

QUALITY_WEIGHT_RULE = float(os.getenv("QUALITY_WEIGHT_RULE", "0.30"))
QUALITY_WEIGHT_VISION = float(os.getenv("QUALITY_WEIGHT_VISION", "0.35"))
QUALITY_WEIGHT_TEXT = float(os.getenv("QUALITY_WEIGHT_TEXT", "0.20"))
QUALITY_WEIGHT_CONSISTENCY = float(os.getenv("QUALITY_WEIGHT_CONSISTENCY", "0.15"))

QUALITY_THRESHOLD_GOOD = int(os.getenv("QUALITY_THRESHOLD_GOOD", "60"))
QUALITY_THRESHOLD_EXCELLENT = int(os.getenv("QUALITY_THRESHOLD_EXCELLENT", "85"))

logger = logging.getLogger(__name__)


def _clamp_score(val: float) -> int:
    return int(max(0, min(100, round(float(val)))))


def _safe_json_load_dict(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _safe_json_load_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [str(x) for x in data if str(x).strip()]


def _safe_json_like_list(val: Any) -> list[Any]:
    if isinstance(val, list):
        return val
    return []


def _build_image_inputs(
    listing: ShopeeListing,
    images: list[ShopeeListingImage],
    variants: list[ShopeeListingVariant],
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _add(label: str, url: str, source: str) -> None:
        key = (label.strip(), url.strip())
        if not label.strip() or not url.strip() or key in seen:
            return
        seen.add(key)
        items.append({"label": label.strip(), "url": url.strip(), "source": source})

    cover = str(listing.cover_url or "").strip()
    if cover:
        _add("主图", cover, "cover")

    image_idx = 0
    for img in images:
        url = str(img.image_url or "").strip()
        if not url:
            continue
        image_idx += 1
        label = "主图" if bool(img.is_cover) else f"商品图{image_idx}"
        _add(label, url, "listing")

    for variant in variants:
        url = str(variant.image_url or "").strip()
        if not url:
            continue
        sku = (variant.sku or "").strip()
        option_value = (variant.option_value or "").strip()
        if sku:
            label = f"SKU {sku}"
        elif option_value:
            label = f"变体 {option_value}"
        else:
            label = f"变体#{int(variant.id or 0)}"
        _add(label, url, "variant")

    return items


def _parse_image_ref_index(image_ref: str) -> int | None:
    raw = str(image_ref or "").strip().lower()
    if raw.startswith("img"):
        digits = "".join(ch for ch in raw if ch.isdigit())
        if digits.isdigit():
            idx = int(digits)
            if idx > 0:
                return idx - 1
    return None


def _normalize_image_feedback(feedback_rows: list[Any], image_inputs: list[dict[str, str]]) -> list[dict[str, Any]]:
    if not feedback_rows:
        return []
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(feedback_rows, start=1):
        if not isinstance(row, dict):
            continue
        image_ref = str(row.get("image_ref") or f"IMG{idx}").strip() or f"IMG{idx}"
        image_idx = _parse_image_ref_index(image_ref)
        mapped_label = ""
        if image_idx is not None and 0 <= image_idx < len(image_inputs):
            mapped_label = str(image_inputs[image_idx].get("label") or "").strip()
        fallback_label = str(row.get("label") or "").strip()
        image_label = mapped_label or fallback_label or f"图片{idx}"
        score_val = row.get("score")
        score_num = int(score_val) if isinstance(score_val, (int, float)) else None
        out.append(
            {
                "image_ref": image_ref,
                "image_label": image_label,
                "score": score_num,
                "good": str(row.get("good") or row.get("strength") or "").strip(),
                "bad": str(row.get("bad") or row.get("issue") or "").strip(),
                "suggestion": str(row.get("suggestion") or "").strip(),
            }
        )
    return out


def _hash_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _infer_text_score(listing: ShopeeListing) -> int:
    title_len = len((listing.title or "").strip())
    desc_len = len((listing.description or "").strip())
    score = 58.0
    if 20 <= title_len <= 120:
        score += 16
    elif 12 <= title_len <= 160:
        score += 8
    if desc_len >= 30:
        score += 14
    if desc_len >= 100:
        score += 8
    if listing.category_id:
        score += 4
    return _clamp_score(score)


def _infer_vision_score(images: list[ShopeeListingImage], *, total_image_count: int | None = None) -> int:
    image_count = int(total_image_count or len(images))
    score = 50.0
    if image_count >= 3:
        score += 18
    if image_count >= 5:
        score += 10
    if any((img.is_cover for img in images)):
        score += 10
    if any(((img.image_ratio or "").strip() == "1:1" for img in images)):
        score += 6
    if any(((img.image_ratio or "").strip() == "3:4" for img in images)):
        score += 6
    return _clamp_score(score)


def _infer_consistency_score(listing: ShopeeListing, images: list[ShopeeListingImage], variants: list[ShopeeListingVariant]) -> int:
    score = 56.0
    if listing.category_id and (listing.category or "").strip():
        score += 14
    if images:
        score += 12
    if variants:
        complete_ratio = sum(1 for v in variants if (v.sku or "").strip() and int(v.price or 0) > 0) / max(len(variants), 1)
        score += 18 * complete_ratio
    return _clamp_score(score)


def _compute_rule_score(
    listing: ShopeeListing,
    images: list[ShopeeListingImage],
    variants: list[ShopeeListingVariant],
    *,
    total_image_count: int | None = None,
) -> tuple[int, list[str], list[str]]:
    score = 100
    reasons: list[str] = []
    suggestions: list[str] = []

    title_len = len((listing.title or "").strip())
    desc_len = len((listing.description or "").strip())
    image_count = int(total_image_count or len(images))

    if image_count < 3:
        deduct = min(24, (3 - image_count) * 8)
        score -= deduct
        reasons.append(f"商品图数量不足（当前 {image_count} 张）")
        suggestions.append("建议上传至少 3 张商品图（主图+细节图+场景图）")

    if title_len < 20 or title_len > 120:
        score -= 8
        reasons.append(f"标题长度不理想（当前 {title_len} 字）")
        suggestions.append("建议标题控制在 20~120 字并包含核心规格信息")

    if not listing.category_id:
        score -= 20
        reasons.append("未绑定有效类目")
        suggestions.append("请先选择准确类目，提升图文匹配与搜索表现")

    if desc_len < 30:
        score -= 10
        reasons.append("商品描述信息偏少")
        suggestions.append("建议补充材质、功效、使用方式与注意事项")

    if int(listing.price or 0) <= 0:
        score -= 10
        reasons.append("价格配置异常（<=0）")
        suggestions.append("请设置有效售价")

    if variants:
        defect_cnt = 0
        for row in variants:
            if not (row.sku or "").strip() or int(row.price or 0) <= 0 or int(row.stock or 0) < 0:
                defect_cnt += 1
        if defect_cnt > 0:
            deduct = min(18, defect_cnt * 3)
            score -= deduct
            reasons.append(f"变体关键信息不完整（{defect_cnt} 个）")
            suggestions.append("建议补齐变体 SKU、价格、库存字段")

    final_score = _clamp_score(score)
    return final_score, reasons, suggestions


def _normalize_weights() -> tuple[float, float, float, float]:
    vals = [max(0.0, QUALITY_WEIGHT_RULE), max(0.0, QUALITY_WEIGHT_VISION), max(0.0, QUALITY_WEIGHT_TEXT), max(0.0, QUALITY_WEIGHT_CONSISTENCY)]
    total = sum(vals)
    if total <= 0:
        return 0.3, 0.35, 0.2, 0.15
    return vals[0] / total, vals[1] / total, vals[2] / total, vals[3] / total


def _resolve_quality_status(total_score: int) -> str:
    if total_score >= QUALITY_THRESHOLD_EXCELLENT:
        return "内容优秀"
    if total_score >= QUALITY_THRESHOLD_GOOD:
        return "内容合格"
    return "内容待完善"


def _call_openai_compatible_score(
    *,
    model: str,
    prompt: str,
    provider: str,
    image_urls: list[str] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    if not QUALITY_SCORER_BASE_URL:
        return None, "QUALITY_SCORER_BASE_URL 未配置"
    endpoint = f"{QUALITY_SCORER_BASE_URL}/v1/chat/completions"
    content_items: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for url in image_urls or []:
        if url:
            content_items.append({"type": "image_url", "image_url": {"url": url}})
    payload: dict[str, Any] = {
        "model": model,
        "temperature": 0,
        "messages": [{"role": "user", "content": content_items}],
    }
    if provider != "ollama":
        payload["response_format"] = {"type": "json_object"}
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if QUALITY_SCORER_API_KEY:
        headers["Authorization"] = f"Bearer {QUALITY_SCORER_API_KEY}"

    attempt = 0
    last_error: str | None = None
    while attempt <= QUALITY_SCORER_MAX_RETRIES:
        attempt += 1
        req = urlrequest.Request(endpoint, data=body, headers=headers, method="POST")
        try:
            with urlrequest.urlopen(req, timeout=QUALITY_SCORER_TIMEOUT_MS / 1000.0) as resp:
                raw = resp.read().decode("utf-8")
            parsed = _safe_json_load_dict(raw)
            choices = parsed.get("choices") or []
            if not choices:
                logger.warning("quality scorer got empty choices: provider=%s model=%s", provider, model)
                last_error = "返回 choices 为空"
                continue
            content_value = (((choices[0] or {}).get("message") or {}).get("content") or "")
            if isinstance(content_value, dict):
                return content_value
            if isinstance(content_value, list):
                merged = " ".join(str((item or {}).get("text") or "") for item in content_value if isinstance(item, dict)).strip()
                content_raw = merged
            else:
                content_raw = str(content_value or "").strip()
            if not content_raw:
                logger.warning("quality scorer got empty content: provider=%s model=%s", provider, model)
                last_error = "返回 content 为空"
                continue
            content_dict = _safe_json_load_dict(content_raw)
            if content_dict:
                return content_dict, None
            logger.warning("quality scorer content is not valid json: provider=%s model=%s content=%s", provider, model, content_raw[:300])
            last_error = f"返回内容非 JSON: {content_raw[:120]}"
        except urlerror.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8")[:600]
            except Exception:
                detail = ""
            logger.warning(
                "quality scorer http error: provider=%s model=%s status=%s detail=%s",
                provider,
                model,
                getattr(exc, "code", None),
                detail,
            )
            last_error = f"HTTP {getattr(exc, 'code', 'ERR')}: {detail[:180] if detail else 'no detail'}"
            continue
        except (urlerror.URLError, TimeoutError, ValueError) as exc:
            logger.warning("quality scorer request failed: provider=%s model=%s error=%s", provider, model, exc)
            last_error = str(exc)
            continue
    return None, last_error


def _to_absolute_image_url(url: str) -> str | None:
    raw = (url or "").strip()
    if not raw:
        return None
    if raw.startswith(("http://", "https://")):
        return raw
    if raw.startswith("/") and QUALITY_SCORER_IMAGE_BASE_URL:
        return f"{QUALITY_SCORER_IMAGE_BASE_URL}{raw}"
    return None


def _fetch_image_base64(url: str) -> str | None:
    absolute = _to_absolute_image_url(url)
    if not absolute:
        return None
    req = urlrequest.Request(absolute, method="GET")
    try:
        with urlrequest.urlopen(req, timeout=max(1.0, QUALITY_SCORER_TIMEOUT_MS / 2000.0)) as resp:
            data = resp.read()
        if not data:
            return None
        return base64.b64encode(data).decode("utf-8")
    except Exception as exc:
        logger.warning("quality scorer image fetch failed: url=%s error=%s", absolute, exc)
        return None


def _call_ollama_native_score(
    *,
    model: str,
    prompt: str,
    image_urls: list[str] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    if not QUALITY_SCORER_BASE_URL:
        return None, "QUALITY_SCORER_BASE_URL 未配置"
    endpoint = f"{QUALITY_SCORER_BASE_URL}/api/chat"
    images_b64: list[str] = []
    for url in image_urls or []:
        encoded = _fetch_image_base64(url)
        if encoded:
            images_b64.append(encoded)
    msg: dict[str, Any] = {"role": "user", "content": prompt}
    if images_b64:
        msg["images"] = images_b64
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "messages": [msg],
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if QUALITY_SCORER_API_KEY:
        headers["Authorization"] = f"Bearer {QUALITY_SCORER_API_KEY}"
    attempt = 0
    last_error: str | None = None
    while attempt <= QUALITY_SCORER_MAX_RETRIES:
        attempt += 1
        req = urlrequest.Request(endpoint, data=body, headers=headers, method="POST")
        try:
            with urlrequest.urlopen(req, timeout=QUALITY_SCORER_TIMEOUT_MS / 1000.0) as resp:
                raw = resp.read().decode("utf-8")
            parsed = _safe_json_load_dict(raw)
            msg_content = ((parsed.get("message") or {}).get("content") or "")
            if isinstance(msg_content, dict):
                return msg_content, None
            content_raw = str(msg_content or "").strip()
            if not content_raw:
                logger.warning("quality scorer ollama native got empty content: model=%s", model)
                last_error = "message.content 为空"
                continue
            content_dict = _safe_json_load_dict(content_raw)
            if content_dict:
                return content_dict, None
            logger.warning("quality scorer ollama native content not json: model=%s content=%s", model, content_raw[:300])
            last_error = f"返回内容非 JSON: {content_raw[:120]}"
        except urlerror.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8")[:600]
            except Exception:
                detail = ""
            logger.warning("quality scorer ollama native http error: model=%s status=%s detail=%s", model, getattr(exc, "code", None), detail)
            last_error = f"HTTP {getattr(exc, 'code', 'ERR')}: {detail[:180] if detail else 'no detail'}"
            continue
        except Exception as exc:
            logger.warning("quality scorer ollama native request failed: model=%s error=%s", model, exc)
            last_error = str(exc)
            continue
    return None, last_error


def recompute_listing_quality(
    db: Session,
    *,
    listing_id: int,
    run_id: int,
    user_id: int,
    force_recompute: bool = False,
) -> ShopeeListingQualityScore | None:
    listing = (
        db.query(ShopeeListing)
        .filter(ShopeeListing.id == listing_id, ShopeeListing.run_id == run_id, ShopeeListing.user_id == user_id)
        .options(selectinload(ShopeeListing.images), selectinload(ShopeeListing.variants))
        .first()
    )
    if not listing:
        return None

    images = sorted(list(listing.images or []), key=lambda x: (int(x.sort_order or 0), int(x.id or 0)))
    variants = sorted(list(listing.variants or []), key=lambda x: (int(x.sort_order or 0), int(x.id or 0)))
    image_inputs = _build_image_inputs(listing, images, variants)
    image_urls = [str(item.get("url") or "").strip() for item in image_inputs if str(item.get("url") or "").strip()]

    content_payload = {
        "title": (listing.title or "").strip(),
        "category_id": listing.category_id,
        "category": (listing.category or "").strip(),
        "description": (listing.description or "").strip(),
        "price": int(listing.price or 0),
        "stock_available": int(listing.stock_available or 0),
            "image_urls": image_urls,
        "variants": [
            {
                "option_value": (v.option_value or "").strip(),
                "option_note": (v.option_note or "").strip(),
                "price": int(v.price or 0),
                "stock": int(v.stock or 0),
                "sku": (v.sku or "").strip(),
            }
            for v in variants
        ],
    }
    content_hash = _hash_payload(content_payload)

    latest = (
        db.query(ShopeeListingQualityScore)
        .filter(
            ShopeeListingQualityScore.listing_id == listing.id,
            ShopeeListingQualityScore.is_latest == True,
        )
        .order_by(ShopeeListingQualityScore.id.desc())
        .first()
    )
    if latest and latest.content_hash == content_hash and not force_recompute:
        if listing.quality_total_score is None:
            listing.quality_total_score = int(latest.total_score or 0)
            listing.quality_status = (latest.quality_status or "").strip() or "内容待完善"
            listing.quality_score_version = (latest.score_version or "").strip() or QUALITY_SCORER_VERSION
            listing.quality_scored_at = latest.created_at
            db.flush()
        return latest

    total_image_count = len(image_urls)
    rule_score, rule_reasons, rule_suggestions = _compute_rule_score(
        listing,
        images,
        variants,
        total_image_count=total_image_count,
    )
    vision_score = _infer_vision_score(images, total_image_count=total_image_count)
    text_score = _infer_text_score(listing)
    consistency_score = _infer_consistency_score(listing, images, variants)

    raw_result: dict[str, Any] = {
        "rule_engine": {"score": rule_score, "reasons": rule_reasons, "suggestions": rule_suggestions},
        "model": {},
    }

    provider = QUALITY_SCORER_PROVIDER if QUALITY_SCORER_ENABLED else "none"
    extra_reasons: list[str] = []
    extra_suggestions: list[str] = []
    prompt_hash = None

    if QUALITY_SCORER_ENABLED and provider in {"openai", "ollama"}:
        single_prompt_payload = {
            "task": (
                "请一次性完成电商商品内容质量评分，返回 JSON："
                "{summary, text_score, vision_score, consistency_score, reasons, suggestions, image_feedback}。"
                "summary 为 AI 自主生成的整体评价总结（2~4 句），禁止使用固定模板句。"
                "三个分数均为 0-100 的数字。reasons/suggestions 为字符串数组。"
                "image_feedback 为数组，要求对每张输入图片都给一条评价；"
                "元素结构为 {image_ref, score, good, bad, suggestion}。"
            ),
            "scoring_focus": {
                "text_score": ["标题信息密度", "描述完整性", "表达可读性", "文案合规性"],
                "vision_score": ["清晰度", "主体完整度", "构图", "背景干净度", "违规视觉元素"],
                "consistency_score": ["标题与图片一致性", "类目与图片一致性", "变体与图片一致性"],
            },
            "listing": {
                "title": content_payload["title"],
                "category": content_payload["category"],
                "description": content_payload["description"],
                "price": content_payload["price"],
                "variants": content_payload["variants"][:10],
            },
            "image_inputs": [
                {"image_ref": f"IMG{i + 1}", "image_label": (row.get("label") or f"图片{i + 1}")}
                for i, row in enumerate(image_inputs[:QUALITY_SCORER_MAX_IMAGE_COUNT])
            ],
        }
        single_prompt = json.dumps(single_prompt_payload, ensure_ascii=False)
        prompt_hash = hashlib.sha256(single_prompt.encode("utf-8")).hexdigest()
        model_name = QUALITY_SCORER_VISION_MODEL if QUALITY_SCORER_VISION_ENABLED else QUALITY_SCORER_TEXT_MODEL
        single_result: dict[str, Any] | None = None
        error_parts: list[str] = []
        if provider == "ollama" and QUALITY_SCORER_OLLAMA_USE_NATIVE:
            single_result, native_error = _call_ollama_native_score(
                model=model_name,
                prompt=single_prompt,
                image_urls=image_urls[:QUALITY_SCORER_MAX_IMAGE_COUNT] if QUALITY_SCORER_VISION_ENABLED else None,
            )
            if native_error:
                error_parts.append(f"native={native_error}")
        if not single_result:
            fallback_image_urls = image_urls[:QUALITY_SCORER_MAX_IMAGE_COUNT] if QUALITY_SCORER_VISION_ENABLED else None
            # Ollama OpenAI-compatible path typically does not accept image_url.
            # Keep fallback text-only to avoid deterministic 400 on image URLs.
            if provider == "ollama":
                fallback_image_urls = None
            fallback_result, fallback_error = _call_openai_compatible_score(
                model=model_name,
                provider=provider,
                prompt=single_prompt,
                image_urls=fallback_image_urls,
            )
            if fallback_result:
                single_result = fallback_result
            elif fallback_error:
                error_parts.append(f"compat={fallback_error}")
        if single_result:
            raw_result["model"]["single_pass"] = single_result
            text_score = _clamp_score(float(single_result.get("text_score", text_score)))
            vision_score = _clamp_score(float(single_result.get("vision_score", vision_score)))
            consistency_score = _clamp_score(float(single_result.get("consistency_score", consistency_score)))
            extra_reasons.extend(_safe_json_load_list(json.dumps(single_result.get("reasons") or [])))
            extra_suggestions.extend(_safe_json_load_list(json.dumps(single_result.get("suggestions") or [])))
            image_feedback_raw = _safe_json_like_list(
                single_result.get("image_feedback")
                or single_result.get("image_assessments")
                or single_result.get("per_image_assessments")
                or single_result.get("image_reviews")
            )
            summary_text = str(
                single_result.get("summary")
                or single_result.get("evaluation_summary")
                or single_result.get("overall_summary")
                or ""
            ).strip()
            if summary_text:
                raw_result["model"]["summary"] = summary_text
            raw_result["model"]["image_feedback"] = _normalize_image_feedback(
                image_feedback_raw,
                image_inputs[:QUALITY_SCORER_MAX_IMAGE_COUNT],
            )
            raw_result["model"]["image_inputs"] = [
                {"image_ref": f"IMG{i + 1}", "image_label": (row.get("label") or f"图片{i + 1}")}
                for i, row in enumerate(image_inputs[:QUALITY_SCORER_MAX_IMAGE_COUNT])
            ]
        else:
            single_error = " | ".join(error_parts).strip() or None
            if provider == "ollama":
                extra_reasons.append("Ollama 模型调用失败，已降级为规则/启发式评分")
                if single_error:
                    extra_suggestions.append(f"Ollama 失败原因：{single_error[:180]}")
                extra_suggestions.append("请确认 Ollama 正在运行，模型支持多模态与 JSON 输出，且图片 URL 对后端可访问")
            else:
                extra_reasons.append("模型不可用，已降级为规则/启发式评分")

    wr, wv, wt, wc = _normalize_weights()
    total_score = _clamp_score(rule_score * wr + vision_score * wv + text_score * wt + consistency_score * wc)
    quality_status = _resolve_quality_status(total_score)
    reasons = [*rule_reasons, *extra_reasons]
    suggestions = [*rule_suggestions, *extra_suggestions]

    db.query(ShopeeListingQualityScore).filter(
        ShopeeListingQualityScore.listing_id == listing.id,
        ShopeeListingQualityScore.is_latest == True,
    ).update({ShopeeListingQualityScore.is_latest: False}, synchronize_session=False)

    snapshot = ShopeeListingQualityScore(
        listing_id=listing.id,
        run_id=run_id,
        user_id=user_id,
        score_version=QUALITY_SCORER_VERSION,
        provider=provider,
        text_model=QUALITY_SCORER_TEXT_MODEL if provider in {"openai", "ollama"} else None,
        vision_model=QUALITY_SCORER_VISION_MODEL if (provider in {"openai", "ollama"} and QUALITY_SCORER_VISION_ENABLED) else None,
        prompt_hash=prompt_hash,
        content_hash=content_hash,
        rule_score=rule_score,
        vision_score=vision_score,
        text_score=text_score,
        consistency_score=consistency_score,
        total_score=total_score,
        quality_status=quality_status,
        reasons_json=json.dumps(reasons, ensure_ascii=False),
        suggestions_json=json.dumps(suggestions, ensure_ascii=False),
        raw_result_json=json.dumps(raw_result, ensure_ascii=False),
        is_latest=True,
    )
    db.add(snapshot)

    listing.quality_status = quality_status
    listing.quality_total_score = total_score
    listing.quality_scored_at = datetime.utcnow()
    listing.quality_score_version = QUALITY_SCORER_VERSION
    db.flush()
    return snapshot

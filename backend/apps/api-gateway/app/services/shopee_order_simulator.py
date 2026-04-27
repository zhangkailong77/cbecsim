from __future__ import annotations

from datetime import datetime, timedelta
import json
import random
from typing import Any
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models import (
    InventoryStockMovement,
    ShopeeDiscountCampaign,
    ShopeeListing,
    ShopeeListingVariant,
    ShopeeOrder,
    ShopeeOrderGenerationLog,
    ShopeeOrderItem,
    SimBuyerProfile,
)
from app.services.inventory_lot_sync import get_lot_available_qty, release_reserved_inventory_lots, reserve_inventory_lots

BACKORDER_GRACE_GAME_HOURS = 48


def _clamp(num: float, low: float, high: float) -> float:
    return max(low, min(high, num))


def _safe_load_list(raw: str, fallback: list[float]) -> list[float]:
    try:
        data = json.loads(raw or "[]")
    except Exception:
        return fallback
    if not isinstance(data, list):
        return fallback
    result: list[float] = []
    for idx, val in enumerate(data):
        if idx >= len(fallback):
            break
        try:
            result.append(float(val))
        except Exception:
            result.append(fallback[idx])
    if len(result) < len(fallback):
        result.extend(fallback[len(result):])
    return result


def _safe_load_str_list(raw: str) -> list[str]:
    try:
        data = json.loads(raw or "[]")
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    values: list[str] = []
    for item in data:
        text = str(item or "").strip()
        if text:
            values.append(text)
    return values


def _resolve_listing_quality_score(listing: ShopeeListing) -> float:
    status = (listing.quality_status or "").strip()
    if status == "内容优秀":
        return 1.0
    if status == "内容合格":
        return 0.85
    if status == "内容待完善":
        return 0.45
    score = int(listing.quality_total_score or 0)
    if score >= 85:
        return 1.0
    if score >= 60:
        return 0.85
    return 0.45


def _pick_variant(listing: ShopeeListing) -> ShopeeListingVariant | None:
    variants = sorted(list(listing.variants or []), key=lambda row: (row.sort_order, row.id))
    for row in variants:
        if _variant_sellable_cap(row) > 0:
            return row
    return None


def _listing_available_stock(listing: ShopeeListing) -> int:
    variants = list(listing.variants or [])
    if variants:
        return int(sum(max(0, int(v.stock or 0)) for v in variants))
    return max(0, int(listing.stock_available or 0))


def _variant_oversell_remaining(variant: ShopeeListingVariant) -> int:
    limit_val = max(0, int(variant.oversell_limit or 0))
    used_val = max(0, int(variant.oversell_used or 0))
    return max(0, limit_val - used_val)


def _variant_sellable_cap(variant: ShopeeListingVariant) -> int:
    return max(0, int(variant.stock or 0)) + _variant_oversell_remaining(variant)


def _listing_sellable_cap(listing: ShopeeListing) -> int:
    variants = list(listing.variants or [])
    if variants:
        return int(sum(_variant_sellable_cap(v) for v in variants))
    return _listing_available_stock(listing)


def _resolve_price_score(*, price: float, target_price: float, price_sensitivity: float) -> tuple[float, float]:
    safe_target_price = max(float(target_price), 1.0)
    safe_price = max(float(price), 1.0)
    sensitivity = _clamp(float(price_sensitivity or 0.5), 0.0, 1.0)
    price_gap = (safe_price - safe_target_price) / safe_target_price
    if price_gap >= 0:
        price_score = _clamp(1 - price_gap * (0.5 + sensitivity * 0.5), 0.0, 1.0)
    else:
        price_score = _clamp(1 + abs(price_gap) * (0.5 - sensitivity * 0.5), 0.0, 1.0)
    return price_score, price_gap


def _load_ongoing_discount_map(db: Session, *, run_id: int, user_id: int, tick_time: datetime) -> dict[tuple[int, int | None], dict[str, Any]]:
    campaigns = (
        db.query(ShopeeDiscountCampaign)
        .options(selectinload(ShopeeDiscountCampaign.items))
        .filter(
            ShopeeDiscountCampaign.run_id == run_id,
            ShopeeDiscountCampaign.user_id == user_id,
            ShopeeDiscountCampaign.campaign_type == "discount",
            ShopeeDiscountCampaign.campaign_status.in_(("ongoing", "upcoming")),
            ShopeeDiscountCampaign.start_at.isnot(None),
            ShopeeDiscountCampaign.end_at.isnot(None),
            ShopeeDiscountCampaign.start_at <= tick_time,
            ShopeeDiscountCampaign.end_at >= tick_time,
        )
        .all()
    )
    discount_map: dict[tuple[int, int | None], dict[str, Any]] = {}
    for campaign in campaigns:
        for item in sorted(campaign.items or [], key=lambda row: (row.sort_order, row.id)):
            if item.final_price is None or float(item.final_price) <= 0:
                continue
            discount_map[(int(item.listing_id or 0), int(item.variant_id) if item.variant_id is not None else None)] = {
                "campaign_id": campaign.id,
                "campaign_name": campaign.campaign_name,
                "campaign_type": campaign.campaign_type,
                "listing_id": int(item.listing_id or 0),
                "variant_id": int(item.variant_id) if item.variant_id is not None else None,
                "discount_type": item.discount_type,
                "discount_value": float(item.discount_value or 0),
                "final_price": max(1, int(round(float(item.final_price)))),
            }
    return discount_map


def _safe_load_bundle_rules(raw: str | None) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _safe_bundle_tiers(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    tiers: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        buy_quantity = int(item.get("buy_quantity") or 0)
        discount_value = float(item.get("discount_value") or 0)
        if buy_quantity <= 1 or discount_value <= 0:
            continue
        tiers.append({
            "tier_no": int(item.get("tier_no") or len(tiers) + 1),
            "buy_quantity": buy_quantity,
            "discount_value": discount_value,
        })
    return sorted(tiers, key=lambda row: row["buy_quantity"])


def _load_ongoing_bundle_map(db: Session, *, run_id: int, user_id: int, tick_time: datetime) -> dict[tuple[int, int | None], dict[str, Any]]:
    campaigns = (
        db.query(ShopeeDiscountCampaign)
        .options(selectinload(ShopeeDiscountCampaign.items))
        .filter(
            ShopeeDiscountCampaign.run_id == run_id,
            ShopeeDiscountCampaign.user_id == user_id,
            ShopeeDiscountCampaign.campaign_type == "bundle",
            ShopeeDiscountCampaign.campaign_status.in_(("ongoing", "upcoming")),
            ShopeeDiscountCampaign.start_at.isnot(None),
            ShopeeDiscountCampaign.end_at.isnot(None),
            ShopeeDiscountCampaign.start_at <= tick_time,
            ShopeeDiscountCampaign.end_at >= tick_time,
        )
        .all()
    )
    bundle_map: dict[tuple[int, int | None], dict[str, Any]] = {}
    if not campaigns:
        return bundle_map

    for campaign in campaigns:
        rules = _safe_load_bundle_rules(campaign.rules_json)
        bundle_type = str(rules.get("bundle_type") or "percent").strip()
        if bundle_type not in {"percent", "fixed_amount", "bundle_price"}:
            continue
        purchase_limit = rules.get("purchase_limit")
        tiers = _safe_bundle_tiers(rules.get("tiers"))
        if not tiers:
            continue
        campaign_items = [
            {
                "listing_id": int(item.listing_id or 0),
                "variant_id": int(item.variant_id) if item.variant_id is not None else None,
                "product_name": item.product_name_snapshot,
                "image_url": item.image_url_snapshot,
                "original_price": max(1.0, float(item.original_price or 0)),
                "sort_order": int(item.sort_order or 0),
            }
            for item in sorted(campaign.items or [], key=lambda row: (row.sort_order, row.id))
            if int(item.listing_id or 0) > 0
        ]
        if len(campaign_items) < 2:
            continue
        for item in campaign_items:
            key = (int(item["listing_id"]), int(item["variant_id"]) if item["variant_id"] is not None else None)
            bundle_map[key] = {
                "campaign_id": campaign.id,
                "campaign_name": campaign.campaign_name,
                "campaign_type": campaign.campaign_type,
                "listing_id": key[0],
                "variant_id": key[1],
                "bundle_type": bundle_type,
                "purchase_limit": int(purchase_limit) if purchase_limit is not None else None,
                "sold_qty": 0,
                "tiers": tiers,
                "items": campaign_items,
            }
    return bundle_map


def _is_bundle_purchase_limit_reached(
    *,
    buyer_name: str,
    campaign_id: int,
    purchase_limit: int | None,
    buyer_bundle_order_counts: dict[tuple[str, int], int],
) -> tuple[bool, int]:
    if purchase_limit is None:
        return False, 0
    used_count = buyer_bundle_order_counts.get((buyer_name, campaign_id), 0)
    return used_count >= int(purchase_limit), used_count


def _resolve_effective_price(
    listing: ShopeeListing,
    *,
    variant: ShopeeListingVariant | None,
    discount_map: dict[tuple[int, int | None], dict[str, Any]],
) -> tuple[int, dict[str, Any] | None]:
    listing_id = int(listing.id)
    variant_id = int(variant.id) if variant else None
    discount = discount_map.get((listing_id, variant_id)) or discount_map.get((listing_id, None))
    base_price = max(1, int((variant.price if variant else listing.price) or 0))
    if not discount:
        return base_price, None
    return max(1, int(discount["final_price"])), discount


def _resolve_bundle_unit_price(*, bundle_type: str, original_price: float, tier: dict[str, Any]) -> float:
    buy_quantity = max(1, int(tier.get("buy_quantity") or 1))
    discount_value = float(tier.get("discount_value") or 0)
    safe_price = max(float(original_price or 0), 1.0)
    if bundle_type == "percent":
        return max(1.0, safe_price * (1 - discount_value / 100))
    if bundle_type == "fixed_amount":
        return max(1.0, (safe_price * buy_quantity - discount_value) / buy_quantity)
    if bundle_type == "bundle_price":
        return max(1.0, discount_value / buy_quantity)
    return safe_price


def _resolve_bundle_upgrade(
    listing: ShopeeListing,
    *,
    variant: ShopeeListingVariant | None,
    bundle_map: dict[tuple[int, int | None], dict[str, Any]],
    sellable_cap: int,
    buyer_purchase_power: float,
    buyer_price_sensitivity: float,
    buyer_impulse_level: float,
    rng: random.Random,
) -> dict[str, Any] | None:
    listing_id = int(listing.id)
    variant_id = int(variant.id) if variant else None
    bundle = bundle_map.get((listing_id, variant_id)) or bundle_map.get((listing_id, None))
    if not bundle:
        return None
    original_price = max(1.0, float((variant.price if variant else listing.price) or 0))
    buyer_budget = 30 + _clamp(float(buyer_purchase_power or 0.5), 0.0, 1.0) * 300
    price_sensitivity = _clamp(float(buyer_price_sensitivity or 0.5), 0.0, 1.0)
    impulse_level = _clamp(float(buyer_impulse_level or 0.0), 0.0, 1.0)
    bundle_item_count = len(list(bundle.get("items") or []))
    available_tiers = [tier for tier in bundle["tiers"] if int(tier["buy_quantity"]) <= bundle_item_count]
    if not available_tiers:
        return None

    tier = max(available_tiers, key=lambda row: int(row["buy_quantity"]))
    tier_qty = int(tier["buy_quantity"])
    unit_price = _resolve_bundle_unit_price(bundle_type=bundle["bundle_type"], original_price=original_price, tier=tier)
    savings_rate = _clamp((original_price - unit_price) / original_price, 0.0, 0.95)
    afford_factor = _clamp(buyer_budget / max(unit_price * tier_qty, 1.0), 0.60, 1.0)
    attempts = [
        {
            "tier_no": tier.get("tier_no"),
            "buy_quantity": tier_qty,
            "unit_price": round(unit_price, 2),
            "savings_rate": round(savings_rate, 4),
            "afford_factor": round(afford_factor, 4),
            "upgrade_prob": 1.0,
            "upgrade_roll": 0.0,
            "hit": True,
            "reason": "active_bundle_combo_auto_applied",
        }
    ]
    return {
        "campaign_id": bundle["campaign_id"],
        "campaign_name": bundle["campaign_name"],
        "campaign_type": bundle["campaign_type"],
        "bundle_type": bundle["bundle_type"],
        "purchase_limit": bundle["purchase_limit"],
        "sold_qty": bundle["sold_qty"],
        "tier_no": tier.get("tier_no"),
        "tier": tier,
        "items": bundle["items"],
        "quantity": tier_qty,
        "unit_price": max(1, int(round(unit_price))),
        "savings_rate": savings_rate,
        "attempts": attempts,
    }


def _allocate_bundle_prices(*, bundle_type: str, tier: dict[str, Any], original_prices: list[float]) -> list[int]:
    safe_prices = [max(1.0, float(price or 0)) for price in original_prices]
    if not safe_prices:
        return []
    total_original = max(sum(safe_prices), 1.0)
    discount_value = float(tier.get("discount_value") or 0)
    if bundle_type == "percent":
        return [max(1, int(round(price * (1 - discount_value / 100)))) for price in safe_prices]
    if bundle_type == "fixed_amount":
        target_total = max(float(len(safe_prices)), total_original - discount_value)
    elif bundle_type == "bundle_price":
        target_total = max(float(len(safe_prices)), discount_value)
    else:
        target_total = total_original
    allocated = [max(1, int(round(target_total * price / total_original))) for price in safe_prices]
    diff = int(round(target_total)) - sum(allocated)
    if allocated and diff != 0:
        allocated[-1] = max(1, allocated[-1] + diff)
    return allocated


def _resolve_bundle_order_lines(
    db: Session,
    *,
    run_id: int,
    user_id: int,
    bundle_hit: dict[str, Any],
    set_qty: int,
) -> list[dict[str, Any]]:
    bundle_items = [item for item in list(bundle_hit.get("items") or []) if int(item.get("listing_id") or 0) > 0]
    if len(bundle_items) < 2:
        return []
    listing_ids = [int(item["listing_id"]) for item in bundle_items]
    listings = (
        db.query(ShopeeListing)
        .options(selectinload(ShopeeListing.variants))
        .filter(
            ShopeeListing.run_id == run_id,
            ShopeeListing.user_id == user_id,
            ShopeeListing.id.in_(listing_ids),
            ShopeeListing.status == "live",
        )
        .all()
    )
    listing_map = {int(row.id): row for row in listings}
    resolved_rows: list[tuple[dict[str, Any], ShopeeListing, ShopeeListingVariant | None, int]] = []
    for item in bundle_items:
        listing = listing_map.get(int(item["listing_id"]))
        if not listing:
            return []
        variant: ShopeeListingVariant | None = None
        item_variant_id = int(item["variant_id"]) if item.get("variant_id") is not None else None
        if item_variant_id is not None:
            variant = next((row for row in list(listing.variants or []) if int(row.id) == item_variant_id), None)
            if not variant:
                return []
        else:
            variant = _pick_variant(listing)
        original_price = max(1, int((variant.price if variant else listing.price) or item.get("original_price") or 0))
        resolved_rows.append((item, listing, variant, original_price))

    set_qty = max(1, int(set_qty or 1))
    prices = _allocate_bundle_prices(
        bundle_type=str(bundle_hit.get("bundle_type") or "percent"),
        tier=dict(bundle_hit.get("tier") or {}),
        original_prices=[float(row[3]) for row in resolved_rows],
    )
    if len(prices) != len(resolved_rows):
        return []

    lines: list[dict[str, Any]] = []
    for idx, (_item, listing, variant, _original_price) in enumerate(resolved_rows):
        product_id = int(listing.product_id or 0)
        available_stock = get_lot_available_qty(db, run_id=run_id, product_id=product_id) if product_id > 0 else (
            max(0, int(variant.stock or 0)) if variant else max(0, int(listing.stock_available or 0))
        )
        oversell_remaining = _variant_oversell_remaining(variant) if variant else 0
        shortfall_qty = max(0, set_qty - available_stock)
        if shortfall_qty > 0 and shortfall_qty > oversell_remaining:
            return []
        lines.append(
            {
                "listing": listing,
                "variant": variant,
                "product_id": product_id if product_id > 0 else None,
                "quantity": set_qty,
                "unit_price": max(1, int(prices[idx])),
                "available_stock": available_stock,
                "shortfall_qty": shortfall_qty,
                "stock_consumed_planned": max(0, set_qty - shortfall_qty),
                "image_url": variant.image_url if variant and (variant.image_url or "").strip() else listing.cover_url,
            }
        )
    return lines


def _pick_variant_for_buyer(
    listing: ShopeeListing,
    *,
    buyer_purchase_power: float,
    buyer_price_sensitivity: float,
    rng: random.Random,
    discount_map: dict[tuple[int, int | None], dict[str, Any]],
) -> tuple[ShopeeListingVariant | None, int, dict[str, Any] | None, float, float]:
    variants = [
        row
        for row in sorted(list(listing.variants or []), key=lambda x: (x.sort_order, x.id))
        if _variant_sellable_cap(row) > 0
    ]
    if not variants:
        base_price, discount = _resolve_effective_price(listing, variant=None, discount_map=discount_map)
        price_score, price_gap = _resolve_price_score(
            price=base_price,
            target_price=30 + _clamp(float(buyer_purchase_power or 0.5), 0.0, 1.0) * 300,
            price_sensitivity=buyer_price_sensitivity,
        )
        return None, base_price, discount, price_score, price_gap
    if len(variants) == 1:
        effective_price, discount = _resolve_effective_price(listing, variant=variants[0], discount_map=discount_map)
        price_score, price_gap = _resolve_price_score(
            price=effective_price,
            target_price=30 + _clamp(float(buyer_purchase_power or 0.5), 0.0, 1.0) * 300,
            price_sensitivity=buyer_price_sensitivity,
        )
        return variants[0], effective_price, discount, price_score, price_gap

    target_price = 30 + _clamp(float(buyer_purchase_power or 0.5), 0.0, 1.0) * 300
    best: ShopeeListingVariant | None = None
    best_discount: dict[str, Any] | None = None
    best_effective_price = 0
    best_price_score = 0.0
    best_price_gap = 0.0
    best_score = -1.0
    for row in variants:
        effective_price, discount = _resolve_effective_price(listing, variant=row, discount_map=discount_map)
        price_score, price_gap = _resolve_price_score(
            price=effective_price,
            target_price=target_price,
            price_sensitivity=buyer_price_sensitivity,
        )
        stock_score = _clamp(float(_variant_sellable_cap(row)) / 30.0, 0.0, 1.0)
        jitter = rng.random() * 0.06
        score = 0.70 * price_score + 0.24 * stock_score + 0.06 * jitter
        if score > best_score:
            best_score = score
            best = row
            best_discount = discount
            best_effective_price = effective_price
            best_price_score = price_score
            best_price_gap = price_gap
    return best, best_effective_price, best_discount, best_price_score, best_price_gap




def _resolve_shipping_channel(listing: ShopeeListing, rng: random.Random) -> str:
    channel_pool: list[str] = []
    if bool(getattr(listing, "shipping_standard_bulk", False)):
        channel_pool.append("标准大件")
    if bool(getattr(listing, "shipping_standard", False)):
        channel_pool.append("标准快递")
    if bool(getattr(listing, "shipping_express", False)):
        channel_pool.append("快捷快递")
    if not channel_pool:
        return "标准快递"
    return channel_pool[rng.randint(0, len(channel_pool) - 1)]


def _category_match_score(category: str | None, preferred_categories: list[str]) -> float:
    if not category or not preferred_categories:
        return 0.0
    normalized = category.strip()
    if not normalized:
        return 0.0
    for pref in preferred_categories:
        if pref in normalized or normalized in pref:
            return 1.0
    return 0.0


def simulate_orders_for_run(
    db: Session,
    *,
    run_id: int,
    user_id: int,
    tick_time: datetime | None = None,
) -> dict:
    rng = random.Random()
    now = tick_time or datetime.now()
    hour = now.hour
    weekday_idx = now.weekday()
    buyer_journeys: list[dict[str, Any]] = []

    live_products = (
        db.query(ShopeeListing)
        .options(selectinload(ShopeeListing.variants))
        .filter(
            ShopeeListing.run_id == run_id,
            ShopeeListing.user_id == user_id,
            ShopeeListing.status == "live",
        )
        .order_by(ShopeeListing.id.asc())
        .all()
    )

    discount_map = _load_ongoing_discount_map(db, run_id=run_id, user_id=user_id, tick_time=now)
    bundle_map = _load_ongoing_bundle_map(db, run_id=run_id, user_id=user_id, tick_time=now)

    skip_reasons: dict[str, int] = {}
    if not live_products:
        skip_reasons["no_live_products"] = 1
        debug_payload = {"buyer_journeys": buyer_journeys}
        row = ShopeeOrderGenerationLog(
            run_id=run_id,
            user_id=user_id,
            tick_time=now,
            active_buyer_count=0,
            candidate_product_count=0,
            generated_order_count=0,
            skip_reasons_json=json.dumps(skip_reasons, ensure_ascii=False),
            debug_payload_json=json.dumps(debug_payload, ensure_ascii=False),
        )
        db.add(row)
        db.commit()
        return {
            "tick_time": now,
            "active_buyer_count": 0,
            "candidate_product_count": 0,
            "generated_order_count": 0,
            "skip_reasons": skip_reasons,
            "buyer_journeys": buyer_journeys,
        }

    sellable_products = [row for row in live_products if _listing_sellable_cap(row) > 0]
    if not sellable_products:
        skip_reasons["no_stock"] = 1
        debug_payload = {"buyer_journeys": buyer_journeys}
        row = ShopeeOrderGenerationLog(
            run_id=run_id,
            user_id=user_id,
            tick_time=now,
            active_buyer_count=0,
            candidate_product_count=len(live_products),
            generated_order_count=0,
            skip_reasons_json=json.dumps(skip_reasons, ensure_ascii=False),
            debug_payload_json=json.dumps(debug_payload, ensure_ascii=False),
        )
        db.add(row)
        db.commit()
        return {
            "tick_time": now,
            "active_buyer_count": 0,
            "candidate_product_count": len(live_products),
            "generated_order_count": 0,
            "skip_reasons": skip_reasons,
            "buyer_journeys": buyer_journeys,
        }

    buyers = (
        db.query(SimBuyerProfile)
        .filter(SimBuyerProfile.is_active == True)
        .order_by(SimBuyerProfile.buyer_code.asc())
        .all()
    )
    if not buyers:
        skip_reasons["no_active_buyer_profiles"] = 1
        debug_payload = {"buyer_journeys": buyer_journeys}
        row = ShopeeOrderGenerationLog(
            run_id=run_id,
            user_id=user_id,
            tick_time=now,
            active_buyer_count=0,
            candidate_product_count=len(sellable_products),
            generated_order_count=0,
            skip_reasons_json=json.dumps(skip_reasons, ensure_ascii=False),
            debug_payload_json=json.dumps(debug_payload, ensure_ascii=False),
        )
        db.add(row)
        db.commit()
        return {
            "tick_time": now,
            "active_buyer_count": 0,
            "candidate_product_count": len(sellable_products),
            "generated_order_count": 0,
            "skip_reasons": skip_reasons,
            "buyer_journeys": buyer_journeys,
        }

    bundle_campaign_ids = {
        int(bundle["campaign_id"])
        for bundle in bundle_map.values()
        if int(bundle.get("campaign_id") or 0) > 0 and bundle.get("purchase_limit") is not None
    }
    buyer_bundle_order_counts: dict[tuple[str, int], int] = {}
    if bundle_campaign_ids:
        bought_rows = (
            db.query(ShopeeOrder.buyer_name, ShopeeOrder.marketing_campaign_id, func.count(ShopeeOrder.id))
            .filter(
                ShopeeOrder.run_id == run_id,
                ShopeeOrder.user_id == user_id,
                ShopeeOrder.marketing_campaign_type == "bundle",
                ShopeeOrder.marketing_campaign_id.in_(bundle_campaign_ids),
            )
            .group_by(ShopeeOrder.buyer_name, ShopeeOrder.marketing_campaign_id)
            .all()
        )
        buyer_bundle_order_counts = {
            (str(buyer_name or ""), int(campaign_id)): int(order_count or 0)
            for buyer_name, campaign_id, order_count in bought_rows
            if campaign_id is not None
        }

    active_buyer_count = 0
    generated_order_count = 0
    for buyer in buyers:
        journey: dict[str, Any] = {
            "buyer_code": buyer.buyer_code,
            "buyer_name": buyer.nickname,
            "city": buyer.city,
            "is_active": False,
            "active_prob": 0.0,
            "active_roll": 0.0,
            "decision": "skipped_inactive",
            "reason": "active_roll_gt_active_prob",
            "candidates": [],
            "selected_candidate": None,
            "order_prob": None,
            "order_roll": None,
            "generated_order": None,
        }
        active_hours = _safe_load_list(buyer.active_hours_json, [0.05] * 24)
        weekday_factors = _safe_load_list(buyer.weekday_factors_json, [1.0] * 7)
        active_prob = _clamp(active_hours[hour] * weekday_factors[weekday_idx], 0.01, 0.95)
        active_roll = rng.random()
        journey["active_prob"] = round(active_prob, 4)
        journey["active_roll"] = round(active_roll, 4)
        if active_roll > active_prob:
            buyer_journeys.append(journey)
            continue
        journey["is_active"] = True
        journey["decision"] = "active"
        journey["reason"] = "active_roll_le_active_prob"
        active_buyer_count += 1

        preferred_categories = _safe_load_str_list(buyer.preferred_categories_json)
        preferred_candidates = [
            row for row in sellable_products if _category_match_score(row.category, preferred_categories) > 0
        ]
        candidates = preferred_candidates if preferred_candidates else sellable_products
        if not candidates:
            skip_reasons["no_candidate"] = skip_reasons.get("no_candidate", 0) + 1
            journey["decision"] = "skipped_no_candidate"
            journey["reason"] = "no_candidate_after_filter"
            buyer_journeys.append(journey)
            continue

        best_listing: ShopeeListing | None = None
        best_score = -1.0
        candidate_logs: list[dict[str, Any]] = []
        for listing in candidates[:8]:
            category_match = _category_match_score(listing.category, preferred_categories)
            target_price = 30 + float(buyer.purchase_power or 0.5) * 300
            preview_variant, effective_price, hit_discount, price_score, price_gap = _pick_variant_for_buyer(
                listing,
                buyer_purchase_power=float(buyer.purchase_power or 0.5),
                buyer_price_sensitivity=float(buyer.price_sensitivity or 0.5),
                rng=rng,
                discount_map=discount_map,
            )
            quality_score = _resolve_listing_quality_score(listing)
            stock_score = _clamp(float(_listing_sellable_cap(listing)) / 40.0, 0.0, 1.0)
            base_intent = _clamp(float(buyer.base_buy_intent or 0.0), 0.0, 1.0)
            impulse = _clamp(float(buyer.impulse_level or 0.0), 0.0, 1.0)
            score = (
                0.32 * category_match
                + 0.22 * price_score
                + 0.14 * quality_score
                + 0.08 * stock_score
                + 0.16 * base_intent
                + 0.08 * impulse
            )
            candidate_logs.append(
                {
                    "listing_id": listing.id,
                    "title": listing.title,
                    "category": listing.category,
                    "sku": listing.sku_code,
                    "parent_sku": listing.parent_sku,
                    "price": int(listing.price or 0),
                    "effective_price": effective_price,
                    "price_gap": round(price_gap, 4),
                    "discount_hit": bool(hit_discount),
                    "discount_campaign_id": hit_discount["campaign_id"] if hit_discount else None,
                    "discount_variant_id": preview_variant.id if preview_variant and hit_discount else None,
                    "stock_available": _listing_available_stock(listing),
                    "sellable_cap": _listing_sellable_cap(listing),
                    "score_components": {
                        "category_match": round(category_match, 4),
                        "price_score": round(price_score, 4),
                        "quality_score": round(quality_score, 4),
                        "stock_score": round(stock_score, 4),
                        "base_intent": round(base_intent, 4),
                        "impulse": round(impulse, 4),
                    },
                    "total_score": round(score, 4),
                }
            )
            if score > best_score:
                best_score = score
                best_listing = listing

        journey["candidates"] = candidate_logs
        if not best_listing:
            skip_reasons["no_candidate"] = skip_reasons.get("no_candidate", 0) + 1
            journey["decision"] = "skipped_no_candidate"
            journey["reason"] = "best_listing_is_none"
            buyer_journeys.append(journey)
            continue

        base_order_prob = _clamp(0.08 + best_score * 0.95, 0.05, 0.90)
        variant, effective_price, hit_discount, selected_price_score, selected_price_gap = _pick_variant_for_buyer(
            best_listing,
            buyer_purchase_power=float(buyer.purchase_power or 0.5),
            buyer_price_sensitivity=float(buyer.price_sensitivity or 0.5),
            rng=rng,
            discount_map=discount_map,
        )
        original_unit_price = max(1, int((variant.price if variant else best_listing.price) or 0))
        no_discount_price_score, no_discount_price_gap = _resolve_price_score(
            price=float(original_unit_price),
            target_price=30 + float(buyer.purchase_power or 0.5) * 300,
            price_sensitivity=float(buyer.price_sensitivity or 0.5),
        )

        variant_available_stock = _listing_available_stock(best_listing)
        variant_oversell_remaining = 0
        sellable_cap = _listing_sellable_cap(best_listing)
        if variant:
            product_id_for_lot = int(best_listing.product_id or 0)
            if product_id_for_lot > 0:
                variant_available_stock = get_lot_available_qty(db, run_id=run_id, product_id=product_id_for_lot)
            else:
                variant_available_stock = max(0, int(variant.stock or 0))
            variant_oversell_remaining = _variant_oversell_remaining(variant)
            sellable_cap = variant_available_stock + variant_oversell_remaining
        if sellable_cap <= 0:
            skip_reasons["no_stock"] = skip_reasons.get("no_stock", 0) + 1
            journey["decision"] = "skipped_no_stock"
            journey["reason"] = "sellable_cap_le_0"
            buyer_journeys.append(journey)
            continue

        min_qty = max(1, int(best_listing.min_purchase_qty or 1))
        max_qty = min(3, sellable_cap)
        if best_listing.max_purchase_qty and int(best_listing.max_purchase_qty) > 0:
            max_qty = min(max_qty, int(best_listing.max_purchase_qty))
        if max_qty < min_qty:
            skip_reasons["below_min_purchase_qty"] = skip_reasons.get("below_min_purchase_qty", 0) + 1
            journey["decision"] = "skipped_min_qty"
            journey["reason"] = "sellable_cap_lt_min_purchase_qty"
            buyer_journeys.append(journey)
            continue

        category_match = _category_match_score(best_listing.category, preferred_categories)
        quality_score = _resolve_listing_quality_score(best_listing)
        stock_score = _clamp(float(_listing_sellable_cap(best_listing)) / 40.0, 0.0, 1.0)
        base_intent = _clamp(float(buyer.base_buy_intent or 0.0), 0.0, 1.0)
        impulse = _clamp(float(buyer.impulse_level or 0.0), 0.0, 1.0)
        no_discount_score = (
            0.32 * category_match
            + 0.22 * no_discount_price_score
            + 0.14 * quality_score
            + 0.08 * stock_score
            + 0.16 * base_intent
            + 0.08 * impulse
        )
        no_discount_order_prob = _clamp(0.08 + no_discount_score * 0.95, 0.05, 0.90)
        discount_order_prob = max(base_order_prob, no_discount_order_prob) if hit_discount else base_order_prob
        bundle_hit = _resolve_bundle_upgrade(
            best_listing,
            variant=variant,
            bundle_map=bundle_map,
            sellable_cap=sellable_cap,
            buyer_purchase_power=float(buyer.purchase_power or 0.5),
            buyer_price_sensitivity=float(buyer.price_sensitivity or 0.5),
            buyer_impulse_level=impulse,
            rng=rng,
        )
        base_unit_price = max(int(effective_price or 0), 1)
        quantity: int | None = None
        unit_price = base_unit_price
        applied_campaign = hit_discount
        bundle_applied = False
        bundle_order_prob = None
        bundle_score = None
        bundle_price_score = None
        bundle_price_gap = None
        bundle_limit_reached = False
        bundle_limit_count = 0
        if bundle_hit:
            bundle_limit_reached, bundle_limit_count = _is_bundle_purchase_limit_reached(
                buyer_name=str(buyer.nickname or ""),
                campaign_id=int(bundle_hit["campaign_id"]),
                purchase_limit=bundle_hit.get("purchase_limit"),
                buyer_bundle_order_counts=buyer_bundle_order_counts,
            )
            if bundle_limit_reached:
                bundle_hit = None
                skip_reasons["bundle_purchase_limit_reached"] = skip_reasons.get("bundle_purchase_limit_reached", 0) + 1
        if bundle_hit:
            bundle_price_score, bundle_price_gap = _resolve_price_score(
                price=float(bundle_hit["unit_price"]),
                target_price=30 + float(buyer.purchase_power or 0.5) * 300,
                price_sensitivity=float(buyer.price_sensitivity or 0.5),
            )
            bundle_score = (
                0.32 * category_match
                + 0.22 * bundle_price_score
                + 0.14 * quality_score
                + 0.08 * stock_score
                + 0.16 * base_intent
                + 0.08 * impulse
            )
            bundle_bonus = _clamp(float(bundle_hit["savings_rate"]) * 0.08, 0.0, 0.06)
            bundle_order_prob = _clamp(0.08 + bundle_score * 0.95 + bundle_bonus, 0.05, 0.90)
            quantity = max(1, len(list(bundle_hit.get("items") or [])))
            unit_price = int(bundle_hit["unit_price"])
            effective_price = unit_price
            selected_price_score = bundle_price_score
            selected_price_gap = bundle_price_gap
            applied_campaign = bundle_hit
            bundle_applied = True
        order_prob = max(discount_order_prob, bundle_order_prob) if bundle_order_prob is not None and bundle_applied else discount_order_prob
        order_roll = rng.random()
        journey["selected_candidate"] = {
            "listing_id": best_listing.id,
            "variant_id": variant.id if variant else None,
            "variant_name": variant.option_value if variant else "",
            "title": best_listing.title,
            "sku": best_listing.sku_code,
            "parent_sku": best_listing.parent_sku,
            "price": int(best_listing.price or 0),
            "effective_price": effective_price,
            "price_gap": round(selected_price_gap, 4),
            "price_score": round(selected_price_score, 4),
            "discount_hit": bool(hit_discount),
            "discount_campaign_id": hit_discount["campaign_id"] if hit_discount else None,
            "discount_campaign_name": hit_discount["campaign_name"] if hit_discount else None,
            "bundle_applied": bool(bundle_applied),
            "bundle_campaign_id": bundle_hit["campaign_id"] if bundle_hit else None,
            "bundle_campaign_name": bundle_hit["campaign_name"] if bundle_hit else None,
            "bundle_qty": int(bundle_hit["quantity"]) if bundle_hit and bundle_applied else None,
            "bundle_attempts": bundle_hit["attempts"] if bundle_hit else [],
            "bundle_purchase_limit_reached": bundle_limit_reached,
            "bundle_purchase_limit_used": bundle_limit_count,
            "base_order_prob": round(base_order_prob, 4),
            "no_discount_order_prob": round(no_discount_order_prob, 4),
            "discount_order_prob": round(discount_order_prob, 4),
            "bundle_order_prob": round(bundle_order_prob, 4) if bundle_order_prob is not None else None,
            "score": round(bundle_score if bundle_applied and bundle_score is not None else best_score, 4),
        }
        journey["order_prob"] = round(order_prob, 4)
        journey["order_roll"] = round(order_roll, 4)
        if order_roll > order_prob:
            skip_reasons["below_probability"] = skip_reasons.get("below_probability", 0) + 1
            journey["decision"] = "skipped_probability"
            journey["reason"] = "order_roll_gt_order_prob"
            buyer_journeys.append(journey)
            continue
        if quantity is None:
            quantity = rng.randint(min_qty, max_qty)
        if quantity <= 0:
            skip_reasons["invalid_qty"] = skip_reasons.get("invalid_qty", 0) + 1
            journey["decision"] = "skipped_invalid_qty"
            journey["reason"] = "quantity_le_0"
            buyer_journeys.append(journey)
            continue

        order_lines: list[dict[str, Any]] = []
        if bundle_applied and bundle_hit:
            bundle_item_count = max(1, len(list(bundle_hit.get("items") or [])))
            set_qty = max(1, int(bundle_hit["quantity"] or 1) // bundle_item_count)
            order_lines = _resolve_bundle_order_lines(
                db,
                run_id=run_id,
                user_id=user_id,
                bundle_hit=bundle_hit,
                set_qty=set_qty,
            )
            if not order_lines:
                skip_reasons["bundle_items_unavailable"] = skip_reasons.get("bundle_items_unavailable", 0) + 1
                journey["decision"] = "skipped_bundle_items_unavailable"
                journey["reason"] = "bundle_order_lines_empty"
                buyer_journeys.append(journey)
                continue
        else:
            shortfall_qty = max(0, quantity - variant_available_stock)
            if shortfall_qty > 0 and variant and shortfall_qty > variant_oversell_remaining:
                skip_reasons["oversell_limit_reached"] = skip_reasons.get("oversell_limit_reached", 0) + 1
                journey["decision"] = "skipped_oversell_limit_reached"
                journey["reason"] = "shortfall_gt_oversell_remaining"
                buyer_journeys.append(journey)
                continue
            order_lines = [
                {
                    "listing": best_listing,
                    "variant": variant,
                    "product_id": int(best_listing.product_id) if best_listing.product_id is not None else None,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "shortfall_qty": shortfall_qty,
                    "stock_consumed_planned": max(0, quantity - shortfall_qty),
                    "image_url": variant.image_url if variant and (variant.image_url or "").strip() else best_listing.cover_url,
                }
            ]

        payment = int(sum(int(line["unit_price"]) * int(line["quantity"]) for line in order_lines))
        total_shortfall_qty = int(sum(max(0, int(line["shortfall_qty"])) for line in order_lines))
        total_quantity = int(sum(max(0, int(line["quantity"])) for line in order_lines))
        for line in order_lines:
            listing_for_line: ShopeeListing = line["listing"]
            variant_for_line: ShopeeListingVariant | None = line["variant"]
            line_qty = int(line["quantity"])
            planned_qty = int(line["stock_consumed_planned"])
            reserved_qty = 0
            product_id = int(line["product_id"] or 0)
            if product_id > 0 and planned_qty > 0:
                reserved_qty = reserve_inventory_lots(
                    db,
                    run_id=run_id,
                    product_id=product_id,
                    qty=planned_qty,
                )
            line["reserved_qty"] = reserved_qty
            stock_consumed = reserved_qty
            listing_for_line.sales_count = int(listing_for_line.sales_count or 0) + line_qty
            listing_for_line.stock_available = max(0, int(listing_for_line.stock_available or 0) - stock_consumed)
            if variant_for_line:
                variant_for_line.stock = max(0, int(variant_for_line.stock or 0) - stock_consumed)
                variant_for_line.sales_count = int(variant_for_line.sales_count or 0) + line_qty
                if int(line["shortfall_qty"]) > 0:
                    variant_for_line.oversell_used = int(variant_for_line.oversell_used or 0) + int(line["shortfall_qty"])
                listing_for_line.stock_available = _listing_available_stock(listing_for_line)

        order = ShopeeOrder(
            run_id=run_id,
            user_id=user_id,
            listing_id=best_listing.id,
            variant_id=variant.id if variant else None,
            order_no=f"SIM{now.strftime('%Y%m%d%H')}{uuid4().hex[:10].upper()}",
            buyer_name=buyer.nickname,
            buyer_payment=payment,
            order_type="order",
            type_bucket="toship",
            process_status="processing",
            shipping_priority="today",
            shipping_channel=_resolve_shipping_channel(best_listing, rng),
            destination=buyer.city or "吉隆坡",
            countdown_text="请在24小时内处理",
            action_text="查看详情",
            ship_by_date=now + timedelta(days=1),
            ship_by_at=now + timedelta(days=1),
            stock_fulfillment_status="backorder" if total_shortfall_qty > 0 else "in_stock",
            backorder_qty=total_shortfall_qty,
            must_restock_before_at=(now + timedelta(hours=BACKORDER_GRACE_GAME_HOURS)) if total_shortfall_qty > 0 else None,
            marketing_campaign_type=applied_campaign["campaign_type"] if applied_campaign else None,
            marketing_campaign_id=applied_campaign["campaign_id"] if applied_campaign else None,
            marketing_campaign_name_snapshot=applied_campaign["campaign_name"] if applied_campaign else None,
        )
        db.add(order)
        db.flush()
        for line in order_lines:
            listing_for_line: ShopeeListing = line["listing"]
            variant_for_line: ShopeeListingVariant | None = line["variant"]
            db.add(
                ShopeeOrderItem(
                    order_id=order.id,
                    listing_id=int(listing_for_line.id),
                    variant_id=int(variant_for_line.id) if variant_for_line else None,
                    product_id=int(line["product_id"]) if line["product_id"] is not None else None,
                    product_name=listing_for_line.title,
                    variant_name=(variant_for_line.option_value if variant_for_line else "") or "",
                    quantity=int(line["quantity"]),
                    unit_price=int(line["unit_price"]),
                    image_url=line["image_url"],
                    stock_fulfillment_status="backorder" if int(line["shortfall_qty"]) > 0 else "in_stock",
                    backorder_qty=int(line["shortfall_qty"]),
                )
            )
            db.add(
                InventoryStockMovement(
                    run_id=run_id,
                    user_id=user_id,
                    product_id=int(line["product_id"]) if line["product_id"] is not None else None,
                    listing_id=int(listing_for_line.id),
                    variant_id=int(variant_for_line.id) if variant_for_line else None,
                    inventory_lot_id=None,
                    biz_order_id=int(order.id),
                    movement_type="order_reserve",
                    qty_delta_on_hand=-int(line.get("reserved_qty") or 0),
                    qty_delta_reserved=int(line.get("reserved_qty") or 0),
                    qty_delta_backorder=int(line["shortfall_qty"]),
                    biz_ref=order.order_no,
                    remark="Shopee订单模拟占用库存/形成待补货",
                )
            )
        generated_order_count += 1
        if bundle_applied and bundle_hit:
            buyer_bundle_key = (str(buyer.nickname or ""), int(bundle_hit["campaign_id"]))
            buyer_bundle_order_counts[buyer_bundle_key] = buyer_bundle_order_counts.get(buyer_bundle_key, 0) + 1
        journey["decision"] = "generated_order"
        journey["reason"] = "order_roll_le_order_prob"
        journey["generated_order"] = {
            "order_no": order.order_no,
            "listing_id": best_listing.id,
            "product_title": best_listing.title,
            "listing_sku": best_listing.sku_code,
            "variant_sku": variant.sku if variant else None,
            "variant_name": variant.option_value if variant else "",
            "quantity": total_quantity,
            "unit_price": unit_price,
            "buyer_payment": payment,
            "effective_price": effective_price,
            "price_gap": round(selected_price_gap, 4),
            "price_score": round(selected_price_score, 4),
            "discount_hit": bool(applied_campaign and applied_campaign["campaign_type"] == "discount"),
            "discount_campaign_id": hit_discount["campaign_id"] if hit_discount else None,
            "discount_campaign_name": hit_discount["campaign_name"] if hit_discount else None,
            "bundle_applied": bundle_applied,
            "bundle_campaign_id": bundle_hit["campaign_id"] if bundle_hit else None,
            "bundle_campaign_name": bundle_hit["campaign_name"] if bundle_hit else None,
            "bundle_qty": total_quantity if bundle_applied else None,
            "bundle_items": [
                {
                    "listing_id": int(line["listing"].id),
                    "variant_id": int(line["variant"].id) if line["variant"] else None,
                    "product_title": line["listing"].title,
                    "variant_name": line["variant"].option_value if line["variant"] else "",
                    "quantity": int(line["quantity"]),
                    "unit_price": int(line["unit_price"]),
                    "backorder_qty": int(line["shortfall_qty"]),
                }
                for line in order_lines
            ] if bundle_applied else [],
            "base_order_prob": round(base_order_prob, 4),
            "no_discount_order_prob": round(no_discount_order_prob, 4),
            "discount_order_prob": round(discount_order_prob, 4),
            "bundle_order_prob": round(bundle_order_prob, 4) if bundle_order_prob is not None else None,
            "stock_fulfillment_status": "backorder" if total_shortfall_qty > 0 else "in_stock",
            "backorder_qty": total_shortfall_qty,
        }
        buyer_journeys.append(journey)

    debug_payload = {
        "buyer_journeys": buyer_journeys,
        "summary": {
            "hour": hour,
            "weekday_idx": weekday_idx,
            "buyers_total": len(buyers),
            "products_total": len(sellable_products),
        },
    }
    log_row = ShopeeOrderGenerationLog(
        run_id=run_id,
        user_id=user_id,
        tick_time=now,
        active_buyer_count=active_buyer_count,
        candidate_product_count=len(sellable_products),
        generated_order_count=generated_order_count,
        skip_reasons_json=json.dumps(skip_reasons, ensure_ascii=False),
        debug_payload_json=json.dumps(debug_payload, ensure_ascii=False),
    )
    db.add(log_row)
    db.commit()

    return {
        "tick_time": now,
        "active_buyer_count": active_buyer_count,
        "candidate_product_count": len(sellable_products),
        "generated_order_count": generated_order_count,
        "skip_reasons": skip_reasons,
        "buyer_journeys": buyer_journeys,
    }

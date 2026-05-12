from __future__ import annotations

from datetime import datetime, timedelta
import json
import os
import random
from typing import Any
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.core.cache import cache_delete_prefix
from app.models import (
    InventoryStockMovement,
    ShopeeAddonCampaign,
    ShopeeDiscountCampaign,
    ShopeeFlashSaleCampaign,
    ShopeeFlashSaleCampaignItem,
    ShopeeBuyerFollowState,
    ShopeeFlashSaleTrafficEvent,
    ShopeeFollowVoucherCampaign,
    ShopeeLiveVoucherCampaign,
    ShopeePrivateVoucherCampaign,
    ShopeeProductVoucherCampaign,
    ShopeeShopVoucherCampaign,
    ShopeeVideoVoucherCampaign,
    ShopeeListing,
    ShopeeListingVariant,
    ShopeeOrder,
    ShopeeOrderGenerationLog,
    ShopeeOrderItem,
    ShopeeShippingFeePromotionCampaign,
    SimBuyerProfile,
    WarehouseLandmark,
    WarehouseStrategy,
)
from app.services.inventory_lot_sync import get_lot_available_qty, release_reserved_inventory_lots, reserve_inventory_lots
from app.services.shopee_fulfillment import calc_shipping_cost, haversine_km

BACKORDER_GRACE_GAME_HOURS = 48
FLASH_SALE_PROBABILITY_CAP = 0.85
FLASH_SALE_SLOT_MULTIPLIERS = {
    "00_12": 2.00,
    "12_18": 2.20,
    "18_21": 2.80,
    "21_00": 2.50,
}
FLASH_SALE_TRAFFIC_SLOT_MULTIPLIERS = {
    "00_12": 1.00,
    "12_18": 1.15,
    "18_21": 1.45,
    "21_00": 1.30,
}
FLASH_SALE_BASE_VIEW_PROB = 0.30
FLASH_SALE_BASE_CLICK_PROB = 0.14
FLASH_SALE_VIEW_PROB_CAP = 0.75
FLASH_SALE_CLICK_PROB_CAP = 0.45
FLASH_SALE_TRAFFIC_MAX_ITEMS_PER_BUYER = 3
FLASH_SALE_TRAFFIC_MAX_EVENTS_PER_TICK = 200
REDIS_PREFIX = os.getenv("REDIS_PREFIX", "cbec")
SHIPPING_FEE_PROMOTION_CHANNEL_MAP = {
    "标准快递": "standard",
    "快捷快递": "standard",
    "标准大件": "bulky",
}
BUYER_CITY_COORDS = {
    "MY-KUL": (3.1390, 101.6869),
    "MY-SGR": (3.0738, 101.5183),
    "MY-PNG": (5.4141, 100.3288),
    "MY-JHB": (1.4927, 103.7414),
    "MY-IPH": (4.5975, 101.0901),
    "MY-MLK": (2.1896, 102.2501),
    "MY-KDH": (6.1184, 100.3685),
    "MY-SBH": (5.9804, 116.0735),
    "MY-SWK": (1.5533, 110.3592),
    "MY-SAM": (3.0733, 101.5185),
}


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


def _align_compare_time(current_tick: datetime, value: datetime) -> datetime:
    if current_tick.tzinfo is None and value.tzinfo is not None:
        return value.replace(tzinfo=None)
    if current_tick.tzinfo is not None and value.tzinfo is None:
        return value.replace(tzinfo=current_tick.tzinfo)
    return value


def _resolve_buyer_latlng(db: Session, buyer: SimBuyerProfile, destination: str | None) -> tuple[float, float]:
    if buyer.lat is not None and buyer.lng is not None:
        return float(buyer.lat), float(buyer.lng)
    if buyer.city_code and buyer.city_code in BUYER_CITY_COORDS:
        return BUYER_CITY_COORDS[buyer.city_code]
    for code, coords in BUYER_CITY_COORDS.items():
        if destination and code.endswith(destination[:3].upper()):
            return coords
    return BUYER_CITY_COORDS["MY-KUL"]


def _resolve_warehouse_latlng(db: Session, *, run_id: int, user_id: int) -> tuple[float, float]:
    strategy = (
        db.query(WarehouseStrategy)
        .filter(WarehouseStrategy.run_id == run_id, WarehouseStrategy.user_id == user_id)
        .order_by(WarehouseStrategy.id.desc())
        .first()
    )
    if strategy:
        point = (
            db.query(WarehouseLandmark)
            .filter(
                WarehouseLandmark.market == (strategy.market or "MY"),
                WarehouseLandmark.warehouse_mode == strategy.warehouse_mode,
                WarehouseLandmark.warehouse_location == strategy.warehouse_location,
                WarehouseLandmark.is_active == True,
            )
            .first()
        )
        if point:
            return float(point.lat), float(point.lng)
    fallback = db.query(WarehouseLandmark).filter(WarehouseLandmark.market == "MY", WarehouseLandmark.is_active == True).order_by(WarehouseLandmark.sort_order.asc(), WarehouseLandmark.id.asc()).first()
    if fallback:
        return float(fallback.lat), float(fallback.lng)
    return BUYER_CITY_COORDS["MY-KUL"]


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


def _flash_sale_traffic_price_affordability(*, price: float, buyer_purchase_power: float) -> float:
    target_price = 30 + _clamp(buyer_purchase_power, 0.0, 1.0) * 300
    if price <= target_price:
        return _clamp(1.1 + (target_price - price) / max(target_price, 1.0) * 0.1, 1.0, 1.2)
    return _clamp(1.0 - (price - target_price) / max(target_price, 1.0) * 0.6, 0.5, 1.0)


def _simulate_flash_sale_traffic_for_buyer(
    db: Session,
    *,
    run_id: int,
    user_id: int,
    tick_time: datetime,
    buyer: SimBuyerProfile,
    preferred_categories: list[str],
    flash_sale_map: dict[tuple[int, int | None], dict[str, Any]],
    listing_by_id: dict[int, ShopeeListing],
    rng: random.Random,
    existing_event_keys: set[tuple[int, str, str]],
    remaining_event_slots: int,
) -> dict[str, int]:
    if remaining_event_slots <= 0 or not flash_sale_map:
        return {"view_count": 0, "click_count": 0}

    buyer_code = str(buyer.buyer_code or buyer.nickname or "").strip()
    if not buyer_code:
        return {"view_count": 0, "click_count": 0}

    traffic_slot_multiplier = FLASH_SALE_TRAFFIC_SLOT_MULTIPLIERS.get(str(next(iter(flash_sale_map.values())).get("slot_key") or ""), 1.0)
    impulse = _clamp(float(buyer.impulse_level or 0.0), 0.0, 1.0)
    purchase_power = _clamp(float(buyer.purchase_power or 0.5), 0.0, 1.0)
    candidates = list(flash_sale_map.values())
    rng.shuffle(candidates)
    view_count = 0
    click_count = 0
    viewed_items = 0

    for item in candidates:
        if remaining_event_slots <= 0 or viewed_items >= FLASH_SALE_TRAFFIC_MAX_ITEMS_PER_BUYER:
            break
        campaign_item_id = int(item.get("campaign_item_id") or 0)
        listing_id = int(item.get("listing_id") or 0)
        if campaign_item_id <= 0 or listing_id <= 0:
            continue
        listing = listing_by_id.get(listing_id)
        category_match = _category_match_score(listing.category if listing else None, preferred_categories)
        interest_factor = _clamp(0.9 + category_match * 0.3, 0.8, 1.2)
        price_affordability = _flash_sale_traffic_price_affordability(price=float(item.get("flash_price") or 0), buyer_purchase_power=purchase_power)
        discount_attraction = _clamp(float(item.get("discount_boost") or 1.0), 1.0, 1.8)
        stock_factor = 1.0 if int(item.get("remaining_qty") or 0) > 0 else 0.0
        view_prob = _clamp(
            FLASH_SALE_BASE_VIEW_PROB * traffic_slot_multiplier * discount_attraction * price_affordability * stock_factor * interest_factor,
            0.0,
            FLASH_SALE_VIEW_PROB_CAP,
        )
        if rng.random() > view_prob:
            continue

        view_key = (campaign_item_id, buyer_code, "view")
        if view_key not in existing_event_keys:
            db.add(
                ShopeeFlashSaleTrafficEvent(
                    run_id=run_id,
                    user_id=user_id,
                    campaign_id=int(item["campaign_id"]),
                    campaign_item_id=campaign_item_id,
                    listing_id=listing_id,
                    variant_id=int(item["variant_id"]) if item.get("variant_id") is not None else None,
                    buyer_code=buyer_code,
                    event_type="view",
                    event_tick=tick_time,
                    source="simulator",
                )
            )
            existing_event_keys.add(view_key)
            view_count += 1
            remaining_event_slots -= 1
        viewed_items += 1

        if remaining_event_slots <= 0:
            break
        click_prob = _clamp(
            FLASH_SALE_BASE_CLICK_PROB * discount_attraction * price_affordability * (0.8 + impulse * 0.8),
            0.0,
            FLASH_SALE_CLICK_PROB_CAP,
        )
        if rng.random() > click_prob:
            continue
        click_key = (campaign_item_id, buyer_code, "click")
        if click_key not in existing_event_keys:
            db.add(
                ShopeeFlashSaleTrafficEvent(
                    run_id=run_id,
                    user_id=user_id,
                    campaign_id=int(item["campaign_id"]),
                    campaign_item_id=campaign_item_id,
                    listing_id=listing_id,
                    variant_id=int(item["variant_id"]) if item.get("variant_id") is not None else None,
                    buyer_code=buyer_code,
                    event_type="click",
                    event_tick=tick_time,
                    source="simulator",
                )
            )
            existing_event_keys.add(click_key)
            click_count += 1
            remaining_event_slots -= 1

    return {"view_count": view_count, "click_count": click_count}


def _serialize_voucher(
    row: ShopeeShopVoucherCampaign | ShopeeProductVoucherCampaign | ShopeePrivateVoucherCampaign | ShopeeLiveVoucherCampaign | ShopeeVideoVoucherCampaign | ShopeeFollowVoucherCampaign,
    voucher_type: str,
) -> dict[str, Any]:
    payload = {
        "voucher_type": voucher_type,
        "campaign_id": int(row.id),
        "voucher_name": row.voucher_name,
        "voucher_code": row.voucher_code,
        "discount_type": row.discount_type,
        "discount_amount": float(row.discount_amount or 0),
        "discount_percent": float(row.discount_percent or 0),
        "max_discount_type": row.max_discount_type,
        "max_discount_amount": float(row.max_discount_amount or 0),
        "min_spend_amount": float(row.min_spend_amount or 0),
        "usage_limit": int(row.usage_limit or 0),
        "used_count": int(row.used_count or 0),
        "claimed_count": int(getattr(row, "claimed_count", 0) or 0),
        "per_buyer_limit": int(row.per_buyer_limit or 1),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
    if voucher_type in {"private_voucher", "live_voucher", "video_voucher", "follow_voucher"}:
        payload["applicable_scope"] = str(getattr(row, "applicable_scope", "all_products") or "all_products")
    if voucher_type == "follow_voucher":
        payload["claim_start_at"] = row.claim_start_at.isoformat() if row.claim_start_at else None
        payload["claim_end_at"] = row.claim_end_at.isoformat() if row.claim_end_at else None
        payload["valid_days_after_claim"] = int(row.valid_days_after_claim or 7)
    return payload


def _load_ongoing_voucher_context(db: Session, *, run_id: int, user_id: int, tick_time: datetime) -> dict[str, Any]:
    shop_rows = (
        db.query(ShopeeShopVoucherCampaign)
        .filter(
            ShopeeShopVoucherCampaign.run_id == run_id,
            ShopeeShopVoucherCampaign.user_id == user_id,
            ShopeeShopVoucherCampaign.reward_type == "discount",
        )
        .order_by(ShopeeShopVoucherCampaign.id.asc())
        .all()
    )
    product_rows = (
        db.query(ShopeeProductVoucherCampaign)
        .options(selectinload(ShopeeProductVoucherCampaign.items))
        .filter(
            ShopeeProductVoucherCampaign.run_id == run_id,
            ShopeeProductVoucherCampaign.user_id == user_id,
            ShopeeProductVoucherCampaign.reward_type == "discount",
        )
        .order_by(ShopeeProductVoucherCampaign.id.asc())
        .all()
    )
    private_rows = (
        db.query(ShopeePrivateVoucherCampaign)
        .options(selectinload(ShopeePrivateVoucherCampaign.items))
        .filter(
            ShopeePrivateVoucherCampaign.run_id == run_id,
            ShopeePrivateVoucherCampaign.user_id == user_id,
            ShopeePrivateVoucherCampaign.reward_type == "discount",
        )
        .order_by(ShopeePrivateVoucherCampaign.id.asc())
        .all()
    )
    live_rows = (
        db.query(ShopeeLiveVoucherCampaign)
        .options(selectinload(ShopeeLiveVoucherCampaign.items))
        .filter(
            ShopeeLiveVoucherCampaign.run_id == run_id,
            ShopeeLiveVoucherCampaign.user_id == user_id,
            ShopeeLiveVoucherCampaign.reward_type == "discount",
        )
        .order_by(ShopeeLiveVoucherCampaign.id.asc())
        .all()
    )
    video_rows = (
        db.query(ShopeeVideoVoucherCampaign)
        .options(selectinload(ShopeeVideoVoucherCampaign.items))
        .filter(
            ShopeeVideoVoucherCampaign.run_id == run_id,
            ShopeeVideoVoucherCampaign.user_id == user_id,
            ShopeeVideoVoucherCampaign.reward_type == "discount",
        )
        .order_by(ShopeeVideoVoucherCampaign.id.asc())
        .all()
    )
    follow_rows = (
        db.query(ShopeeFollowVoucherCampaign)
        .filter(
            ShopeeFollowVoucherCampaign.run_id == run_id,
            ShopeeFollowVoucherCampaign.user_id == user_id,
            ShopeeFollowVoucherCampaign.reward_type == "discount",
        )
        .order_by(ShopeeFollowVoucherCampaign.id.asc())
        .all()
    )
    shop_vouchers: list[dict[str, Any]] = []
    product_vouchers_by_listing: dict[tuple[int, int | None], list[dict[str, Any]]] = {}
    private_vouchers: list[dict[str, Any]] = []
    private_vouchers_by_listing: dict[tuple[int, int | None], list[dict[str, Any]]] = {}
    live_vouchers: list[dict[str, Any]] = []
    live_vouchers_by_listing: dict[tuple[int, int | None], list[dict[str, Any]]] = {}
    video_vouchers: list[dict[str, Any]] = []
    video_vouchers_by_listing: dict[tuple[int, int | None], list[dict[str, Any]]] = {}
    follow_vouchers: list[dict[str, Any]] = []
    campaign_by_key: dict[
        tuple[str, int],
        ShopeeShopVoucherCampaign | ShopeeProductVoucherCampaign | ShopeePrivateVoucherCampaign | ShopeeLiveVoucherCampaign | ShopeeVideoVoucherCampaign | ShopeeFollowVoucherCampaign,
    ] = {}

    for row in shop_rows:
        if _align_compare_time(tick_time, row.start_at) > tick_time or _align_compare_time(tick_time, row.end_at) <= tick_time:
            continue
        if int(row.used_count or 0) >= int(row.usage_limit or 0):
            continue
        voucher = _serialize_voucher(row, "shop_voucher")
        shop_vouchers.append(voucher)
        campaign_by_key[("shop_voucher", int(row.id))] = row

    for row in product_rows:
        if _align_compare_time(tick_time, row.start_at) > tick_time or _align_compare_time(tick_time, row.end_at) <= tick_time:
            continue
        if int(row.used_count or 0) >= int(row.usage_limit or 0):
            continue
        voucher = _serialize_voucher(row, "product_voucher")
        for item in sorted(row.items or [], key=lambda item_row: item_row.id):
            key = (int(item.listing_id), int(item.variant_id) if item.variant_id is not None else None)
            product_vouchers_by_listing.setdefault(key, []).append(voucher)
        campaign_by_key[("product_voucher", int(row.id))] = row

    for row in private_rows:
        if _align_compare_time(tick_time, row.start_at) > tick_time or _align_compare_time(tick_time, row.end_at) <= tick_time:
            continue
        if int(row.used_count or 0) >= int(row.usage_limit or 0):
            continue
        voucher = _serialize_voucher(row, "private_voucher")
        if str(row.applicable_scope or "all_products") == "selected_products":
            for item in sorted(row.items or [], key=lambda item_row: item_row.id):
                key = (int(item.listing_id), int(item.variant_id) if item.variant_id is not None else None)
                private_vouchers_by_listing.setdefault(key, []).append(voucher)
        else:
            private_vouchers.append(voucher)
        campaign_by_key[("private_voucher", int(row.id))] = row

    for row in live_rows:
        if _align_compare_time(tick_time, row.start_at) > tick_time or _align_compare_time(tick_time, row.end_at) <= tick_time:
            continue
        if int(row.used_count or 0) >= int(row.usage_limit or 0):
            continue
        voucher = _serialize_voucher(row, "live_voucher")
        if str(row.applicable_scope or "all_products") == "selected_products":
            for item in sorted(row.items or [], key=lambda item_row: item_row.id):
                key = (int(item.listing_id), int(item.variant_id) if item.variant_id is not None else None)
                live_vouchers_by_listing.setdefault(key, []).append(voucher)
        else:
            live_vouchers.append(voucher)
        campaign_by_key[("live_voucher", int(row.id))] = row

    for row in video_rows:
        if _align_compare_time(tick_time, row.start_at) > tick_time or _align_compare_time(tick_time, row.end_at) <= tick_time:
            continue
        if int(row.used_count or 0) >= int(row.usage_limit or 0):
            continue
        voucher = _serialize_voucher(row, "video_voucher")
        if str(row.applicable_scope or "all_products") == "selected_products":
            for item in sorted(row.items or [], key=lambda item_row: item_row.id):
                key = (int(item.listing_id), int(item.variant_id) if item.variant_id is not None else None)
                video_vouchers_by_listing.setdefault(key, []).append(voucher)
        else:
            video_vouchers.append(voucher)
        campaign_by_key[("video_voucher", int(row.id))] = row

    for row in follow_rows:
        if str(row.status or "") == "stopped":
            continue
        if _align_compare_time(tick_time, row.claim_start_at) > tick_time:
            continue
        if int(row.used_count or 0) >= int(row.usage_limit or 0):
            continue
        if str(row.applicable_scope or "all_products") != "all_products":
            continue
        follow_vouchers.append(_serialize_voucher(row, "follow_voucher"))
        campaign_by_key[("follow_voucher", int(row.id))] = row

    return {
        "shop_vouchers": shop_vouchers,
        "product_vouchers_by_listing": product_vouchers_by_listing,
        "private_vouchers": private_vouchers,
        "private_vouchers_by_listing": private_vouchers_by_listing,
        "live_vouchers": live_vouchers,
        "live_vouchers_by_listing": live_vouchers_by_listing,
        "video_vouchers": video_vouchers,
        "video_vouchers_by_listing": video_vouchers_by_listing,
        "follow_vouchers": follow_vouchers,
        "campaign_by_key": campaign_by_key,
    }


def _calculate_voucher_discount(voucher: dict[str, Any], order_subtotal: float) -> float:
    if order_subtotal < float(voucher.get("min_spend_amount") or 0):
        return 0.0
    if str(voucher.get("discount_type") or "") == "percent":
        discount = order_subtotal * float(voucher.get("discount_percent") or 0) / 100
        if str(voucher.get("max_discount_type") or "") == "set_amount":
            max_discount = float(voucher.get("max_discount_amount") or 0)
            if max_discount > 0:
                discount = min(discount, max_discount)
    else:
        discount = float(voucher.get("discount_amount") or 0)
    return round(max(0.0, min(discount, max(order_subtotal - 1, 0.0))), 2)


def _candidate_product_vouchers(voucher_context: dict[str, Any], *, listing_id: int, variant_id: int | None) -> list[dict[str, Any]]:
    product_map = voucher_context.get("product_vouchers_by_listing") or {}
    return list(product_map.get((listing_id, variant_id), [])) + list(product_map.get((listing_id, None), []))


def _candidate_private_vouchers(voucher_context: dict[str, Any], *, listing_id: int, variant_id: int | None) -> list[dict[str, Any]]:
    private_map = voucher_context.get("private_vouchers_by_listing") or {}
    return (
        list(voucher_context.get("private_vouchers") or [])
        + list(private_map.get((listing_id, variant_id), []))
        + list(private_map.get((listing_id, None), []))
    )


def _candidate_content_vouchers(voucher_context: dict[str, Any], *, voucher_type: str, listing_id: int, variant_id: int | None) -> list[dict[str, Any]]:
    if voucher_type == "live_voucher":
        voucher_map = voucher_context.get("live_vouchers_by_listing") or {}
        all_product_vouchers = list(voucher_context.get("live_vouchers") or [])
    else:
        voucher_map = voucher_context.get("video_vouchers_by_listing") or {}
        all_product_vouchers = list(voucher_context.get("video_vouchers") or [])
    return all_product_vouchers + list(voucher_map.get((listing_id, variant_id), [])) + list(voucher_map.get((listing_id, None), []))


def _buyer_has_private_voucher_access(
    *,
    buyer: SimBuyerProfile | None,
    voucher: dict[str, Any],
    order_subtotal: float,
    private_access_cache: dict[tuple[str, int], dict[str, Any]],
    rng: random.Random,
) -> dict[str, Any]:
    buyer_name = str(getattr(buyer, "nickname", "") or "")
    campaign_id = int(voucher.get("campaign_id") or 0)
    key = (buyer_name, campaign_id)
    if key in private_access_cache:
        return private_access_cache[key]

    price_sensitivity = _clamp(float(getattr(buyer, "price_sensitivity", 0.5) or 0.5), 0.0, 1.0)
    impulse_level = _clamp(float(getattr(buyer, "impulse_level", 0.3) or 0.3), 0.0, 1.0)
    base_intent = _clamp(float(getattr(buyer, "base_buy_intent", 0.2) or 0.2), 0.0, 1.0)
    preview_discount = _calculate_voucher_discount(voucher, max(float(order_subtotal or 0), 1.0))
    voucher_savings_rate = preview_discount / max(float(order_subtotal or 0), 1.0)
    access_prob = _clamp(
        0.10 + price_sensitivity * 0.18 + base_intent * 0.12 + impulse_level * 0.15 + voucher_savings_rate * 0.20,
        0.05,
        0.45,
    )
    hit = rng.random() <= access_prob
    result = {
        "private_access_checked": True,
        "private_access_hit": hit,
        "private_access_prob": round(access_prob, 4),
        "private_access_reason": "simulated_private_audience" if hit else "not_private_access",
    }
    private_access_cache[key] = result
    return result


def _buyer_has_follow_voucher_access(
    *,
    db: Session,
    run_id: int,
    user_id: int,
    buyer: SimBuyerProfile | None,
    voucher: dict[str, Any],
    order_subtotal: float,
    tick_time: datetime,
    follow_state_by_buyer: dict[str, ShopeeBuyerFollowState],
    follow_access_cache: dict[tuple[str, int], dict[str, Any]],
    campaign_by_key: dict[tuple[str, int], Any],
    rng: random.Random,
) -> dict[str, Any]:
    buyer_name = str(getattr(buyer, "nickname", "") or "")
    campaign_id = int(voucher.get("campaign_id") or 0)
    key = (buyer_name, campaign_id)
    if key in follow_access_cache:
        return follow_access_cache[key]

    state = follow_state_by_buyer.get(buyer_name)
    already_following = bool(state and state.is_following)
    valid_until = None
    if state and state.first_followed_at:
        valid_until = state.first_followed_at + timedelta(days=int(voucher.get("valid_days_after_claim") or 7))
    if already_following:
        follow_hit = int(state.source_campaign_id or 0) == campaign_id and valid_until is not None and _align_compare_time(tick_time, valid_until) > tick_time
        result = {
            "follow_access_checked": True,
            "follow_access_hit": follow_hit,
            "follow_access_prob": None,
            "already_following_before_tick": True,
            "claim_game_time": state.first_followed_at.isoformat() if state.first_followed_at else None,
            "valid_until_game_time": valid_until.isoformat() if valid_until else None,
            "follow_access_reason": "existing_follow_voucher_valid" if follow_hit else "already_following",
        }
        follow_access_cache[key] = result
        return result

    price_sensitivity = _clamp(float(getattr(buyer, "price_sensitivity", 0.5) or 0.5), 0.0, 1.0)
    impulse_level = _clamp(float(getattr(buyer, "impulse_level", 0.3) or 0.3), 0.0, 1.0)
    base_intent = _clamp(float(getattr(buyer, "base_buy_intent", 0.2) or 0.2), 0.0, 1.0)
    preview_discount = _calculate_voucher_discount(voucher, max(float(order_subtotal or 0), 1.0))
    voucher_savings_rate = preview_discount / max(float(order_subtotal or 0), 1.0)
    access_prob = _clamp(
        0.08 + price_sensitivity * 0.20 + base_intent * 0.12 + impulse_level * 0.16 + voucher_savings_rate * 0.18,
        0.03,
        0.48,
    )
    claim_window_open = _align_compare_time(tick_time, datetime.fromisoformat(str(voucher.get("claim_end_at")))) > tick_time if voucher.get("claim_end_at") else True
    can_claim = claim_window_open and int(voucher.get("claimed_count") or 0) < int(voucher.get("usage_limit") or 0)
    follow_hit = can_claim and rng.random() <= access_prob
    valid_until = tick_time + timedelta(days=int(voucher.get("valid_days_after_claim") or 7)) if follow_hit else None
    if follow_hit:
        state = ShopeeBuyerFollowState(
            run_id=run_id,
            user_id=user_id,
            buyer_name=buyer_name,
            is_following=True,
            first_followed_at=tick_time,
            follow_source="follow_voucher",
            source_campaign_id=campaign_id,
        )
        db.add(state)
        follow_state_by_buyer[buyer_name] = state
        campaign = campaign_by_key.get(("follow_voucher", campaign_id))
        if campaign is not None:
            campaign.claimed_count = int(campaign.claimed_count or 0) + 1
        voucher["claimed_count"] = int(voucher.get("claimed_count") or 0) + 1
    result = {
        "follow_access_checked": True,
        "follow_access_hit": follow_hit,
        "follow_access_prob": round(access_prob, 4),
        "already_following_before_tick": False,
        "claim_game_time": tick_time.isoformat() if follow_hit else None,
        "valid_until_game_time": valid_until.isoformat() if valid_until else None,
        "follow_access_reason": "simulated_new_follower" if follow_hit else ("claim_window_closed" if not claim_window_open else "usage_limit_reached" if not can_claim else "not_followed"),
    }
    follow_access_cache[key] = result
    return result



def _buyer_has_content_voucher_access(
    *,
    buyer: SimBuyerProfile | None,
    voucher: dict[str, Any],
    order_subtotal: float,
    content_access_cache: dict[tuple[str, str, int], dict[str, Any]],
    rng: random.Random,
) -> dict[str, Any]:
    buyer_name = str(getattr(buyer, "nickname", "") or "")
    voucher_type = str(voucher.get("voucher_type") or "")
    campaign_id = int(voucher.get("campaign_id") or 0)
    key = (buyer_name, voucher_type, campaign_id)
    if key in content_access_cache:
        return content_access_cache[key]

    scene = "live" if voucher_type == "live_voucher" else "video"
    price_sensitivity = _clamp(float(getattr(buyer, "price_sensitivity", 0.5) or 0.5), 0.0, 1.0)
    impulse_level = _clamp(float(getattr(buyer, "impulse_level", 0.3) or 0.3), 0.0, 1.0)
    base_intent = _clamp(float(getattr(buyer, "base_buy_intent", 0.2) or 0.2), 0.0, 1.0)
    preview_discount = _calculate_voucher_discount(voucher, max(float(order_subtotal or 0), 1.0))
    voucher_savings_rate = preview_discount / max(float(order_subtotal or 0), 1.0)
    if voucher_type == "live_voucher":
        access_prob = _clamp(0.192 + impulse_level * 0.24 + price_sensitivity * 0.144 + base_intent * 0.12 + voucher_savings_rate * 0.216, 0.096, 0.66)
    else:
        access_prob = _clamp(0.156 + impulse_level * 0.168 + price_sensitivity * 0.144 + base_intent * 0.12 + voucher_savings_rate * 0.216, 0.084, 0.576)
    hit = rng.random() <= access_prob
    result = {
        "content_access_checked": True,
        "content_access_hit": hit,
        "content_access_prob": round(access_prob, 4),
        "content_scene": scene,
        "content_access_reason": f"simulated_{scene}_viewer" if hit else "not_content_access",
    }
    content_access_cache[key] = result
    return result


def _resolve_best_voucher_for_order(
    *,
    db: Session,
    run_id: int,
    user_id: int,
    tick_time: datetime,
    voucher_context: dict[str, Any],
    buyer: SimBuyerProfile,
    buyer_name: str,
    listing_id: int,
    variant_id: int | None,
    order_subtotal: float,
    buyer_voucher_usage_counts: dict[tuple[str, str, int], int],
    private_access_cache: dict[tuple[str, int], dict[str, Any]],
    content_access_cache: dict[tuple[str, str, int], dict[str, Any]],
    follow_state_by_buyer: dict[str, ShopeeBuyerFollowState],
    follow_access_cache: dict[tuple[str, int], dict[str, Any]],
    campaign_by_key: dict[tuple[str, int], Any],
    rng: random.Random,
    flash_sale_hit: bool,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    all_vouchers = (
        list(voucher_context.get("shop_vouchers") or [])
        + _candidate_product_vouchers(voucher_context, listing_id=listing_id, variant_id=variant_id)
        + _candidate_content_vouchers(voucher_context, voucher_type="live_voucher", listing_id=listing_id, variant_id=variant_id)
        + _candidate_content_vouchers(voucher_context, voucher_type="video_voucher", listing_id=listing_id, variant_id=variant_id)
        + _candidate_private_vouchers(voucher_context, listing_id=listing_id, variant_id=variant_id)
        + list(voucher_context.get("follow_vouchers") or [])
    )
    if flash_sale_hit:
        for voucher in all_vouchers:
            candidates.append({**voucher, "eligible": False, "reason": "flash_sale_excluded", "discount_amount": 0.0, "savings_rate": 0.0})
        return None, candidates

    for voucher in all_vouchers:
        voucher_type = str(voucher["voucher_type"])
        campaign_id = int(voucher["campaign_id"])
        reason = "eligible"
        discount = 0.0
        access_result: dict[str, Any] = {}
        if voucher_type == "private_voucher":
            access_result = _buyer_has_private_voucher_access(
                buyer=buyer,
                voucher=voucher,
                order_subtotal=order_subtotal,
                private_access_cache=private_access_cache,
                rng=rng,
            )
        elif voucher_type in {"live_voucher", "video_voucher"}:
            access_result = _buyer_has_content_voucher_access(
                buyer=buyer,
                voucher=voucher,
                order_subtotal=order_subtotal,
                content_access_cache=content_access_cache,
                rng=rng,
            )
        elif voucher_type == "follow_voucher":
            access_result = _buyer_has_follow_voucher_access(
                db=db,
                run_id=run_id,
                user_id=user_id,
                buyer=buyer,
                voucher=voucher,
                order_subtotal=order_subtotal,
                tick_time=tick_time,
                follow_state_by_buyer=follow_state_by_buyer,
                follow_access_cache=follow_access_cache,
                campaign_by_key=campaign_by_key,
                rng=rng,
            )
        if voucher_type == "follow_voucher" and int(voucher.get("claimed_count") or 0) >= int(voucher.get("usage_limit") or 0) and not bool(access_result.get("follow_access_hit")):
            reason = "usage_limit_reached"
        elif int(voucher.get("used_count") or 0) >= int(voucher.get("usage_limit") or 0):
            reason = "usage_limit_reached"
        elif buyer_voucher_usage_counts.get((buyer_name, voucher_type, campaign_id), 0) >= int(voucher.get("per_buyer_limit") or 1):
            reason = "buyer_limit_reached"
        elif voucher_type == "private_voucher" and not bool(access_result.get("private_access_hit")):
            reason = "not_private_access"
        elif voucher_type in {"live_voucher", "video_voucher"} and not bool(access_result.get("content_access_hit")):
            reason = "not_content_access"
        elif voucher_type == "follow_voucher" and not bool(access_result.get("follow_access_hit")):
            reason = str(access_result.get("follow_access_reason") or "not_followed")
        elif order_subtotal < float(voucher.get("min_spend_amount") or 0):
            reason = "below_min_spend"
        else:
            discount = _calculate_voucher_discount(voucher, order_subtotal)
            if discount <= 0:
                reason = "below_min_spend"
        candidates.append({
            **voucher,
            **access_result,
            "eligible": reason == "eligible",
            "reason": reason,
            "discount_amount": discount,
            "savings_rate": round(discount / max(order_subtotal, 1.0), 4),
        })
    eligible = [row for row in candidates if row.get("eligible")]
    if not eligible:
        return None, candidates
    selected = sorted(
        eligible,
        key=lambda row: (
            -float(row.get("discount_amount") or 0),
            {"product_voucher": 0, "live_voucher": 1, "video_voucher": 2, "private_voucher": 3, "follow_voucher": 4, "shop_voucher": 5}.get(str(row.get("voucher_type") or ""), 6),
            row.get("created_at") or "",
            int(row.get("campaign_id") or 0),
        ),
    )[0]
    return selected, candidates


def _apply_voucher_stats(
    *,
    voucher_context: dict[str, Any],
    selected_voucher: dict[str, Any] | None,
    buyer_name: str,
    buyer_payment: float,
    buyer_voucher_usage_counts: dict[tuple[str, str, int], int],
) -> None:
    if not selected_voucher:
        return
    voucher_type = str(selected_voucher["voucher_type"])
    campaign_id = int(selected_voucher["campaign_id"])
    key = (voucher_type, campaign_id)
    campaign = (voucher_context.get("campaign_by_key") or {}).get(key)
    if not campaign:
        return
    buyer_key = (buyer_name, voucher_type, campaign_id)
    previous_count = buyer_voucher_usage_counts.get(buyer_key, 0)
    campaign.used_count = int(campaign.used_count or 0) + 1
    campaign.order_count = int(campaign.order_count or 0) + 1
    campaign.sales_amount = float(campaign.sales_amount or 0) + float(buyer_payment)
    if previous_count <= 0:
        campaign.buyer_count = int(campaign.buyer_count or 0) + 1
    buyer_voucher_usage_counts[buyer_key] = previous_count + 1
    selected_voucher["used_count"] = int(selected_voucher.get("used_count") or 0) + 1


def _load_ongoing_shipping_fee_promotion_context(db: Session, *, run_id: int, user_id: int, tick_time: datetime) -> dict[str, Any]:
    campaigns = (
        db.query(ShopeeShippingFeePromotionCampaign)
        .options(
            selectinload(ShopeeShippingFeePromotionCampaign.channels),
            selectinload(ShopeeShippingFeePromotionCampaign.tiers),
        )
        .filter(
            ShopeeShippingFeePromotionCampaign.run_id == run_id,
            ShopeeShippingFeePromotionCampaign.user_id == user_id,
            ShopeeShippingFeePromotionCampaign.status.in_(("ongoing", "upcoming")),
        )
        .all()
    )
    active_campaigns = []
    for campaign in campaigns:
        if str(campaign.status or "") == "stopped":
            continue
        start_at = _align_compare_time(tick_time, campaign.start_at)
        end_at = _align_compare_time(tick_time, campaign.end_at) if campaign.end_at else None
        if tick_time < start_at or (end_at is not None and tick_time >= end_at):
            continue
        budget_limit = float(campaign.budget_limit or 0)
        budget_used = float(campaign.budget_used or 0)
        if str(campaign.budget_type or "") == "selected" and budget_used >= budget_limit:
            campaign.status = "budget_exhausted"
            continue
        channel_keys = {str(row.channel_key or "") for row in campaign.channels or [] if row.channel_key}
        tiers = sorted(
            [row for row in campaign.tiers or [] if float(row.min_spend_amount or 0) >= 0],
            key=lambda row: (float(row.min_spend_amount or 0), int(row.tier_index or 0), int(row.id or 0)),
        )
        if channel_keys and tiers:
            active_campaigns.append({"campaign": campaign, "channel_keys": channel_keys, "tiers": tiers})
    return {"campaigns": active_campaigns}


def _resolve_best_shipping_fee_promotion_for_order(
    *,
    shipping_promotion_context: dict[str, Any],
    shipping_channel: str,
    order_subtotal: float,
    original_shipping_fee: float,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    matched_channel_key = SHIPPING_FEE_PROMOTION_CHANNEL_MAP.get(shipping_channel)
    candidates: list[dict[str, Any]] = []
    if not matched_channel_key:
        return None, [{"reason": "shipping_channel_not_matched", "shipping_channel": shipping_channel}]
    if not (shipping_promotion_context.get("campaigns") or []):
        return None, [{"reason": "no_active_shipping_fee_promotion", "shipping_channel": shipping_channel}]

    for row in shipping_promotion_context.get("campaigns") or []:
        campaign = row["campaign"]
        if matched_channel_key not in row["channel_keys"]:
            candidates.append({
                "campaign_id": campaign.id,
                "promotion_name": campaign.promotion_name,
                "matched_channel": False,
                "reason": "shipping_channel_not_matched",
            })
            continue
        matched_tiers = [tier for tier in row["tiers"] if order_subtotal >= float(tier.min_spend_amount or 0)]
        if not matched_tiers:
            candidates.append({
                "campaign_id": campaign.id,
                "promotion_name": campaign.promotion_name,
                "matched_channel": True,
                "reason": "order_subtotal_below_min_spend",
            })
            continue
        tier = sorted(matched_tiers, key=lambda item: (float(item.min_spend_amount or 0), int(item.tier_index or 0), int(item.id or 0)), reverse=True)[0]
        if str(tier.fee_type or "") == "free_shipping":
            shipping_fee_after = 0.0
            discount = round(max(0.0, original_shipping_fee), 2)
        else:
            discount = round(min(original_shipping_fee, float(tier.fixed_fee_amount or 0)), 2)
            shipping_fee_after = round(original_shipping_fee - discount, 2)
        remaining_budget = None
        if str(campaign.budget_type or "") == "selected":
            remaining_budget = max(0.0, float(campaign.budget_limit or 0) - float(campaign.budget_used or 0))
            discount = round(min(discount, remaining_budget), 2)
            shipping_fee_after = round(original_shipping_fee - discount, 2)
        reason = "eligible" if discount > 0 else "zero_discount"
        candidates.append({
            "campaign_id": campaign.id,
            "promotion_name": campaign.promotion_name,
            "matched_channel": True,
            "matched_tier_index": int(tier.tier_index or 0),
            "min_spend_amount": float(tier.min_spend_amount or 0),
            "fee_type": tier.fee_type,
            "fixed_fee_amount": float(tier.fixed_fee_amount) if tier.fixed_fee_amount is not None else None,
            "original_shipping_fee": original_shipping_fee,
            "shipping_fee_after_promotion": shipping_fee_after,
            "shipping_discount_amount": discount,
            "remaining_budget": remaining_budget,
            "eligible": reason == "eligible",
            "reason": reason,
            "campaign": campaign,
            "tier": tier,
        })
    eligible = [row for row in candidates if row.get("eligible")]
    if not eligible:
        return None, candidates or [{"reason": "no_active_shipping_fee_promotion"}]
    selected = sorted(
        eligible,
        key=lambda row: (
            -float(row.get("shipping_discount_amount") or 0),
            -float(row.get("min_spend_amount") or 0),
            str(getattr(row.get("campaign"), "created_at", "") or ""),
            int(row.get("campaign_id") or 0),
        ),
    )[0]
    return selected, candidates


def _apply_shipping_fee_promotion_stats(
    *,
    selected_shipping_promotion: dict[str, Any] | None,
    buyer_name: str,
    order_subtotal: float,
    buyer_shipping_promotion_usage_counts: dict[tuple[str, int], int],
) -> None:
    if not selected_shipping_promotion:
        return
    campaign = selected_shipping_promotion.get("campaign")
    if not campaign:
        return
    discount = round(float(selected_shipping_promotion.get("shipping_discount_amount") or 0), 2)
    if discount <= 0:
        return
    campaign_id = int(selected_shipping_promotion.get("campaign_id") or 0)
    buyer_key = (buyer_name, campaign_id)
    previous_count = buyer_shipping_promotion_usage_counts.get(buyer_key, 0)
    campaign.budget_used = round(float(campaign.budget_used or 0) + discount, 2)
    campaign.order_count = int(campaign.order_count or 0) + 1
    if previous_count <= 0:
        campaign.buyer_count = int(campaign.buyer_count or 0) + 1
    buyer_shipping_promotion_usage_counts[buyer_key] = previous_count + 1
    campaign.sales_amount = round(float(campaign.sales_amount or 0) + float(order_subtotal or 0), 2)
    campaign.shipping_discount_amount = round(float(campaign.shipping_discount_amount or 0) + discount, 2)
    if str(campaign.budget_type or "") == "selected" and campaign.budget_limit is not None and float(campaign.budget_used or 0) >= float(campaign.budget_limit or 0):
        campaign.status = "budget_exhausted"
    selected_shipping_promotion["budget_used_after"] = float(campaign.budget_used or 0)
    selected_shipping_promotion["buyer_name"] = buyer_name


def _sanitize_shipping_fee_promotion_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in row.items() if key not in {"campaign", "tier"}}
        for row in candidates
    ]


def _invalidate_shipping_fee_promotion_simulation_cache(*, run_id: int, user_id: int) -> None:
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:shipping_fee_promotion:list:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:shipping_fee_promotion:active:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:orders:list:{run_id}:{user_id}:")


def _load_ongoing_flash_sale_map(db: Session, *, run_id: int, user_id: int, tick_time: datetime) -> dict[tuple[int, int | None], dict[str, Any]]:
    campaigns = (
        db.query(ShopeeFlashSaleCampaign)
        .options(selectinload(ShopeeFlashSaleCampaign.items))
        .filter(
            ShopeeFlashSaleCampaign.run_id == run_id,
            ShopeeFlashSaleCampaign.user_id == user_id,
            ShopeeFlashSaleCampaign.status == "active",
            ShopeeFlashSaleCampaign.start_tick <= tick_time,
            ShopeeFlashSaleCampaign.end_tick > tick_time,
        )
        .all()
    )
    flash_sale_map: dict[tuple[int, int | None], dict[str, Any]] = {}
    for campaign in campaigns:
        slot_multiplier = FLASH_SALE_SLOT_MULTIPLIERS.get(str(campaign.slot_key or ""), 2.0)
        for item in sorted(campaign.items or [], key=lambda row: row.id):
            if str(item.status or "") != "active":
                continue
            stock_limit = max(0, int(item.activity_stock_limit or 0))
            sold_qty = max(0, int(item.sold_qty or 0))
            remaining_qty = max(0, stock_limit - sold_qty)
            if remaining_qty <= 0 or float(item.flash_price or 0) <= 0:
                continue
            original_price = max(1.0, float(item.original_price or item.flash_price or 0))
            flash_price = max(1, int(round(float(item.flash_price or 0))))
            discount_boost = _clamp(1.0 + (original_price - float(flash_price)) / original_price, 1.0, 1.8)
            payload = {
                "campaign_id": int(campaign.id),
                "campaign_item_id": int(item.id),
                "campaign_name": campaign.campaign_name,
                "campaign_type": "flash_sale",
                "listing_id": int(item.listing_id or 0),
                "variant_id": int(item.variant_id) if item.variant_id is not None else None,
                "slot_key": campaign.slot_key,
                "slot_multiplier": float(slot_multiplier),
                "discount_boost": float(discount_boost),
                "original_price": original_price,
                "flash_price": flash_price,
                "activity_stock_limit": stock_limit,
                "sold_qty": sold_qty,
                "remaining_qty": remaining_qty,
                "purchase_limit_per_buyer": max(1, int(item.purchase_limit_per_buyer or 1)),
            }
            key = (int(item.listing_id or 0), int(item.variant_id) if item.variant_id is not None else None)
            flash_sale_map[key] = payload
    return flash_sale_map


def _resolve_flash_sale(
    listing: ShopeeListing,
    *,
    variant: ShopeeListingVariant | None,
    flash_sale_map: dict[tuple[int, int | None], dict[str, Any]],
) -> dict[str, Any] | None:
    listing_id = int(listing.id)
    variant_id = int(variant.id) if variant else None
    return flash_sale_map.get((listing_id, variant_id)) or flash_sale_map.get((listing_id, None))


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


def _load_ongoing_addon_map(db: Session, *, run_id: int, user_id: int, tick_time: datetime) -> dict[tuple[int, int | None], list[dict[str, Any]]]:
    campaigns = (
        db.query(ShopeeAddonCampaign)
        .options(selectinload(ShopeeAddonCampaign.main_items), selectinload(ShopeeAddonCampaign.reward_items))
        .filter(
            ShopeeAddonCampaign.run_id == run_id,
            ShopeeAddonCampaign.user_id == user_id,
            ShopeeAddonCampaign.campaign_status.in_(("ongoing", "upcoming")),
            ShopeeAddonCampaign.start_at <= tick_time,
            ShopeeAddonCampaign.end_at >= tick_time,
        )
        .all()
    )
    addon_map: dict[tuple[int, int | None], list[dict[str, Any]]] = {}
    for campaign in campaigns:
        reward_items = [
            {
                "listing_id": int(item.listing_id or 0),
                "variant_id": int(item.variant_id) if item.variant_id is not None else None,
                "product_id": int(item.product_id) if item.product_id is not None else None,
                "product_name": item.product_name_snapshot,
                "variant_name": item.variant_name_snapshot or "",
                "image_url": item.image_url_snapshot,
                "original_price": max(1.0, float(item.original_price_snapshot or 0)),
                "addon_price": float(item.addon_price) if item.addon_price is not None else None,
                "reward_qty": max(1, int(item.reward_qty or 1)),
                "stock_snapshot": max(0, int(item.stock_snapshot or 0)),
                "sort_order": int(item.sort_order or 0),
            }
            for item in sorted(campaign.reward_items or [], key=lambda row: (row.sort_order, row.id))
            if int(item.listing_id or 0) > 0 and max(0, int(item.stock_snapshot or 0)) > 0
        ]
        if not reward_items:
            continue
        campaign_payload = {
            "campaign_id": int(campaign.id),
            "campaign_name": campaign.campaign_name,
            "campaign_type": campaign.promotion_type,
            "promotion_type": campaign.promotion_type,
            "addon_purchase_limit": int(campaign.addon_purchase_limit or 1),
            "gift_min_spend": float(campaign.gift_min_spend or 0),
            "reward_items": reward_items,
        }
        for main_item in sorted(campaign.main_items or [], key=lambda row: (row.sort_order, row.id)):
            listing_id = int(main_item.listing_id or 0)
            if listing_id <= 0:
                continue
            key = (listing_id, int(main_item.variant_id) if main_item.variant_id is not None else None)
            addon_map.setdefault(key, []).append(campaign_payload)
    return addon_map



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


def _matching_addon_campaigns(
    addon_map: dict[tuple[int, int | None], list[dict[str, Any]]],
    *,
    listing_id: int,
    variant_id: int | None,
    promotion_type: str,
) -> list[dict[str, Any]]:
    return [
        campaign
        for campaign in (
            list(addon_map.get((listing_id, variant_id), []))
            + ([] if variant_id is None else list(addon_map.get((listing_id, None), [])))
        )
        if str(campaign.get("promotion_type") or "") == promotion_type
    ]



def _resolve_addon_attractiveness(
    campaign: dict[str, Any],
    *,
    main_unit_price: float,
    base_order_amount: float,
    buyer_budget: float,
    buyer_price_sensitivity: float,
    buyer_impulse_level: float,
) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_score = -1.0
    for item in list(campaign.get("reward_items") or []):
        addon_price = item.get("addon_price")
        if addon_price is None or float(addon_price) <= 0:
            continue
        original_price = max(1.0, float(item.get("original_price") or 0))
        addon_price = float(addon_price)
        if addon_price >= original_price:
            continue
        savings_rate = _clamp((original_price - addon_price) / original_price, 0.0, 0.95)
        stock_score = _clamp(float(item.get("stock_snapshot") or 0) / 30.0, 0.0, 1.0)
        item_score = (
            savings_rate * 0.45
            + stock_score * 0.15
            + buyer_price_sensitivity * savings_rate * 0.20
            + buyer_impulse_level * 0.20
        )
        if item_score > best_score:
            best_score = item_score
            best = {**item, "savings_rate": savings_rate, "item_score": item_score}
    if not best:
        return None

    addon_price = float(best["addon_price"])
    relative_price_factor = _clamp(float(main_unit_price) / max(addon_price, 0.01), 0.40, 1.60)
    budget_factor = _clamp(float(buyer_budget) / max(float(base_order_amount) + addon_price, 1.0), 0.45, 1.0)
    savings_rate = float(best["savings_rate"])
    attractiveness = _clamp(
        0.08
        + savings_rate * (0.45 + buyer_price_sensitivity * 0.35)
        + buyer_impulse_level * 0.10
        + (relative_price_factor - 1.0) * 0.04,
        0.0,
        0.55,
    ) * budget_factor
    return {
        "campaign": campaign,
        "reward_item": best,
        "addon_attractiveness": attractiveness,
        "addon_order_bonus": _clamp(attractiveness * 0.08, 0.0, 0.04),
        "addon_attach_prob": attractiveness,
        "savings_rate": savings_rate,
    }



def _resolve_gift_bonus(
    campaign: dict[str, Any],
    *,
    base_order_amount: float,
    buyer_budget: float,
    buyer_price_sensitivity: float,
    buyer_impulse_level: float,
) -> dict[str, Any] | None:
    threshold = float(campaign.get("gift_min_spend") or 0)
    if threshold <= 0:
        return None
    reward_items = list(campaign.get("reward_items") or [])
    gift_item = max(reward_items, key=lambda item: float(item.get("original_price") or 0), default=None)
    if not gift_item:
        return None
    shortfall = max(threshold - float(base_order_amount), 0.0)
    threshold_factor = 1.0 if shortfall <= 0 else _clamp(1.0 - shortfall / max(threshold, 0.01), 0.0, 1.0)
    gift_value_rate = _clamp(float(gift_item.get("original_price") or 0) / max(float(base_order_amount), 1.0), 0.0, 0.50)
    budget_factor = _clamp(float(buyer_budget) / max(threshold, float(base_order_amount), 1.0), 0.45, 1.0)
    gift_order_bonus = _clamp(
        threshold_factor * 0.04
        + gift_value_rate * (0.08 + buyer_price_sensitivity * 0.04)
        + buyer_impulse_level * 0.03,
        0.0,
        0.08,
    ) * budget_factor
    return {
        "campaign": campaign,
        "gift_item": gift_item,
        "gift_order_bonus": gift_order_bonus,
        "gift_threshold_shortfall": shortfall,
        "gift_value_rate": gift_value_rate,
    }



def _resolve_listing_line(
    db: Session,
    *,
    run_id: int,
    user_id: int,
    item: dict[str, Any],
    quantity: int,
    unit_price: int,
    line_role: str,
    campaign: dict[str, Any],
) -> dict[str, Any] | None:
    listing = (
        db.query(ShopeeListing)
        .options(selectinload(ShopeeListing.variants))
        .filter(
            ShopeeListing.run_id == run_id,
            ShopeeListing.user_id == user_id,
            ShopeeListing.id == int(item.get("listing_id") or 0),
            ShopeeListing.status == "live",
        )
        .first()
    )
    if not listing:
        return None
    variant: ShopeeListingVariant | None = None
    item_variant_id = int(item["variant_id"]) if item.get("variant_id") is not None else None
    if item_variant_id is not None:
        variant = next((row for row in list(listing.variants or []) if int(row.id) == item_variant_id), None)
        if not variant:
            return None
    else:
        variant = _pick_variant(listing)
    product_id = int(listing.product_id or item.get("product_id") or 0)
    available_stock = get_lot_available_qty(db, run_id=run_id, product_id=product_id) if product_id > 0 else (
        max(0, int(variant.stock or 0)) if variant else max(0, int(listing.stock_available or 0))
    )
    quantity = max(1, int(quantity or 1))
    if available_stock < quantity:
        return None
    return {
        "listing": listing,
        "variant": variant,
        "product_id": product_id if product_id > 0 else None,
        "quantity": quantity,
        "unit_price": max(0, int(unit_price)),
        "shortfall_qty": 0,
        "stock_consumed_planned": quantity,
        "image_url": item.get("image_url") or (variant.image_url if variant and (variant.image_url or "").strip() else listing.cover_url),
        "line_role": line_role,
        "marketing_campaign_type": campaign.get("campaign_type"),
        "marketing_campaign_id": campaign.get("campaign_id"),
        "marketing_campaign_name_snapshot": campaign.get("campaign_name"),
        "original_unit_price": float(item.get("original_price") or (variant.price if variant else listing.price) or 0),
        "discounted_unit_price": float(unit_price),
    }



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
    flash_sale_map: dict[tuple[int, int | None], dict[str, Any]] | None = None,
) -> tuple[ShopeeListingVariant | None, int, dict[str, Any] | None, float, float, dict[str, Any] | None]:
    variants = [
        row
        for row in sorted(list(listing.variants or []), key=lambda x: (x.sort_order, x.id))
        if _variant_sellable_cap(row) > 0
    ]
    if not variants:
        flash_sale = _resolve_flash_sale(listing, variant=None, flash_sale_map=flash_sale_map or {})
        base_price, discount = _resolve_effective_price(listing, variant=None, discount_map=discount_map)
        effective_price = int(flash_sale["flash_price"]) if flash_sale else base_price
        price_score, price_gap = _resolve_price_score(
            price=effective_price,
            target_price=30 + _clamp(float(buyer_purchase_power or 0.5), 0.0, 1.0) * 300,
            price_sensitivity=buyer_price_sensitivity,
        )
        return None, effective_price, None if flash_sale else discount, price_score, price_gap, flash_sale
    if len(variants) == 1:
        flash_sale = _resolve_flash_sale(listing, variant=variants[0], flash_sale_map=flash_sale_map or {})
        effective_price, discount = _resolve_effective_price(listing, variant=variants[0], discount_map=discount_map)
        if flash_sale:
            effective_price = int(flash_sale["flash_price"])
            discount = None
        price_score, price_gap = _resolve_price_score(
            price=effective_price,
            target_price=30 + _clamp(float(buyer_purchase_power or 0.5), 0.0, 1.0) * 300,
            price_sensitivity=buyer_price_sensitivity,
        )
        return variants[0], effective_price, discount, price_score, price_gap, flash_sale

    target_price = 30 + _clamp(float(buyer_purchase_power or 0.5), 0.0, 1.0) * 300
    best: ShopeeListingVariant | None = None
    best_discount: dict[str, Any] | None = None
    best_flash_sale: dict[str, Any] | None = None
    best_effective_price = 0
    best_price_score = 0.0
    best_price_gap = 0.0
    best_score = -1.0
    for row in variants:
        flash_sale = _resolve_flash_sale(listing, variant=row, flash_sale_map=flash_sale_map or {})
        effective_price, discount = _resolve_effective_price(listing, variant=row, discount_map=discount_map)
        if flash_sale:
            effective_price = int(flash_sale["flash_price"])
            discount = None
        price_score, price_gap = _resolve_price_score(
            price=effective_price,
            target_price=target_price,
            price_sensitivity=buyer_price_sensitivity,
        )
        stock_score = _clamp(float(_variant_sellable_cap(row)) / 30.0, 0.0, 1.0)
        jitter = rng.random() * 0.06
        flash_sale_bonus = 0.12 if flash_sale else 0.0
        score = 0.70 * price_score + 0.24 * stock_score + 0.06 * jitter + flash_sale_bonus
        if score > best_score:
            best_score = score
            best = row
            best_discount = discount
            best_flash_sale = flash_sale
            best_effective_price = effective_price
            best_price_score = price_score
            best_price_gap = price_gap
    return best, best_effective_price, best_discount, best_price_score, best_price_gap, best_flash_sale




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
    addon_map = _load_ongoing_addon_map(db, run_id=run_id, user_id=user_id, tick_time=now)
    bundle_map = _load_ongoing_bundle_map(db, run_id=run_id, user_id=user_id, tick_time=now)
    flash_sale_map = _load_ongoing_flash_sale_map(db, run_id=run_id, user_id=user_id, tick_time=now)
    voucher_context = _load_ongoing_voucher_context(db, run_id=run_id, user_id=user_id, tick_time=now)
    shipping_promotion_context = _load_ongoing_shipping_fee_promotion_context(db, run_id=run_id, user_id=user_id, tick_time=now)
    warehouse_latlng = _resolve_warehouse_latlng(db, run_id=run_id, user_id=user_id)

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

    flash_sale_campaign_ids = {
        int(item["campaign_id"])
        for item in flash_sale_map.values()
        if int(item.get("campaign_id") or 0) > 0
    }
    buyer_flash_sale_qty_counts: dict[tuple[str, int, int, int | None], int] = {}
    if flash_sale_campaign_ids:
        flash_sale_rows = (
            db.query(
                ShopeeOrder.buyer_name,
                ShopeeOrderItem.marketing_campaign_id,
                ShopeeOrderItem.listing_id,
                ShopeeOrderItem.variant_id,
                func.coalesce(func.sum(ShopeeOrderItem.quantity), 0),
            )
            .join(ShopeeOrderItem, ShopeeOrderItem.order_id == ShopeeOrder.id)
            .filter(
                ShopeeOrder.run_id == run_id,
                ShopeeOrder.user_id == user_id,
                ShopeeOrderItem.marketing_campaign_type == "flash_sale",
                ShopeeOrderItem.marketing_campaign_id.in_(flash_sale_campaign_ids),
            )
            .group_by(
                ShopeeOrder.buyer_name,
                ShopeeOrderItem.marketing_campaign_id,
                ShopeeOrderItem.listing_id,
                ShopeeOrderItem.variant_id,
            )
            .all()
        )
        buyer_flash_sale_qty_counts = {
            (str(buyer_name or ""), int(campaign_id), int(listing_id), int(variant_id) if variant_id is not None else None): int(qty or 0)
            for buyer_name, campaign_id, listing_id, variant_id, qty in flash_sale_rows
            if campaign_id is not None and listing_id is not None
        }

    all_voucher_rows = (
        list(voucher_context.get("shop_vouchers") or [])
        + [voucher for vouchers in (voucher_context.get("product_vouchers_by_listing") or {}).values() for voucher in vouchers]
        + list(voucher_context.get("private_vouchers") or [])
        + [voucher for vouchers in (voucher_context.get("private_vouchers_by_listing") or {}).values() for voucher in vouchers]
        + list(voucher_context.get("live_vouchers") or [])
        + [voucher for vouchers in (voucher_context.get("live_vouchers_by_listing") or {}).values() for voucher in vouchers]
        + list(voucher_context.get("video_vouchers") or [])
        + [voucher for vouchers in (voucher_context.get("video_vouchers_by_listing") or {}).values() for voucher in vouchers]
        + list(voucher_context.get("follow_vouchers") or [])
    )
    voucher_campaign_ids = {
        int(voucher["campaign_id"])
        for voucher in all_voucher_rows
        if int(voucher.get("campaign_id") or 0) > 0
    }
    buyer_voucher_usage_counts: dict[tuple[str, str, int], int] = {}
    private_access_cache: dict[tuple[str, int], dict[str, Any]] = {}
    content_access_cache: dict[tuple[str, str, int], dict[str, Any]] = {}
    follow_access_cache: dict[tuple[str, int], dict[str, Any]] = {}
    buyer_shipping_promotion_usage_counts: dict[tuple[str, int], int] = {}
    follow_state_rows = (
        db.query(ShopeeBuyerFollowState)
        .filter(
            ShopeeBuyerFollowState.run_id == run_id,
            ShopeeBuyerFollowState.user_id == user_id,
        )
        .all()
    )
    follow_state_by_buyer: dict[str, ShopeeBuyerFollowState] = {
        str(row.buyer_name or ""): row
        for row in follow_state_rows
        if row.buyer_name
    }
    shipping_promotion_campaign_ids = {
        int(row["campaign"].id)
        for row in shipping_promotion_context.get("campaigns") or []
        if row.get("campaign") and int(row["campaign"].id or 0) > 0
    }
    if shipping_promotion_campaign_ids:
        shipping_promotion_rows = (
            db.query(ShopeeOrder.buyer_name, ShopeeOrder.shipping_promotion_campaign_id, func.count(ShopeeOrder.id))
            .filter(
                ShopeeOrder.run_id == run_id,
                ShopeeOrder.user_id == user_id,
                ShopeeOrder.shipping_promotion_campaign_id.in_(shipping_promotion_campaign_ids),
            )
            .group_by(ShopeeOrder.buyer_name, ShopeeOrder.shipping_promotion_campaign_id)
            .all()
        )
        buyer_shipping_promotion_usage_counts = {
            (str(buyer_name or ""), int(campaign_id)): int(order_count or 0)
            for buyer_name, campaign_id, order_count in shipping_promotion_rows
            if campaign_id is not None
        }

    if voucher_campaign_ids:
        voucher_rows = (
            db.query(ShopeeOrder.buyer_name, ShopeeOrder.voucher_campaign_type, ShopeeOrder.voucher_campaign_id, func.count(ShopeeOrder.id))
            .filter(
                ShopeeOrder.run_id == run_id,
                ShopeeOrder.user_id == user_id,
                ShopeeOrder.voucher_campaign_type.in_(("shop_voucher", "product_voucher", "private_voucher", "live_voucher", "video_voucher", "follow_voucher")),
                ShopeeOrder.voucher_campaign_id.in_(voucher_campaign_ids),
            )
            .group_by(ShopeeOrder.buyer_name, ShopeeOrder.voucher_campaign_type, ShopeeOrder.voucher_campaign_id)
            .all()
        )
        buyer_voucher_usage_counts = {
            (str(buyer_name or ""), str(voucher_type or ""), int(campaign_id)): int(order_count or 0)
            for buyer_name, voucher_type, campaign_id, order_count in voucher_rows
            if voucher_type and campaign_id is not None
        }

    flash_sale_listing_ids = {int(item.get("listing_id") or 0) for item in flash_sale_map.values() if int(item.get("listing_id") or 0) > 0}
    flash_sale_listing_map = {int(row.id): row for row in sellable_products if int(row.id) in flash_sale_listing_ids}
    flash_sale_existing_event_keys: set[tuple[int, str, str]] = set()
    if flash_sale_map:
        event_rows = (
            db.query(
                ShopeeFlashSaleTrafficEvent.campaign_item_id,
                ShopeeFlashSaleTrafficEvent.buyer_code,
                ShopeeFlashSaleTrafficEvent.event_type,
            )
            .filter(
                ShopeeFlashSaleTrafficEvent.run_id == run_id,
                ShopeeFlashSaleTrafficEvent.user_id == user_id,
                ShopeeFlashSaleTrafficEvent.event_tick == now,
            )
            .all()
        )
        flash_sale_existing_event_keys = {
            (int(campaign_item_id), str(buyer_code or ""), str(event_type or ""))
            for campaign_item_id, buyer_code, event_type in event_rows
            if campaign_item_id is not None and buyer_code and event_type
        }

    active_buyer_count = 0
    generated_order_count = 0
    flash_sale_traffic_view_count = 0
    flash_sale_traffic_click_count = 0
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
        if flash_sale_map and flash_sale_traffic_view_count + flash_sale_traffic_click_count < FLASH_SALE_TRAFFIC_MAX_EVENTS_PER_TICK:
            traffic_summary = _simulate_flash_sale_traffic_for_buyer(
                db,
                run_id=run_id,
                user_id=user_id,
                tick_time=now,
                buyer=buyer,
                preferred_categories=preferred_categories,
                flash_sale_map=flash_sale_map,
                listing_by_id=flash_sale_listing_map,
                rng=rng,
                existing_event_keys=flash_sale_existing_event_keys,
                remaining_event_slots=FLASH_SALE_TRAFFIC_MAX_EVENTS_PER_TICK - flash_sale_traffic_view_count - flash_sale_traffic_click_count,
            )
            flash_sale_traffic_view_count += int(traffic_summary["view_count"])
            flash_sale_traffic_click_count += int(traffic_summary["click_count"])
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
            preview_variant, effective_price, hit_discount, price_score, price_gap, preview_flash_sale = _pick_variant_for_buyer(
                listing,
                buyer_purchase_power=float(buyer.purchase_power or 0.5),
                buyer_price_sensitivity=float(buyer.price_sensitivity or 0.5),
                rng=rng,
                discount_map=discount_map,
                flash_sale_map=flash_sale_map,
            )
            quality_score = _resolve_listing_quality_score(listing)
            stock_score = _clamp(float(_listing_sellable_cap(listing)) / 40.0, 0.0, 1.0)
            base_intent = _clamp(float(buyer.base_buy_intent or 0.0), 0.0, 1.0)
            impulse = _clamp(float(buyer.impulse_level or 0.0), 0.0, 1.0)
            flash_sale_candidate_bonus = 0.08 if preview_flash_sale else 0.0
            score = (
                0.32 * category_match
                + 0.22 * price_score
                + 0.14 * quality_score
                + 0.08 * stock_score
                + 0.16 * base_intent
                + 0.08 * impulse
                + flash_sale_candidate_bonus
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
                    "flash_sale_hit": bool(preview_flash_sale),
                    "flash_sale_campaign_id": preview_flash_sale["campaign_id"] if preview_flash_sale else None,
                    "flash_sale_variant_id": preview_variant.id if preview_variant and preview_flash_sale else None,
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
        variant, effective_price, hit_discount, selected_price_score, selected_price_gap, flash_sale_hit = _pick_variant_for_buyer(
            best_listing,
            buyer_purchase_power=float(buyer.purchase_power or 0.5),
            buyer_price_sensitivity=float(buyer.price_sensitivity or 0.5),
            rng=rng,
            discount_map=discount_map,
            flash_sale_map=flash_sale_map,
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
        flash_sale_limit_used = 0
        if flash_sale_hit:
            flash_sale_remaining_qty = max(0, int(flash_sale_hit.get("remaining_qty") or 0))
            flash_sale_limit_key = (
                str(buyer.nickname or ""),
                int(flash_sale_hit["campaign_id"]),
                int(best_listing.id),
                int(variant.id) if variant else None,
            )
            flash_sale_limit_used = buyer_flash_sale_qty_counts.get(flash_sale_limit_key, 0)
            flash_sale_limit_remaining = max(0, int(flash_sale_hit["purchase_limit_per_buyer"]) - flash_sale_limit_used)
            max_qty = min(max_qty, flash_sale_remaining_qty, flash_sale_limit_remaining)
            if flash_sale_remaining_qty <= 0:
                skip_reasons["flash_sale_stock_limit_reached"] = skip_reasons.get("flash_sale_stock_limit_reached", 0) + 1
            if flash_sale_limit_remaining <= 0:
                skip_reasons["flash_sale_purchase_limit_reached"] = skip_reasons.get("flash_sale_purchase_limit_reached", 0) + 1
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
        bundle_hit = None if flash_sale_hit else _resolve_bundle_upgrade(
            best_listing,
            variant=variant,
            bundle_map=bundle_map,
            sellable_cap=sellable_cap,
            buyer_purchase_power=float(buyer.purchase_power or 0.5),
            buyer_price_sensitivity=float(buyer.price_sensitivity or 0.5),
            buyer_impulse_level=impulse,
            rng=rng,
        )
        flash_sale_order_prob = None
        if flash_sale_hit:
            flash_sale_order_prob = _clamp(
                base_order_prob * float(flash_sale_hit["discount_boost"]) * float(flash_sale_hit["slot_multiplier"]),
                base_order_prob,
                FLASH_SALE_PROBABILITY_CAP,
            )
        base_unit_price = max(int(effective_price or 0), 1)
        quantity: int | None = None
        unit_price = base_unit_price
        applied_campaign = flash_sale_hit or hit_discount
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
        if flash_sale_order_prob is not None:
            order_prob = flash_sale_order_prob
        buyer_budget = 30 + _clamp(float(buyer.purchase_power or 0.5), 0.0, 1.0) * 300
        projected_quantity = max(1, int(quantity or min_qty))
        projected_order_amount = float(unit_price * projected_quantity)
        addon_decision: dict[str, Any] | None = None
        gift_decision: dict[str, Any] | None = None
        matching_gifts = [] if flash_sale_hit else _matching_addon_campaigns(
            addon_map,
            listing_id=int(best_listing.id),
            variant_id=int(variant.id) if variant else None,
            promotion_type="gift",
        )
        for gift_campaign in matching_gifts:
            candidate_gift = _resolve_gift_bonus(
                gift_campaign,
                base_order_amount=projected_order_amount,
                buyer_budget=buyer_budget,
                buyer_price_sensitivity=float(buyer.price_sensitivity or 0.5),
                buyer_impulse_level=impulse,
            )
            if candidate_gift and (
                gift_decision is None
                or float(candidate_gift["gift_order_bonus"]) > float(gift_decision["gift_order_bonus"])
            ):
                gift_decision = candidate_gift
        preview_voucher_subtotal = float(unit_price * max(1, int(quantity or min_qty)))
        preview_voucher, preview_voucher_candidates = _resolve_best_voucher_for_order(
            db=db,
            run_id=run_id,
            user_id=user_id,
            tick_time=now,
            voucher_context=voucher_context,
            buyer=buyer,
            buyer_name=str(buyer.nickname or ""),
            listing_id=int(best_listing.id),
            variant_id=int(variant.id) if variant else None,
            order_subtotal=preview_voucher_subtotal,
            buyer_voucher_usage_counts=buyer_voucher_usage_counts,
            private_access_cache=private_access_cache,
            content_access_cache=content_access_cache,
            follow_state_by_buyer=follow_state_by_buyer,
            follow_access_cache=follow_access_cache,
            campaign_by_key=voucher_context.get("campaign_by_key") or {},
            rng=rng,
            flash_sale_hit=bool(flash_sale_hit),
        )
        voucher_order_bonus = 0.0
        if preview_voucher:
            voucher_type = str(preview_voucher.get("voucher_type") or "")
            voucher_savings_rate = float(preview_voucher.get("discount_amount") or 0) / max(preview_voucher_subtotal, 1.0)
            if voucher_type == "follow_voucher":
                voucher_order_bonus = _clamp(
                    0.02 + float(buyer.price_sensitivity or 0.5) * 0.06 + voucher_savings_rate * 0.12,
                    0.01,
                    0.16,
                )
            elif voucher_type in {"live_voucher", "video_voucher"}:
                scene_base = 0.02 if voucher_type == "live_voucher" else 0.014
                scene_multiplier = 1.10 if voucher_type == "live_voucher" else 0.85
                voucher_order_bonus = _clamp(
                    scene_base + voucher_savings_rate * 0.08 * scene_multiplier + impulse * voucher_savings_rate * 0.08,
                    0.0,
                    0.085 if voucher_type == "live_voucher" else 0.065,
                )
            else:
                voucher_order_bonus = _clamp(
                    0.02 + voucher_savings_rate * 0.10 + float(buyer.price_sensitivity or 0.5) * voucher_savings_rate * 0.08,
                    0.0,
                    0.08,
                )
            order_prob = _clamp(order_prob + voucher_order_bonus, order_prob, 0.92)

        if gift_decision and not bundle_applied:
            order_prob = _clamp(order_prob + float(gift_decision["gift_order_bonus"]), order_prob, 0.92)

        if not bundle_applied and not flash_sale_hit:
            matching_addons = _matching_addon_campaigns(
                addon_map,
                listing_id=int(best_listing.id),
                variant_id=int(variant.id) if variant else None,
                promotion_type="add_on",
            )
            for addon_campaign in matching_addons:
                candidate_addon = _resolve_addon_attractiveness(
                    addon_campaign,
                    main_unit_price=float(unit_price),
                    base_order_amount=projected_order_amount,
                    buyer_budget=buyer_budget,
                    buyer_price_sensitivity=float(buyer.price_sensitivity or 0.5),
                    buyer_impulse_level=impulse,
                )
                if candidate_addon and (
                    addon_decision is None
                    or float(candidate_addon["addon_attractiveness"]) > float(addon_decision["addon_attractiveness"])
                ):
                    addon_decision = candidate_addon
            if addon_decision:
                order_prob = _clamp(order_prob + float(addon_decision["addon_order_bonus"]), order_prob, 0.92)

        if addon_decision:
            addon_reward = addon_decision.get("reward_item") or {}
            preview_after_addon_subtotal = preview_voucher_subtotal + float(addon_reward.get("addon_price") or 0)
            preview_after_addon_voucher, preview_after_addon_candidates = _resolve_best_voucher_for_order(
                db=db,
                run_id=run_id,
                user_id=user_id,
                tick_time=now,
                voucher_context=voucher_context,
                buyer=buyer,
                buyer_name=str(buyer.nickname or ""),
                listing_id=int(best_listing.id),
                variant_id=int(variant.id) if variant else None,
                order_subtotal=preview_after_addon_subtotal,
                buyer_voucher_usage_counts=buyer_voucher_usage_counts,
                private_access_cache=private_access_cache,
                content_access_cache=content_access_cache,
                follow_state_by_buyer=follow_state_by_buyer,
                follow_access_cache=follow_access_cache,
                campaign_by_key=voucher_context.get("campaign_by_key") or {},
                rng=rng,
                flash_sale_hit=bool(flash_sale_hit),
            )
            if preview_after_addon_voucher and (
                not preview_voucher
                or float(preview_after_addon_voucher.get("discount_amount") or 0) > float(preview_voucher.get("discount_amount") or 0)
            ):
                old_voucher_order_bonus = voucher_order_bonus
                preview_voucher = preview_after_addon_voucher
                preview_voucher_candidates = preview_after_addon_candidates
                voucher_type = str(preview_voucher.get("voucher_type") or "")
                voucher_savings_rate = float(preview_voucher.get("discount_amount") or 0) / max(preview_after_addon_subtotal, 1.0)
                if voucher_type == "follow_voucher":
                    voucher_order_bonus = _clamp(
                        0.02 + float(buyer.price_sensitivity or 0.5) * 0.06 + voucher_savings_rate * 0.12,
                        0.01,
                        0.16,
                    )
                elif voucher_type in {"live_voucher", "video_voucher"}:
                    scene_base = 0.02 if voucher_type == "live_voucher" else 0.014
                    scene_multiplier = 1.10 if voucher_type == "live_voucher" else 0.85
                    voucher_order_bonus = _clamp(
                        scene_base + voucher_savings_rate * 0.08 * scene_multiplier + impulse * voucher_savings_rate * 0.08,
                        0.0,
                        0.085 if voucher_type == "live_voucher" else 0.065,
                    )
                else:
                    voucher_order_bonus = _clamp(
                        0.02 + voucher_savings_rate * 0.10 + float(buyer.price_sensitivity or 0.5) * voucher_savings_rate * 0.08,
                        0.0,
                        0.08,
                    )
                order_prob = _clamp(order_prob + max(0.0, voucher_order_bonus - old_voucher_order_bonus), order_prob, 0.92)

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
            "flash_sale_hit": bool(flash_sale_hit),
            "flash_sale_campaign_id": flash_sale_hit["campaign_id"] if flash_sale_hit else None,
            "flash_sale_campaign_name": flash_sale_hit["campaign_name"] if flash_sale_hit else None,
            "flash_sale_order_prob": round(flash_sale_order_prob, 4) if flash_sale_order_prob is not None else None,
            "flash_sale_slot_multiplier": round(float(flash_sale_hit["slot_multiplier"]), 4) if flash_sale_hit else None,
            "flash_sale_discount_boost": round(float(flash_sale_hit["discount_boost"]), 4) if flash_sale_hit else None,
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
            "flash_sale_order_prob": round(flash_sale_order_prob, 4) if flash_sale_order_prob is not None else None,
            "bundle_order_prob": round(bundle_order_prob, 4) if bundle_order_prob is not None else None,
            "addon_campaign_id": addon_decision["campaign"]["campaign_id"] if addon_decision else None,
            "addon_order_bonus": round(float(addon_decision["addon_order_bonus"]), 4) if addon_decision else 0.0,
            "addon_attach_prob": round(float(addon_decision["addon_attach_prob"]), 4) if addon_decision else 0.0,
            "addon_savings_rate": round(float(addon_decision["savings_rate"]), 4) if addon_decision else 0.0,
            "gift_campaign_id": gift_decision["campaign"]["campaign_id"] if gift_decision else None,
            "gift_order_bonus": round(float(gift_decision["gift_order_bonus"]), 4) if gift_decision else 0.0,
            "gift_threshold_shortfall": round(float(gift_decision["gift_threshold_shortfall"]), 2) if gift_decision else None,
            "voucher_candidates": preview_voucher_candidates,
            "voucher_hit": bool(preview_voucher),
            "voucher_campaign_type": preview_voucher["voucher_type"] if preview_voucher else None,
            "voucher_campaign_id": preview_voucher["campaign_id"] if preview_voucher else None,
            "voucher_discount_amount": round(float(preview_voucher.get("discount_amount") or 0), 2) if preview_voucher else 0.0,
            "voucher_order_bonus": round(voucher_order_bonus, 4),
            "score": round(bundle_score if bundle_applied and bundle_score is not None else best_score, 4),
        }
        journey["voucher_candidates"] = preview_voucher_candidates
        journey["voucher_hit"] = bool(preview_voucher)
        journey["voucher_campaign_type"] = preview_voucher["voucher_type"] if preview_voucher else None
        journey["voucher_campaign_id"] = preview_voucher["campaign_id"] if preview_voucher else None
        journey["voucher_discount_amount"] = round(float(preview_voucher.get("discount_amount") or 0), 2) if preview_voucher else 0.0
        journey["voucher_order_bonus"] = round(voucher_order_bonus, 4)
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
                    "line_role": "main",
                    "marketing_campaign_type": applied_campaign["campaign_type"] if applied_campaign else None,
                    "marketing_campaign_id": applied_campaign["campaign_id"] if applied_campaign else None,
                    "marketing_campaign_name_snapshot": applied_campaign["campaign_name"] if applied_campaign else None,
                    "original_unit_price": float(original_unit_price),
                    "discounted_unit_price": float(unit_price),
                }
            ]

        addon_applied = False
        gift_applied = False
        if addon_decision and not bundle_applied:
            addon_roll = rng.random()
            addon_decision["addon_roll"] = addon_roll
            if addon_roll <= float(addon_decision["addon_attach_prob"]):
                reward_item = dict(addon_decision["reward_item"])
                addon_price = max(1, int(round(float(reward_item.get("addon_price") or 0))))
                addon_budget = 30 + _clamp(float(buyer.purchase_power or 0.5), 0.0, 1.0) * 1000
                max_addon_qty = min(
                    max(1, int(addon_decision["campaign"].get("addon_purchase_limit") or 1)),
                    max(0, int(reward_item.get("stock_snapshot") or 0)),
                    int(max(0, addon_budget - sum(int(line["unit_price"]) * int(line["quantity"]) for line in order_lines)) // addon_price),
                )
                addon_qty = 1 if max_addon_qty >= 1 else 0
                if addon_qty > 0 and max_addon_qty >= 2:
                    extra_qty_prob = _clamp(float(addon_decision["addon_attach_prob"]) * 0.35, 0.0, 0.25)
                    while addon_qty < max_addon_qty and rng.random() < extra_qty_prob:
                        addon_qty += 1
                        extra_qty_prob *= 0.55
                if addon_qty > 0:
                    addon_line = _resolve_listing_line(
                        db,
                        run_id=run_id,
                        user_id=user_id,
                        item=reward_item,
                        quantity=addon_qty,
                        unit_price=addon_price,
                        line_role="add_on",
                        campaign=addon_decision["campaign"],
                    )
                    if addon_line:
                        order_lines.append(addon_line)
                        addon_applied = True
        if gift_decision:
            order_amount_after_addon = int(sum(int(line["unit_price"]) * int(line["quantity"]) for line in order_lines))
            if order_amount_after_addon >= float(gift_decision["campaign"].get("gift_min_spend") or 0):
                gift_item = dict(gift_decision["gift_item"])
                gift_line = _resolve_listing_line(
                    db,
                    run_id=run_id,
                    user_id=user_id,
                    item=gift_item,
                    quantity=max(1, int(gift_item.get("reward_qty") or 1)),
                    unit_price=0,
                    line_role="gift",
                    campaign=gift_decision["campaign"],
                )
                if gift_line:
                    order_lines.append(gift_line)
                    gift_applied = True

        if bundle_applied and bundle_hit:
            for line in order_lines:
                line.setdefault("line_role", "bundle_component")
                line.setdefault("marketing_campaign_type", bundle_hit["campaign_type"])
                line.setdefault("marketing_campaign_id", bundle_hit["campaign_id"])
                line.setdefault("marketing_campaign_name_snapshot", bundle_hit["campaign_name"])
                line.setdefault("original_unit_price", float(line["unit_price"]))
                line.setdefault("discounted_unit_price", float(line["unit_price"]))

        if not applied_campaign:
            if addon_applied and addon_decision:
                applied_campaign = addon_decision["campaign"]
            elif gift_applied and gift_decision:
                applied_campaign = gift_decision["campaign"]

        order_subtotal = float(sum(int(line["unit_price"]) * int(line["quantity"]) for line in order_lines))
        selected_voucher, voucher_candidates = _resolve_best_voucher_for_order(
            db=db,
            run_id=run_id,
            user_id=user_id,
            tick_time=now,
            voucher_context=voucher_context,
            buyer=buyer,
            buyer_name=str(buyer.nickname or ""),
            listing_id=int(best_listing.id),
            variant_id=int(variant.id) if variant else None,
            order_subtotal=order_subtotal,
            buyer_voucher_usage_counts=buyer_voucher_usage_counts,
            private_access_cache=private_access_cache,
            content_access_cache=content_access_cache,
            follow_state_by_buyer=follow_state_by_buyer,
            follow_access_cache=follow_access_cache,
            campaign_by_key=voucher_context.get("campaign_by_key") or {},
            rng=rng,
            flash_sale_hit=bool(flash_sale_hit),
        )
        voucher_discount_amount = round(float(selected_voucher.get("discount_amount") or 0), 2) if selected_voucher else 0.0
        payment = int(round(order_subtotal - voucher_discount_amount))
        shipping_channel = _resolve_shipping_channel(best_listing, rng)
        buyer_destination = buyer.city or "吉隆坡"
        distance_km = haversine_km(warehouse_latlng, _resolve_buyer_latlng(db, buyer, buyer_destination))
        shipping_fee_before_promotion = calc_shipping_cost(distance_km, shipping_channel)
        selected_shipping_promotion, shipping_promotion_candidates = _resolve_best_shipping_fee_promotion_for_order(
            shipping_promotion_context=shipping_promotion_context,
            shipping_channel=shipping_channel,
            order_subtotal=order_subtotal,
            original_shipping_fee=shipping_fee_before_promotion,
        )
        shipping_promotion_discount_amount = round(float(selected_shipping_promotion.get("shipping_discount_amount") or 0), 2) if selected_shipping_promotion else 0.0
        shipping_fee_after_promotion = round(shipping_fee_before_promotion - shipping_promotion_discount_amount, 2)
        total_shortfall_qty = int(sum(max(0, int(line["shortfall_qty"])) for line in order_lines))
        total_quantity = int(sum(max(0, int(line["quantity"])) for line in order_lines))
        flash_sale_item: ShopeeFlashSaleCampaignItem | None = None
        if flash_sale_hit:
            flash_sale_item = (
                db.query(ShopeeFlashSaleCampaignItem)
                .filter(
                    ShopeeFlashSaleCampaignItem.id == int(flash_sale_hit["campaign_item_id"]),
                    ShopeeFlashSaleCampaignItem.run_id == run_id,
                    ShopeeFlashSaleCampaignItem.user_id == user_id,
                    ShopeeFlashSaleCampaignItem.status == "active",
                )
                .first()
            )
            if not flash_sale_item:
                skip_reasons["flash_sale_item_missing"] = skip_reasons.get("flash_sale_item_missing", 0) + 1
                journey["decision"] = "skipped_flash_sale_item_missing"
                journey["reason"] = "flash_sale_item_missing_before_commit"
                buyer_journeys.append(journey)
                continue
            remaining_qty = max(0, int(flash_sale_item.activity_stock_limit or 0) - int(flash_sale_item.sold_qty or 0))
            if total_quantity > remaining_qty:
                skip_reasons["flash_sale_stock_limit_reached"] = skip_reasons.get("flash_sale_stock_limit_reached", 0) + 1
                journey["decision"] = "skipped_flash_sale_stock_limit"
                journey["reason"] = "quantity_gt_flash_sale_remaining_qty"
                buyer_journeys.append(journey)
                continue
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

        if flash_sale_item is not None:
            flash_sale_item.sold_qty = int(flash_sale_item.sold_qty or 0) + total_quantity
            if flash_sale_item.campaign:
                flash_sale_item.campaign.order_count = int(flash_sale_item.campaign.order_count or 0) + 1
                flash_sale_item.campaign.sales_amount = float(flash_sale_item.campaign.sales_amount or 0) + float(unit_price * total_quantity)

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
            shipping_channel=shipping_channel,
            destination=buyer_destination,
            countdown_text="请在24小时内处理",
            action_text="查看详情",
            ship_by_date=now + timedelta(days=1),
            ship_by_at=now + timedelta(days=1),
            distance_km=distance_km,
            stock_fulfillment_status="backorder" if total_shortfall_qty > 0 else "in_stock",
            backorder_qty=total_shortfall_qty,
            must_restock_before_at=(now + timedelta(hours=BACKORDER_GRACE_GAME_HOURS)) if total_shortfall_qty > 0 else None,
            marketing_campaign_type=applied_campaign["campaign_type"] if applied_campaign else None,
            marketing_campaign_id=applied_campaign["campaign_id"] if applied_campaign else None,
            marketing_campaign_name_snapshot=applied_campaign["campaign_name"] if applied_campaign else None,
            order_subtotal_amount=order_subtotal,
            voucher_campaign_type=selected_voucher["voucher_type"] if selected_voucher else None,
            voucher_campaign_id=int(selected_voucher["campaign_id"]) if selected_voucher else None,
            voucher_name_snapshot=selected_voucher["voucher_name"] if selected_voucher else None,
            voucher_code_snapshot=selected_voucher["voucher_code"] if selected_voucher else None,
            voucher_discount_amount=voucher_discount_amount,
            shipping_promotion_campaign_id=int(selected_shipping_promotion["campaign_id"]) if selected_shipping_promotion else None,
            shipping_promotion_name_snapshot=selected_shipping_promotion["promotion_name"] if selected_shipping_promotion else None,
            shipping_promotion_tier_index=int(selected_shipping_promotion["matched_tier_index"]) if selected_shipping_promotion else None,
            shipping_fee_before_promotion=shipping_fee_before_promotion,
            shipping_fee_after_promotion=shipping_fee_after_promotion,
            shipping_promotion_discount_amount=shipping_promotion_discount_amount,
            created_at=now,
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
                    marketing_campaign_type=line.get("marketing_campaign_type"),
                    marketing_campaign_id=int(line["marketing_campaign_id"]) if line.get("marketing_campaign_id") is not None else None,
                    marketing_campaign_name_snapshot=line.get("marketing_campaign_name_snapshot"),
                    line_role=str(line.get("line_role") or "main"),
                    original_unit_price=float(line.get("original_unit_price") or line["unit_price"] or 0),
                    discounted_unit_price=float(line.get("discounted_unit_price") or line["unit_price"] or 0),
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
        _apply_voucher_stats(
            voucher_context=voucher_context,
            selected_voucher=selected_voucher,
            buyer_name=str(buyer.nickname or ""),
            buyer_payment=float(payment),
            buyer_voucher_usage_counts=buyer_voucher_usage_counts,
        )
        _apply_shipping_fee_promotion_stats(
            selected_shipping_promotion=selected_shipping_promotion,
            buyer_name=str(buyer.nickname or ""),
            order_subtotal=order_subtotal,
            buyer_shipping_promotion_usage_counts=buyer_shipping_promotion_usage_counts,
        )
        if selected_shipping_promotion:
            _invalidate_shipping_fee_promotion_simulation_cache(run_id=run_id, user_id=user_id)
        if bundle_applied and bundle_hit:
            buyer_bundle_key = (str(buyer.nickname or ""), int(bundle_hit["campaign_id"]))
            buyer_bundle_order_counts[buyer_bundle_key] = buyer_bundle_order_counts.get(buyer_bundle_key, 0) + 1
        if flash_sale_hit:
            flash_sale_limit_key = (
                str(buyer.nickname or ""),
                int(flash_sale_hit["campaign_id"]),
                int(best_listing.id),
                int(variant.id) if variant else None,
            )
            buyer_flash_sale_qty_counts[flash_sale_limit_key] = buyer_flash_sale_qty_counts.get(flash_sale_limit_key, 0) + total_quantity
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
            "order_subtotal": round(order_subtotal, 2),
            "buyer_payment_after_voucher": payment,
            "voucher_candidates": voucher_candidates,
            "voucher_hit": bool(selected_voucher),
            "voucher_campaign_type": selected_voucher["voucher_type"] if selected_voucher else None,
            "voucher_campaign_id": selected_voucher["campaign_id"] if selected_voucher else None,
            "voucher_discount_amount": voucher_discount_amount,
            "voucher_order_bonus": round(voucher_order_bonus, 4),
            "shipping_fee_promotion_candidates": _sanitize_shipping_fee_promotion_candidates(shipping_promotion_candidates),
            "selected_shipping_fee_promotion": (
                {key: value for key, value in selected_shipping_promotion.items() if key not in {"campaign", "tier"}}
                if selected_shipping_promotion else None
            ),
            "shipping_fee_before_promotion": shipping_fee_before_promotion,
            "shipping_fee_after_promotion": shipping_fee_after_promotion,
            "shipping_promotion_discount_amount": shipping_promotion_discount_amount,
            "effective_price": effective_price,
            "price_gap": round(selected_price_gap, 4),
            "price_score": round(selected_price_score, 4),
            "discount_hit": bool(applied_campaign and applied_campaign["campaign_type"] == "discount"),
            "discount_campaign_id": hit_discount["campaign_id"] if hit_discount else None,
            "discount_campaign_name": hit_discount["campaign_name"] if hit_discount else None,
            "flash_sale_hit": bool(flash_sale_hit),
            "flash_sale_campaign_id": flash_sale_hit["campaign_id"] if flash_sale_hit else None,
            "flash_sale_campaign_name": flash_sale_hit["campaign_name"] if flash_sale_hit else None,
            "flash_sale_limit_used": flash_sale_limit_used if flash_sale_hit else None,
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
            "flash_sale_order_prob": round(flash_sale_order_prob, 4) if flash_sale_order_prob is not None else None,
            "bundle_order_prob": round(bundle_order_prob, 4) if bundle_order_prob is not None else None,
            "addon_campaign_id": addon_decision["campaign"]["campaign_id"] if addon_decision else None,
            "addon_applied": addon_applied,
            "addon_attach_prob": round(float(addon_decision["addon_attach_prob"]), 4) if addon_decision else 0.0,
            "addon_savings_rate": round(float(addon_decision["savings_rate"]), 4) if addon_decision else 0.0,
            "gift_campaign_id": gift_decision["campaign"]["campaign_id"] if gift_decision else None,
            "gift_applied": gift_applied,
            "gift_order_bonus": round(float(gift_decision["gift_order_bonus"]), 4) if gift_decision else 0.0,
            "gift_threshold_shortfall": round(float(gift_decision["gift_threshold_shortfall"]), 2) if gift_decision else None,
            "addon_gift_items": [
                {
                    "listing_id": int(line["listing"].id),
                    "variant_id": int(line["variant"].id) if line["variant"] else None,
                    "product_title": line["listing"].title,
                    "variant_name": line["variant"].option_value if line["variant"] else "",
                    "quantity": int(line["quantity"]),
                    "unit_price": int(line["unit_price"]),
                    "line_role": str(line.get("line_role") or "main"),
                    "marketing_campaign_id": line.get("marketing_campaign_id"),
                }
                for line in order_lines
                if str(line.get("line_role") or "") in {"add_on", "gift"}
            ],
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
            "flash_sale_traffic": {
                "view_count": flash_sale_traffic_view_count,
                "click_count": flash_sale_traffic_click_count,
            },
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
        "flash_sale_traffic": {
            "view_count": flash_sale_traffic_view_count,
            "click_count": flash_sale_traffic_click_count,
        },
        "skip_reasons": skip_reasons,
        "buyer_journeys": buyer_journeys,
    }

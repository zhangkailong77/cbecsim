from __future__ import annotations

from datetime import datetime, timedelta
import json
import random
from typing import Any
from uuid import uuid4

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
    now = tick_time or datetime.utcnow()
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

        order_prob = _clamp(0.08 + best_score * 0.95, 0.05, 0.90)
        order_roll = rng.random()
        variant, effective_price, hit_discount, selected_price_score, selected_price_gap = _pick_variant_for_buyer(
            best_listing,
            buyer_purchase_power=float(buyer.purchase_power or 0.5),
            buyer_price_sensitivity=float(buyer.price_sensitivity or 0.5),
            rng=rng,
            discount_map=discount_map,
        )
        journey["selected_candidate"] = {
            "listing_id": best_listing.id,
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
            "score": round(best_score, 4),
        }
        journey["order_prob"] = round(order_prob, 4)
        journey["order_roll"] = round(order_roll, 4)
        if order_roll > order_prob:
            skip_reasons["below_probability"] = skip_reasons.get("below_probability", 0) + 1
            journey["decision"] = "skipped_probability"
            journey["reason"] = "order_roll_gt_order_prob"
            buyer_journeys.append(journey)
            continue

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
        else:
            quantity = rng.randint(min_qty, max_qty)
        if quantity <= 0:
            skip_reasons["invalid_qty"] = skip_reasons.get("invalid_qty", 0) + 1
            journey["decision"] = "skipped_invalid_qty"
            journey["reason"] = "quantity_le_0"
            buyer_journeys.append(journey)
            continue

        unit_price = max(int(effective_price or 0), 1)
        payment = unit_price * quantity
        shortfall_qty = max(0, quantity - variant_available_stock)
        if shortfall_qty > 0 and variant and shortfall_qty > variant_oversell_remaining:
            skip_reasons["oversell_limit_reached"] = skip_reasons.get("oversell_limit_reached", 0) + 1
            journey["decision"] = "skipped_oversell_limit_reached"
            journey["reason"] = "shortfall_gt_oversell_remaining"
            buyer_journeys.append(journey)
            continue

        stock_consumed_planned = quantity - shortfall_qty
        reserved_qty = 0
        if int(best_listing.product_id or 0) > 0 and stock_consumed_planned > 0:
            reserved_qty = reserve_inventory_lots(
                db,
                run_id=run_id,
                product_id=int(best_listing.product_id),
                qty=stock_consumed_planned,
            )
        stock_consumed = reserved_qty
        best_listing.sales_count = int(best_listing.sales_count or 0) + quantity
        best_listing.stock_available = max(0, int(best_listing.stock_available or 0) - stock_consumed)
        if variant:
            variant.stock = max(0, int(variant.stock or 0) - stock_consumed)
            variant.sales_count = int(variant.sales_count or 0) + quantity
            if shortfall_qty > 0:
                variant.oversell_used = int(variant.oversell_used or 0) + shortfall_qty
            # Keep parent stock synchronized with variant total for variant listings.
            best_listing.stock_available = _listing_available_stock(best_listing)

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
            stock_fulfillment_status="backorder" if shortfall_qty > 0 else "in_stock",
            backorder_qty=shortfall_qty,
            must_restock_before_at=(now + timedelta(hours=BACKORDER_GRACE_GAME_HOURS)) if shortfall_qty > 0 else None,
            marketing_campaign_type=hit_discount["campaign_type"] if hit_discount else None,
            marketing_campaign_id=hit_discount["campaign_id"] if hit_discount else None,
            marketing_campaign_name_snapshot=hit_discount["campaign_name"] if hit_discount else None,
        )
        db.add(order)
        db.flush()
        db.add(
            ShopeeOrderItem(
                order_id=order.id,
                product_name=best_listing.title,
                variant_name=(variant.option_value if variant else "") or "",
                quantity=quantity,
                unit_price=unit_price,
                image_url=(variant.image_url if variant and (variant.image_url or "").strip() else best_listing.cover_url),
            )
        )
        db.add(
            InventoryStockMovement(
                run_id=run_id,
                user_id=user_id,
                product_id=int(best_listing.product_id) if best_listing.product_id is not None else None,
                listing_id=int(best_listing.id),
                variant_id=int(variant.id) if variant else None,
                inventory_lot_id=None,
                biz_order_id=int(order.id),
                movement_type="order_reserve",
                qty_delta_on_hand=-int(stock_consumed),
                qty_delta_reserved=int(reserved_qty),
                qty_delta_backorder=int(shortfall_qty),
                biz_ref=order.order_no,
                remark="Shopee订单模拟占用库存/形成待补货",
            )
        )
        generated_order_count += 1
        journey["decision"] = "generated_order"
        journey["reason"] = "order_roll_le_order_prob"
        journey["generated_order"] = {
            "order_no": order.order_no,
            "listing_id": best_listing.id,
            "product_title": best_listing.title,
            "listing_sku": best_listing.sku_code,
            "variant_sku": variant.sku if variant else None,
            "variant_name": variant.option_value if variant else "",
            "quantity": quantity,
            "unit_price": unit_price,
            "buyer_payment": payment,
            "effective_price": effective_price,
            "price_gap": round(selected_price_gap, 4),
            "price_score": round(selected_price_score, 4),
            "discount_hit": bool(hit_discount),
            "discount_campaign_id": hit_discount["campaign_id"] if hit_discount else None,
            "discount_campaign_name": hit_discount["campaign_name"] if hit_discount else None,
            "stock_fulfillment_status": "backorder" if shortfall_qty > 0 else "in_stock",
            "backorder_qty": shortfall_qty,
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

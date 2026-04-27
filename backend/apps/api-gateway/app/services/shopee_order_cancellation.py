from __future__ import annotations

from datetime import datetime
import hashlib
from typing import Any

from sqlalchemy.orm import Session

from app.models import InventoryStockMovement, ShopeeListing, ShopeeListingVariant, ShopeeOrder, ShopeeOrderItem, ShopeeOrderLogisticsEvent
from app.services.inventory_lot_sync import release_reserved_inventory_lots, reserve_inventory_lots


CANCEL_THRESHOLD_HOURS = 48
CANCEL_BASE_PROB = 0.25
CANCEL_HOURLY_INCREMENT = 0.08
CANCEL_MAX_PROB = 0.90

_CANCEL_EVENT_CODE = "cancelled_by_buyer"
_CANCEL_EVENT_TITLE = "买家取消订单"
_CANCEL_EVENT_DESC = "卖家超时未发货，买家取消订单"


def _rollback_order_stock_and_sales(
    db: Session,
    *,
    run_id: int,
    user_id: int,
    order: ShopeeOrder,
) -> set[int]:
    items = list(order.items or [])
    released_product_ids: set[int] = set()
    if not items:
        return released_product_ids

    for item in items:
        qty = max(0, int(item.quantity or 0))
        if qty <= 0:
            continue
        product_name = (item.product_name or "").strip()
        variant_name = (item.variant_name or "").strip()

        listing: ShopeeListing | None = None
        item_listing_id = int(getattr(item, "listing_id", 0) or 0)
        if item_listing_id > 0:
            listing = (
                db.query(ShopeeListing)
                .filter(
                    ShopeeListing.run_id == run_id,
                    ShopeeListing.user_id == user_id,
                    ShopeeListing.id == item_listing_id,
                )
                .first()
            )
        if not listing and int(order.listing_id or 0) > 0:
            listing = (
                db.query(ShopeeListing)
                .filter(
                    ShopeeListing.run_id == run_id,
                    ShopeeListing.user_id == user_id,
                    ShopeeListing.id == int(order.listing_id),
                )
                .first()
            )
        if not listing and product_name:
            listing = (
                db.query(ShopeeListing)
                .filter(
                    ShopeeListing.run_id == run_id,
                    ShopeeListing.user_id == user_id,
                    ShopeeListing.title == product_name,
                )
                .order_by(ShopeeListing.id.desc())
                .first()
            )
        if not listing:
            continue

        product_id = int(listing.product_id or 0) if listing.product_id is not None else 0
        listing.sales_count = max(0, int(listing.sales_count or 0) - qty)
        variants = list(listing.variants or [])
        if variants:
            matched_variant: ShopeeListingVariant | None = None
            item_variant_id = int(getattr(item, "variant_id", 0) or 0)
            if item_variant_id > 0:
                matched_variant = (
                    db.query(ShopeeListingVariant)
                    .filter(
                        ShopeeListingVariant.listing_id == listing.id,
                        ShopeeListingVariant.id == item_variant_id,
                    )
                    .first()
                )
            if not matched_variant and int(order.variant_id or 0) > 0:
                matched_variant = (
                    db.query(ShopeeListingVariant)
                    .filter(
                        ShopeeListingVariant.listing_id == listing.id,
                        ShopeeListingVariant.id == int(order.variant_id),
                    )
                    .first()
                )
            if not matched_variant and variant_name:
                matched_variant = (
                    db.query(ShopeeListingVariant)
                    .filter(
                        ShopeeListingVariant.listing_id == listing.id,
                        ShopeeListingVariant.option_value == variant_name,
                    )
                    .order_by(ShopeeListingVariant.sort_order.asc(), ShopeeListingVariant.id.asc())
                    .first()
                )
            if matched_variant:
                backorder_from_order = max(
                0,
                int(getattr(item, "backorder_qty", 0) or 0)
                if (order.marketing_campaign_type or "") == "bundle"
                else int(order.backorder_qty or 0),
            )
                oversell_release = min(qty, backorder_from_order)
                stock_release = max(0, qty - oversell_release)
                released_reserved = 0
                if product_id > 0 and stock_release > 0:
                    released_reserved = release_reserved_inventory_lots(
                        db,
                        run_id=run_id,
                        product_id=product_id,
                        qty=stock_release,
                    )
                    released_product_ids.add(product_id)
                matched_variant.stock = max(0, int(matched_variant.stock or 0) + stock_release)
                matched_variant.sales_count = max(0, int(matched_variant.sales_count or 0) - qty)
                matched_variant.oversell_used = max(0, int(matched_variant.oversell_used or 0) - oversell_release)
                db.add(
                    InventoryStockMovement(
                        run_id=run_id,
                        user_id=user_id,
                        product_id=int(listing.product_id) if listing.product_id is not None else None,
                        listing_id=int(listing.id),
                        variant_id=int(matched_variant.id),
                        biz_order_id=int(order.id),
                        movement_type="cancel_release",
                        qty_delta_on_hand=int(stock_release),
                        qty_delta_reserved=-int(released_reserved),
                        qty_delta_backorder=-int(oversell_release),
                        biz_ref=order.order_no,
                        remark="订单取消释放库存/回退缺货占用",
                    )
                )
            listing.stock_available = int(sum(max(0, int(v.stock or 0)) for v in variants))
        else:
            backorder_from_order = max(
                0,
                int(getattr(item, "backorder_qty", 0) or 0)
                if (order.marketing_campaign_type or "") == "bundle"
                else int(order.backorder_qty or 0),
            )
            stock_release = max(0, qty - min(qty, backorder_from_order))
            released_reserved = 0
            if product_id > 0 and stock_release > 0:
                released_reserved = release_reserved_inventory_lots(
                    db,
                    run_id=run_id,
                    product_id=product_id,
                    qty=stock_release,
                )
                released_product_ids.add(product_id)
            listing.stock_available = max(0, int(listing.stock_available or 0) + stock_release)
            db.add(
                InventoryStockMovement(
                    run_id=run_id,
                    user_id=user_id,
                    product_id=int(listing.product_id) if listing.product_id is not None else None,
                    listing_id=int(listing.id),
                    variant_id=None,
                    biz_order_id=int(order.id),
                    movement_type="cancel_release",
                    qty_delta_on_hand=int(stock_release),
                    qty_delta_reserved=-int(released_reserved),
                    qty_delta_backorder=-int(min(qty, backorder_from_order)),
                    biz_ref=order.order_no,
                    remark="订单取消释放库存/回退缺货占用",
                )
            )
    return released_product_ids


def _rebalance_backorders_from_released_inventory(
    db: Session,
    *,
    run_id: int,
    user_id: int,
    product_ids: set[int],
) -> None:
    if not product_ids:
        return

    for product_id in sorted({int(pid) for pid in product_ids if int(pid) > 0}):
        backlog_items = (
            db.query(ShopeeOrder, ShopeeOrderItem)
            .join(ShopeeOrderItem, ShopeeOrderItem.order_id == ShopeeOrder.id)
            .filter(
                ShopeeOrder.run_id == run_id,
                ShopeeOrder.user_id == user_id,
                ShopeeOrder.type_bucket == "toship",
                ShopeeOrder.stock_fulfillment_status == "backorder",
                ShopeeOrderItem.product_id == product_id,
                ShopeeOrderItem.backorder_qty > 0,
            )
            .order_by(ShopeeOrder.created_at.asc(), ShopeeOrder.id.asc(), ShopeeOrderItem.id.asc())
            .all()
        )
        for backlog_order, backlog_item in backlog_items:
            needed = max(0, int(backlog_item.backorder_qty or 0))
            if needed <= 0:
                continue
            reserved_fill_qty = reserve_inventory_lots(
                db,
                run_id=run_id,
                product_id=product_id,
                qty=needed,
            )
            if reserved_fill_qty <= 0:
                break
            backlog_item.backorder_qty = needed - reserved_fill_qty
            if backlog_item.backorder_qty <= 0:
                backlog_item.backorder_qty = 0
                backlog_item.stock_fulfillment_status = "restocked"
            backlog_order.backorder_qty = max(0, int(backlog_order.backorder_qty or 0) - reserved_fill_qty)
            if backlog_order.backorder_qty <= 0:
                backlog_order.backorder_qty = 0
                backlog_order.stock_fulfillment_status = "restocked"
                backlog_order.must_restock_before_at = None
            if int(backlog_item.variant_id or 0) > 0:
                matched_variant = (
                    db.query(ShopeeListingVariant)
                    .filter(ShopeeListingVariant.id == int(backlog_item.variant_id))
                    .first()
                )
                if matched_variant:
                    matched_variant.oversell_used = max(0, int(matched_variant.oversell_used or 0) - reserved_fill_qty)
            db.add(
                InventoryStockMovement(
                    run_id=run_id,
                    user_id=user_id,
                    product_id=product_id,
                    listing_id=int(backlog_item.listing_id or 0) or int(backlog_order.listing_id or 0) or None,
                    variant_id=int(backlog_item.variant_id or 0) or int(backlog_order.variant_id or 0) or None,
                    biz_order_id=int(backlog_order.id),
                    movement_type="restock_fill",
                    qty_delta_on_hand=0,
                    qty_delta_reserved=int(reserved_fill_qty),
                    qty_delta_backorder=-int(reserved_fill_qty),
                    biz_ref=backlog_order.order_no,
                    remark="订单取消释放库存后自动冲减缺货",
                )
            )


def rebalance_backorders_from_current_inventory(
    db: Session,
    *,
    run_id: int,
    user_id: int,
) -> None:
    """Best-effort self-heal for legacy backorders when available inventory already exists."""
    product_ids = {
        int(row[0])
        for row in (
            db.query(ShopeeOrderItem.product_id)
            .join(ShopeeOrder, ShopeeOrder.id == ShopeeOrderItem.order_id)
            .filter(
                ShopeeOrder.run_id == run_id,
                ShopeeOrder.user_id == user_id,
                ShopeeOrder.type_bucket == "toship",
                ShopeeOrder.stock_fulfillment_status == "backorder",
                ShopeeOrderItem.product_id.isnot(None),
                ShopeeOrderItem.backorder_qty > 0,
            )
            .all()
        )
        if row and row[0] is not None and int(row[0]) > 0
    }
    _rebalance_backorders_from_released_inventory(
        db,
        run_id=run_id,
        user_id=user_id,
        product_ids=product_ids,
    )


def calc_cancel_prob(overdue_hours: int) -> float:
    if overdue_hours < CANCEL_THRESHOLD_HOURS:
        return 0.0
    return min(
        CANCEL_MAX_PROB,
        CANCEL_BASE_PROB + (overdue_hours - CANCEL_THRESHOLD_HOURS) * CANCEL_HOURLY_INCREMENT,
    )


def should_cancel_for_tick(order_id: int, tick: datetime, prob: float) -> bool:
    if prob <= 0:
        return False
    if prob >= 1:
        return True
    seed = f"{order_id}-{tick.isoformat()}".encode("utf-8")
    digest = hashlib.sha256(seed).hexdigest()
    roll = int(digest[:8], 16) / 0xFFFFFFFF
    return roll < prob


def cancel_order(
    db: Session,
    *,
    run_id: int,
    user_id: int,
    order: ShopeeOrder,
    cancel_time: datetime,
    reason: str,
    source: str,
) -> None:
    locked_order = (
        db.query(ShopeeOrder)
        .filter(
            ShopeeOrder.id == int(order.id),
            ShopeeOrder.run_id == run_id,
            ShopeeOrder.user_id == user_id,
        )
        .with_for_update()
        .first()
    )
    if not locked_order:
        return
    if (locked_order.type_bucket or "").strip() != "toship":
        return

    released_product_ids = _rollback_order_stock_and_sales(
        db,
        run_id=run_id,
        user_id=user_id,
        order=locked_order,
    )
    # SessionLocal 使用 autoflush=False，先把取消释放的库存落盘，
    # 避免后续 backorder 回补查询看不到最新 quantity_available。
    db.flush()
    locked_order.type_bucket = "cancelled"
    locked_order.process_status = "processed"
    locked_order.cancelled_at = cancel_time
    locked_order.cancel_reason = reason
    locked_order.cancel_source = source
    locked_order.countdown_text = "订单已取消"
    _rebalance_backorders_from_released_inventory(
        db,
        run_id=run_id,
        user_id=user_id,
        product_ids=released_product_ids,
    )
    db.add(
        ShopeeOrderLogisticsEvent(
            run_id=run_id,
            user_id=user_id,
            order_id=locked_order.id,
            event_code=_CANCEL_EVENT_CODE,
            event_title=_CANCEL_EVENT_TITLE,
            event_desc=_CANCEL_EVENT_DESC,
            event_time=cancel_time,
        )
    )


def auto_cancel_overdue_orders_by_tick(
    db: Session,
    *,
    run_id: int,
    user_id: int,
    current_tick: datetime,
    commit: bool = True,
) -> list[dict[str, Any]]:
    toship_orders = (
        db.query(ShopeeOrder)
        .filter(
            ShopeeOrder.run_id == run_id,
            ShopeeOrder.user_id == user_id,
            ShopeeOrder.type_bucket == "toship",
        )
        .all()
    )
    changed = False
    cancel_logs: list[dict[str, Any]] = []
    for order in toship_orders:
        if not order.ship_by_at:
            continue
        overdue_hours = int((current_tick - order.ship_by_at).total_seconds() // 3600)
        cancel_prob = calc_cancel_prob(overdue_hours)
        if not should_cancel_for_tick(order.id, current_tick, cancel_prob):
            continue
        cancel_order(
            db,
            run_id=run_id,
            user_id=user_id,
            order=order,
            cancel_time=current_tick,
            reason="seller_not_ship_in_time",
            source="buyer_auto",
        )
        cancel_logs.append(
            {
                "order_id": order.id,
                "order_no": order.order_no,
                "buyer_name": order.buyer_name,
                "cancelled_at": current_tick,
                "cancel_reason": "seller_not_ship_in_time",
                "cancel_source": "buyer_auto",
                "overdue_hours": overdue_hours,
                "cancel_prob": round(cancel_prob, 4),
            }
        )
        changed = True

    if changed and commit:
        db.commit()
    return cancel_logs

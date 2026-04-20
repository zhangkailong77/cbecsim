from datetime import datetime, timedelta
import json
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.core.cache import cache_delete_prefix, cache_get_json, cache_set_json
from app.core.distributed_lock import acquire_distributed_lock, release_distributed_lock
from app.core.rate_limit import check_rate_limit
from app.core.security import get_current_user
from app.db import get_db
from app.models import (
    GameRun,
    GameRunCashAdjustment,
    InventoryLot,
    InventoryStockMovement,
    LogisticsShipment,
    LogisticsShipmentOrder,
    MarketProduct,
    ProcurementOrder,
    ProcurementOrderItem,
    SimBuyerProfile,
    ShopeeListing,
    ShopeeListingVariant,
    ShopeeOrder,
    ShopeeOrderItem,
    ShopeeOrderGenerationLog,
    User,
    WarehouseInboundOrder,
    WarehouseLandmark,
    WarehouseStrategy,
)
from app.services.shopee_order_simulator import simulate_orders_for_run
from app.services.shopee_order_cancellation import auto_cancel_overdue_orders_by_tick, calc_cancel_prob
from app.services.inventory_lot_sync import reserve_inventory_lots


router = APIRouter(prefix="/game", tags=["game"])
REAL_SECONDS_PER_GAME_DAY = 30 * 60
REAL_SECONDS_PER_GAME_HOUR = REAL_SECONDS_PER_GAME_DAY / 24
DEFAULT_TOTAL_GAME_DAYS = 365
BOOKED_SECONDS = 10
RUN_FINISHED_DETAIL = "当前对局已结束，无法继续订单演化操作"
RUN_EXTEND_FINISHED_DETAIL = "当前对局已结束，无法继续延长"
STOCK_MOVEMENT_LABELS = {
    "purchase_in": "采购入库",
    "order_reserve": "订单占用",
    "order_ship": "订单发货",
    "cancel_release": "取消释放",
    "restock_fill": "补货冲减",
    "drift_reconcile": "漂移修复",
}
REDIS_PREFIX = os.getenv("REDIS_PREFIX", "cbec")
REDIS_LOCK_TTL_SEC = max(10, int(os.getenv("REDIS_LOCK_TTL_SEC", "45")))
REDIS_RATE_LIMIT_ADMIN_SIMULATE_PER_MIN = max(1, int(os.getenv("REDIS_RATE_LIMIT_ADMIN_SIMULATE_PER_MIN", "10")))
REDIS_CACHE_TTL_OVERVIEW_SEC = max(5, int(os.getenv("REDIS_CACHE_TTL_OVERVIEW_SEC", "15")))
REDIS_CACHE_TTL_HISTORY_SUMMARY_SEC = max(5, int(os.getenv("REDIS_CACHE_TTL_HISTORY_SUMMARY_SEC", "30")))


def _invalidate_shopee_orders_cache_for_user(*, run_id: int, user_id: int) -> None:
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:orders:list:{run_id}:{user_id}:")


def _game_overview_cache_key(*, name: str, run_id: int | None = None, top_n: int | None = None) -> str:
    rid = "latest" if run_id is None else str(run_id)
    suffix = ""
    if top_n is not None:
        suffix = f":top_n:{int(top_n)}"
    return f"{REDIS_PREFIX}:cache:game:{name}:run:{rid}{suffix}"


def _invalidate_admin_run_related_cache(*, run_id: int, user_id: int) -> None:
    cache_delete_prefix(_game_overview_cache_key(name="buyer_pool_overview", run_id=run_id))
    cache_delete_prefix(_game_overview_cache_key(name="buyer_pool_overview", run_id=None))
    cache_delete_prefix(f"{_game_overview_cache_key(name='history_summary', run_id=run_id)}:user:{user_id}")


def _enforce_admin_simulate_rate_limit(*, admin_user_id: int) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:game:admin:simulate:user:{admin_user_id}",
        limit=REDIS_RATE_LIMIT_ADMIN_SIMULATE_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"模拟请求过于频繁，请在 {reset_at} 后重试",
        )


def _acquire_admin_simulate_lock_or_409(*, run_id: int, user_id: int) -> tuple[str, str]:
    lock_key = f"{REDIS_PREFIX}:lock:shopee:simulate:{run_id}:{user_id}"
    token = acquire_distributed_lock(lock_key, REDIS_LOCK_TTL_SEC)
    if token is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="订单模拟正在进行中，请稍后重试")
    return lock_key, token


def _append_inventory_stock_movement(
    db: Session,
    *,
    run_id: int,
    user_id: int,
    movement_type: str,
    qty_delta_on_hand: int = 0,
    qty_delta_reserved: int = 0,
    qty_delta_backorder: int = 0,
    product_id: int | None = None,
    listing_id: int | None = None,
    variant_id: int | None = None,
    inventory_lot_id: int | None = None,
    biz_order_id: int | None = None,
    biz_ref: str | None = None,
    remark: str | None = None,
) -> None:
    db.add(
        InventoryStockMovement(
            run_id=run_id,
            user_id=user_id,
            product_id=product_id,
            listing_id=listing_id,
            variant_id=variant_id,
            inventory_lot_id=inventory_lot_id,
            biz_order_id=biz_order_id,
            movement_type=movement_type,
            qty_delta_on_hand=qty_delta_on_hand,
            qty_delta_reserved=qty_delta_reserved,
            qty_delta_backorder=qty_delta_backorder,
            biz_ref=biz_ref,
            remark=remark,
        )
    )


def _apply_inbound_to_shopee_inventory_and_backorders(
    db: Session,
    *,
    run_id: int,
    user_id: int,
    product_inbound_qty_map: dict[int, int],
) -> None:
    if not product_inbound_qty_map:
        return

    changed_listing_ids: set[int] = set()
    product_ids = [pid for pid, qty in product_inbound_qty_map.items() if int(qty or 0) > 0]
    if not product_ids:
        return

    product_listings = (
        db.query(ShopeeListing)
        .filter(
            ShopeeListing.run_id == run_id,
            ShopeeListing.user_id == user_id,
            ShopeeListing.product_id.in_(product_ids),
        )
        .order_by(ShopeeListing.id.asc())
        .all()
    )
    product_listing_map: dict[int, list[ShopeeListing]] = {}
    for row in product_listings:
        if row.product_id is None:
            continue
        product_listing_map.setdefault(int(row.product_id), []).append(row)

    variants = (
        db.query(ShopeeListingVariant)
        .join(ShopeeListing, ShopeeListing.id == ShopeeListingVariant.listing_id)
        .filter(
            ShopeeListing.run_id == run_id,
            ShopeeListing.user_id == user_id,
            ShopeeListing.product_id.in_(product_ids),
        )
        .order_by(ShopeeListing.id.asc(), ShopeeListingVariant.sort_order.asc(), ShopeeListingVariant.id.asc())
        .all()
    )
    listing_variants_map: dict[int, list[ShopeeListingVariant]] = {}
    variant_map: dict[int, ShopeeListingVariant] = {}
    product_variant_map: dict[int, list[ShopeeListingVariant]] = {}
    for row in variants:
        variant_map[row.id] = row
        listing_variants_map.setdefault(int(row.listing_id), []).append(row)
        if row.listing and row.listing.product_id is not None:
            product_variant_map.setdefault(int(row.listing.product_id), []).append(row)

    for product_id in product_ids:
        remaining = max(0, int(product_inbound_qty_map.get(product_id) or 0))
        if remaining <= 0:
            continue

        backlog_orders = (
            db.query(ShopeeOrder)
            .join(ShopeeListing, ShopeeListing.id == ShopeeOrder.listing_id)
            .filter(
                ShopeeOrder.run_id == run_id,
                ShopeeOrder.user_id == user_id,
                ShopeeOrder.type_bucket == "toship",
                ShopeeOrder.stock_fulfillment_status == "backorder",
                ShopeeOrder.backorder_qty > 0,
                ShopeeListing.product_id == product_id,
            )
            .order_by(ShopeeOrder.created_at.asc(), ShopeeOrder.id.asc())
            .all()
        )

        for order in backlog_orders:
            if remaining <= 0:
                break
            needed = max(0, int(order.backorder_qty or 0))
            if needed <= 0:
                continue
            plan_fill_qty = min(remaining, needed)
            if plan_fill_qty <= 0:
                continue
            reserved_fill_qty = reserve_inventory_lots(
                db,
                run_id=run_id,
                product_id=product_id,
                qty=plan_fill_qty,
            )
            if reserved_fill_qty <= 0:
                continue
            remaining -= reserved_fill_qty
            order.backorder_qty = needed - reserved_fill_qty
            if order.backorder_qty <= 0:
                order.backorder_qty = 0
                order.stock_fulfillment_status = "restocked"
                order.must_restock_before_at = None
            matched_variant = variant_map.get(int(order.variant_id or 0))
            if matched_variant:
                matched_variant.oversell_used = max(0, int(matched_variant.oversell_used or 0) - reserved_fill_qty)
                changed_listing_ids.add(int(matched_variant.listing_id))
            if int(order.listing_id or 0) > 0:
                changed_listing_ids.add(int(order.listing_id))
            _append_inventory_stock_movement(
                db,
                run_id=run_id,
                user_id=user_id,
                movement_type="restock_fill",
                qty_delta_on_hand=0,
                qty_delta_reserved=reserved_fill_qty,
                qty_delta_backorder=-reserved_fill_qty,
                product_id=product_id,
                listing_id=int(order.listing_id or 0) or None,
                variant_id=int(order.variant_id or 0) or None,
                biz_order_id=order.id,
                biz_ref=order.order_no,
                remark="Step04入库后自动冲减待补货缺口",
            )

        if remaining <= 0:
            continue

        candidate_variants = list(product_variant_map.get(product_id, []))
        if not candidate_variants:
            listings_without_variants = [
                row
                for row in product_listing_map.get(product_id, [])
                if not list(row.variants or [])
            ]
            if listings_without_variants:
                per_listing = remaining // len(listings_without_variants)
                mod_listing = remaining % len(listings_without_variants)
                for idx, row in enumerate(listings_without_variants):
                    add_qty = per_listing + (1 if idx < mod_listing else 0)
                    if add_qty <= 0:
                        continue
                    row.stock_available = max(0, int(row.stock_available or 0) + add_qty)
                    changed_listing_ids.add(int(row.id))
            continue

        cnt = len(candidate_variants)
        base = remaining // cnt
        mod = remaining % cnt
        for idx, row in enumerate(candidate_variants):
            add_qty = base + (1 if idx < mod else 0)
            if add_qty <= 0:
                continue
            row.stock = max(0, int(row.stock or 0) + add_qty)
            changed_listing_ids.add(int(row.listing_id))

    if changed_listing_ids:
        affected_listings = (
            db.query(ShopeeListing)
            .filter(ShopeeListing.id.in_(list(changed_listing_ids)))
            .all()
        )
        for listing in affected_listings:
            listing.stock_available = int(sum(max(0, int(v.stock or 0)) for v in list(listing.variants or [])))


class CreateRunRequest(BaseModel):
    initial_cash: int = Field(ge=1000, le=100000000)
    market: str = Field(min_length=2, max_length=16)
    duration_days: int = Field(ge=7, le=3650)


class RunResponse(BaseModel):
    id: int
    user_id: int
    initial_cash: int
    market: str
    duration_days: int
    base_real_duration_days: int
    base_game_days: int
    total_game_days: int
    manual_end_time: datetime | None
    effective_end_time: datetime | None
    day_index: int
    status: str
    created_at: datetime


class CurrentRunResponse(BaseModel):
    run: RunResponse | None


class RunHistoryOptionsResponse(BaseModel):
    runs: list[RunResponse]


class RunHistorySummaryResponse(BaseModel):
    run: RunResponse
    initial_cash: float
    total_cash: float
    income_withdrawal_total: float
    total_expense: float
    current_balance: float
    procurement_order_count: int
    logistics_shipment_count: int
    warehouse_completed_inbound_count: int
    inventory_total_quantity: int
    inventory_total_sku: int
    shopee_order_total_count: int
    shopee_order_toship_count: int
    shopee_order_shipping_count: int
    shopee_order_completed_count: int
    shopee_order_cancelled_count: int
    shopee_order_sold_inventory_quantity: int
    shopee_order_generation_log_count: int


class ProcurementSummaryResponse(BaseModel):
    run_id: int
    initial_cash: float
    income_withdrawal_total: float
    total_expense: float
    current_balance: float
    total_cash: float
    spent_total: int
    logistics_spent_total: int
    warehouse_spent_total: int
    remaining_cash: float


class GameFinanceDetailRowResponse(BaseModel):
    id: str
    direction: str
    type: str
    type_label: str
    amount: float
    created_at: datetime
    remark: str | None = None


class GameFinanceDetailsResponse(BaseModel):
    tab: str
    page: int
    page_size: int
    total: int
    rows: list[GameFinanceDetailRowResponse]


class ProcurementOrderItemPayload(BaseModel):
    product_id: int
    quantity: int = Field(ge=1000, le=1000000)


class ProcurementCreateOrderRequest(BaseModel):
    items: list[ProcurementOrderItemPayload] = Field(min_length=1, max_length=200)


class ProcurementOrderItemResponse(BaseModel):
    product_id: int
    product_name: str
    unit_price: int
    quantity: int
    line_total: int


class ProcurementOrderResponse(BaseModel):
    id: int
    total_amount: int
    created_at: datetime
    items: list[ProcurementOrderItemResponse]


class ProcurementOrdersResponse(BaseModel):
    orders: list[ProcurementOrderResponse]


class ProcurementCreateOrderResponse(BaseModel):
    order_id: int
    total_amount: int
    spent_total: int
    remaining_cash: float


class LogisticsCreateShipmentRequest(BaseModel):
    order_ids: list[int] = Field(min_length=1, max_length=200)
    forwarder_key: str = Field(min_length=2, max_length=32)
    customs_key: str = Field(min_length=2, max_length=32)


class LogisticsShipmentResponse(BaseModel):
    id: int
    order_ids: list[int]
    forwarder_key: str
    forwarder_label: str
    customs_key: str
    customs_label: str
    cargo_value: int
    logistics_fee: int
    customs_fee: int
    total_fee: int
    transport_days: int
    customs_days: int
    created_at: datetime


class LogisticsShipmentsResponse(BaseModel):
    shipments: list[LogisticsShipmentResponse]


class LogisticsCreateShipmentResponse(BaseModel):
    shipment_id: int
    total_fee: int
    spent_total: int
    logistics_spent_total: int
    warehouse_spent_total: int
    remaining_cash: float


class LogisticsDebugAccelerateResponse(BaseModel):
    shipment_id: int
    status: str
    created_at: datetime


class WarehouseInboundCandidateItem(BaseModel):
    shipment_id: int
    cargo_value: int
    total_quantity: int
    created_at: datetime
    forwarder_label: str
    customs_label: str
    status: str


class WarehouseInboundCandidatesResponse(BaseModel):
    candidates: list[WarehouseInboundCandidateItem]


class WarehouseOptionsResponse(BaseModel):
    warehouse_modes: list[dict]
    warehouse_locations: list[dict]


class WarehouseLandmarkPointResponse(BaseModel):
    point_code: str
    point_name: str
    warehouse_mode: str
    warehouse_location: str
    lng: float
    lat: float
    sort_order: int


class WarehouseLandmarksResponse(BaseModel):
    market: str
    points: list[WarehouseLandmarkPointResponse]


class WarehouseStrategyCreateRequest(BaseModel):
    warehouse_mode: str = Field(min_length=2, max_length=32)
    warehouse_location: str = Field(min_length=2, max_length=32)


class WarehouseStrategyResponse(BaseModel):
    id: int
    warehouse_mode: str
    warehouse_location: str
    one_time_cost: int
    inbound_cost: int
    rent_cost: int
    total_cost: int
    delivery_eta_score: int
    fulfillment_accuracy: float
    warehouse_cost_per_order: int
    created_at: datetime


class WarehouseCreateStrategyResponse(BaseModel):
    strategy: WarehouseStrategyResponse
    remaining_cash: float


class WarehouseInboundRequest(BaseModel):
    # 按文档保留接口结构；V1 默认空则代表一次性入全部可入仓物流单
    shipment_ids: list[int] = Field(default_factory=list, max_length=500)


class WarehouseInboundResponse(BaseModel):
    inbound_count: int
    shipment_ids: list[int]
    inventory_lot_count: int
    remaining_cash: float


class WarehouseSummaryResponse(BaseModel):
    strategy: WarehouseStrategyResponse | None
    pending_inbound_count: int
    completed_inbound_count: int
    completed_inbound_total_quantity: int
    completed_inbound_total_value: int
    inventory_total_quantity: int
    inventory_total_sku: int


class WarehouseStockOverviewResponse(BaseModel):
    inventory_sku_count: int
    total_stock_qty: int
    available_stock_qty: int
    reserved_stock_qty: int
    backorder_qty: int
    locked_stock_qty: int


class WarehouseStockMovementItemResponse(BaseModel):
    id: int
    movement_type: str
    movement_type_label: str
    qty_delta_on_hand: int
    qty_delta_reserved: int
    qty_delta_backorder: int
    product_id: int | None
    listing_id: int | None
    variant_id: int | None
    biz_order_id: int | None
    biz_ref: str | None
    remark: str | None
    created_at: datetime


class WarehouseStockMovementsResponse(BaseModel):
    page: int
    page_size: int
    total: int
    rows: list[WarehouseStockMovementItemResponse]


class WarehouseBackorderRiskItemResponse(BaseModel):
    listing_id: int | None
    variant_id: int | None
    title: str
    sku: str | None
    pending_order_count: int
    backorder_qty_total: int
    overdue_order_count: int
    urgent_24h_order_count: int
    nearest_deadline_at: datetime | None
    estimated_cancel_amount: float


class WarehouseBackorderRiskOverviewResponse(BaseModel):
    current_tick: datetime
    affected_order_count: int
    backorder_qty_total: int
    overdue_order_count: int
    urgent_24h_order_count: int
    estimated_cancel_amount_total: float
    top_items: list[WarehouseBackorderRiskItemResponse]


class AdminBuyerPoolProfileResponse(BaseModel):
    id: int
    buyer_code: str
    nickname: str
    gender: str | None
    age: int | None
    city: str | None
    occupation: str | None
    background: str | None
    preferred_categories: list[str]
    base_buy_intent: float
    price_sensitivity: float
    quality_sensitivity: float
    brand_sensitivity: float
    impulse_level: float
    purchase_power: float
    current_hour_active_prob: float
    current_hour_order_intent_prob: float
    peak_hour: int


class AdminBuyerPoolOverviewResponse(BaseModel):
    selected_run_id: int | None
    selected_run_status: str | None
    selected_run_market: str | None
    selected_run_username: str | None
    selected_run_day_index: int | None
    selected_run_duration_days: int | None
    selected_run_base_real_duration_days: int | None
    selected_run_base_game_days: int | None
    selected_run_total_game_days: int | None
    selected_run_created_at: datetime | None
    selected_run_manual_end_time: datetime | None
    selected_run_end_time: datetime | None
    server_time: datetime
    game_clock: str
    game_hour: int
    game_minute: int
    buyer_count: int
    currently_active_estimate: float
    expected_orders_per_hour: float
    profiles: list[AdminBuyerPoolProfileResponse]


class AdminRunOptionResponse(BaseModel):
    run_id: int
    user_id: int
    username: str
    status: str
    market: str
    day_index: int
    duration_days: int
    base_real_duration_days: int
    base_game_days: int
    total_game_days: int
    created_at: datetime
    manual_end_time: datetime | None
    end_time: datetime


class AdminRunOptionsResponse(BaseModel):
    runs: list[AdminRunOptionResponse]


class AdminActiveRunItemResponse(BaseModel):
    run_id: int
    user_id: int
    username: str
    status: str
    market: str
    duration_days: int
    base_real_duration_days: int
    base_game_days: int
    total_game_days: int
    current_day_index: int
    created_at: datetime
    manual_end_time: datetime | None
    end_time: datetime
    remaining_seconds: int


class AdminActiveRunsResponse(BaseModel):
    runs: list[AdminActiveRunItemResponse]


class AdminExtendRunRequest(BaseModel):
    extend_days: int = Field(ge=1, le=3650)


class AdminExtendRunResponse(BaseModel):
    run_id: int
    user_id: int
    username: str
    status: str
    market: str
    old_duration_days: int
    new_duration_days: int
    base_real_duration_days: int
    base_game_days: int
    total_game_days: int
    current_day_index: int
    created_at: datetime
    manual_end_time: datetime | None
    new_end_time: datetime
    remaining_seconds: int


class AdminRenewRunRequest(BaseModel):
    extend_days: int = Field(ge=1, le=3650)


class AdminRenewRunResponse(BaseModel):
    run_id: int
    user_id: int
    username: str
    old_status: str
    new_status: str
    market: str
    old_duration_days: int
    new_duration_days: int
    old_total_game_days: int
    new_total_game_days: int
    base_real_duration_days: int
    base_game_days: int
    current_day_index: int
    created_at: datetime
    old_end_time: datetime
    new_end_time: datetime
    manual_end_time: datetime | None
    remaining_seconds: int


class AdminSimulateOrdersResponse(BaseModel):
    tick_time: datetime
    active_buyer_count: int
    candidate_product_count: int
    generated_order_count: int
    skip_reasons: dict[str, int] = Field(default_factory=dict)
    shop_context: dict[str, Any] = Field(default_factory=dict)
    buyer_journeys: list[dict[str, Any]] = Field(default_factory=list)
    cancellation_logs: list[dict[str, Any]] = Field(default_factory=list)


def _require_super_admin_or_403(current_user: dict):
    if (current_user.get("role") or "").strip() != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅超级管理员可访问")


def _parse_float_list(raw_json: str, expected_len: int, fallback: float) -> list[float]:
    try:
        raw = json.loads(raw_json or "[]")
    except Exception:
        raw = []
    if not isinstance(raw, list):
        raw = []
    values = []
    for i in range(expected_len):
        item = raw[i] if i < len(raw) else fallback
        try:
            num = float(item)
        except Exception:
            num = fallback
        values.append(max(0.0, min(1.0, num)))
    return values


def _parse_str_list(raw_json: str) -> list[str]:
    try:
        raw = json.loads(raw_json or "[]")
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    result: list[str] = []
    for item in raw:
        text = str(item).strip()
        if text:
            result.append(text)
    return result


def _resolve_run_base_real_duration_days(run: GameRun) -> int:
    return max(1, int(run.base_real_duration_days or run.duration_days or 1))


def _resolve_run_base_game_days(run: GameRun) -> int:
    return max(1, int(run.base_game_days or DEFAULT_TOTAL_GAME_DAYS))


def _resolve_run_total_game_days(run: GameRun) -> int:
    if run.total_game_days is not None and int(run.total_game_days or 0) > 0:
        return int(run.total_game_days)
    base_real_duration_days = _resolve_run_base_real_duration_days(run)
    duration_days = max(1, int(run.duration_days or base_real_duration_days))
    base_game_days = _resolve_run_base_game_days(run)
    return max(1, int(round(duration_days / base_real_duration_days * base_game_days)))


def _resolve_run_duration_days_by_end_time(run: GameRun, end_time: datetime) -> int:
    if not run.created_at:
        return max(1, int(run.duration_days or 1))
    compare_end_time = _align_compare_time(run.created_at, end_time)
    total_seconds = max(1, int((compare_end_time - run.created_at).total_seconds()))
    return max(1, int((total_seconds + 86400 - 1) // 86400))


def _resolve_run_total_game_days_by_end_time(run: GameRun, end_time: datetime) -> int:
    if not run.created_at:
        return _resolve_run_total_game_days(run)
    compare_end_time = _align_compare_time(run.created_at, end_time)
    total_seconds = max(1, int((compare_end_time - run.created_at).total_seconds()))
    base_real_seconds = _resolve_run_base_real_duration_days(run) * 24 * 60 * 60
    old_end_time = _resolve_run_end_time(run)
    old_total_game_days = _resolve_run_total_game_days(run)
    computed_total_game_days = max(1, int(round(total_seconds / base_real_seconds * _resolve_run_base_game_days(run))))
    if old_end_time is not None and compare_end_time > _align_compare_time(run.created_at, old_end_time):
        return max(old_total_game_days + 1, computed_total_game_days)
    return computed_total_game_days


def _resolve_run_effective_duration_seconds(run: GameRun) -> int:
    if not run.created_at:
        return max(1, int(run.duration_days or 1)) * 24 * 60 * 60
    run_end_time = _resolve_run_end_time(run)
    if not run_end_time:
        return max(1, int(run.duration_days or 1)) * 24 * 60 * 60
    return max(1, int((_align_compare_time(run.created_at, run_end_time) - run.created_at).total_seconds()))


def _resolve_run_elapsed_seconds(run: GameRun, *, now: datetime | None = None) -> int:
    if not run.created_at:
        return 0
    now = now or datetime.utcnow()
    compare_now = _align_compare_time(run.created_at, now)
    run_end_time = _resolve_run_end_time(run)
    if run_end_time is not None:
        compare_now = min(compare_now, _align_compare_time(run.created_at, run_end_time))
    return max(0, int((compare_now - run.created_at).total_seconds()))


def _resolve_game_day_float_by_run(run: GameRun, *, now: datetime | None = None) -> float:
    total_real_seconds = _resolve_run_effective_duration_seconds(run)
    elapsed_seconds = _resolve_run_elapsed_seconds(run, now=now)
    total_game_days = _resolve_run_total_game_days(run)
    return (elapsed_seconds / total_real_seconds) * total_game_days + 1


def _resolve_game_day_index_by_run(run: GameRun, *, now: datetime | None = None) -> int:
    total_game_days = _resolve_run_total_game_days(run)
    game_day_float = _resolve_game_day_float_by_run(run, now=now)
    return min(total_game_days, max(1, int(game_day_float)))


def _resolve_game_clock_info_by_run(run: GameRun, *, now: datetime | None = None) -> tuple[str, int, int]:
    game_day_float = _resolve_game_day_float_by_run(run, now=now)
    frac = max(0.0, game_day_float - int(game_day_float))
    seconds_of_day = max(0, int(frac * 24 * 60 * 60))
    game_hour = (seconds_of_day // 3600) % 24
    game_minute = (seconds_of_day % 3600) // 60
    game_clock = f"{game_hour:02d}:{game_minute:02d}:{seconds_of_day % 60:02d}"
    return game_clock, game_hour, game_minute


def _resolve_run_remaining_seconds(run: GameRun, *, now: datetime | None = None) -> int:
    run_end_time = _resolve_run_end_time(run)
    if not run_end_time:
        return 0
    now = now or datetime.utcnow()
    compare_now = _align_compare_time(run_end_time, now)
    return max(0, int((run_end_time - compare_now).total_seconds()))


def _auto_finish_expired_running_runs(db: Session, *, now: datetime | None = None) -> int:
    now = now or datetime.utcnow()
    runs = db.query(GameRun).filter(GameRun.status == "running").all()
    updated = 0
    for run in runs:
        if _persist_run_finished_if_reached(db, run, tick_time=now):
            updated += 1
    if updated > 0:
        db.commit()
    return updated


@router.get("/admin/buyer-pool/overview", response_model=AdminBuyerPoolOverviewResponse)
def get_admin_buyer_pool_overview(
    run_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> AdminBuyerPoolOverviewResponse:
    _require_super_admin_or_403(current_user)
    cached_payload = cache_get_json(_game_overview_cache_key(name="buyer_pool_overview", run_id=run_id))
    if isinstance(cached_payload, dict):
        return AdminBuyerPoolOverviewResponse.model_validate(cached_payload)

    selected_run: GameRun | None = None
    selected_run_username: str | None = None
    selected_run_day_index: int | None = None
    selected_run_duration_days: int | None = None
    selected_run_base_real_duration_days: int | None = None
    selected_run_base_game_days: int | None = None
    selected_run_total_game_days: int | None = None
    selected_run_manual_end_time: datetime | None = None
    selected_run_end_time: datetime | None = None
    if run_id is not None:
        selected_run = db.query(GameRun).filter(GameRun.id == run_id).first()
        if not selected_run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    else:
        selected_run = db.query(GameRun).order_by(GameRun.id.desc()).first()
    if selected_run:
        selected_run_username = (
            db.query(User.username).filter(User.id == selected_run.user_id).scalar()
        )
        selected_run_day_index = _resolve_game_day_index_by_run(selected_run)
        selected_run_duration_days = int(selected_run.duration_days or 0)
        selected_run_base_real_duration_days = _resolve_run_base_real_duration_days(selected_run)
        selected_run_base_game_days = max(1, int(selected_run.base_game_days or DEFAULT_TOTAL_GAME_DAYS))
        selected_run_total_game_days = _resolve_run_total_game_days(selected_run)
        selected_run_manual_end_time = selected_run.manual_end_time
        selected_run_end_time = _resolve_run_end_time(selected_run)

    server_now = datetime.now()
    if selected_run:
        game_clock, game_hour, game_minute = _resolve_game_clock_info_by_run(selected_run)
    else:
        seconds_of_day = server_now.hour * 3600 + server_now.minute * 60 + server_now.second
        game_minutes = seconds_of_day % (24 * 60)
        game_hour = game_minutes // 60
        game_minute = game_minutes % 60
        game_clock = f"{game_hour:02d}:{game_minute:02d}:{seconds_of_day % 60:02d}"

    rows = (
        db.query(SimBuyerProfile)
        .filter(SimBuyerProfile.is_active == True)
        .order_by(SimBuyerProfile.buyer_code.asc())
        .all()
    )

    profiles: list[AdminBuyerPoolProfileResponse] = []
    currently_active_estimate = 0.0
    expected_orders_per_hour = 0.0

    for row in rows:
        active_hours = _parse_float_list(row.active_hours_json, 24, 0.05)
        current_hour_active = active_hours[game_hour]
        peak_hour = max(range(24), key=lambda i: active_hours[i])
        base_intent = max(0.0, min(1.0, float(row.base_buy_intent or 0.0)))
        current_hour_order_intent = max(0.0, min(1.0, current_hour_active * base_intent))

        currently_active_estimate += current_hour_active
        expected_orders_per_hour += current_hour_order_intent

        profiles.append(
            AdminBuyerPoolProfileResponse(
                id=row.id,
                buyer_code=row.buyer_code,
                nickname=row.nickname,
                gender=row.gender,
                age=row.age,
                city=row.city,
                occupation=row.occupation,
                background=row.background,
                preferred_categories=_parse_str_list(row.preferred_categories_json),
                base_buy_intent=base_intent,
                price_sensitivity=max(0.0, min(1.0, float(row.price_sensitivity or 0.0))),
                quality_sensitivity=max(0.0, min(1.0, float(row.quality_sensitivity or 0.0))),
                brand_sensitivity=max(0.0, min(1.0, float(row.brand_sensitivity or 0.0))),
                impulse_level=max(0.0, min(1.0, float(row.impulse_level or 0.0))),
                purchase_power=max(0.0, min(1.0, float(row.purchase_power or 0.0))),
                current_hour_active_prob=current_hour_active,
                current_hour_order_intent_prob=current_hour_order_intent,
                peak_hour=peak_hour,
            )
        )

    response = AdminBuyerPoolOverviewResponse(
        selected_run_id=selected_run.id if selected_run else None,
        selected_run_status=selected_run.status if selected_run else None,
        selected_run_market=selected_run.market if selected_run else None,
        selected_run_username=selected_run_username,
        selected_run_day_index=selected_run_day_index if selected_run else None,
        selected_run_duration_days=selected_run_duration_days,
        selected_run_base_real_duration_days=selected_run_base_real_duration_days,
        selected_run_base_game_days=selected_run_base_game_days,
        selected_run_total_game_days=selected_run_total_game_days,
        selected_run_created_at=selected_run.created_at if selected_run else None,
        selected_run_manual_end_time=selected_run_manual_end_time,
        selected_run_end_time=selected_run_end_time,
        server_time=server_now,
        game_clock=game_clock,
        game_hour=game_hour,
        game_minute=game_minute,
        buyer_count=len(profiles),
        currently_active_estimate=round(currently_active_estimate, 3),
        expected_orders_per_hour=round(expected_orders_per_hour, 3),
        profiles=profiles,
    )
    cache_set_json(
        _game_overview_cache_key(name="buyer_pool_overview", run_id=run_id),
        response.model_dump(mode="json"),
        REDIS_CACHE_TTL_OVERVIEW_SEC,
    )
    return response


@router.get("/admin/runs/options", response_model=AdminRunOptionsResponse)
def get_admin_run_options(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> AdminRunOptionsResponse:
    _require_super_admin_or_403(current_user)

    rows = (
        db.query(GameRun, User.username)
        .join(User, User.id == GameRun.user_id)
        .order_by(GameRun.id.desc())
        .limit(200)
        .all()
    )
    runs = [
        AdminRunOptionResponse(
            run_id=run.id,
            user_id=run.user_id,
            username=username,
            status=run.status,
            market=run.market,
            day_index=_resolve_game_day_index_by_run(run),
            duration_days=run.duration_days,
            base_real_duration_days=_resolve_run_base_real_duration_days(run),
            base_game_days=max(1, int(run.base_game_days or DEFAULT_TOTAL_GAME_DAYS)),
            total_game_days=_resolve_run_total_game_days(run),
            created_at=run.created_at,
            manual_end_time=run.manual_end_time,
            end_time=_resolve_run_end_time(run),
        )
        for run, username in rows
    ]
    return AdminRunOptionsResponse(runs=runs)


@router.get("/admin/runs/active", response_model=AdminActiveRunsResponse)
def get_admin_active_runs(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> AdminActiveRunsResponse:
    _require_super_admin_or_403(current_user)
    _auto_finish_expired_running_runs(db)

    rows = (
        db.query(GameRun, User.username)
        .join(User, User.id == GameRun.user_id)
        .filter(GameRun.status == "running")
        .order_by(GameRun.id.desc())
        .all()
    )
    runs = [
        AdminActiveRunItemResponse(
            run_id=run.id,
            user_id=run.user_id,
            username=username,
            status=run.status,
            market=run.market,
            duration_days=run.duration_days,
            base_real_duration_days=_resolve_run_base_real_duration_days(run),
            base_game_days=max(1, int(run.base_game_days or DEFAULT_TOTAL_GAME_DAYS)),
            total_game_days=_resolve_run_total_game_days(run),
            current_day_index=_resolve_game_day_index_by_run(run),
            created_at=run.created_at,
            manual_end_time=run.manual_end_time,
            end_time=_resolve_run_end_time(run),
            remaining_seconds=_resolve_run_remaining_seconds(run),
        )
        for run, username in rows
    ]
    return AdminActiveRunsResponse(runs=runs)


@router.post("/admin/runs/{run_id}/extend", response_model=AdminExtendRunResponse)
def admin_extend_run(
    run_id: int,
    payload: AdminExtendRunRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> AdminExtendRunResponse:
    _require_super_admin_or_403(current_user)

    run = db.query(GameRun).filter(GameRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if _persist_run_finished_if_reached(db, run):
        db.commit()
        db.refresh(run)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=RUN_EXTEND_FINISHED_DETAIL)
    if (run.status or "").strip() != "running":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run is not running")

    safe_extend_days = int(payload.extend_days)
    old_duration_days = int(run.duration_days or 0)
    old_end_time = _resolve_run_end_time(run)
    run.duration_days = old_duration_days + safe_extend_days
    if run.manual_end_time is not None and old_end_time is not None:
        run.manual_end_time = old_end_time + timedelta(days=safe_extend_days)
    db.commit()
    db.refresh(run)
    _invalidate_admin_run_related_cache(run_id=run.id, user_id=run.user_id)

    owner_username = db.query(User.username).filter(User.id == run.user_id).scalar()
    return AdminExtendRunResponse(
        run_id=run.id,
        user_id=run.user_id,
        username=owner_username or "",
        status=run.status,
        market=run.market,
        old_duration_days=old_duration_days,
        new_duration_days=run.duration_days,
        base_real_duration_days=_resolve_run_base_real_duration_days(run),
        base_game_days=max(1, int(run.base_game_days or DEFAULT_TOTAL_GAME_DAYS)),
        total_game_days=_resolve_run_total_game_days(run),
        current_day_index=_resolve_game_day_index_by_run(run),
        created_at=run.created_at,
        manual_end_time=run.manual_end_time,
        new_end_time=_resolve_run_end_time(run),
        remaining_seconds=_resolve_run_remaining_seconds(run),
    )


@router.post("/admin/runs/{run_id}/renew", response_model=AdminRenewRunResponse)
def admin_renew_run(
    run_id: int,
    payload: AdminRenewRunRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> AdminRenewRunResponse:
    _require_super_admin_or_403(current_user)

    run = db.query(GameRun).filter(GameRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if (run.status or "").strip() != "finished":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅已结束对局支持续期恢复")

    existing_running = (
        db.query(GameRun)
        .filter(
            GameRun.user_id == run.user_id,
            GameRun.status == "running",
            GameRun.id != run.id,
        )
        .first()
    )
    if existing_running:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该玩家已有其他运行中对局，无法恢复旧对局")

    safe_extend_days = int(payload.extend_days)
    old_status = (run.status or "").strip()
    old_duration_days = int(run.duration_days or 0)
    old_total_game_days = _resolve_run_total_game_days(run)
    old_end_time = _resolve_run_end_time(run)
    if old_end_time is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前对局缺少有效结束时间，无法续期恢复")

    new_end_time = old_end_time + timedelta(days=safe_extend_days)
    now = datetime.utcnow()
    if _align_compare_time(new_end_time, now) >= new_end_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="续期后的结束时间必须晚于当前时间")
    run.status = "running"
    run.duration_days = _resolve_run_duration_days_by_end_time(run, new_end_time)
    run.manual_end_time = new_end_time
    run.total_game_days = _resolve_run_total_game_days_by_end_time(run, new_end_time)
    db.commit()
    db.refresh(run)
    _invalidate_admin_run_related_cache(run_id=run.id, user_id=run.user_id)

    owner_username = db.query(User.username).filter(User.id == run.user_id).scalar()
    return AdminRenewRunResponse(
        run_id=run.id,
        user_id=run.user_id,
        username=owner_username or "",
        old_status=old_status,
        new_status=run.status,
        market=run.market,
        old_duration_days=old_duration_days,
        new_duration_days=int(run.duration_days or 0),
        old_total_game_days=old_total_game_days,
        new_total_game_days=_resolve_run_total_game_days(run),
        base_real_duration_days=_resolve_run_base_real_duration_days(run),
        base_game_days=_resolve_run_base_game_days(run),
        current_day_index=_resolve_game_day_index_by_run(run),
        created_at=run.created_at,
        old_end_time=old_end_time,
        new_end_time=_resolve_run_end_time(run) or new_end_time,
        manual_end_time=run.manual_end_time,
        remaining_seconds=_resolve_run_remaining_seconds(run),
    )


@router.post("/admin/runs/{run_id}/orders/simulate", response_model=AdminSimulateOrdersResponse)
def admin_simulate_orders(
    run_id: int,
    tick_time: datetime | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> AdminSimulateOrdersResponse:
    _require_super_admin_or_403(current_user)
    _enforce_admin_simulate_rate_limit(admin_user_id=int(current_user["id"]))
    run = db.query(GameRun).filter(GameRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if _persist_run_finished_if_reached(db, run):
        db.commit()
        db.refresh(run)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=RUN_FINISHED_DETAIL)
    if (run.status or "").strip() != "running":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run is not running")
    lock_key, lock_token = _acquire_admin_simulate_lock_or_409(run_id=run.id, user_id=run.user_id)

    effective_tick_time = tick_time
    if effective_tick_time is None:
        latest_tick_time = (
            db.query(func.max(ShopeeOrderGenerationLog.tick_time))
            .filter(
                ShopeeOrderGenerationLog.run_id == run.id,
                ShopeeOrderGenerationLog.user_id == run.user_id,
            )
            .scalar()
        )
        if latest_tick_time:
            effective_tick_time = latest_tick_time + timedelta(hours=1)
        else:
            effective_tick_time = datetime.utcnow()

    try:
        result = simulate_orders_for_run(db, run_id=run.id, user_id=run.user_id, tick_time=effective_tick_time)
        cancellation_logs = auto_cancel_overdue_orders_by_tick(
            db,
            run_id=run.id,
            user_id=run.user_id,
            current_tick=result["tick_time"],
            commit=True,
        )
        _invalidate_shopee_orders_cache_for_user(run_id=run.id, user_id=run.user_id)
        owner_username = db.query(User.username).filter(User.id == run.user_id).scalar()
        return AdminSimulateOrdersResponse(
            tick_time=result["tick_time"],
            active_buyer_count=result["active_buyer_count"],
            candidate_product_count=result["candidate_product_count"],
            generated_order_count=result["generated_order_count"],
            skip_reasons=result["skip_reasons"],
            shop_context={
                "run_id": run.id,
                "user_id": run.user_id,
                "username": owner_username,
                "market": run.market,
                "status": run.status,
            },
            buyer_journeys=result.get("buyer_journeys") or [],
            cancellation_logs=cancellation_logs,
        )
    finally:
        release_distributed_lock(lock_key, lock_token)


def _to_warehouse_strategy_response(row: WarehouseStrategy) -> WarehouseStrategyResponse:
    return WarehouseStrategyResponse(
        id=row.id,
        warehouse_mode=row.warehouse_mode,
        warehouse_location=row.warehouse_location,
        one_time_cost=row.one_time_cost,
        inbound_cost=row.inbound_cost,
        rent_cost=row.rent_cost,
        total_cost=row.total_cost,
        delivery_eta_score=row.delivery_eta_score,
        fulfillment_accuracy=row.fulfillment_accuracy,
        warehouse_cost_per_order=row.warehouse_cost_per_order,
        created_at=row.created_at,
    )


def _to_run_response(run: GameRun) -> RunResponse:
    return RunResponse(
        id=run.id,
        user_id=run.user_id,
        initial_cash=run.initial_cash,
        market=run.market,
        duration_days=run.duration_days,
        base_real_duration_days=_resolve_run_base_real_duration_days(run),
        base_game_days=max(1, int(run.base_game_days or DEFAULT_TOTAL_GAME_DAYS)),
        total_game_days=_resolve_run_total_game_days(run),
        manual_end_time=run.manual_end_time,
        effective_end_time=_resolve_run_end_time(run),
        day_index=_resolve_game_day_index_by_run(run),
        status=run.status,
        created_at=run.created_at,
    )


def _get_owned_running_run_or_404(db: Session, run_id: int, user_id: int) -> GameRun:
    run = (
        db.query(GameRun)
        .filter(
            GameRun.id == run_id,
            GameRun.user_id == user_id,
            GameRun.status == "running",
        )
        .first()
    )
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Running game not found")
    return run


def _get_owned_readable_run_or_404(db: Session, run_id: int, user_id: int) -> GameRun:
    run = (
        db.query(GameRun)
        .filter(
            GameRun.id == run_id,
            GameRun.user_id == user_id,
            GameRun.status.in_(("running", "finished")),
        )
        .first()
    )
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    return run


def _get_owned_writable_run_or_400(db: Session, run_id: int, user_id: int) -> GameRun:
    run = (
        db.query(GameRun)
        .filter(
            GameRun.id == run_id,
            GameRun.user_id == user_id,
        )
        .first()
    )
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    if _persist_run_finished_if_reached(db, run):
        db.commit()
        db.refresh(run)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=RUN_FINISHED_DETAIL)
    if (run.status or "").strip() != "running":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run is not running")
    return run


def _calc_run_procurement_spent(db: Session, run_id: int) -> int:
    spent = db.query(func.coalesce(func.sum(ProcurementOrder.total_amount), 0)).filter(ProcurementOrder.run_id == run_id).scalar()
    return int(spent or 0)


def _calc_run_logistics_spent(db: Session, run_id: int) -> int:
    spent = db.query(func.coalesce(func.sum(LogisticsShipment.total_fee), 0)).filter(LogisticsShipment.run_id == run_id).scalar()
    return int(spent or 0)


def _calc_run_warehouse_spent(db: Session, run_id: int) -> int:
    spent = db.query(func.coalesce(func.sum(WarehouseStrategy.total_cost), 0)).filter(WarehouseStrategy.run_id == run_id).scalar()
    return int(spent or 0)


def _calc_run_cash_adjustment_in(db: Session, run_id: int) -> float:
    amount = (
        db.query(func.coalesce(func.sum(GameRunCashAdjustment.amount), 0.0))
        .filter(
            GameRunCashAdjustment.run_id == run_id,
            GameRunCashAdjustment.direction == "in",
        )
        .scalar()
        or 0.0
    )
    return round(float(amount), 2)


def _calc_run_withdrawal_income_total(db: Session, run_id: int) -> float:
    amount = (
        db.query(func.coalesce(func.sum(GameRunCashAdjustment.amount), 0.0))
        .filter(
            GameRunCashAdjustment.run_id == run_id,
            GameRunCashAdjustment.direction == "in",
            GameRunCashAdjustment.source == "shopee_withdrawal",
        )
        .scalar()
        or 0.0
    )
    return round(float(amount), 2)


def _calc_run_cash_adjustment_out(db: Session, run_id: int) -> float:
    amount = (
        db.query(func.coalesce(func.sum(GameRunCashAdjustment.amount), 0.0))
        .filter(
            GameRunCashAdjustment.run_id == run_id,
            GameRunCashAdjustment.direction == "out",
        )
        .scalar()
        or 0.0
    )
    return round(float(amount), 2)


def _calc_run_total_cash(db: Session, run: GameRun) -> float:
    adjustment_in = _calc_run_cash_adjustment_in(db, run.id)
    adjustment_out = _calc_run_cash_adjustment_out(db, run.id)
    return round(float(run.initial_cash) + adjustment_in - adjustment_out, 2)


def _calc_run_remaining_cash(
    db: Session,
    run: GameRun,
    *,
    procurement_spent_total: int,
    logistics_spent_total: int,
    warehouse_spent_total: int,
) -> float:
    total_cash = _calc_run_total_cash(db, run)
    remaining = total_cash - float(procurement_spent_total) - float(logistics_spent_total) - float(warehouse_spent_total)
    return round(max(0.0, remaining), 2)


def _list_run_income_detail_rows(db: Session, run_id: int) -> list[GameFinanceDetailRowResponse]:
    rows = (
        db.query(GameRunCashAdjustment)
        .filter(
            GameRunCashAdjustment.run_id == run_id,
            GameRunCashAdjustment.direction == "in",
            GameRunCashAdjustment.source == "shopee_withdrawal",
        )
        .order_by(GameRunCashAdjustment.created_at.desc(), GameRunCashAdjustment.id.desc())
        .all()
    )
    return [
        GameFinanceDetailRowResponse(
            id=f"cash_adj:{row.id}",
            direction="in",
            type="withdrawal_transfer",
            type_label="提现转入",
            amount=round(float(row.amount or 0), 2),
            created_at=row.created_at,
            remark=row.remark,
        )
        for row in rows
    ]


def _list_run_expense_detail_rows(db: Session, run_id: int) -> list[GameFinanceDetailRowResponse]:
    procurement_rows = (
        db.query(ProcurementOrder)
        .filter(ProcurementOrder.run_id == run_id)
        .order_by(ProcurementOrder.created_at.desc(), ProcurementOrder.id.desc())
        .all()
    )
    logistics_rows = (
        db.query(LogisticsShipment)
        .filter(LogisticsShipment.run_id == run_id)
        .order_by(LogisticsShipment.created_at.desc(), LogisticsShipment.id.desc())
        .all()
    )
    warehouse_rows = (
        db.query(WarehouseStrategy)
        .filter(WarehouseStrategy.run_id == run_id)
        .order_by(WarehouseStrategy.created_at.desc(), WarehouseStrategy.id.desc())
        .all()
    )

    merged: list[GameFinanceDetailRowResponse] = []
    merged.extend(
        [
            GameFinanceDetailRowResponse(
                id=f"procurement:{row.id}",
                direction="out",
                type="procurement",
                type_label="采购支出",
                amount=round(float(row.total_amount or 0), 2),
                created_at=row.created_at,
                remark=f"采购单 #{row.id}",
            )
            for row in procurement_rows
        ]
    )
    merged.extend(
        [
            GameFinanceDetailRowResponse(
                id=f"logistics:{row.id}",
                direction="out",
                type="logistics",
                type_label="物流支出",
                amount=round(float(row.total_fee or 0), 2),
                created_at=row.created_at,
                remark=f"物流单 #{row.id}",
            )
            for row in logistics_rows
        ]
    )
    merged.extend(
        [
            GameFinanceDetailRowResponse(
                id=f"warehouse:{row.id}",
                direction="out",
                type="warehouse",
                type_label="仓储支出",
                amount=round(float(row.total_cost or 0), 2),
                created_at=row.created_at,
                remark=f"仓储策略 #{row.id}",
            )
            for row in warehouse_rows
        ]
    )
    merged.sort(key=lambda item: (item.created_at, item.id), reverse=True)
    return merged


def _warehouse_mode_options() -> dict[str, dict]:
    return {
        "official": {
            "label": "Shopee 官方仓",
            "one_time_base": 0,
            "inbound_rate": 0.018,
            "rent_base": 8000,
            "delivery_eta_score": 92,
            "fulfillment_accuracy": 0.992,
            "warehouse_cost_per_order": 6,
        },
        "third_party": {
            "label": "第三方仓",
            "one_time_base": 0,
            "inbound_rate": 0.012,
            "rent_base": 5200,
            "delivery_eta_score": 78,
            "fulfillment_accuracy": 0.945,
            "warehouse_cost_per_order": 4,
        },
        "self_built": {
            "label": "自建仓",
            "one_time_base": 50000,
            "inbound_rate": 0.009,
            "rent_base": 2800,
            "delivery_eta_score": 95,
            "fulfillment_accuracy": 0.995,
            "warehouse_cost_per_order": 3,
        },
    }


def _warehouse_location_options() -> dict[str, dict]:
    return {
        "near_kl": {
            "label": "近吉隆坡仓位",
            "rent_delta": 2200,
            "eta_delta": 4,
        },
        "far_kl": {
            "label": "远吉隆坡仓位",
            "rent_delta": -1000,
            "eta_delta": -3,
        },
    }


def _calc_shipment_status(shipment: LogisticsShipment, now: datetime) -> str:
    created = shipment.created_at
    if created.tzinfo is not None and now.tzinfo is None:
        now = now.replace(tzinfo=created.tzinfo)
    elif created.tzinfo is None and now.tzinfo is not None:
        now = now.replace(tzinfo=None)
    elapsed_seconds = max(0, int((now - created).total_seconds()))
    transport_seconds = max(1, int(shipment.transport_days * REAL_SECONDS_PER_GAME_DAY))
    customs_seconds = max(1, int(shipment.customs_days * REAL_SECONDS_PER_GAME_DAY))
    if elapsed_seconds >= BOOKED_SECONDS + transport_seconds + customs_seconds:
        return "customs_cleared"
    if elapsed_seconds >= BOOKED_SECONDS + transport_seconds:
        return "customs_processing"
    if elapsed_seconds >= BOOKED_SECONDS:
        return "in_transit"
    return "booked"


def _align_compare_time(ref: datetime, val: datetime) -> datetime:
    if ref.tzinfo is not None and val.tzinfo is None:
        return val.replace(tzinfo=ref.tzinfo)
    if ref.tzinfo is None and val.tzinfo is not None:
        return val.replace(tzinfo=None)
    return val


def _resolve_run_end_time(run: GameRun) -> datetime | None:
    if not run.created_at:
        return None
    if run.manual_end_time is not None:
        return _align_compare_time(run.created_at, run.manual_end_time)
    return run.created_at + timedelta(days=max(1, int(run.duration_days or 1)))


def _resolve_game_hour_tick_by_run(run: GameRun, now: datetime | None = None) -> datetime:
    now = now or datetime.utcnow()
    if not run.created_at:
        return now
    compare_now = _align_compare_time(run.created_at, now)
    elapsed_seconds = max(0, int((compare_now - run.created_at).total_seconds()))
    elapsed_game_hours = int(elapsed_seconds // REAL_SECONDS_PER_GAME_HOUR)
    tick_time = run.created_at + timedelta(hours=elapsed_game_hours)
    run_end_time = _resolve_run_end_time(run)
    if not run_end_time:
        return tick_time
    compare_tick = _align_compare_time(run_end_time, tick_time)
    return min(compare_tick, run_end_time)


def _mark_run_finished_if_reached(db: Session, run: GameRun, *, tick_time: datetime | None = None) -> bool:
    status_value = (run.status or "").strip()
    if status_value == "finished":
        return True
    if status_value != "running":
        return False
    run_end_time = _resolve_run_end_time(run)
    if not run_end_time:
        return False
    compare_time = tick_time or datetime.utcnow()
    compare_time = _align_compare_time(run_end_time, compare_time)
    if compare_time < run_end_time:
        return False
    run.status = "finished"
    return True


def _persist_run_finished_if_reached(db: Session, run: GameRun, *, tick_time: datetime | None = None) -> bool:
    old_status = (run.status or "").strip()
    reached = _mark_run_finished_if_reached(db, run, tick_time=tick_time)
    if not reached:
        return False
    if old_status != "finished" and (run.status or "").strip() == "finished":
        db.commit()
        db.refresh(run)
    return True


def _auto_finish_expired_running_runs_for_user(db: Session, *, user_id: int, now: datetime | None = None) -> int:
    now = now or datetime.utcnow()
    runs = (
        db.query(GameRun)
        .filter(
            GameRun.user_id == user_id,
            GameRun.status == "running",
        )
        .all()
    )
    updated = 0
    for run in runs:
        if _persist_run_finished_if_reached(db, run, tick_time=now):
            updated += 1
    if updated > 0:
        db.commit()
    return updated


@router.get("/runs/current", response_model=CurrentRunResponse)
def get_current_run(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CurrentRunResponse:
    _auto_finish_expired_running_runs_for_user(db, user_id=int(current_user["id"]))
    run = (
        db.query(GameRun)
        .filter(
            GameRun.user_id == current_user["id"],
            GameRun.status == "running",
        )
        .order_by(GameRun.id.desc())
        .first()
    )
    if not run:
        return CurrentRunResponse(run=None)
    return CurrentRunResponse(run=_to_run_response(run))


@router.get("/runs/history/options", response_model=RunHistoryOptionsResponse)
def get_history_run_options(
    limit: int = Query(default=200, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RunHistoryOptionsResponse:
    rows = (
        db.query(GameRun)
        .filter(
            GameRun.user_id == current_user["id"],
            GameRun.status == "finished",
        )
        .order_by(GameRun.id.desc())
        .limit(limit)
        .all()
    )
    return RunHistoryOptionsResponse(runs=[_to_run_response(row) for row in rows])


@router.get("/runs/{run_id}/context", response_model=RunResponse)
def get_run_context(
    run_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RunResponse:
    run = _get_owned_readable_run_or_404(db, run_id=run_id, user_id=current_user["id"])
    return _to_run_response(run)


@router.get("/runs/{run_id}/history/summary", response_model=RunHistorySummaryResponse)
def get_run_history_summary(
    run_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RunHistorySummaryResponse:
    user_id = int(current_user["id"])
    run = _get_owned_readable_run_or_404(db, run_id=run_id, user_id=user_id)
    if (run.status or "").strip() != "finished":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅已结束对局支持历史总结查看")
    cache_key = f"{_game_overview_cache_key(name='history_summary', run_id=run.id)}:user:{user_id}"
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        normalized_cached_payload = dict(cached_payload)
        normalized_cached_payload["run"] = _to_run_response(run).model_dump(mode="json")
        return RunHistorySummaryResponse.model_validate(normalized_cached_payload)

    procurement_spent_total = _calc_run_procurement_spent(db, run.id)
    logistics_spent_total = _calc_run_logistics_spent(db, run.id)
    warehouse_spent_total = _calc_run_warehouse_spent(db, run.id)
    total_expense = round(float(procurement_spent_total + logistics_spent_total + warehouse_spent_total), 2)
    total_cash = _calc_run_total_cash(db, run)
    current_balance = _calc_run_remaining_cash(
        db,
        run,
        procurement_spent_total=procurement_spent_total,
        logistics_spent_total=logistics_spent_total,
        warehouse_spent_total=warehouse_spent_total,
    )
    income_withdrawal_total = _calc_run_withdrawal_income_total(db, run.id)

    procurement_order_count = db.query(ProcurementOrder).filter(ProcurementOrder.run_id == run.id).count()
    logistics_shipment_count = db.query(LogisticsShipment).filter(LogisticsShipment.run_id == run.id).count()
    warehouse_completed_inbound_count = (
        db.query(WarehouseInboundOrder)
        .filter(
            WarehouseInboundOrder.run_id == run.id,
            WarehouseInboundOrder.status == "completed",
        )
        .count()
    )
    inventory_total_quantity = (
        db.query(
            func.coalesce(
                func.sum(
                    func.coalesce(InventoryLot.quantity_available, 0)
                    + func.coalesce(InventoryLot.reserved_qty, 0)
                ),
                0,
            )
        )
        .filter(InventoryLot.run_id == run.id)
        .scalar()
        or 0
    )
    inventory_total_sku = db.query(InventoryLot.product_id).filter(InventoryLot.run_id == run.id).distinct().count()

    shopee_base = db.query(ShopeeOrder).filter(
        ShopeeOrder.run_id == run.id,
        ShopeeOrder.user_id == run.user_id,
    )
    shopee_order_total_count = shopee_base.count()
    shopee_order_toship_count = shopee_base.filter(ShopeeOrder.type_bucket == "toship").count()
    shopee_order_shipping_count = shopee_base.filter(ShopeeOrder.type_bucket == "shipping").count()
    shopee_order_completed_count = shopee_base.filter(ShopeeOrder.type_bucket == "completed").count()
    shopee_order_cancelled_count = shopee_base.filter(ShopeeOrder.type_bucket == "cancelled").count()
    shopee_order_sold_inventory_quantity = (
        db.query(func.coalesce(func.sum(ShopeeOrderItem.quantity), 0))
        .join(ShopeeOrder, ShopeeOrder.id == ShopeeOrderItem.order_id)
        .filter(
            ShopeeOrder.run_id == run.id,
            ShopeeOrder.user_id == run.user_id,
            ShopeeOrder.type_bucket.in_(("shipping", "completed")),
        )
        .scalar()
        or 0
    )
    shopee_order_generation_log_count = (
        db.query(ShopeeOrderGenerationLog)
        .filter(
            ShopeeOrderGenerationLog.run_id == run.id,
            ShopeeOrderGenerationLog.user_id == run.user_id,
        )
        .count()
    )

    response = RunHistorySummaryResponse(
        run=_to_run_response(run),
        initial_cash=round(float(run.initial_cash), 2),
        total_cash=total_cash,
        income_withdrawal_total=income_withdrawal_total,
        total_expense=total_expense,
        current_balance=current_balance,
        procurement_order_count=procurement_order_count,
        logistics_shipment_count=logistics_shipment_count,
        warehouse_completed_inbound_count=warehouse_completed_inbound_count,
        inventory_total_quantity=int(inventory_total_quantity or 0),
        inventory_total_sku=int(inventory_total_sku or 0),
        shopee_order_total_count=shopee_order_total_count,
        shopee_order_toship_count=shopee_order_toship_count,
        shopee_order_shipping_count=shopee_order_shipping_count,
        shopee_order_completed_count=shopee_order_completed_count,
        shopee_order_cancelled_count=shopee_order_cancelled_count,
        shopee_order_sold_inventory_quantity=int(shopee_order_sold_inventory_quantity or 0),
        shopee_order_generation_log_count=shopee_order_generation_log_count,
    )
    cache_set_json(cache_key, response.model_dump(mode="json"), REDIS_CACHE_TTL_HISTORY_SUMMARY_SEC)
    return response


@router.post("/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
def create_run(
    payload: CreateRunRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RunResponse:
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user")
    if user.role != "player":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only player can create runs")
    _auto_finish_expired_running_runs_for_user(db, user_id=user.id)

    existing_running = (
        db.query(GameRun)
        .filter(
            GameRun.user_id == user.id,
            GameRun.status == "running",
        )
        .first()
    )
    if existing_running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A running game already exists",
        )

    normalized_duration_days = int(payload.duration_days)
    run = GameRun(
        user_id=user.id,
        initial_cash=payload.initial_cash,
        market=payload.market.strip().upper(),
        duration_days=normalized_duration_days,
        base_real_duration_days=normalized_duration_days,
        base_game_days=DEFAULT_TOTAL_GAME_DAYS,
        total_game_days=DEFAULT_TOTAL_GAME_DAYS,
        day_index=1,
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return _to_run_response(run)


@router.post("/runs/reset-current", response_model=RunResponse)
def reset_current_run(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RunResponse:
    user = db.query(User).filter(User.id == current_user["id"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user")
    if user.role != "player":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only player can reset runs")

    run = (
        db.query(GameRun)
        .filter(
            GameRun.user_id == user.id,
            GameRun.status == "running",
        )
        .order_by(GameRun.id.desc())
        .first()
    )
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No running game found")

    run.status = "abandoned"
    db.commit()
    db.refresh(run)
    return _to_run_response(run)


@router.get("/runs/{run_id}/procurement/cart-summary", response_model=ProcurementSummaryResponse)
def get_procurement_cart_summary(
    run_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProcurementSummaryResponse:
    run = _get_owned_readable_run_or_404(db, run_id=run_id, user_id=current_user["id"])
    spent_total = _calc_run_procurement_spent(db, run.id)
    logistics_spent_total = _calc_run_logistics_spent(db, run.id)
    warehouse_spent_total = _calc_run_warehouse_spent(db, run.id)
    income_withdrawal_total = _calc_run_withdrawal_income_total(db, run.id)
    total_expense = float(spent_total + logistics_spent_total + warehouse_spent_total)
    total_cash = _calc_run_total_cash(db, run)
    remaining_cash = _calc_run_remaining_cash(
        db,
        run,
        procurement_spent_total=spent_total,
        logistics_spent_total=logistics_spent_total,
        warehouse_spent_total=warehouse_spent_total,
    )
    return ProcurementSummaryResponse(
        run_id=run.id,
        initial_cash=float(run.initial_cash),
        income_withdrawal_total=income_withdrawal_total,
        total_expense=round(total_expense, 2),
        current_balance=remaining_cash,
        total_cash=total_cash,
        spent_total=spent_total,
        logistics_spent_total=logistics_spent_total,
        warehouse_spent_total=warehouse_spent_total,
        remaining_cash=remaining_cash,
    )


@router.get("/runs/{run_id}/finance/details", response_model=GameFinanceDetailsResponse)
def list_run_finance_details(
    run_id: int,
    tab: str = Query(default="income"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GameFinanceDetailsResponse:
    run = _get_owned_readable_run_or_404(db, run_id=run_id, user_id=current_user["id"])
    normalized_tab = (tab or "income").strip().lower()
    if normalized_tab not in {"income", "expense"}:
        normalized_tab = "income"

    if normalized_tab == "income":
        all_rows = _list_run_income_detail_rows(db, run.id)
    else:
        all_rows = _list_run_expense_detail_rows(db, run.id)

    total = len(all_rows)
    start = (page - 1) * page_size
    end = start + page_size
    rows = all_rows[start:end]
    return GameFinanceDetailsResponse(
        tab=normalized_tab,
        page=page,
        page_size=page_size,
        total=total,
        rows=rows,
    )


@router.get("/runs/{run_id}/procurement/orders", response_model=ProcurementOrdersResponse)
def list_procurement_orders(
    run_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProcurementOrdersResponse:
    run = _get_owned_readable_run_or_404(db, run_id=run_id, user_id=current_user["id"])
    rows = (
        db.query(ProcurementOrder)
        .options(selectinload(ProcurementOrder.items))
        .filter(ProcurementOrder.run_id == run.id)
        .order_by(ProcurementOrder.id.desc())
        .all()
    )
    return ProcurementOrdersResponse(
        orders=[
            ProcurementOrderResponse(
                id=row.id,
                total_amount=row.total_amount,
                created_at=row.created_at,
                items=[
                    ProcurementOrderItemResponse(
                        product_id=item.product_id,
                        product_name=item.product_name_snapshot,
                        unit_price=item.unit_price,
                        quantity=item.quantity,
                        line_total=item.line_total,
                    )
                    for item in row.items
                ],
            )
            for row in rows
        ]
    )


@router.post("/runs/{run_id}/procurement/orders", response_model=ProcurementCreateOrderResponse, status_code=status.HTTP_201_CREATED)
def create_procurement_order(
    run_id: int,
    payload: ProcurementCreateOrderRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProcurementCreateOrderResponse:
    run = _get_owned_writable_run_or_400(db, run_id=run_id, user_id=current_user["id"])

    quantity_map: dict[int, int] = {}
    for item in payload.items:
        quantity_map[item.product_id] = quantity_map.get(item.product_id, 0) + item.quantity

    products = (
        db.query(MarketProduct)
        .filter(
            MarketProduct.id.in_(list(quantity_map.keys())),
            MarketProduct.market == run.market,
        )
        .all()
    )
    product_map = {product.id: product for product in products}
    missing = [pid for pid in quantity_map if pid not in product_map]
    if missing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Some products are invalid for this market")

    line_items: list[tuple[MarketProduct, int, int]] = []
    order_total = 0
    for product_id, quantity in quantity_map.items():
        product = product_map[product_id]
        line_total = product.supplier_price * quantity
        order_total += line_total
        line_items.append((product, quantity, line_total))

    spent_total = _calc_run_procurement_spent(db, run.id)
    logistics_spent_total = _calc_run_logistics_spent(db, run.id)
    warehouse_spent_total = _calc_run_warehouse_spent(db, run.id)
    remaining_cash = _calc_run_remaining_cash(
        db,
        run,
        procurement_spent_total=spent_total,
        logistics_spent_total=logistics_spent_total,
        warehouse_spent_total=warehouse_spent_total,
    )
    if order_total > remaining_cash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient cash balance, remaining {remaining_cash}",
        )

    order = ProcurementOrder(
        run_id=run.id,
        user_id=current_user["id"],
        total_amount=order_total,
    )
    db.add(order)
    db.flush()

    for product, quantity, line_total in line_items:
        db.add(
            ProcurementOrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name_snapshot=product.product_name,
                unit_price=product.supplier_price,
                quantity=quantity,
                line_total=line_total,
            )
        )

    db.commit()
    db.refresh(order)

    updated_spent = spent_total + order_total
    return ProcurementCreateOrderResponse(
        order_id=order.id,
        total_amount=order_total,
        spent_total=updated_spent,
        remaining_cash=_calc_run_remaining_cash(
            db,
            run,
            procurement_spent_total=updated_spent,
            logistics_spent_total=logistics_spent_total,
            warehouse_spent_total=warehouse_spent_total,
        ),
    )


@router.get("/runs/{run_id}/logistics/shipments", response_model=LogisticsShipmentsResponse)
def list_logistics_shipments(
    run_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LogisticsShipmentsResponse:
    run = _get_owned_readable_run_or_404(db, run_id=run_id, user_id=current_user["id"])
    rows = (
        db.query(LogisticsShipment)
        .options(selectinload(LogisticsShipment.orders))
        .filter(LogisticsShipment.run_id == run.id)
        .order_by(LogisticsShipment.id.desc())
        .all()
    )
    return LogisticsShipmentsResponse(
        shipments=[
            LogisticsShipmentResponse(
                id=row.id,
                order_ids=[item.procurement_order_id for item in row.orders],
                forwarder_key=row.forwarder_key,
                forwarder_label=row.forwarder_label,
                customs_key=row.customs_key,
                customs_label=row.customs_label,
                cargo_value=row.cargo_value,
                logistics_fee=row.logistics_fee,
                customs_fee=row.customs_fee,
                total_fee=row.total_fee,
                transport_days=row.transport_days,
                customs_days=row.customs_days,
                created_at=row.created_at,
            )
            for row in rows
        ]
    )


@router.post("/runs/{run_id}/logistics/shipments", response_model=LogisticsCreateShipmentResponse, status_code=status.HTTP_201_CREATED)
def create_logistics_shipment(
    run_id: int,
    payload: LogisticsCreateShipmentRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LogisticsCreateShipmentResponse:
    run = _get_owned_writable_run_or_400(db, run_id=run_id, user_id=current_user["id"])

    order_ids = list(dict.fromkeys(payload.order_ids))
    orders = (
        db.query(ProcurementOrder)
        .options(selectinload(ProcurementOrder.items))
        .filter(
            ProcurementOrder.run_id == run.id,
            ProcurementOrder.id.in_(order_ids),
        )
        .all()
    )
    if len(orders) != len(order_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Some procurement orders are invalid")

    existing_links = (
        db.query(LogisticsShipmentOrder)
        .join(LogisticsShipment, LogisticsShipment.id == LogisticsShipmentOrder.shipment_id)
        .filter(
            LogisticsShipment.run_id == run.id,
            LogisticsShipmentOrder.procurement_order_id.in_(order_ids),
        )
        .all()
    )
    if existing_links:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Some procurement orders are already shipped")

    forwarder_map = {
        "economy": {"label": "经济线（马来）", "fee_rate": 0.035, "fixed_fee": 1800, "eta_days": 18},
        "standard": {"label": "标准线（马来）", "fee_rate": 0.052, "fixed_fee": 2600, "eta_days": 12},
        "express": {"label": "快速线（马来）", "fee_rate": 0.075, "fixed_fee": 3600, "eta_days": 8},
    }
    customs_map = {
        "normal": {"label": "标准清关", "add_fee": 0, "days": 4},
        "priority": {"label": "加急清关", "add_fee": 1200, "days": 2},
    }
    if payload.forwarder_key not in forwarder_map:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid forwarder key")
    if payload.customs_key not in customs_map:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid customs key")

    selected_forwarder = forwarder_map[payload.forwarder_key]
    selected_customs = customs_map[payload.customs_key]
    cargo_value = int(sum(order.total_amount for order in orders))
    logistics_fee = int(round(cargo_value * selected_forwarder["fee_rate"]) + selected_forwarder["fixed_fee"])
    customs_fee = int(round(cargo_value * 0.02) + 600 + selected_customs["add_fee"])
    total_fee = logistics_fee + customs_fee

    procurement_spent_total = _calc_run_procurement_spent(db, run.id)
    logistics_spent_total = _calc_run_logistics_spent(db, run.id)
    warehouse_spent_total = _calc_run_warehouse_spent(db, run.id)
    remaining_cash = _calc_run_remaining_cash(
        db,
        run,
        procurement_spent_total=procurement_spent_total,
        logistics_spent_total=logistics_spent_total,
        warehouse_spent_total=warehouse_spent_total,
    )
    if total_fee > remaining_cash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient cash balance, remaining {remaining_cash}",
        )

    shipment = LogisticsShipment(
        run_id=run.id,
        user_id=current_user["id"],
        market=run.market,
        forwarder_key=payload.forwarder_key,
        forwarder_label=selected_forwarder["label"],
        customs_key=payload.customs_key,
        customs_label=selected_customs["label"],
        cargo_value=cargo_value,
        logistics_fee=logistics_fee,
        customs_fee=customs_fee,
        total_fee=total_fee,
        transport_days=selected_forwarder["eta_days"],
        customs_days=selected_customs["days"],
    )
    db.add(shipment)
    db.flush()

    for order in orders:
        total_quantity = sum(item.quantity for item in order.items)
        db.add(
            LogisticsShipmentOrder(
                shipment_id=shipment.id,
                procurement_order_id=order.id,
                order_total_amount=order.total_amount,
                order_total_quantity=total_quantity,
            )
        )

    db.commit()

    updated_logistics_spent = logistics_spent_total + total_fee
    return LogisticsCreateShipmentResponse(
        shipment_id=shipment.id,
        total_fee=total_fee,
        spent_total=procurement_spent_total,
        logistics_spent_total=updated_logistics_spent,
        warehouse_spent_total=warehouse_spent_total,
        remaining_cash=_calc_run_remaining_cash(
            db,
            run,
            procurement_spent_total=procurement_spent_total,
            logistics_spent_total=updated_logistics_spent,
            warehouse_spent_total=warehouse_spent_total,
        ),
    )


@router.post("/runs/{run_id}/logistics/shipments/{shipment_id}/debug/accelerate-clearance", response_model=LogisticsDebugAccelerateResponse)
def debug_accelerate_logistics_clearance(
    run_id: int,
    shipment_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LogisticsDebugAccelerateResponse:
    run = _get_owned_writable_run_or_400(db, run_id=run_id, user_id=current_user["id"])
    shipment = (
        db.query(LogisticsShipment)
        .filter(
            LogisticsShipment.id == shipment_id,
            LogisticsShipment.run_id == run.id,
        )
        .first()
    )
    if not shipment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found")

    created_ref = shipment.created_at
    now = datetime.now(tz=created_ref.tzinfo) if created_ref.tzinfo is not None else datetime.utcnow()
    transport_seconds = max(1, int(shipment.transport_days * REAL_SECONDS_PER_GAME_DAY))
    customs_seconds = max(1, int(shipment.customs_days * REAL_SECONDS_PER_GAME_DAY))
    total_seconds = BOOKED_SECONDS + transport_seconds + customs_seconds
    shipment.created_at = now - timedelta(seconds=total_seconds + 1)

    db.commit()
    db.refresh(shipment)
    status_now = _calc_shipment_status(shipment, datetime.utcnow())
    return LogisticsDebugAccelerateResponse(
        shipment_id=shipment.id,
        status=status_now,
        created_at=shipment.created_at,
    )


@router.get("/runs/{run_id}/warehouse/options", response_model=WarehouseOptionsResponse)
def get_warehouse_options(
    run_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WarehouseOptionsResponse:
    _get_owned_readable_run_or_404(db, run_id=run_id, user_id=current_user["id"])
    mode_items = []
    for key, val in _warehouse_mode_options().items():
        mode_items.append(
            {
                "key": key,
                "label": val["label"],
                "one_time_base": val["one_time_base"],
                "inbound_rate": val["inbound_rate"],
                "rent_base": val["rent_base"],
                "delivery_eta_score": val["delivery_eta_score"],
                "fulfillment_accuracy": val["fulfillment_accuracy"],
                "warehouse_cost_per_order": val["warehouse_cost_per_order"],
            }
        )
    location_items = []
    for key, val in _warehouse_location_options().items():
        location_items.append(
            {
                "key": key,
                "label": val["label"],
                "rent_delta": val["rent_delta"],
                "eta_delta": val["eta_delta"],
            }
        )
    return WarehouseOptionsResponse(warehouse_modes=mode_items, warehouse_locations=location_items)


@router.get("/runs/{run_id}/warehouse/landmarks", response_model=WarehouseLandmarksResponse)
def get_warehouse_landmarks(
    run_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WarehouseLandmarksResponse:
    run = _get_owned_readable_run_or_404(db, run_id=run_id, user_id=current_user["id"])
    points = (
        db.query(WarehouseLandmark)
        .filter(
            WarehouseLandmark.market == run.market,
            WarehouseLandmark.is_active.is_(True),
        )
        .order_by(
            WarehouseLandmark.warehouse_location.asc(),
            WarehouseLandmark.warehouse_mode.asc(),
            WarehouseLandmark.sort_order.asc(),
            WarehouseLandmark.id.asc(),
        )
        .all()
    )
    return WarehouseLandmarksResponse(
        market=run.market,
        points=[
            WarehouseLandmarkPointResponse(
                point_code=row.point_code,
                point_name=row.point_name,
                warehouse_mode=row.warehouse_mode,
                warehouse_location=row.warehouse_location,
                lng=float(row.lng),
                lat=float(row.lat),
                sort_order=row.sort_order,
            )
            for row in points
        ],
    )


@router.get("/runs/{run_id}/warehouse/inbound-candidates", response_model=WarehouseInboundCandidatesResponse)
def get_warehouse_inbound_candidates(
    run_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WarehouseInboundCandidatesResponse:
    run = _get_owned_readable_run_or_404(db, run_id=run_id, user_id=current_user["id"])
    inbounded_shipment_ids = {
        row[0]
        for row in db.query(WarehouseInboundOrder.shipment_id).filter(WarehouseInboundOrder.run_id == run.id).all()
    }

    shipments = (
        db.query(LogisticsShipment)
        .options(selectinload(LogisticsShipment.orders))
        .filter(LogisticsShipment.run_id == run.id)
        .order_by(LogisticsShipment.id.desc())
        .all()
    )
    now = datetime.utcnow()
    candidates: list[WarehouseInboundCandidateItem] = []
    for shipment in shipments:
        if shipment.id in inbounded_shipment_ids:
            continue
        status = _calc_shipment_status(shipment, now)
        if status != "customs_cleared":
            continue
        total_qty = int(sum(item.order_total_quantity for item in shipment.orders))
        candidates.append(
            WarehouseInboundCandidateItem(
                shipment_id=shipment.id,
                cargo_value=shipment.cargo_value,
                total_quantity=total_qty,
                created_at=shipment.created_at,
                forwarder_label=shipment.forwarder_label,
                customs_label=shipment.customs_label,
                status=status,
            )
        )
    return WarehouseInboundCandidatesResponse(candidates=candidates)


@router.post("/runs/{run_id}/warehouse/strategy", response_model=WarehouseCreateStrategyResponse, status_code=status.HTTP_201_CREATED)
def create_warehouse_strategy(
    run_id: int,
    payload: WarehouseStrategyCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WarehouseCreateStrategyResponse:
    run = _get_owned_writable_run_or_400(db, run_id=run_id, user_id=current_user["id"])
    mode_options = _warehouse_mode_options()
    location_options = _warehouse_location_options()
    if payload.warehouse_mode not in mode_options:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid warehouse_mode")
    if payload.warehouse_location not in location_options:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid warehouse_location")

    candidates_resp = get_warehouse_inbound_candidates(run.id, current_user=current_user, db=db)
    if not candidates_resp.candidates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No customs-cleared shipments available for inbound")

    cargo_total = int(sum(item.cargo_value for item in candidates_resp.candidates))
    selected_mode = mode_options[payload.warehouse_mode]
    selected_location = location_options[payload.warehouse_location]

    is_first_self_built = (
        payload.warehouse_mode == "self_built"
        and db.query(WarehouseStrategy)
        .filter(WarehouseStrategy.run_id == run.id, WarehouseStrategy.warehouse_mode == "self_built")
        .count()
        == 0
    )
    one_time_cost = selected_mode["one_time_base"] if is_first_self_built else 0
    inbound_cost = int(round(cargo_total * selected_mode["inbound_rate"]))
    rent_cost = int(max(0, selected_mode["rent_base"] + selected_location["rent_delta"]))
    total_cost = one_time_cost + inbound_cost + rent_cost

    procurement_spent_total = _calc_run_procurement_spent(db, run.id)
    logistics_spent_total = _calc_run_logistics_spent(db, run.id)
    warehouse_spent_total = _calc_run_warehouse_spent(db, run.id)
    remaining_cash = _calc_run_remaining_cash(
        db,
        run,
        procurement_spent_total=procurement_spent_total,
        logistics_spent_total=logistics_spent_total,
        warehouse_spent_total=warehouse_spent_total,
    )
    if total_cost > remaining_cash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient cash balance, remaining {remaining_cash}",
        )

    strategy = WarehouseStrategy(
        run_id=run.id,
        user_id=current_user["id"],
        market=run.market,
        warehouse_mode=payload.warehouse_mode,
        warehouse_location=payload.warehouse_location,
        one_time_cost=one_time_cost,
        inbound_cost=inbound_cost,
        rent_cost=rent_cost,
        total_cost=total_cost,
        delivery_eta_score=max(1, min(100, selected_mode["delivery_eta_score"] + selected_location["eta_delta"])),
        fulfillment_accuracy=selected_mode["fulfillment_accuracy"],
        warehouse_cost_per_order=selected_mode["warehouse_cost_per_order"],
        status="active",
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)

    return WarehouseCreateStrategyResponse(
        strategy=_to_warehouse_strategy_response(strategy),
        remaining_cash=_calc_run_remaining_cash(
            db,
            run,
            procurement_spent_total=procurement_spent_total,
            logistics_spent_total=logistics_spent_total,
            warehouse_spent_total=warehouse_spent_total + total_cost,
        ),
    )


@router.post("/runs/{run_id}/warehouse/inbound", response_model=WarehouseInboundResponse, status_code=status.HTTP_201_CREATED)
def warehouse_inbound(
    run_id: int,
    payload: WarehouseInboundRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WarehouseInboundResponse:
    run = _get_owned_writable_run_or_400(db, run_id=run_id, user_id=current_user["id"])
    strategy = (
        db.query(WarehouseStrategy)
        .filter(WarehouseStrategy.run_id == run.id, WarehouseStrategy.status == "active")
        .order_by(WarehouseStrategy.id.desc())
        .first()
    )
    if not strategy:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please create warehouse strategy first")

    candidates_resp = get_warehouse_inbound_candidates(run.id, current_user=current_user, db=db)
    candidate_ids = [item.shipment_id for item in candidates_resp.candidates]
    if not candidate_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No customs-cleared shipments available for inbound")

    if payload.shipment_ids:
        requested = set(payload.shipment_ids)
        if not requested.issubset(set(candidate_ids)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Some shipment_ids are invalid for inbound")
        target_ids = [sid for sid in candidate_ids if sid in requested]
    else:
        # V1：一次性入仓全部可入仓物流单
        target_ids = candidate_ids

    shipments = (
        db.query(LogisticsShipment)
        .options(selectinload(LogisticsShipment.orders))
        .filter(LogisticsShipment.id.in_(target_ids), LogisticsShipment.run_id == run.id)
        .all()
    )
    shipment_map = {row.id: row for row in shipments}
    now = datetime.utcnow()
    created_inbound_count = 0
    created_lot_count = 0
    product_inbound_qty_map: dict[int, int] = {}

    for shipment_id in target_ids:
        shipment = shipment_map.get(shipment_id)
        if not shipment:
            continue
        total_quantity = int(sum(item.order_total_quantity for item in shipment.orders))
        inbound_order = WarehouseInboundOrder(
            run_id=run.id,
            strategy_id=strategy.id,
            shipment_id=shipment.id,
            total_quantity=total_quantity,
            total_value=shipment.cargo_value,
            status="completed",
            completed_at=now,
        )
        db.add(inbound_order)
        db.flush()
        created_inbound_count += 1

        order_ids = [item.procurement_order_id for item in shipment.orders]
        if not order_ids:
            continue
        order_items = (
            db.query(ProcurementOrderItem)
            .filter(ProcurementOrderItem.order_id.in_(order_ids))
            .all()
        )
        for row in order_items:
            lot = InventoryLot(
                run_id=run.id,
                product_id=row.product_id,
                inbound_order_id=inbound_order.id,
                quantity_available=row.quantity,
                quantity_locked=0,
                unit_cost=row.unit_price,
            )
            db.add(lot)
            db.flush()
            qty_val = max(0, int(row.quantity or 0))
            product_inbound_qty_map[int(row.product_id)] = product_inbound_qty_map.get(int(row.product_id), 0) + qty_val
            _append_inventory_stock_movement(
                db,
                run_id=run.id,
                user_id=current_user["id"],
                movement_type="purchase_in",
                qty_delta_on_hand=qty_val,
                qty_delta_reserved=0,
                qty_delta_backorder=0,
                product_id=int(row.product_id),
                inventory_lot_id=int(lot.id),
                biz_ref=f"inbound:{inbound_order.id}",
                remark="Step04入库创建库存批次",
            )
            created_lot_count += 1

    _apply_inbound_to_shopee_inventory_and_backorders(
        db,
        run_id=run.id,
        user_id=current_user["id"],
        product_inbound_qty_map=product_inbound_qty_map,
    )

    db.commit()

    procurement_spent_total = _calc_run_procurement_spent(db, run.id)
    logistics_spent_total = _calc_run_logistics_spent(db, run.id)
    warehouse_spent_total = _calc_run_warehouse_spent(db, run.id)
    remaining_cash = _calc_run_remaining_cash(
        db,
        run,
        procurement_spent_total=procurement_spent_total,
        logistics_spent_total=logistics_spent_total,
        warehouse_spent_total=warehouse_spent_total,
    )

    return WarehouseInboundResponse(
        inbound_count=created_inbound_count,
        shipment_ids=target_ids,
        inventory_lot_count=created_lot_count,
        remaining_cash=remaining_cash,
    )


@router.get("/runs/{run_id}/warehouse/summary", response_model=WarehouseSummaryResponse)
def get_warehouse_summary(
    run_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WarehouseSummaryResponse:
    run = _get_owned_readable_run_or_404(db, run_id=run_id, user_id=current_user["id"])
    cache_key = _game_overview_cache_key(name="warehouse_summary", run_id=run.id)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return WarehouseSummaryResponse.model_validate(cached_payload)
    strategy = (
        db.query(WarehouseStrategy)
        .filter(WarehouseStrategy.run_id == run.id, WarehouseStrategy.status == "active")
        .order_by(WarehouseStrategy.id.desc())
        .first()
    )
    if strategy is None and (run.status or "").strip() == "finished":
        strategy = (
            db.query(WarehouseStrategy)
            .filter(WarehouseStrategy.run_id == run.id)
            .order_by(WarehouseStrategy.id.desc())
            .first()
        )

    completed_count = (
        db.query(func.count(WarehouseInboundOrder.id))
        .filter(WarehouseInboundOrder.run_id == run.id, WarehouseInboundOrder.status == "completed")
        .scalar()
        or 0
    )
    completed_totals = (
        db.query(
            func.coalesce(func.sum(WarehouseInboundOrder.total_quantity), 0),
            func.coalesce(func.sum(WarehouseInboundOrder.total_value), 0),
        )
        .filter(WarehouseInboundOrder.run_id == run.id, WarehouseInboundOrder.status == "completed")
        .first()
    )
    pending_count = (
        db.query(func.count(WarehouseInboundOrder.id))
        .filter(WarehouseInboundOrder.run_id == run.id, WarehouseInboundOrder.status != "completed")
        .scalar()
        or 0
    )
    inventory_total_quantity = (
        db.query(func.coalesce(func.sum(InventoryLot.quantity_available), 0))
        .filter(InventoryLot.run_id == run.id)
        .scalar()
        or 0
    )
    inventory_total_sku = (
        db.query(func.count(func.distinct(InventoryLot.product_id)))
        .filter(InventoryLot.run_id == run.id)
        .scalar()
        or 0
    )

    response = WarehouseSummaryResponse(
        strategy=_to_warehouse_strategy_response(strategy) if strategy else None,
        pending_inbound_count=int(pending_count),
        completed_inbound_count=int(completed_count),
        completed_inbound_total_quantity=int(completed_totals[0] or 0),
        completed_inbound_total_value=int(completed_totals[1] or 0),
        inventory_total_quantity=int(inventory_total_quantity),
        inventory_total_sku=int(inventory_total_sku),
    )
    cache_set_json(cache_key, response.model_dump(mode="json"), REDIS_CACHE_TTL_OVERVIEW_SEC)
    return response


@router.get("/runs/{run_id}/warehouse/stock-overview", response_model=WarehouseStockOverviewResponse)
def get_warehouse_stock_overview(
    run_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WarehouseStockOverviewResponse:
    run = _get_owned_readable_run_or_404(db, run_id=run_id, user_id=current_user["id"])
    cache_key = _game_overview_cache_key(name="warehouse_stock_overview", run_id=run.id)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return WarehouseStockOverviewResponse.model_validate(cached_payload)

    totals = (
        db.query(
            func.coalesce(func.sum(InventoryLot.quantity_available), 0),
            func.coalesce(func.sum(InventoryLot.reserved_qty), 0),
            func.coalesce(func.sum(InventoryLot.backorder_qty), 0),
            func.coalesce(func.sum(InventoryLot.quantity_locked), 0),
            func.coalesce(func.count(func.distinct(InventoryLot.product_id)), 0),
        )
        .filter(InventoryLot.run_id == run.id)
        .first()
    )
    available_stock_qty = int(totals[0] or 0)
    reserved_stock_qty = int(totals[1] or 0)
    backorder_qty = int(totals[2] or 0)
    locked_stock_qty = int(totals[3] or 0)
    inventory_sku_count = int(totals[4] or 0)
    total_stock_qty = max(0, available_stock_qty + reserved_stock_qty + locked_stock_qty)

    response = WarehouseStockOverviewResponse(
        inventory_sku_count=inventory_sku_count,
        total_stock_qty=total_stock_qty,
        available_stock_qty=available_stock_qty,
        reserved_stock_qty=reserved_stock_qty,
        backorder_qty=backorder_qty,
        locked_stock_qty=locked_stock_qty,
    )
    cache_set_json(cache_key, response.model_dump(mode="json"), REDIS_CACHE_TTL_OVERVIEW_SEC)
    return response


@router.get("/runs/{run_id}/warehouse/stock-movements", response_model=WarehouseStockMovementsResponse)
def get_warehouse_stock_movements(
    run_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    movement_type: str | None = Query(None),
    keyword: str | None = Query(None, max_length=64),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WarehouseStockMovementsResponse:
    run = _get_owned_readable_run_or_404(db, run_id=run_id, user_id=current_user["id"])

    q = db.query(InventoryStockMovement).filter(
        InventoryStockMovement.run_id == run.id,
        InventoryStockMovement.user_id == current_user["id"],
    )

    movement_type_val = (movement_type or "").strip()
    if movement_type_val and movement_type_val != "all":
        q = q.filter(InventoryStockMovement.movement_type == movement_type_val)

    keyword_val = (keyword or "").strip()
    if keyword_val:
        q = q.filter(
            or_(
                InventoryStockMovement.biz_ref.like(f"%{keyword_val}%"),
                InventoryStockMovement.remark.like(f"%{keyword_val}%"),
            )
        )

    total = int(q.count())
    rows = (
        q.order_by(InventoryStockMovement.created_at.desc(), InventoryStockMovement.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return WarehouseStockMovementsResponse(
        page=page,
        page_size=page_size,
        total=total,
        rows=[
            WarehouseStockMovementItemResponse(
                id=int(row.id),
                movement_type=str(row.movement_type),
                movement_type_label=STOCK_MOVEMENT_LABELS.get(str(row.movement_type), str(row.movement_type)),
                qty_delta_on_hand=int(row.qty_delta_on_hand or 0),
                qty_delta_reserved=int(row.qty_delta_reserved or 0),
                qty_delta_backorder=int(row.qty_delta_backorder or 0),
                product_id=int(row.product_id) if row.product_id is not None else None,
                listing_id=int(row.listing_id) if row.listing_id is not None else None,
                variant_id=int(row.variant_id) if row.variant_id is not None else None,
                biz_order_id=int(row.biz_order_id) if row.biz_order_id is not None else None,
                biz_ref=row.biz_ref,
                remark=row.remark,
                created_at=row.created_at,
            )
            for row in rows
        ],
    )


@router.get("/runs/{run_id}/warehouse/backorder-risk", response_model=WarehouseBackorderRiskOverviewResponse)
def get_warehouse_backorder_risk_overview(
    run_id: int,
    top_n: int = Query(5, ge=1, le=20),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WarehouseBackorderRiskOverviewResponse:
    run = _get_owned_readable_run_or_404(db, run_id=run_id, user_id=current_user["id"])
    cache_key = _game_overview_cache_key(name="warehouse_backorder_risk", run_id=run.id, top_n=top_n)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return WarehouseBackorderRiskOverviewResponse.model_validate(cached_payload)

    current_tick = (
        db.query(func.max(ShopeeOrderGenerationLog.tick_time))
        .filter(
            ShopeeOrderGenerationLog.run_id == run.id,
            ShopeeOrderGenerationLog.user_id == current_user["id"],
        )
        .scalar()
    ) or datetime.utcnow()

    orders = (
        db.query(ShopeeOrder)
        .filter(
            ShopeeOrder.run_id == run.id,
            ShopeeOrder.user_id == current_user["id"],
            ShopeeOrder.type_bucket == "toship",
            ShopeeOrder.stock_fulfillment_status == "backorder",
            ShopeeOrder.backorder_qty > 0,
        )
        .all()
    )
    if not orders:
        response = WarehouseBackorderRiskOverviewResponse(
            current_tick=current_tick,
            affected_order_count=0,
            backorder_qty_total=0,
            overdue_order_count=0,
            urgent_24h_order_count=0,
            estimated_cancel_amount_total=0.0,
            top_items=[],
        )
        cache_set_json(cache_key, response.model_dump(mode="json"), REDIS_CACHE_TTL_OVERVIEW_SEC)
        return response

    listing_ids = {int(o.listing_id) for o in orders if o.listing_id is not None}
    variant_ids = {int(o.variant_id) for o in orders if o.variant_id is not None}
    listing_map: dict[int, ShopeeListing] = {}
    variant_map: dict[int, ShopeeListingVariant] = {}
    if listing_ids:
        listing_rows = db.query(ShopeeListing).filter(ShopeeListing.id.in_(list(listing_ids))).all()
        listing_map = {int(row.id): row for row in listing_rows}
    if variant_ids:
        variant_rows = db.query(ShopeeListingVariant).filter(ShopeeListingVariant.id.in_(list(variant_ids))).all()
        variant_map = {int(row.id): row for row in variant_rows}

    affected_order_count = len(orders)
    backorder_qty_total = 0
    overdue_order_count = 0
    urgent_24h_order_count = 0
    estimated_cancel_amount_total = 0.0
    grouped: dict[tuple[int | None, int | None], dict[str, Any]] = {}

    for order in orders:
        order_backorder_qty = max(0, int(order.backorder_qty or 0))
        backorder_qty_total += order_backorder_qty

        deadline = order.must_restock_before_at or order.ship_by_at
        overdue_hours = 0
        if deadline and current_tick > deadline:
            overdue_hours = max(0, int((current_tick - deadline).total_seconds() // 3600))
            if overdue_hours > 0:
                overdue_order_count += 1
        elif deadline:
            remaining_hours = int((deadline - current_tick).total_seconds() // 3600)
            if remaining_hours <= 24:
                urgent_24h_order_count += 1

        risk_prob = calc_cancel_prob(overdue_hours)
        estimated_cancel_amount = round(float(order.buyer_payment or 0) * float(risk_prob), 2)
        estimated_cancel_amount_total += estimated_cancel_amount

        key = (
            int(order.listing_id) if order.listing_id is not None else None,
            int(order.variant_id) if order.variant_id is not None else None,
        )
        listing_row = listing_map.get(key[0]) if key[0] is not None else None
        variant_row = variant_map.get(key[1]) if key[1] is not None else None
        title = (
            (listing_row.title or "").strip()
            if listing_row
            else (order.items[0].product_name if order.items else order.order_no)
        ) or order.order_no
        sku = (variant_row.sku_code or "").strip() if variant_row and variant_row.sku_code else None

        if key not in grouped:
            grouped[key] = {
                "listing_id": key[0],
                "variant_id": key[1],
                "title": title,
                "sku": sku,
                "pending_order_count": 0,
                "backorder_qty_total": 0,
                "overdue_order_count": 0,
                "urgent_24h_order_count": 0,
                "nearest_deadline_at": deadline,
                "estimated_cancel_amount": 0.0,
            }
        bucket = grouped[key]
        bucket["pending_order_count"] += 1
        bucket["backorder_qty_total"] += order_backorder_qty
        bucket["estimated_cancel_amount"] += estimated_cancel_amount
        if overdue_hours > 0:
            bucket["overdue_order_count"] += 1
        elif deadline and int((deadline - current_tick).total_seconds() // 3600) <= 24:
            bucket["urgent_24h_order_count"] += 1
        nearest_deadline = bucket.get("nearest_deadline_at")
        if nearest_deadline is None or (deadline is not None and deadline < nearest_deadline):
            bucket["nearest_deadline_at"] = deadline

    top_rows = sorted(
        grouped.values(),
        key=lambda x: (int(x["backorder_qty_total"]), float(x["estimated_cancel_amount"])),
        reverse=True,
    )[:top_n]

    response = WarehouseBackorderRiskOverviewResponse(
        current_tick=current_tick,
        affected_order_count=affected_order_count,
        backorder_qty_total=backorder_qty_total,
        overdue_order_count=overdue_order_count,
        urgent_24h_order_count=urgent_24h_order_count,
        estimated_cancel_amount_total=round(estimated_cancel_amount_total, 2),
        top_items=[
            WarehouseBackorderRiskItemResponse(
                listing_id=row["listing_id"],
                variant_id=row["variant_id"],
                title=row["title"],
                sku=row["sku"],
                pending_order_count=int(row["pending_order_count"]),
                backorder_qty_total=int(row["backorder_qty_total"]),
                overdue_order_count=int(row["overdue_order_count"]),
                urgent_24h_order_count=int(row["urgent_24h_order_count"]),
                nearest_deadline_at=row["nearest_deadline_at"],
                estimated_cancel_amount=round(float(row["estimated_cancel_amount"]), 2),
            )
            for row in top_rows
        ],
    )
    cache_set_json(cache_key, response.model_dump(mode="json"), REDIS_CACHE_TTL_OVERVIEW_SEC)
    return response

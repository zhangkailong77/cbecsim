from datetime import date, datetime, time, timedelta
import hashlib
import httpx
import re
import json
import logging
import os
from typing import Any
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import Date, String, asc, cast, desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.security import get_current_user
from app.core.cache import cache_delete_prefix, cache_get_json, cache_set_json
from app.core.distributed_lock import acquire_distributed_lock, release_distributed_lock
from app.core.rate_limit import check_rate_limit
from app.db import get_db
from app.models import (
    GameRun,
    GameRunCashAdjustment,
    LogisticsShipment,
    InventoryLot,
    MarketProduct,
    OssStorageConfig,
    ShopeeCategoryNode,
    ShopeeListing,
    ShopeeListingDraft,
    ShopeeListingDraftImage,
    ShopeeListingDraftSpecValue,
    ShopeeListingImage,
    ShopeeListingQualityScore,
    ShopeeListingVariant,
    ShopeeListingWholesaleTier,
    ShopeeListingSpecValue,
    ShopeeOrder,
    ShopeeOrderItem,
    ShopeeOrderLogisticsEvent,
    ShopeeOrderSettlement,
    ShopeeBankAccount,
    ShopeeAddonCampaign,
    ShopeeAddonCampaignMainItem,
    ShopeeAddonCampaignRewardItem,
    ShopeeAddonDraft,
    ShopeeAddonDraftMainItem,
    ShopeeAddonDraftRewardItem,
    ShopeeDiscountCampaign,
    ShopeeDiscountCampaignItem,
    ShopeeDiscountDraft,
    ShopeeDiscountDraftItem,
    ShopeeDiscountPerformanceDaily,
    ShopeeShopVoucherCampaign,
    ShopeeProductVoucherCampaign,
    ShopeeFollowVoucherCampaign,
    ShopeeAutoReplySetting,
    ShopeeCustomerServiceConversation,
    ShopeeCustomerServiceMessage,
    ShopeeCustomerServiceModelSetting,
    ShopeeCustomerServiceScenario,
    ShopeeQuickReplyPreference,
    ShopeeQuickReplyGroup,
    ShopeeQuickReplyMessage,
    ShopeeShippingFeePromotionCampaign,
    ShopeeShippingFeePromotionChannel,
    ShopeeShippingFeePromotionTier,
    ShopeeProductVoucherItem,
    ShopeePrivateVoucherCampaign,
    ShopeePrivateVoucherItem,
    ShopeeLiveVoucherCampaign,
    ShopeeLiveVoucherItem,
    ShopeeVideoVoucherCampaign,
    ShopeeVideoVoucherItem,
    ShopeeFinanceLedgerEntry,
    ShopeeFlashSaleCampaign,
    ShopeeFlashSaleCampaignItem,
    ShopeeFlashSaleTrafficEvent,
    ShopeeFlashSaleCategoryRule,
    ShopeeFlashSaleDraft,
    ShopeeFlashSaleDraftItem,
    ShopeeFlashSaleSlot,
    ShopeeMarketingAnnouncement,
    ShopeeMarketingEvent,
    ShopeeMarketingTool,
    ShopeeOrderGenerationLog,
    ShopeeSpecTemplate,
    ShopeeSpecTemplateOption,
    ShopeeUserDiscountPreference,
    ShopeeUserMarketingPreference,
    SimBuyerProfile,
    User,
    InventoryStockMovement,
    WarehouseLandmark,
    WarehouseStrategy,
)
from app.services.shopee_fulfillment import (
    calc_settlement,
    calc_shipping_cost,
    gen_tracking_no,
    gen_waybill_no,
    haversine_km,
)
from app.services.shopee_order_cancellation import (
    auto_cancel_overdue_orders_by_tick as service_auto_cancel_overdue_orders_by_tick,
    cancel_order as service_cancel_order,
    rebalance_backorders_from_current_inventory as service_rebalance_backorders_from_current_inventory,
)
from app.services.inventory_lot_sync import consume_available_inventory_lots, consume_reserved_inventory_lots
from app.services.shopee_listing_quality import recompute_listing_quality
from app.services.shopee_order_simulator import simulate_orders_for_run
from app.api.routes.game import (
    REAL_SECONDS_PER_GAME_DAY,
    REAL_SECONDS_PER_GAME_HOUR,
    _align_compare_time,
    _persist_run_finished_if_reached,
    _resolve_game_hour_tick_by_run,
    _resolve_run_end_time,
)


router = APIRouter(prefix="/shopee", tags=["shopee"])
logger = logging.getLogger(__name__)
ORDER_SIM_TICK_GAME_HOURS = 8
ORDER_INCOME_RELEASE_DELAY_GAME_DAYS = 3
RM_TO_RMB_RATE = float(os.getenv("RM_TO_RMB_RATE", "1.74"))
REDIS_CACHE_TTL_ORDERS_LIST_SEC = max(3, int(os.getenv("REDIS_CACHE_TTL_ORDERS_LIST_SEC", "10")))
REDIS_CACHE_TTL_MARKETING_BOOTSTRAP_SEC = max(10, int(os.getenv("REDIS_CACHE_TTL_MARKETING_BOOTSTRAP_SEC", "30")))
REDIS_CACHE_TTL_DISCOUNT_BOOTSTRAP_SEC = max(10, int(os.getenv("REDIS_CACHE_TTL_DISCOUNT_BOOTSTRAP_SEC", "30")))
REDIS_CACHE_TTL_DISCOUNT_LIST_SEC = max(10, int(os.getenv("REDIS_CACHE_TTL_DISCOUNT_LIST_SEC", "30")))
REDIS_CACHE_TTL_DISCOUNT_DETAIL_SEC = max(10, int(os.getenv("REDIS_CACHE_TTL_DISCOUNT_DETAIL_SEC", "30")))
REDIS_CACHE_TTL_DISCOUNT_CREATE_BOOTSTRAP_SEC = max(10, int(os.getenv("REDIS_CACHE_TTL_DISCOUNT_CREATE_BOOTSTRAP_SEC", "30")))
REDIS_CACHE_TTL_SHOPEE_VOUCHER_CREATE_BOOTSTRAP_SEC = max(10, int(os.getenv("REDIS_CACHE_TTL_SHOPEE_VOUCHER_CREATE_BOOTSTRAP_SEC", "60")))
REDIS_CACHE_TTL_SHOPEE_VOUCHER_CODE_CHECK_SEC = max(5, int(os.getenv("REDIS_CACHE_TTL_SHOPEE_VOUCHER_CODE_CHECK_SEC", "10")))
REDIS_CACHE_TTL_SHOPEE_PRODUCT_VOUCHER_ELIGIBLE_PRODUCTS_SEC = max(10, int(os.getenv("REDIS_CACHE_TTL_SHOPEE_PRODUCT_VOUCHER_ELIGIBLE_PRODUCTS_SEC", "30")))
REDIS_CACHE_TTL_SHOPEE_SHIPPING_FEE_PROMOTION_BOOTSTRAP_SEC = max(10, int(os.getenv("REDIS_CACHE_TTL_SHOPEE_SHIPPING_FEE_PROMOTION_BOOTSTRAP_SEC", "60")))
REDIS_CACHE_TTL_SHOPEE_SHIPPING_FEE_PROMOTION_LIST_SEC = max(10, int(os.getenv("REDIS_CACHE_TTL_SHOPEE_SHIPPING_FEE_PROMOTION_LIST_SEC", "60")))
REDIS_CACHE_TTL_SHOPEE_AUTO_REPLY_SETTINGS_SEC = max(10, int(os.getenv("REDIS_CACHE_TTL_SHOPEE_AUTO_REPLY_SETTINGS_SEC", "300")))
REDIS_CACHE_TTL_SHOPEE_QUICK_REPLY_LIST_SEC = max(10, int(os.getenv("REDIS_CACHE_TTL_SHOPEE_QUICK_REPLY_LIST_SEC", "300")))
REDIS_CACHE_TTL_SHOPEE_CUSTOMER_SERVICE_LIST_SEC = max(5, int(os.getenv("REDIS_CACHE_TTL_SHOPEE_CUSTOMER_SERVICE_LIST_SEC", "30")))
REDIS_CACHE_TTL_SHOPEE_CUSTOMER_SERVICE_DETAIL_SEC = max(5, int(os.getenv("REDIS_CACHE_TTL_SHOPEE_CUSTOMER_SERVICE_DETAIL_SEC", "30")))
REDIS_CACHE_TTL_DISCOUNT_ELIGIBLE_PRODUCTS_SEC = max(10, int(os.getenv("REDIS_CACHE_TTL_DISCOUNT_ELIGIBLE_PRODUCTS_SEC", "20")))
REDIS_CACHE_TTL_DISCOUNT_DRAFT_SEC = max(30, int(os.getenv("REDIS_CACHE_TTL_DISCOUNT_DRAFT_SEC", "300")))
REDIS_CACHE_TTL_ADDON_BOOTSTRAP_SEC = max(10, int(os.getenv("REDIS_CACHE_TTL_ADDON_BOOTSTRAP_SEC", "30")))
REDIS_CACHE_TTL_ADDON_ELIGIBLE_PRODUCTS_SEC = max(10, int(os.getenv("REDIS_CACHE_TTL_ADDON_ELIGIBLE_PRODUCTS_SEC", "20")))
REDIS_CACHE_TTL_ADDON_DRAFT_SEC = max(30, int(os.getenv("REDIS_CACHE_TTL_ADDON_DRAFT_SEC", "300")))
REDIS_CACHE_TTL_ADDON_DETAIL_SEC = max(10, int(os.getenv("REDIS_CACHE_TTL_ADDON_DETAIL_SEC", "120")))
REDIS_CACHE_TTL_FLASH_SALE_BOOTSTRAP_SEC = max(10, int(os.getenv("REDIS_CACHE_TTL_FLASH_SALE_BOOTSTRAP_SEC", "300")))
REDIS_CACHE_TTL_FLASH_SALE_LIST_SEC = max(10, int(os.getenv("REDIS_CACHE_TTL_FLASH_SALE_LIST_SEC", "120")))
REDIS_CACHE_TTL_FLASH_SALE_DETAIL_SEC = max(10, int(os.getenv("REDIS_CACHE_TTL_FLASH_SALE_DETAIL_SEC", "120")))
REDIS_CACHE_TTL_FLASH_SALE_ELIGIBLE_PRODUCTS_SEC = max(10, int(os.getenv("REDIS_CACHE_TTL_FLASH_SALE_ELIGIBLE_PRODUCTS_SEC", "120")))
REDIS_CACHE_TTL_FLASH_SALE_DRAFT_SEC = max(30, int(os.getenv("REDIS_CACHE_TTL_FLASH_SALE_DRAFT_SEC", "1800")))
REDIS_PREFIX = os.getenv("REDIS_PREFIX", "cbec")
REDIS_LOCK_TTL_SEC = max(10, int(os.getenv("REDIS_LOCK_TTL_SEC", "45")))
REDIS_RATE_LIMIT_SIMULATE_PER_MIN = max(1, int(os.getenv("REDIS_RATE_LIMIT_SIMULATE_PER_MIN", "5")))
REDIS_RATE_LIMIT_ORDERS_LIST_PER_MIN = max(10, int(os.getenv("REDIS_RATE_LIMIT_ORDERS_LIST_PER_MIN", "120")))
REDIS_RATE_LIMIT_MARKETING_BOOTSTRAP_PER_MIN = max(10, int(os.getenv("REDIS_RATE_LIMIT_MARKETING_BOOTSTRAP_PER_MIN", "60")))
REDIS_RATE_LIMIT_DISCOUNT_BOOTSTRAP_PER_MIN = max(10, int(os.getenv("REDIS_RATE_LIMIT_DISCOUNT_BOOTSTRAP_PER_MIN", "60")))
REDIS_RATE_LIMIT_DISCOUNT_LIST_PER_MIN = max(10, int(os.getenv("REDIS_RATE_LIMIT_DISCOUNT_LIST_PER_MIN", "120")))
REDIS_RATE_LIMIT_DISCOUNT_DETAIL_PER_MIN = max(10, int(os.getenv("REDIS_RATE_LIMIT_DISCOUNT_DETAIL_PER_MIN", "120")))
REDIS_RATE_LIMIT_DISCOUNT_DATA_PER_MIN = max(10, int(os.getenv("REDIS_RATE_LIMIT_DISCOUNT_DATA_PER_MIN", "120")))
REDIS_RATE_LIMIT_DISCOUNT_DATA_EXPORT_PER_MIN = max(5, int(os.getenv("REDIS_RATE_LIMIT_DISCOUNT_DATA_EXPORT_PER_MIN", "10")))
REDIS_RATE_LIMIT_SHOPEE_CUSTOMER_SERVICE_PER_MIN = max(10, int(os.getenv("REDIS_RATE_LIMIT_SHOPEE_CUSTOMER_SERVICE_PER_MIN", "60")))
REDIS_RATE_LIMIT_SHOPEE_CUSTOMER_SERVICE_LLM_PER_MIN = max(3, int(os.getenv("REDIS_RATE_LIMIT_SHOPEE_CUSTOMER_SERVICE_LLM_PER_MIN", "10")))
REDIS_RATE_LIMIT_DISCOUNT_CREATE_BOOTSTRAP_PER_MIN = max(10, int(os.getenv("REDIS_RATE_LIMIT_DISCOUNT_CREATE_BOOTSTRAP_PER_MIN", "60")))
REDIS_RATE_LIMIT_SHOPEE_VOUCHER_CREATE_BOOTSTRAP_PER_MIN = max(10, int(os.getenv("REDIS_RATE_LIMIT_SHOPEE_VOUCHER_CREATE_BOOTSTRAP_PER_MIN", "60")))
REDIS_RATE_LIMIT_SHOPEE_VOUCHER_CODE_CHECK_PER_MIN = max(10, int(os.getenv("REDIS_RATE_LIMIT_SHOPEE_VOUCHER_CODE_CHECK_PER_MIN", "120")))
REDIS_RATE_LIMIT_SHOPEE_VOUCHER_CREATE_PER_MIN = max(5, int(os.getenv("REDIS_RATE_LIMIT_SHOPEE_VOUCHER_CREATE_PER_MIN", "20")))
REDIS_RATE_LIMIT_SHOPEE_SHIPPING_FEE_PROMOTION_PER_MIN = max(10, int(os.getenv("REDIS_RATE_LIMIT_SHOPEE_SHIPPING_FEE_PROMOTION_PER_MIN", "120")))
REDIS_RATE_LIMIT_SHOPEE_SHIPPING_FEE_PROMOTION_CREATE_PER_MIN = max(5, int(os.getenv("REDIS_RATE_LIMIT_SHOPEE_SHIPPING_FEE_PROMOTION_CREATE_PER_MIN", "20")))
REDIS_RATE_LIMIT_SHOPEE_AUTO_REPLY_PER_MIN = max(10, int(os.getenv("REDIS_RATE_LIMIT_SHOPEE_AUTO_REPLY_PER_MIN", "120")))
REDIS_RATE_LIMIT_SHOPEE_AUTO_REPLY_UPDATE_PER_MIN = max(5, int(os.getenv("REDIS_RATE_LIMIT_SHOPEE_AUTO_REPLY_UPDATE_PER_MIN", "30")))
REDIS_RATE_LIMIT_SHOPEE_QUICK_REPLY_PER_MIN = max(10, int(os.getenv("REDIS_RATE_LIMIT_SHOPEE_QUICK_REPLY_PER_MIN", "120")))
REDIS_RATE_LIMIT_SHOPEE_QUICK_REPLY_UPDATE_PER_MIN = max(5, int(os.getenv("REDIS_RATE_LIMIT_SHOPEE_QUICK_REPLY_UPDATE_PER_MIN", "30")))
REDIS_RATE_LIMIT_DISCOUNT_ELIGIBLE_PRODUCTS_PER_MIN = max(10, int(os.getenv("REDIS_RATE_LIMIT_DISCOUNT_ELIGIBLE_PRODUCTS_PER_MIN", "120")))
REDIS_RATE_LIMIT_DISCOUNT_DRAFTS_PER_MIN = max(10, int(os.getenv("REDIS_RATE_LIMIT_DISCOUNT_DRAFTS_PER_MIN", "60")))
REDIS_RATE_LIMIT_DISCOUNT_CREATE_PER_MIN = max(5, int(os.getenv("REDIS_RATE_LIMIT_DISCOUNT_CREATE_PER_MIN", "20")))
REDIS_RATE_LIMIT_ADDON_BOOTSTRAP_PER_MIN = max(10, int(os.getenv("REDIS_RATE_LIMIT_ADDON_BOOTSTRAP_PER_MIN", "60")))
REDIS_RATE_LIMIT_ADDON_ELIGIBLE_PRODUCTS_PER_MIN = max(10, int(os.getenv("REDIS_RATE_LIMIT_ADDON_ELIGIBLE_PRODUCTS_PER_MIN", "120")))
REDIS_RATE_LIMIT_ADDON_DRAFTS_PER_MIN = max(10, int(os.getenv("REDIS_RATE_LIMIT_ADDON_DRAFTS_PER_MIN", "30")))
REDIS_RATE_LIMIT_ADDON_CREATE_PER_MIN = max(5, int(os.getenv("REDIS_RATE_LIMIT_ADDON_CREATE_PER_MIN", "20")))
REDIS_RATE_LIMIT_FLASH_SALE_PER_MIN = max(10, int(os.getenv("REDIS_RATE_LIMIT_FLASH_SALE_PER_MIN", "120")))
REDIS_RATE_LIMIT_FLASH_SALE_CREATE_PER_MIN = max(5, int(os.getenv("REDIS_RATE_LIMIT_FLASH_SALE_CREATE_PER_MIN", "20")))
RUN_FINISHED_DETAIL = "当前对局已结束，无法继续订单演化操作"
LINE_TRANSIT_DAY_BOUNDS: dict[str, tuple[int, int]] = {
    "economy": (8, 18),
    "standard": (5, 12),
    "express": (3, 8),
}
CHANNEL_TO_FORWARDER_KEY: dict[str, str] = {
    "快捷快递": "express",
    "标准快递": "standard",
    "标准大件": "economy",
}
FORWARDER_KEY_TO_LABEL: dict[str, str] = {
    "economy": "经济线（马来）",
    "standard": "标准线（马来）",
    "express": "快速线（马来）",
}


def _shopee_orders_cache_prefix(run_id: int, user_id: int) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:orders:list:{run_id}:{user_id}:"


def _shopee_addon_orders_cache_prefix(run_id: int, user_id: int) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:add-on:orders:{run_id}:{user_id}:"


def _shopee_bundle_orders_cache_prefix(run_id: int, user_id: int) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:bundle:orders:{run_id}:{user_id}:"


def _shopee_voucher_orders_cache_prefix(run_id: int, user_id: int) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:voucher:orders:{run_id}:{user_id}:"


def _shopee_marketing_bootstrap_cache_key(*, run_id: int, user_id: int, market: str, lang: str) -> str:
    safe_market = (market or "MY").strip().upper() or "MY"
    safe_lang = (lang or "zh-CN").strip() or "zh-CN"
    return f"{REDIS_PREFIX}:cache:shopee:marketing:bootstrap:{run_id}:{user_id}:{safe_market}:{safe_lang}"


def _invalidate_shopee_marketing_bootstrap_cache(*, run_id: int, user_id: int) -> None:
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:marketing:bootstrap:{run_id}:{user_id}:")


def _enforce_shopee_marketing_bootstrap_rate_limit(*, user_id: int) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:marketing:bootstrap:user:{user_id}",
        limit=REDIS_RATE_LIMIT_MARKETING_BOOTSTRAP_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"请求过于频繁，请在 {reset_at} 后重试",
        )


def _build_shopee_orders_cache_key(
    *,
    run_id: int,
    user_id: int,
    type_value: str,
    source: str | None,
    sort_by: str | None,
    order: str,
    order_type: str,
    order_status: str,
    priority: str,
    keyword: str | None,
    channel: str | None,
    page: int,
    page_size: int,
) -> str:
    query_payload = {
        "type": type_value or "all",
        "source": source or "",
        "sort_by": sort_by or "",
        "order": order or "asc",
        "order_type": order_type or "all",
        "order_status": order_status or "all",
        "priority": priority or "all",
        "keyword": keyword or "",
        "channel": channel or "",
        "page": int(page),
        "page_size": int(page_size),
    }
    digest = hashlib.sha1(
        json.dumps(query_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return f"{_shopee_orders_cache_prefix(run_id, user_id)}{digest}"


def _get_shopee_orders_cache_payload(**kwargs) -> dict[str, Any] | None:
    key = _build_shopee_orders_cache_key(**kwargs)
    payload = cache_get_json(key)
    if isinstance(payload, dict):
        return payload
    return None


def _set_shopee_orders_cache_payload(*, payload: dict[str, Any], **kwargs) -> None:
    key = _build_shopee_orders_cache_key(**kwargs)
    cache_set_json(key, payload, REDIS_CACHE_TTL_ORDERS_LIST_SEC)


def _invalidate_shopee_orders_cache_for_user(*, run_id: int, user_id: int) -> None:
    cache_delete_prefix(_shopee_orders_cache_prefix(run_id, user_id))
    cache_delete_prefix(_shopee_addon_orders_cache_prefix(run_id, user_id))
    cache_delete_prefix(_shopee_bundle_orders_cache_prefix(run_id, user_id))
    cache_delete_prefix(_shopee_voucher_orders_cache_prefix(run_id, user_id))


def _shopee_addon_orders_cache_key(*, run_id: int, user_id: int, source_campaign_id: int) -> str:
    return f"{_shopee_addon_orders_cache_prefix(run_id, user_id)}{source_campaign_id}"


def _shopee_bundle_orders_cache_key(*, run_id: int, user_id: int, campaign_id: int) -> str:
    return f"{_shopee_bundle_orders_cache_prefix(run_id, user_id)}{campaign_id}"


def _shopee_voucher_orders_cache_key(*, run_id: int, user_id: int, voucher_type: str, campaign_id: int, page: int, page_size: int) -> str:
    safe_voucher_type = (voucher_type or "shop_voucher").strip().lower() or "shop_voucher"
    return f"{_shopee_voucher_orders_cache_prefix(run_id, user_id)}{safe_voucher_type}:{campaign_id}:{page}:{page_size}"


def _shopee_auto_reply_settings_cache_key(*, run_id: int, user_id: int) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:auto_reply:settings:{run_id}:{user_id}"


def _invalidate_shopee_auto_reply_cache(*, run_id: int, user_id: int) -> None:
    cache_delete_prefix(_shopee_auto_reply_settings_cache_key(run_id=run_id, user_id=user_id))


def _enforce_shopee_auto_reply_rate_limit(*, user_id: int, update: bool = False) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:auto_reply:{'update' if update else 'read'}:user:{user_id}",
        limit=REDIS_RATE_LIMIT_SHOPEE_AUTO_REPLY_UPDATE_PER_MIN if update else REDIS_RATE_LIMIT_SHOPEE_AUTO_REPLY_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"请求过于频繁，请在 {reset_at} 后重试",
        )


def _shopee_quick_reply_list_cache_key(*, run_id: int, user_id: int) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:quick_reply:list:{run_id}:{user_id}"


def _invalidate_shopee_quick_reply_cache(*, run_id: int, user_id: int) -> None:
    cache_delete_prefix(_shopee_quick_reply_list_cache_key(run_id=run_id, user_id=user_id))


def _enforce_shopee_quick_reply_rate_limit(*, user_id: int, update: bool = False) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:quick_reply:{'update' if update else 'read'}:user:{user_id}",
        limit=REDIS_RATE_LIMIT_SHOPEE_QUICK_REPLY_UPDATE_PER_MIN if update else REDIS_RATE_LIMIT_SHOPEE_QUICK_REPLY_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"请求过于频繁，请在 {reset_at} 后重试",
        )


def _enforce_shopee_orders_list_rate_limit(*, user_id: int) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:orders:list:user:{user_id}",
        limit=REDIS_RATE_LIMIT_ORDERS_LIST_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"请求过于频繁，请在 {reset_at} 后重试",
        )


def _enforce_shopee_simulate_rate_limit(*, user_id: int) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:simulate:user:{user_id}",
        limit=REDIS_RATE_LIMIT_SIMULATE_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"模拟请求过于频繁，请在 {reset_at} 后重试",
        )


def _acquire_shopee_simulate_lock_or_409(*, run_id: int, user_id: int) -> tuple[str, str]:
    lock_key = f"{REDIS_PREFIX}:lock:shopee:simulate:{run_id}:{user_id}"
    token = acquire_distributed_lock(lock_key, REDIS_LOCK_TTL_SEC)
    if token is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="订单模拟正在进行中，请稍后重试")
    return lock_key, token


DEFAULT_AUTO_REPLY_MESSAGE = "您好，欢迎光临本店！请问有什么可以帮您？"
OFF_WORK_AUTO_REPLY_MESSAGE = "亲爱的买家，您的消息已收到。由于目前是非工作时间，我们暂时无法回复您。我们一上线就会立即回复您。感谢您的理解。"
AUTO_REPLY_TYPES = {"default", "off_work"}
AUTO_REPLY_MAX_MESSAGE_LENGTH = 500


class ShopeeAutoReplySettingResponse(BaseModel):
    id: int | None = None
    reply_type: str
    enabled: bool
    message: str
    work_time_enabled: bool = False
    work_start_time: str | None = None
    work_end_time: str | None = None
    timezone: str = "game_time"
    trigger_interval_minutes: int
    trigger_once_per_game_day: bool
    sent_count: int = 0
    last_sent_game_at: datetime | None = None
    status: str


class ShopeeAutoReplyRulesResponse(BaseModel):
    max_message_length: int = AUTO_REPLY_MAX_MESSAGE_LENGTH
    default_reply_interval_minutes: int = 1440
    off_work_once_per_game_day: bool = True


class ShopeeAutoReplySettingsResponse(BaseModel):
    default_reply: ShopeeAutoReplySettingResponse
    off_work_reply: ShopeeAutoReplySettingResponse
    rules: ShopeeAutoReplyRulesResponse


class ShopeeAutoReplyUpdateRequest(BaseModel):
    enabled: bool | None = None
    message: str | None = None
    work_start_time: str | None = None
    work_end_time: str | None = None


class ShopeeAutoReplyUpdateResponse(BaseModel):
    setting: ShopeeAutoReplySettingResponse


QUICK_REPLY_MAX_GROUPS = 25
QUICK_REPLY_MAX_MESSAGES_PER_GROUP = 20
QUICK_REPLY_MAX_GROUP_NAME_LENGTH = 200
QUICK_REPLY_MAX_MESSAGE_LENGTH = 500
QUICK_REPLY_MAX_TAGS_PER_MESSAGE = 3
QUICK_REPLY_MAX_TAG_LENGTH = 32


class ShopeeQuickReplyPreferenceResponse(BaseModel):
    auto_hint_enabled: bool


class ShopeeQuickReplyLimitsResponse(BaseModel):
    max_groups: int = QUICK_REPLY_MAX_GROUPS
    max_messages_per_group: int = QUICK_REPLY_MAX_MESSAGES_PER_GROUP
    max_group_name_length: int = QUICK_REPLY_MAX_GROUP_NAME_LENGTH
    max_message_length: int = QUICK_REPLY_MAX_MESSAGE_LENGTH
    max_tags_per_message: int = QUICK_REPLY_MAX_TAGS_PER_MESSAGE


class ShopeeQuickReplyMessageResponse(BaseModel):
    id: int
    message: str
    tags: list[str]
    sort_order: int


class ShopeeQuickReplyGroupResponse(BaseModel):
    id: int
    group_name: str
    enabled: bool
    sort_order: int
    message_count: int
    messages: list[ShopeeQuickReplyMessageResponse]


class ShopeeQuickReplyListResponse(BaseModel):
    preference: ShopeeQuickReplyPreferenceResponse
    limits: ShopeeQuickReplyLimitsResponse
    groups: list[ShopeeQuickReplyGroupResponse]


class ShopeeQuickReplyPreferenceUpdateRequest(BaseModel):
    auto_hint_enabled: bool


class ShopeeQuickReplyPreferenceUpdateResponse(BaseModel):
    preference: ShopeeQuickReplyPreferenceResponse


class ShopeeQuickReplyCreateMessageRequest(BaseModel):
    message: str
    tags: list[str] = Field(default_factory=list)


class ShopeeQuickReplyCreateGroupRequest(BaseModel):
    group_name: str
    enabled: bool = True
    messages: list[ShopeeQuickReplyCreateMessageRequest]


class ShopeeQuickReplyUpdateGroupRequest(BaseModel):
    group_name: str
    enabled: bool = True
    messages: list[ShopeeQuickReplyCreateMessageRequest]


class ShopeeQuickReplyGroupCreateResponse(BaseModel):
    group: ShopeeQuickReplyGroupResponse


class ShopeeQuickReplyGroupEnabledRequest(BaseModel):
    enabled: bool


class ShopeeQuickReplyGroupSortRequest(BaseModel):
    direction: str


class ShopeeQuickReplyGroupReorderRequest(BaseModel):
    group_ids: list[int]


CUSTOMER_SERVICE_SCENARIO_PRODUCT_DETAIL = "product_detail_inquiry"
CUSTOMER_SERVICE_OPEN_STATUSES = {"open", "waiting_seller"}
CUSTOMER_SERVICE_MAX_OPEN_CONVERSATIONS = 3
CUSTOMER_SERVICE_MAX_DAILY_CONVERSATIONS = 5
CUSTOMER_SERVICE_MAX_MESSAGES = 10
CUSTOMER_SERVICE_RECOMMENDED_MESSAGES = 7
CUSTOMER_SERVICE_MIN_MESSAGES = 5


class ShopeeCustomerServiceListingResponse(BaseModel):
    id: int | None = None
    title: str = ""
    image_url: str | None = None
    price: int | None = None
    original_price: int | None = None
    stock_available: int | None = None
    quality_total_score: int | None = None
    specs: list[dict[str, Any]] = Field(default_factory=list)
    variants: list[dict[str, Any]] = Field(default_factory=list)
    description_summary: str = ""


class ShopeeCustomerServiceMessageResponse(BaseModel):
    id: int
    sender_type: str
    message_type: str
    content: str
    sent_game_at: datetime


class ShopeeCustomerServiceConversationSummaryResponse(BaseModel):
    id: int
    scenario_code: str
    scenario_name: str
    buyer_name: str
    status: str
    last_message: str
    last_message_game_at: datetime | None = None
    listing: ShopeeCustomerServiceListingResponse | None = None
    unread_count: int = 0
    message_count: int = 0


class ShopeeCustomerServiceConversationListResponse(BaseModel):
    items: list[ShopeeCustomerServiceConversationSummaryResponse]
    total: int
    page: int
    page_size: int
    model_ready: bool
    model_message: str | None = None


class ShopeeCustomerServiceConversationDetailResponse(BaseModel):
    id: int
    scenario_code: str
    scenario_name: str
    buyer_name: str
    status: str
    trigger_reason: str
    listing: ShopeeCustomerServiceListingResponse | None = None
    messages: list[ShopeeCustomerServiceMessageResponse]
    satisfaction_score: float | None = None
    satisfaction_level: str | None = None
    score_detail: dict[str, Any] | None = None
    can_send: bool
    can_resolve: bool
    min_messages: int = CUSTOMER_SERVICE_MIN_MESSAGES
    recommended_messages: int = CUSTOMER_SERVICE_RECOMMENDED_MESSAGES
    max_messages: int = CUSTOMER_SERVICE_MAX_MESSAGES
    model_ready: bool
    model_message: str | None = None


class ShopeeCustomerServiceSendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class ShopeeCustomerServiceResolveResponse(BaseModel):
    conversation: ShopeeCustomerServiceConversationDetailResponse


class ShopeeCustomerServiceModelSettingResponse(BaseModel):
    id: int | None = None
    provider: str = "lm_studio"
    model_name: str = "local-model"
    base_url: str | None = "http://localhost:1234/v1"
    temperature: float = 0.7
    max_tokens: int = 300
    enabled: bool = False
    api_key_configured: bool = False


class ShopeeCustomerServiceModelSettingUpdateRequest(BaseModel):
    provider: str = "lm_studio"
    model_name: str
    base_url: str | None = "http://localhost:1234/v1"
    api_key_ref: str | None = None
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=300, ge=64, le=2000)
    enabled: bool = True


class ShopeeCustomerServiceModelSettingUpdateResponse(BaseModel):
    setting: ShopeeCustomerServiceModelSettingResponse


class ShopeeOrderItemResponse(BaseModel):
    listing_id: int | None = None
    variant_id: int | None = None
    product_id: int | None = None
    product_name: str
    variant_name: str
    quantity: int
    unit_price: int
    image_url: str | None
    stock_fulfillment_status: str = "in_stock"
    backorder_qty: int = 0
    marketing_campaign_type: str | None = None
    marketing_campaign_id: int | None = None
    marketing_campaign_name_snapshot: str | None = None
    line_role: str = "main"
    original_unit_price: float = 0
    discounted_unit_price: float = 0


class ShopeeOrderResponse(BaseModel):
    id: int
    order_no: str
    buyer_name: str
    buyer_payment: int
    order_type: str
    type_bucket: str
    process_status: str
    shipping_priority: str
    shipping_channel: str
    destination: str
    countdown_text: str
    action_text: str
    ship_by_date: datetime | None
    tracking_no: str | None = None
    waybill_no: str | None = None
    listing_id: int | None = None
    variant_id: int | None = None
    stock_fulfillment_status: str
    backorder_qty: int
    must_restock_before_at: datetime | None = None
    ship_by_at: datetime | None = None
    shipped_at: datetime | None = None
    delivered_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancel_reason: str | None = None
    cancel_source: str | None = None
    eta_start_at: datetime | None = None
    eta_end_at: datetime | None = None
    distance_km: float | None = None
    delivery_line_label: str | None = None
    promised_transit_days_text: str | None = None
    transit_days_expected: int | None = None
    transit_days_elapsed: int | None = None
    transit_days_remaining: int | None = None
    created_at: datetime
    items: list[ShopeeOrderItemResponse]
    marketing_campaign_type: str | None = None
    marketing_campaign_id: int | None = None
    marketing_campaign_name_snapshot: str | None = None
    discount_percent: float | None = None
    order_subtotal_amount: float = 0
    voucher_campaign_type: str | None = None
    voucher_campaign_id: int | None = None
    voucher_name_snapshot: str | None = None
    voucher_code_snapshot: str | None = None
    voucher_discount_amount: float = 0
    shipping_promotion_campaign_id: int | None = None
    shipping_promotion_name_snapshot: str | None = None
    shipping_promotion_tier_index: int | None = None
    shipping_fee_before_promotion: float = 0
    shipping_fee_after_promotion: float = 0
    shipping_promotion_discount_amount: float = 0


class ShopeeOrderTabCounts(BaseModel):
    all: int
    unpaid: int
    toship: int
    shipping: int
    completed: int
    return_refund_cancel: int


class ShopeeOrdersListResponse(BaseModel):
    counts: ShopeeOrderTabCounts
    page: int
    page_size: int
    total: int
    simulated_recent_1h: int = 0
    last_simulated_at: datetime | None = None
    orders: list[ShopeeOrderResponse]


class ShopeeSimulateOrdersResponse(BaseModel):
    tick_time: datetime
    active_buyer_count: int
    candidate_product_count: int
    generated_order_count: int
    flash_sale_traffic: dict[str, int] = Field(default_factory=dict)
    skip_reasons: dict[str, int] = Field(default_factory=dict)
    shop_context: dict[str, Any] = Field(default_factory=dict)
    buyer_journeys: list[dict[str, Any]] = Field(default_factory=list)


class ShopeeShipOrderRequest(BaseModel):
    shipping_channel: str | None = None


class ShopeeShipOrderResponse(BaseModel):
    order_id: int
    tracking_no: str
    waybill_no: str
    shipping_channel: str
    distance_km: float
    delivery_line_label: str | None = None
    promised_transit_days_text: str | None = None
    transit_days_expected: int | None = None
    eta_start_at: datetime
    eta_end_at: datetime
    process_status: str
    type_bucket: str


class ShopeeCancelOrderRequest(BaseModel):
    reason: str | None = None


class ShopeeCancelOrderResponse(BaseModel):
    order_id: int
    type_bucket: str
    process_status: str
    cancelled_at: datetime | None
    cancel_reason: str | None
    cancel_source: str | None


class ShopeeLogisticsEventResponse(BaseModel):
    event_code: str
    event_title: str
    event_desc: str | None
    event_time: datetime


class ShopeeOrderLogisticsResponse(BaseModel):
    order_id: int
    order_no: str
    tracking_no: str | None
    waybill_no: str | None
    shipping_channel: str
    destination: str
    eta_start_at: datetime | None
    eta_end_at: datetime | None
    delivery_line_label: str | None = None
    promised_transit_days_text: str | None = None
    transit_days_expected: int | None = None
    transit_days_elapsed: int | None = None
    transit_days_remaining: int | None = None
    events: list[ShopeeLogisticsEventResponse]


class ShopeeProgressLogisticsRequest(BaseModel):
    event_code: str | None = None


class ShopeeProgressLogisticsResponse(BaseModel):
    order_id: int
    order_no: str
    type_bucket: str
    process_status: str
    current_event_code: str
    delivered_at: datetime | None


class ShopeeOrderSettlementResponse(BaseModel):
    order_id: int
    settlement_status: str
    buyer_payment: float
    platform_commission_amount: float
    payment_fee_amount: float
    shipping_cost_amount: float
    shipping_subsidy_amount: float
    shipping_promotion_discount_amount: float = 0
    net_income_amount: float
    settled_at: datetime | None


class ShopeeFinanceOverviewResponse(BaseModel):
    wallet_balance: float
    total_income: float
    today_income: float
    week_income: float
    month_income: float
    transaction_count: int
    current_tick: datetime


class ShopeeFinanceTransactionRowResponse(BaseModel):
    id: int
    order_id: int | None
    order_no: str | None
    buyer_name: str | None
    entry_type: str
    direction: str
    amount: float
    balance_after: float
    status: str
    remark: str | None
    credited_at: datetime


class ShopeeFinanceTransactionsResponse(BaseModel):
    page: int
    page_size: int
    total: int
    rows: list[ShopeeFinanceTransactionRowResponse]


class ShopeeFinanceIncomeRowResponse(BaseModel):
    id: int
    order_id: int
    order_no: str
    buyer_name: str
    product_name: str | None
    variant_name: str | None
    image_url: str | None
    amount: float
    status: str
    credited_at: datetime


class ShopeeFinanceIncomeListResponse(BaseModel):
    page: int
    page_size: int
    total: int
    rows: list[ShopeeFinanceIncomeRowResponse]


class ShopeeBankAccountCreateRequest(BaseModel):
    bank_name: str
    account_holder: str
    account_no: str
    is_default: bool = False


class ShopeeBankAccountResponse(BaseModel):
    id: int
    bank_name: str
    account_holder: str
    account_no_masked: str
    currency: str
    is_default: bool
    verify_status: str
    created_at: datetime


class ShopeeBankAccountsListResponse(BaseModel):
    total: int
    rows: list[ShopeeBankAccountResponse]


class ShopeeFinanceWithdrawRequest(BaseModel):
    amount: float = Field(gt=0, le=100000000)


class ShopeeFinanceWithdrawResponse(BaseModel):
    wallet_balance: float
    withdraw_rm: float
    credited_rmb: float
    exchange_rate: float
    ledger_id: int
    cash_adjustment_id: int
    credited_at: datetime


class ShopeeMarketingAnnouncementResponse(BaseModel):
    id: int
    title: str
    summary: str
    badge_text: str | None = None
    published_at: datetime | None = None


class ShopeeMarketingToolResponse(BaseModel):
    tool_key: str
    tool_name: str
    tag_type: str
    description: str
    icon_key: str
    target_route: str
    is_enabled: bool
    is_visible: bool


class ShopeeMarketingEventResponse(BaseModel):
    id: int
    title: str
    image_url: str
    jump_url: str
    status: str


class ShopeeMarketingPreferencesResponse(BaseModel):
    tools_collapsed: bool = False
    last_viewed_at: datetime | None = None


class ShopeeMarketingBootstrapMetaResponse(BaseModel):
    run_id: int
    user_id: int
    market: str
    lang: str
    current_tick: datetime


class ShopeeMarketingBootstrapResponse(BaseModel):
    meta: ShopeeMarketingBootstrapMetaResponse
    preferences: ShopeeMarketingPreferencesResponse
    announcements: list[ShopeeMarketingAnnouncementResponse] = Field(default_factory=list)
    tools: list[ShopeeMarketingToolResponse] = Field(default_factory=list)
    events: list[ShopeeMarketingEventResponse] = Field(default_factory=list)


class ShopeeMarketingPreferencesUpdateRequest(BaseModel):
    tools_collapsed: bool = False


class ShopeeDiscountCreateCardResponse(BaseModel):
    type: str
    title: str
    description: str
    enabled: bool
    target_route: str


class ShopeeDiscountTabResponse(BaseModel):
    key: str
    label: str
    count: int
    active: bool = False


class ShopeeDiscountMetricResponse(BaseModel):
    key: str
    label: str
    value: str | int | float
    delta: float = 0.0


class ShopeeDiscountPerformanceResponse(BaseModel):
    label: str
    range_text: str
    metrics: list[ShopeeDiscountMetricResponse] = Field(default_factory=list)


class ShopeeDiscountFiltersResponse(BaseModel):
    discount_type: str = "all"
    status: str = "all"
    search_field: str = "campaign_name"
    keyword: str = ""
    date_from: str | None = None
    date_to: str | None = None


class ShopeeDiscountProductThumbResponse(BaseModel):
    image_url: str | None = None


class ShopeeDiscountCampaignRowResponse(BaseModel):
    id: int
    campaign_name: str
    status: str
    status_label: str
    campaign_type: str
    campaign_type_label: str
    products: list[ShopeeDiscountProductThumbResponse] = Field(default_factory=list)
    products_overflow_count: int = 0
    period_text: str
    actions: list[str] = Field(default_factory=list)


class ShopeeDiscountPaginationResponse(BaseModel):
    page: int
    page_size: int
    total: int


class ShopeeDiscountCampaignListResponse(BaseModel):
    items: list[ShopeeDiscountCampaignRowResponse] = Field(default_factory=list)
    pagination: ShopeeDiscountPaginationResponse


class ShopeeDiscountPreferencesResponse(BaseModel):
    selected_discount_type: str = "all"
    selected_status: str = "all"
    search_field: str = "campaign_name"
    keyword: str = ""
    date_from: datetime | None = None
    date_to: datetime | None = None
    last_viewed_at: datetime | None = None


class ShopeeDiscountPreferencesUpdateRequest(BaseModel):
    selected_discount_type: str = "all"
    selected_status: str = "all"
    search_field: str = "campaign_name"
    keyword: str = ""
    date_from: str | None = None
    date_to: str | None = None


class ShopeeDiscountBootstrapMetaResponse(BaseModel):
    run_id: int
    user_id: int
    market: str
    currency: str
    read_only: bool
    current_tick: datetime


class ShopeeDiscountBootstrapResponse(BaseModel):
    meta: ShopeeDiscountBootstrapMetaResponse
    create_cards: list[ShopeeDiscountCreateCardResponse] = Field(default_factory=list)
    tabs: list[ShopeeDiscountTabResponse] = Field(default_factory=list)
    performance: ShopeeDiscountPerformanceResponse
    filters: ShopeeDiscountFiltersResponse
    list: ShopeeDiscountCampaignListResponse
    preferences: ShopeeDiscountPreferencesResponse


class ShopeeDiscountCreateMetaResponse(BaseModel):
    run_id: int
    user_id: int
    campaign_type: str
    read_only: bool
    current_tick: datetime


class ShopeeDiscountCreateFormResponse(BaseModel):
    campaign_name: str = ""
    name_max_length: int = 150
    start_at: str | None = None
    end_at: str | None = None
    max_duration_days: int = 180


class ShopeeDiscountCreateRulesResponse(BaseModel):
    discount_modes: list[str] = Field(default_factory=lambda: ["percent", "final_price"])
    discount_percent_range: list[int] = Field(default_factory=lambda: [1, 99])
    requires_at_least_one_product: bool = True


class ShopeeDiscountCreateProductRowResponse(BaseModel):
    listing_id: int
    variant_id: int | None = None
    product_name: str
    variant_name: str = ""
    category: str = ""
    image_url: str | None = None
    sku: str | None = None
    original_price: float
    stock_available: int
    discount_mode: str = "percent"
    discount_percent: float | None = 10.0
    final_price: float | None = None
    activity_stock_limit: int | None = None
    conflict: bool = False
    conflict_reason: str | None = None


class ShopeeDiscountCreateProductPickerResponse(BaseModel):
    default_page_size: int = 20


class ShopeeDiscountCreateDraftSummaryResponse(BaseModel):
    id: int
    updated_at: datetime


class ShopeeDiscountCreateBootstrapResponse(BaseModel):
    meta: ShopeeDiscountCreateMetaResponse
    form: ShopeeDiscountCreateFormResponse
    rules: ShopeeDiscountCreateRulesResponse
    selected_products: list[ShopeeDiscountCreateProductRowResponse] = Field(default_factory=list)
    product_picker: ShopeeDiscountCreateProductPickerResponse
    draft: ShopeeDiscountCreateDraftSummaryResponse | None = None


class ShopeeDiscountEligibleProductsResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[ShopeeDiscountCreateProductRowResponse] = Field(default_factory=list)


class ShopeeDiscountDraftItemPayload(BaseModel):
    listing_id: int
    variant_id: int | None = None
    product_name: str
    variant_name: str = ""
    image_url: str | None = None
    sku: str | None = None
    original_price: float
    stock_available: int = 0
    discount_mode: str = "percent"
    discount_percent: float | None = None
    final_price: float | None = None
    activity_stock_limit: int | None = None


class ShopeeDiscountDraftUpsertRequest(BaseModel):
    draft_id: int | None = None
    campaign_type: str = "discount"
    campaign_name: str = ""
    start_at: str | None = None
    end_at: str | None = None
    items: list[ShopeeDiscountDraftItemPayload] = Field(default_factory=list)


class ShopeeDiscountDraftDetailResponse(BaseModel):
    id: int
    campaign_type: str
    campaign_name: str
    start_at: str | None = None
    end_at: str | None = None
    status: str
    items: list[ShopeeDiscountCreateProductRowResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ShopeeDiscountCampaignCreateRequest(BaseModel):
    campaign_type: str = "discount"
    campaign_name: str
    start_at: str
    end_at: str
    items: list[ShopeeDiscountDraftItemPayload] = Field(default_factory=list)


class ShopeeDiscountCampaignCreateResponse(BaseModel):
    campaign_id: int
    campaign_name: str
    campaign_status: str
    item_count: int
    start_at: datetime
    end_at: datetime


class ShopeeVoucherCreateMetaResponse(BaseModel):
    run_id: int
    user_id: int
    voucher_type: str
    read_only: bool
    current_tick: datetime
    currency: str = "RM"


class ShopeeVoucherCreateFormResponse(BaseModel):
    voucher_name: str = ""
    code_prefix: str = "HOME"
    code_suffix_max_length: int = 5
    start_at: str
    end_at: str
    display_before_start: bool = False
    display_start_at: str | None = None
    reward_type: str = "discount"
    discount_type: str = "fixed_amount"
    discount_amount: float | None = None
    discount_percent: float | None = None
    max_discount_type: str = "set_amount"
    max_discount_amount: float | None = None
    min_spend_amount: float | None = None
    usage_limit: int | None = None
    per_buyer_limit: int = 1
    display_type: str = "all_pages"
    display_channels: list[str] = Field(default_factory=list)
    applicable_scope: str = "all_shop_products"
    audience_scope: str = ""


class ShopeeVoucherCreateRulesResponse(BaseModel):
    voucher_name_max_length: int = 100
    code_suffix_pattern: str = "^[A-Z0-9]{1,5}$"
    min_duration_minutes: int = 1
    max_duration_days: int = 180
    discount_types: list[str] = Field(default_factory=lambda: ["fixed_amount", "percent"])
    max_discount_types: list[str] = Field(default_factory=lambda: ["set_amount", "no_limit"])
    display_types: list[str] = Field(default_factory=lambda: ["all_pages", "specific_channels", "code_only"])
    display_channels: list[str] = Field(default_factory=lambda: ["checkout_page"])
    min_selected_products: int = 1
    max_selected_products: int = 100
    requires_usage_limit: bool = True


class ShopeeVoucherProductPickerResponse(BaseModel):
    default_page_size: int = 20
    search_fields: list[str] = Field(default_factory=lambda: ["product_name", "product_id"])
    available_only_default: bool = True


class ShopeeVoucherCreateBootstrapResponse(BaseModel):
    meta: ShopeeVoucherCreateMetaResponse
    form: ShopeeVoucherCreateFormResponse
    rules: ShopeeVoucherCreateRulesResponse
    product_picker: ShopeeVoucherProductPickerResponse | None = None
    selected_products: list[dict[str, Any]] = Field(default_factory=list)


class ShopeeFollowVoucherCreateFormResponse(BaseModel):
    voucher_name: str = ""
    claim_start_at: str
    claim_end_at: str
    valid_days_after_claim: int = 7
    reward_type: str = "discount"
    discount_type: str = "fixed_amount"
    discount_amount: float | None = None
    discount_percent: float | None = None
    max_discount_type: str = "set_amount"
    max_discount_amount: float | None = None
    min_spend_amount: float | None = None
    usage_limit: int | None = None
    per_buyer_limit: int = 1
    trigger_type: str = "follow_shop"
    display_type: str = "follow_reward"
    applicable_scope: str = "all_products"


class ShopeeFollowVoucherCreateRulesResponse(BaseModel):
    voucher_name_max_length: int = 100
    valid_days_after_claim: int = 7
    min_duration_minutes: int = 1
    max_duration_days: int = 180
    discount_types: list[str] = Field(default_factory=lambda: ["fixed_amount", "percent"])
    max_discount_types: list[str] = Field(default_factory=lambda: ["set_amount", "no_limit"])
    requires_usage_limit: bool = True


class ShopeeFollowVoucherCreateBootstrapResponse(BaseModel):
    meta: ShopeeVoucherCreateMetaResponse
    form: ShopeeFollowVoucherCreateFormResponse
    rules: ShopeeFollowVoucherCreateRulesResponse


class ShopeeFollowVoucherCampaignCreateRequest(BaseModel):
    voucher_type: str = "follow_voucher"
    voucher_name: str
    claim_start_at: str
    claim_end_at: str
    reward_type: str = "discount"
    discount_type: str = "fixed_amount"
    discount_amount: float | None = None
    discount_percent: float | None = None
    max_discount_type: str = "set_amount"
    max_discount_amount: float | None = None
    min_spend_amount: float
    usage_limit: int
    per_buyer_limit: int = 1


class ShopeeVoucherCodeCheckResponse(BaseModel):
    code_prefix: str
    code_suffix: str
    voucher_code: str
    available: bool
    message: str


class ShopeeProductVoucherEligibleProductResponse(BaseModel):
    listing_id: int
    variant_id: int | None = None
    variant_ids: list[int] = Field(default_factory=list)
    product_name: str
    variant_name: str = ""
    sku: str | None = None
    image_url: str | None = None
    category_key: str = "all"
    category_label: str = "全部"
    original_price: float
    price_range_label: str | None = None
    stock_available: int
    likes_count: int = 0
    conflict: bool = False


class ShopeeProductVoucherEligibleProductsResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[ShopeeProductVoucherEligibleProductResponse] = Field(default_factory=list)


class ShopeeProductVoucherItemPayload(BaseModel):
    listing_id: int
    variant_id: int | None = None


class ShopeeVoucherCampaignCreateRequest(BaseModel):
    voucher_type: str = "shop_voucher"
    voucher_name: str
    code_suffix: str = ""
    start_at: str
    end_at: str
    display_before_start: bool = False
    display_start_at: str | None = None
    reward_type: str = "discount"
    discount_type: str = "fixed_amount"
    discount_amount: float | None = None
    discount_percent: float | None = None
    max_discount_type: str = "set_amount"
    max_discount_amount: float | None = None
    min_spend_amount: float
    usage_limit: int
    per_buyer_limit: int = 1
    display_type: str = "all_pages"
    display_channels: list[str] = Field(default_factory=list)
    applicable_scope: str = ""
    live_scope: str = "all_live_sessions"
    video_scope: str = "all_videos"
    selected_products: list[ShopeeProductVoucherItemPayload] = Field(default_factory=list)


class ShopeeVoucherCampaignCreateResponse(BaseModel):
    campaign_id: int
    voucher_type: str
    status: str
    redirect_url: str = "/shopee/marketing/vouchers"


class ShopeeVoucherSummaryResponse(BaseModel):
    sales_amount: float = 0
    order_count: int = 0
    usage_rate: float = 0
    buyer_count: int = 0


class ShopeeVoucherTabResponse(BaseModel):
    key: str
    label: str
    count: int


class ShopeeVoucherRowResponse(BaseModel):
    id: int
    voucher_name: str
    voucher_code: str
    voucher_type: str
    voucher_type_label: str
    discount_type: str
    discount_label: str
    status: str
    status_label: str
    scope_label: str
    usage_limit: int
    used_count: int
    period: str


class ShopeeVoucherListPageResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[ShopeeVoucherRowResponse] = Field(default_factory=list)


class ShopeeVoucherListResponse(BaseModel):
    summary: ShopeeVoucherSummaryResponse
    tabs: list[ShopeeVoucherTabResponse] = Field(default_factory=list)
    list: ShopeeVoucherListPageResponse


class ShopeeVoucherDetailResponse(BaseModel):
    meta: ShopeeVoucherCreateMetaResponse
    form: ShopeeVoucherCreateFormResponse | ShopeeFollowVoucherCreateFormResponse
    selected_products: list[dict[str, Any]] = Field(default_factory=list)
    status: str
    status_label: str
    voucher_code: str
    used_count: int = 0
    sales_amount: float = 0
    order_count: int = 0
    buyer_count: int = 0
    created_at: datetime
    updated_at: datetime


class ShopeeVoucherOrdersInfoResponse(BaseModel):
    status_label: str
    voucher_name: str
    reward_type_label: str
    min_spend_text: str
    discount_text: str
    period: str
    voucher_code: str
    voucher_type_label: str
    applicable_scope_label: str
    display_setting_label: str
    usage_limit: int
    claimed_count: int
    used_count: int


class ShopeeVoucherOrderProductResponse(BaseModel):
    image_url: str | None = None
    product_name: str = ""


class ShopeeVoucherOrderRowResponse(BaseModel):
    id: int
    order_no: str
    products: list[ShopeeVoucherOrderProductResponse] = Field(default_factory=list)
    discount_amount: float
    total_amount: float
    created_at_text: str
    status_label: str


class ShopeeVoucherOrdersResponse(BaseModel):
    voucher: ShopeeVoucherOrdersInfoResponse
    page: int
    page_size: int
    total: int
    orders: list[ShopeeVoucherOrderRowResponse] = Field(default_factory=list)


class ShopeeShippingFeePromotionMetaResponse(BaseModel):
    run_id: int
    user_id: int
    read_only: bool
    current_tick: str
    currency: str = "RM"


class ShopeeShippingFeePromotionTierFormResponse(BaseModel):
    tier_index: int
    min_spend_amount: float | None = None
    fee_type: str = "fixed_fee"
    fixed_fee_amount: float | None = None


class ShopeeShippingFeePromotionCreateFormResponse(BaseModel):
    promotion_name: str = ""
    name_max_length: int = 20
    period_type: str = "no_limit"
    start_at: str
    end_at: str | None = None
    budget_type: str = "no_limit"
    budget_limit: float | None = None
    channels: list[str] = Field(default_factory=lambda: ["standard"])
    tiers: list[ShopeeShippingFeePromotionTierFormResponse] = Field(default_factory=list)


class ShopeeShippingFeePromotionChannelOptionResponse(BaseModel):
    key: str
    label: str
    enabled: bool = True


class ShopeeShippingFeePromotionRulesResponse(BaseModel):
    max_tier_count: int = 3
    min_tier_count: int = 1
    currency: str = "RM"
    min_budget_amount: float = 0.01


class ShopeeShippingFeePromotionCreateBootstrapResponse(BaseModel):
    meta: ShopeeShippingFeePromotionMetaResponse
    form: ShopeeShippingFeePromotionCreateFormResponse
    channels: list[ShopeeShippingFeePromotionChannelOptionResponse] = Field(default_factory=list)
    rules: ShopeeShippingFeePromotionRulesResponse


class ShopeeShippingFeePromotionTierPayload(BaseModel):
    tier_index: int
    min_spend_amount: float
    fee_type: str
    fixed_fee_amount: float | None = None


class ShopeeShippingFeePromotionCreateRequest(BaseModel):
    promotion_name: str
    period_type: str = "no_limit"
    start_at: str | None = None
    end_at: str | None = None
    budget_type: str = "no_limit"
    budget_limit: float | None = None
    channels: list[str] = Field(default_factory=list)
    tiers: list[ShopeeShippingFeePromotionTierPayload] = Field(default_factory=list)


class ShopeeShippingFeePromotionCreateResponse(BaseModel):
    id: int
    status: str
    message: str = "运费促销创建成功"


class ShopeeShippingFeePromotionTabResponse(BaseModel):
    key: str
    status: str
    count: int


class ShopeeShippingFeePromotionRowResponse(BaseModel):
    id: int
    promotion_name: str
    status: str
    status_label: str
    period: str
    budget_text: str
    budget_used_text: str
    channels_text: str
    tier_summary: str
    order_count: int = 0
    shipping_discount_amount: float = 0


class ShopeeShippingFeePromotionListPageResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[ShopeeShippingFeePromotionRowResponse] = Field(default_factory=list)


class ShopeeShippingFeePromotionListResponse(BaseModel):
    tabs: list[ShopeeShippingFeePromotionTabResponse] = Field(default_factory=list)
    list: ShopeeShippingFeePromotionListPageResponse


class ShopeeFlashSaleMetaResponse(BaseModel):
    run_id: int
    user_id: int
    market: str = "MY"
    read_only: bool = False
    current_tick: datetime
    current_game_time: str = ""


class ShopeeFlashSaleSlotResponse(BaseModel):
    slot_key: str
    display_time: str
    start_tick: datetime
    end_tick: datetime
    cross_day: bool
    product_limit: int
    used_product_count: int
    available_product_count: int
    selectable: bool
    disabled_reason: str | None = None


class ShopeeFlashSaleCategoryResponse(BaseModel):
    key: str
    label: str


class ShopeeFlashSaleCategoryRuleDisplayResponse(BaseModel):
    label: str
    value: str


class ShopeeFlashSaleCreateFormResponse(BaseModel):
    campaign_name: str = ""
    name_max_length: int = 60
    selected_slot: ShopeeFlashSaleSlotResponse | None = None


class ShopeeFlashSaleRulesResponse(BaseModel):
    product_limit_per_slot: int = 50
    activity_stock_range: list[int] = Field(default_factory=lambda: [5, 10000])
    discount_percent_range: list[int] = Field(default_factory=lambda: [5, 99])
    purchase_limit_range: list[int] = Field(default_factory=lambda: [1, 99])


class ShopeeFlashSaleProductRowResponse(BaseModel):
    listing_id: int
    variant_id: int | None = None
    product_id: int | None = None
    product_name: str
    variant_name: str = ""
    sku: str | None = None
    image_url: str | None = None
    category_key: str = "all"
    category_label: str = "全部"
    original_price: float
    price_range_label: str | None = None
    stock_available: int
    rating: float | None = None
    likes_count: int = 0
    orders_30d: int = 0
    ship_days: int | None = None
    is_preorder: bool = False
    conflict: bool = False
    conflict_reason: str | None = None
    suggested_flash_price: float | None = None
    flash_price: float | None = None
    activity_stock_limit: int | None = None
    purchase_limit_per_buyer: int | None = 1
    status: str = "active"
    variations: list[dict[str, Any]] = Field(default_factory=list)


class ShopeeFlashSaleCreateBootstrapResponse(BaseModel):
    meta: ShopeeFlashSaleMetaResponse
    form: ShopeeFlashSaleCreateFormResponse
    rules: ShopeeFlashSaleRulesResponse
    categories: list[ShopeeFlashSaleCategoryResponse] = Field(default_factory=list)
    category_rules: dict[str, list[ShopeeFlashSaleCategoryRuleDisplayResponse]] = Field(default_factory=dict)
    selected_products: list[ShopeeFlashSaleProductRowResponse] = Field(default_factory=list)


class ShopeeFlashSaleSlotsResponse(BaseModel):
    date: str
    slots: list[ShopeeFlashSaleSlotResponse] = Field(default_factory=list)


class ShopeeFlashSaleCategoryRulesResponse(BaseModel):
    categories: list[ShopeeFlashSaleCategoryResponse] = Field(default_factory=list)
    category_rules: dict[str, list[ShopeeFlashSaleCategoryRuleDisplayResponse]] = Field(default_factory=dict)


class ShopeeFlashSaleEligibleProductsResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[ShopeeFlashSaleProductRowResponse] = Field(default_factory=list)


class ShopeeFlashSaleItemPayload(BaseModel):
    listing_id: int
    variant_id: int | None = None
    flash_price: float
    activity_stock_limit: int
    purchase_limit_per_buyer: int = 1
    status: str = "active"


class ShopeeFlashSaleDraftUpsertRequest(BaseModel):
    draft_id: int | None = None
    campaign_name: str = ""
    slot_date: str | None = None
    slot_key: str | None = None
    items: list[ShopeeFlashSaleItemPayload] = Field(default_factory=list)


class ShopeeFlashSaleDraftUpsertResponse(BaseModel):
    draft_id: int
    saved_at: datetime


class ShopeeFlashSaleDraftDetailResponse(BaseModel):
    id: int
    campaign_name: str
    slot_date: str | None = None
    slot_key: str | None = None
    items: list[ShopeeFlashSaleProductRowResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ShopeeFlashSaleCampaignCreateRequest(BaseModel):
    draft_id: int | None = None
    campaign_name: str = ""
    slot_date: str
    slot_key: str
    items: list[ShopeeFlashSaleItemPayload] = Field(default_factory=list)


class ShopeeFlashSaleCampaignCreateResponse(BaseModel):
    campaign_id: int
    status: str
    redirect_url: str = "/shopee/marketing/flash-sale"


class ShopeeFlashSaleCampaignRowResponse(BaseModel):
    id: int
    slot_date: str
    display_time: str
    product_enabled_count: int
    product_limit: int
    reminder_count: int
    click_count: int
    status: str
    status_label: str
    enabled: bool
    actions: list[str] = Field(default_factory=list)


class ShopeeFlashSaleCampaignListResponse(BaseModel):
    page: int
    page_size: int
    total: int
    rows: list[ShopeeFlashSaleCampaignRowResponse] = Field(default_factory=list)


class ShopeeFlashSaleMetricResponse(BaseModel):
    key: str
    label: str
    value: str | int | float
    delta: float = 0.0


class ShopeeFlashSalePerformanceResponse(BaseModel):
    label: str
    range_text: str
    metrics: list[ShopeeFlashSaleMetricResponse] = Field(default_factory=list)


class ShopeeFlashSaleDataCampaignResponse(BaseModel):
    id: int
    name: str
    status: str
    status_label: str
    edit_period_label: str
    activity_period_label: str
    item_count: int


class ShopeeFlashSaleDataMetricsResponse(BaseModel):
    reminder_count: int = 0
    product_view_count: int = 0
    product_click_count: int = 0
    ctr: float = 0.0
    sales_amount: float = 0.0
    order_count: int = 0
    unit_count: int = 0
    buyer_count: int = 0


class ShopeeFlashSaleDataResponse(BaseModel):
    campaign: ShopeeFlashSaleDataCampaignResponse
    order_type: str
    metrics: ShopeeFlashSaleDataMetricsResponse


class ShopeeFlashSaleDataVariationResponse(BaseModel):
    campaign_item_id: int
    variant_id: int | None = None
    variation_name: str
    activity_stock: int
    flash_price: float
    sales_amount: float = 0.0
    order_count: int = 0
    unit_count: int = 0


class ShopeeFlashSaleDataProductResponse(BaseModel):
    listing_id: int
    item_id_label: str
    name: str
    image_url: str | None = None
    sales_amount: float = 0.0
    order_count: int = 0
    unit_count: int = 0
    variations: list[ShopeeFlashSaleDataVariationResponse] = Field(default_factory=list)


class ShopeeFlashSaleDataProductsResponse(BaseModel):
    items: list[ShopeeFlashSaleDataProductResponse] = Field(default_factory=list)


class ShopeeFlashSaleDataExportResponse(BaseModel):
    export_id: str
    status: str
    download_url: str | None = None


class ShopeeFlashSaleCampaignDetailResponse(BaseModel):
    id: int
    campaign_name: str
    slot_date: str
    slot_key: str
    display_time: str
    status: str
    status_label: str
    enabled: bool
    items: list[ShopeeFlashSaleProductRowResponse] = Field(default_factory=list)
    reminder_count: int
    click_count: int
    order_count: int
    sales_amount: float


class ShopeeFlashSaleToggleRequest(BaseModel):
    enabled: bool


class ShopeeDiscountDetailPerformanceResponse(BaseModel):
    total_sales_amount: float = 0.0
    total_orders_count: int = 0
    total_units_sold: int = 0
    total_buyers_count: int = 0


class ShopeeDiscountDetailPaginationResponse(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class ShopeeDiscountDetailItemRowResponse(BaseModel):
    item_id: int
    product_name: str
    image_url: str | None = None
    sku: str | None = None
    original_price: float
    discount_type: str
    discount_type_label: str
    discount_value: float
    final_price: float | None = None
    stock: int = 0


class ShopeeDiscountDetailItemListResponse(BaseModel):
    rows: list[ShopeeDiscountDetailItemRowResponse] = Field(default_factory=list)
    pagination: ShopeeDiscountDetailPaginationResponse


class ShopeeDiscountDetailDailyRowResponse(BaseModel):
    stat_date: str
    sales_amount: float
    orders_count: int
    units_sold: int
    buyers_count: int


class ShopeeDiscountDetailDailyListResponse(BaseModel):
    rows: list[ShopeeDiscountDetailDailyRowResponse] = Field(default_factory=list)
    pagination: ShopeeDiscountDetailPaginationResponse


class ShopeeDiscountDetailOrderRowResponse(BaseModel):
    order_id: int
    order_no: str
    buyer_name: str
    product_summary: str
    buyer_payment: float
    discount_percent: float | None = None
    type_bucket: str
    type_bucket_label: str
    created_at: str


class ShopeeDiscountDetailOrderListResponse(BaseModel):
    rows: list[ShopeeDiscountDetailOrderRowResponse] = Field(default_factory=list)
    pagination: ShopeeDiscountDetailPaginationResponse


class ShopeeDiscountDetailResponse(BaseModel):
    campaign_id: int
    campaign_name: str
    campaign_type: str
    campaign_type_label: str
    status: str
    status_label: str
    start_at: str | None = None
    end_at: str | None = None
    created_at: str
    market: str
    currency: str
    performance: ShopeeDiscountDetailPerformanceResponse
    items: ShopeeDiscountDetailItemListResponse
    daily_performance: ShopeeDiscountDetailDailyListResponse
    orders: ShopeeDiscountDetailOrderListResponse


class ShopeeDiscountDataMetricCardsResponse(BaseModel):
    sales_amount: float = 0.0
    units_sold: int = 0
    orders_count: int = 0
    buyers_count: int = 0
    items_sold: int = 0


class ShopeeDiscountDataTrendPointResponse(BaseModel):
    stat_date: str
    sales_amount: float = 0.0
    units_sold: int = 0
    orders_count: int = 0
    buyers_count: int = 0
    items_sold: int = 0


class ShopeeDiscountDataTrendResponse(BaseModel):
    rows: list[ShopeeDiscountDataTrendPointResponse] = Field(default_factory=list)
    monthly_rows: list[ShopeeDiscountDataTrendPointResponse] = Field(default_factory=list)


class ShopeeDiscountDataRankingRowResponse(BaseModel):
    rank: int
    campaign_item_id: int
    product_id: int | None = None
    product_name: str
    image_url: str | None = None
    variation_name: str | None = None
    original_price: float
    discount_label: str
    discounted_price: float | None = None
    units_sold: int = 0
    buyers_count: int = 0
    sales_amount: float = 0.0


class ShopeeDiscountDataRankingListResponse(BaseModel):
    rows: list[ShopeeDiscountDataRankingRowResponse] = Field(default_factory=list)
    pagination: ShopeeDiscountDetailPaginationResponse


class ShopeeDiscountAvailableYear(BaseModel):
    year: int
    label: str

class ShopeeDiscountDataResponse(BaseModel):
    campaign_id: int
    campaign_name: str
    campaign_type: str
    campaign_type_label: str
    status: str
    status_label: str
    start_at: str | None = None
    end_at: str | None = None
    market: str
    currency: str
    time_basis: str
    data_period_text: str = ""
    available_years: list[ShopeeDiscountAvailableYear] = Field(default_factory=list)
    selected_game_year: int = 0
    metric_cards: ShopeeDiscountDataMetricCardsResponse
    trend: ShopeeDiscountDataTrendResponse
    product_ranking: ShopeeDiscountDataRankingListResponse
    export_enabled: bool = True


class ShopeeDiscountDataExportRequest(BaseModel):
    time_basis: str = "order_time"
    export_type: str = "csv"


class ShopeeDiscountDataExportResponse(BaseModel):
    export_id: str
    status: str
    download_url: str | None = None
    expires_at: str | None = None


class ShopeeBundleTierResponse(BaseModel):
    tier_no: int
    buy_quantity: int
    discount_value: float


class ShopeeBundleCreateFormResponse(BaseModel):
    campaign_name: str = ""
    name_max_length: int = 25
    start_at: str | None = None
    end_at: str | None = None
    max_duration_days: int = 180
    bundle_type: str = "percent"
    purchase_limit: int | None = None
    tiers: list[ShopeeBundleTierResponse] = Field(default_factory=list)


class ShopeeBundleCreateRulesResponse(BaseModel):
    bundle_types: list[str] = Field(default_factory=lambda: ["percent", "fixed_amount", "bundle_price"])
    tier_count_limit: int = 10
    purchase_limit_range: list[int] = Field(default_factory=lambda: [1, 999])
    requires_at_least_one_product: bool = True


class ShopeeBundleCreateBootstrapResponse(BaseModel):
    meta: ShopeeDiscountCreateMetaResponse
    form: ShopeeBundleCreateFormResponse
    rules: ShopeeBundleCreateRulesResponse
    selected_products: list[ShopeeDiscountCreateProductRowResponse] = Field(default_factory=list)
    product_picker: ShopeeDiscountCreateProductPickerResponse
    draft: ShopeeDiscountCreateDraftSummaryResponse | None = None


class ShopeeBundleCampaignCreateRequest(BaseModel):
    campaign_type: str = "bundle"
    campaign_name: str
    start_at: str
    end_at: str
    bundle_type: str = "percent"
    purchase_limit: int | None = None
    tiers: list[ShopeeBundleTierResponse] = Field(default_factory=list)
    items: list[ShopeeDiscountDraftItemPayload] = Field(default_factory=list)


class ShopeeAddonCreateFormResponse(BaseModel):
    campaign_name: str = ""
    name_max_length: int = 25
    start_at: str | None = None
    end_at: str | None = None
    addon_purchase_limit: int | None = 1
    gift_min_spend: float | None = None


class ShopeeAddonCreateRulesResponse(BaseModel):
    promotion_types: list[str] = Field(default_factory=lambda: ["add_on", "gift"])
    main_product_limit: int = 100
    reward_product_limit: int = 100
    addon_purchase_limit_range: list[int] = Field(default_factory=lambda: [1, 99])
    min_duration_minutes: int = 60
    requires_at_least_one_main_product: bool = True
    requires_at_least_one_reward_product: bool = True


class ShopeeAddonProductRowResponse(BaseModel):
    listing_id: int
    variant_id: int | None = None
    product_id: int | None = None
    product_name: str
    variant_name: str = ""
    category: str = ""
    image_url: str | None = None
    sku: str | None = None
    original_price: float
    stock_available: int
    addon_price: float | None = None
    reward_qty: int = 1
    suggested_addon_price: float | None = None
    can_be_gift: bool = True
    conflict: bool = False
    conflict_reason: str | None = None


class ShopeeAddonCreateBootstrapResponse(BaseModel):
    meta: ShopeeDiscountCreateMetaResponse
    form: ShopeeAddonCreateFormResponse
    rules: ShopeeAddonCreateRulesResponse
    selected_main_products: list[ShopeeAddonProductRowResponse] = Field(default_factory=list)
    selected_reward_products: list[ShopeeAddonProductRowResponse] = Field(default_factory=list)
    product_picker: ShopeeDiscountCreateProductPickerResponse
    draft: ShopeeDiscountCreateDraftSummaryResponse | None = None


class ShopeeAddonEligibleProductsResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[ShopeeAddonProductRowResponse] = Field(default_factory=list)


class ShopeeAddonMainProductPayload(BaseModel):
    listing_id: int
    variant_id: int | None = None


class ShopeeAddonRewardProductPayload(BaseModel):
    listing_id: int
    variant_id: int | None = None
    addon_price: float | None = None
    reward_qty: int = 1


class ShopeeAddonDraftUpsertRequest(BaseModel):
    draft_id: int | None = None
    promotion_type: str = "add_on"
    campaign_name: str = ""
    start_at: str | None = None
    end_at: str | None = None
    addon_purchase_limit: int | None = None
    gift_min_spend: float | None = None
    main_products: list[ShopeeAddonMainProductPayload] = Field(default_factory=list)
    reward_products: list[ShopeeAddonRewardProductPayload] = Field(default_factory=list)


class ShopeeAddonDraftDetailResponse(BaseModel):
    id: int
    promotion_type: str
    campaign_name: str
    start_at: str | None = None
    end_at: str | None = None
    addon_purchase_limit: int | None = None
    gift_min_spend: float | None = None
    draft_status: str
    main_products: list[ShopeeAddonProductRowResponse] = Field(default_factory=list)
    reward_products: list[ShopeeAddonProductRowResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ShopeeAddonCampaignCreateRequest(BaseModel):
    promotion_type: str = "add_on"
    campaign_name: str
    start_at: str
    end_at: str
    addon_purchase_limit: int | None = None
    gift_min_spend: float | None = None
    main_products: list[ShopeeAddonMainProductPayload] = Field(default_factory=list)
    reward_products: list[ShopeeAddonRewardProductPayload] = Field(default_factory=list)


class ShopeeAddonCampaignCreateResponse(BaseModel):
    campaign_id: int
    campaign_name: str
    promotion_type: str
    campaign_status: str
    main_product_count: int
    reward_product_count: int
    start_at: datetime
    end_at: datetime


class ShopeeAddonCampaignDetailResponse(BaseModel):
    campaign_id: int
    campaign_name: str
    promotion_type: str
    promotion_type_label: str
    campaign_status: str
    status_label: str
    start_at: str | None = None
    end_at: str | None = None
    addon_purchase_limit: int | None = None
    gift_min_spend: float | None = None
    main_products: list[ShopeeAddonProductRowResponse] = Field(default_factory=list)
    reward_products: list[ShopeeAddonProductRowResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ShopeeAddonOrderItemResponse(BaseModel):
    id: str
    type: str
    imageUrl: str | None = None
    name: str
    sku: str | None = None
    variation: str = ""
    priceCurrent: float
    priceOriginal: float | None = None
    qty: int


class ShopeeAddonOrderRowResponse(BaseModel):
    id: str
    status: str
    subtotalCurrent: float
    subtotalOriginal: float | None = None
    items: list[ShopeeAddonOrderItemResponse] = Field(default_factory=list)


class ShopeeAddonOrdersResponse(BaseModel):
    campaign_id: int
    campaign_name: str
    promotion_type: str
    promotion_type_label: str
    status_label: str
    start_at: str | None = None
    end_at: str | None = None
    addon_purchase_limit: int | None = None
    gift_min_spend: float | None = None
    orders: list[ShopeeAddonOrderRowResponse] = Field(default_factory=list)


class ShopeeBundleOrderItemResponse(BaseModel):
    id: str
    imageUrl: str | None = None
    name: str
    sku: str | None = None
    variation: str = ""
    priceCurrent: float
    qty: int


class ShopeeBundleOrderRowResponse(BaseModel):
    id: str
    status: str
    subtotalCurrent: float
    subtotalOriginal: float | None = None
    items: list[ShopeeBundleOrderItemResponse] = Field(default_factory=list)


class ShopeeBundleDataRowResponse(BaseModel):
    date: str
    sales: float = 0.0
    orders: int = 0
    bundles: int = 0
    units: int = 0
    buyers: int = 0
    salesPerBuyer: float = 0.0


class ShopeeBundleMetricCardsResponse(BaseModel):
    sales: float = 0.0
    orders: int = 0
    bundles: int = 0
    units: int = 0
    buyers: int = 0
    salesPerBuyer: float = 0.0


class ShopeeBundleOrdersResponse(BaseModel):
    campaign_id: int
    campaign_name: str
    status_label: str
    start_at: str | None = None
    end_at: str | None = None
    purchase_limit: int | None = None
    bundle_type_label: str
    bundle_rule_text: str
    data_period_text: str
    order_count: int = 0
    metric_cards: ShopeeBundleMetricCardsResponse
    orders: list[ShopeeBundleOrderRowResponse] = Field(default_factory=list)
    data_rows: list[ShopeeBundleDataRowResponse] = Field(default_factory=list)


class ShopeeListingRowResponse(BaseModel):
    id: int
    title: str
    category: str | None
    sku_code: str | None
    model_id: str | None
    cover_url: str | None
    sales_count: int
    price: int
    original_price: int
    stock_available: int
    quality_status: str
    quality_total_score: int | None = None
    quality_scored_at: datetime | None = None
    quality_score_version: str | None = None
    status: str
    created_at: datetime
    variants: list["ShopeeListingVariantPreviewResponse"] = Field(default_factory=list)


class ShopeeListingQualityDetailResponse(BaseModel):
    listing_id: int
    score_version: str
    provider: str
    text_model: str | None
    vision_model: str | None
    summary: str | None = None
    total_score: int
    quality_status: str
    rule_score: int
    vision_score: int
    text_score: int
    consistency_score: int
    scoring_dimensions: dict[str, list[str]]
    reasons: list[str]
    suggestions: list[str]
    image_feedback: list["ShopeeListingQualityImageFeedbackItem"] = Field(default_factory=list)
    quality_scored_at: datetime


class ShopeeListingQualityRecomputeResponse(BaseModel):
    listing_id: int
    total_score: int
    quality_status: str
    score_version: str
    scored_at: datetime


class ShopeeListingQualityImageFeedbackItem(BaseModel):
    image_ref: str
    image_label: str
    score: int | None = None
    good: str = ""
    bad: str = ""
    suggestion: str = ""


class ShopeeListingVariantPreviewResponse(BaseModel):
    id: int
    option_value: str
    option_note: str | None
    price: int
    stock: int
    sales_count: int
    oversell_limit: int
    oversell_used: int
    sku: str | None
    image_url: str | None


class ShopeeListingsCountsResponse(BaseModel):
    all: int
    live: int
    violation: int
    review: int
    unpublished: int


class ShopeeListingsListResponse(BaseModel):
    counts: ShopeeListingsCountsResponse
    page: int
    page_size: int
    total: int
    listings: list[ShopeeListingRowResponse]


ShopeeListingRowResponse.model_rebuild()


class ShopeeProductsBatchActionRequest(BaseModel):
    listing_ids: list[int]
    action: str


class ShopeeProductsBatchActionResponse(BaseModel):
    success: bool
    affected: int
    action: str


class ShopeeCreateListingResponse(BaseModel):
    id: int
    title: str
    cover_url: str | None


class ShopeeListingEditVariantResponse(BaseModel):
    id: int
    variant_name: str | None
    option_value: str
    option_note: str | None
    price: int
    stock: int
    sku: str | None
    gtin: str | None
    item_without_gtin: bool
    weight_kg: float | None
    parcel_length_cm: int | None
    parcel_width_cm: int | None
    parcel_height_cm: int | None
    image_url: str | None
    sort_order: int


class ShopeeListingEditWholesaleTierResponse(BaseModel):
    id: int
    tier_no: int
    min_qty: int | None
    max_qty: int | None
    unit_price: int | None


class ShopeeListingDetailResponse(BaseModel):
    id: int
    product_id: int | None
    title: str
    category_id: int | None
    category: str | None
    gtin: str | None
    description: str | None
    video_url: str | None
    cover_url: str | None
    price: int
    stock_available: int
    min_purchase_qty: int
    max_purchase_qty: int | None
    max_purchase_mode: str
    max_purchase_period_start_date: date | None
    max_purchase_period_end_date: date | None
    max_purchase_period_qty: int | None
    max_purchase_period_days: int | None
    max_purchase_period_model: str | None
    weight_kg: float | None
    parcel_length_cm: int | None
    parcel_width_cm: int | None
    parcel_height_cm: int | None
    shipping_variation_dimension_enabled: bool
    shipping_standard_bulk: bool
    shipping_standard: bool
    shipping_express: bool
    preorder_enabled: bool
    insurance_enabled: bool
    condition_label: str | None
    schedule_publish_at: datetime | None
    parent_sku: str | None
    variants: list[ShopeeListingEditVariantResponse]
    wholesale_tiers: list[ShopeeListingEditWholesaleTierResponse]


class ShopeeEditBootstrapResponse(BaseModel):
    draft: "ShopeeDraftDetailResponse"
    listing: ShopeeListingDetailResponse


class ShopeeDraftImageResponse(BaseModel):
    id: int
    image_url: str
    sort_order: int
    is_cover: bool


class ShopeeDraftDetailResponse(BaseModel):
    id: int
    title: str
    category_id: int | None
    category: str | None
    gtin: str | None
    description: str | None
    video_url: str | None
    cover_url: str | None
    image_count_11: int
    image_count_34: int
    images_11: list[ShopeeDraftImageResponse]
    images_34: list[ShopeeDraftImageResponse]
    specs: list[dict[str, str | None]]
    created_at: datetime
    updated_at: datetime


class ShopeeDraftPublishResponse(BaseModel):
    draft_id: int
    listing_id: int
    status: str


class ShopeeWarehouseLinkProductRowResponse(BaseModel):
    product_id: int
    product_name: str
    available_qty: int
    reserved_qty: int
    backorder_qty: int
    inbound_lot_count: int


class ShopeeWarehouseLinkProductsResponse(BaseModel):
    page: int
    page_size: int
    total: int
    rows: list[ShopeeWarehouseLinkProductRowResponse]


class ShopeeDraftUpdatePayload(BaseModel):
    title: str
    category_id: int | None = None
    category: str | None = None
    gtin: str | None = None
    description: str | None = None
    spec_values: dict[str, str] | None = None


ShopeeEditBootstrapResponse.model_rebuild()


class ShopeeDraftSpecValueResponse(BaseModel):
    attr_key: str
    attr_label: str
    attr_value: str | None


class ShopeeSpecTemplateFieldResponse(BaseModel):
    attr_key: str
    attr_label: str
    input_type: str
    options: list[str]
    is_required: bool
    sort_order: int


class ShopeeSpecTemplateResponse(BaseModel):
    category_id: int
    category_path: str
    fields: list[ShopeeSpecTemplateFieldResponse]


class ShopeeCategoryNodeResponse(BaseModel):
    id: int
    name: str
    level: int
    path: str
    children: list[dict]


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


def _get_owned_order_readable_run_or_404(db: Session, run_id: int, user_id: int) -> GameRun:
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


def _default_auto_reply_values(reply_type: str) -> dict[str, Any]:
    if reply_type == "off_work":
        return {
            "reply_type": "off_work",
            "enabled": False,
            "message": OFF_WORK_AUTO_REPLY_MESSAGE,
            "work_time_enabled": True,
            "work_start_time": "09:00",
            "work_end_time": "18:00",
            "timezone": "game_time",
            "trigger_interval_minutes": 1440,
            "trigger_once_per_game_day": True,
            "sent_count": 0,
            "last_sent_game_at": None,
        }
    return {
        "reply_type": "default",
        "enabled": False,
        "message": DEFAULT_AUTO_REPLY_MESSAGE,
        "work_time_enabled": False,
        "work_start_time": None,
        "work_end_time": None,
        "timezone": "game_time",
        "trigger_interval_minutes": 1440,
        "trigger_once_per_game_day": False,
        "sent_count": 0,
        "last_sent_game_at": None,
    }


def _resolve_auto_reply_status(*, enabled: bool, message: str) -> str:
    normalized_message = (message or "").strip()
    if not normalized_message or len(normalized_message) > AUTO_REPLY_MAX_MESSAGE_LENGTH:
        return "invalid"
    return "enabled" if enabled else "disabled"


def _enforce_shopee_customer_service_rate_limit(*, user_id: int, llm: bool = False) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:customer_service:{'llm' if llm else 'api'}:user:{user_id}",
        limit=REDIS_RATE_LIMIT_SHOPEE_CUSTOMER_SERVICE_LLM_PER_MIN if llm else REDIS_RATE_LIMIT_SHOPEE_CUSTOMER_SERVICE_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"客服请求过于频繁，请在 {reset_at} 后重试")


def _customer_service_list_cache_key(*, run_id: int, user_id: int, status_filter: str | None, page: int, page_size: int) -> str:
    digest = hashlib.md5(json.dumps({"status": status_filter, "page": page, "page_size": page_size}, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return f"{REDIS_PREFIX}:shopee:customer_service:conversations:{run_id}:{user_id}:{digest}"


def _customer_service_detail_cache_key(*, conversation_id: int) -> str:
    return f"{REDIS_PREFIX}:shopee:customer_service:conversation:{conversation_id}"


def _invalidate_customer_service_cache(*, run_id: int, user_id: int, conversation_id: int | None = None) -> None:
    cache_delete_prefix(f"{REDIS_PREFIX}:shopee:customer_service:conversations:{run_id}:{user_id}:")
    if conversation_id is not None:
        cache_delete_prefix(_customer_service_detail_cache_key(conversation_id=conversation_id))


def _safe_json_loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return default


def _ensure_customer_service_scenario(db: Session) -> ShopeeCustomerServiceScenario:
    row = db.query(ShopeeCustomerServiceScenario).filter(ShopeeCustomerServiceScenario.scenario_code == CUSTOMER_SERVICE_SCENARIO_PRODUCT_DETAIL).first()
    if row is not None:
        return row
    row = ShopeeCustomerServiceScenario(
        scenario_code=CUSTOMER_SERVICE_SCENARIO_PRODUCT_DETAIL,
        name="商品细节追问",
        trigger_type="product",
        enabled=True,
        base_probability=0.35,
        cooldown_game_hours=48,
        buyer_persona_prompt="你是 Shopee 买家，准备下单前会礼貌追问商品细节；回复要像真实买家，可以先表达理解、犹豫、认可或补充个人偏好。",
        scenario_prompt="只围绕当前商品的标题、图片、规格、材质、颜色、尺码、库存、发货信息追问；可用生活化语言复述客服解释并逐步澄清需求，不编造商品事实，不暴露内部评分。",
        rubric_json=json.dumps({"响应完整度": 30, "商品准确性": 25, "服务态度": 20, "购买引导": 15, "平台合规": 10}, ensure_ascii=False),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _get_customer_service_model_setting(db: Session, *, run_id: int, user_id: int) -> ShopeeCustomerServiceModelSetting | None:
    row = db.query(ShopeeCustomerServiceModelSetting).filter(ShopeeCustomerServiceModelSetting.run_id == run_id, ShopeeCustomerServiceModelSetting.user_id == user_id).first()
    if row is not None:
        return row
    row = db.query(ShopeeCustomerServiceModelSetting).filter(ShopeeCustomerServiceModelSetting.run_id.is_(None), ShopeeCustomerServiceModelSetting.user_id.is_(None)).first()
    if row is not None:
        return row
    env_enabled = os.getenv("SHOPEE_CUSTOMER_SERVICE_LLM_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    return ShopeeCustomerServiceModelSetting(
        run_id=run_id,
        user_id=user_id,
        provider=os.getenv("SHOPEE_CUSTOMER_SERVICE_LLM_PROVIDER", "lm_studio"),
        model_name=os.getenv("SHOPEE_CUSTOMER_SERVICE_LLM_MODEL", "local-model"),
        base_url=os.getenv("SHOPEE_CUSTOMER_SERVICE_LLM_BASE_URL", "http://localhost:1234/v1"),
        api_key_ref=os.getenv("SHOPEE_CUSTOMER_SERVICE_LLM_API_KEY") or None,
        temperature=float(os.getenv("SHOPEE_CUSTOMER_SERVICE_LLM_TEMPERATURE", "0.7")),
        max_tokens=int(os.getenv("SHOPEE_CUSTOMER_SERVICE_LLM_MAX_TOKENS", "300")),
        enabled=env_enabled,
    )


def _serialize_customer_service_model_setting(row: ShopeeCustomerServiceModelSetting | None) -> ShopeeCustomerServiceModelSettingResponse:
    if row is None:
        return ShopeeCustomerServiceModelSettingResponse()
    return ShopeeCustomerServiceModelSettingResponse(
        id=row.id,
        provider=row.provider or "lm_studio",
        model_name=row.model_name or "local-model",
        base_url=row.base_url or "http://localhost:1234/v1",
        temperature=float(row.temperature),
        max_tokens=int(row.max_tokens),
        enabled=bool(row.enabled),
        api_key_configured=bool(row.api_key_ref),
    )


def _customer_service_model_ready(row: ShopeeCustomerServiceModelSetting | None) -> tuple[bool, str | None]:
    if row is None or not row.enabled:
        return False, "请先启用客服模型配置（LM Studio 默认 http://localhost:1234/v1）。"
    if not (row.model_name or "").strip():
        return False, "客服模型名称不能为空。"
    if not (row.base_url or "").strip():
        return False, "客服模型 Base URL 不能为空。"
    return True, None


def _build_customer_service_listing_context(listing: ShopeeListing) -> dict[str, Any]:
    images = sorted(listing.images, key=lambda item: (not item.is_cover, item.sort_order, item.id))
    specs = sorted(listing.specs, key=lambda item: item.id)
    variants = sorted(listing.variants, key=lambda item: (item.sort_order, item.id))
    latest_score = next((score for score in sorted(listing.quality_scores, key=lambda item: item.created_at or datetime.min, reverse=True) if score.is_latest), None)
    reasons = _safe_json_loads(latest_score.reasons_json if latest_score else None, [])
    suggestions = _safe_json_loads(latest_score.suggestions_json if latest_score else None, [])
    return {
        "id": listing.id,
        "title": listing.title,
        "category": listing.category,
        "description": listing.description or "",
        "description_summary": (listing.description or "")[:160],
        "price": listing.price,
        "original_price": listing.original_price,
        "stock_available": listing.stock_available,
        "cover_url": listing.cover_url or (images[0].image_url if images else None),
        "image_urls": [image.image_url for image in images],
        "image_count": len(images),
        "specs": [{"key": spec.attr_key, "label": spec.attr_label, "value": spec.attr_value} for spec in specs],
        "variants": [{"name": item.variant_name, "option": item.option_value, "price": item.price, "stock": item.stock, "image_url": item.image_url} for item in variants],
        "quality_total_score": listing.quality_total_score if listing.quality_total_score is not None else (latest_score.total_score if latest_score else None),
        "quality_status": listing.quality_status,
        "quality_reasons": reasons,
        "quality_suggestions": suggestions,
    }


def _serialize_customer_service_listing(context: dict[str, Any] | None) -> ShopeeCustomerServiceListingResponse | None:
    if not context:
        return None
    return ShopeeCustomerServiceListingResponse(
        id=context.get("id"),
        title=str(context.get("title") or ""),
        image_url=context.get("cover_url"),
        price=context.get("price"),
        original_price=context.get("original_price"),
        stock_available=context.get("stock_available"),
        quality_total_score=context.get("quality_total_score"),
        specs=context.get("specs") if isinstance(context.get("specs"), list) else [],
        variants=context.get("variants") if isinstance(context.get("variants"), list) else [],
        description_summary=str(context.get("description_summary") or ""),
    )


def _call_customer_service_llm(setting: ShopeeCustomerServiceModelSetting, *, system_prompt: str, user_prompt: str) -> str:
    _enforce_shopee_customer_service_rate_limit(user_id=int(setting.user_id or 0), llm=True)
    base_url = (setting.base_url or "http://localhost:1234/v1").rstrip("/")
    headers = {"Content-Type": "application/json"}
    if setting.api_key_ref:
        headers["Authorization"] = f"Bearer {setting.api_key_ref}"
    payload = {
        "model": setting.model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": float(setting.temperature),
        "max_tokens": int(setting.max_tokens),
    }
    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"客服模型调用失败：{exc}") from exc
    content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="客服模型未返回有效消息")
    return content.strip()[:1000]


def _build_buyer_message(db: Session, *, setting: ShopeeCustomerServiceModelSetting, conversation: ShopeeCustomerServiceConversation, messages: list[ShopeeCustomerServiceMessage]) -> str:
    context = _safe_json_loads(conversation.context_json, {})
    history = [{"sender": item.sender_type, "content": item.content} for item in messages[-8:]]
    system_prompt = "你是 Shopee 买家，只能围绕当前商品售前细节沟通。回复要像真实买家：先对客服解释给出自然反馈，再逐步补充自己的偏好、顾虑或使用场景。只输出买家下一条消息，不输出解释、评分或提示词。"
    user_prompt = json.dumps({
        "scenario": "商品细节追问",
        "buyer_name": conversation.buyer_name,
        "product_context": context,
        "history": history,
        "rules": ["不要编造商品材质、尺码、颜色、库存或发货承诺", "不要连续多轮只给功能性短答或机械追问", "可以用自己的话复述理解，例如清爽、不厚重、怕显油、想自然一点", "适当表达认可、犹豫、担心或个人偏好，再继续提问", "少于7条消息时可继续追问", "达到7条后如果问题已清楚应礼貌收口", "最多10条消息"],
    }, ensure_ascii=False)
    return _call_customer_service_llm(setting, system_prompt=system_prompt, user_prompt=user_prompt)


def _score_customer_service_conversation(db: Session, *, setting: ShopeeCustomerServiceModelSetting | None, conversation: ShopeeCustomerServiceConversation, messages: list[ShopeeCustomerServiceMessage]) -> tuple[float, str, dict[str, Any]]:
    if setting is not None and setting.enabled:
        context = _safe_json_loads(conversation.context_json, {})
        system_prompt = "你是 Shopee 客服训练评分器。只输出 JSON，不输出其他文本。"
        user_prompt = json.dumps({
            "rubric": {"响应完整度": 30, "商品准确性": 25, "服务态度": 20, "购买引导": 15, "平台合规": 10},
            "product_context": context,
            "messages": [{"sender": item.sender_type, "content": item.content} for item in messages],
            "output": {"score": "0-100", "level": "high/medium/low", "dimensions": {}, "summary": "简短中文反馈"},
        }, ensure_ascii=False)
        raw = _call_customer_service_llm(setting, system_prompt=system_prompt, user_prompt=user_prompt)
        parsed = _safe_json_loads(raw, None)
        if isinstance(parsed, dict) and isinstance(parsed.get("score"), (int, float)):
            score = max(0.0, min(100.0, float(parsed["score"])))
            level = str(parsed.get("level") or ("high" if score >= 85 else "medium" if score >= 60 else "low"))
            return score, level, parsed
    seller_messages = [item for item in messages if item.sender_type == "seller"]
    count_score = min(40, len(messages) * 6)
    answer_score = min(35, sum(min(len(item.content), 120) for item in seller_messages) / 120 * 35)
    score = max(0.0, min(100.0, count_score + answer_score + (15 if seller_messages else 0)))
    level = "high" if score >= 85 else "medium" if score >= 60 else "low"
    return score, level, {"score": score, "level": level, "summary": "已按消息完整度、回复长度和会话轮次生成规则评分。"}


def _select_customer_service_buyer(db: Session) -> SimBuyerProfile | None:
    return db.query(SimBuyerProfile).filter(SimBuyerProfile.is_active == True).order_by(func.rand()).first()


def _serialize_customer_service_message(row: ShopeeCustomerServiceMessage) -> ShopeeCustomerServiceMessageResponse:
    return ShopeeCustomerServiceMessageResponse(id=row.id, sender_type=row.sender_type, message_type=row.message_type, content=row.content, sent_game_at=row.sent_game_at)


def _serialize_customer_service_summary(row: ShopeeCustomerServiceConversation) -> ShopeeCustomerServiceConversationSummaryResponse:
    messages = sorted(row.messages, key=lambda item: (item.sent_game_at, item.id))
    last_message = messages[-1] if messages else None
    context = _safe_json_loads(row.context_json, {})
    return ShopeeCustomerServiceConversationSummaryResponse(
        id=row.id,
        scenario_code=row.scenario_code,
        scenario_name=row.scenario.name if row.scenario else "商品细节追问",
        buyer_name=row.buyer_name,
        status=row.status,
        last_message=last_message.content if last_message else "",
        last_message_game_at=last_message.sent_game_at if last_message else None,
        listing=_serialize_customer_service_listing(context),
        unread_count=sum(1 for item in messages if item.sender_type == "buyer" and row.status in CUSTOMER_SERVICE_OPEN_STATUSES),
        message_count=len(messages),
    )


def _serialize_customer_service_detail(db: Session, *, run: GameRun, user_id: int, row: ShopeeCustomerServiceConversation) -> ShopeeCustomerServiceConversationDetailResponse:
    messages = sorted(row.messages, key=lambda item: (item.sent_game_at, item.id))
    context = _safe_json_loads(row.context_json, {})
    score_detail = _safe_json_loads(row.score_detail_json, None) if row.score_detail_json else None
    setting = _get_customer_service_model_setting(db, run_id=run.id, user_id=user_id)
    ready, message = _customer_service_model_ready(setting)
    return ShopeeCustomerServiceConversationDetailResponse(
        id=row.id,
        scenario_code=row.scenario_code,
        scenario_name=row.scenario.name if row.scenario else "商品细节追问",
        buyer_name=row.buyer_name,
        status=row.status,
        trigger_reason=row.trigger_reason,
        listing=_serialize_customer_service_listing(context),
        messages=[_serialize_customer_service_message(item) for item in messages],
        satisfaction_score=row.satisfaction_score,
        satisfaction_level=row.satisfaction_level,
        score_detail=score_detail,
        can_send=run.status == "running" and row.status in CUSTOMER_SERVICE_OPEN_STATUSES and len(messages) < CUSTOMER_SERVICE_MAX_MESSAGES,
        can_resolve=run.status == "running" and row.status in CUSTOMER_SERVICE_OPEN_STATUSES,
        model_ready=ready,
        model_message=message,
    )


def _serialize_auto_reply_setting(row: ShopeeAutoReplySetting | None, *, reply_type: str) -> ShopeeAutoReplySettingResponse:
    values = _default_auto_reply_values(reply_type)
    if row is not None:
        values.update(
            {
                "id": row.id,
                "reply_type": row.reply_type,
                "enabled": bool(row.enabled),
                "message": row.message or "",
                "work_time_enabled": bool(row.work_time_enabled),
                "work_start_time": row.work_start_time,
                "work_end_time": row.work_end_time,
                "timezone": row.timezone or "game_time",
                "trigger_interval_minutes": row.trigger_interval_minutes,
                "trigger_once_per_game_day": bool(row.trigger_once_per_game_day),
                "sent_count": row.sent_count,
                "last_sent_game_at": row.last_sent_game_at,
            }
        )
    values["status"] = _resolve_auto_reply_status(enabled=values["enabled"], message=values["message"])
    return ShopeeAutoReplySettingResponse(**values)


def _ensure_auto_reply_settings(db: Session, *, run: GameRun, user_id: int) -> dict[str, ShopeeAutoReplySetting]:
    rows = (
        db.query(ShopeeAutoReplySetting)
        .filter(
            ShopeeAutoReplySetting.run_id == run.id,
            ShopeeAutoReplySetting.user_id == user_id,
            ShopeeAutoReplySetting.reply_type.in_(AUTO_REPLY_TYPES),
        )
        .all()
    )
    by_type = {row.reply_type: row for row in rows}
    if run.status != "running":
        return by_type

    created = False
    for reply_type in AUTO_REPLY_TYPES:
        if reply_type in by_type:
            continue
        values = _default_auto_reply_values(reply_type)
        row = ShopeeAutoReplySetting(
            run_id=run.id,
            user_id=user_id,
            reply_type=reply_type,
            enabled=values["enabled"],
            message=values["message"],
            work_time_enabled=values["work_time_enabled"],
            work_start_time=values["work_start_time"],
            work_end_time=values["work_end_time"],
            timezone=values["timezone"],
            trigger_interval_minutes=values["trigger_interval_minutes"],
            trigger_once_per_game_day=values["trigger_once_per_game_day"],
        )
        db.add(row)
        by_type[reply_type] = row
        created = True
    if created:
        db.commit()
        for row in by_type.values():
            db.refresh(row)
    return by_type


def _build_auto_reply_settings_response(db: Session, *, run: GameRun, user_id: int) -> ShopeeAutoReplySettingsResponse:
    settings = _ensure_auto_reply_settings(db, run=run, user_id=user_id)
    return ShopeeAutoReplySettingsResponse(
        default_reply=_serialize_auto_reply_setting(settings.get("default"), reply_type="default"),
        off_work_reply=_serialize_auto_reply_setting(settings.get("off_work"), reply_type="off_work"),
        rules=ShopeeAutoReplyRulesResponse(),
    )


def _is_valid_hhmm(value: str) -> bool:
    if not re.fullmatch(r"\d{2}:\d{2}", value):
        return False
    hour, minute = value.split(":")
    return 0 <= int(hour) <= 23 and 0 <= int(minute) <= 59


def _validate_auto_reply_update(reply_type: str, payload: ShopeeAutoReplyUpdateRequest, row: ShopeeAutoReplySetting) -> tuple[bool, str, str | None, str | None]:
    if reply_type not in AUTO_REPLY_TYPES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="自动回复类型不存在")

    next_enabled = bool(row.enabled) if payload.enabled is None else payload.enabled
    next_message = row.message if payload.message is None else payload.message.strip()
    if not next_message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="自动回复内容不能为空")
    if len(next_message) > AUTO_REPLY_MAX_MESSAGE_LENGTH:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"自动回复内容不能超过 {AUTO_REPLY_MAX_MESSAGE_LENGTH} 字")
    if next_enabled and not next_message.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开启自动回复前必须填写回复内容")

    next_start_time = row.work_start_time
    next_end_time = row.work_end_time
    if reply_type == "off_work":
        if payload.work_start_time is not None:
            next_start_time = payload.work_start_time.strip()
        if payload.work_end_time is not None:
            next_end_time = payload.work_end_time.strip()
        if next_start_time is not None and not _is_valid_hhmm(next_start_time):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="工作开始时间格式必须为 HH:mm")
        if next_end_time is not None and not _is_valid_hhmm(next_end_time):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="工作结束时间格式必须为 HH:mm")
        if next_start_time and next_end_time and next_start_time == next_end_time:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="工作开始时间不能等于结束时间")
    else:
        next_start_time = None
        next_end_time = None

    return next_enabled, next_message, next_start_time, next_end_time


DEFAULT_QUICK_REPLY_MESSAGES = [
    "商品有现货哦",
    "谢谢",
    "感谢您的支持！我们会尽快为您发货",
    "我们已经发货了，您可以查看订单页面获取物流状态",
    "亲爱的顾客，您订购的商品正在运输途中，感谢您的购买。",
    "本店经常有促销活动，请关注我们的店铺以获取最新优惠",
    "这是给您的专属特殊折扣",
    "抱歉，我们目前无法降低该商品的价格了",
    "如果您喜欢这款商品，请点击购买，我们会立即为您安排发货",
    "请告诉我您需要的尺寸或重量，以便我们推荐合适的型号",
    "麻烦提供一下您的订单号，以便我们核查详细信息",
    "您可以申请取消订单/退款/退货，我们会按照流程尽快处理",
    "亲爱的顾客，对于给您带来的不便我们深表歉意，请您先提供破损照片。",
]


def _parse_quick_reply_tags(tags_json: str | None) -> list[str]:
    if not tags_json:
        return []
    try:
        parsed = json.loads(tags_json)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item).strip()]


def _serialize_quick_reply_message(row: ShopeeQuickReplyMessage) -> ShopeeQuickReplyMessageResponse:
    return ShopeeQuickReplyMessageResponse(
        id=row.id,
        message=row.message,
        tags=_parse_quick_reply_tags(row.tags_json),
        sort_order=row.sort_order,
    )


def _serialize_quick_reply_group(row: ShopeeQuickReplyGroup) -> ShopeeQuickReplyGroupResponse:
    messages = sorted(row.messages, key=lambda item: (item.sort_order, item.id))
    return ShopeeQuickReplyGroupResponse(
        id=row.id,
        group_name=row.group_name,
        enabled=bool(row.enabled),
        sort_order=row.sort_order,
        message_count=row.message_count,
        messages=[_serialize_quick_reply_message(item) for item in messages],
    )


def _ensure_quick_reply_data(db: Session, *, run: GameRun, user_id: int) -> tuple[ShopeeQuickReplyPreference | None, list[ShopeeQuickReplyGroup]]:
    preference = (
        db.query(ShopeeQuickReplyPreference)
        .filter(ShopeeQuickReplyPreference.run_id == run.id, ShopeeQuickReplyPreference.user_id == user_id)
        .first()
    )
    groups = (
        db.query(ShopeeQuickReplyGroup)
        .options(selectinload(ShopeeQuickReplyGroup.messages))
        .filter(ShopeeQuickReplyGroup.run_id == run.id, ShopeeQuickReplyGroup.user_id == user_id)
        .order_by(ShopeeQuickReplyGroup.sort_order.asc(), ShopeeQuickReplyGroup.id.asc())
        .all()
    )
    if run.status != "running":
        return preference, groups

    created = False
    if preference is None:
        preference = ShopeeQuickReplyPreference(run_id=run.id, user_id=user_id, auto_hint_enabled=True)
        db.add(preference)
        created = True
    if not groups:
        group = ShopeeQuickReplyGroup(run_id=run.id, user_id=user_id, group_name="默认分组", enabled=True, sort_order=1, message_count=len(DEFAULT_QUICK_REPLY_MESSAGES))
        db.add(group)
        db.flush()
        for index, message in enumerate(DEFAULT_QUICK_REPLY_MESSAGES, start=1):
            db.add(
                ShopeeQuickReplyMessage(
                    group_id=group.id,
                    run_id=run.id,
                    user_id=user_id,
                    message=message,
                    tags_json="[]",
                    sort_order=index,
                )
            )
        created = True
    if created:
        db.commit()
        preference = (
            db.query(ShopeeQuickReplyPreference)
            .filter(ShopeeQuickReplyPreference.run_id == run.id, ShopeeQuickReplyPreference.user_id == user_id)
            .first()
        )
        groups = (
            db.query(ShopeeQuickReplyGroup)
            .options(selectinload(ShopeeQuickReplyGroup.messages))
            .filter(ShopeeQuickReplyGroup.run_id == run.id, ShopeeQuickReplyGroup.user_id == user_id)
            .order_by(ShopeeQuickReplyGroup.sort_order.asc(), ShopeeQuickReplyGroup.id.asc())
            .all()
        )
    return preference, groups


def _build_quick_reply_list_response(db: Session, *, run: GameRun, user_id: int) -> ShopeeQuickReplyListResponse:
    preference, groups = _ensure_quick_reply_data(db, run=run, user_id=user_id)
    return ShopeeQuickReplyListResponse(
        preference=ShopeeQuickReplyPreferenceResponse(auto_hint_enabled=bool(preference.auto_hint_enabled) if preference else True),
        limits=ShopeeQuickReplyLimitsResponse(),
        groups=[_serialize_quick_reply_group(group) for group in groups],
    )


def _normalize_quick_reply_tags(raw_tags: list[str]) -> list[str]:
    tags: list[str] = []
    for raw_tag in raw_tags:
        tag = str(raw_tag).strip()
        if not tag or tag in tags:
            continue
        if len(tag) > QUICK_REPLY_MAX_TAG_LENGTH:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"标签不能超过 {QUICK_REPLY_MAX_TAG_LENGTH} 字")
        tags.append(tag)
        if len(tags) > QUICK_REPLY_MAX_TAGS_PER_MESSAGE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"单条消息最多 {QUICK_REPLY_MAX_TAGS_PER_MESSAGE} 个标签")
    return tags


def _validate_quick_reply_payload(payload: ShopeeQuickReplyCreateGroupRequest | ShopeeQuickReplyUpdateGroupRequest) -> tuple[str, list[tuple[str, list[str]]]]:
    group_name = payload.group_name.strip()
    if not group_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="分组名称不能为空")
    if len(group_name) > QUICK_REPLY_MAX_GROUP_NAME_LENGTH:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"分组名称不能超过 {QUICK_REPLY_MAX_GROUP_NAME_LENGTH} 字")

    if not payload.messages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="至少需要添加一条快捷回复消息")
    if len(payload.messages) > QUICK_REPLY_MAX_MESSAGES_PER_GROUP:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"每个分组最多 {QUICK_REPLY_MAX_MESSAGES_PER_GROUP} 条消息")

    messages: list[tuple[str, list[str]]] = []
    for item in payload.messages:
        message = item.message.strip()
        if not message:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="快捷回复消息不能为空")
        if len(message) > QUICK_REPLY_MAX_MESSAGE_LENGTH:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"快捷回复消息不能超过 {QUICK_REPLY_MAX_MESSAGE_LENGTH} 字")
        messages.append((message, _normalize_quick_reply_tags(item.tags)))
    return group_name, messages


def _validate_quick_reply_create_payload(db: Session, *, run_id: int, user_id: int, payload: ShopeeQuickReplyCreateGroupRequest) -> tuple[str, list[tuple[str, list[str]]]]:
    group_count = db.query(ShopeeQuickReplyGroup).filter(ShopeeQuickReplyGroup.run_id == run_id, ShopeeQuickReplyGroup.user_id == user_id).count()
    if group_count >= QUICK_REPLY_MAX_GROUPS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"快捷回复分组最多 {QUICK_REPLY_MAX_GROUPS} 个")
    return _validate_quick_reply_payload(payload)


def _resolve_marketing_lang(raw_lang: str | None) -> str:
    value = (raw_lang or "zh-CN").strip()
    return value or "zh-CN"


def _resolve_marketing_event_image(image_key: str) -> str:
    presets = {
        "marketing-event-super-voucher-day": "linear-gradient(135deg,#0f5ef7 0%,#38b6ff 55%,#d9f4ff 100%)",
        "marketing-event-mega-payday": "linear-gradient(135deg,#ff7a18 0%,#ffb347 40%,#fff2b8 100%)",
        "marketing-event-growth-week": "linear-gradient(135deg,#f43f5e 0%,#fb7185 45%,#ffd7c2 100%)",
    }
    return presets.get(image_key, image_key)


def _build_marketing_target_route(route_template: str, public_id: str | None) -> str:
    if not public_id:
        return route_template
    return route_template.replace("{public_id}", public_id)


def _build_marketing_bootstrap_payload(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    public_id: str,
    lang: str,
    current_tick: datetime,
) -> ShopeeMarketingBootstrapResponse:
    market = (run.market or "MY").strip().upper() or "MY"
    announcement_rows = (
        db.query(ShopeeMarketingAnnouncement)
        .filter(
            ShopeeMarketingAnnouncement.market == market,
            ShopeeMarketingAnnouncement.lang == lang,
            ShopeeMarketingAnnouncement.status == "published",
        )
        .order_by(desc(ShopeeMarketingAnnouncement.priority), desc(ShopeeMarketingAnnouncement.id))
        .limit(3)
        .all()
    )
    tool_rows = (
        db.query(ShopeeMarketingTool)
        .filter(
            ShopeeMarketingTool.is_visible == True,
        )
        .order_by(asc(ShopeeMarketingTool.sort_order), asc(ShopeeMarketingTool.id))
        .all()
    )
    event_rows = (
        db.query(ShopeeMarketingEvent)
        .filter(
            ShopeeMarketingEvent.market == market,
            ShopeeMarketingEvent.lang == lang,
            ShopeeMarketingEvent.status.in_(("ongoing", "upcoming")),
        )
        .order_by(asc(ShopeeMarketingEvent.sort_order), asc(ShopeeMarketingEvent.id))
        .limit(3)
        .all()
    )
    pref = (
        db.query(ShopeeUserMarketingPreference)
        .filter(
            ShopeeUserMarketingPreference.run_id == run.id,
            ShopeeUserMarketingPreference.user_id == user_id,
        )
        .first()
    )

    return ShopeeMarketingBootstrapResponse(
        meta=ShopeeMarketingBootstrapMetaResponse(
            run_id=run.id,
            user_id=user_id,
            market=market,
            lang=lang,
            current_tick=current_tick,
        ),
        preferences=ShopeeMarketingPreferencesResponse(
            tools_collapsed=bool(pref.tools_collapsed) if pref else False,
            last_viewed_at=pref.last_viewed_at if pref else None,
        ),
        announcements=[
            ShopeeMarketingAnnouncementResponse(
                id=row.id,
                title=row.title,
                summary=row.summary,
                badge_text=row.badge_text,
                published_at=row.updated_at or row.created_at,
            )
            for row in announcement_rows
        ],
        tools=[
            ShopeeMarketingToolResponse(
                tool_key=row.tool_key,
                tool_name=row.tool_name,
                tag_type=row.tag_type,
                description=row.description,
                icon_key=row.icon_key,
                target_route=_build_marketing_target_route(row.target_route, public_id),
                is_enabled=bool(row.is_enabled),
                is_visible=bool(row.is_visible),
            )
            for row in tool_rows
        ],
        events=[
            ShopeeMarketingEventResponse(
                id=row.id,
                title=row.title,
                image_url=_resolve_marketing_event_image(row.image_url),
                jump_url=_build_marketing_target_route(row.jump_url, public_id),
                status=row.status,
            )
            for row in event_rows
        ],
    )


def _resolve_discount_type(raw_value: str | None) -> str:
    value = (raw_value or "all").strip().lower()
    return value if value in {"all", "discount", "bundle", "add_on"} else "all"


def _resolve_discount_status(raw_value: str | None) -> str:
    value = (raw_value or "all").strip().lower()
    return value if value in {"all", "draft", "upcoming", "ongoing", "ended", "disabled"} else "all"


def _resolve_discount_search_field(raw_value: str | None) -> str:
    value = (raw_value or "campaign_name").strip().lower()
    return value if value in {"campaign_name", "campaign_id"} else "campaign_name"


def _parse_discount_date(raw_value: str | None) -> date | None:
    value = (raw_value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _resolve_discount_campaign_status(row: ShopeeDiscountCampaign, *, current_tick: datetime) -> str:
    status_value = (row.campaign_status or "draft").strip().lower()
    if status_value in {"draft", "disabled"}:
        return status_value
    if row.start_at and current_tick < _align_compare_time(current_tick, row.start_at):
        return "upcoming"
    if row.end_at and current_tick > _align_compare_time(current_tick, row.end_at):
        return "ended"
    return "ongoing"


def _discount_status_label(status_value: str) -> str:
    return {
        "draft": "草稿",
        "upcoming": "即将开始",
        "ongoing": "进行中",
        "ended": "已结束",
        "disabled": "已停用",
    }.get(status_value, status_value)


def _discount_type_label(discount_type: str) -> str:
    return {
        "discount": "单品折扣",
        "bundle": "套餐优惠",
        "add_on": "加价购",
        "gift": "满额赠",
    }.get(discount_type, discount_type)


def _discount_actions(status_value: str, read_only: bool, campaign_type: str = "discount") -> list[str]:
    if campaign_type == "bundle":
        return ["详情", "订单"] if read_only else ["编辑", "复制", "详情", "订单"]
    if campaign_type == "add_on":
        return ["详情", "订单"] if read_only else ["详情", "复制", "订单"]
    if read_only:
        return ["数据", "详情"]
    if status_value == "ongoing":
        return ["编辑", "数据", "详情"]
    if status_value == "upcoming":
        return ["编辑", "详情"]
    if status_value == "ended":
        return ["数据", "详情", "复制"]
    if status_value == "draft":
        return ["编辑", "详情"]
    return ["详情"]


def _format_discount_period(start_at: datetime | None, end_at: datetime | None) -> str:
    def _fmt(value: datetime | None) -> str:
        if not value:
            return "-"
        return value.strftime("%Y/%m/%d %H:%M")

    return f"{_fmt(start_at)} - {_fmt(end_at)}"


def _discount_query_payload_hash(
    *,
    discount_type: str,
    status_value: str,
    search_field: str,
    keyword: str,
    date_from: str | None,
    date_to: str | None,
    page: int,
    page_size: int,
) -> str:
    payload = {
        "discount_type": discount_type,
        "status": status_value,
        "search_field": search_field,
        "keyword": keyword,
        "date_from": date_from or "",
        "date_to": date_to or "",
        "page": page,
        "page_size": page_size,
    }
    return hashlib.sha1(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _shopee_discount_bootstrap_cache_key(
    *,
    run_id: int,
    user_id: int,
    discount_type: str,
    status_value: str,
    search_field: str,
    keyword: str,
    date_from: str | None,
    date_to: str | None,
    page: int,
    page_size: int,
) -> str:
    digest = _discount_query_payload_hash(
        discount_type=discount_type,
        status_value=status_value,
        search_field=search_field,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return f"{REDIS_PREFIX}:cache:shopee:discount:bootstrap:{run_id}:{user_id}:{discount_type}:{status_value}:{page}:{digest}"


def _shopee_discount_list_cache_key(
    *,
    run_id: int,
    user_id: int,
    discount_type: str,
    status_value: str,
    search_field: str,
    keyword: str,
    date_from: str | None,
    date_to: str | None,
    page: int,
    page_size: int,
) -> str:
    digest = _discount_query_payload_hash(
        discount_type=discount_type,
        status_value=status_value,
        search_field=search_field,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return f"{REDIS_PREFIX}:cache:shopee:discount:list:{run_id}:{user_id}:{discount_type}:{status_value}:{page}:{digest}"


def _invalidate_shopee_discount_cache(*, run_id: int, user_id: int) -> None:
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:discount:bootstrap:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:discount:list:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:discount:detail:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:discount:data:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:discount:data-trend:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:discount:data-ranking:{run_id}:{user_id}:")


def _shopee_discount_data_cache_key(*, run_id: int, user_id: int, campaign_id: int, time_basis: str, game_year: int = 0) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:discount:data:game-day-v4:{run_id}:{user_id}:{campaign_id}:{time_basis}:{game_year}"


def _shopee_discount_data_trend_cache_key(*, run_id: int, user_id: int, campaign_id: int, metric: str, time_basis: str) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:discount:data-trend:game-day-v3:{run_id}:{user_id}:{campaign_id}:{metric}:{time_basis}"


def _shopee_discount_data_ranking_cache_key(
    *,
    run_id: int,
    user_id: int,
    campaign_id: int,
    page: int,
    page_size: int,
    sort: str,
    order: str,
    time_basis: str,
    game_year: int = 0,
) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:discount:data-ranking:game-year-v3:{run_id}:{user_id}:{campaign_id}:{page}:{page_size}:{sort}:{order}:{time_basis}:{game_year}"


def _shopee_discount_detail_cache_key(
    *,
    run_id: int,
    user_id: int,
    campaign_id: int,
    section: str,
    page: int,
    page_size: int,
    status_value: str = "all",
) -> str:
    return (
        f"{REDIS_PREFIX}:cache:shopee:discount:detail:{run_id}:{user_id}:"
        f"{campaign_id}:{section}:{page}:{page_size}:{status_value or 'all'}"
    )


def _shopee_discount_create_bootstrap_cache_key(
    *,
    run_id: int,
    user_id: int,
    campaign_type: str,
    draft_id: int | None,
    source_campaign_id: int | None,
) -> str:
    safe_campaign_type = (campaign_type or "discount").strip().lower() or "discount"
    return (
        f"{REDIS_PREFIX}:cache:shopee:discount:create:bootstrap:"
        f"{run_id}:{user_id}:{safe_campaign_type}:{draft_id or 0}:{source_campaign_id or 0}"
    )


def _eligible_products_hash(*, keyword: str, page: int, page_size: int) -> str:
    payload = {"keyword": keyword.strip(), "page": page, "page_size": page_size}
    return hashlib.md5(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _shopee_discount_eligible_products_cache_key(*, run_id: int, user_id: int, keyword: str, page: int, page_size: int) -> str:
    return (
        f"{REDIS_PREFIX}:cache:shopee:discount:eligible-products:{run_id}:{user_id}:"
        f"{_eligible_products_hash(keyword=keyword, page=page, page_size=page_size)}"
    )


def _shopee_discount_draft_cache_key(*, run_id: int, user_id: int, draft_id: int) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:discount:draft:{run_id}:{user_id}:{draft_id}"


def _invalidate_shopee_discount_create_cache(*, run_id: int, user_id: int, draft_id: int | None = None) -> None:
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:discount:create:bootstrap:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:discount:eligible-products:{run_id}:{user_id}:")
    if draft_id:
        cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:discount:draft:{run_id}:{user_id}:{draft_id}")


def _enforce_shopee_discount_bootstrap_rate_limit(*, user_id: int) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:discount:bootstrap:user:{user_id}",
        limit=REDIS_RATE_LIMIT_DISCOUNT_BOOTSTRAP_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"请求过于频繁，请在 {reset_at} 后重试")


def _enforce_shopee_discount_list_rate_limit(*, user_id: int) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:discount:list:user:{user_id}",
        limit=REDIS_RATE_LIMIT_DISCOUNT_LIST_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"请求过于频繁，请在 {reset_at} 后重试")


def _enforce_shopee_discount_detail_rate_limit(*, user_id: int) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:discount:detail:user:{user_id}",
        limit=REDIS_RATE_LIMIT_DISCOUNT_DETAIL_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"请求过于频繁，请在 {reset_at} 后重试")


def _enforce_shopee_discount_data_rate_limit(*, user_id: int) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:discount:data:user:{user_id}",
        limit=REDIS_RATE_LIMIT_DISCOUNT_DATA_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"请求过于频繁，请在 {reset_at} 后重试")


def _enforce_shopee_discount_data_export_rate_limit(*, user_id: int) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:discount:data-export:user:{user_id}",
        limit=REDIS_RATE_LIMIT_DISCOUNT_DATA_EXPORT_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"请求过于频繁，请在 {reset_at} 后重试")


def _enforce_shopee_discount_create_bootstrap_rate_limit(*, user_id: int) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:discount:create:bootstrap:user:{user_id}",
        limit=REDIS_RATE_LIMIT_DISCOUNT_CREATE_BOOTSTRAP_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"请求过于频繁，请在 {reset_at} 后重试")


def _enforce_shopee_discount_eligible_products_rate_limit(*, user_id: int) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:discount:eligible-products:user:{user_id}",
        limit=REDIS_RATE_LIMIT_DISCOUNT_ELIGIBLE_PRODUCTS_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"请求过于频繁，请在 {reset_at} 后重试")


def _enforce_shopee_discount_drafts_rate_limit(*, user_id: int) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:discount:drafts:user:{user_id}",
        limit=REDIS_RATE_LIMIT_DISCOUNT_DRAFTS_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"请求过于频繁，请在 {reset_at} 后重试")


def _enforce_shopee_discount_create_rate_limit(*, user_id: int) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:discount:create:user:{user_id}",
        limit=REDIS_RATE_LIMIT_DISCOUNT_CREATE_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"请求过于频繁，请在 {reset_at} 后重试")


def _shopee_voucher_create_bootstrap_cache_key(*, run_id: int, user_id: int, voucher_type: str) -> str:
    safe_voucher_type = (voucher_type or "shop_voucher").strip().lower() or "shop_voucher"
    return f"{REDIS_PREFIX}:cache:shopee:voucher:create:bootstrap:{run_id}:{user_id}:{safe_voucher_type}"


def _shopee_voucher_code_check_cache_key(*, run_id: int, user_id: int, voucher_type: str, code_suffix: str) -> str:
    safe_voucher_type = (voucher_type or "shop_voucher").strip().lower() or "shop_voucher"
    return f"{REDIS_PREFIX}:cache:shopee:voucher:code-check:{run_id}:{user_id}:{safe_voucher_type}:{code_suffix}"



def _shopee_voucher_eligible_products_cache_key(*, run_id: int, user_id: int, voucher_type: str, search_field: str, category_key: str, keyword: str, page: int, page_size: int) -> str:
    payload = {
        "search_field": (search_field or "product_name").strip().lower(),
        "category_key": (category_key or "all").strip().lower(),
        "keyword": keyword.strip(),
        "page": page,
        "page_size": page_size,
    }
    digest = hashlib.md5(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    safe_voucher_type = (voucher_type or "product_voucher").strip().lower().replace("_", "-")
    return f"{REDIS_PREFIX}:cache:shopee:{safe_voucher_type}:eligible-products:{run_id}:{user_id}:{digest}"


def _shopee_voucher_list_cache_key(*, run_id: int, user_id: int, status_value: str, keyword: str, page: int, page_size: int) -> str:
    digest = hashlib.md5(json.dumps({"keyword": keyword.strip(), "page_size": page_size}, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return f"{REDIS_PREFIX}:cache:shopee:voucher:list:{run_id}:{user_id}:{status_value}:{page}:{digest}"


def _invalidate_shopee_voucher_cache(*, run_id: int, user_id: int, campaign_id: int | None = None) -> None:
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:voucher:create:bootstrap:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:voucher:code-check:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:product-voucher:eligible-products:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:private-voucher:eligible-products:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:live-voucher:eligible-products:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:video-voucher:eligible-products:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:voucher:list:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:voucher:performance:{run_id}:{user_id}")
    if campaign_id:
        cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:voucher:detail:{run_id}:{user_id}:{campaign_id}")


def _enforce_shopee_voucher_create_bootstrap_rate_limit(*, user_id: int) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:voucher:create:bootstrap:user:{user_id}",
        limit=REDIS_RATE_LIMIT_SHOPEE_VOUCHER_CREATE_BOOTSTRAP_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"请求过于频繁，请在 {reset_at} 后重试")


def _enforce_shopee_voucher_code_check_rate_limit(*, user_id: int) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:voucher:code-check:user:{user_id}",
        limit=REDIS_RATE_LIMIT_SHOPEE_VOUCHER_CODE_CHECK_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"请求过于频繁，请在 {reset_at} 后重试")


def _enforce_shopee_voucher_create_rate_limit(*, user_id: int) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:voucher:create:user:{user_id}",
        limit=REDIS_RATE_LIMIT_SHOPEE_VOUCHER_CREATE_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"请求过于频繁，请在 {reset_at} 后重试")


SHOPEE_SHIPPING_FEE_PROMOTION_CHANNELS = {
    "standard": "标准快递 (Standard Delivery)",
    "bulky": "大件快递 (Standard Delivery Bulky)",
}


def _shopee_shipping_fee_promotion_bootstrap_cache_key(*, run_id: int, user_id: int) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:shipping_fee_promotion:create:bootstrap:{run_id}:{user_id}"


def _shopee_shipping_fee_promotion_list_cache_key(*, run_id: int, user_id: int, status_value: str, page: int, page_size: int) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:shipping_fee_promotion:list:{run_id}:{user_id}:{status_value}:{page}:{page_size}"


def _invalidate_shopee_shipping_fee_promotion_cache(*, run_id: int, user_id: int) -> None:
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:shipping_fee_promotion:list:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:shipping_fee_promotion:active:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:orders:list:{run_id}:{user_id}:")


def _enforce_shopee_shipping_fee_promotion_rate_limit(*, user_id: int) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:shipping_fee_promotion:user:{user_id}",
        limit=REDIS_RATE_LIMIT_SHOPEE_SHIPPING_FEE_PROMOTION_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"请求过于频繁，请在 {reset_at} 后重试")


def _enforce_shopee_shipping_fee_promotion_create_rate_limit(*, user_id: int) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:shipping_fee_promotion:create:user:{user_id}",
        limit=REDIS_RATE_LIMIT_SHOPEE_SHIPPING_FEE_PROMOTION_CREATE_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"请求过于频繁，请在 {reset_at} 后重试")



def _flash_sale_query_hash(**kwargs: Any) -> str:
    return hashlib.md5(json.dumps(kwargs, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _shopee_flash_sale_bootstrap_cache_key(*, run_id: int, user_id: int, draft_id: int | None, source_campaign_id: int | None) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:flash_sale:create_bootstrap:market-category-v3:{run_id}:{user_id}:{draft_id or 0}:{source_campaign_id or 0}"


def _shopee_flash_sale_slots_cache_key(*, run_id: int, date_value: str) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:flash_sale:slots:{run_id}:{date_value}"


def _shopee_flash_sale_category_rules_cache_key(*, market: str) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:flash_sale:category_rules:{market}"


def _shopee_flash_sale_eligible_cache_key(*, run_id: int, user_id: int, **kwargs: Any) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:flash_sale:eligible:main-product-v2:{run_id}:{user_id}:{_flash_sale_query_hash(**kwargs)}"


def _shopee_flash_sale_draft_cache_key(*, run_id: int, user_id: int, draft_id: int) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:flash_sale:draft:{run_id}:{user_id}:{draft_id}"


def _shopee_flash_sale_list_cache_key(*, run_id: int, user_id: int, **kwargs: Any) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:flash_sale:list:{run_id}:{user_id}:{_flash_sale_query_hash(**kwargs)}"


def _shopee_flash_sale_performance_cache_key(*, run_id: int, user_id: int) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:flash_sale:performance:{run_id}:{user_id}"


def _shopee_flash_sale_data_cache_key(*, run_id: int, user_id: int, campaign_id: int, order_type: str) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:flash_sale:data:{run_id}:{user_id}:{campaign_id}:{order_type}"


def _shopee_flash_sale_data_products_cache_key(*, run_id: int, user_id: int, campaign_id: int, order_type: str, sort_by: str, sort_order: str) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:flash_sale:data_products:{run_id}:{user_id}:{campaign_id}:{order_type}:{sort_by}:{sort_order}"


def _shopee_flash_sale_detail_cache_key(*, run_id: int, campaign_id: int) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:flash_sale:detail:v2:{run_id}:{campaign_id}"


def _invalidate_shopee_flash_sale_cache(*, run_id: int, user_id: int, draft_id: int | None = None, campaign_id: int | None = None) -> None:
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:flash_sale:create_bootstrap:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:flash_sale:create_bootstrap:game-time-v2:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:flash_sale:create_bootstrap:market-category-v3:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:flash_sale:slots:{run_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:flash_sale:eligible:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:flash_sale:eligible:main-product-v2:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:flash_sale:list:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:flash_sale:performance:{run_id}:{user_id}")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:flash_sale:data:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:flash_sale:data_products:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:flash_sale:active_map:{run_id}")
    if draft_id:
        cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:flash_sale:draft:{run_id}:{user_id}:{draft_id}")
    if campaign_id:
        cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:flash_sale:detail:{run_id}:{campaign_id}")


def _enforce_shopee_flash_sale_rate_limit(*, user_id: int, create: bool = False) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:flash-sale:{'create' if create else 'read'}:user:{user_id}",
        limit=REDIS_RATE_LIMIT_FLASH_SALE_CREATE_PER_MIN if create else REDIS_RATE_LIMIT_FLASH_SALE_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"请求过于频繁，请在 {reset_at} 后重试")



def _enforce_shopee_addon_bootstrap_rate_limit(*, user_id: int) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:add-on:bootstrap:user:{user_id}",
        limit=REDIS_RATE_LIMIT_ADDON_BOOTSTRAP_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"请求过于频繁，请在 {reset_at} 后重试")


def _enforce_shopee_addon_eligible_products_rate_limit(*, user_id: int) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:add-on:eligible-products:user:{user_id}",
        limit=REDIS_RATE_LIMIT_ADDON_ELIGIBLE_PRODUCTS_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"请求过于频繁，请在 {reset_at} 后重试")


def _enforce_shopee_addon_drafts_rate_limit(*, user_id: int) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:add-on:drafts:user:{user_id}",
        limit=REDIS_RATE_LIMIT_ADDON_DRAFTS_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"请求过于频繁，请在 {reset_at} 后重试")


def _enforce_shopee_addon_create_rate_limit(*, user_id: int) -> None:
    limited, _remaining, reset_at = check_rate_limit(
        key=f"{REDIS_PREFIX}:ratelimit:shopee:add-on:create:user:{user_id}",
        limit=REDIS_RATE_LIMIT_ADDON_CREATE_PER_MIN,
        window_sec=60,
    )
    if limited:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"请求过于频繁，请在 {reset_at} 后重试")


def _query_discount_campaign_rows(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    discount_type: str,
    status_value: str,
    search_field: str,
    keyword: str,
    date_from: date | None,
    date_to: date | None,
    current_tick: datetime,
    page: int,
    page_size: int,
) -> tuple[list[ShopeeDiscountCampaign], int]:
    query = (
        db.query(ShopeeDiscountCampaign)
        .filter(
            ShopeeDiscountCampaign.run_id == run.id,
            ShopeeDiscountCampaign.user_id == user_id,
        )
        .options(selectinload(ShopeeDiscountCampaign.items))
    )
    if discount_type != "all":
        query = query.filter(ShopeeDiscountCampaign.campaign_type == discount_type)
    if date_from:
        query = query.filter(or_(ShopeeDiscountCampaign.end_at.is_(None), cast(ShopeeDiscountCampaign.end_at, Date) >= date_from))
    if date_to:
        query = query.filter(or_(ShopeeDiscountCampaign.start_at.is_(None), cast(ShopeeDiscountCampaign.start_at, Date) <= date_to))
    clean_keyword = keyword.strip()
    if clean_keyword:
        if search_field == "campaign_id" and clean_keyword.isdigit():
            query = query.filter(ShopeeDiscountCampaign.id == int(clean_keyword))
        else:
            query = query.filter(ShopeeDiscountCampaign.campaign_name.ilike(f"%{clean_keyword}%"))

    all_rows = query.order_by(desc(ShopeeDiscountCampaign.created_at), desc(ShopeeDiscountCampaign.id)).all()
    filtered_rows = [
        row for row in all_rows
        if status_value == "all" or _resolve_discount_campaign_status(row, current_tick=current_tick) == status_value
    ]
    total = len(filtered_rows)
    start = max(0, (page - 1) * page_size)
    end = start + page_size
    return filtered_rows[start:end], total


def _build_discount_campaign_list_response(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    discount_type: str,
    status_value: str,
    search_field: str,
    keyword: str,
    date_from: date | None,
    date_to: date | None,
    current_tick: datetime,
    page: int,
    page_size: int,
    read_only: bool,
) -> ShopeeDiscountCampaignListResponse:
    rows, total = _query_discount_campaign_rows(
        db=db,
        run=run,
        user_id=user_id,
        discount_type=discount_type,
        status_value=status_value,
        search_field=search_field,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        current_tick=current_tick,
        page=page,
        page_size=page_size,
    )
    addon_source_ids = [int(row.id) for row in rows if row.campaign_type == "add_on"]
    addon_campaigns_by_source_id: dict[int, ShopeeAddonCampaign] = {}
    if addon_source_ids:
        addon_campaigns = (
            db.query(ShopeeAddonCampaign)
            .options(selectinload(ShopeeAddonCampaign.main_items), selectinload(ShopeeAddonCampaign.reward_items))
            .filter(
                ShopeeAddonCampaign.run_id == run.id,
                ShopeeAddonCampaign.user_id == user_id,
                ShopeeAddonCampaign.source_campaign_id.in_(addon_source_ids),
            )
            .all()
        )
        addon_campaigns_by_source_id = {
            int(campaign.source_campaign_id): campaign
            for campaign in addon_campaigns
            if campaign.source_campaign_id is not None
        }

    items: list[ShopeeDiscountCampaignRowResponse] = []
    for row in rows:
        effective_status = _resolve_discount_campaign_status(row, current_tick=current_tick)
        campaign_type_label = _discount_type_label(row.campaign_type)
        if row.campaign_type == "add_on" and row.id in addon_campaigns_by_source_id:
            addon_campaign = addon_campaigns_by_source_id[int(row.id)]
            campaign_type_label = _addon_promotion_type_label(addon_campaign.promotion_type)
            product_images = [
                item.image_url_snapshot
                for item in sorted(addon_campaign.main_items or [], key=lambda item: (item.sort_order, item.id))
            ] + [
                item.image_url_snapshot
                for item in sorted(addon_campaign.reward_items or [], key=lambda item: (item.sort_order, item.id))
            ]
        else:
            product_images = [
                item.image_url_snapshot
                for item in sorted(row.items or [], key=lambda item: (item.sort_order, item.id))
            ]
        product_thumbs = [ShopeeDiscountProductThumbResponse(image_url=image_url) for image_url in product_images[:5]]
        overflow_count = max(len(product_images) - len(product_thumbs), 0)
        items.append(
            ShopeeDiscountCampaignRowResponse(
                id=row.id,
                campaign_name=row.campaign_name,
                status=effective_status,
                status_label=_discount_status_label(effective_status),
                campaign_type=row.campaign_type,
                campaign_type_label=campaign_type_label,
                products=product_thumbs,
                products_overflow_count=overflow_count,
                period_text=_format_discount_period(row.start_at, row.end_at),
                actions=_discount_actions(effective_status, read_only, row.campaign_type),
            )
        )

    return ShopeeDiscountCampaignListResponse(
        items=items,
        pagination=ShopeeDiscountPaginationResponse(page=page, page_size=page_size, total=total),
    )


def _build_discount_tabs(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    active_discount_type: str,
) -> list[ShopeeDiscountTabResponse]:
    rows = (
        db.query(ShopeeDiscountCampaign.campaign_type, func.count(ShopeeDiscountCampaign.id))
        .filter(
            ShopeeDiscountCampaign.run_id == run.id,
            ShopeeDiscountCampaign.user_id == user_id,
        )
        .group_by(ShopeeDiscountCampaign.campaign_type)
        .all()
    )
    counts_by_type = {str(campaign_type): int(count or 0) for campaign_type, count in rows}
    addon_count = db.query(func.count(ShopeeAddonCampaign.id)).filter(ShopeeAddonCampaign.run_id == run.id, ShopeeAddonCampaign.user_id == user_id).scalar() or 0
    counts_by_type["add_on"] = counts_by_type.get("add_on", 0) + int(addon_count)
    total_count = sum(counts_by_type.values())
    tabs = [
        ("all", "全部", total_count),
        ("discount", "单品折扣", counts_by_type.get("discount", 0)),
        ("bundle", "套餐优惠", counts_by_type.get("bundle", 0)),
        ("add_on", "加价购", counts_by_type.get("add_on", 0)),
    ]
    return [
        ShopeeDiscountTabResponse(key=key, label=label, count=count, active=active_discount_type == key)
        for key, label, count in tabs
    ]


def _current_game_week_range(run: GameRun, current_tick: datetime) -> tuple[date, date]:
    current_game_text = _format_discount_game_datetime(current_tick, run=run)
    current_game_date = datetime.strptime(current_game_text[:10], "%Y-%m-%d").date() if current_game_text else current_tick.date()
    week_start = current_game_date - timedelta(days=current_game_date.weekday())
    return week_start, week_start + timedelta(days=6)


def _resolve_flash_sale_data_order_type(value: str) -> str:
    return "placed" if value == "placed" else "confirmed"


def _resolve_flash_sale_data_sort(value: str) -> str:
    return value if value in {"sales_amount", "order_count", "unit_count"} else "sales_amount"


def _resolve_flash_sale_data_sort_order(value: str) -> str:
    return "asc" if value == "asc" else "desc"


def _flash_sale_order_filters(run_id: int, user_id: int, campaign_id: int) -> list[Any]:
    return [
        ShopeeOrder.run_id == run_id,
        ShopeeOrder.user_id == user_id,
        ShopeeOrder.type_bucket != "cancelled",
        ShopeeOrderItem.marketing_campaign_type == "flash_sale",
        ShopeeOrderItem.marketing_campaign_id == campaign_id,
    ]


def _flash_sale_traffic_counts(db: Session, *, run_id: int, user_id: int, campaign_id: int) -> tuple[int, int]:
    rows = (
        db.query(ShopeeFlashSaleTrafficEvent.event_type, func.count(ShopeeFlashSaleTrafficEvent.id))
        .filter(
            ShopeeFlashSaleTrafficEvent.run_id == run_id,
            ShopeeFlashSaleTrafficEvent.user_id == user_id,
            ShopeeFlashSaleTrafficEvent.campaign_id == campaign_id,
            ShopeeFlashSaleTrafficEvent.event_type.in_(["view", "click"]),
        )
        .group_by(ShopeeFlashSaleTrafficEvent.event_type)
        .all()
    )
    counts = {str(event_type or ""): int(count or 0) for event_type, count in rows}
    return counts.get("view", 0), counts.get("click", 0)


def _build_flash_sale_data_campaign(campaign: ShopeeFlashSaleCampaign, *, run: GameRun, current_tick: datetime) -> ShopeeFlashSaleDataCampaignResponse:
    status_value = _flash_sale_status(campaign, current_tick=current_tick)
    return ShopeeFlashSaleDataCampaignResponse(
        id=int(campaign.id),
        name=campaign.campaign_name,
        status=status_value,
        status_label=_flash_sale_status_label(status_value),
        edit_period_label=_flash_sale_campaign_display_time(campaign, run=run),
        activity_period_label=_flash_sale_campaign_display_time(campaign, run=run),
        item_count=len(campaign.items or []),
    )


def _build_flash_sale_data_metrics(
    db: Session,
    *,
    run: GameRun,
    user_id: int,
    campaign: ShopeeFlashSaleCampaign,
    order_type: str,
) -> ShopeeFlashSaleDataMetricsResponse:
    view_count, click_count = _flash_sale_traffic_counts(db, run_id=run.id, user_id=user_id, campaign_id=campaign.id)
    order_rows = (
        db.query(
            ShopeeOrder.id,
            ShopeeOrder.buyer_name,
            func.coalesce(func.sum(ShopeeOrderItem.discounted_unit_price * ShopeeOrderItem.quantity), 0.0),
            func.coalesce(func.sum(ShopeeOrderItem.quantity), 0),
        )
        .join(ShopeeOrderItem, ShopeeOrderItem.order_id == ShopeeOrder.id)
        .filter(*_flash_sale_order_filters(run.id, user_id, campaign.id))
        .group_by(ShopeeOrder.id, ShopeeOrder.buyer_name)
        .all()
    )
    sales_amount = sum(float(row_sales or 0) for _order_id, _buyer_name, row_sales, _qty in order_rows)
    unit_count = sum(int(qty or 0) for _order_id, _buyer_name, _row_sales, qty in order_rows)
    buyer_count = len({str(buyer_name or "") for _order_id, buyer_name, _row_sales, _qty in order_rows})
    return ShopeeFlashSaleDataMetricsResponse(
        reminder_count=0,
        product_view_count=view_count,
        product_click_count=click_count,
        ctr=round((click_count / view_count * 100), 2) if view_count > 0 else 0.0,
        sales_amount=round(sales_amount, 2),
        order_count=len(order_rows),
        unit_count=unit_count,
        buyer_count=buyer_count,
    )


def _build_flash_sale_data_products(
    db: Session,
    *,
    run: GameRun,
    user_id: int,
    campaign: ShopeeFlashSaleCampaign,
    order_type: str,
    sort_by: str,
    sort_order: str,
) -> ShopeeFlashSaleDataProductsResponse:
    stats_rows = (
        db.query(
            ShopeeOrderItem.listing_id,
            ShopeeOrderItem.variant_id,
            func.count(func.distinct(ShopeeOrder.id)),
            func.coalesce(func.sum(ShopeeOrderItem.quantity), 0),
            func.coalesce(func.sum(ShopeeOrderItem.discounted_unit_price * ShopeeOrderItem.quantity), 0.0),
        )
        .join(ShopeeOrder, ShopeeOrder.id == ShopeeOrderItem.order_id)
        .filter(*_flash_sale_order_filters(run.id, user_id, campaign.id))
        .group_by(ShopeeOrderItem.listing_id, ShopeeOrderItem.variant_id)
        .all()
    )
    stats = {
        (int(listing_id), int(variant_id) if variant_id is not None else None): {
            "order_count": int(order_count or 0),
            "unit_count": int(unit_count or 0),
            "sales_amount": float(sales_amount or 0),
        }
        for listing_id, variant_id, order_count, unit_count, sales_amount in stats_rows
        if listing_id is not None
    }
    listing_ids = [int(item.listing_id) for item in campaign.items or []]
    cover_rows = (
        db.query(ShopeeListing.id, ShopeeListing.cover_url, ShopeeListingImage.image_url)
        .outerjoin(ShopeeListingImage, (ShopeeListingImage.listing_id == ShopeeListing.id) & (ShopeeListingImage.is_cover.is_(True)))
        .filter(
            ShopeeListing.run_id == run.id,
            ShopeeListing.user_id == user_id,
            ShopeeListing.id.in_(listing_ids),
        )
        .all()
        if listing_ids
        else []
    )
    main_image_by_listing_id = {
        int(listing_id): (cover_url or image_url)
        for listing_id, cover_url, image_url in cover_rows
    }
    grouped: dict[int, ShopeeFlashSaleDataProductResponse] = {}
    for item in sorted(campaign.items or [], key=lambda row: row.id):
        listing_id = int(item.listing_id)
        variant_id = int(item.variant_id) if item.variant_id is not None else None
        item_stats = stats.get((listing_id, variant_id), {"order_count": 0, "unit_count": 0, "sales_amount": 0.0})
        product = grouped.get(listing_id)
        if not product:
            product = ShopeeFlashSaleDataProductResponse(
                listing_id=listing_id,
                item_id_label=str(listing_id),
                name=item.product_name_snapshot,
                image_url=main_image_by_listing_id.get(listing_id) or item.image_url_snapshot,
            )
            grouped[listing_id] = product
        product.sales_amount = round(float(product.sales_amount or 0) + float(item_stats["sales_amount"]), 2)
        product.order_count = int(product.order_count or 0) + int(item_stats["order_count"])
        product.unit_count = int(product.unit_count or 0) + int(item_stats["unit_count"])
        product.variations.append(
            ShopeeFlashSaleDataVariationResponse(
                campaign_item_id=int(item.id),
                variant_id=variant_id,
                variation_name=item.variant_name_snapshot or "单规格",
                activity_stock=int(item.activity_stock_limit or 0) if item.status == "active" else 0,
                flash_price=round(float(item.flash_price or 0), 2),
                sales_amount=round(float(item_stats["sales_amount"]), 2),
                order_count=int(item_stats["order_count"]),
                unit_count=int(item_stats["unit_count"]),
            )
        )
    items = list(grouped.values())
    reverse = sort_order != "asc"
    items.sort(key=lambda row: (float(getattr(row, sort_by)), int(row.order_count), int(row.unit_count), int(row.listing_id)), reverse=reverse)
    return ShopeeFlashSaleDataProductsResponse(items=items)


def _build_flash_sale_performance(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    current_tick: datetime,
) -> ShopeeFlashSalePerformanceResponse:
    week_start, week_end = _current_game_week_range(run, current_tick)
    campaign_rows = (
        db.query(ShopeeFlashSaleCampaign.id, ShopeeFlashSaleCampaign.reminder_count, ShopeeFlashSaleCampaign.click_count)
        .filter(
            ShopeeFlashSaleCampaign.run_id == run.id,
            ShopeeFlashSaleCampaign.user_id == user_id,
            ShopeeFlashSaleCampaign.slot_date >= week_start,
            ShopeeFlashSaleCampaign.slot_date <= week_end,
        )
        .all()
    )
    campaign_ids = [int(campaign_id) for campaign_id, _reminders, _clicks in campaign_rows]
    view_count = 0
    click_count = 0
    if campaign_ids:
        traffic_rows = (
            db.query(ShopeeFlashSaleTrafficEvent.event_type, func.count(ShopeeFlashSaleTrafficEvent.id))
            .filter(
                ShopeeFlashSaleTrafficEvent.run_id == run.id,
                ShopeeFlashSaleTrafficEvent.user_id == user_id,
                ShopeeFlashSaleTrafficEvent.campaign_id.in_(campaign_ids),
                ShopeeFlashSaleTrafficEvent.event_type.in_(["view", "click"]),
            )
            .group_by(ShopeeFlashSaleTrafficEvent.event_type)
            .all()
        )
        traffic_counts = {str(event_type or ""): int(count or 0) for event_type, count in traffic_rows}
        view_count = traffic_counts.get("view", 0)
        click_count = traffic_counts.get("click", 0)
    ctr = (click_count / view_count * 100) if view_count > 0 else 0.0

    sales_amount = 0.0
    orders_count = 0
    buyers_count = 0
    if campaign_ids:
        order_rows = (
            db.query(
                ShopeeOrder.id,
                ShopeeOrder.buyer_name,
                func.coalesce(func.sum(ShopeeOrderItem.discounted_unit_price * ShopeeOrderItem.quantity), 0.0),
            )
            .join(ShopeeOrderItem, ShopeeOrderItem.order_id == ShopeeOrder.id)
            .filter(
                ShopeeOrder.run_id == run.id,
                ShopeeOrder.user_id == user_id,
                ShopeeOrderItem.marketing_campaign_type == "flash_sale",
                ShopeeOrderItem.marketing_campaign_id.in_(campaign_ids),
            )
            .group_by(ShopeeOrder.id, ShopeeOrder.buyer_name)
            .all()
        )
        sales_amount = sum(float(row_sales or 0) for _order_id, _buyer_name, row_sales in order_rows)
        orders_count = len(order_rows)
        buyers_count = len({str(buyer_name or "") for _order_id, buyer_name, _row_sales in order_rows})

    return ShopeeFlashSalePerformanceResponse(
        label="我的店铺限时抢购表现",
        range_text=f"数据截至于 {week_start.isoformat()} 至 {week_end.isoformat()} GMT+7",
        metrics=[
            ShopeeFlashSaleMetricResponse(key="sales_amount", label="销售额", value=f"RM {sales_amount:.2f}", delta=0.0),
            ShopeeFlashSaleMetricResponse(key="orders_count", label="订单", value=orders_count, delta=0.0),
            ShopeeFlashSaleMetricResponse(key="buyers_count", label="买家数", value=buyers_count, delta=0.0),
            ShopeeFlashSaleMetricResponse(key="ctr", label="点击率 (CTR)", value=f"{ctr:.2f} %", delta=0.0),
        ],
    )


def _build_discount_performance(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    discount_type: str,
    status_value: str,
    date_from: date | None,
    date_to: date | None,
    current_tick: datetime,
) -> ShopeeDiscountPerformanceResponse:
    week_start, week_end = _current_game_week_range(run, current_tick)
    start_date = date_from or week_start
    end_date = date_to or week_end

    query = (
        db.query(ShopeeDiscountPerformanceDaily)
        .join(ShopeeDiscountCampaign, ShopeeDiscountCampaign.id == ShopeeDiscountPerformanceDaily.campaign_id)
        .filter(
            ShopeeDiscountPerformanceDaily.run_id == run.id,
            ShopeeDiscountPerformanceDaily.user_id == user_id,
            ShopeeDiscountPerformanceDaily.stat_date >= start_date,
            ShopeeDiscountPerformanceDaily.stat_date <= end_date,
        )
    )
    if discount_type != "all":
        query = query.filter(ShopeeDiscountCampaign.campaign_type == discount_type)
    if status_value != "all":
        campaign_rows = (
            db.query(ShopeeDiscountCampaign.id)
            .filter(
                ShopeeDiscountCampaign.run_id == run.id,
                ShopeeDiscountCampaign.user_id == user_id,
            )
            .all()
        )
        allowed_ids = [
            campaign_id for (campaign_id,) in campaign_rows
            if (
                _resolve_discount_campaign_status(
                    db.query(ShopeeDiscountCampaign).filter(ShopeeDiscountCampaign.id == campaign_id).first(),
                    current_tick=current_tick,
                )
                == status_value
            )
        ]
        if not allowed_ids:
            aggregate = (0.0, 0, 0, 0)
        else:
            aggregate = query.filter(ShopeeDiscountCampaign.id.in_(allowed_ids)).with_entities(
                func.coalesce(func.sum(ShopeeDiscountPerformanceDaily.sales_amount), 0.0),
                func.coalesce(func.sum(ShopeeDiscountPerformanceDaily.orders_count), 0),
                func.coalesce(func.sum(ShopeeDiscountPerformanceDaily.units_sold), 0),
                func.coalesce(func.sum(ShopeeDiscountPerformanceDaily.buyers_count), 0),
            ).first() or (0.0, 0, 0, 0)
    else:
        aggregate = query.with_entities(
            func.coalesce(func.sum(ShopeeDiscountPerformanceDaily.sales_amount), 0.0),
            func.coalesce(func.sum(ShopeeDiscountPerformanceDaily.orders_count), 0),
            func.coalesce(func.sum(ShopeeDiscountPerformanceDaily.units_sold), 0),
            func.coalesce(func.sum(ShopeeDiscountPerformanceDaily.buyers_count), 0),
        ).first() or (0.0, 0, 0, 0)

    sales_amount, orders_count, units_sold, buyers_count = aggregate
    return ShopeeDiscountPerformanceResponse(
        label="促销表现",
        range_text=f"统计时间：{start_date.isoformat()} 至 {end_date.isoformat()}",
        metrics=[
            ShopeeDiscountMetricResponse(key="sales_amount", label="销售额", value=f"RM {float(sales_amount or 0):.2f}", delta=0.0),
            ShopeeDiscountMetricResponse(key="orders_count", label="订单数", value=int(orders_count or 0), delta=0.0),
            ShopeeDiscountMetricResponse(key="units_sold", label="售出件数", value=int(units_sold or 0), delta=0.0),
            ShopeeDiscountMetricResponse(key="buyers_count", label="买家数", value=int(buyers_count or 0), delta=0.0),
        ],
    )


def _discount_item_type_label(discount_type: str) -> str:
    return {
        "percent": "百分比折扣",
        "final_price": "固定折后价",
        "fixed_amount": "固定金额折扣",
        "bundle_price": "套餐价",
    }.get(discount_type, discount_type)


def _order_type_bucket_label(type_bucket: str) -> str:
    return {
        "unpaid": "未付款",
        "toship": "待出货",
        "shipping": "运输中",
        "completed": "已完成",
        "cancelled": "已取消",
    }.get(type_bucket, type_bucket)


def _resolve_discount_order_status(raw_value: str | None) -> str:
    value = (raw_value or "all").strip().lower()
    if value == "return_refund_cancel":
        return "cancelled"
    return value if value in {"all", "unpaid", "toship", "shipping", "completed", "cancelled"} else "all"


def _format_discount_detail_datetime(value: datetime | None) -> str | None:
    if not value:
        return None
    return value.strftime("%Y/%m/%d %H:%M")


def _build_discount_detail_pagination(*, page: int, page_size: int, total: int) -> ShopeeDiscountDetailPaginationResponse:
    total_pages = max(1, (total + page_size - 1) // page_size)
    return ShopeeDiscountDetailPaginationResponse(page=page, page_size=page_size, total=total, total_pages=total_pages)


def _load_discount_campaign_or_404(db: Session, *, run_id: int, user_id: int, campaign_id: int) -> ShopeeDiscountCampaign:
    campaign = (
        db.query(ShopeeDiscountCampaign)
        .filter(
            ShopeeDiscountCampaign.id == campaign_id,
            ShopeeDiscountCampaign.run_id == run_id,
            ShopeeDiscountCampaign.user_id == user_id,
        )
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discount campaign not found")
    return campaign


def _load_addon_campaign_by_source_or_404(db: Session, *, run_id: int, user_id: int, source_campaign_id: int) -> ShopeeAddonCampaign:
    campaign = (
        db.query(ShopeeAddonCampaign)
        .options(selectinload(ShopeeAddonCampaign.main_items), selectinload(ShopeeAddonCampaign.reward_items))
        .filter(
            ShopeeAddonCampaign.run_id == run_id,
            ShopeeAddonCampaign.user_id == user_id,
            ShopeeAddonCampaign.source_campaign_id == source_campaign_id,
        )
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Add-on campaign not found")
    return campaign


def _addon_campaign_status(campaign: ShopeeAddonCampaign, *, current_tick: datetime) -> str:
    status_value = (campaign.campaign_status or "draft").strip().lower()
    if status_value in {"draft", "disabled"}:
        return status_value
    if campaign.start_at and current_tick < _align_compare_time(current_tick, campaign.start_at):
        return "upcoming"
    if campaign.end_at and current_tick > _align_compare_time(current_tick, campaign.end_at):
        return "ended"
    return "ongoing"


def _addon_detail_item_response_from_main(row: ShopeeAddonCampaignMainItem, *, stock: int) -> ShopeeDiscountDetailItemRowResponse:
    return ShopeeDiscountDetailItemRowResponse(
        item_id=row.id,
        product_name=f"主商品：{row.product_name_snapshot}",
        image_url=row.image_url_snapshot,
        sku=row.sku_snapshot,
        original_price=float(row.original_price_snapshot or 0),
        discount_type="main",
        discount_type_label="主商品",
        discount_value=0,
        final_price=float(row.original_price_snapshot or 0),
        stock=stock,
    )


def _addon_detail_item_response_from_reward(row: ShopeeAddonCampaignRewardItem, *, promotion_type: str, stock: int) -> ShopeeDiscountDetailItemRowResponse:
    addon_price = float(row.addon_price) if row.addon_price is not None else 0.0
    return ShopeeDiscountDetailItemRowResponse(
        item_id=row.id,
        product_name=f"{'加价商品' if promotion_type == 'add_on' else '赠品'}：{row.product_name_snapshot}",
        image_url=row.image_url_snapshot,
        sku=row.sku_snapshot,
        original_price=float(row.original_price_snapshot or 0),
        discount_type=promotion_type,
        discount_type_label=f"加价 RM {addon_price:.2f}" if promotion_type == "add_on" else f"赠品 ×{max(1, int(row.reward_qty or 1))}",
        discount_value=addon_price if promotion_type == "add_on" else 0,
        final_price=addon_price if promotion_type == "add_on" else 0,
        stock=stock,
    )


def _build_addon_detail_items_response(
    *,
    db: Session,
    campaign: ShopeeAddonCampaign,
    page: int,
    page_size: int,
) -> ShopeeDiscountDetailItemListResponse:
    main_items = sorted(campaign.main_items or [], key=lambda item: (item.sort_order, item.id))
    reward_items = sorted(campaign.reward_items or [], key=lambda item: (item.sort_order, item.id))
    combined: list[tuple[str, ShopeeAddonCampaignMainItem | ShopeeAddonCampaignRewardItem]] = [("main", item) for item in main_items] + [("reward", item) for item in reward_items]
    total = len(combined)
    page_rows = combined[(page - 1) * page_size : page * page_size]
    listing_ids = [int(item.listing_id) for _role, item in page_rows if item.listing_id]
    variant_ids = [int(item.variant_id) for _role, item in page_rows if item.variant_id]
    listing_stock_map: dict[int, int] = {}
    variant_stock_map: dict[int, int] = {}
    if listing_ids:
        listing_stock_map = {
            int(row.id): max(0, int(row.stock_available or 0))
            for row in db.query(ShopeeListing.id, ShopeeListing.stock_available).filter(ShopeeListing.id.in_(listing_ids)).all()
        }
    if variant_ids:
        variant_stock_map = {
            int(row.id): max(0, int(row.stock or 0))
            for row in db.query(ShopeeListingVariant.id, ShopeeListingVariant.stock).filter(ShopeeListingVariant.id.in_(variant_ids)).all()
        }

    rows: list[ShopeeDiscountDetailItemRowResponse] = []
    for role, item in page_rows:
        stock = variant_stock_map.get(int(item.variant_id), 0) if item.variant_id else listing_stock_map.get(int(item.listing_id), 0) if item.listing_id else 0
        if role == "main":
            rows.append(_addon_detail_item_response_from_main(item, stock=stock))
        else:
            rows.append(_addon_detail_item_response_from_reward(item, promotion_type=campaign.promotion_type, stock=stock))
    return ShopeeDiscountDetailItemListResponse(
        rows=rows,
        pagination=_build_discount_detail_pagination(page=page, page_size=page_size, total=total),
    )


def _build_discount_detail_items_response(
    *,
    db: Session,
    campaign_id: int,
    page: int,
    page_size: int,
) -> ShopeeDiscountDetailItemListResponse:
    query = db.query(ShopeeDiscountCampaignItem).filter(ShopeeDiscountCampaignItem.campaign_id == campaign_id)
    total = query.count()
    rows = (
        query.order_by(ShopeeDiscountCampaignItem.sort_order.asc(), ShopeeDiscountCampaignItem.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    listing_ids = [int(row.listing_id) for row in rows if row.listing_id]
    variant_ids = [int(row.variant_id) for row in rows if row.variant_id]
    listing_stock_map: dict[int, int] = {}
    variant_stock_map: dict[int, int] = {}
    if listing_ids:
        listing_stock_map = {
            int(row.id): max(0, int(row.stock_available or 0))
            for row in db.query(ShopeeListing.id, ShopeeListing.stock_available).filter(ShopeeListing.id.in_(listing_ids)).all()
        }
    if variant_ids:
        variant_stock_map = {
            int(row.id): max(0, int(row.stock or 0))
            for row in db.query(ShopeeListingVariant.id, ShopeeListingVariant.stock).filter(ShopeeListingVariant.id.in_(variant_ids)).all()
        }

    return ShopeeDiscountDetailItemListResponse(
        rows=[
            ShopeeDiscountDetailItemRowResponse(
                item_id=row.id,
                product_name=row.product_name_snapshot,
                image_url=row.image_url_snapshot,
                sku=row.sku_snapshot,
                original_price=float(row.original_price or 0),
                discount_type=row.discount_type,
                discount_type_label=_discount_item_type_label(row.discount_type),
                discount_value=float(row.discount_value or 0),
                final_price=float(row.final_price) if row.final_price is not None else None,
                stock=variant_stock_map.get(int(row.variant_id), 0) if row.variant_id else listing_stock_map.get(int(row.listing_id), 0) if row.listing_id else 0,
            )
            for row in rows
        ],
        pagination=_build_discount_detail_pagination(page=page, page_size=page_size, total=total),
    )


def _build_discount_detail_daily_response(
    *,
    db: Session,
    run_id: int,
    user_id: int,
    campaign_id: int,
    page: int,
    page_size: int,
) -> ShopeeDiscountDetailDailyListResponse:
    query = db.query(ShopeeDiscountPerformanceDaily).filter(
        ShopeeDiscountPerformanceDaily.run_id == run_id,
        ShopeeDiscountPerformanceDaily.user_id == user_id,
        ShopeeDiscountPerformanceDaily.campaign_id == campaign_id,
    )
    total = query.count()
    rows = (
        query.order_by(ShopeeDiscountPerformanceDaily.stat_date.asc(), ShopeeDiscountPerformanceDaily.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ShopeeDiscountDetailDailyListResponse(
        rows=[
            ShopeeDiscountDetailDailyRowResponse(
                stat_date=row.stat_date.strftime("%Y/%m/%d"),
                sales_amount=float(row.sales_amount or 0),
                orders_count=int(row.orders_count or 0),
                units_sold=int(row.units_sold or 0),
                buyers_count=int(row.buyers_count or 0),
            )
            for row in rows
        ],
        pagination=_build_discount_detail_pagination(page=page, page_size=page_size, total=total),
    )


def _resolve_discount_data_time_basis(value: str) -> str:
    safe_value = (value or "order_time").strip().lower()
    if safe_value not in {"order_time", "completed_time"}:
        return "order_time"
    return safe_value


def _resolve_discount_data_sort(value: str) -> str:
    safe_value = (value or "sales_amount").strip().lower()
    if safe_value not in {"sales_amount", "units_sold", "buyers_count", "discounted_price"}:
        return "sales_amount"
    return safe_value


def _resolve_discount_data_order(value: str) -> str:
    return "asc" if (value or "desc").strip().lower() == "asc" else "desc"


def _discount_data_order_query(db: Session, *, run_id: int, user_id: int, campaign_id: int, time_basis: str):
    query = db.query(ShopeeOrder).options(selectinload(ShopeeOrder.items)).filter(
        ShopeeOrder.run_id == run_id,
        ShopeeOrder.user_id == user_id,
        ShopeeOrder.marketing_campaign_id == campaign_id,
    )
    if time_basis == "completed_time":
        query = query.filter(ShopeeOrder.delivered_at.isnot(None))
    return query


def _addon_order_query(db: Session, *, run_id: int, user_id: int, addon_campaign_id: int, source_campaign_id: int, promotion_type: str, time_basis: str):
    item_order_ids = (
        db.query(ShopeeOrderItem.order_id)
        .filter(
            ShopeeOrderItem.marketing_campaign_type == promotion_type,
            ShopeeOrderItem.marketing_campaign_id == addon_campaign_id,
        )
        .subquery()
    )
    query = db.query(ShopeeOrder).options(selectinload(ShopeeOrder.items)).filter(
        ShopeeOrder.run_id == run_id,
        ShopeeOrder.user_id == user_id,
        or_(
            ShopeeOrder.marketing_campaign_id == source_campaign_id,
            ShopeeOrder.marketing_campaign_id == addon_campaign_id,
            ShopeeOrder.id.in_(select(item_order_ids.c.order_id)),
        ),
    )
    if time_basis == "completed_time":
        query = query.filter(ShopeeOrder.delivered_at.isnot(None))
    return query


def _bundle_order_query(db: Session, *, run_id: int, user_id: int, campaign_id: int, time_basis: str):
    item_order_ids = (
        db.query(ShopeeOrderItem.order_id)
        .filter(
            ShopeeOrderItem.marketing_campaign_type == "bundle",
            ShopeeOrderItem.marketing_campaign_id == campaign_id,
        )
        .subquery()
    )
    query = db.query(ShopeeOrder).options(selectinload(ShopeeOrder.items)).filter(
        ShopeeOrder.run_id == run_id,
        ShopeeOrder.user_id == user_id,
        or_(
            (ShopeeOrder.marketing_campaign_type == "bundle") & (ShopeeOrder.marketing_campaign_id == campaign_id),
            ShopeeOrder.id.in_(select(item_order_ids.c.order_id)),
        ),
    )
    if time_basis == "completed_time":
        query = query.filter(ShopeeOrder.delivered_at.isnot(None))
    return query


def _discount_data_stat_date(order: ShopeeOrder, *, run: GameRun, time_basis: str) -> date:
    value = order.delivered_at if time_basis == "completed_time" else order.created_at
    game_text = _format_discount_game_datetime(value or order.created_at, run=run)
    if game_text:
        return datetime.strptime(game_text[:10], "%Y-%m-%d").date()
    return (value or order.created_at).date()


def _discount_data_campaign_game_date_range(campaign: ShopeeDiscountCampaign, *, run: GameRun) -> tuple[date, date] | None:
    start_text = _format_discount_game_datetime(campaign.start_at or campaign.created_at, run=run)
    end_text = _format_discount_game_datetime(campaign.end_at or campaign.created_at, run=run)
    if not start_text or not end_text:
        return None
    start_date = datetime.strptime(start_text[:10], "%Y-%m-%d").date()
    end_date = datetime.strptime(end_text[:10], "%Y-%m-%d").date()
    if end_date < start_date:
        end_date = start_date
    return start_date, end_date


def _addon_data_campaign_game_date_range(campaign: ShopeeAddonCampaign, *, run: GameRun) -> tuple[date, date] | None:
    start_text = _format_discount_game_datetime(campaign.start_at or campaign.created_at, run=run)
    end_text = _format_discount_game_datetime(campaign.end_at or campaign.created_at, run=run)
    if not start_text or not end_text:
        return None
    start_date = datetime.strptime(start_text[:10], "%Y-%m-%d").date()
    end_date = datetime.strptime(end_text[:10], "%Y-%m-%d").date()
    if end_date < start_date:
        end_date = start_date
    return start_date, end_date


def _build_discount_data_analytics(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    campaign_id: int,
    time_basis: str,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[ShopeeDiscountDataMetricCardsResponse, ShopeeDiscountDataTrendResponse, dict[int, dict[str, Any]]]:
    orders = _discount_data_order_query(db, run_id=run.id, user_id=user_id, campaign_id=campaign_id, time_basis=time_basis).all()
    by_date: dict[date, dict[str, Any]] = {}
    ranking: dict[int, dict[str, Any]] = {}
    buyer_names: set[str] = set()
    sold_item_ids: set[int] = set()
    total_sales_amount = 0.0
    total_units_sold = 0
    total_orders_count = 0

    for order in orders:
        stat_date = _discount_data_stat_date(order, run=run, time_basis=time_basis)
        if date_from is not None and stat_date < date_from:
            continue
        if date_to is not None and stat_date >= date_to:
            continue
        total_orders_count += 1
        bucket = by_date.setdefault(
            stat_date,
            {"sales_amount": 0.0, "units_sold": 0, "orders_count": 0, "buyers": set(), "items": set()},
        )
        bucket["orders_count"] += 1
        bucket["buyers"].add(order.buyer_name)
        buyer_names.add(order.buyer_name)
        order_sales_amount = float(order.buyer_payment or 0)
        total_sales_amount += order_sales_amount
        bucket["sales_amount"] += order_sales_amount

        item_quantity = sum(int(item.quantity or 0) for item in (order.items or []))
        total_units_sold += item_quantity
        bucket["units_sold"] += item_quantity

        matched_items = (
            db.query(ShopeeDiscountCampaignItem)
            .filter(
                ShopeeDiscountCampaignItem.campaign_id == campaign_id,
                ShopeeDiscountCampaignItem.listing_id == order.listing_id,
                or_(ShopeeDiscountCampaignItem.variant_id == order.variant_id, ShopeeDiscountCampaignItem.variant_id.is_(None)),
            )
            .order_by(ShopeeDiscountCampaignItem.variant_id.desc(), ShopeeDiscountCampaignItem.id.asc())
            .all()
        )
        campaign_item = matched_items[0] if matched_items else None
        if campaign_item:
            sold_item_ids.add(campaign_item.id)
            bucket["items"].add(campaign_item.id)
            row = ranking.setdefault(
                campaign_item.id,
                {
                    "units_sold": 0,
                    "buyers": set(),
                    "sales_amount": 0.0,
                },
            )
            row["units_sold"] += item_quantity
            row["buyers"].add(order.buyer_name)
            row["sales_amount"] += order_sales_amount

    campaign = db.query(ShopeeDiscountCampaign).filter(ShopeeDiscountCampaign.id == campaign_id).first()
    campaign_range = _discount_data_campaign_game_date_range(campaign, run=run) if campaign else None
    if campaign_range:
        start_date, end_date = campaign_range
    elif by_date:
        start_date = min(by_date.keys())
        end_date = max(by_date.keys())
    else:
        start_date = date.today()
        end_date = start_date

    trend_rows: list[ShopeeDiscountDataTrendPointResponse] = []
    cursor = start_date
    while cursor <= end_date:
        bucket = by_date.get(cursor, {"sales_amount": 0.0, "units_sold": 0, "orders_count": 0, "buyers": set(), "items": set()})
        trend_rows.append(
            ShopeeDiscountDataTrendPointResponse(
                stat_date=cursor.strftime("%Y/%m/%d"),
                sales_amount=float(bucket["sales_amount"] or 0),
                units_sold=int(bucket["units_sold"] or 0),
                orders_count=int(bucket["orders_count"] or 0),
                buyers_count=len(bucket["buyers"]),
                items_sold=len(bucket["items"]),
            )
        )
        cursor += timedelta(days=1)

    # Compute monthly aggregates with proper deduplication for buyers and items
    by_month: dict[tuple[int, int], dict[str, Any]] = {}
    for d, bucket in by_date.items():
        month_key = (d.year, d.month)
        month_bucket = by_month.setdefault(month_key, {"sales_amount": 0.0, "units_sold": 0, "orders_count": 0, "buyers": set(), "items": set()})
        month_bucket["sales_amount"] += bucket["sales_amount"]
        month_bucket["units_sold"] += bucket["units_sold"]
        month_bucket["orders_count"] += bucket["orders_count"]
        month_bucket["buyers"] |= bucket["buyers"]
        month_bucket["items"] |= bucket["items"]

    monthly_rows: list[ShopeeDiscountDataTrendPointResponse] = []
    if date_from is not None and date_to is not None and date_from.month == 1 and date_from.day == 1 and date_to == date(date_from.year + 1, 1, 1):
        month_keys = [(date_from.year, month) for month in range(1, 13)]
    else:
        month_keys = sorted(by_month.keys())
    for yr, mo in month_keys:
        mb = by_month.get((yr, mo), {"sales_amount": 0.0, "units_sold": 0, "orders_count": 0, "buyers": set(), "items": set()})
        monthly_rows.append(
            ShopeeDiscountDataTrendPointResponse(
                stat_date=f"{yr}/{mo:02d}/01",
                sales_amount=float(mb["sales_amount"] or 0),
                units_sold=int(mb["units_sold"] or 0),
                orders_count=int(mb["orders_count"] or 0),
                buyers_count=len(mb["buyers"]),
                items_sold=len(mb["items"]),
            )
        )

    cards = ShopeeDiscountDataMetricCardsResponse(
        sales_amount=total_sales_amount,
        units_sold=total_units_sold,
        orders_count=total_orders_count,
        buyers_count=len(buyer_names),
        items_sold=len(sold_item_ids),
    )
    return cards, ShopeeDiscountDataTrendResponse(rows=trend_rows, monthly_rows=monthly_rows), ranking


def _discount_data_discount_label(row: ShopeeDiscountCampaignItem) -> str:
    if row.discount_type == "percent":
        value = float(row.discount_value or 0)
        return f"{int(value) if value.is_integer() else round(value, 1)}% OFF"
    if row.final_price is not None:
        return f"RM {float(row.final_price or 0):.2f}"
    return _discount_item_type_label(row.discount_type)


def _build_addon_data_analytics(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    campaign: ShopeeAddonCampaign,
    time_basis: str,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[ShopeeDiscountDataMetricCardsResponse, ShopeeDiscountDataTrendResponse, dict[int, dict[str, Any]]]:
    source_campaign_id = int(campaign.source_campaign_id or 0)
    orders = _addon_order_query(db, run_id=run.id, user_id=user_id, addon_campaign_id=campaign.id, source_campaign_id=source_campaign_id, promotion_type=campaign.promotion_type, time_basis=time_basis).all()
    by_date: dict[date, dict[str, Any]] = {}
    ranking: dict[int, dict[str, Any]] = {}
    buyer_names: set[str] = set()
    sold_item_ids: set[int] = set()
    total_sales_amount = 0.0
    total_units_sold = 0
    total_orders_count = 0

    for order in orders:
        stat_date = _discount_data_stat_date(order, run=run, time_basis=time_basis)
        if date_from is not None and stat_date < date_from:
            continue
        if date_to is not None and stat_date >= date_to:
            continue
        attributed_items = [
            item for item in (order.items or [])
            if item.marketing_campaign_type == campaign.promotion_type and int(item.marketing_campaign_id or 0) == campaign.id
        ]
        if campaign.promotion_type == "gift":
            matched_items = [
                item for item in (order.items or [])
                if any(
                    int(main_item.listing_id) == int(item.listing_id or 0)
                    and (main_item.variant_id is None or int(main_item.variant_id) == int(item.variant_id or 0))
                    for main_item in (campaign.main_items or [])
                )
                and item.line_role not in {"gift", "add_on"}
            ]
        else:
            matched_items = attributed_items
        total_orders_count += 1
        buyer_names.add(order.buyer_name)
        order_sales_amount = sum(float(item.discounted_unit_price or item.unit_price or 0) * int(item.quantity or 0) for item in matched_items)
        if not matched_items:
            order_sales_amount = float(order.buyer_payment or 0)
        item_quantity = sum(int(item.quantity or 0) for item in matched_items)
        total_sales_amount += order_sales_amount
        total_units_sold += item_quantity
        bucket = by_date.setdefault(stat_date, {"sales_amount": 0.0, "units_sold": 0, "orders_count": 0, "buyers": set(), "items": set()})
        bucket["orders_count"] += 1
        bucket["buyers"].add(order.buyer_name)
        bucket["sales_amount"] += order_sales_amount
        bucket["units_sold"] += item_quantity

        for item in matched_items:
            campaign_item = next(
                (
                    row for row in ((campaign.main_items or []) if campaign.promotion_type == "gift" else (campaign.reward_items or []))
                    if int(row.listing_id) == int(item.listing_id or 0) and (row.variant_id is None or int(row.variant_id) == int(item.variant_id or 0))
                ),
                None,
            )
            if not campaign_item:
                continue
            sold_item_ids.add(campaign_item.id)
            bucket["items"].add(campaign_item.id)
            row = ranking.setdefault(campaign_item.id, {"units_sold": 0, "buyers": set(), "sales_amount": 0.0})
            row["units_sold"] += int(item.quantity or 0)
            row["buyers"].add(order.buyer_name)
            row["sales_amount"] += float(item.discounted_unit_price or item.unit_price or 0) * int(item.quantity or 0)

    campaign_range = _addon_data_campaign_game_date_range(campaign, run=run)
    if campaign_range:
        start_date, end_date = campaign_range
    elif by_date:
        start_date = min(by_date.keys())
        end_date = max(by_date.keys())
    else:
        start_date = date.today()
        end_date = start_date

    trend_rows: list[ShopeeDiscountDataTrendPointResponse] = []
    cursor = start_date
    while cursor <= end_date:
        bucket = by_date.get(cursor, {"sales_amount": 0.0, "units_sold": 0, "orders_count": 0, "buyers": set(), "items": set()})
        trend_rows.append(ShopeeDiscountDataTrendPointResponse(stat_date=cursor.strftime("%Y/%m/%d"), sales_amount=float(bucket["sales_amount"] or 0), units_sold=int(bucket["units_sold"] or 0), orders_count=int(bucket["orders_count"] or 0), buyers_count=len(bucket["buyers"]), items_sold=len(bucket["items"])))
        cursor += timedelta(days=1)

    by_month: dict[tuple[int, int], dict[str, Any]] = {}
    for d, bucket in by_date.items():
        month_key = (d.year, d.month)
        month_bucket = by_month.setdefault(month_key, {"sales_amount": 0.0, "units_sold": 0, "orders_count": 0, "buyers": set(), "items": set()})
        month_bucket["sales_amount"] += bucket["sales_amount"]
        month_bucket["units_sold"] += bucket["units_sold"]
        month_bucket["orders_count"] += bucket["orders_count"]
        month_bucket["buyers"] |= bucket["buyers"]
        month_bucket["items"] |= bucket["items"]

    monthly_rows: list[ShopeeDiscountDataTrendPointResponse] = []
    if date_from is not None and date_to is not None and date_from.month == 1 and date_from.day == 1 and date_to == date(date_from.year + 1, 1, 1):
        month_keys = [(date_from.year, month) for month in range(1, 13)]
    else:
        month_keys = sorted(by_month.keys())
    for yr, mo in month_keys:
        mb = by_month.get((yr, mo), {"sales_amount": 0.0, "units_sold": 0, "orders_count": 0, "buyers": set(), "items": set()})
        monthly_rows.append(ShopeeDiscountDataTrendPointResponse(stat_date=f"{yr}/{mo:02d}/01", sales_amount=float(mb["sales_amount"] or 0), units_sold=int(mb["units_sold"] or 0), orders_count=int(mb["orders_count"] or 0), buyers_count=len(mb["buyers"]), items_sold=len(mb["items"])))

    cards = ShopeeDiscountDataMetricCardsResponse(
        sales_amount=total_sales_amount,
        units_sold=total_units_sold,
        orders_count=total_orders_count,
        buyers_count=len(buyer_names),
        items_sold=len(sold_item_ids),
    )
    return cards, ShopeeDiscountDataTrendResponse(rows=trend_rows, monthly_rows=monthly_rows), ranking


def _build_addon_data_ranking_response(
    *,
    campaign: ShopeeAddonCampaign,
    ranking_stats: dict[int, dict[str, Any]],
    page: int,
    page_size: int,
    sort: str,
    order: str,
) -> ShopeeDiscountDataRankingListResponse:
    rows: list[ShopeeDiscountDataRankingRowResponse] = []
    ranking_items = sorted(campaign.reward_items or [], key=lambda row: (row.sort_order, row.id)) if campaign.promotion_type == "add_on" else sorted(campaign.main_items or [], key=lambda row: (row.sort_order, row.id))
    for item in ranking_items:
        stats = ranking_stats.get(item.id, {"units_sold": 0, "buyers": set(), "sales_amount": 0.0})
        addon_price = float(getattr(item, "addon_price", None) or 0)
        rows.append(ShopeeDiscountDataRankingRowResponse(
            rank=0,
            campaign_item_id=item.id,
            product_id=int(item.listing_id) if item.listing_id else None,
            product_name=item.product_name_snapshot,
            image_url=item.image_url_snapshot,
            variation_name=item.variant_name_snapshot,
            original_price=float(item.original_price_snapshot or 0),
            discount_label=f"加价 RM {addon_price:.2f}" if campaign.promotion_type == "add_on" else "满额赠主商品",
            discounted_price=addon_price if campaign.promotion_type == "add_on" else float(item.original_price_snapshot or 0),
            units_sold=int(stats["units_sold"] or 0),
            buyers_count=len(stats["buyers"]),
            sales_amount=float(stats["sales_amount"] or 0),
        ))

    def sort_value(row: ShopeeDiscountDataRankingRowResponse) -> float:
        if sort == "units_sold":
            return float(row.units_sold)
        if sort == "buyers_count":
            return float(row.buyers_count)
        if sort == "discounted_price":
            return float(row.discounted_price or 0)
        return float(row.sales_amount)

    rows.sort(key=sort_value, reverse=order == "desc")
    for index, row in enumerate(rows, start=1):
        row.rank = index
    total = len(rows)
    start = (page - 1) * page_size
    end = start + page_size
    return ShopeeDiscountDataRankingListResponse(
        rows=rows[start:end],
        pagination=_build_discount_detail_pagination(page=page, page_size=page_size, total=total),
    )


def _build_discount_data_ranking_response(
    *,
    db: Session,
    campaign_id: int,
    ranking_stats: dict[int, dict[str, Any]],
    page: int,
    page_size: int,
    sort: str,
    order: str,
) -> ShopeeDiscountDataRankingListResponse:
    items = db.query(ShopeeDiscountCampaignItem).filter(ShopeeDiscountCampaignItem.campaign_id == campaign_id).all()
    variant_ids = [int(item.variant_id) for item in items if item.variant_id]
    variant_name_map: dict[int, str] = {}
    if variant_ids:
        variant_name_map = {
            int(row.id): (row.variant_name or row.option_value or "")
            for row in db.query(ShopeeListingVariant.id, ShopeeListingVariant.variant_name, ShopeeListingVariant.option_value).filter(ShopeeListingVariant.id.in_(variant_ids)).all()
        }
    rows: list[ShopeeDiscountDataRankingRowResponse] = []
    for item in items:
        stats = ranking_stats.get(item.id, {"units_sold": 0, "buyers": set(), "sales_amount": 0.0})
        rows.append(
            ShopeeDiscountDataRankingRowResponse(
                rank=0,
                campaign_item_id=item.id,
                product_id=int(item.listing_id) if item.listing_id else None,
                product_name=item.product_name_snapshot,
                image_url=item.image_url_snapshot,
                variation_name=variant_name_map.get(int(item.variant_id), "") if item.variant_id else None,
                original_price=float(item.original_price or 0),
                discount_label=_discount_data_discount_label(item),
                discounted_price=float(item.final_price) if item.final_price is not None else None,
                units_sold=int(stats["units_sold"] or 0),
                buyers_count=len(stats["buyers"]),
                sales_amount=float(stats["sales_amount"] or 0),
            )
        )

    def sort_value(row: ShopeeDiscountDataRankingRowResponse) -> float:
        if sort == "units_sold":
            return float(row.units_sold)
        if sort == "buyers_count":
            return float(row.buyers_count)
        if sort == "discounted_price":
            return float(row.discounted_price or 0)
        return float(row.sales_amount)

    rows.sort(key=sort_value, reverse=order == "desc")
    for index, row in enumerate(rows, start=1):
        row.rank = index
    total = len(rows)
    start = (page - 1) * page_size
    end = start + page_size
    return ShopeeDiscountDataRankingListResponse(
        rows=rows[start:end],
        pagination=_build_discount_detail_pagination(page=page, page_size=page_size, total=total),
    )


def _build_discount_data_response(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    campaign: ShopeeDiscountCampaign,
    current_tick: datetime,
    time_basis: str,
    selected_game_year: int = 0,
) -> ShopeeDiscountDataResponse:
    addon_campaign = _load_addon_campaign_by_source_or_404(db, run_id=run.id, user_id=user_id, source_campaign_id=campaign.id) if campaign.campaign_type == "add_on" else None
    campaign_range = _addon_data_campaign_game_date_range(addon_campaign, run=run) if addon_campaign else _discount_data_campaign_game_date_range(campaign, run=run)
    current_game_text = _format_discount_game_datetime(current_tick, run=run)
    current_game_date = datetime.strptime(current_game_text[:10], "%Y-%m-%d").date() if current_game_text else current_tick.date()

    if campaign_range:
        first_year = campaign_range[0].year
        last_year = max(campaign_range[1].year, current_game_date.year)
    else:
        first_year = run.created_at.year
        last_year = current_game_date.year

    available_years: list[dict] = []
    for y in range(first_year, last_year + 1):
        start_label = datetime(y, 1, 1).strftime("%Y-%m-%d")
        end_label = datetime(y + 1, 1, 1).strftime("%Y-%m-%d")
        available_years.append({"year": y, "label": f"{start_label} - {end_label}"})
    if not available_years:
        available_years.append({"year": current_game_date.year, "label": f"{current_game_date.year}-01-01 - {current_game_date.year + 1}-01-01"})

    year_values = [item["year"] for item in available_years]
    if selected_game_year > 0 and selected_game_year in year_values:
        selected_year = selected_game_year
    else:
        selected_year = current_game_date.year
        if selected_year not in year_values:
            selected_year = year_values[-1] if year_values else current_game_date.year

    year_start = date(selected_year, 1, 1)
    year_end = date(selected_year + 1, 1, 1)
    data_period_text = f"GMT+07 {selected_year}-01-01 00:00 - {selected_year + 1}-01-01 00:00"

    if addon_campaign:
        cards, trend, ranking_stats = _build_addon_data_analytics(
            db=db, run=run, user_id=user_id, campaign=addon_campaign, time_basis=time_basis,
            date_from=year_start, date_to=year_end,
        )
        campaign_type = addon_campaign.promotion_type
        campaign_type_label = _addon_promotion_type_label(addon_campaign.promotion_type)
        effective_status = _addon_campaign_status(addon_campaign, current_tick=current_tick)
        ranking = _build_addon_data_ranking_response(campaign=addon_campaign, ranking_stats=ranking_stats, page=1, page_size=10, sort="sales_amount", order="desc")
        campaign_name = addon_campaign.campaign_name
        start_at = addon_campaign.start_at
        end_at = addon_campaign.end_at
        market = addon_campaign.market
        currency = addon_campaign.currency
    else:
        cards, trend, ranking_stats = _build_discount_data_analytics(
            db=db, run=run, user_id=user_id, campaign_id=campaign.id, time_basis=time_basis,
            date_from=year_start, date_to=year_end,
        )
        campaign_type = campaign.campaign_type
        campaign_type_label = _discount_type_label(campaign.campaign_type)
        effective_status = _resolve_discount_campaign_status(campaign, current_tick=current_tick)
        ranking = _build_discount_data_ranking_response(db=db, campaign_id=campaign.id, ranking_stats=ranking_stats, page=1, page_size=10, sort="sales_amount", order="desc")
        campaign_name = campaign.campaign_name
        start_at = campaign.start_at
        end_at = campaign.end_at
        market = campaign.market
        currency = campaign.currency

    return ShopeeDiscountDataResponse(
        campaign_id=campaign.id,
        campaign_name=campaign_name,
        campaign_type=campaign_type,
        campaign_type_label=campaign_type_label,
        status=effective_status,
        status_label=_discount_status_label(effective_status),
        start_at=_format_discount_game_datetime(start_at, run=run),
        end_at=_format_discount_game_datetime(end_at, run=run),
        market=market,
        currency=currency,
        time_basis=time_basis,
        data_period_text=data_period_text,
        available_years=[ShopeeDiscountAvailableYear(**item) for item in available_years],
        selected_game_year=selected_year,
        metric_cards=cards,
        trend=trend,
        product_ranking=ranking,
        export_enabled=True,
    )


def _discount_percent_lookup_for_campaign(db: Session, *, campaign_id: int) -> dict[tuple[int | None, int | None], float]:
    rows = db.query(ShopeeDiscountCampaignItem).filter(ShopeeDiscountCampaignItem.campaign_id == campaign_id).all()
    result: dict[tuple[int | None, int | None], float] = {}
    for row in rows:
        if row.final_price is None or not row.original_price or row.original_price <= 0:
            continue
        pct = round(max(0.0, min(99.99, (1 - float(row.final_price) / float(row.original_price)) * 100)), 2)
        result[(int(row.listing_id) if row.listing_id else None, int(row.variant_id) if row.variant_id else None)] = pct
    return result


def _build_discount_detail_orders_response(
    *,
    db: Session,
    run_id: int,
    user_id: int,
    campaign_id: int,
    page: int,
    page_size: int,
    status_value: str,
    addon_campaign: ShopeeAddonCampaign | None = None,
) -> ShopeeDiscountDetailOrderListResponse:
    if addon_campaign:
        query = _addon_order_query(db, run_id=run_id, user_id=user_id, addon_campaign_id=addon_campaign.id, source_campaign_id=campaign_id, promotion_type=addon_campaign.promotion_type, time_basis="order_time")
    else:
        query = db.query(ShopeeOrder).filter(
            ShopeeOrder.run_id == run_id,
            ShopeeOrder.user_id == user_id,
            ShopeeOrder.marketing_campaign_id == campaign_id,
        )
    if status_value != "all":
        query = query.filter(ShopeeOrder.type_bucket == status_value)
    total = query.count()
    rows = (
        query.options(selectinload(ShopeeOrder.items))
        .order_by(desc(ShopeeOrder.created_at), desc(ShopeeOrder.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    discount_lookup = _discount_percent_lookup_for_campaign(db, campaign_id=campaign_id)
    mapped_rows: list[ShopeeDiscountDetailOrderRowResponse] = []
    for row in rows:
        product_names = [item.product_name for item in (row.items or []) if item.product_name]
        discount_percent = (
            discount_lookup.get((int(row.listing_id) if row.listing_id else None, int(row.variant_id) if row.variant_id else None))
            or discount_lookup.get((int(row.listing_id) if row.listing_id else None, None))
        )
        mapped_rows.append(
            ShopeeDiscountDetailOrderRowResponse(
                order_id=row.id,
                order_no=row.order_no,
                buyer_name=row.buyer_name,
                product_summary="、".join(product_names) if product_names else "-",
                buyer_payment=float(row.buyer_payment or 0),
                discount_percent=discount_percent,
                type_bucket=row.type_bucket,
                type_bucket_label=_order_type_bucket_label(row.type_bucket),
                created_at=row.created_at.strftime("%Y/%m/%d %H:%M"),
            )
        )
    return ShopeeDiscountDetailOrderListResponse(
        rows=mapped_rows,
        pagination=_build_discount_detail_pagination(page=page, page_size=page_size, total=total),
    )


def _addon_order_item_sku_map(db: Session, *, order_items: list[ShopeeOrderItem]) -> dict[tuple[int | None, int | None], str | None]:
    listing_ids = {int(item.listing_id) for item in order_items if item.listing_id}
    variant_ids = {int(item.variant_id) for item in order_items if item.variant_id}
    sku_map: dict[tuple[int | None, int | None], str | None] = {}
    if listing_ids:
        listings = db.query(ShopeeListing.id, ShopeeListing.sku_code, ShopeeListing.parent_sku).filter(ShopeeListing.id.in_(listing_ids)).all()
        for listing_id, sku_code, parent_sku in listings:
            sku_map[(int(listing_id), None)] = sku_code or parent_sku
    if variant_ids:
        variants = db.query(ShopeeListingVariant.id, ShopeeListingVariant.listing_id, ShopeeListingVariant.sku).filter(ShopeeListingVariant.id.in_(variant_ids)).all()
        for variant_id, listing_id, sku in variants:
            sku_map[(int(listing_id) if listing_id else None, int(variant_id))] = sku
    return sku_map


def _addon_order_line_type(item: ShopeeOrderItem, *, promotion_type: str) -> str:
    role = (item.line_role or "main").strip().lower()
    if role in {"add_on", "gift"} or item.marketing_campaign_type == promotion_type:
        return "gift" if promotion_type == "gift" else "addon"
    return "main"


def _addon_order_item_belongs_to_campaign(item: ShopeeOrderItem, *, campaign: ShopeeAddonCampaign) -> bool:
    if item.marketing_campaign_type == campaign.promotion_type and int(item.marketing_campaign_id or 0) == int(campaign.id):
        return True
    if item.line_role in {"add_on", "gift"}:
        return False
    return any(
        int(main_item.listing_id) == int(item.listing_id or 0)
        and (main_item.variant_id is None or int(main_item.variant_id) == int(item.variant_id or 0))
        for main_item in (campaign.main_items or [])
    )


def _bundle_rules_payload(campaign: ShopeeDiscountCampaign) -> dict[str, Any]:
    try:
        data = json.loads(campaign.rules_json or "{}")
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _bundle_type_label(bundle_type: str) -> str:
    return {
        "percent": "折扣比例",
        "fixed_amount": "固定金额减免",
        "bundle_price": "套餐价",
    }.get(bundle_type, bundle_type or "套餐优惠")


def _bundle_rule_text(campaign: ShopeeDiscountCampaign) -> str:
    rules = _bundle_rules_payload(campaign)
    bundle_type = str(rules.get("bundle_type") or "percent")
    tiers = rules.get("tiers") if isinstance(rules.get("tiers"), list) else []
    parts: list[str] = []
    for row in tiers:
        if not isinstance(row, dict):
            continue
        qty = int(row.get("buy_quantity") or 0)
        value = float(row.get("discount_value") or 0)
        if qty <= 0 or value <= 0:
            continue
        display_value = int(value) if value.is_integer() else round(value, 2)
        if bundle_type == "percent":
            parts.append(f"买 {qty} 件享 {display_value}% 折扣")
        elif bundle_type == "fixed_amount":
            parts.append(f"买 {qty} 件减 RM {display_value}")
        else:
            parts.append(f"买 {qty} 件套餐价 RM {display_value}")
    return "，".join(parts) or _bundle_type_label(bundle_type)


def _build_bundle_orders_response(*, db: Session, run: GameRun, user_id: int, campaign: ShopeeDiscountCampaign) -> ShopeeBundleOrdersResponse:
    orders = (
        _bundle_order_query(db, run_id=run.id, user_id=user_id, campaign_id=campaign.id, time_basis="order_time")
        .order_by(desc(ShopeeOrder.created_at), desc(ShopeeOrder.id))
        .all()
    )
    all_items = [item for order in orders for item in (order.items or [])]
    sku_map = _addon_order_item_sku_map(db, order_items=all_items)
    response_orders: list[ShopeeBundleOrderRowResponse] = []
    by_date: dict[date, dict[str, Any]] = {}
    total_sales = 0.0
    total_bundles = 0
    total_units = 0
    buyers: set[str] = set()
    for order in orders:
        bundle_items = [item for item in (order.items or []) if item.marketing_campaign_type == "bundle" and int(item.marketing_campaign_id or 0) == campaign.id]
        order_items = bundle_items or list(order.items or [])
        mapped_items: list[ShopeeBundleOrderItemResponse] = []
        subtotal_original = 0.0
        subtotal_current = 0.0
        order_units = 0
        for item in sorted(order_items, key=lambda row: row.id):
            qty = int(item.quantity or 0)
            current_price = float(item.discounted_unit_price or item.unit_price or 0)
            original_price = float(item.original_unit_price or item.unit_price or 0)
            subtotal_current += current_price * qty
            subtotal_original += original_price * qty
            order_units += qty
            sku = sku_map.get((int(item.listing_id) if item.listing_id else None, int(item.variant_id) if item.variant_id else None)) or sku_map.get((int(item.listing_id) if item.listing_id else None, None))
            mapped_items.append(
                ShopeeBundleOrderItemResponse(
                    id=str(item.id),
                    imageUrl=item.image_url,
                    name=item.product_name,
                    sku=sku,
                    variation=item.variant_name or "-",
                    priceCurrent=current_price,
                    qty=qty,
                )
            )
        order_sales = subtotal_current or float(order.buyer_payment or 0)
        total_sales += order_sales
        total_units += order_units
        total_bundles += 1
        buyers.add(order.buyer_name)
        stat_date = _discount_data_stat_date(order, run=run, time_basis="order_time")
        bucket = by_date.setdefault(stat_date, {"sales": 0.0, "orders": 0, "bundles": 0, "units": 0, "buyers": set()})
        bucket["sales"] += order_sales
        bucket["orders"] += 1
        bucket["bundles"] += 1
        bucket["units"] += order_units
        bucket["buyers"].add(order.buyer_name)
        response_orders.append(
            ShopeeBundleOrderRowResponse(
                id=order.order_no,
                status=_order_type_bucket_label(order.type_bucket),
                subtotalCurrent=order_sales,
                subtotalOriginal=subtotal_original if subtotal_original > 0 and abs(subtotal_original - order_sales) > 0.0001 else None,
                items=mapped_items,
            )
        )
    data_rows = [
        ShopeeBundleDataRowResponse(
            date=stat_date.strftime("%d-%m-%Y"),
            sales=float(bucket["sales"] or 0),
            orders=int(bucket["orders"] or 0),
            bundles=int(bucket["bundles"] or 0),
            units=int(bucket["units"] or 0),
            buyers=len(bucket["buyers"]),
            salesPerBuyer=(float(bucket["sales"] or 0) / len(bucket["buyers"])) if bucket["buyers"] else 0.0,
        )
        for stat_date, bucket in sorted(by_date.items(), key=lambda item: item[0], reverse=True)
    ]
    current_tick = _resolve_game_tick(db, run.id, user_id)
    status_value = _resolve_discount_campaign_status(campaign, current_tick=current_tick)
    rules = _bundle_rules_payload(campaign)
    purchase_limit = rules.get("purchase_limit")
    buyers_count = len(buyers)
    return ShopeeBundleOrdersResponse(
        campaign_id=campaign.id,
        campaign_name=campaign.campaign_name,
        status_label=_discount_status_label(status_value),
        start_at=_format_discount_game_datetime(campaign.start_at, run=run),
        end_at=_format_discount_game_datetime(campaign.end_at, run=run),
        purchase_limit=int(purchase_limit) if purchase_limit is not None else None,
        bundle_type_label=_bundle_type_label(str(rules.get("bundle_type") or "percent")),
        bundle_rule_text=_bundle_rule_text(campaign),
        data_period_text=f"GMT+08 {_format_discount_game_datetime(campaign.start_at, run=run) or '-'} - {_format_discount_game_datetime(campaign.end_at, run=run) or '-'}",
        order_count=len(response_orders),
        metric_cards=ShopeeBundleMetricCardsResponse(
            sales=total_sales,
            orders=len(response_orders),
            bundles=total_bundles,
            units=total_units,
            buyers=buyers_count,
            salesPerBuyer=(total_sales / buyers_count) if buyers_count else 0.0,
        ),
        orders=response_orders,
        data_rows=data_rows,
    )


def _build_addon_orders_response(*, db: Session, run: GameRun, user_id: int, campaign: ShopeeAddonCampaign) -> ShopeeAddonOrdersResponse:
    source_campaign_id = int(campaign.source_campaign_id or 0)
    orders = (
        _addon_order_query(
            db,
            run_id=run.id,
            user_id=user_id,
            addon_campaign_id=campaign.id,
            source_campaign_id=source_campaign_id,
            promotion_type=campaign.promotion_type,
            time_basis="order_time",
        )
        .order_by(desc(ShopeeOrder.created_at), desc(ShopeeOrder.id))
        .all()
    )
    matched_order_items = [
        item
        for order in orders
        for item in (order.items or [])
        if _addon_order_item_belongs_to_campaign(item, campaign=campaign)
    ]
    sku_map = _addon_order_item_sku_map(db, order_items=matched_order_items)
    response_orders: list[ShopeeAddonOrderRowResponse] = []
    for order in orders:
        order_items = sorted(
            [item for item in (order.items or []) if _addon_order_item_belongs_to_campaign(item, campaign=campaign)],
            key=lambda item: (0 if _addon_order_line_type(item, promotion_type=campaign.promotion_type) == "main" else 1, item.id),
        )
        if not order_items:
            continue
        mapped_items: list[ShopeeAddonOrderItemResponse] = []
        subtotal_original = 0.0
        subtotal_current = 0.0
        for item in order_items:
            original_price = float(item.original_unit_price or item.unit_price or 0)
            current_price = float(item.discounted_unit_price or item.unit_price or 0)
            qty = int(item.quantity or 0)
            subtotal_original += original_price * qty
            subtotal_current += current_price * qty
            sku = sku_map.get((int(item.listing_id) if item.listing_id else None, int(item.variant_id) if item.variant_id else None)) or sku_map.get((int(item.listing_id) if item.listing_id else None, None))
            mapped_items.append(
                ShopeeAddonOrderItemResponse(
                    id=str(item.id),
                    type=_addon_order_line_type(item, promotion_type=campaign.promotion_type),
                    imageUrl=item.image_url,
                    name=item.product_name,
                    sku=sku,
                    variation=item.variant_name or "-",
                    priceCurrent=current_price,
                    priceOriginal=original_price if abs(original_price - current_price) > 0.0001 else None,
                    qty=qty,
                )
            )
        response_orders.append(
            ShopeeAddonOrderRowResponse(
                id=order.order_no,
                status=_order_type_bucket_label(order.type_bucket),
                subtotalCurrent=subtotal_current or float(order.buyer_payment or 0),
                subtotalOriginal=subtotal_original if subtotal_original > 0 and abs(subtotal_original - (subtotal_current or float(order.buyer_payment or 0))) > 0.0001 else None,
                items=mapped_items,
            )
        )
    current_tick = _resolve_game_tick(db, run.id, user_id)
    status_value = _addon_campaign_status(campaign, current_tick=current_tick)
    return ShopeeAddonOrdersResponse(
        campaign_id=int(source_campaign_id or campaign.id),
        campaign_name=campaign.campaign_name,
        promotion_type=campaign.promotion_type,
        promotion_type_label=_addon_promotion_type_label(campaign.promotion_type),
        status_label=_discount_status_label(status_value),
        start_at=_format_discount_game_datetime(campaign.start_at, run=run),
        end_at=_format_discount_game_datetime(campaign.end_at, run=run),
        addon_purchase_limit=campaign.addon_purchase_limit,
        gift_min_spend=float(campaign.gift_min_spend) if campaign.gift_min_spend is not None else None,
        orders=response_orders,
    )


def _build_discount_detail_performance(
    *,
    db: Session,
    run_id: int,
    user_id: int,
    campaign_id: int,
    addon_campaign: ShopeeAddonCampaign | None = None,
) -> ShopeeDiscountDetailPerformanceResponse:
    if addon_campaign:
        cards, _trend, _ranking = _build_addon_data_analytics(db=db, run=addon_campaign.run, user_id=user_id, campaign=addon_campaign, time_basis="order_time")
        return ShopeeDiscountDetailPerformanceResponse(
            total_sales_amount=cards.sales_amount,
            total_orders_count=cards.orders_count,
            total_units_sold=cards.units_sold,
            total_buyers_count=cards.buyers_count,
        )
    aggregate = (
        db.query(
            func.coalesce(func.sum(ShopeeDiscountPerformanceDaily.sales_amount), 0.0),
            func.coalesce(func.sum(ShopeeDiscountPerformanceDaily.orders_count), 0),
            func.coalesce(func.sum(ShopeeDiscountPerformanceDaily.units_sold), 0),
            func.coalesce(func.sum(ShopeeDiscountPerformanceDaily.buyers_count), 0),
        )
        .filter(
            ShopeeDiscountPerformanceDaily.run_id == run_id,
            ShopeeDiscountPerformanceDaily.user_id == user_id,
            ShopeeDiscountPerformanceDaily.campaign_id == campaign_id,
        )
        .first()
        or (0.0, 0, 0, 0)
    )
    sales_amount, orders_count, units_sold, buyers_count = aggregate
    return ShopeeDiscountDetailPerformanceResponse(
        total_sales_amount=float(sales_amount or 0),
        total_orders_count=int(orders_count or 0),
        total_units_sold=int(units_sold or 0),
        total_buyers_count=int(buyers_count or 0),
    )


def _build_discount_detail_response(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    campaign: ShopeeDiscountCampaign,
    current_tick: datetime,
) -> ShopeeDiscountDetailResponse:
    addon_campaign = _load_addon_campaign_by_source_or_404(db, run_id=run.id, user_id=user_id, source_campaign_id=campaign.id) if campaign.campaign_type == "add_on" else None
    if addon_campaign:
        effective_status = _addon_campaign_status(addon_campaign, current_tick=current_tick)
        return ShopeeDiscountDetailResponse(
            campaign_id=campaign.id,
            campaign_name=addon_campaign.campaign_name,
            campaign_type=addon_campaign.promotion_type,
            campaign_type_label=_addon_promotion_type_label(addon_campaign.promotion_type),
            status=effective_status,
            status_label=_discount_status_label(effective_status),
            start_at=_format_discount_detail_datetime(addon_campaign.start_at),
            end_at=_format_discount_detail_datetime(addon_campaign.end_at),
            created_at=_format_discount_detail_datetime(addon_campaign.created_at) or "-",
            market=addon_campaign.market,
            currency=addon_campaign.currency,
            performance=_build_discount_detail_performance(db=db, run_id=run.id, user_id=user_id, campaign_id=campaign.id, addon_campaign=addon_campaign),
            items=_build_addon_detail_items_response(db=db, campaign=addon_campaign, page=1, page_size=10),
            daily_performance=_build_discount_detail_daily_response(db=db, run_id=run.id, user_id=user_id, campaign_id=campaign.id, page=1, page_size=10),
            orders=_build_discount_detail_orders_response(db=db, run_id=run.id, user_id=user_id, campaign_id=campaign.id, page=1, page_size=10, status_value="all", addon_campaign=addon_campaign),
        )
    effective_status = _resolve_discount_campaign_status(campaign, current_tick=current_tick)
    return ShopeeDiscountDetailResponse(
        campaign_id=campaign.id,
        campaign_name=campaign.campaign_name,
        campaign_type=campaign.campaign_type,
        campaign_type_label=_discount_type_label(campaign.campaign_type),
        status=effective_status,
        status_label=_discount_status_label(effective_status),
        start_at=_format_discount_detail_datetime(campaign.start_at),
        end_at=_format_discount_detail_datetime(campaign.end_at),
        created_at=_format_discount_detail_datetime(campaign.created_at) or "-",
        market=campaign.market,
        currency=campaign.currency,
        performance=_build_discount_detail_performance(db=db, run_id=run.id, user_id=user_id, campaign_id=campaign.id),
        items=_build_discount_detail_items_response(db=db, campaign_id=campaign.id, page=1, page_size=10),
        daily_performance=_build_discount_detail_daily_response(db=db, run_id=run.id, user_id=user_id, campaign_id=campaign.id, page=1, page_size=10),
        orders=_build_discount_detail_orders_response(db=db, run_id=run.id, user_id=user_id, campaign_id=campaign.id, page=1, page_size=10, status_value="all"),
    )


def _build_discount_bootstrap_payload(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    public_id: str,
    current_tick: datetime,
    read_only: bool,
    discount_type: str,
    status_value: str,
    search_field: str,
    keyword: str,
    date_from_raw: str | None,
    date_to_raw: str | None,
    page: int,
    page_size: int,
) -> ShopeeDiscountBootstrapResponse:
    pref = (
        db.query(ShopeeUserDiscountPreference)
        .filter(
            ShopeeUserDiscountPreference.run_id == run.id,
            ShopeeUserDiscountPreference.user_id == user_id,
        )
        .first()
    )
    date_from = _parse_discount_date(date_from_raw)
    date_to = _parse_discount_date(date_to_raw)
    selected_discount_type = discount_type if discount_type != "all" or not pref else (pref.selected_discount_type or "all")
    selected_status = status_value if status_value != "all" or not pref else (pref.selected_status or "all")
    selected_search_field = search_field if search_field != "campaign_name" or not pref else (pref.search_field or "campaign_name")
    selected_keyword = keyword if keyword.strip() or not pref else (pref.keyword or "")
    if not date_from_raw and pref and pref.date_from:
        date_from = pref.date_from.date()
    if not date_to_raw and pref and pref.date_to:
        date_to = pref.date_to.date()

    campaign_list = _build_discount_campaign_list_response(
        db=db,
        run=run,
        user_id=user_id,
        discount_type=selected_discount_type,
        status_value=selected_status,
        search_field=selected_search_field,
        keyword=selected_keyword,
        date_from=date_from,
        date_to=date_to,
        current_tick=current_tick,
        page=page,
        page_size=page_size,
        read_only=read_only,
    )

    create_cards = [
        ShopeeDiscountCreateCardResponse(
            type="discount",
            title="单品折扣",
            description="为单个商品设置折扣。",
            enabled=not read_only,
            target_route=f"/u/{public_id}/shopee/marketing/discount/create?type=discount" if public_id else "/shopee/marketing/discount/create?type=discount",
        ),
        ShopeeDiscountCreateCardResponse(
            type="bundle",
            title="套餐优惠",
            description="组合销售多个商品，提升客单价。",
            enabled=not read_only,
            target_route=f"/u/{public_id}/shopee/marketing/discount/create?type=bundle" if public_id else "/shopee/marketing/discount/create?type=bundle",
        ),
        ShopeeDiscountCreateCardResponse(
            type="add_on",
            title="加价购",
            description="购买主商品后可优惠加购关联商品。",
            enabled=not read_only,
            target_route=f"/u/{public_id}/shopee/marketing/discount/create?type=add_on" if public_id else "/shopee/marketing/discount/create?type=add_on",
        ),
    ]

    return ShopeeDiscountBootstrapResponse(
        meta=ShopeeDiscountBootstrapMetaResponse(
            run_id=run.id,
            user_id=user_id,
            market=(run.market or "MY").strip().upper() or "MY",
            currency="RM",
            read_only=read_only,
            current_tick=current_tick,
        ),
        create_cards=create_cards,
        tabs=_build_discount_tabs(db=db, run=run, user_id=user_id, active_discount_type=selected_discount_type),
        performance=_build_discount_performance(
            db=db,
            run=run,
            user_id=user_id,
            discount_type=selected_discount_type,
            status_value=selected_status,
            date_from=date_from,
            date_to=date_to,
            current_tick=current_tick,
        ),
        filters=ShopeeDiscountFiltersResponse(
            discount_type=selected_discount_type,
            status=selected_status,
            search_field=selected_search_field,
            keyword=selected_keyword,
            date_from=date_from.isoformat() if date_from else None,
            date_to=date_to.isoformat() if date_to else None,
        ),
        list=campaign_list,
        preferences=ShopeeDiscountPreferencesResponse(
            selected_discount_type=pref.selected_discount_type if pref else selected_discount_type,
            selected_status=pref.selected_status if pref else selected_status,
            search_field=pref.search_field if pref else selected_search_field,
            keyword=pref.keyword if pref and pref.keyword else selected_keyword,
            date_from=pref.date_from if pref else None,
            date_to=pref.date_to if pref else None,
            last_viewed_at=pref.last_viewed_at if pref else None,
        ),
    )


def _parse_discount_datetime(raw_value: str | None) -> datetime | None:
    value = (raw_value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _format_discount_game_datetime(value: datetime | None, *, run: GameRun) -> str | None:
    if value is None or run.created_at is None:
        return None
    aligned_value = _align_compare_time(run.created_at, value)
    elapsed_seconds = max(0.0, (aligned_value - run.created_at).total_seconds())
    game_seconds = round((elapsed_seconds / REAL_SECONDS_PER_GAME_DAY) * 24 * 60 * 60)
    game_base = datetime(run.created_at.year, 1, 1, 0, 0, 0)
    game_value = game_base + timedelta(seconds=game_seconds)
    return game_value.strftime("%Y-%m-%dT%H:%M")


def _parse_discount_game_datetime(raw_value: str | None, *, run: GameRun) -> datetime | None:
    parsed_value = _parse_discount_datetime(raw_value)
    if parsed_value is None or run.created_at is None:
        return parsed_value
    game_year_start = datetime(run.created_at.year, 1, 1, 0, 0, 0)
    game_elapsed_seconds = max(0.0, (parsed_value - game_year_start).total_seconds())
    real_elapsed_seconds = (game_elapsed_seconds / (24 * 60 * 60)) * REAL_SECONDS_PER_GAME_DAY
    return run.created_at + timedelta(seconds=real_elapsed_seconds)


def _compute_discount_final_price(*, original_price: float, discount_mode: str, discount_percent: float | None, final_price: float | None) -> tuple[float | None, float | None]:
    safe_original_price = float(original_price or 0)
    if safe_original_price <= 0:
        return None, None
    if discount_mode == "final_price":
        if final_price is None or float(final_price) <= 0 or float(final_price) >= safe_original_price:
            return None, None
        computed_percent = round((1 - float(final_price) / safe_original_price) * 100, 2)
        return computed_percent, round(float(final_price), 2)

    safe_percent = float(discount_percent or 0)
    if safe_percent < 1 or safe_percent > 99:
        return None, None
    computed_final_price = round(safe_original_price * (100 - safe_percent) / 100, 2)
    if computed_final_price <= 0 or computed_final_price >= safe_original_price:
        return None, None
    return round(safe_percent, 2), computed_final_price


def _resolve_bundle_discount_type(raw_value: str | None) -> str:
    value = (raw_value or "percent").strip().lower()
    return value if value in {"percent", "fixed_amount", "bundle_price"} else "percent"


def _load_discount_draft_or_404(db: Session, *, draft_id: int, run_id: int, user_id: int) -> ShopeeDiscountDraft:
    draft = (
        db.query(ShopeeDiscountDraft)
        .options(selectinload(ShopeeDiscountDraft.items))
        .filter(
            ShopeeDiscountDraft.id == draft_id,
            ShopeeDiscountDraft.run_id == run_id,
            ShopeeDiscountDraft.user_id == user_id,
        )
        .first()
    )
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="折扣草稿不存在")
    return draft


def _resolve_addon_promotion_type(raw_value: str | None) -> str:
    value = (raw_value or "add_on").strip().lower()
    return value if value in {"add_on", "gift"} else "add_on"


def _addon_promotion_type_label(promotion_type: str) -> str:
    return {"add_on": "加价购", "gift": "满额赠"}.get(promotion_type, promotion_type)


def _shopee_addon_bootstrap_cache_key(*, run_id: int, user_id: int, promotion_type: str, draft_id: int | None, source_campaign_id: int | None) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:add-on:create:bootstrap:{run_id}:{user_id}:{promotion_type}:{draft_id or 0}:{source_campaign_id or 0}"


def _shopee_addon_eligible_products_cache_key(*, run_id: int, user_id: int, role: str, promotion_type: str, keyword: str, page: int, page_size: int) -> str:
    payload = {"role": role, "promotion_type": promotion_type, "keyword": keyword.strip(), "page": page, "page_size": page_size}
    digest = hashlib.md5(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return f"{REDIS_PREFIX}:cache:shopee:add-on:eligible-products:{run_id}:{user_id}:{digest}"


def _shopee_addon_draft_cache_key(*, run_id: int, user_id: int, draft_id: int) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:add-on:draft:{run_id}:{user_id}:{draft_id}"


def _shopee_addon_detail_cache_key(*, run_id: int, user_id: int, campaign_id: int) -> str:
    return f"{REDIS_PREFIX}:cache:shopee:add-on:detail:{run_id}:{user_id}:{campaign_id}"


def _invalidate_shopee_addon_cache(*, run_id: int, user_id: int, draft_id: int | None = None, campaign_id: int | None = None) -> None:
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:add-on:create:bootstrap:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:add-on:eligible-products:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:add-on:active-map:{run_id}:{user_id}")
    if draft_id:
        cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:add-on:draft:{run_id}:{user_id}:{draft_id}")
    if campaign_id:
        cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:add-on:detail:{run_id}:{user_id}:{campaign_id}")


def _load_addon_draft_or_404(db: Session, *, draft_id: int, run_id: int, user_id: int) -> ShopeeAddonDraft:
    draft = (
        db.query(ShopeeAddonDraft)
        .options(selectinload(ShopeeAddonDraft.main_items), selectinload(ShopeeAddonDraft.reward_items))
        .filter(ShopeeAddonDraft.id == draft_id, ShopeeAddonDraft.run_id == run_id, ShopeeAddonDraft.user_id == user_id)
        .first()
    )
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="加价购草稿不存在")
    return draft


def _load_addon_campaign_or_404(db: Session, *, campaign_id: int, run_id: int, user_id: int) -> ShopeeAddonCampaign:
    campaign = (
        db.query(ShopeeAddonCampaign)
        .options(selectinload(ShopeeAddonCampaign.main_items), selectinload(ShopeeAddonCampaign.reward_items))
        .filter(ShopeeAddonCampaign.id == campaign_id, ShopeeAddonCampaign.run_id == run_id, ShopeeAddonCampaign.user_id == user_id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="加价购活动不存在")
    return campaign


def _build_discount_create_product_row(
    *,
    listing: ShopeeListing,
    variant: ShopeeListingVariant | None = None,
    discount_mode: str = "percent",
    discount_percent: float | None = 10.0,
    final_price: float | None = None,
    activity_stock_limit: int | None = None,
    conflict: bool = False,
    conflict_reason: str | None = None,
) -> ShopeeDiscountCreateProductRowResponse:
    original_price = float(variant.price if variant else listing.price)
    stock_available = int(variant.stock if variant else listing.stock_available)
    computed_percent, computed_final_price = _compute_discount_final_price(
        original_price=original_price,
        discount_mode=discount_mode,
        discount_percent=discount_percent,
        final_price=final_price,
    )
    return ShopeeDiscountCreateProductRowResponse(
        listing_id=listing.id,
        variant_id=variant.id if variant else None,
        product_name=listing.title,
        variant_name=variant.option_value if variant else "",
        category=listing.category or "",
        image_url=(variant.image_url if variant and variant.image_url else listing.cover_url),
        sku=(variant.sku if variant else listing.sku_code),
        original_price=round(original_price, 2),
        stock_available=stock_available,
        discount_mode=discount_mode,
        discount_percent=computed_percent,
        final_price=computed_final_price,
        activity_stock_limit=activity_stock_limit,
        conflict=conflict,
        conflict_reason=conflict_reason,
    )


def _build_discount_draft_detail_response(db: Session, draft: ShopeeDiscountDraft) -> ShopeeDiscountDraftDetailResponse:
    listing_ids = {item.listing_id for item in draft.items}
    variant_ids = {item.variant_id for item in draft.items if item.variant_id}
    listing_map = {
        row.id: row
        for row in db.query(ShopeeListing).filter(ShopeeListing.id.in_(listing_ids)).all()
    } if listing_ids else {}
    variant_map = {
        row.id: row
        for row in db.query(ShopeeListingVariant).filter(ShopeeListingVariant.id.in_(variant_ids)).all()
    } if variant_ids else {}
    rows = []
    for item in sorted(draft.items, key=lambda row: (row.sort_order, row.id)):
        listing = listing_map.get(item.listing_id)
        if not listing:
            continue
        variant = variant_map.get(item.variant_id) if item.variant_id else None
        rows.append(
            _build_discount_create_product_row(
                listing=listing,
                variant=variant,
                discount_mode=item.discount_mode,
                discount_percent=item.discount_percent,
                final_price=item.final_price,
                activity_stock_limit=item.activity_stock_limit,
            )
        )
    run = db.query(GameRun).filter(GameRun.id == draft.run_id).first()
    return ShopeeDiscountDraftDetailResponse(
        id=draft.id,
        campaign_type=draft.campaign_type,
        campaign_name=draft.campaign_name,
        start_at=_format_discount_game_datetime(draft.start_at, run=run) if run else None,
        end_at=_format_discount_game_datetime(draft.end_at, run=run) if run else None,
        status=draft.status,
        items=rows,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


def _build_addon_product_row(
    *,
    listing: ShopeeListing,
    variant: ShopeeListingVariant | None = None,
    promotion_type: str = "add_on",
    addon_price: float | None = None,
    reward_qty: int = 1,
    conflict: bool = False,
    conflict_reason: str | None = None,
) -> ShopeeAddonProductRowResponse:
    original_price = float(variant.price if variant else listing.price)
    suggested_addon_price = round(original_price * 0.8, 2) if original_price > 0 else None
    safe_addon_price = addon_price if addon_price is not None else (suggested_addon_price if promotion_type == "add_on" else None)
    return ShopeeAddonProductRowResponse(
        listing_id=listing.id,
        variant_id=variant.id if variant else None,
        product_id=listing.product_id,
        product_name=listing.title,
        variant_name=variant.option_value if variant else "",
        category=listing.category or "",
        image_url=(variant.image_url if variant and variant.image_url else listing.cover_url),
        sku=(variant.sku if variant else listing.sku_code),
        original_price=round(original_price, 2),
        stock_available=int(variant.stock if variant else listing.stock_available),
        addon_price=round(float(safe_addon_price), 2) if safe_addon_price is not None else None,
        reward_qty=max(1, int(reward_qty or 1)),
        suggested_addon_price=suggested_addon_price,
        can_be_gift=True,
        conflict=conflict,
        conflict_reason=conflict_reason,
    )


def _build_addon_eligible_products_response(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    keyword: str,
    page: int,
    page_size: int,
    promotion_type: str,
) -> ShopeeAddonEligibleProductsResponse:
    query = (
        db.query(ShopeeListing)
        .options(selectinload(ShopeeListing.variants))
        .filter(ShopeeListing.run_id == run.id, ShopeeListing.user_id == user_id, ShopeeListing.status == "live")
        .order_by(desc(ShopeeListing.updated_at), desc(ShopeeListing.id))
    )
    if keyword.strip():
        like = f"%{keyword.strip()}%"
        query = query.filter(or_(ShopeeListing.title.ilike(like), ShopeeListing.sku_code.ilike(like)))

    all_items: list[ShopeeAddonProductRowResponse] = []
    for listing in query.all():
        active_variants = [variant for variant in sorted(listing.variants, key=lambda row: row.sort_order) if variant.stock > 0 and variant.price > 0]
        if active_variants:
            for variant in active_variants:
                all_items.append(_build_addon_product_row(listing=listing, variant=variant, promotion_type=promotion_type))
        elif listing.stock_available > 0 and listing.price > 0:
            all_items.append(_build_addon_product_row(listing=listing, promotion_type=promotion_type))

    total = len(all_items)
    start = max(0, (page - 1) * page_size)
    end = start + page_size
    return ShopeeAddonEligibleProductsResponse(page=page, page_size=page_size, total=total, items=all_items[start:end])


def _hydrate_addon_payload_products(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    main_products: list[ShopeeAddonMainProductPayload],
    reward_products: list[ShopeeAddonRewardProductPayload],
) -> tuple[dict[int, ShopeeListing], dict[int, ShopeeListingVariant]]:
    listing_ids = {item.listing_id for item in main_products} | {item.listing_id for item in reward_products}
    variant_ids = {item.variant_id for item in main_products if item.variant_id} | {item.variant_id for item in reward_products if item.variant_id}
    listing_map = {
        row.id: row
        for row in db.query(ShopeeListing)
        .filter(ShopeeListing.run_id == run.id, ShopeeListing.user_id == user_id, ShopeeListing.id.in_(listing_ids))
        .all()
    } if listing_ids else {}
    variant_map = {row.id: row for row in db.query(ShopeeListingVariant).filter(ShopeeListingVariant.id.in_(variant_ids)).all()} if variant_ids else {}
    return listing_map, variant_map


def _validate_addon_payload(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    promotion_type: str,
    campaign_name: str,
    start_at: datetime | None,
    end_at: datetime | None,
    addon_purchase_limit: int | None,
    gift_min_spend: float | None,
    main_products: list[ShopeeAddonMainProductPayload],
    reward_products: list[ShopeeAddonRewardProductPayload],
) -> None:
    if not campaign_name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="活动名称不能为空")
    if len(campaign_name.strip()) > 25:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="活动名称不能超过 25 个字符")
    if not start_at or not end_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请完整填写活动时间")
    if start_at >= end_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开始时间必须早于结束时间")
    if end_at - start_at < timedelta(seconds=REAL_SECONDS_PER_GAME_HOUR):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="结束时间必须晚于开始时间至少 1 小时")
    if not main_products:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请至少添加 1 个主商品")
    if not reward_products:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请至少添加 1 个加购商品或赠品")
    if len(main_products) > 100 or len(reward_products) > 100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="主商品和加购/赠品商品均不能超过 100 个")
    if promotion_type == "add_on" and (addon_purchase_limit is None or addon_purchase_limit < 1 or addon_purchase_limit > 99):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="加价购限购数量必须在 1 到 99 之间")
    if promotion_type == "gift" and (gift_min_spend is None or float(gift_min_spend) <= 0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="满额赠最低消费门槛必须大于 0")

    listing_map, variant_map = _hydrate_addon_payload_products(db=db, run=run, user_id=user_id, main_products=main_products, reward_products=reward_products)
    for group, label in ((main_products, "主商品"), (reward_products, "加购商品或赠品")):
        seen: set[tuple[int, int | None]] = set()
        for item in group:
            key = (item.listing_id, item.variant_id)
            if key in seen:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"同一{label}不能重复添加")
            seen.add(key)
            listing = listing_map.get(item.listing_id)
            if not listing or listing.status != "live":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"所选{label}不存在或不是上架状态")
            variant = variant_map.get(item.variant_id) if item.variant_id else None
            if item.variant_id and (not variant or variant.listing_id != listing.id):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"所选{label}规格不存在")
            price = float(variant.price if variant else listing.price)
            stock = int(variant.stock if variant else listing.stock_available)
            if price <= 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{label}原价必须大于 0")
            if stock <= 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{label}库存不足")

    if promotion_type == "add_on":
        for item in reward_products:
            listing = listing_map.get(item.listing_id)
            variant = variant_map.get(item.variant_id) if item.variant_id else None
            original_price = float(variant.price if variant else listing.price) if listing else 0
            if item.addon_price is None or float(item.addon_price) <= 0 or float(item.addon_price) >= original_price:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="加价购价必须大于 0 且小于原价")


def _build_addon_draft_detail_response(db: Session, draft: ShopeeAddonDraft) -> ShopeeAddonDraftDetailResponse:
    run = db.query(GameRun).filter(GameRun.id == draft.run_id).first()
    main_payload = [ShopeeAddonMainProductPayload(listing_id=item.listing_id, variant_id=item.variant_id) for item in draft.main_items]
    reward_payload = [ShopeeAddonRewardProductPayload(listing_id=item.listing_id, variant_id=item.variant_id, addon_price=item.addon_price, reward_qty=item.reward_qty) for item in draft.reward_items]
    listing_map, variant_map = _hydrate_addon_payload_products(db=db, run=run, user_id=draft.user_id, main_products=main_payload, reward_products=reward_payload) if run else ({}, {})
    main_rows = []
    for item in sorted(draft.main_items, key=lambda row: (row.sort_order, row.id)):
        listing = listing_map.get(item.listing_id)
        if listing:
            main_rows.append(_build_addon_product_row(listing=listing, variant=variant_map.get(item.variant_id) if item.variant_id else None, promotion_type=draft.promotion_type))
    reward_rows = []
    for item in sorted(draft.reward_items, key=lambda row: (row.sort_order, row.id)):
        listing = listing_map.get(item.listing_id)
        if listing:
            reward_rows.append(_build_addon_product_row(listing=listing, variant=variant_map.get(item.variant_id) if item.variant_id else None, promotion_type=draft.promotion_type, addon_price=item.addon_price, reward_qty=item.reward_qty))
    return ShopeeAddonDraftDetailResponse(
        id=draft.id,
        promotion_type=draft.promotion_type,
        campaign_name=draft.campaign_name,
        start_at=_format_discount_game_datetime(draft.start_at, run=run) if run else None,
        end_at=_format_discount_game_datetime(draft.end_at, run=run) if run else None,
        addon_purchase_limit=draft.addon_purchase_limit,
        gift_min_spend=draft.gift_min_spend,
        draft_status=draft.draft_status,
        main_products=main_rows,
        reward_products=reward_rows,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


def _build_addon_create_bootstrap_payload(*, db: Session, run: GameRun, user_id: int, current_tick: datetime, read_only: bool, promotion_type: str, draft: ShopeeAddonDraft | None = None) -> ShopeeAddonCreateBootstrapResponse:
    detail = _build_addon_draft_detail_response(db, draft) if draft else None
    return ShopeeAddonCreateBootstrapResponse(
        meta=ShopeeDiscountCreateMetaResponse(run_id=run.id, user_id=user_id, campaign_type=promotion_type, read_only=read_only, current_tick=current_tick),
        form=ShopeeAddonCreateFormResponse(
            campaign_name=draft.campaign_name if draft else "",
            start_at=detail.start_at if detail else _format_discount_game_datetime(current_tick, run=run),
            end_at=detail.end_at if detail else _format_discount_game_datetime(current_tick + timedelta(seconds=REAL_SECONDS_PER_GAME_HOUR), run=run),
            addon_purchase_limit=draft.addon_purchase_limit if draft else 1,
            gift_min_spend=draft.gift_min_spend if draft else None,
        ),
        rules=ShopeeAddonCreateRulesResponse(),
        selected_main_products=detail.main_products if detail else [],
        selected_reward_products=detail.reward_products if detail else [],
        product_picker=ShopeeDiscountCreateProductPickerResponse(default_page_size=20),
        draft=ShopeeDiscountCreateDraftSummaryResponse(id=draft.id, updated_at=draft.updated_at) if draft else None,
    )


def _build_addon_campaign_detail_response(db: Session, campaign: ShopeeAddonCampaign, *, current_tick: datetime) -> ShopeeAddonCampaignDetailResponse:
    main_rows = [
        ShopeeAddonProductRowResponse(
            listing_id=item.listing_id,
            variant_id=item.variant_id,
            product_id=item.product_id,
            product_name=item.product_name_snapshot,
            variant_name=item.variant_name_snapshot or "",
            image_url=item.image_url_snapshot,
            sku=item.sku_snapshot,
            original_price=item.original_price_snapshot,
            stock_available=item.stock_snapshot,
        )
        for item in sorted(campaign.main_items, key=lambda row: (row.sort_order, row.id))
    ]
    reward_rows = [
        ShopeeAddonProductRowResponse(
            listing_id=item.listing_id,
            variant_id=item.variant_id,
            product_id=item.product_id,
            product_name=item.product_name_snapshot,
            variant_name=item.variant_name_snapshot or "",
            image_url=item.image_url_snapshot,
            sku=item.sku_snapshot,
            original_price=item.original_price_snapshot,
            stock_available=item.stock_snapshot,
            addon_price=item.addon_price,
            reward_qty=item.reward_qty,
        )
        for item in sorted(campaign.reward_items, key=lambda row: (row.sort_order, row.id))
    ]
    status_value = _resolve_discount_campaign_status(campaign, current_tick=current_tick)
    return ShopeeAddonCampaignDetailResponse(
        campaign_id=campaign.id,
        campaign_name=campaign.campaign_name,
        promotion_type=campaign.promotion_type,
        promotion_type_label=_addon_promotion_type_label(campaign.promotion_type),
        campaign_status=status_value,
        status_label=_discount_status_label(status_value),
        start_at=_format_discount_game_datetime(campaign.start_at, run=campaign.run),
        end_at=_format_discount_game_datetime(campaign.end_at, run=campaign.run),
        addon_purchase_limit=campaign.addon_purchase_limit,
        gift_min_spend=campaign.gift_min_spend,
        main_products=main_rows,
        reward_products=reward_rows,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


def _build_discount_create_bootstrap_payload(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    current_tick: datetime,
    read_only: bool,
    campaign_type: str,
    draft: ShopeeDiscountDraft | None = None,
) -> ShopeeDiscountCreateBootstrapResponse:
    start_at = _format_discount_game_datetime(draft.start_at, run=run) if draft and draft.start_at else _format_discount_game_datetime(current_tick, run=run)
    end_at = _format_discount_game_datetime(draft.end_at, run=run) if draft and draft.end_at else _format_discount_game_datetime(current_tick + timedelta(seconds=REAL_SECONDS_PER_GAME_HOUR), run=run)
    selected_products: list[ShopeeDiscountCreateProductRowResponse] = []
    if draft:
        selected_products = _build_discount_draft_detail_response(db, draft).items

    return ShopeeDiscountCreateBootstrapResponse(
        meta=ShopeeDiscountCreateMetaResponse(
            run_id=run.id,
            user_id=user_id,
            campaign_type=campaign_type,
            read_only=read_only,
            current_tick=current_tick,
        ),
        form=ShopeeDiscountCreateFormResponse(
            campaign_name=draft.campaign_name if draft else "",
            start_at=start_at,
            end_at=end_at,
        ),
        rules=ShopeeDiscountCreateRulesResponse(),
        selected_products=selected_products,
        product_picker=ShopeeDiscountCreateProductPickerResponse(default_page_size=20),
        draft=ShopeeDiscountCreateDraftSummaryResponse(id=draft.id, updated_at=draft.updated_at) if draft else None,
    )


def _build_shipping_fee_promotion_create_bootstrap_payload(
    *,
    run: GameRun,
    user_id: int,
    current_tick: datetime,
    read_only: bool,
) -> ShopeeShippingFeePromotionCreateBootstrapResponse:
    start_at = _format_discount_game_datetime(current_tick, run=run) or ""
    end_at = _format_discount_game_datetime(current_tick + timedelta(seconds=REAL_SECONDS_PER_GAME_HOUR), run=run) or ""
    return ShopeeShippingFeePromotionCreateBootstrapResponse(
        meta=ShopeeShippingFeePromotionMetaResponse(
            run_id=run.id,
            user_id=user_id,
            read_only=read_only,
            current_tick=start_at,
            currency="RM",
        ),
        form=ShopeeShippingFeePromotionCreateFormResponse(
            start_at=start_at,
            end_at=end_at,
            tiers=[ShopeeShippingFeePromotionTierFormResponse(tier_index=1)],
        ),
        channels=[
            ShopeeShippingFeePromotionChannelOptionResponse(key=key, label=label, enabled=True)
            for key, label in SHOPEE_SHIPPING_FEE_PROMOTION_CHANNELS.items()
        ],
        rules=ShopeeShippingFeePromotionRulesResponse(),
    )


def _resolve_shipping_fee_promotion_status(row: ShopeeShippingFeePromotionCampaign, *, current_tick: datetime) -> str:
    if row.status == "stopped":
        return "stopped"
    if row.budget_type == "selected" and row.budget_limit is not None and float(row.budget_used or 0) >= float(row.budget_limit):
        return "budget_exhausted"
    if current_tick < _align_compare_time(current_tick, row.start_at):
        return "upcoming"
    if row.period_type == "selected" and row.end_at is not None and current_tick >= _align_compare_time(current_tick, row.end_at):
        return "ended"
    return "ongoing"


def _shipping_fee_promotion_status_label(status_value: str) -> str:
    return {
        "upcoming": "即将开始",
        "ongoing": "进行中",
        "ended": "已结束",
        "budget_exhausted": "预算用尽",
        "stopped": "已停止",
    }.get(status_value, status_value)


def _format_shipping_fee_promotion_period(row: ShopeeShippingFeePromotionCampaign, *, run: GameRun) -> str:
    if row.period_type == "no_limit" or row.end_at is None:
        return "无期限"
    start_text = _format_discount_game_datetime(row.start_at, run=run) or ""
    end_text = _format_discount_game_datetime(row.end_at, run=run) or ""
    return f"{start_text.replace('T', ' ')} - {end_text.replace('T', ' ')}"


def _format_shipping_fee_promotion_budget(row: ShopeeShippingFeePromotionCampaign) -> tuple[str, str]:
    budget_text = "无限制" if row.budget_type == "no_limit" or row.budget_limit is None else f"RM {float(row.budget_limit):.2f}"
    return budget_text, f"RM {float(row.budget_used or 0):.2f}"


def _format_shipping_fee_promotion_tier_summary(tiers: list[ShopeeShippingFeePromotionTier]) -> str:
    parts = []
    for tier in sorted(tiers, key=lambda item: (item.min_spend_amount, item.tier_index)):
        min_spend = f"RM{float(tier.min_spend_amount):.2f}"
        if tier.fee_type == "free_shipping":
            parts.append(f"满 {min_spend} 免运费")
        else:
            fixed_fee = float(tier.fixed_fee_amount or 0)
            parts.append(f"满 {min_spend}，运费减 RM{fixed_fee:.2f}")
    return "；".join(parts)


def _build_shipping_fee_promotion_row(row: ShopeeShippingFeePromotionCampaign, *, run: GameRun, current_tick: datetime) -> ShopeeShippingFeePromotionRowResponse:
    status_value = _resolve_shipping_fee_promotion_status(row, current_tick=current_tick)
    budget_text, budget_used_text = _format_shipping_fee_promotion_budget(row)
    channels_text = "、".join(channel.channel_label for channel in sorted(row.channels, key=lambda item: item.id))
    return ShopeeShippingFeePromotionRowResponse(
        id=row.id,
        promotion_name=row.promotion_name,
        status=status_value,
        status_label=_shipping_fee_promotion_status_label(status_value),
        period=_format_shipping_fee_promotion_period(row, run=run),
        budget_text=budget_text,
        budget_used_text=budget_used_text,
        channels_text=channels_text,
        tier_summary=_format_shipping_fee_promotion_tier_summary(list(row.tiers or [])),
        order_count=int(row.order_count or 0),
        shipping_discount_amount=float(row.shipping_discount_amount or 0),
    )


def _build_shipping_fee_promotion_list_response(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    status_value: str,
    page: int,
    page_size: int,
) -> ShopeeShippingFeePromotionListResponse:
    current_tick = _resolve_game_tick(db, run.id, user_id)
    rows = db.query(ShopeeShippingFeePromotionCampaign).options(
        selectinload(ShopeeShippingFeePromotionCampaign.channels),
        selectinload(ShopeeShippingFeePromotionCampaign.tiers),
    ).filter(
        ShopeeShippingFeePromotionCampaign.run_id == run.id,
        ShopeeShippingFeePromotionCampaign.user_id == user_id,
    ).order_by(ShopeeShippingFeePromotionCampaign.created_at.desc(), ShopeeShippingFeePromotionCampaign.id.desc()).all()
    built_rows = [_build_shipping_fee_promotion_row(row, run=run, current_tick=current_tick) for row in rows]
    counts = {key: 0 for key in ["ongoing", "upcoming", "ended"]}
    for item in built_rows:
        if item.status == "ongoing":
            counts["ongoing"] += 1
        elif item.status == "upcoming":
            counts["upcoming"] += 1
        elif item.status in {"ended", "budget_exhausted", "stopped"}:
            counts["ended"] += 1
    if status_value == "ongoing":
        filtered_rows = [item for item in built_rows if item.status == "ongoing"]
    elif status_value == "upcoming":
        filtered_rows = [item for item in built_rows if item.status == "upcoming"]
    elif status_value == "ended":
        filtered_rows = [item for item in built_rows if item.status in {"ended", "budget_exhausted", "stopped"}]
    else:
        filtered_rows = built_rows
    total = len(filtered_rows)
    start = max(0, (page - 1) * page_size)
    return ShopeeShippingFeePromotionListResponse(
        tabs=[
            ShopeeShippingFeePromotionTabResponse(key="全部", status="all", count=len(built_rows)),
            ShopeeShippingFeePromotionTabResponse(key="进行中", status="ongoing", count=counts["ongoing"]),
            ShopeeShippingFeePromotionTabResponse(key="即将开始", status="upcoming", count=counts["upcoming"]),
            ShopeeShippingFeePromotionTabResponse(key="已结束", status="ended", count=counts["ended"]),
        ],
        list=ShopeeShippingFeePromotionListPageResponse(page=page, page_size=page_size, total=total, items=filtered_rows[start:start + page_size]),
    )


def _validate_shipping_fee_promotion_create_payload(
    *,
    payload: ShopeeShippingFeePromotionCreateRequest,
    start_at: datetime | None,
    end_at: datetime | None,
) -> list[ShopeeShippingFeePromotionTierPayload]:
    promotion_name = payload.promotion_name.strip()
    if not promotion_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入运费促销名称")
    if len(promotion_name) > 20:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="运费促销名称最多 20 个字符")
    if payload.period_type not in {"no_limit", "selected"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="期限类型不支持")
    if payload.period_type == "selected":
        if start_at is None or end_at is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择自定义期限")
        if start_at >= end_at:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="结束时间必须晚于开始时间")
    if payload.budget_type not in {"no_limit", "selected"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="预算类型不支持")
    if payload.budget_type == "selected" and (payload.budget_limit is None or payload.budget_limit <= 0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="自定义预算必须大于 0")
    if not payload.channels:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请至少选择一个物流渠道")
    invalid_channels = [item for item in payload.channels if item not in SHOPEE_SHIPPING_FEE_PROMOTION_CHANNELS]
    if invalid_channels:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="物流渠道不支持")
    if not (1 <= len(payload.tiers) <= 3):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="运费层级数量必须为 1 到 3 个")
    sorted_tiers = sorted(payload.tiers, key=lambda item: item.min_spend_amount)
    seen_min_spend: set[float] = set()
    previous_rank = -1
    previous_fixed_fee: float | None = None
    for tier in sorted_tiers:
        if tier.min_spend_amount < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="最低消费金额必须大于等于 0")
        if tier.min_spend_amount in seen_min_spend:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="同一活动内层级门槛不能重复")
        seen_min_spend.add(tier.min_spend_amount)
        if tier.fee_type not in {"fixed_fee", "free_shipping"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="运费类型不支持")
        rank = 2 if tier.fee_type == "free_shipping" else 1
        if rank < previous_rank:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="高门槛层级的优惠力度不能低于低门槛层级")
        if tier.fee_type == "fixed_fee":
            if tier.fixed_fee_amount is None or tier.fixed_fee_amount < 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="运费减免金额必须大于等于 0")
            if previous_fixed_fee is not None and tier.fixed_fee_amount < previous_fixed_fee:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="高门槛层级的运费减免金额不能低于低门槛层级")
            previous_fixed_fee = tier.fixed_fee_amount
        previous_rank = max(previous_rank, rank)
    return sorted_tiers



def _build_voucher_create_bootstrap_payload(
    *,
    run: GameRun,
    user_id: int,
    current_tick: datetime,
    read_only: bool,
    voucher_type: str,
) -> ShopeeVoucherCreateBootstrapResponse:
    safe_voucher_type = (voucher_type or "shop_voucher").strip().lower() or "shop_voucher"
    if safe_voucher_type == "product_voucher":
        applicable_scope = "selected_products"
        display_type = "all_pages"
        audience_scope = ""
    elif safe_voucher_type == "private_voucher":
        applicable_scope = "all_products"
        display_type = "code_only"
        audience_scope = "private_code"
    elif safe_voucher_type == "live_voucher":
        applicable_scope = "all_products"
        display_type = "live_stream"
        audience_scope = ""
    elif safe_voucher_type == "video_voucher":
        applicable_scope = "all_products"
        display_type = "video_stream"
        audience_scope = ""
    else:
        applicable_scope = "all_shop_products"
        display_type = "all_pages"
        audience_scope = ""
    return ShopeeVoucherCreateBootstrapResponse(
        meta=ShopeeVoucherCreateMetaResponse(
            run_id=run.id,
            user_id=user_id,
            voucher_type=safe_voucher_type,
            read_only=read_only,
            current_tick=current_tick,
            currency="RM",
        ),
        form=ShopeeVoucherCreateFormResponse(
            start_at=_format_discount_game_datetime(current_tick, run=run) or "",
            end_at=_format_discount_game_datetime(current_tick + timedelta(seconds=REAL_SECONDS_PER_GAME_HOUR), run=run) or "",
            display_type=display_type,
            applicable_scope=applicable_scope,
            audience_scope=audience_scope,
        ),
        rules=ShopeeVoucherCreateRulesResponse(),
        product_picker=ShopeeVoucherProductPickerResponse() if safe_voucher_type in {"product_voucher", "private_voucher", "live_voucher", "video_voucher"} else None,
        selected_products=[],
    )


def _build_follow_voucher_create_bootstrap_payload(
    *,
    run: GameRun,
    user_id: int,
    current_tick: datetime,
    read_only: bool,
) -> ShopeeFollowVoucherCreateBootstrapResponse:
    return ShopeeFollowVoucherCreateBootstrapResponse(
        meta=ShopeeVoucherCreateMetaResponse(
            run_id=run.id,
            user_id=user_id,
            voucher_type="follow_voucher",
            read_only=read_only,
            current_tick=current_tick,
            currency="RM",
        ),
        form=ShopeeFollowVoucherCreateFormResponse(
            claim_start_at=_format_discount_game_datetime(current_tick, run=run) or "",
            claim_end_at=_format_discount_game_datetime(current_tick + timedelta(seconds=REAL_SECONDS_PER_GAME_HOUR), run=run) or "",
            valid_days_after_claim=7,
            reward_type="discount",
            discount_type="fixed_amount",
            max_discount_type="set_amount",
            per_buyer_limit=1,
            trigger_type="follow_shop",
            display_type="follow_reward",
            applicable_scope="all_products",
        ),
        rules=ShopeeFollowVoucherCreateRulesResponse(),
    )


def _normalize_shop_voucher_code_suffix(raw_value: str) -> str:
    code_suffix = (raw_value or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{1,5}", code_suffix):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="代金券代码后缀仅允许 A-Z、0-9，且最多 5 个字符")
    return code_suffix



def _resolve_voucher_code_exists(*, db: Session, run: GameRun, user_id: int, voucher_code: str) -> bool:
    shop_exists = db.query(ShopeeShopVoucherCampaign.id).filter(
        ShopeeShopVoucherCampaign.run_id == run.id,
        ShopeeShopVoucherCampaign.user_id == user_id,
        ShopeeShopVoucherCampaign.voucher_code == voucher_code,
    ).first()
    if shop_exists:
        return True
    product_exists = db.query(ShopeeProductVoucherCampaign.id).filter(
        ShopeeProductVoucherCampaign.run_id == run.id,
        ShopeeProductVoucherCampaign.user_id == user_id,
        ShopeeProductVoucherCampaign.voucher_code == voucher_code,
    ).first()
    if product_exists:
        return True
    private_exists = db.query(ShopeePrivateVoucherCampaign.id).filter(
        ShopeePrivateVoucherCampaign.run_id == run.id,
        ShopeePrivateVoucherCampaign.user_id == user_id,
        ShopeePrivateVoucherCampaign.voucher_code == voucher_code,
    ).first()
    if private_exists:
        return True
    live_exists = db.query(ShopeeLiveVoucherCampaign.id).filter(
        ShopeeLiveVoucherCampaign.run_id == run.id,
        ShopeeLiveVoucherCampaign.user_id == user_id,
        ShopeeLiveVoucherCampaign.voucher_code == voucher_code,
    ).first()
    if live_exists:
        return True
    video_exists = db.query(ShopeeVideoVoucherCampaign.id).filter(
        ShopeeVideoVoucherCampaign.run_id == run.id,
        ShopeeVideoVoucherCampaign.user_id == user_id,
        ShopeeVideoVoucherCampaign.voucher_code == voucher_code,
    ).first()
    if video_exists:
        return True
    follow_exists = db.query(ShopeeFollowVoucherCampaign.id).filter(
        ShopeeFollowVoucherCampaign.run_id == run.id,
        ShopeeFollowVoucherCampaign.user_id == user_id,
        ShopeeFollowVoucherCampaign.voucher_code == voucher_code,
    ).first()
    return follow_exists is not None


def _resolve_shop_voucher_status(*, start_at: datetime, end_at: datetime, current_tick: datetime, used_count: int = 0, usage_limit: int = 0) -> str:
    if usage_limit > 0 and used_count >= usage_limit:
        return "sold_out"
    if current_tick < _align_compare_time(current_tick, start_at):
        return "upcoming"
    if current_tick >= _align_compare_time(current_tick, end_at):
        return "ended"
    return "ongoing"


def _resolve_follow_voucher_status(*, claim_start_at: datetime, claim_end_at: datetime, current_tick: datetime, claimed_count: int = 0, usage_limit: int = 0) -> str:
    return _resolve_shop_voucher_status(
        start_at=claim_start_at,
        end_at=claim_end_at,
        current_tick=current_tick,
        used_count=claimed_count,
        usage_limit=usage_limit,
    )


def _validate_follow_voucher_create_payload(
    *,
    payload: ShopeeFollowVoucherCampaignCreateRequest,
    claim_start_at: datetime | None,
    claim_end_at: datetime | None,
) -> None:
    if (payload.voucher_type or "follow_voucher").strip().lower() != "follow_voucher":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前仅支持关注礼代金券")
    if (payload.reward_type or "discount").strip().lower() != "discount":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前仅支持折扣奖励")
    voucher_name = payload.voucher_name.strip()
    if not voucher_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入代金券名称")
    if len(voucher_name) > 100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="代金券名称最多 100 个字符")
    if claim_start_at is None or claim_end_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择领取期限")
    if claim_start_at >= claim_end_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="领取结束时间必须晚于开始时间")
    if claim_end_at - claim_start_at > timedelta(seconds=REAL_SECONDS_PER_GAME_DAY * 180):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="领取期限最多 180 个游戏天")

    discount_type = (payload.discount_type or "").strip().lower()
    max_discount_type = (payload.max_discount_type or "").strip().lower()
    if discount_type not in {"fixed_amount", "percent"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="折扣类型不支持")
    if payload.min_spend_amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="最低消费金额必须大于 0")
    if discount_type == "fixed_amount":
        if payload.discount_amount is None or payload.discount_amount <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="优惠金额必须大于 0")
        if payload.min_spend_amount < payload.discount_amount:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="最低消费金额不能小于优惠金额")
    else:
        if payload.discount_percent is None or payload.discount_percent <= 0 or payload.discount_percent > 100:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="优惠百分比必须大于 0 且不超过 100")
        if max_discount_type not in {"set_amount", "no_limit"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="最大折扣金额类型不支持")
        if max_discount_type == "set_amount" and (payload.max_discount_amount is None or payload.max_discount_amount <= 0):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="最大折扣金额必须大于 0")
        if max_discount_type == "no_limit" and payload.max_discount_amount is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无限制时最大折扣金额必须为空")

    if payload.usage_limit <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="使用数量必须大于 0")
    if payload.per_buyer_limit <= 0 or payload.per_buyer_limit > payload.usage_limit:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="每位买家最大发放量必须大于 0 且不超过使用数量")


def _validate_shop_voucher_create_payload(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    payload: ShopeeVoucherCampaignCreateRequest,
    start_at: datetime | None,
    end_at: datetime | None,
    display_start_at: datetime | None,
) -> str:
    voucher_type = (payload.voucher_type or "shop_voucher").strip().lower() or "shop_voucher"
    if voucher_type not in {"shop_voucher", "product_voucher", "private_voucher", "live_voucher", "video_voucher"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前仅支持店铺代金券、商品代金券、专属代金券、直播代金券和视频代金券")
    if (payload.reward_type or "").strip().lower() != "discount":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前仅支持折扣奖励")
    voucher_name = payload.voucher_name.strip()
    if not voucher_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入代金券名称")
    if len(voucher_name) > 100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="代金券名称最多 100 个字符")
    code_suffix = "" if voucher_type == "video_voucher" else _normalize_shop_voucher_code_suffix(payload.code_suffix)
    if start_at is None or end_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择代金券使用期限")
    if start_at >= end_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="代金券结束时间必须晚于开始时间")
    if payload.display_before_start:
        if display_start_at is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择提前展示时间")
        if display_start_at >= start_at:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="提前展示时间必须早于代金券开始时间")
    elif display_start_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未开启提前展示时展示时间必须为空")
    if end_at - start_at > timedelta(seconds=REAL_SECONDS_PER_GAME_DAY * 180):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="代金券使用期限最多 180 个游戏天")

    discount_type = (payload.discount_type or "").strip().lower()
    max_discount_type = (payload.max_discount_type or "").strip().lower()
    display_type = (payload.display_type or "").strip().lower()
    if discount_type not in {"fixed_amount", "percent"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="折扣类型不支持")
    if payload.min_spend_amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="最低消费金额必须大于 0")
    if discount_type == "fixed_amount":
        if payload.discount_amount is None or payload.discount_amount <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="优惠金额必须大于 0")
        if payload.min_spend_amount < payload.discount_amount:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="最低消费金额不能小于优惠金额")
    else:
        if payload.discount_percent is None or payload.discount_percent <= 0 or payload.discount_percent > 100:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="优惠百分比必须大于 0 且不超过 100")
        if max_discount_type not in {"set_amount", "no_limit"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="最大折扣金额类型不支持")
        if max_discount_type == "set_amount" and (payload.max_discount_amount is None or payload.max_discount_amount <= 0):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="最大折扣金额必须大于 0")
        if max_discount_type == "no_limit" and payload.max_discount_amount is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无限制时最大折扣金额必须为空")

    if payload.usage_limit <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="使用数量必须大于 0")
    if payload.per_buyer_limit <= 0 or payload.per_buyer_limit > payload.usage_limit:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="每位买家最大发放量必须大于 0 且不超过使用数量")
    if display_type not in {"all_pages", "specific_channels", "code_only", "live_stream", "video_stream"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="代金券展示设置不支持")
    display_channels = set(payload.display_channels or [])
    if voucher_type == "private_voucher":
        if display_type != "code_only":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="专属代金券仅支持通过代金券代码分享")
        if display_channels:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="专属代金券不支持特定展示渠道")
    elif voucher_type == "live_voucher":
        if display_type != "live_stream":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="直播代金券仅支持 Shopee Live 展示")
        if display_channels != {"shopee_live"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="直播代金券展示渠道仅支持 Shopee Live")
        if (payload.live_scope or "all_live_sessions").strip().lower() != "all_live_sessions":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前仅支持全部直播场次")
    elif voucher_type == "video_voucher":
        if display_type != "video_stream":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="视频代金券仅支持 Shopee Video 展示")
        if display_channels != {"shopee_video"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="视频代金券展示渠道仅支持 Shopee Video")
        if (payload.video_scope or "all_videos").strip().lower() != "all_videos":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前仅支持全部视频场景")
    else:
        if display_type == "specific_channels" and not display_channels:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择特定展示渠道")
        if display_channels - {"checkout_page"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前仅支持订单支付页面展示")
    if voucher_type in {"product_voucher", "private_voucher", "live_voucher", "video_voucher"}:
        selected_products = payload.selected_products or []
        applicable_scope = (payload.applicable_scope or "").strip().lower()
        if voucher_type == "product_voucher":
            applicable_scope = "selected_products"
        elif applicable_scope not in {"all_products", "selected_products"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="适用商品范围不支持")
        if applicable_scope == "selected_products" and not selected_products:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请至少选择一个适用商品")
        if len(selected_products) > 100:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="最多选择 100 个适用商品")
        dedupe_keys = {(item.listing_id, item.variant_id) for item in selected_products}
        if len(dedupe_keys) != len(selected_products):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="适用商品不可重复选择")

    if voucher_type != "video_voucher":
        voucher_code = f"HOME{code_suffix}"
        if _resolve_voucher_code_exists(db=db, run=run, user_id=user_id, voucher_code=voucher_code):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该代金券代码已存在，请更换后缀")
    return code_suffix


def _format_shop_voucher_period(row: ShopeeShopVoucherCampaign | ShopeeProductVoucherCampaign | ShopeePrivateVoucherCampaign | ShopeeLiveVoucherCampaign | ShopeeVideoVoucherCampaign, *, run: GameRun) -> str:
    start_text = _format_discount_game_datetime(row.start_at, run=run) or ""
    end_text = _format_discount_game_datetime(row.end_at, run=run) or ""
    return _format_game_datetime_period(start_text, end_text)


def _format_follow_voucher_period(row: ShopeeFollowVoucherCampaign, *, run: GameRun) -> str:
    start_text = _format_discount_game_datetime(row.claim_start_at, run=run) or ""
    end_text = _format_discount_game_datetime(row.claim_end_at, run=run) or ""
    return _format_game_datetime_period(start_text, end_text)


def _format_game_datetime_period(start_text: str, end_text: str) -> str:
    def normalize(value: str) -> str:
        parsed = _parse_discount_datetime(value)
        return parsed.strftime("%d/%m/%Y %H:%M") if parsed else value
    return f"{normalize(start_text)} - {normalize(end_text)}"


def _parse_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _build_voucher_detail_selected_products(items: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "listing_id": int(item.listing_id),
            "variant_id": int(item.variant_id) if item.variant_id is not None else None,
            "product_id": item.product_id,
            "product_name": item.product_name_snapshot,
            "variant_name": item.variant_name_snapshot or "",
            "sku": item.sku_snapshot,
            "image_url": item.image_url_snapshot,
            "category_key": item.category_key_snapshot or "all",
            "category_label": item.category_label_snapshot or "全部",
            "original_price": float(item.original_price_snapshot or 0),
            "stock_available": int(item.stock_snapshot or 0),
        }
        for item in sorted(items or [], key=lambda row: (row.sort_order, row.id))
    ]


def _build_voucher_detail_response(
    *,
    row: Any,
    run: GameRun,
    user_id: int,
    voucher_type: str,
    status_value: str,
    status_label: str,
    current_tick: datetime,
) -> ShopeeVoucherDetailResponse:
    is_follow = voucher_type == "follow_voucher"
    if is_follow:
        form = ShopeeFollowVoucherCreateFormResponse(
            voucher_name=row.voucher_name,
            claim_start_at=_format_discount_game_datetime(row.claim_start_at, run=run) or "",
            claim_end_at=_format_discount_game_datetime(row.claim_end_at, run=run) or "",
            valid_days_after_claim=int(row.valid_days_after_claim or 7),
            reward_type=row.reward_type,
            discount_type=row.discount_type,
            discount_amount=row.discount_amount,
            discount_percent=row.discount_percent,
            max_discount_type=row.max_discount_type,
            max_discount_amount=row.max_discount_amount,
            min_spend_amount=row.min_spend_amount,
            usage_limit=row.usage_limit,
            per_buyer_limit=row.per_buyer_limit,
            trigger_type=row.trigger_type,
            display_type=row.display_type,
            applicable_scope=row.applicable_scope,
        )
        selected_products: list[dict[str, Any]] = []
    else:
        form = ShopeeVoucherCreateFormResponse(
            voucher_name=row.voucher_name,
            code_prefix=getattr(row, "code_prefix", "HOME") or "HOME",
            code_suffix_max_length=5,
            start_at=_format_discount_game_datetime(row.start_at, run=run) or "",
            end_at=_format_discount_game_datetime(row.end_at, run=run) or "",
            display_before_start=bool(getattr(row, "display_before_start", False)),
            display_start_at=_format_discount_game_datetime(getattr(row, "display_start_at", None), run=run),
            reward_type=row.reward_type,
            discount_type=row.discount_type,
            discount_amount=row.discount_amount,
            discount_percent=row.discount_percent,
            max_discount_type=row.max_discount_type,
            max_discount_amount=row.max_discount_amount,
            min_spend_amount=row.min_spend_amount,
            usage_limit=row.usage_limit,
            per_buyer_limit=row.per_buyer_limit,
            display_type=row.display_type,
            display_channels=_parse_json_list(getattr(row, "display_channels", None)),
            applicable_scope=row.applicable_scope,
            audience_scope=getattr(row, "audience_scope", ""),
        )
        selected_products = _build_voucher_detail_selected_products(list(getattr(row, "items", []) or []))
    return ShopeeVoucherDetailResponse(
        meta=ShopeeVoucherCreateMetaResponse(
            run_id=run.id,
            user_id=user_id,
            voucher_type=voucher_type,
            read_only=True,
            current_tick=current_tick,
        ),
        form=form,
        selected_products=selected_products,
        status=status_value,
        status_label=status_label,
        voucher_code=row.voucher_code,
        used_count=int(getattr(row, "used_count", 0) or 0),
        sales_amount=float(getattr(row, "sales_amount", 0) or 0),
        order_count=int(getattr(row, "order_count", 0) or 0),
        buyer_count=int(getattr(row, "buyer_count", 0) or 0),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _voucher_campaign_config() -> dict[str, tuple[Any, Any, str]]:
    return {
        "shop_voucher": (ShopeeShopVoucherCampaign, None, "店铺代金券"),
        "product_voucher": (ShopeeProductVoucherCampaign, ShopeeProductVoucherCampaign.items, "商品代金券"),
        "private_voucher": (ShopeePrivateVoucherCampaign, ShopeePrivateVoucherCampaign.items, "专属代金券"),
        "live_voucher": (ShopeeLiveVoucherCampaign, ShopeeLiveVoucherCampaign.items, "直播代金券"),
        "video_voucher": (ShopeeVideoVoucherCampaign, ShopeeVideoVoucherCampaign.items, "视频代金券"),
        "follow_voucher": (ShopeeFollowVoucherCampaign, None, "关注礼代金券"),
    }


def _format_rm_amount(value: float | int | None) -> str:
    amount = float(value or 0)
    text = f"{amount:.2f}".rstrip("0").rstrip(".")
    return f"RM{text}"


def _voucher_discount_text(row: Any) -> str:
    if (getattr(row, "discount_type", "") or "") == "percent":
        return f"{float(getattr(row, 'discount_percent', 0) or 0):.0f}%"
    return _format_rm_amount(getattr(row, "discount_amount", 0))


def _voucher_scope_label(row: Any, voucher_type: str) -> str:
    if voucher_type == "shop_voucher":
        return "所有商品"
    if voucher_type == "follow_voucher":
        return "全部商品"
    selected_count = int(getattr(row, "selected_product_count", 0) or len(getattr(row, "items", []) or []))
    if selected_count > 0:
        return f"{selected_count} 件商品"
    return "全部商品"


def _voucher_order_status_label(row: ShopeeOrder) -> str:
    if (row.type_bucket or "") == "cancelled" or row.cancelled_at:
        return "已取消"
    if (row.type_bucket or "") == "completed" or row.delivered_at:
        return "已完成"
    if (row.process_status or "") == "shipping":
        return "运送中"
    if (row.process_status or "") == "processing":
        return "待发货"
    return row.process_status or "处理中"


def _build_voucher_orders_response(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    voucher_type: str,
    campaign_id: int,
    page: int,
    page_size: int,
) -> ShopeeVoucherOrdersResponse:
    campaign_config = _voucher_campaign_config()
    if voucher_type not in campaign_config:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="代金券类型不支持")

    model, items_relation, type_label = campaign_config[voucher_type]
    campaign_query = db.query(model)
    if items_relation is not None:
        campaign_query = campaign_query.options(selectinload(items_relation))
    campaign = campaign_query.filter(model.id == campaign_id, model.run_id == run.id, model.user_id == user_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="代金券不存在")

    current_tick = _resolve_game_tick(db, run.id, user_id)
    if voucher_type == "follow_voucher":
        status_value = _resolve_follow_voucher_status(
            claim_start_at=campaign.claim_start_at,
            claim_end_at=campaign.claim_end_at,
            current_tick=current_tick,
            claimed_count=campaign.claimed_count,
            usage_limit=campaign.usage_limit,
        )
        period = _format_follow_voucher_period(campaign, run=run)
        claimed_count = int(campaign.claimed_count or 0)
    else:
        status_value = _resolve_shop_voucher_status(
            start_at=campaign.start_at,
            end_at=campaign.end_at,
            current_tick=current_tick,
            used_count=campaign.used_count,
            usage_limit=campaign.usage_limit,
        )
        period = _format_shop_voucher_period(campaign, run=run)
        claimed_count = int(getattr(campaign, "claimed_count", 0) or campaign.used_count or 0)

    status_label = {
        "upcoming": "即将开始",
        "ongoing": "进行中",
        "sold_out": "已抢完",
        "ended": "已过期",
        "stopped": "已停止",
    }.get(status_value, status_value)

    query = (
        db.query(ShopeeOrder)
        .options(selectinload(ShopeeOrder.items))
        .filter(
            ShopeeOrder.run_id == run.id,
            ShopeeOrder.user_id == user_id,
            ShopeeOrder.voucher_campaign_type == voucher_type,
            ShopeeOrder.voucher_campaign_id == campaign_id,
        )
        .order_by(desc(ShopeeOrder.created_at), desc(ShopeeOrder.id))
    )
    total = query.count()
    orders = query.offset((page - 1) * page_size).limit(page_size).all()

    return ShopeeVoucherOrdersResponse(
        voucher=ShopeeVoucherOrdersInfoResponse(
            status_label=status_label,
            voucher_name=campaign.voucher_name,
            reward_type_label="折扣" if (campaign.reward_type or "discount") == "discount" else campaign.reward_type,
            min_spend_text=_format_rm_amount(campaign.min_spend_amount),
            discount_text=_voucher_discount_text(campaign),
            period=period,
            voucher_code=campaign.voucher_code,
            voucher_type_label=type_label,
            applicable_scope_label=_voucher_scope_label(campaign, voucher_type),
            display_setting_label="不展示" if not bool(getattr(campaign, "display_before_start", False)) else "展示",
            usage_limit=int(campaign.usage_limit or 0),
            claimed_count=claimed_count,
            used_count=int(campaign.used_count or 0),
        ),
        page=page,
        page_size=page_size,
        total=total,
        orders=[
            ShopeeVoucherOrderRowResponse(
                id=int(order.id),
                order_no=order.order_no,
                products=[
                    ShopeeVoucherOrderProductResponse(
                        image_url=item.image_url,
                        product_name=item.product_name,
                    )
                    for item in (order.items or [])[:2]
                ],
                discount_amount=float(order.voucher_discount_amount or 0),
                total_amount=float(order.buyer_payment or 0),
                created_at_text=(_format_discount_game_datetime(order.created_at, run=run) or "")[:10],
                status_label=_voucher_order_status_label(order),
            )
            for order in orders
        ],
    )


def _build_product_voucher_eligible_products_response(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    search_field: str,
    category_key: str,
    keyword: str,
    page: int,
    page_size: int,
) -> ShopeeProductVoucherEligibleProductsResponse:
    query = (
        db.query(ShopeeListing)
        .options(selectinload(ShopeeListing.variants), selectinload(ShopeeListing.images))
        .filter(
            ShopeeListing.run_id == run.id,
            ShopeeListing.user_id == user_id,
            ShopeeListing.status == "live",
        )
        .order_by(desc(ShopeeListing.updated_at), desc(ShopeeListing.id))
    )
    clean_keyword = keyword.strip()
    if clean_keyword:
        like = f"%{clean_keyword}%"
        if (search_field or "product_name").strip().lower() == "product_id" and clean_keyword.isdigit():
            query = query.filter(ShopeeListing.id == int(clean_keyword))
        else:
            query = query.filter(or_(ShopeeListing.title.ilike(like), ShopeeListing.sku_code.ilike(like)))

    all_items: list[ShopeeProductVoucherEligibleProductResponse] = []
    safe_category_key = (category_key or "all").strip()
    for listing in query.all():
        category_value = (listing.category or "未分类").strip() or "未分类"
        row_category_key = category_value
        row_category_label = category_value
        if safe_category_key != "all" and row_category_key != safe_category_key:
            continue
        image_url = listing.cover_url or next((image.image_url for image in sorted(listing.images, key=lambda row: row.sort_order) if image.image_url), None)
        active_variants = [variant for variant in sorted(listing.variants, key=lambda row: row.sort_order) if variant.stock > 0 and variant.price > 0]
        if active_variants:
            prices = [float(variant.price) for variant in active_variants]
            min_price = min(prices)
            max_price = max(prices)
            price_range_label = f"RM {min_price:.2f}" if min_price == max_price else f"RM {min_price:.2f} - RM {max_price:.2f}"
            stock_total = sum(int(variant.stock or 0) for variant in active_variants)
            all_items.append(
                ShopeeProductVoucherEligibleProductResponse(
                    listing_id=listing.id,
                    variant_id=None,
                    variant_ids=[int(variant.id) for variant in active_variants],
                    product_name=listing.title,
                    variant_name="",
                    sku=active_variants[0].sku,
                    image_url=image_url,
                    category_key=row_category_key,
                    category_label=row_category_label,
                    original_price=round(min_price, 2),
                    price_range_label=price_range_label,
                    stock_available=stock_total,
                    likes_count=0,
                    conflict=False,
                )
            )
        elif listing.stock_available > 0 and float(listing.price or 0) > 0:
            all_items.append(
                ShopeeProductVoucherEligibleProductResponse(
                    listing_id=listing.id,
                    variant_id=None,
                    product_name=listing.title,
                    variant_name="",
                    sku=listing.sku_code,
                    image_url=image_url,
                    category_key=row_category_key,
                    category_label=row_category_label,
                    original_price=round(float(listing.price or 0), 2),
                    price_range_label=f"RM {float(listing.price or 0):.2f}",
                    stock_available=int(listing.stock_available or 0),
                    likes_count=0,
                    conflict=False,
                )
            )

    total = len(all_items)
    start = max(0, (page - 1) * page_size)
    end = start + page_size
    return ShopeeProductVoucherEligibleProductsResponse(page=page, page_size=page_size, total=total, items=all_items[start:end])


def _resolve_product_voucher_item_snapshots(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    selected_products: list[ShopeeProductVoucherItemPayload],
) -> list[ShopeeProductVoucherItem]:
    items: list[ShopeeProductVoucherItem] = []
    for sort_order, selected in enumerate(selected_products):
        listing = (
            db.query(ShopeeListing)
            .options(selectinload(ShopeeListing.variants), selectinload(ShopeeListing.images))
            .filter(
                ShopeeListing.id == selected.listing_id,
                ShopeeListing.run_id == run.id,
                ShopeeListing.user_id == user_id,
                ShopeeListing.status == "live",
            )
            .first()
        )
        if not listing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所选商品不存在或不可售")
        variant = None
        if selected.variant_id is not None:
            variant = next((row for row in listing.variants if row.id == selected.variant_id), None)
            if not variant:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所选商品变体不存在")
        stock_available = int(variant.stock if variant else listing.stock_available or 0)
        original_price = float(variant.price if variant else listing.price or 0)
        if stock_available <= 0 or original_price <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所选商品库存或售价不满足参与条件")
        image_url = (variant.image_url if variant else None) or listing.cover_url or next(
            (image.image_url for image in sorted(listing.images, key=lambda row: row.sort_order) if image.image_url),
            None,
        )
        category_label = (listing.category or "未分类").strip() or "未分类"
        items.append(
            ShopeeProductVoucherItem(
                run_id=run.id,
                user_id=user_id,
                listing_id=listing.id,
                variant_id=variant.id if variant else None,
                product_id=listing.product_id,
                product_name_snapshot=listing.title,
                variant_name_snapshot=(variant.variant_name or variant.option_value) if variant else None,
                sku_snapshot=(variant.sku if variant else listing.sku_code),
                image_url_snapshot=image_url,
                category_key_snapshot=category_label,
                category_label_snapshot=category_label,
                original_price_snapshot=original_price,
                stock_snapshot=stock_available,
                sort_order=sort_order,
            )
        )
    return items


def _build_shop_voucher_row(row: ShopeeShopVoucherCampaign, *, run: GameRun, current_tick: datetime) -> ShopeeVoucherRowResponse:
    status_value = _resolve_shop_voucher_status(
        start_at=row.start_at,
        end_at=row.end_at,
        current_tick=current_tick,
        used_count=row.used_count,
        usage_limit=row.usage_limit,
    )
    status_labels = {
        "upcoming": "即将开始",
        "ongoing": "进行中",
        "sold_out": "已抢完",
        "ended": "已结束",
        "stopped": "已停止",
    }
    if row.discount_type == "percent":
        discount_label = f"{float(row.discount_percent or 0):g}%OFF"
    else:
        discount_label = f"RM {float(row.discount_amount or 0):g}"
    return ShopeeVoucherRowResponse(
        id=row.id,
        voucher_name=row.voucher_name,
        voucher_code=row.voucher_code,
        voucher_type="shop_voucher",
        voucher_type_label="店铺代金券",
        discount_type=row.discount_type,
        discount_label=discount_label,
        status=status_value,
        status_label=status_labels.get(status_value, status_value),
        scope_label="所有商品",
        usage_limit=row.usage_limit,
        used_count=row.used_count,
        period=_format_shop_voucher_period(row, run=run),
    )


def _resolve_private_voucher_item_snapshots(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    selected_products: list[ShopeeProductVoucherItemPayload],
) -> list[ShopeePrivateVoucherItem]:
    items: list[ShopeePrivateVoucherItem] = []
    for sort_order, selected in enumerate(selected_products):
        listing = (
            db.query(ShopeeListing)
            .options(selectinload(ShopeeListing.variants), selectinload(ShopeeListing.images))
            .filter(
                ShopeeListing.id == selected.listing_id,
                ShopeeListing.run_id == run.id,
                ShopeeListing.user_id == user_id,
                ShopeeListing.status == "live",
            )
            .first()
        )
        if not listing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所选商品不存在或不可售")
        variant = None
        if selected.variant_id is not None:
            variant = next((row for row in listing.variants if row.id == selected.variant_id), None)
            if not variant:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所选商品变体不存在")
        stock_available = int(variant.stock if variant else listing.stock_available or 0)
        original_price = float(variant.price if variant else listing.price or 0)
        if stock_available <= 0 or original_price <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所选商品库存或售价不满足参与条件")
        image_url = (variant.image_url if variant else None) or listing.cover_url or next(
            (image.image_url for image in sorted(listing.images, key=lambda row: row.sort_order) if image.image_url),
            None,
        )
        category_label = (listing.category or "未分类").strip() or "未分类"
        items.append(
            ShopeePrivateVoucherItem(
                run_id=run.id,
                user_id=user_id,
                listing_id=listing.id,
                variant_id=variant.id if variant else None,
                product_id=listing.product_id,
                product_name_snapshot=listing.title,
                variant_name_snapshot=(variant.variant_name or variant.option_value) if variant else None,
                sku_snapshot=(variant.sku if variant else listing.sku_code),
                image_url_snapshot=image_url,
                category_key_snapshot=category_label,
                category_label_snapshot=category_label,
                original_price_snapshot=original_price,
                stock_snapshot=stock_available,
                sort_order=sort_order,
            )
        )
    return items


def _resolve_live_voucher_item_snapshots(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    selected_products: list[ShopeeProductVoucherItemPayload],
) -> list[ShopeeLiveVoucherItem]:
    return _resolve_scene_voucher_item_snapshots(
        db=db,
        run=run,
        user_id=user_id,
        selected_products=selected_products,
        item_model=ShopeeLiveVoucherItem,
    )


def _resolve_video_voucher_item_snapshots(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    selected_products: list[ShopeeProductVoucherItemPayload],
) -> list[ShopeeVideoVoucherItem]:
    return _resolve_scene_voucher_item_snapshots(
        db=db,
        run=run,
        user_id=user_id,
        selected_products=selected_products,
        item_model=ShopeeVideoVoucherItem,
    )


def _resolve_scene_voucher_item_snapshots(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    selected_products: list[ShopeeProductVoucherItemPayload],
    item_model: type[ShopeeLiveVoucherItem] | type[ShopeeVideoVoucherItem],
):
    items = []
    for sort_order, selected in enumerate(selected_products):
        listing = (
            db.query(ShopeeListing)
            .options(selectinload(ShopeeListing.variants), selectinload(ShopeeListing.images))
            .filter(
                ShopeeListing.id == selected.listing_id,
                ShopeeListing.run_id == run.id,
                ShopeeListing.user_id == user_id,
                ShopeeListing.status == "live",
            )
            .first()
        )
        if not listing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所选商品不存在或不可售")
        variant = None
        if selected.variant_id is not None:
            variant = next((row for row in listing.variants if row.id == selected.variant_id), None)
            if not variant:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所选商品变体不存在")
        stock_available = int(variant.stock if variant else listing.stock_available or 0)
        original_price = float(variant.price if variant else listing.price or 0)
        if stock_available <= 0 or original_price <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所选商品库存或售价不满足参与条件")
        image_url = (variant.image_url if variant else None) or listing.cover_url or next(
            (image.image_url for image in sorted(listing.images, key=lambda row: row.sort_order) if image.image_url),
            None,
        )
        category_label = (listing.category or "未分类").strip() or "未分类"
        items.append(
            item_model(
                run_id=run.id,
                user_id=user_id,
                listing_id=listing.id,
                variant_id=variant.id if variant else None,
                product_id=listing.product_id,
                product_name_snapshot=listing.title,
                variant_name_snapshot=(variant.variant_name or variant.option_value) if variant else None,
                sku_snapshot=(variant.sku if variant else listing.sku_code),
                image_url_snapshot=image_url,
                category_key_snapshot=category_label,
                category_label_snapshot=category_label,
                original_price_snapshot=original_price,
                stock_snapshot=stock_available,
                sort_order=sort_order,
            )
        )
    return items


def _build_follow_voucher_row(row: ShopeeFollowVoucherCampaign, *, run: GameRun, current_tick: datetime) -> ShopeeVoucherRowResponse:
    status_value = _resolve_follow_voucher_status(
        claim_start_at=row.claim_start_at,
        claim_end_at=row.claim_end_at,
        current_tick=current_tick,
        claimed_count=row.claimed_count,
        usage_limit=row.usage_limit,
    )
    status_labels = {
        "upcoming": "即将开始",
        "ongoing": "进行中",
        "sold_out": "已抢完",
        "ended": "已结束",
        "stopped": "已停止",
    }
    if row.discount_type == "percent":
        discount_label = f"{float(row.discount_percent or 0):g}%OFF"
    else:
        discount_label = f"RM {float(row.discount_amount or 0):g}"
    return ShopeeVoucherRowResponse(
        id=row.id,
        voucher_name=row.voucher_name,
        voucher_code=row.voucher_code,
        voucher_type="follow_voucher",
        voucher_type_label="关注礼代金券",
        discount_type=row.discount_type,
        discount_label=discount_label,
        status=status_value,
        status_label=status_labels.get(status_value, status_value),
        scope_label="全部商品",
        usage_limit=row.usage_limit,
        used_count=row.used_count,
        period=_format_follow_voucher_period(row, run=run),
    )


def _build_product_voucher_row(row: ShopeeProductVoucherCampaign, *, run: GameRun, current_tick: datetime) -> ShopeeVoucherRowResponse:
    status_value = _resolve_shop_voucher_status(
        start_at=row.start_at,
        end_at=row.end_at,
        current_tick=current_tick,
        used_count=row.used_count,
        usage_limit=row.usage_limit,
    )
    status_labels = {
        "upcoming": "即将开始",
        "ongoing": "进行中",
        "sold_out": "已抢完",
        "ended": "已结束",
        "stopped": "已停止",
    }
    if row.discount_type == "percent":
        discount_label = f"{float(row.discount_percent or 0):g}%OFF"
    else:
        discount_label = f"RM {float(row.discount_amount or 0):g}"
    selected_count = int(row.selected_product_count or len(row.items or []))
    return ShopeeVoucherRowResponse(
        id=row.id,
        voucher_name=row.voucher_name,
        voucher_code=row.voucher_code,
        voucher_type="product_voucher",
        voucher_type_label="商品代金券",
        discount_type=row.discount_type,
        discount_label=discount_label,
        status=status_value,
        status_label=status_labels.get(status_value, status_value),
        scope_label=f"指定商品 {selected_count} 个",
        usage_limit=row.usage_limit,
        used_count=row.used_count,
        period=_format_shop_voucher_period(row, run=run),
    )


def _build_private_voucher_row(row: ShopeePrivateVoucherCampaign, *, run: GameRun, current_tick: datetime) -> ShopeeVoucherRowResponse:
    status_value = _resolve_shop_voucher_status(
        start_at=row.start_at,
        end_at=row.end_at,
        current_tick=current_tick,
        used_count=row.used_count,
        usage_limit=row.usage_limit,
    )
    status_labels = {
        "upcoming": "即将开始",
        "ongoing": "进行中",
        "sold_out": "已抢完",
        "ended": "已结束",
        "stopped": "已停止",
    }
    if row.discount_type == "percent":
        discount_label = f"{float(row.discount_percent or 0):g}%OFF"
    else:
        discount_label = f"RM {float(row.discount_amount or 0):g}"
    selected_count = int(row.selected_product_count or len(row.items or []))
    scope_label = "全部商品" if row.applicable_scope == "all_products" else f"指定商品 {selected_count} 个"
    return ShopeeVoucherRowResponse(
        id=row.id,
        voucher_name=row.voucher_name,
        voucher_code=row.voucher_code,
        voucher_type="private_voucher",
        voucher_type_label="专属代金券",
        discount_type=row.discount_type,
        discount_label=discount_label,
        status=status_value,
        status_label=status_labels.get(status_value, status_value),
        scope_label=scope_label,
        usage_limit=row.usage_limit,
        used_count=row.used_count,
        period=_format_shop_voucher_period(row, run=run),
    )


def _build_live_voucher_row(row: ShopeeLiveVoucherCampaign, *, run: GameRun, current_tick: datetime) -> ShopeeVoucherRowResponse:
    return _build_scene_voucher_row(
        row,
        run=run,
        current_tick=current_tick,
        voucher_type="live_voucher",
        voucher_type_label="直播代金券",
    )


def _build_video_voucher_row(row: ShopeeVideoVoucherCampaign, *, run: GameRun, current_tick: datetime) -> ShopeeVoucherRowResponse:
    return _build_scene_voucher_row(
        row,
        run=run,
        current_tick=current_tick,
        voucher_type="video_voucher",
        voucher_type_label="视频代金券",
    )


def _build_scene_voucher_row(
    row: ShopeeLiveVoucherCampaign | ShopeeVideoVoucherCampaign,
    *,
    run: GameRun,
    current_tick: datetime,
    voucher_type: str,
    voucher_type_label: str,
) -> ShopeeVoucherRowResponse:
    status_value = _resolve_shop_voucher_status(
        start_at=row.start_at,
        end_at=row.end_at,
        current_tick=current_tick,
        used_count=row.used_count,
        usage_limit=row.usage_limit,
    )
    status_labels = {
        "upcoming": "即将开始",
        "ongoing": "进行中",
        "sold_out": "已抢完",
        "ended": "已结束",
        "stopped": "已停止",
    }
    if row.discount_type == "percent":
        discount_label = f"{float(row.discount_percent or 0):g}%OFF"
    else:
        discount_label = f"RM {float(row.discount_amount or 0):g}"
    selected_count = int(row.selected_product_count or len(row.items or []))
    scope_label = "全部商品" if row.applicable_scope == "all_products" else f"指定商品 {selected_count} 个"
    return ShopeeVoucherRowResponse(
        id=row.id,
        voucher_name=row.voucher_name,
        voucher_code=row.voucher_code,
        voucher_type=voucher_type,
        voucher_type_label=voucher_type_label,
        discount_type=row.discount_type,
        discount_label=discount_label,
        status=status_value,
        status_label=status_labels.get(status_value, status_value),
        scope_label=scope_label,
        usage_limit=row.usage_limit,
        used_count=row.used_count,
        period=_format_shop_voucher_period(row, run=run),
    )


def _build_shop_voucher_list_response(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    status_value: str,
    keyword: str,
    page: int,
    page_size: int,
) -> ShopeeVoucherListResponse:
    current_tick = _resolve_game_tick(db, run.id, user_id)
    shop_rows = db.query(ShopeeShopVoucherCampaign).filter(
        ShopeeShopVoucherCampaign.run_id == run.id,
        ShopeeShopVoucherCampaign.user_id == user_id,
    ).all()
    product_rows = db.query(ShopeeProductVoucherCampaign).options(selectinload(ShopeeProductVoucherCampaign.items)).filter(
        ShopeeProductVoucherCampaign.run_id == run.id,
        ShopeeProductVoucherCampaign.user_id == user_id,
    ).all()
    private_rows = db.query(ShopeePrivateVoucherCampaign).options(selectinload(ShopeePrivateVoucherCampaign.items)).filter(
        ShopeePrivateVoucherCampaign.run_id == run.id,
        ShopeePrivateVoucherCampaign.user_id == user_id,
    ).all()
    live_rows = db.query(ShopeeLiveVoucherCampaign).options(selectinload(ShopeeLiveVoucherCampaign.items)).filter(
        ShopeeLiveVoucherCampaign.run_id == run.id,
        ShopeeLiveVoucherCampaign.user_id == user_id,
    ).all()
    video_rows = db.query(ShopeeVideoVoucherCampaign).options(selectinload(ShopeeVideoVoucherCampaign.items)).filter(
        ShopeeVideoVoucherCampaign.run_id == run.id,
        ShopeeVideoVoucherCampaign.user_id == user_id,
    ).all()
    follow_rows = db.query(ShopeeFollowVoucherCampaign).filter(
        ShopeeFollowVoucherCampaign.run_id == run.id,
        ShopeeFollowVoucherCampaign.user_id == user_id,
    ).all()
    row_pairs: list[tuple[datetime, int, ShopeeVoucherRowResponse]] = [
        (row.created_at, row.id, _build_shop_voucher_row(row, run=run, current_tick=current_tick)) for row in shop_rows
    ] + [
        (row.created_at, row.id, _build_product_voucher_row(row, run=run, current_tick=current_tick)) for row in product_rows
    ] + [
        (row.created_at, row.id, _build_private_voucher_row(row, run=run, current_tick=current_tick)) for row in private_rows
    ] + [
        (row.created_at, row.id, _build_live_voucher_row(row, run=run, current_tick=current_tick)) for row in live_rows
    ] + [
        (row.created_at, row.id, _build_video_voucher_row(row, run=run, current_tick=current_tick)) for row in video_rows
    ] + [
        (row.created_at, row.id, _build_follow_voucher_row(row, run=run, current_tick=current_tick)) for row in follow_rows
    ]
    row_pairs.sort(key=lambda item: (item[0], item[1]), reverse=True)
    built_rows = [item[2] for item in row_pairs]
    if keyword.strip():
        needle = keyword.strip().lower()
        built_rows = [row for row in built_rows if needle in row.voucher_name.lower() or needle in row.voucher_code.lower()]
    if status_value != "all":
        built_rows = [row for row in built_rows if row.status == status_value]
    total = len(built_rows)
    start = max(0, (page - 1) * page_size)
    items = built_rows[start:start + page_size]
    all_rows = [item[2] for item in row_pairs]
    counts = {key: 0 for key in ["ongoing", "upcoming", "ended"]}
    for row in all_rows:
        if row.status in counts:
            counts[row.status] += 1
    campaign_rows = shop_rows + product_rows + private_rows + live_rows + video_rows + follow_rows
    usage_limit_sum = sum(row.usage_limit for row in campaign_rows)
    used_count_sum = sum(row.used_count for row in campaign_rows)
    return ShopeeVoucherListResponse(
        summary=ShopeeVoucherSummaryResponse(
            sales_amount=sum(float(row.sales_amount or 0) for row in campaign_rows),
            order_count=sum(int(row.order_count or 0) for row in campaign_rows),
            usage_rate=(used_count_sum / usage_limit_sum * 100) if usage_limit_sum > 0 else 0,
            buyer_count=sum(int(row.buyer_count or 0) for row in campaign_rows),
        ),
        tabs=[
            ShopeeVoucherTabResponse(key="all", label="全部", count=len(all_rows)),
            ShopeeVoucherTabResponse(key="ongoing", label="进行中", count=counts["ongoing"]),
            ShopeeVoucherTabResponse(key="upcoming", label="即将开始", count=counts["upcoming"]),
            ShopeeVoucherTabResponse(key="ended", label="已结束", count=counts["ended"]),
        ],
        list=ShopeeVoucherListPageResponse(page=page, page_size=page_size, total=total, items=items),
    )


def _build_bundle_create_bootstrap_payload(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    current_tick: datetime,
    read_only: bool,
) -> ShopeeBundleCreateBootstrapResponse:
    del db
    return ShopeeBundleCreateBootstrapResponse(
        meta=ShopeeDiscountCreateMetaResponse(
            run_id=run.id,
            user_id=user_id,
            campaign_type="bundle",
            read_only=read_only,
            current_tick=current_tick,
        ),
        form=ShopeeBundleCreateFormResponse(
            campaign_name="",
            start_at=_format_discount_game_datetime(current_tick, run=run),
            end_at=_format_discount_game_datetime(current_tick + timedelta(seconds=REAL_SECONDS_PER_GAME_HOUR), run=run),
            bundle_type="percent",
            purchase_limit=None,
            tiers=[ShopeeBundleTierResponse(tier_no=1, buy_quantity=2, discount_value=10)],
        ),
        rules=ShopeeBundleCreateRulesResponse(),
        selected_products=[],
        product_picker=ShopeeDiscountCreateProductPickerResponse(default_page_size=20),
        draft=None,
    )


def _build_discount_eligible_products_response(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    keyword: str,
    page: int,
    page_size: int,
) -> ShopeeDiscountEligibleProductsResponse:
    query = (
        db.query(ShopeeListing)
        .options(selectinload(ShopeeListing.variants))
        .filter(
            ShopeeListing.run_id == run.id,
            ShopeeListing.user_id == user_id,
            ShopeeListing.status == "live",
        )
        .order_by(desc(ShopeeListing.updated_at), desc(ShopeeListing.id))
    )
    if keyword.strip():
        like = f"%{keyword.strip()}%"
        query = query.filter(or_(ShopeeListing.title.ilike(like), ShopeeListing.sku_code.ilike(like)))

    listings = query.all()
    all_items: list[ShopeeDiscountCreateProductRowResponse] = []
    for listing in listings:
        active_variants = [variant for variant in sorted(listing.variants, key=lambda row: row.sort_order) if variant.stock > 0 or variant.price > 0]
        if active_variants:
            for variant in active_variants:
                all_items.append(_build_discount_create_product_row(listing=listing, variant=variant))
        else:
            all_items.append(_build_discount_create_product_row(listing=listing))

    total = len(all_items)
    start = max(0, (page - 1) * page_size)
    end = start + page_size
    return ShopeeDiscountEligibleProductsResponse(page=page, page_size=page_size, total=total, items=all_items[start:end])


def _validate_discount_create_payload(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    campaign_name: str,
    start_at: datetime | None,
    end_at: datetime | None,
    items: list[ShopeeDiscountDraftItemPayload],
    exclude_campaign_id: int | None = None,
) -> None:
    if not campaign_name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="活动名称不能为空")
    if len(campaign_name.strip()) > 150:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="活动名称不能超过 150 个字符")
    if not start_at or not end_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请完整填写活动时间")
    if start_at >= end_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开始时间必须早于结束时间")
    if end_at - start_at >= timedelta(days=180):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="活动时长必须小于 180 天")
    if not items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请至少添加 1 个商品")

    dedupe_keys: set[tuple[int, int | None]] = set()
    listing_ids = {item.listing_id for item in items}
    variant_ids = {item.variant_id for item in items if item.variant_id}
    listing_map = {
        row.id: row
        for row in db.query(ShopeeListing)
        .filter(
            ShopeeListing.run_id == run.id,
            ShopeeListing.user_id == user_id,
            ShopeeListing.id.in_(listing_ids),
        )
        .all()
    }
    variant_map = {
        row.id: row
        for row in db.query(ShopeeListingVariant)
        .filter(ShopeeListingVariant.id.in_(variant_ids))
        .all()
    } if variant_ids else {}

    for item in items:
        dedupe_key = (item.listing_id, item.variant_id)
        if dedupe_key in dedupe_keys:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="同一商品/变体不能重复添加")
        dedupe_keys.add(dedupe_key)

        listing = listing_map.get(item.listing_id)
        if not listing or listing.status != "live":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所选商品不存在或不是上架状态")
        variant = variant_map.get(item.variant_id) if item.variant_id else None
        original_price = float(variant.price if variant else listing.price)
        stock_available = int(variant.stock if variant else listing.stock_available)
        if original_price <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="商品原价必须大于 0")
        if stock_available <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="商品库存不足，无法加入活动")
        discount_mode = item.discount_mode if item.discount_mode in {"percent", "final_price"} else "percent"
        computed_percent, computed_final_price = _compute_discount_final_price(
            original_price=original_price,
            discount_mode=discount_mode,
            discount_percent=item.discount_percent,
            final_price=item.final_price,
        )
        if computed_percent is None or computed_final_price is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="折扣设置不合法，请检查折扣比例或折后价")

    overlapping_campaigns = (
        db.query(ShopeeDiscountCampaign)
        .filter(
            ShopeeDiscountCampaign.run_id == run.id,
            ShopeeDiscountCampaign.user_id == user_id,
            ShopeeDiscountCampaign.campaign_type == "discount",
            ShopeeDiscountCampaign.campaign_status.in_(["draft", "upcoming", "ongoing"]),
            ShopeeDiscountCampaign.start_at.isnot(None),
            ShopeeDiscountCampaign.end_at.isnot(None),
            ShopeeDiscountCampaign.start_at < end_at,
            ShopeeDiscountCampaign.end_at > start_at,
        )
        .all()
    )
    if exclude_campaign_id:
        overlapping_campaigns = [row for row in overlapping_campaigns if row.id != exclude_campaign_id]
    if overlapping_campaigns:
        overlap_ids = [row.id for row in overlapping_campaigns]
        overlap_items = (
            db.query(ShopeeDiscountCampaignItem)
            .filter(ShopeeDiscountCampaignItem.campaign_id.in_(overlap_ids))
            .all()
        )
        occupied = {(row.listing_id, row.variant_id) for row in overlap_items}
        for item in items:
            if (item.listing_id, item.variant_id) in occupied:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="存在与同时间段单品折扣冲突的商品，请调整活动时间或商品范围")


def _validate_bundle_tiers(*, bundle_type: str, tiers: list[ShopeeBundleTierResponse]) -> list[ShopeeBundleTierResponse]:
    if not tiers:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请至少配置 1 条套餐阶梯")
    if len(tiers) > 10:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="套餐阶梯不能超过 10 条")

    safe_bundle_type = _resolve_bundle_discount_type(bundle_type)
    normalized: list[ShopeeBundleTierResponse] = []
    last_quantity = 0
    for index, tier in enumerate(tiers, start=1):
        buy_quantity = int(tier.buy_quantity or 0)
        discount_value = round(float(tier.discount_value or 0), 2)
        if buy_quantity <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="购买件数必须大于 0")
        if buy_quantity <= last_quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="阶梯购买件数必须严格递增")
        if safe_bundle_type == "percent":
            if discount_value <= 0 or discount_value >= 100:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="折扣比例必须在 1% 到 99% 之间")
        else:
            if discount_value <= 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="固定金额减免或套餐价必须大于 0")
        normalized.append(ShopeeBundleTierResponse(tier_no=index, buy_quantity=buy_quantity, discount_value=discount_value))
        last_quantity = buy_quantity
    return normalized


def _validate_bundle_create_payload(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    campaign_name: str,
    start_at: datetime | None,
    end_at: datetime | None,
    bundle_type: str,
    purchase_limit: int | None,
    tiers: list[ShopeeBundleTierResponse],
    items: list[ShopeeDiscountDraftItemPayload],
) -> list[ShopeeBundleTierResponse]:
    if not campaign_name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="套餐名称不能为空")
    if len(campaign_name.strip()) > 25:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="套餐名称不能超过 25 个字符")
    if not start_at or not end_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请完整填写套餐活动时间")
    if start_at >= end_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开始时间必须早于结束时间")
    if end_at - start_at >= timedelta(days=180):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="活动时长必须小于 180 天")
    if not items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请至少添加 1 个套餐商品")
    if purchase_limit is not None and (int(purchase_limit) < 1 or int(purchase_limit) > 999):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="限购次数必须在 1 到 999 之间")

    normalized_tiers = _validate_bundle_tiers(bundle_type=bundle_type, tiers=tiers)

    dedupe_keys: set[tuple[int, int | None]] = set()
    listing_ids = {item.listing_id for item in items}
    variant_ids = {item.variant_id for item in items if item.variant_id}
    listing_map = {
        row.id: row
        for row in db.query(ShopeeListing)
        .filter(
            ShopeeListing.run_id == run.id,
            ShopeeListing.user_id == user_id,
            ShopeeListing.id.in_(listing_ids),
        )
        .all()
    }
    variant_map = {
        row.id: row
        for row in db.query(ShopeeListingVariant)
        .filter(ShopeeListingVariant.id.in_(variant_ids))
        .all()
    } if variant_ids else {}

    safe_bundle_type = _resolve_bundle_discount_type(bundle_type)
    max_buy_quantity = max(tier.buy_quantity for tier in normalized_tiers)
    total_reference_price = 0.0

    for item in items:
        dedupe_key = (item.listing_id, item.variant_id)
        if dedupe_key in dedupe_keys:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="同一商品/变体不能重复添加")
        dedupe_keys.add(dedupe_key)

        listing = listing_map.get(item.listing_id)
        if not listing or listing.status != "live":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所选商品不存在或不是上架状态")
        variant = variant_map.get(item.variant_id) if item.variant_id else None
        original_price = float(variant.price if variant else listing.price)
        stock_available = int(variant.stock if variant else listing.stock_available)
        if original_price <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="商品原价必须大于 0")
        if stock_available <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="商品库存不足，无法加入套餐活动")
        total_reference_price += original_price

    reference_total = total_reference_price * max_buy_quantity
    for tier in normalized_tiers:
        if safe_bundle_type == "fixed_amount" and tier.discount_value >= reference_total:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="固定金额减免不能大于套餐原总价")
        if safe_bundle_type == "bundle_price" and tier.discount_value >= reference_total:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="套餐价必须小于套餐原总价")

    overlapping_campaigns = (
        db.query(ShopeeDiscountCampaign)
        .filter(
            ShopeeDiscountCampaign.run_id == run.id,
            ShopeeDiscountCampaign.user_id == user_id,
            ShopeeDiscountCampaign.campaign_type == "bundle",
            ShopeeDiscountCampaign.campaign_status.in_(["draft", "upcoming", "ongoing"]),
            ShopeeDiscountCampaign.start_at.isnot(None),
            ShopeeDiscountCampaign.end_at.isnot(None),
            ShopeeDiscountCampaign.start_at < end_at,
            ShopeeDiscountCampaign.end_at > start_at,
        )
        .all()
    )
    if overlapping_campaigns:
        overlap_ids = [row.id for row in overlapping_campaigns]
        overlap_items = db.query(ShopeeDiscountCampaignItem).filter(ShopeeDiscountCampaignItem.campaign_id.in_(overlap_ids)).all()
        occupied = {(row.listing_id, row.variant_id) for row in overlap_items}
        for item in items:
            if (item.listing_id, item.variant_id) in occupied:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="存在与同时间段套餐优惠冲突的商品，请调整活动时间或商品范围")

    return normalized_tiers
def _flash_sale_default_slots(market: str) -> list[ShopeeFlashSaleSlot]:
    return [
        ShopeeFlashSaleSlot(market=market, slot_key="00_12", start_time=time(0, 0), end_time=time(12, 0), cross_day=False, product_limit=50, sort_order=1),
        ShopeeFlashSaleSlot(market=market, slot_key="12_18", start_time=time(12, 0), end_time=time(18, 0), cross_day=False, product_limit=50, sort_order=2),
        ShopeeFlashSaleSlot(market=market, slot_key="18_21", start_time=time(18, 0), end_time=time(21, 0), cross_day=False, product_limit=50, sort_order=3),
        ShopeeFlashSaleSlot(market=market, slot_key="21_00", start_time=time(21, 0), end_time=time(0, 0), cross_day=True, product_limit=50, sort_order=4),
    ]


def _flash_sale_default_category_rules(market: str) -> list[ShopeeFlashSaleCategoryRule]:
    labels = [
        ("baby", "母婴"),
        ("tools_home", "工具与家装"),
        ("kitchen", "厨房用品"),
        ("storage", "收纳整理"),
        ("tv_accessories", "电视及配件"),
        ("beauty", "美容护肤"),
        ("furniture", "家具"),
        ("all", "全部"),
    ]
    return [
        ShopeeFlashSaleCategoryRule(
            market=market,
            category_key=key,
            category_label=label,
            min_activity_stock=5,
            max_activity_stock=10000,
            min_discount_percent=5,
            max_discount_percent=99,
            allow_preorder=True,
            sort_order=index,
        )
        for index, (key, label) in enumerate(labels, start=1)
    ]


def _load_flash_sale_slots(db: Session, market: str) -> list[ShopeeFlashSaleSlot]:
    safe_market = (market or "MY").strip().upper() or "MY"
    rows = (
        db.query(ShopeeFlashSaleSlot)
        .filter(ShopeeFlashSaleSlot.market == safe_market, ShopeeFlashSaleSlot.is_active.is_(True))
        .order_by(ShopeeFlashSaleSlot.sort_order, ShopeeFlashSaleSlot.id)
        .all()
    )
    return rows or _flash_sale_default_slots(safe_market)


def _load_flash_sale_category_rules(db: Session, market: str) -> list[ShopeeFlashSaleCategoryRule]:
    safe_market = (market or "MY").strip().upper() or "MY"
    rows = (
        db.query(ShopeeFlashSaleCategoryRule)
        .filter(ShopeeFlashSaleCategoryRule.market == safe_market, ShopeeFlashSaleCategoryRule.is_active.is_(True))
        .order_by(ShopeeFlashSaleCategoryRule.sort_order, ShopeeFlashSaleCategoryRule.id)
        .all()
    )
    return rows or _flash_sale_default_category_rules(safe_market)


def _flash_sale_display_time(slot: ShopeeFlashSaleSlot) -> str:
    end_suffix = " +1" if slot.cross_day else ""
    return f"{slot.start_time.strftime('%H:%M:%S')} - {slot.end_time.strftime('%H:%M:%S')}{end_suffix}"


def _flash_sale_campaign_display_time(campaign: ShopeeFlashSaleCampaign, *, run: GameRun) -> str:
    start_game_time = _format_discount_game_datetime(campaign.start_tick, run=run)
    end_game_time = _format_discount_game_datetime(campaign.end_tick, run=run)
    if start_game_time and end_game_time:
        return f"{campaign.slot_date.strftime('%d-%m-%Y')} {start_game_time[11:16]} - {end_game_time[11:16]}"
    return f"{campaign.slot_date.strftime('%d-%m-%Y')} {campaign.start_tick.strftime('%H:%M')} - {campaign.end_tick.strftime('%H:%M')}"


def _flash_sale_slot_ticks(slot_date: date, slot: ShopeeFlashSaleSlot, *, run: GameRun) -> tuple[datetime, datetime]:
    start_tick = _parse_discount_game_datetime(f"{slot_date.isoformat()}T{slot.start_time.strftime('%H:%M')}", run=run)
    end_date = slot_date + timedelta(days=1) if slot.cross_day else slot_date
    end_tick = _parse_discount_game_datetime(f"{end_date.isoformat()}T{slot.end_time.strftime('%H:%M')}", run=run)
    if start_tick is None or end_tick is None:
        fallback_start = datetime.combine(slot_date, slot.start_time)
        fallback_end = datetime.combine(end_date, slot.end_time)
        return fallback_start, fallback_end
    return start_tick, end_tick


def _parse_flash_sale_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _build_flash_sale_slot_response(db: Session, *, run: GameRun, user_id: int, slot_date: date, slot: ShopeeFlashSaleSlot, current_tick: datetime) -> ShopeeFlashSaleSlotResponse:
    start_tick, end_tick = _flash_sale_slot_ticks(slot_date, slot, run=run)
    used_count = (
        db.query(func.coalesce(func.sum(ShopeeFlashSaleCampaignItem.activity_stock_limit * 0 + 1), 0))
        .join(ShopeeFlashSaleCampaign, ShopeeFlashSaleCampaign.id == ShopeeFlashSaleCampaignItem.campaign_id)
        .filter(
            ShopeeFlashSaleCampaign.run_id == run.id,
            ShopeeFlashSaleCampaign.user_id == user_id,
            ShopeeFlashSaleCampaign.slot_date == slot_date,
            ShopeeFlashSaleCampaign.slot_key == slot.slot_key,
            ShopeeFlashSaleCampaign.status == "active",
            ShopeeFlashSaleCampaignItem.status == "active",
        )
        .scalar()
        or 0
    )
    available = max(0, int(slot.product_limit or 50) - int(used_count))
    disabled_reason = None
    if end_tick <= current_tick:
        disabled_reason = "该时间段已结束"
    elif available <= 0:
        disabled_reason = "该时间段商品名额已满"
    return ShopeeFlashSaleSlotResponse(
        slot_key=slot.slot_key,
        display_time=_flash_sale_display_time(slot),
        start_tick=start_tick,
        end_tick=end_tick,
        cross_day=bool(slot.cross_day),
        product_limit=int(slot.product_limit or 50),
        used_product_count=int(used_count),
        available_product_count=available,
        selectable=disabled_reason is None,
        disabled_reason=disabled_reason,
    )


def _flash_sale_category_key_for_listing(listing: ShopeeListing, rules: list[ShopeeFlashSaleCategoryRule], market_category_by_product_id: dict[int, str] | None = None) -> str:
    if market_category_by_product_id and listing.product_id:
        market_category = market_category_by_product_id.get(listing.product_id)
        if market_category:
            return market_category
    category_text = (listing.category or "").lower()
    for rule in rules:
        if rule.category_key == "all":
            continue
        if rule.category_label and rule.category_label.lower() in category_text:
            return rule.category_key
    return "all"


def _flash_sale_category_rule_display(rule: ShopeeFlashSaleCategoryRule) -> list[ShopeeFlashSaleCategoryRuleDisplayResponse]:
    return [
        ShopeeFlashSaleCategoryRuleDisplayResponse(label="活动库存", value=f"{rule.min_activity_stock} ~ {rule.max_activity_stock}"),
        ShopeeFlashSaleCategoryRuleDisplayResponse(label="折扣限制", value=f"{rule.min_discount_percent:g}% ~ {rule.max_discount_percent:g}%"),
        ShopeeFlashSaleCategoryRuleDisplayResponse(label="商品评分(0.0-5.0)", value=f"≥ {rule.min_rating:g}" if rule.min_rating is not None else "无限制"),
        ShopeeFlashSaleCategoryRuleDisplayResponse(label="点赞数", value=f"≥ {rule.min_likes}" if rule.min_likes is not None else "无限制"),
        ShopeeFlashSaleCategoryRuleDisplayResponse(label="预购商品", value="允许" if rule.allow_preorder else "不允许"),
        ShopeeFlashSaleCategoryRuleDisplayResponse(label="过去30天订单量", value=f"≥ {rule.min_30d_orders}" if rule.min_30d_orders is not None else "无限制"),
        ShopeeFlashSaleCategoryRuleDisplayResponse(label="发货天数", value=f"≤ {rule.max_ship_days} 天" if rule.max_ship_days is not None else "无限制"),
        ShopeeFlashSaleCategoryRuleDisplayResponse(label="重复控制", value=f"{rule.repeat_control_days} 天" if rule.repeat_control_days is not None else "无限制"),
    ]


def _build_flash_sale_category_rules_response(db: Session, *, market: str) -> ShopeeFlashSaleCategoryRulesResponse:
    rules = _load_flash_sale_category_rules(db, market)
    return ShopeeFlashSaleCategoryRulesResponse(
        categories=[ShopeeFlashSaleCategoryResponse(key=row.category_key, label=row.category_label) for row in rules],
        category_rules={row.category_key: _flash_sale_category_rule_display(row) for row in rules},
    )


def _flash_sale_market_category_by_product_id(db: Session, *, run_id: int) -> dict[int, str]:
    rows = (
        db.query(InventoryLot.product_id, MarketProduct.category)
        .join(MarketProduct, MarketProduct.id == InventoryLot.product_id)
        .filter(InventoryLot.run_id == run_id, InventoryLot.quantity_available > 0)
        .all()
    )
    return {int(product_id): str(category) for product_id, category in rows if product_id and category}


def _build_flash_sale_stocked_category_rules_response(db: Session, *, run: GameRun, user_id: int) -> ShopeeFlashSaleCategoryRulesResponse:
    rules = _load_flash_sale_category_rules(db, run.market)
    fallback_rule = next((row for row in rules if row.category_key == "all"), rules[0] if rules else None)
    category_by_product_id = _flash_sale_market_category_by_product_id(db, run_id=run.id)
    listings = (
        db.query(ShopeeListing)
        .options(selectinload(ShopeeListing.variants))
        .filter(ShopeeListing.run_id == run.id, ShopeeListing.user_id == user_id, ShopeeListing.status == "live")
        .all()
    )
    stocked_categories: set[str] = set()
    for listing in listings:
        has_variant_stock = any((variant.stock or 0) > 0 and (variant.price or 0) > 0 for variant in listing.variants)
        has_listing_stock = (listing.stock_available or 0) > 0 and (listing.price or 0) > 0
        category = category_by_product_id.get(listing.product_id or 0)
        if category and (has_variant_stock or has_listing_stock):
            stocked_categories.add(category)

    categories = sorted(stocked_categories)
    if not categories and fallback_rule:
        return ShopeeFlashSaleCategoryRulesResponse(
            categories=[ShopeeFlashSaleCategoryResponse(key=fallback_rule.category_key, label=fallback_rule.category_label)],
            category_rules={fallback_rule.category_key: _flash_sale_category_rule_display(fallback_rule)},
        )

    rule_display = _flash_sale_category_rule_display(fallback_rule) if fallback_rule else []
    return ShopeeFlashSaleCategoryRulesResponse(
        categories=[ShopeeFlashSaleCategoryResponse(key=category, label=category) for category in categories],
        category_rules={category: rule_display for category in categories},
    )


def _build_flash_sale_product_row(
    *,
    listing: ShopeeListing,
    variant: ShopeeListingVariant | None,
    category_key: str,
    category_label: str,
    conflict: bool = False,
    conflict_reason: str | None = None,
    flash_price: float | None = None,
    activity_stock_limit: int | None = None,
    purchase_limit_per_buyer: int | None = 1,
) -> ShopeeFlashSaleProductRowResponse:
    original_price = float(variant.price if variant else listing.price)
    stock_available = int(variant.stock if variant else listing.stock_available)
    suggested_price = round(original_price * 0.9, 2) if original_price > 0 else None
    return ShopeeFlashSaleProductRowResponse(
        listing_id=listing.id,
        variant_id=variant.id if variant else None,
        product_id=listing.product_id,
        product_name=listing.title,
        variant_name=variant.option_value if variant else "",
        sku=variant.sku if variant else listing.sku_code,
        image_url=listing.cover_url,
        category_key=category_key,
        category_label=category_label,
        original_price=round(original_price, 2),
        stock_available=stock_available,
        rating=float(listing.quality_total_score or 0) / 20 if listing.quality_total_score is not None else None,
        likes_count=0,
        orders_30d=0,
        ship_days=None,
        is_preorder=bool(listing.preorder_enabled),
        conflict=conflict,
        conflict_reason=conflict_reason,
        suggested_flash_price=suggested_price,
        flash_price=flash_price if flash_price is not None else suggested_price,
        activity_stock_limit=activity_stock_limit,
        purchase_limit_per_buyer=purchase_limit_per_buyer,
    )


def _build_flash_sale_eligible_products_response(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    slot_date: date,
    slot_key: str,
    category_key: str,
    keyword: str,
    search_field: str,
    page: int,
    page_size: int,
) -> ShopeeFlashSaleEligibleProductsResponse:
    rules = _load_flash_sale_category_rules(db, run.market)
    label_by_key = {rule.category_key: rule.category_label for rule in rules}
    category_by_product_id = _flash_sale_market_category_by_product_id(db, run_id=run.id)
    query = (
        db.query(ShopeeListing)
        .options(selectinload(ShopeeListing.variants))
        .filter(ShopeeListing.run_id == run.id, ShopeeListing.user_id == user_id, ShopeeListing.status == "live")
        .order_by(desc(ShopeeListing.updated_at), desc(ShopeeListing.id))
    )
    safe_keyword = keyword.strip()
    if safe_keyword:
        like = f"%{safe_keyword}%"
        if search_field == "sku":
            query = query.filter(ShopeeListing.sku_code.ilike(like))
        elif search_field == "product_id" and safe_keyword.isdigit():
            query = query.filter(ShopeeListing.product_id == int(safe_keyword))
        else:
            query = query.filter(ShopeeListing.title.ilike(like))

    conflict_rows = (
        db.query(ShopeeFlashSaleCampaignItem)
        .join(ShopeeFlashSaleCampaign, ShopeeFlashSaleCampaign.id == ShopeeFlashSaleCampaignItem.campaign_id)
        .filter(
            ShopeeFlashSaleCampaign.run_id == run.id,
            ShopeeFlashSaleCampaign.user_id == user_id,
            ShopeeFlashSaleCampaign.slot_date == slot_date,
            ShopeeFlashSaleCampaign.slot_key == slot_key,
            ShopeeFlashSaleCampaign.status == "active",
            ShopeeFlashSaleCampaignItem.status == "active",
        )
        .all()
    )
    conflicts = {(row.listing_id, row.variant_id) for row in conflict_rows}

    all_items: list[ShopeeFlashSaleProductRowResponse] = []
    for listing in query.all():
        row_category_key = _flash_sale_category_key_for_listing(listing, rules, category_by_product_id)
        if category_key and category_key != "all" and row_category_key != category_key:
            continue
        row_category_label = category_by_product_id.get(listing.product_id or 0) or label_by_key.get(row_category_key, "全部")
        variants = [variant for variant in sorted(listing.variants, key=lambda row: row.sort_order) if variant.stock > 0 and variant.price > 0]
        if variants:
            stock_available = sum(int(variant.stock or 0) for variant in variants)
            min_price = min(float(variant.price or 0) for variant in variants)
            max_price = max(float(variant.price or 0) for variant in variants)
            key = (listing.id, None)
            variation_rows = [
                {
                    "listing_id": listing.id,
                    "variant_id": variant.id,
                    "product_id": listing.product_id,
                    "product_name": listing.title,
                    "variant_name": variant.option_value or "默认款式",
                    "sku": variant.sku,
                    "image_url": listing.cover_url,
                    "category_key": row_category_key,
                    "category_label": row_category_label,
                    "original_price": round(float(variant.price or 0), 2),
                    "price_range_label": None,
                    "stock_available": int(variant.stock or 0),
                    "rating": float(listing.quality_total_score or 0) / 20 if listing.quality_total_score is not None else None,
                    "likes_count": 0,
                    "orders_30d": 0,
                    "ship_days": None,
                    "is_preorder": bool(listing.preorder_enabled),
                    "conflict": (listing.id, variant.id) in conflicts,
                    "conflict_reason": "该商品已参加当前时间段限时抢购" if (listing.id, variant.id) in conflicts else None,
                    "suggested_flash_price": round(float(variant.price or 0) * 0.9, 2) if (variant.price or 0) > 0 else None,
                    "flash_price": round(float(variant.price or 0) * 0.9, 2) if (variant.price or 0) > 0 else None,
                    "activity_stock_limit": min(max(int(variant.stock or 0), 5), 10000),
                    "purchase_limit_per_buyer": 1,
                    "variations": [],
                }
                for variant in variants
            ]
            all_items.append(
                _build_flash_sale_product_row(
                    listing=listing,
                    variant=None,
                    category_key=row_category_key,
                    category_label=row_category_label,
                    conflict=any((listing.id, variant.id) in conflicts for variant in variants) or key in conflicts,
                    conflict_reason="该商品已参加当前时间段限时抢购" if any((listing.id, variant.id) in conflicts for variant in variants) or key in conflicts else None,
                    flash_price=round(min_price * 0.9, 2) if min_price > 0 else None,
                    activity_stock_limit=min(max(stock_available, 5), 10000),
                ).model_copy(
                    update={
                        "variant_id": None,
                        "variant_name": "",
                        "sku": listing.sku_code,
                        "image_url": listing.cover_url,
                        "original_price": round(min_price, 2),
                        "price_range_label": f"RM {min_price:.2f}" if min_price == max_price else f"RM {min_price:.2f} - RM {max_price:.2f}",
                        "stock_available": stock_available,
                        "suggested_flash_price": round(min_price * 0.9, 2) if min_price > 0 else None,
                        "variations": variation_rows,
                    }
                )
            )
        elif listing.stock_available > 0 and listing.price > 0:
            key = (listing.id, None)
            all_items.append(_build_flash_sale_product_row(listing=listing, variant=None, category_key=row_category_key, category_label=row_category_label, conflict=key in conflicts, conflict_reason="该商品已参加当前时间段限时抢购" if key in conflicts else None))

    total = len(all_items)
    start = max(0, (page - 1) * page_size)
    end = start + page_size
    return ShopeeFlashSaleEligibleProductsResponse(page=page, page_size=page_size, total=total, items=all_items[start:end])


def _flash_sale_status(campaign: ShopeeFlashSaleCampaign, *, current_tick: datetime) -> str:
    if campaign.status == "disabled":
        return "disabled"
    if current_tick < campaign.start_tick:
        return "upcoming"
    if current_tick >= campaign.end_tick:
        return "ended"
    return "ongoing"


def _flash_sale_status_label(value: str) -> str:
    return {"upcoming": "即将开始", "ongoing": "进行中", "ended": "已结束", "disabled": "已停用", "draft": "草稿"}.get(value, value)


def _load_flash_sale_campaign_or_404(db: Session, *, run_id: int, user_id: int, campaign_id: int) -> ShopeeFlashSaleCampaign:
    campaign = (
        db.query(ShopeeFlashSaleCampaign)
        .options(selectinload(ShopeeFlashSaleCampaign.items), selectinload(ShopeeFlashSaleCampaign.run))
        .filter(ShopeeFlashSaleCampaign.id == campaign_id, ShopeeFlashSaleCampaign.run_id == run_id, ShopeeFlashSaleCampaign.user_id == user_id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="限时抢购活动不存在")
    return campaign


def _validate_flash_sale_items(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    slot_date: date,
    slot_key: str,
    items: list[ShopeeFlashSaleItemPayload],
) -> tuple[ShopeeFlashSaleSlot, dict[int, ShopeeListing], dict[int, ShopeeListingVariant]]:
    slots = {slot.slot_key: slot for slot in _load_flash_sale_slots(db, run.market)}
    slot = slots.get(slot_key)
    if not slot:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择有效的限时抢购时间段")
    if not items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请至少添加 1 个商品")
    if any(item.status not in {"active", "disabled"} for item in items):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="商品启停状态无效")
    active_items = [item for item in items if item.status == "active"]
    if not active_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请至少启用 1 个商品")
    if len(active_items) > int(slot.product_limit or 50):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"单个时间段最多可启用 {slot.product_limit} 个商品")

    listing_ids = {item.listing_id for item in items}
    variant_ids = {item.variant_id for item in items if item.variant_id}
    listing_map = {
        row.id: row
        for row in db.query(ShopeeListing)
        .filter(ShopeeListing.run_id == run.id, ShopeeListing.user_id == user_id, ShopeeListing.id.in_(listing_ids))
        .all()
    } if listing_ids else {}
    variant_map = {row.id: row for row in db.query(ShopeeListingVariant).filter(ShopeeListingVariant.id.in_(variant_ids)).all()} if variant_ids else {}

    dedupe: set[tuple[int, int | None]] = set()
    for item in items:
        key = (item.listing_id, item.variant_id)
        if key in dedupe:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="同一商品/变体不能重复添加")
        dedupe.add(key)
        listing = listing_map.get(item.listing_id)
        if not listing or listing.status != "live":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所选商品不存在或不是上架状态")
        variant = variant_map.get(item.variant_id) if item.variant_id else None
        if item.variant_id and (not variant or variant.listing_id != listing.id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所选商品规格不存在")
        original_price = float(variant.price if variant else listing.price)
        stock_available = int(variant.stock if variant else listing.stock_available)
        if original_price <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="商品原价必须大于 0")
        if stock_available <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="商品库存不足，无法加入活动")
        if item.flash_price <= 0 or item.flash_price >= original_price:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="限时抢购价必须大于 0 且小于原价")
        discount_percent = (1 - float(item.flash_price) / original_price) * 100
        if discount_percent < 5 or discount_percent > 99:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="折扣限制为 5% ~ 99%")
        if item.activity_stock_limit < 5 or item.activity_stock_limit > 10000 or item.activity_stock_limit > stock_available:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="活动库存需在 5 ~ 10000 范围内且不超过可售库存")
        if item.purchase_limit_per_buyer < 1 or item.purchase_limit_per_buyer > 99:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="每人限购数量需在 1 ~ 99 范围内")

    existing = (
        db.query(ShopeeFlashSaleCampaignItem)
        .join(ShopeeFlashSaleCampaign, ShopeeFlashSaleCampaign.id == ShopeeFlashSaleCampaignItem.campaign_id)
        .filter(
            ShopeeFlashSaleCampaign.run_id == run.id,
            ShopeeFlashSaleCampaign.user_id == user_id,
            ShopeeFlashSaleCampaign.slot_date == slot_date,
            ShopeeFlashSaleCampaign.slot_key == slot_key,
            ShopeeFlashSaleCampaign.status == "active",
            ShopeeFlashSaleCampaignItem.status == "active",
        )
        .all()
    )
    occupied = {(row.listing_id, row.variant_id) for row in existing}
    for item in active_items:
        if (item.listing_id, item.variant_id) in occupied:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="同一 SKU 在当前时间段已参加限时抢购")
    if len(existing) + len(active_items) > int(slot.product_limit or 50):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前时间段剩余商品名额不足")
    return slot, listing_map, variant_map


def _build_flash_sale_draft_detail_response(db: Session, draft: ShopeeFlashSaleDraft) -> ShopeeFlashSaleDraftDetailResponse:
    run = db.query(GameRun).filter(GameRun.id == draft.run_id).first()
    rules = _load_flash_sale_category_rules(db, run.market if run else "MY")
    label_by_key = {rule.category_key: rule.category_label for rule in rules}
    category_by_product_id = _flash_sale_market_category_by_product_id(db, run_id=draft.run_id)
    listing_ids = {item.listing_id for item in draft.items}
    variant_ids = {item.variant_id for item in draft.items if item.variant_id}
    listing_map = {row.id: row for row in db.query(ShopeeListing).filter(ShopeeListing.id.in_(listing_ids)).all()} if listing_ids else {}
    variant_map = {row.id: row for row in db.query(ShopeeListingVariant).filter(ShopeeListingVariant.id.in_(variant_ids)).all()} if variant_ids else {}
    rows = []
    for item in draft.items:
        listing = listing_map.get(item.listing_id)
        if not listing:
            continue
        category_key = _flash_sale_category_key_for_listing(listing, rules, category_by_product_id)
        category_label = category_by_product_id.get(listing.product_id or 0) or label_by_key.get(category_key, "全部")
        rows.append(_build_flash_sale_product_row(listing=listing, variant=variant_map.get(item.variant_id) if item.variant_id else None, category_key=category_key, category_label=category_label, flash_price=item.flash_price, activity_stock_limit=item.activity_stock_limit, purchase_limit_per_buyer=item.purchase_limit_per_buyer))
    return ShopeeFlashSaleDraftDetailResponse(id=draft.id, campaign_name=draft.campaign_name, slot_date=draft.slot_date.isoformat() if draft.slot_date else None, slot_key=draft.slot_key, items=rows, created_at=draft.created_at, updated_at=draft.updated_at)


def _safe_load_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data if str(item).strip()]


def _extract_image_feedback(raw: str | None) -> list[ShopeeListingQualityImageFeedbackItem]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    model_data = data.get("model") if isinstance(data.get("model"), dict) else {}
    feedback_raw = model_data.get("image_feedback")
    image_inputs_raw = model_data.get("image_inputs")
    feedback_rows = feedback_raw if isinstance(feedback_raw, list) else []
    image_inputs = image_inputs_raw if isinstance(image_inputs_raw, list) else []

    out: list[ShopeeListingQualityImageFeedbackItem] = []
    by_ref: dict[str, ShopeeListingQualityImageFeedbackItem] = {}
    for idx, row in enumerate(feedback_rows, start=1):
        if isinstance(row, str):
            text = row.strip()
            if text:
                item = ShopeeListingQualityImageFeedbackItem(
                    image_ref=f"IMG{idx}",
                    image_label=f"图片{idx}",
                    score=None,
                    good=text,
                    bad="",
                    suggestion="",
                )
                out.append(item)
                by_ref[item.image_ref] = item
            continue
        if not isinstance(row, dict):
            continue
        image_ref = str(row.get("image_ref") or row.get("image") or f"IMG{idx}").strip()
        image_label = str(row.get("image_label") or row.get("label") or f"图片{idx}").strip() or f"图片{idx}"
        score = row.get("score")
        good = str(row.get("good") or row.get("strength") or "").strip() or "无"
        bad = str(row.get("bad") or row.get("issue") or "").strip() or "无"
        suggestion = str(row.get("suggestion") or "").strip() or "无"
        item = ShopeeListingQualityImageFeedbackItem(
            image_ref=image_ref,
            image_label=image_label,
            score=int(score) if isinstance(score, (int, float)) else None,
            good=good,
            bad=bad,
            suggestion=suggestion,
        )
        out.append(item)
        by_ref[item.image_ref] = item

    # Ensure each input image has a row (prevents "missing main image" in UI).
    for idx, row in enumerate(image_inputs, start=1):
        if not isinstance(row, dict):
            continue
        image_ref = str(row.get("image_ref") or f"IMG{idx}").strip() or f"IMG{idx}"
        if image_ref in by_ref:
            continue
        image_label = str(row.get("image_label") or f"图片{idx}").strip() or f"图片{idx}"
        out.append(
            ShopeeListingQualityImageFeedbackItem(
                image_ref=image_ref,
                image_label=image_label,
                score=None,
                good="",
                bad="",
                suggestion="",
            )
        )
    return out


def _extract_quality_summary(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    model_data = data.get("model") if isinstance(data.get("model"), dict) else {}
    summary = str(model_data.get("summary") or "").strip()
    if summary:
        return summary
    single_pass = model_data.get("single_pass") if isinstance(model_data.get("single_pass"), dict) else {}
    summary = str(
        single_pass.get("summary")
        or single_pass.get("evaluation_summary")
        or single_pass.get("overall_summary")
        or ""
    ).strip()
    return summary or None


def _try_recompute_listing_quality(
    db: Session,
    *,
    listing_id: int,
    run_id: int,
    user_id: int,
    force_recompute: bool = False,
) -> None:
    try:
        recompute_listing_quality(
            db,
            listing_id=listing_id,
            run_id=run_id,
            user_id=user_id,
            force_recompute=force_recompute,
        )
        db.commit()
    except Exception:
        db.rollback()


def _ensure_run_writable_or_400(db: Session, run: GameRun, *, tick_time: datetime | None = None) -> None:
    if _persist_run_finished_if_reached(db, run):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=RUN_FINISHED_DETAIL)


def _save_shopee_image(db: Session, image: UploadFile) -> str:
    try:
        import boto3
    except ImportError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务端缺少 boto3 依赖") from exc

    content_type = (image.content_type or "").lower()
    allow_map = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    suffix = allow_map.get(content_type)
    if not suffix:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 JPG/PNG/WEBP 图片")

    data = image.file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="图片内容为空")
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="图片大小不能超过 5MB")

    oss_config = db.query(OssStorageConfig).filter(OssStorageConfig.is_active == True).order_by(OssStorageConfig.id.desc()).first()
    if not oss_config:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="未配置可用 OSS 存储")

    object_key = f"shopee/{datetime.now().strftime('%Y%m%d')}/{uuid4().hex}{suffix}"
    client = boto3.client(
        "s3",
        endpoint_url=oss_config.endpoint,
        aws_access_key_id=oss_config.access_key,
        aws_secret_access_key=oss_config.access_secret,
    )
    try:
        client.put_object(
            Bucket=oss_config.bucket,
            Key=object_key,
            Body=data,
            ContentType=content_type,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"OSS 上传失败: {exc}") from exc

    return f"{oss_config.domain.rstrip('/')}/{object_key.lstrip('/')}"


def _save_shopee_video(db: Session, video: UploadFile) -> str:
    try:
        import boto3
    except ImportError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务端缺少 boto3 依赖") from exc

    content_type = (video.content_type or "").lower()
    allow_map = {
        "video/mp4": ".mp4",
    }
    suffix = allow_map.get(content_type)
    if not suffix:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 MP4 视频")

    data = video.file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="视频内容为空")
    if len(data) > 30 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="视频大小不能超过 30MB")

    oss_config = db.query(OssStorageConfig).filter(OssStorageConfig.is_active == True).order_by(OssStorageConfig.id.desc()).first()
    if not oss_config:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="未配置可用 OSS 存储")

    object_key = f"shopee/{datetime.now().strftime('%Y%m%d')}/{uuid4().hex}{suffix}"
    client = boto3.client(
        "s3",
        endpoint_url=oss_config.endpoint,
        aws_access_key_id=oss_config.access_key,
        aws_secret_access_key=oss_config.access_secret,
    )
    try:
        client.put_object(
            Bucket=oss_config.bucket,
            Key=object_key,
            Body=data,
            ContentType=content_type,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"OSS 上传失败: {exc}") from exc

    return f"{oss_config.domain.rstrip('/')}/{object_key.lstrip('/')}"


def _apply_filters(
    query,
    *,
    type_value: str,
    source: str | None,
    order_type: str,
    order_status: str,
    priority: str,
    keyword: str | None,
    channel: str | None,
):
    if type_value and type_value != "all":
        target_bucket = "cancelled" if type_value == "return_refund_cancel" else type_value
        query = query.filter(ShopeeOrder.type_bucket == target_bucket)

    if source == "to_process":
        query = query.filter(ShopeeOrder.process_status == "processing")

    if order_type != "all":
        query = query.filter(ShopeeOrder.order_type == order_type)

    if order_status != "all":
        query = query.filter(ShopeeOrder.process_status == order_status)

    if priority != "all":
        query = query.filter(ShopeeOrder.shipping_priority == priority)

    if keyword:
        kw = keyword.strip()
        if kw:
            query = query.filter(ShopeeOrder.order_no.ilike(f"%{kw}%"))

    if channel:
        ch = channel.strip()
        if ch:
            query = query.filter(ShopeeOrder.shipping_channel == ch)

    return query


LOGISTICS_FLOW = [
    "label_created",
    "picked_up",
    "in_transit",
    "out_for_delivery",
    "delivered",
]

LOGISTICS_EVENT_META = {
    "label_created": ("已创建运单", "卖家已安排发货并生成面单"),
    "picked_up": ("已揽件", "包裹已由承运商揽收"),
    "in_transit": ("运输中", "包裹正在干线运输"),
    "out_for_delivery": ("派送中", "包裹正在末端派送"),
    "delivered": ("已签收", "包裹已完成签收"),
    "cancelled_by_buyer": ("买家取消订单", "卖家超时未发货，买家取消订单"),
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


def _get_owned_order_or_404(db: Session, run_id: int, user_id: int, order_id: int) -> ShopeeOrder:
    order = (
        db.query(ShopeeOrder)
        .filter(
            ShopeeOrder.id == order_id,
            ShopeeOrder.run_id == run_id,
            ShopeeOrder.user_id == user_id,
        )
        .first()
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    return order


def _resolve_buyer_latlng(db: Session, buyer_name: str, destination: str | None) -> tuple[float, float]:
    profile = db.query(SimBuyerProfile).filter(SimBuyerProfile.nickname == buyer_name).first()
    if profile and profile.lat is not None and profile.lng is not None:
        return float(profile.lat), float(profile.lng)
    if profile and profile.city_code and profile.city_code in BUYER_CITY_COORDS:
        return BUYER_CITY_COORDS[profile.city_code]
    for code, coords in BUYER_CITY_COORDS.items():
        if destination and code.endswith(destination[:3].upper()):
            return coords
    return BUYER_CITY_COORDS["MY-KUL"]


def _resolve_warehouse_latlng(db: Session, run: GameRun) -> tuple[float, float]:
    strategy = (
        db.query(WarehouseStrategy)
        .filter(WarehouseStrategy.run_id == run.id, WarehouseStrategy.user_id == run.user_id)
        .order_by(WarehouseStrategy.id.desc())
        .first()
    )
    if strategy:
        point = (
            db.query(WarehouseLandmark)
            .filter(
                WarehouseLandmark.market == run.market,
                WarehouseLandmark.warehouse_mode == strategy.warehouse_mode,
                WarehouseLandmark.warehouse_location == strategy.warehouse_location,
                WarehouseLandmark.is_active == True,
            )
            .first()
        )
        if point:
            return float(point.lat), float(point.lng)

    fallback = (
        db.query(WarehouseLandmark)
        .filter(WarehouseLandmark.market == run.market, WarehouseLandmark.is_active == True)
        .order_by(WarehouseLandmark.sort_order.asc(), WarehouseLandmark.id.asc())
        .first()
    )
    if fallback:
        return float(fallback.lat), float(fallback.lng)
    return BUYER_CITY_COORDS["MY-KUL"]


def _resolve_forwarder_for_order(
    db: Session,
    *,
    run_id: int,
    user_id: int,
    shipping_channel: str,
) -> tuple[str, str]:
    latest_shipment = (
        db.query(LogisticsShipment)
        .filter(
            LogisticsShipment.run_id == run_id,
            LogisticsShipment.user_id == user_id,
        )
        .order_by(LogisticsShipment.created_at.desc(), LogisticsShipment.id.desc())
        .first()
    )
    if latest_shipment and latest_shipment.forwarder_key in LINE_TRANSIT_DAY_BOUNDS:
        key = latest_shipment.forwarder_key
        return key, latest_shipment.forwarder_label or FORWARDER_KEY_TO_LABEL.get(key, "标准线（马来）")
    mapped_key = CHANNEL_TO_FORWARDER_KEY.get(shipping_channel, "standard")
    return mapped_key, FORWARDER_KEY_TO_LABEL.get(mapped_key, "标准线（马来）")


def _calc_transit_days_by_line_and_distance(
    *,
    forwarder_key: str,
    distance_km: float,
) -> tuple[int, int, int]:
    min_days, max_days = LINE_TRANSIT_DAY_BOUNDS.get(forwarder_key, LINE_TRANSIT_DAY_BOUNDS["standard"])
    if distance_km <= 80:
        ratio = 0.10
    elif distance_km <= 300:
        ratio = 0.35
    elif distance_km <= 800:
        ratio = 0.65
    else:
        ratio = 1.00
    raw_days = min_days + (max_days - min_days) * ratio
    transit_days = max(min_days, min(max_days, int(round(raw_days))))
    return transit_days, min_days, max_days


def _resolve_event_milestone_time(
    *,
    event_code: str,
    shipped_at: datetime,
    delivered_due_at: datetime,
) -> datetime:
    total_seconds = max(2 * 3600, int((delivered_due_at - shipped_at).total_seconds()))
    if event_code == "label_created":
        return shipped_at
    if event_code == "delivered":
        return delivered_due_at

    stage_ratio = {
        "picked_up": 0.08,
        "in_transit": 0.45,
        "out_for_delivery": 0.82,
    }.get(event_code, 0.45)
    return shipped_at + timedelta(seconds=int(total_seconds * stage_ratio))


def _resolve_line_meta_by_channel(shipping_channel: str) -> tuple[str, str]:
    forwarder_key = CHANNEL_TO_FORWARDER_KEY.get(shipping_channel, "standard")
    label = FORWARDER_KEY_TO_LABEL.get(forwarder_key, "标准线（马来）")
    return forwarder_key, label


def _infer_forwarder_key_by_eta(order: ShopeeOrder) -> str | None:
    if not order.shipped_at or not order.eta_start_at:
        return None
    expected_days = max(
        1,
        int(round((order.eta_start_at - order.shipped_at).total_seconds() / REAL_SECONDS_PER_GAME_DAY)),
    )

    matched_keys: list[str] = []
    for key, (min_days, max_days) in LINE_TRANSIT_DAY_BOUNDS.items():
        if min_days <= expected_days <= max_days:
            matched_keys.append(key)
    if len(matched_keys) == 1:
        return matched_keys[0]
    if len(matched_keys) > 1:
        return matched_keys[0]

    scored = sorted(
        LINE_TRANSIT_DAY_BOUNDS.items(),
        key=lambda kv: abs(((kv[1][0] + kv[1][1]) / 2) - expected_days),
    )
    return scored[0][0] if scored else None


def _calc_order_shipping_metrics(order: ShopeeOrder, current_tick: datetime) -> dict[str, int | str | None]:
    forwarder_key: str | None = None
    line_label: str | None = None

    if order.delivery_line_key and order.delivery_line_key in LINE_TRANSIT_DAY_BOUNDS:
        forwarder_key = order.delivery_line_key
        line_label = order.delivery_line_label or FORWARDER_KEY_TO_LABEL.get(forwarder_key, "标准线（马来）")
    else:
        inferred_key = _infer_forwarder_key_by_eta(order)
        if inferred_key and inferred_key in LINE_TRANSIT_DAY_BOUNDS:
            forwarder_key = inferred_key
            line_label = FORWARDER_KEY_TO_LABEL.get(forwarder_key, "标准线（马来）")
        else:
            forwarder_key, line_label = _resolve_line_meta_by_channel(order.shipping_channel or "")

    min_days, max_days = LINE_TRANSIT_DAY_BOUNDS.get(forwarder_key, LINE_TRANSIT_DAY_BOUNDS["standard"])
    promised_text = f"{min_days}~{max_days}天"

    expected_days: int | None = None
    elapsed_days: int | None = None
    remaining_days: int | None = None
    if order.shipped_at and order.eta_start_at:
        delta_sec = (order.eta_start_at - order.shipped_at).total_seconds()
        expected_days = max(1, int(round(delta_sec / REAL_SECONDS_PER_GAME_DAY)))
        elapsed_days = max(0, int((current_tick - order.shipped_at).total_seconds() // REAL_SECONDS_PER_GAME_DAY))
        if order.type_bucket == "completed":
            remaining_days = 0
        else:
            remaining_days = max(0, expected_days - elapsed_days)

    return {
        "delivery_line_label": line_label,
        "promised_transit_days_text": promised_text,
        "transit_days_expected": expected_days,
        "transit_days_elapsed": elapsed_days,
        "transit_days_remaining": remaining_days,
    }


def _next_event_code(current_event_code: str | None) -> str:
    if not current_event_code:
        return LOGISTICS_FLOW[0]
    if current_event_code not in LOGISTICS_FLOW:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前物流节点非法")
    idx = LOGISTICS_FLOW.index(current_event_code)
    if idx >= len(LOGISTICS_FLOW) - 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="物流已签收，无法继续推进")
    return LOGISTICS_FLOW[idx + 1]


def _resolve_game_tick(db: Session, run_id: int, user_id: int) -> datetime:
    latest_tick_time = (
        db.query(func.max(ShopeeOrderGenerationLog.tick_time))
        .filter(
            ShopeeOrderGenerationLog.run_id == run_id,
            ShopeeOrderGenerationLog.user_id == user_id,
        )
        .scalar()
    )
    if latest_tick_time:
        return latest_tick_time
    run = db.query(GameRun).filter(GameRun.id == run_id, GameRun.user_id == user_id).first()
    if run is not None:
        return _resolve_game_hour_tick_by_run(run)
    return datetime.now()


def _has_flash_sale_overlap_for_order_simulation(
    db: Session,
    *,
    run_id: int,
    user_id: int,
    base_tick: datetime,
    current_game_tick: datetime,
) -> bool:
    return db.query(ShopeeFlashSaleCampaign.id).filter(
        ShopeeFlashSaleCampaign.run_id == run_id,
        ShopeeFlashSaleCampaign.user_id == user_id,
        ShopeeFlashSaleCampaign.status == "active",
        ShopeeFlashSaleCampaign.start_tick < current_game_tick,
        ShopeeFlashSaleCampaign.end_tick > base_tick,
    ).first() is not None


def _auto_simulate_orders_by_game_hour(
    db: Session,
    *,
    run: GameRun,
    user_id: int,
    max_ticks_per_request: int = 240,
) -> None:
    latest_tick_time = (
        db.query(func.max(ShopeeOrderGenerationLog.tick_time))
        .filter(
            ShopeeOrderGenerationLog.run_id == run.id,
            ShopeeOrderGenerationLog.user_id == user_id,
        )
        .scalar()
    )
    base_tick = latest_tick_time or run.created_at
    if not base_tick:
        return

    current_game_tick = _resolve_game_hour_tick_by_run(run)
    if base_tick > current_game_tick:
        logger.warning(
            "[order-auto-sim] clamp future base_tick run_id=%s user_id=%s latest_tick_time=%s base_tick=%s current_game_tick=%s",
            run.id,
            user_id,
            latest_tick_time,
            base_tick,
            current_game_tick,
        )
        base_tick = current_game_tick
    has_flash_sale_overlap = _has_flash_sale_overlap_for_order_simulation(
        db,
        run_id=run.id,
        user_id=user_id,
        base_tick=base_tick,
        current_game_tick=current_game_tick,
    )
    tick_game_hours = 1 if has_flash_sale_overlap else ORDER_SIM_TICK_GAME_HOURS
    step_seconds = max(1, int(REAL_SECONDS_PER_GAME_HOUR * tick_game_hours))
    missing_steps = int((current_game_tick - base_tick).total_seconds() // step_seconds)
    logger.info(
        "[order-auto-sim] run_id=%s user_id=%s latest_tick_time=%s base_tick=%s current_game_tick=%s step_seconds=%s missing_steps=%s max_ticks_per_request=%s",
        run.id,
        user_id,
        latest_tick_time,
        base_tick,
        current_game_tick,
        step_seconds,
        missing_steps,
        max_ticks_per_request,
    )
    if missing_steps <= 0:
        return

    ticks_to_run = min(missing_steps, max(1, int(max_ticks_per_request)))
    logger.info(
        "[order-auto-sim] run_id=%s user_id=%s ticks_to_run=%s",
        run.id,
        user_id,
        ticks_to_run,
    )
    for offset in range(1, ticks_to_run + 1):
        simulate_orders_for_run(
            db,
            run_id=run.id,
            user_id=user_id,
            tick_time=base_tick + timedelta(seconds=offset * step_seconds),
        )


def _upsert_order_settlement(
    db: Session,
    *,
    run_id: int,
    user_id: int,
    order: ShopeeOrder,
    settled_at: datetime,
) -> None:
    shipping_cost = calc_shipping_cost(float(order.distance_km or 0), order.shipping_channel)
    settlement_data = calc_settlement(
        buyer_payment=float(order.buyer_payment or 0),
        shipping_cost=shipping_cost,
        shipping_channel=order.shipping_channel,
    )
    shipping_promotion_discount = round(float(order.shipping_promotion_discount_amount or 0), 2)
    settlement_data["shipping_promotion_discount_amount"] = shipping_promotion_discount
    settlement_data["net_income_amount"] = round(float(settlement_data["net_income_amount"] or 0) - shipping_promotion_discount, 2)
    settlement = (
        db.query(ShopeeOrderSettlement)
        .filter(
            ShopeeOrderSettlement.run_id == run_id,
            ShopeeOrderSettlement.user_id == user_id,
            ShopeeOrderSettlement.order_id == order.id,
        )
        .first()
    )
    if not settlement:
        # Concurrency-safe create: another request/worker may insert the same order_id
        # between "query none" and commit. Use savepoint + flush and fallback to update.
        try:
            with db.begin_nested():
                db.add(
                    ShopeeOrderSettlement(
                        run_id=run_id,
                        user_id=user_id,
                        order_id=order.id,
                        **settlement_data,
                        settlement_status="settled",
                        settled_at=settled_at,
                    )
                )
                db.flush()
            return
        except IntegrityError:
            settlement = (
                db.query(ShopeeOrderSettlement)
                .filter(
                    ShopeeOrderSettlement.run_id == run_id,
                    ShopeeOrderSettlement.user_id == user_id,
                    ShopeeOrderSettlement.order_id == order.id,
                )
                .first()
            )
            if not settlement:
                raise
    for key, value in settlement_data.items():
        setattr(settlement, key, value)
    settlement.settlement_status = "settled"
    settlement.settled_at = settled_at


def _calc_wallet_balance(db: Session, *, run_id: int, user_id: int) -> float:
    in_sum = (
        db.query(func.coalesce(func.sum(ShopeeFinanceLedgerEntry.amount), 0.0))
        .filter(
            ShopeeFinanceLedgerEntry.run_id == run_id,
            ShopeeFinanceLedgerEntry.user_id == user_id,
            ShopeeFinanceLedgerEntry.status == "completed",
            ShopeeFinanceLedgerEntry.direction == "in",
        )
        .scalar()
        or 0.0
    )
    out_sum = (
        db.query(func.coalesce(func.sum(ShopeeFinanceLedgerEntry.amount), 0.0))
        .filter(
            ShopeeFinanceLedgerEntry.run_id == run_id,
            ShopeeFinanceLedgerEntry.user_id == user_id,
            ShopeeFinanceLedgerEntry.status == "completed",
            ShopeeFinanceLedgerEntry.direction == "out",
        )
        .scalar()
        or 0.0
    )
    return round(float(in_sum) - float(out_sum), 2)


def _credit_order_income_if_needed(
    db: Session,
    *,
    run_id: int,
    user_id: int,
    order: ShopeeOrder,
    credited_at: datetime,
) -> bool:
    if order.type_bucket != "completed":
        return False
    if order.cancelled_at is not None or order.cancel_reason:
        return False
    if not order.delivered_at:
        return False

    release_at = order.delivered_at + timedelta(seconds=ORDER_INCOME_RELEASE_DELAY_GAME_DAYS * REAL_SECONDS_PER_GAME_DAY)
    if credited_at < release_at:
        return False

    settlement = (
        db.query(ShopeeOrderSettlement)
        .filter(
            ShopeeOrderSettlement.run_id == run_id,
            ShopeeOrderSettlement.user_id == user_id,
            ShopeeOrderSettlement.order_id == order.id,
            ShopeeOrderSettlement.settlement_status == "settled",
        )
        .first()
    )
    if not settlement:
        return False

    existing = (
        db.query(ShopeeFinanceLedgerEntry)
        .filter(
            ShopeeFinanceLedgerEntry.run_id == run_id,
            ShopeeFinanceLedgerEntry.user_id == user_id,
            ShopeeFinanceLedgerEntry.order_id == order.id,
            ShopeeFinanceLedgerEntry.entry_type == "income_from_order",
        )
        .first()
    )
    if existing:
        return False

    net_income = float(settlement.net_income_amount or 0.0)
    direction = "in" if net_income >= 0 else "out"
    amount = abs(round(net_income, 2))
    if amount <= 0:
        return False

    current_balance = _calc_wallet_balance(db, run_id=run_id, user_id=user_id)
    signed_delta = amount if direction == "in" else -amount
    balance_after = round(current_balance + signed_delta, 2)
    remark = f"订单回款 {order.order_no}"

    try:
        with db.begin_nested():
            db.add(
                ShopeeFinanceLedgerEntry(
                    run_id=run_id,
                    user_id=user_id,
                    order_id=order.id,
                    entry_type="income_from_order",
                    direction=direction,
                    amount=amount,
                    balance_after=balance_after,
                    status="completed",
                    remark=remark,
                    credited_at=release_at,
                )
            )
            db.flush()
    except IntegrityError:
        # 并发情况下可能被其他请求先写入，同订单仅允许一条回款流水。
        return False
    return True


def _resolve_game_day_start(run: GameRun, current_tick: datetime) -> datetime:
    if not run.created_at:
        return current_tick
    elapsed_seconds = max(0, int((current_tick - run.created_at).total_seconds()))
    elapsed_hours = elapsed_seconds // 3600
    day_index = elapsed_hours // 24
    return run.created_at + timedelta(hours=day_index * 24)


def _resolve_game_week_start(current_tick: datetime) -> datetime:
    week_start = current_tick - timedelta(days=current_tick.weekday())
    return week_start.replace(hour=0, minute=0, second=0, microsecond=0)


def _resolve_game_month_start(current_tick: datetime) -> datetime:
    return current_tick.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _mask_bank_account_no(raw: str) -> str:
    text_no = (raw or "").strip().replace(" ", "")
    if not text_no:
        return "****"
    suffix = text_no[-4:] if len(text_no) >= 4 else text_no
    return f"**** {suffix}"


def _apply_logistics_transition(
    db: Session,
    *,
    run_id: int,
    user_id: int,
    order: ShopeeOrder,
    event_code: str,
    event_time: datetime,
) -> None:
    title, desc_text = LOGISTICS_EVENT_META[event_code]
    db.add(
        ShopeeOrderLogisticsEvent(
            run_id=run_id,
            user_id=user_id,
            order_id=order.id,
            event_code=event_code,
            event_title=title,
            event_desc=desc_text,
            event_time=event_time,
        )
    )
    if event_code != "delivered":
        order.type_bucket = "shipping"
        order.process_status = "processed"
        order.countdown_text = title
        return

    order.type_bucket = "completed"
    order.process_status = "processed"
    order.delivered_at = event_time
    order.countdown_text = "订单已签收"
    if not order.shipped_at:
        order.shipped_at = event_time
    _upsert_order_settlement(
        db,
        run_id=run_id,
        user_id=user_id,
        order=order,
        settled_at=event_time,
    )
    _credit_order_income_if_needed(
        db,
        run_id=run_id,
        user_id=user_id,
        order=order,
        credited_at=event_time,
    )


def _cancel_order(
    db: Session,
    *,
    run_id: int,
    user_id: int,
    order: ShopeeOrder,
    cancel_time: datetime,
    reason: str,
    source: str,
) -> None:
    service_cancel_order(
        db,
        run_id=run_id,
        user_id=user_id,
        order=order,
        cancel_time=cancel_time,
        reason=reason,
        source=source,
    )


def _auto_cancel_overdue_orders_by_tick(
    db: Session,
    *,
    run_id: int,
    user_id: int,
    current_tick: datetime,
) -> None:
    service_auto_cancel_overdue_orders_by_tick(
        db,
        run_id=run_id,
        user_id=user_id,
        current_tick=current_tick,
        commit=True,
    )


def _auto_progress_shipping_orders_by_tick(
    db: Session,
    *,
    run_id: int,
    user_id: int,
    current_tick: datetime,
) -> None:
    shipping_orders = (
        db.query(ShopeeOrder)
        .filter(
            ShopeeOrder.run_id == run_id,
            ShopeeOrder.user_id == user_id,
            ShopeeOrder.type_bucket == "shipping",
        )
        .all()
    )
    changed = False
    for order in shipping_orders:
        latest_event = (
            db.query(ShopeeOrderLogisticsEvent)
            .filter(
                ShopeeOrderLogisticsEvent.run_id == run_id,
                ShopeeOrderLogisticsEvent.user_id == user_id,
                ShopeeOrderLogisticsEvent.order_id == order.id,
            )
            .order_by(ShopeeOrderLogisticsEvent.event_time.desc(), ShopeeOrderLogisticsEvent.id.desc())
            .first()
        )
        if not latest_event or latest_event.event_code == "delivered":
            continue
        if not order.shipped_at:
            continue
        delivered_due_at = order.eta_start_at or (order.shipped_at + timedelta(seconds=3 * REAL_SECONDS_PER_GAME_DAY))
        if delivered_due_at <= order.shipped_at:
            delivered_due_at = order.shipped_at + timedelta(seconds=REAL_SECONDS_PER_GAME_DAY)

        step_code = latest_event.event_code
        if step_code not in LOGISTICS_FLOW:
            continue
        step_index = LOGISTICS_FLOW.index(step_code)
        for idx in range(step_index + 1, len(LOGISTICS_FLOW)):
            next_code = LOGISTICS_FLOW[idx]
            next_event_time = _resolve_event_milestone_time(
                event_code=next_code,
                shipped_at=order.shipped_at,
                delivered_due_at=delivered_due_at,
            )
            if current_tick < next_event_time:
                break
            _apply_logistics_transition(
                db,
                run_id=run_id,
                user_id=user_id,
                order=order,
                event_code=next_code,
                event_time=next_event_time,
            )
            changed = True
            step_code = next_code

    if changed:
        db.commit()


def _backfill_income_for_completed_orders(
    db: Session,
    *,
    run_id: int,
    user_id: int,
    current_tick: datetime,
    max_rows: int = 200,
) -> None:
    completed_orders = (
        db.query(ShopeeOrder)
        .filter(
            ShopeeOrder.run_id == run_id,
            ShopeeOrder.user_id == user_id,
            ShopeeOrder.type_bucket == "completed",
            ShopeeOrder.cancelled_at.is_(None),
        )
        .order_by(ShopeeOrder.id.desc())
        .limit(max_rows)
        .all()
    )
    changed = False
    for order in completed_orders:
        created = _credit_order_income_if_needed(
            db,
            run_id=run_id,
            user_id=user_id,
            order=order,
            credited_at=current_tick,
        )
        if created:
            changed = True
    if changed:
        db.commit()


def _get_owned_draft_or_404(db: Session, draft_id: int, run_id: int, user_id: int) -> ShopeeListingDraft:
    draft = (
        db.query(ShopeeListingDraft)
        .options(selectinload(ShopeeListingDraft.images), selectinload(ShopeeListingDraft.specs))
        .filter(
            ShopeeListingDraft.id == draft_id,
            ShopeeListingDraft.run_id == run_id,
            ShopeeListingDraft.user_id == user_id,
        )
        .first()
    )
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品草稿不存在")
    return draft


def _get_owned_listing_or_404(db: Session, listing_id: int, run_id: int, user_id: int) -> ShopeeListing:
    listing = (
        db.query(ShopeeListing)
        .options(
            selectinload(ShopeeListing.images),
            selectinload(ShopeeListing.specs),
            selectinload(ShopeeListing.variants),
            selectinload(ShopeeListing.wholesale_tiers),
        )
        .filter(
            ShopeeListing.id == listing_id,
            ShopeeListing.run_id == run_id,
            ShopeeListing.user_id == user_id,
        )
        .first()
    )
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")
    return listing


def _build_draft_response(draft: ShopeeListingDraft) -> ShopeeDraftDetailResponse:
    images_11 = [
        ShopeeDraftImageResponse(id=img.id, image_url=img.image_url, sort_order=img.sort_order, is_cover=img.is_cover)
        for img in sorted(
            [row for row in draft.images if row.image_ratio == "1:1"],
            key=lambda row: row.sort_order,
        )
    ]
    images_34 = [
        ShopeeDraftImageResponse(id=img.id, image_url=img.image_url, sort_order=img.sort_order, is_cover=img.is_cover)
        for img in sorted(
            [row for row in draft.images if row.image_ratio == "3:4"],
            key=lambda row: row.sort_order,
        )
    ]
    specs = [
        {"attr_key": row.attr_key, "attr_label": row.attr_label, "attr_value": row.attr_value}
        for row in sorted(draft.specs, key=lambda row: row.attr_key)
    ]
    return ShopeeDraftDetailResponse(
        id=draft.id,
        title=draft.title,
        category_id=draft.category_id,
        category=draft.category,
        gtin=draft.gtin,
        description=draft.description,
        video_url=draft.video_url,
        cover_url=draft.cover_url,
        image_count_11=len(images_11),
        image_count_34=len(images_34),
        images_11=images_11,
        images_34=images_34,
        specs=specs,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


def _build_listing_detail_response(listing: ShopeeListing) -> ShopeeListingDetailResponse:
    return ShopeeListingDetailResponse(
        id=listing.id,
        product_id=listing.product_id,
        title=listing.title,
        category_id=listing.category_id,
        category=listing.category,
        gtin=listing.gtin,
        description=listing.description,
        video_url=listing.video_url,
        cover_url=listing.cover_url,
        price=listing.price,
        stock_available=listing.stock_available,
        min_purchase_qty=listing.min_purchase_qty,
        max_purchase_qty=listing.max_purchase_qty,
        max_purchase_mode=listing.max_purchase_mode,
        max_purchase_period_start_date=listing.max_purchase_period_start_date,
        max_purchase_period_end_date=listing.max_purchase_period_end_date,
        max_purchase_period_qty=listing.max_purchase_period_qty,
        max_purchase_period_days=listing.max_purchase_period_days,
        max_purchase_period_model=listing.max_purchase_period_model,
        weight_kg=listing.weight_kg,
        parcel_length_cm=listing.parcel_length_cm,
        parcel_width_cm=listing.parcel_width_cm,
        parcel_height_cm=listing.parcel_height_cm,
        shipping_variation_dimension_enabled=listing.shipping_variation_dimension_enabled,
        shipping_standard_bulk=listing.shipping_standard_bulk,
        shipping_standard=listing.shipping_standard,
        shipping_express=listing.shipping_express,
        preorder_enabled=listing.preorder_enabled,
        insurance_enabled=listing.insurance_enabled,
        condition_label=listing.condition_label,
        schedule_publish_at=listing.schedule_publish_at,
        parent_sku=listing.parent_sku,
        variants=[
            ShopeeListingEditVariantResponse(
                id=row.id,
                variant_name=row.variant_name,
                option_value=row.option_value,
                option_note=row.option_note,
                price=row.price,
                stock=row.stock,
                sku=row.sku,
                gtin=row.gtin,
                item_without_gtin=row.item_without_gtin,
                weight_kg=row.weight_kg,
                parcel_length_cm=row.parcel_length_cm,
                parcel_width_cm=row.parcel_width_cm,
                parcel_height_cm=row.parcel_height_cm,
                image_url=row.image_url,
                sort_order=row.sort_order,
            )
            for row in sorted(listing.variants or [], key=lambda x: (x.sort_order, x.id))
        ],
        wholesale_tiers=[
            ShopeeListingEditWholesaleTierResponse(
                id=row.id,
                tier_no=row.tier_no,
                min_qty=row.min_qty,
                max_qty=row.max_qty,
                unit_price=row.unit_price,
            )
            for row in sorted(listing.wholesale_tiers or [], key=lambda x: (x.tier_no, x.id))
        ],
    )


def _validate_linkable_product_or_400(db: Session, *, run_id: int, product_id: int) -> None:
    linked_exists = (
        db.query(InventoryLot.id)
        .filter(
            InventoryLot.run_id == run_id,
            InventoryLot.product_id == product_id,
        )
        .first()
    )
    if not linked_exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择当前海外仓已入仓商品进行关联")


def _load_spec_templates(db: Session, category_id: int | None) -> list[ShopeeSpecTemplate]:
    if not category_id:
        return []
    return (
        db.query(ShopeeSpecTemplate)
        .options(selectinload(ShopeeSpecTemplate.options))
        .filter(
            ShopeeSpecTemplate.category_id == category_id,
            ShopeeSpecTemplate.is_active == True,
        )
        .order_by(ShopeeSpecTemplate.sort_order.asc(), ShopeeSpecTemplate.id.asc())
        .all()
    )


def _resolve_category_or_400(db: Session, category_id: int | None, category_path: str | None) -> tuple[int | None, str | None]:
    normalized_path = (category_path or "").strip() or None
    if category_id:
        row = (
            db.query(ShopeeCategoryNode)
            .filter(ShopeeCategoryNode.id == category_id, ShopeeCategoryNode.is_active == True)
            .first()
        )
        if not row:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="类目不存在或已下线")
        return row.id, row.path

    if normalized_path:
        row = (
            db.query(ShopeeCategoryNode)
            .filter(ShopeeCategoryNode.path == normalized_path, ShopeeCategoryNode.is_active == True)
            .first()
        )
        if not row:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="类目不存在或已下线")
        return row.id, row.path

    return None, None


def _parse_variants_payload(variations_payload: str | None) -> list[dict]:
    if not variations_payload or not variations_payload.strip():
        return []
    try:
        data = json.loads(variations_payload)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="变体数据格式错误") from exc
    if not isinstance(data, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="变体数据格式错误")
    rows: list[dict] = []

    def _to_positive_int(val):
        if val in (None, ""):
            return None
        try:
            num = int(float(val))
        except Exception:
            return None
        return num if num > 0 else None

    def _to_positive_float(val):
        if val in (None, ""):
            return None
        try:
            num = float(val)
        except Exception:
            return None
        return num if num > 0 else None

    def _to_positive_id(val):
        if val in (None, ""):
            return None
        try:
            num = int(val)
        except Exception:
            return None
        return num if num > 0 else None

    for idx, row in enumerate(data):
        if not isinstance(row, dict):
            continue
        option_value = str(row.get("option_value", "")).strip()
        if not option_value:
            continue
        rows.append(
            {
                "option_value": option_value,
                "option_note": str(row.get("option_note", "")).strip() or None,
                "source_variant_id": _to_positive_id(row.get("source_variant_id")),
                "price": max(int(row.get("price", 0) or 0), 0),
                "stock": max(int(row.get("stock", 0) or 0), 0),
                "sku": str(row.get("sku", "")).strip() or None,
                "gtin": str(row.get("gtin", "")).strip() or None,
                "image_url": str(row.get("image_url", "")).strip() or None,
                "item_without_gtin": bool(row.get("item_without_gtin", False)),
                "weight_kg": _to_positive_float(row.get("weight_kg")),
                "parcel_length_cm": _to_positive_int(row.get("parcel_length_cm")),
                "parcel_width_cm": _to_positive_int(row.get("parcel_width_cm")),
                "parcel_height_cm": _to_positive_int(row.get("parcel_height_cm")),
                "variant_name": str(row.get("variant_name", "")).strip() or None,
                "image_file_index": row.get("image_file_index", None),
                "sort_order": idx,
            }
        )
    return rows


def _parse_wholesale_tiers_payload(wholesale_tiers_payload: str | None) -> list[dict]:
    if not wholesale_tiers_payload or not wholesale_tiers_payload.strip():
        return []
    try:
        data = json.loads(wholesale_tiers_payload)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="批发价阶梯数据格式错误") from exc
    if not isinstance(data, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="批发价阶梯数据格式错误")
    rows: list[dict] = []
    for idx, row in enumerate(data):
        if not isinstance(row, dict):
            continue
        min_qty_raw = row.get("min_qty")
        max_qty_raw = row.get("max_qty")
        unit_price_raw = row.get("unit_price")

        def _to_positive_int(val):
            if val in (None, ""):
                return None
            try:
                num = int(val)
            except Exception:
                return None
            return num if num > 0 else None

        min_qty = _to_positive_int(min_qty_raw)
        max_qty = _to_positive_int(max_qty_raw)
        unit_price = _to_positive_int(unit_price_raw)
        if min_qty is None and max_qty is None and unit_price is None:
            continue
        rows.append(
            {
                "tier_no": idx + 1,
                "min_qty": min_qty,
                "max_qty": max_qty,
                "unit_price": unit_price,
            }
        )
    return rows


def _project_readonly_backorder_fulfillment(
    db: Session,
    *,
    run_id: int,
    user_id: int,
    orders: list[ShopeeOrder],
) -> dict[int, tuple[str, int, datetime | None]]:
    """Readonly projection for finished runs: do not write DB, only adjust response view."""
    if not orders:
        return {}
    listing_ids = {int(row.listing_id) for row in orders if int(row.listing_id or 0) > 0}
    if not listing_ids:
        return {}

    listing_rows = (
        db.query(ShopeeListing.id, ShopeeListing.product_id, ShopeeListing.stock_available)
        .filter(
            ShopeeListing.run_id == run_id,
            ShopeeListing.user_id == user_id,
            ShopeeListing.id.in_(listing_ids),
        )
        .all()
    )
    listing_product_map = {int(row[0]): int(row[1]) for row in listing_rows if row[1] is not None}
    listing_available_map = {int(row[0]): max(0, int(row[2] or 0)) for row in listing_rows}
    product_ids = sorted({pid for pid in listing_product_map.values() if pid > 0})

    available_by_product: dict[int, int] = {}
    if product_ids:
        available_rows = (
            db.query(InventoryLot.product_id, func.coalesce(func.sum(InventoryLot.quantity_available), 0))
            .filter(
                InventoryLot.run_id == run_id,
                InventoryLot.product_id.in_(product_ids),
            )
            .group_by(InventoryLot.product_id)
            .all()
        )
        available_by_product = {int(pid): int(qty or 0) for pid, qty in available_rows}

    variant_rows = (
        db.query(ShopeeListingVariant.id, ShopeeListingVariant.listing_id, ShopeeListingVariant.stock)
        .filter(
            ShopeeListingVariant.listing_id.in_(listing_ids),
        )
        .all()
    )
    variant_available_map = {int(row[0]): max(0, int(row[2] or 0)) for row in variant_rows}
    variant_listing_map = {int(row[0]): int(row[1]) for row in variant_rows}

    projected: dict[int, tuple[str, int, datetime | None]] = {}

    for row in orders:
        base_status = (row.stock_fulfillment_status or "").strip()
        base_backorder = max(0, int(row.backorder_qty or 0))
        if row.type_bucket != "toship" or base_status != "backorder" or base_backorder <= 0:
            continue
        listing_id = int(row.listing_id or 0)
        product_id = listing_product_map.get(listing_id)
        can_fill = 0

        if product_id:
            can_fill = min(base_backorder, max(0, int(available_by_product.get(product_id, 0))))
            if can_fill > 0:
                available_by_product[product_id] = max(0, int(available_by_product.get(product_id, 0)) - can_fill)
        else:
            variant_id = int(row.variant_id or 0)
            if variant_id > 0 and variant_id in variant_available_map:
                can_fill = min(base_backorder, max(0, int(variant_available_map.get(variant_id, 0))))
                if can_fill > 0:
                    variant_available_map[variant_id] = max(0, int(variant_available_map.get(variant_id, 0)) - can_fill)
                    v_listing_id = variant_listing_map.get(variant_id)
                    if v_listing_id is not None:
                        listing_available_map[v_listing_id] = max(
                            0, int(listing_available_map.get(v_listing_id, 0)) - can_fill
                        )
            if can_fill <= 0 and listing_id > 0:
                can_fill = min(base_backorder, max(0, int(listing_available_map.get(listing_id, 0))))
                if can_fill > 0:
                    listing_available_map[listing_id] = max(0, int(listing_available_map.get(listing_id, 0)) - can_fill)

        if can_fill <= 0:
            continue
        remaining = base_backorder - can_fill
        if remaining <= 0:
            projected[int(row.id)] = ("restocked", 0, None)
        else:
            projected[int(row.id)] = ("backorder", remaining, row.must_restock_before_at)
    return projected


@router.get("/runs/{run_id}/orders", response_model=ShopeeOrdersListResponse)
def list_shopee_orders(
    run_id: int,
    type: str = Query(default="all"),
    source: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    order: str = Query(default="desc"),
    order_type: str = Query(default="all"),
    order_status: str = Query(default="all"),
    priority: str = Query(default="all"),
    keyword: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeOrdersListResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_orders_list_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    is_finished = _persist_run_finished_if_reached(db, run)
    if not is_finished:
        _auto_simulate_orders_by_game_hour(db, run=run, user_id=user_id, max_ticks_per_request=10)
        _invalidate_shopee_discount_cache(run_id=run.id, user_id=user_id)
        _invalidate_shopee_flash_sale_cache(run_id=run.id, user_id=user_id)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    if not _persist_run_finished_if_reached(db, run):
        _auto_cancel_overdue_orders_by_tick(db, run_id=run.id, user_id=user_id, current_tick=current_tick)
        _auto_progress_shipping_orders_by_tick(db, run_id=run.id, user_id=user_id, current_tick=current_tick)
        _backfill_income_for_completed_orders(db, run_id=run.id, user_id=user_id, current_tick=current_tick)
        service_rebalance_backorders_from_current_inventory(db, run_id=run.id, user_id=user_id)
        db.commit()
        _invalidate_shopee_orders_cache_for_user(run_id=run.id, user_id=user_id)
    cached_payload = _get_shopee_orders_cache_payload(
        run_id=run.id,
        user_id=user_id,
        type_value=type,
        source=source,
        sort_by=sort_by,
        order=order,
        order_type=order_type,
        order_status=order_status,
        priority=priority,
        keyword=keyword,
        channel=channel,
        page=page,
        page_size=page_size,
    )
    if cached_payload:
        return ShopeeOrdersListResponse.model_validate(cached_payload)

    base_query = db.query(ShopeeOrder).filter(ShopeeOrder.run_id == run.id, ShopeeOrder.user_id == user_id)
    counts = ShopeeOrderTabCounts(
        all=base_query.count(),
        unpaid=base_query.filter(ShopeeOrder.type_bucket == "unpaid").count(),
        toship=base_query.filter(ShopeeOrder.type_bucket == "toship").count(),
        shipping=base_query.filter(ShopeeOrder.type_bucket == "shipping").count(),
        completed=base_query.filter(ShopeeOrder.type_bucket == "completed").count(),
        return_refund_cancel=base_query.filter(ShopeeOrder.type_bucket == "cancelled").count(),
    )

    query = db.query(ShopeeOrder).options(selectinload(ShopeeOrder.items)).filter(
        ShopeeOrder.run_id == run.id, ShopeeOrder.user_id == user_id
    )
    query = _apply_filters(
        query,
        type_value=type,
        source=source,
        order_type=order_type,
        order_status=order_status,
        priority=priority,
        keyword=keyword,
        channel=channel,
    )

    sort_order = desc if order.strip().lower() == "desc" else asc
    if sort_by == "ship_by_date_asc":
        query = query.order_by(asc(ShopeeOrder.ship_by_date), ShopeeOrder.id.desc())
    elif sort_by == "ship_by_date_desc":
        query = query.order_by(desc(ShopeeOrder.ship_by_date), ShopeeOrder.id.desc())
    else:
        query = query.order_by(sort_order(ShopeeOrder.created_at), ShopeeOrder.id.desc())

    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()

    # 预加载命中折扣的比例：(campaign_id, variant_id) -> discount_percent
    campaign_ids = [r.marketing_campaign_id for r in rows if r.marketing_campaign_id]
    discount_percent_map: dict[tuple[int, int | None], float] = {}
    if campaign_ids:
        discount_items = (
            db.query(ShopeeDiscountCampaignItem)
            .filter(ShopeeDiscountCampaignItem.campaign_id.in_(campaign_ids))
            .all()
        )
        for di in discount_items:
            pct = float(di.discount_value or 0) if (di.discount_type or "") == "percent" else None
            if pct is not None:
                discount_percent_map[(int(di.campaign_id), int(di.variant_id) if di.variant_id else None)] = pct

    readonly_backorder_projection: dict[int, tuple[str, int, datetime | None]] = {}
    if (run.status or "").strip() == "finished":
        readonly_backorder_projection = _project_readonly_backorder_fulfillment(
            db,
            run_id=run.id,
            user_id=user_id,
            orders=rows,
        )
    recent_window_start = datetime.now() - timedelta(hours=1)
    simulated_recent_1h = (
        db.query(func.coalesce(func.sum(ShopeeOrderGenerationLog.generated_order_count), 0))
        .filter(
            ShopeeOrderGenerationLog.run_id == run.id,
            ShopeeOrderGenerationLog.user_id == user_id,
            ShopeeOrderGenerationLog.created_at >= recent_window_start,
        )
        .scalar()
        or 0
    )
    # Avoid full-row ORDER BY on a potentially large log table.
    # We only need the latest timestamp, so use aggregate MAX(created_at).
    last_simulated_at = (
        db.query(func.max(ShopeeOrderGenerationLog.created_at))
        .filter(
            ShopeeOrderGenerationLog.run_id == run.id,
            ShopeeOrderGenerationLog.user_id == user_id,
        )
        .scalar()
    )

    response = ShopeeOrdersListResponse(
        counts=counts,
        page=page,
        page_size=page_size,
        total=total,
        simulated_recent_1h=int(simulated_recent_1h),
        last_simulated_at=last_simulated_at,
        orders=[
            ShopeeOrderResponse(
                **{
                    **{
                        "id": row.id,
                        "order_no": row.order_no,
                        "buyer_name": row.buyer_name,
                        "buyer_payment": row.buyer_payment,
                        "order_type": row.order_type,
                        "type_bucket": row.type_bucket,
                        "process_status": row.process_status,
                        "shipping_priority": row.shipping_priority,
                        "shipping_channel": row.shipping_channel,
                        "destination": row.destination,
                        "countdown_text": row.countdown_text,
                        "action_text": row.action_text,
                        "ship_by_date": row.ship_by_date,
                        "tracking_no": row.tracking_no,
                        "waybill_no": row.waybill_no,
                        "listing_id": row.listing_id,
                        "variant_id": row.variant_id,
                        "stock_fulfillment_status": row.stock_fulfillment_status,
                        "backorder_qty": int(row.backorder_qty or 0),
                        "must_restock_before_at": row.must_restock_before_at,
                        "ship_by_at": row.ship_by_at,
                        "shipped_at": row.shipped_at,
                        "delivered_at": row.delivered_at,
                        "cancelled_at": row.cancelled_at,
                        "cancel_reason": row.cancel_reason,
                        "cancel_source": row.cancel_source,
                        "eta_start_at": row.eta_start_at,
                        "eta_end_at": row.eta_end_at,
                        "distance_km": row.distance_km,
                        "created_at": row.created_at,
                        "marketing_campaign_type": row.marketing_campaign_type,
                        "marketing_campaign_id": row.marketing_campaign_id,
                        "marketing_campaign_name_snapshot": row.marketing_campaign_name_snapshot,
                        "order_subtotal_amount": float(row.order_subtotal_amount or 0),
                        "voucher_campaign_type": row.voucher_campaign_type,
                        "voucher_campaign_id": row.voucher_campaign_id,
                        "voucher_name_snapshot": row.voucher_name_snapshot,
                        "voucher_code_snapshot": row.voucher_code_snapshot,
                        "voucher_discount_amount": float(row.voucher_discount_amount or 0),
                        "shipping_promotion_campaign_id": row.shipping_promotion_campaign_id,
                        "shipping_promotion_name_snapshot": row.shipping_promotion_name_snapshot,
                        "shipping_promotion_tier_index": row.shipping_promotion_tier_index,
                        "shipping_fee_before_promotion": float(row.shipping_fee_before_promotion or 0),
                        "shipping_fee_after_promotion": float(row.shipping_fee_after_promotion or 0),
                        "shipping_promotion_discount_amount": float(row.shipping_promotion_discount_amount or 0),
                        "discount_percent": (
                            discount_percent_map.get((int(row.marketing_campaign_id), int(row.variant_id) if row.variant_id else None))
                            or discount_percent_map.get((int(row.marketing_campaign_id), None))
                        ) if row.marketing_campaign_id else None,
                        "items": [
                            ShopeeOrderItemResponse(
                                listing_id=item.listing_id,
                                variant_id=item.variant_id,
                                product_id=item.product_id,
                                product_name=item.product_name,
                                variant_name=item.variant_name,
                                quantity=item.quantity,
                                unit_price=item.unit_price,
                                image_url=item.image_url,
                                stock_fulfillment_status=item.stock_fulfillment_status,
                                backorder_qty=int(item.backorder_qty or 0),
                                marketing_campaign_type=item.marketing_campaign_type,
                                marketing_campaign_id=item.marketing_campaign_id,
                                marketing_campaign_name_snapshot=item.marketing_campaign_name_snapshot,
                                line_role=item.line_role or "main",
                                original_unit_price=float(item.original_unit_price or item.unit_price or 0),
                                discounted_unit_price=float(item.discounted_unit_price or item.unit_price or 0),
                            )
                            for item in row.items
                        ],
                    },
                    **(
                        {
                            "stock_fulfillment_status": readonly_backorder_projection[int(row.id)][0],
                            "backorder_qty": int(readonly_backorder_projection[int(row.id)][1]),
                            "must_restock_before_at": readonly_backorder_projection[int(row.id)][2],
                        }
                        if int(row.id) in readonly_backorder_projection
                        else {}
                    ),
                    **_calc_order_shipping_metrics(row, current_tick),
                }
            )
            for row in rows
        ],
    )
    _set_shopee_orders_cache_payload(
        run_id=run.id,
        user_id=user_id,
        type_value=type,
        source=source,
        sort_by=sort_by,
        order=order,
        order_type=order_type,
        order_status=order_status,
        priority=priority,
        keyword=keyword,
        channel=channel,
        page=page,
        page_size=page_size,
        payload=response.model_dump(mode="json"),
    )
    return response


@router.get("/runs/{run_id}/orders/{order_id}", response_model=ShopeeOrderResponse)
def get_shopee_order_detail(
    run_id: int,
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeOrderResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    if not _persist_run_finished_if_reached(db, run):
        _auto_cancel_overdue_orders_by_tick(db, run_id=run.id, user_id=user_id, current_tick=current_tick)
        _auto_progress_shipping_orders_by_tick(db, run_id=run.id, user_id=user_id, current_tick=current_tick)
        _backfill_income_for_completed_orders(db, run_id=run.id, user_id=user_id, current_tick=current_tick)
    row = (
        db.query(ShopeeOrder)
        .options(selectinload(ShopeeOrder.items))
        .filter(
            ShopeeOrder.id == order_id,
            ShopeeOrder.run_id == run.id,
            ShopeeOrder.user_id == user_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    readonly_backorder_projection: dict[int, tuple[str, int, datetime | None]] = {}
    if (run.status or "").strip() == "finished":
        readonly_backorder_projection = _project_readonly_backorder_fulfillment(
            db,
            run_id=run.id,
            user_id=user_id,
            orders=[row],
        )
    discount_percent: float | None = None
    if row.marketing_campaign_id:
        discount_item = (
            db.query(ShopeeDiscountCampaignItem)
            .filter(
                ShopeeDiscountCampaignItem.campaign_id == row.marketing_campaign_id,
                ShopeeDiscountCampaignItem.variant_id == row.variant_id,
            )
            .first()
            or db.query(ShopeeDiscountCampaignItem)
            .filter(
                ShopeeDiscountCampaignItem.campaign_id == row.marketing_campaign_id,
                ShopeeDiscountCampaignItem.variant_id.is_(None),
            )
            .first()
        )
        if discount_item and (discount_item.discount_type or "") == "percent":
            discount_percent = float(discount_item.discount_value or 0)
    return ShopeeOrderResponse(
        **{
            **{
                "id": row.id,
                "order_no": row.order_no,
                "buyer_name": row.buyer_name,
                "buyer_payment": row.buyer_payment,
                "order_type": row.order_type,
                "type_bucket": row.type_bucket,
                "process_status": row.process_status,
                "shipping_priority": row.shipping_priority,
                "shipping_channel": row.shipping_channel,
                "destination": row.destination,
                "countdown_text": row.countdown_text,
                "action_text": row.action_text,
                "ship_by_date": row.ship_by_date,
                "tracking_no": row.tracking_no,
                "waybill_no": row.waybill_no,
                "listing_id": row.listing_id,
                "variant_id": row.variant_id,
                "stock_fulfillment_status": row.stock_fulfillment_status,
                "backorder_qty": int(row.backorder_qty or 0),
                "must_restock_before_at": row.must_restock_before_at,
                "ship_by_at": row.ship_by_at,
                "shipped_at": row.shipped_at,
                "delivered_at": row.delivered_at,
                "cancelled_at": row.cancelled_at,
                "cancel_reason": row.cancel_reason,
                "cancel_source": row.cancel_source,
                "eta_start_at": row.eta_start_at,
                "eta_end_at": row.eta_end_at,
                "distance_km": row.distance_km,
                "created_at": row.created_at,
                "marketing_campaign_type": row.marketing_campaign_type,
                "marketing_campaign_id": row.marketing_campaign_id,
                "marketing_campaign_name_snapshot": row.marketing_campaign_name_snapshot,
                "order_subtotal_amount": float(row.order_subtotal_amount or 0),
                "voucher_campaign_type": row.voucher_campaign_type,
                "voucher_campaign_id": row.voucher_campaign_id,
                "voucher_name_snapshot": row.voucher_name_snapshot,
                "voucher_code_snapshot": row.voucher_code_snapshot,
                "voucher_discount_amount": float(row.voucher_discount_amount or 0),
                "shipping_promotion_campaign_id": row.shipping_promotion_campaign_id,
                "shipping_promotion_name_snapshot": row.shipping_promotion_name_snapshot,
                "shipping_promotion_tier_index": row.shipping_promotion_tier_index,
                "shipping_fee_before_promotion": float(row.shipping_fee_before_promotion or 0),
                "shipping_fee_after_promotion": float(row.shipping_fee_after_promotion or 0),
                "shipping_promotion_discount_amount": float(row.shipping_promotion_discount_amount or 0),
                "discount_percent": discount_percent,
                "items": [
                    ShopeeOrderItemResponse(
                        listing_id=item.listing_id,
                        variant_id=item.variant_id,
                        product_id=item.product_id,
                        product_name=item.product_name,
                        variant_name=item.variant_name,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                        image_url=item.image_url,
                        stock_fulfillment_status=item.stock_fulfillment_status,
                        backorder_qty=int(item.backorder_qty or 0),
                    )
                    for item in row.items
                ],
            },
            **(
                {
                    "stock_fulfillment_status": readonly_backorder_projection[int(row.id)][0],
                    "backorder_qty": int(readonly_backorder_projection[int(row.id)][1]),
                    "must_restock_before_at": readonly_backorder_projection[int(row.id)][2],
                }
                if int(row.id) in readonly_backorder_projection
                else {}
            ),
            **_calc_order_shipping_metrics(row, current_tick),
        }
    )


@router.post("/runs/{run_id}/orders/{order_id}/ship", response_model=ShopeeShipOrderResponse)
def ship_order(
    run_id: int,
    order_id: int,
    payload: ShopeeShipOrderRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeShipOrderResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    _ensure_run_writable_or_400(db, run, tick_time=current_tick)
    _auto_cancel_overdue_orders_by_tick(db, run_id=run.id, user_id=user_id, current_tick=current_tick)
    order = _get_owned_order_or_404(db, run.id, user_id, order_id)

    if order.type_bucket != "toship":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅待出货订单可安排发货")
    if (order.stock_fulfillment_status or "").strip() == "backorder" and int(order.backorder_qty or 0) > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="订单仍待补货，暂不可发货",
        )

    allowed_channels = {"标准快递", "标准大件", "快捷快递"}
    shipping_channel = (payload.shipping_channel or order.shipping_channel or "标准快递").strip()
    if shipping_channel not in allowed_channels:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="物流渠道不合法")

    ship_lines: list[dict[str, int | None]] = []
    for item in list(order.items or []):
        item_qty = max(0, int(item.quantity or 0))
        if item_qty <= 0:
            continue
        product_id = int(item.product_id or 0)
        listing_id = int(item.listing_id or 0) or int(order.listing_id or 0) or None
        variant_id = int(item.variant_id or 0) or int(order.variant_id or 0) or None
        if product_id <= 0 and listing_id:
            listing = (
                db.query(ShopeeListing)
                .filter(
                    ShopeeListing.run_id == run.id,
                    ShopeeListing.user_id == user_id,
                    ShopeeListing.id == listing_id,
                )
                .first()
            )
            product_id = int(listing.product_id or 0) if listing and listing.product_id is not None else 0
        if product_id <= 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="订单缺少库存商品映射，暂不可发货")
        consumed_qty = consume_reserved_inventory_lots(
            db,
            run_id=run.id,
            product_id=product_id,
            qty=item_qty,
        )
        shortfall = item_qty - consumed_qty
        if shortfall > 0:
            consumed_qty += consume_available_inventory_lots(
                db,
                run_id=run.id,
                product_id=product_id,
                qty=shortfall,
            )
        if consumed_qty < item_qty:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="库存不足，订单暂不可发货")
        ship_lines.append(
            {
                "product_id": product_id,
                "listing_id": listing_id,
                "variant_id": variant_id,
                "consumed_qty": consumed_qty,
            }
        )

    now = current_tick
    warehouse_latlng = _resolve_warehouse_latlng(db, run)
    buyer_latlng = _resolve_buyer_latlng(db, order.buyer_name, order.destination)
    distance_km = haversine_km(warehouse_latlng, buyer_latlng)
    forwarder_key, _forwarder_label = _resolve_forwarder_for_order(
        db,
        run_id=run.id,
        user_id=user_id,
        shipping_channel=shipping_channel,
    )
    transit_days, _min_days, max_days = _calc_transit_days_by_line_and_distance(
        forwarder_key=forwarder_key,
        distance_km=distance_km,
    )
    eta_start_at = now + timedelta(seconds=transit_days * REAL_SECONDS_PER_GAME_DAY)
    eta_end_at = now + timedelta(seconds=min(transit_days + 1, max_days) * REAL_SECONDS_PER_GAME_DAY)

    order.tracking_no = gen_tracking_no(now)
    order.waybill_no = gen_waybill_no(now)
    order.shipped_at = now
    order.ship_by_at = order.ship_by_at or order.ship_by_date or (now + timedelta(days=1))
    order.distance_km = distance_km
    order.eta_start_at = eta_start_at
    order.eta_end_at = eta_end_at
    order.shipping_channel = shipping_channel
    order.delivery_line_key = forwarder_key
    order.delivery_line_label = FORWARDER_KEY_TO_LABEL.get(forwarder_key, _forwarder_label or "标准线（马来）")
    order.type_bucket = "shipping"
    order.process_status = "processed"
    order.countdown_text = "物流运输中"

    for line in ship_lines:
        consumed_qty = int(line["consumed_qty"] or 0)
        if consumed_qty <= 0:
            continue
        # 发货出库：释放预占，转为已出库消耗。
        db.add(
            InventoryStockMovement(
                run_id=run.id,
                user_id=user_id,
                product_id=int(line["product_id"]) if line["product_id"] is not None else None,
                listing_id=int(line["listing_id"]) if line["listing_id"] is not None else None,
                variant_id=int(line["variant_id"]) if line["variant_id"] is not None else None,
                biz_order_id=int(order.id),
                movement_type="order_ship",
                qty_delta_on_hand=0,
                qty_delta_reserved=-consumed_qty,
                qty_delta_backorder=0,
                biz_ref=order.order_no,
                remark="订单发货出库（释放预占）",
            )
        )

    _apply_logistics_transition(
        db,
        run_id=run.id,
        user_id=user_id,
        order=order,
        event_code="label_created",
        event_time=now,
    )
    db.commit()
    db.refresh(order)
    _invalidate_shopee_orders_cache_for_user(run_id=run.id, user_id=user_id)

    return ShopeeShipOrderResponse(
        order_id=order.id,
        tracking_no=order.tracking_no or "",
        waybill_no=order.waybill_no or "",
        shipping_channel=order.shipping_channel,
        distance_km=float(order.distance_km or 0),
        delivery_line_label=order.delivery_line_label or FORWARDER_KEY_TO_LABEL.get(forwarder_key, "标准线（马来）"),
        promised_transit_days_text=f"{_min_days}~{max_days}天",
        transit_days_expected=transit_days,
        eta_start_at=order.eta_start_at or now,
        eta_end_at=order.eta_end_at or now,
        process_status=order.process_status,
        type_bucket=order.type_bucket,
    )


@router.post("/runs/{run_id}/orders/{order_id}/cancel", response_model=ShopeeCancelOrderResponse)
def cancel_order(
    run_id: int,
    order_id: int,
    payload: ShopeeCancelOrderRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeCancelOrderResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    _ensure_run_writable_or_400(db, run)
    order = _get_owned_order_or_404(db, run.id, user_id, order_id)
    if order.type_bucket != "toship":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅待出货订单可取消")

    now = _resolve_game_tick(db, run.id, user_id)
    _cancel_order(
        db,
        run_id=run.id,
        user_id=user_id,
        order=order,
        cancel_time=now,
        reason=(payload.reason or "seller_not_ship_in_time").strip() or "seller_not_ship_in_time",
        source="manual_debug",
    )
    db.commit()
    db.refresh(order)
    _invalidate_shopee_orders_cache_for_user(run_id=run.id, user_id=user_id)
    return ShopeeCancelOrderResponse(
        order_id=order.id,
        type_bucket=order.type_bucket,
        process_status=order.process_status,
        cancelled_at=order.cancelled_at,
        cancel_reason=order.cancel_reason,
        cancel_source=order.cancel_source,
    )


@router.get("/runs/{run_id}/orders/{order_id}/logistics", response_model=ShopeeOrderLogisticsResponse)
def get_order_logistics(
    run_id: int,
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeOrderLogisticsResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    if not _persist_run_finished_if_reached(db, run):
        _auto_cancel_overdue_orders_by_tick(db, run_id=run.id, user_id=user_id, current_tick=current_tick)
        _auto_progress_shipping_orders_by_tick(db, run_id=run.id, user_id=user_id, current_tick=current_tick)
    order = _get_owned_order_or_404(db, run.id, user_id, order_id)
    events = (
        db.query(ShopeeOrderLogisticsEvent)
        .filter(
            ShopeeOrderLogisticsEvent.run_id == run.id,
            ShopeeOrderLogisticsEvent.user_id == user_id,
            ShopeeOrderLogisticsEvent.order_id == order.id,
        )
        .order_by(ShopeeOrderLogisticsEvent.event_time.desc(), ShopeeOrderLogisticsEvent.id.desc())
        .all()
    )
    return ShopeeOrderLogisticsResponse(
        order_id=order.id,
        order_no=order.order_no,
        tracking_no=order.tracking_no,
        waybill_no=order.waybill_no,
        shipping_channel=order.shipping_channel,
        destination=order.destination,
        eta_start_at=order.eta_start_at,
        eta_end_at=order.eta_end_at,
        **_calc_order_shipping_metrics(order, current_tick),
        events=[
            ShopeeLogisticsEventResponse(
                event_code=e.event_code,
                event_title=e.event_title,
                event_desc=e.event_desc,
                event_time=e.event_time,
            )
            for e in events
        ],
    )


@router.post("/runs/{run_id}/orders/{order_id}/logistics/progress", response_model=ShopeeProgressLogisticsResponse)
def progress_order_logistics(
    run_id: int,
    order_id: int,
    payload: ShopeeProgressLogisticsRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeProgressLogisticsResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    now = _resolve_game_tick(db, run.id, user_id)
    _ensure_run_writable_or_400(db, run, tick_time=now)
    order = _get_owned_order_or_404(db, run.id, user_id, order_id)
    if order.type_bucket == "cancelled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="订单已取消，无法推进物流")

    latest_event = (
        db.query(ShopeeOrderLogisticsEvent)
        .filter(
            ShopeeOrderLogisticsEvent.run_id == run.id,
            ShopeeOrderLogisticsEvent.user_id == user_id,
            ShopeeOrderLogisticsEvent.order_id == order.id,
        )
        .order_by(ShopeeOrderLogisticsEvent.event_time.desc(), ShopeeOrderLogisticsEvent.id.desc())
        .first()
    )

    expected_next = _next_event_code(latest_event.event_code if latest_event else None)
    target_code = payload.event_code or expected_next
    if target_code != expected_next:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"仅允许推进到下一节点: {expected_next}")

    _apply_logistics_transition(
        db,
        run_id=run.id,
        user_id=user_id,
        order=order,
        event_code=target_code,
        event_time=now,
    )

    db.commit()
    db.refresh(order)
    _invalidate_shopee_orders_cache_for_user(run_id=run.id, user_id=user_id)
    return ShopeeProgressLogisticsResponse(
        order_id=order.id,
        order_no=order.order_no,
        type_bucket=order.type_bucket,
        process_status=order.process_status,
        current_event_code=target_code,
        delivered_at=order.delivered_at,
    )


@router.get("/runs/{run_id}/orders/{order_id}/settlement", response_model=ShopeeOrderSettlementResponse)
def get_order_settlement(
    run_id: int,
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeOrderSettlementResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    _ = _get_owned_order_or_404(db, run.id, user_id, order_id)
    settlement = (
        db.query(ShopeeOrderSettlement)
        .filter(
            ShopeeOrderSettlement.run_id == run.id,
            ShopeeOrderSettlement.user_id == user_id,
            ShopeeOrderSettlement.order_id == order_id,
        )
        .first()
    )
    if not settlement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单尚未生成结算")
    return ShopeeOrderSettlementResponse(
        order_id=order_id,
        settlement_status=settlement.settlement_status,
        buyer_payment=float(settlement.buyer_payment),
        platform_commission_amount=float(settlement.platform_commission_amount),
        payment_fee_amount=float(settlement.payment_fee_amount),
        shipping_cost_amount=float(settlement.shipping_cost_amount),
        shipping_subsidy_amount=float(settlement.shipping_subsidy_amount),
        shipping_promotion_discount_amount=float(settlement.shipping_promotion_discount_amount or 0),
        net_income_amount=float(settlement.net_income_amount),
        settled_at=settlement.settled_at,
    )


@router.get("/runs/{run_id}/finance/overview", response_model=ShopeeFinanceOverviewResponse)
def get_shopee_finance_overview(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeFinanceOverviewResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    if not _persist_run_finished_if_reached(db, run):
        _backfill_income_for_completed_orders(db, run_id=run.id, user_id=user_id, current_tick=current_tick)

    wallet_balance = _calc_wallet_balance(db, run_id=run.id, user_id=user_id)
    total_income = (
        db.query(func.coalesce(func.sum(ShopeeFinanceLedgerEntry.amount), 0.0))
        .filter(
            ShopeeFinanceLedgerEntry.run_id == run.id,
            ShopeeFinanceLedgerEntry.user_id == user_id,
            ShopeeFinanceLedgerEntry.status == "completed",
            ShopeeFinanceLedgerEntry.direction == "in",
            ShopeeFinanceLedgerEntry.entry_type == "income_from_order",
        )
        .scalar()
        or 0.0
    )
    day_start = _resolve_game_day_start(run, current_tick)
    today_income = (
        db.query(func.coalesce(func.sum(ShopeeFinanceLedgerEntry.amount), 0.0))
        .filter(
            ShopeeFinanceLedgerEntry.run_id == run.id,
            ShopeeFinanceLedgerEntry.user_id == user_id,
            ShopeeFinanceLedgerEntry.status == "completed",
            ShopeeFinanceLedgerEntry.direction == "in",
            ShopeeFinanceLedgerEntry.entry_type == "income_from_order",
            ShopeeFinanceLedgerEntry.credited_at >= day_start,
        )
        .scalar()
        or 0.0
    )
    week_start = _resolve_game_week_start(current_tick)
    week_income = (
        db.query(func.coalesce(func.sum(ShopeeFinanceLedgerEntry.amount), 0.0))
        .filter(
            ShopeeFinanceLedgerEntry.run_id == run.id,
            ShopeeFinanceLedgerEntry.user_id == user_id,
            ShopeeFinanceLedgerEntry.status == "completed",
            ShopeeFinanceLedgerEntry.direction == "in",
            ShopeeFinanceLedgerEntry.entry_type == "income_from_order",
            ShopeeFinanceLedgerEntry.credited_at >= week_start,
        )
        .scalar()
        or 0.0
    )
    month_start = _resolve_game_month_start(current_tick)
    month_income = (
        db.query(func.coalesce(func.sum(ShopeeFinanceLedgerEntry.amount), 0.0))
        .filter(
            ShopeeFinanceLedgerEntry.run_id == run.id,
            ShopeeFinanceLedgerEntry.user_id == user_id,
            ShopeeFinanceLedgerEntry.status == "completed",
            ShopeeFinanceLedgerEntry.direction == "in",
            ShopeeFinanceLedgerEntry.entry_type == "income_from_order",
            ShopeeFinanceLedgerEntry.credited_at >= month_start,
        )
        .scalar()
        or 0.0
    )
    transaction_count = (
        db.query(func.count(ShopeeFinanceLedgerEntry.id))
        .filter(
            ShopeeFinanceLedgerEntry.run_id == run.id,
            ShopeeFinanceLedgerEntry.user_id == user_id,
        )
        .scalar()
        or 0
    )
    return ShopeeFinanceOverviewResponse(
        wallet_balance=round(float(wallet_balance), 2),
        total_income=round(float(total_income), 2),
        today_income=round(float(today_income), 2),
        week_income=round(float(week_income), 2),
        month_income=round(float(month_income), 2),
        transaction_count=int(transaction_count),
        current_tick=current_tick,
    )


@router.get("/runs/{run_id}/finance/transactions", response_model=ShopeeFinanceTransactionsResponse)
def list_shopee_finance_transactions(
    run_id: int,
    direction: str = Query(default="all"),
    entry_type: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeFinanceTransactionsResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    if not _persist_run_finished_if_reached(db, run):
        _backfill_income_for_completed_orders(db, run_id=run.id, user_id=user_id, current_tick=current_tick)

    query = (
        db.query(ShopeeFinanceLedgerEntry)
        .options(selectinload(ShopeeFinanceLedgerEntry.order))
        .filter(
            ShopeeFinanceLedgerEntry.run_id == run.id,
            ShopeeFinanceLedgerEntry.user_id == user_id,
        )
    )

    normalized_direction = (direction or "all").strip().lower()
    if normalized_direction in {"in", "out"}:
        query = query.filter(ShopeeFinanceLedgerEntry.direction == normalized_direction)
    if entry_type and entry_type.strip():
        query = query.filter(ShopeeFinanceLedgerEntry.entry_type == entry_type.strip())
    if keyword and keyword.strip():
        kw = keyword.strip()
        query = query.join(ShopeeOrder, ShopeeOrder.id == ShopeeFinanceLedgerEntry.order_id, isouter=True).filter(
            ShopeeOrder.order_no.ilike(f"%{kw}%")
        )

    query = query.order_by(ShopeeFinanceLedgerEntry.credited_at.desc(), ShopeeFinanceLedgerEntry.id.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()

    return ShopeeFinanceTransactionsResponse(
        page=page,
        page_size=page_size,
        total=total,
        rows=[
            ShopeeFinanceTransactionRowResponse(
                id=row.id,
                order_id=row.order_id,
                order_no=row.order.order_no if row.order else None,
                buyer_name=row.order.buyer_name if row.order else None,
                entry_type=row.entry_type,
                direction=row.direction,
                amount=float(row.amount or 0),
                balance_after=float(row.balance_after or 0),
                status=row.status,
                remark=row.remark,
                credited_at=row.credited_at,
            )
            for row in rows
        ],
    )


@router.get("/runs/{run_id}/finance/income", response_model=ShopeeFinanceIncomeListResponse)
def list_shopee_finance_income(
    run_id: int,
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeFinanceIncomeListResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    if not _persist_run_finished_if_reached(db, run):
        _backfill_income_for_completed_orders(db, run_id=run.id, user_id=user_id, current_tick=current_tick)

    query = (
        db.query(ShopeeFinanceLedgerEntry)
        .options(selectinload(ShopeeFinanceLedgerEntry.order).selectinload(ShopeeOrder.items))
        .filter(
            ShopeeFinanceLedgerEntry.run_id == run.id,
            ShopeeFinanceLedgerEntry.user_id == user_id,
            ShopeeFinanceLedgerEntry.entry_type == "income_from_order",
            ShopeeFinanceLedgerEntry.direction == "in",
        )
    )
    if keyword and keyword.strip():
        kw = keyword.strip()
        query = query.join(ShopeeOrder, ShopeeOrder.id == ShopeeFinanceLedgerEntry.order_id).filter(
            ShopeeOrder.order_no.ilike(f"%{kw}%")
        )

    query = query.order_by(ShopeeFinanceLedgerEntry.credited_at.desc(), ShopeeFinanceLedgerEntry.id.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()

    def _first_item(order: ShopeeOrder | None) -> ShopeeOrderItem | None:
        if not order or not order.items:
            return None
        return order.items[0]

    return ShopeeFinanceIncomeListResponse(
        page=page,
        page_size=page_size,
        total=total,
        rows=[
            ShopeeFinanceIncomeRowResponse(
                id=row.id,
                order_id=int(row.order_id or 0),
                order_no=row.order.order_no if row.order else "-",
                buyer_name=row.order.buyer_name if row.order else "-",
                product_name=(item.product_name if item else None),
                variant_name=(item.variant_name if item else None),
                image_url=(item.image_url if item else None),
                amount=float(row.amount or 0),
                status=row.status,
                credited_at=row.credited_at,
            )
            for row in rows
            for item in [_first_item(row.order)]
            if row.order_id
        ],
    )


@router.get("/runs/{run_id}/finance/bank-accounts", response_model=ShopeeBankAccountsListResponse)
def list_shopee_bank_accounts(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeBankAccountsListResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    rows = (
        db.query(ShopeeBankAccount)
        .filter(
            ShopeeBankAccount.run_id == run.id,
            ShopeeBankAccount.user_id == user_id,
        )
        .order_by(desc(ShopeeBankAccount.is_default), ShopeeBankAccount.id.desc())
        .all()
    )
    return ShopeeBankAccountsListResponse(
        total=len(rows),
        rows=[
            ShopeeBankAccountResponse(
                id=row.id,
                bank_name=row.bank_name,
                account_holder=row.account_holder,
                account_no_masked=row.account_no_masked,
                currency=row.currency,
                is_default=bool(row.is_default),
                verify_status=row.verify_status,
                created_at=row.created_at,
            )
            for row in rows
        ],
    )


@router.post("/runs/{run_id}/finance/bank-accounts", response_model=ShopeeBankAccountResponse)
def create_shopee_bank_account(
    run_id: int,
    payload: ShopeeBankAccountCreateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeBankAccountResponse:
    user_id = int(current_user["id"])
    run = _get_owned_running_run_or_404(db, run_id, user_id)

    bank_name = (payload.bank_name or "").strip()
    account_holder = (payload.account_holder or "").strip()
    account_no = (payload.account_no or "").strip().replace(" ", "")
    if len(account_holder) < 2 or len(account_holder) > 64:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="银行卡账户姓名需为2~64个字符")
    if not bank_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择银行名称")
    if len(account_no) < 4 or len(account_no) > 32:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="银行账号长度需为4~32位")

    exists = (
        db.query(ShopeeBankAccount)
        .filter(
            ShopeeBankAccount.run_id == run.id,
            ShopeeBankAccount.user_id == user_id,
            ShopeeBankAccount.account_no == account_no,
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该银行账号已存在")

    if payload.is_default:
        db.query(ShopeeBankAccount).filter(
            ShopeeBankAccount.run_id == run.id,
            ShopeeBankAccount.user_id == user_id,
            ShopeeBankAccount.is_default.is_(True),
        ).update({"is_default": False}, synchronize_session=False)

    new_row = ShopeeBankAccount(
        run_id=run.id,
        user_id=user_id,
        bank_name=bank_name,
        account_holder=account_holder,
        account_no=account_no,
        account_no_masked=_mask_bank_account_no(account_no),
        currency="RM",
        is_default=bool(payload.is_default),
        verify_status="verified",
    )
    db.add(new_row)
    db.commit()
    db.refresh(new_row)
    return ShopeeBankAccountResponse(
        id=new_row.id,
        bank_name=new_row.bank_name,
        account_holder=new_row.account_holder,
        account_no_masked=new_row.account_no_masked,
        currency=new_row.currency,
        is_default=bool(new_row.is_default),
        verify_status=new_row.verify_status,
        created_at=new_row.created_at,
    )


@router.post("/runs/{run_id}/finance/bank-accounts/{account_id}/set-default", response_model=ShopeeBankAccountResponse)
def set_default_shopee_bank_account(
    run_id: int,
    account_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeBankAccountResponse:
    user_id = int(current_user["id"])
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    row = (
        db.query(ShopeeBankAccount)
        .filter(
            ShopeeBankAccount.id == account_id,
            ShopeeBankAccount.run_id == run.id,
            ShopeeBankAccount.user_id == user_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="银行账户不存在")

    db.query(ShopeeBankAccount).filter(
        ShopeeBankAccount.run_id == run.id,
        ShopeeBankAccount.user_id == user_id,
        ShopeeBankAccount.is_default.is_(True),
    ).update({"is_default": False}, synchronize_session=False)
    row.is_default = True
    db.commit()
    db.refresh(row)
    return ShopeeBankAccountResponse(
        id=row.id,
        bank_name=row.bank_name,
        account_holder=row.account_holder,
        account_no_masked=row.account_no_masked,
        currency=row.currency,
        is_default=bool(row.is_default),
        verify_status=row.verify_status,
        created_at=row.created_at,
    )


@router.post("/runs/{run_id}/finance/withdraw", response_model=ShopeeFinanceWithdrawResponse)
def withdraw_shopee_wallet_to_game_cash(
    run_id: int,
    payload: ShopeeFinanceWithdrawRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeFinanceWithdrawResponse:
    user_id = int(current_user["id"])
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    _backfill_income_for_completed_orders(db, run_id=run.id, user_id=user_id, current_tick=current_tick)

    default_bank = (
        db.query(ShopeeBankAccount)
        .filter(
            ShopeeBankAccount.run_id == run.id,
            ShopeeBankAccount.user_id == user_id,
            ShopeeBankAccount.is_default.is_(True),
        )
        .order_by(ShopeeBankAccount.id.desc())
        .first()
    )
    if not default_bank:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先设置默认银行卡后再提现")

    withdraw_rm = round(float(payload.amount or 0), 2)
    if withdraw_rm <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="提现金额必须大于 0")

    wallet_balance = _calc_wallet_balance(db, run_id=run.id, user_id=user_id)
    if withdraw_rm > wallet_balance:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"余额不足，当前可提现 {wallet_balance:.2f} RM")

    credited_rmb = round(withdraw_rm * RM_TO_RMB_RATE, 2)
    balance_after = round(wallet_balance - withdraw_rm, 2)

    ledger = ShopeeFinanceLedgerEntry(
        run_id=run.id,
        user_id=user_id,
        order_id=None,
        entry_type="withdrawal",
        direction="out",
        amount=withdraw_rm,
        balance_after=balance_after,
        status="completed",
        remark=f"提现至工作台（汇率 1:{RM_TO_RMB_RATE:.2f}）",
        credited_at=current_tick,
    )
    db.add(ledger)
    db.flush()

    adjustment = GameRunCashAdjustment(
        run_id=run.id,
        user_id=user_id,
        source="shopee_withdrawal",
        direction="in",
        amount=credited_rmb,
        remark=f"Shopee 提现转入，银行卡 {default_bank.bank_name}（{default_bank.account_no_masked}）",
        related_ledger_id=ledger.id,
    )
    db.add(adjustment)
    db.commit()
    db.refresh(ledger)
    db.refresh(adjustment)

    return ShopeeFinanceWithdrawResponse(
        wallet_balance=balance_after,
        withdraw_rm=withdraw_rm,
        credited_rmb=credited_rmb,
        exchange_rate=round(RM_TO_RMB_RATE, 4),
        ledger_id=ledger.id,
        cash_adjustment_id=adjustment.id,
        credited_at=current_tick,
    )


@router.get("/runs/{run_id}/marketing-centre/bootstrap", response_model=ShopeeMarketingBootstrapResponse)
def get_shopee_marketing_bootstrap(
    run_id: int,
    lang: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeMarketingBootstrapResponse:
    user_id = int(current_user["id"])
    user = db.query(User).filter(User.id == user_id).first()
    public_id = str(user.public_id) if user and user.public_id else ""
    _enforce_shopee_marketing_bootstrap_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    safe_lang = _resolve_marketing_lang(lang)
    cache_key = _shopee_marketing_bootstrap_cache_key(
        run_id=run.id,
        user_id=user_id,
        market=run.market,
        lang=safe_lang,
    )
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeMarketingBootstrapResponse.model_validate(cached_payload)

    current_tick = _resolve_game_tick(db, run.id, user_id)
    payload = _build_marketing_bootstrap_payload(
        db=db,
        run=run,
        user_id=user_id,
        public_id=public_id,
        lang=safe_lang,
        current_tick=current_tick,
    )
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_MARKETING_BOOTSTRAP_SEC)
    return payload


@router.post("/runs/{run_id}/marketing/preferences", response_model=ShopeeMarketingPreferencesResponse)
def update_shopee_marketing_preferences(
    run_id: int,
    payload: ShopeeMarketingPreferencesUpdateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeMarketingPreferencesResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    pref = (
        db.query(ShopeeUserMarketingPreference)
        .filter(
            ShopeeUserMarketingPreference.run_id == run.id,
            ShopeeUserMarketingPreference.user_id == user_id,
        )
        .first()
    )
    now = datetime.now()
    if not pref:
        pref = ShopeeUserMarketingPreference(
            run_id=run.id,
            user_id=user_id,
            tools_collapsed=bool(payload.tools_collapsed),
            last_viewed_at=now,
        )
        db.add(pref)
    else:
        pref.tools_collapsed = bool(payload.tools_collapsed)
        pref.last_viewed_at = now
    db.commit()
    db.refresh(pref)
    _invalidate_shopee_marketing_bootstrap_cache(run_id=run.id, user_id=user_id)
    return ShopeeMarketingPreferencesResponse(
        tools_collapsed=bool(pref.tools_collapsed),
        last_viewed_at=pref.last_viewed_at,
    )


@router.get("/runs/{run_id}/marketing/discount/bootstrap", response_model=ShopeeDiscountBootstrapResponse)
def get_shopee_discount_bootstrap(
    run_id: int,
    discount_type: str = Query(default="all"),
    status_value: str = Query(default="all", alias="status"),
    search_field: str = Query(default="campaign_name"),
    keyword: str = Query(default=""),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDiscountBootstrapResponse:
    user_id = int(current_user["id"])
    user = db.query(User).filter(User.id == user_id).first()
    public_id = str(user.public_id) if user and user.public_id else ""
    _enforce_shopee_discount_bootstrap_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    safe_discount_type = _resolve_discount_type(discount_type)
    safe_status = _resolve_discount_status(status_value)
    safe_search_field = _resolve_discount_search_field(search_field)
    safe_keyword = keyword.strip()
    cache_key = _shopee_discount_bootstrap_cache_key(
        run_id=run.id,
        user_id=user_id,
        discount_type=safe_discount_type,
        status_value=safe_status,
        search_field=safe_search_field,
        keyword=safe_keyword,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeDiscountBootstrapResponse.model_validate(cached_payload)

    current_tick = _resolve_game_tick(db, run.id, user_id)
    payload = _build_discount_bootstrap_payload(
        db=db,
        run=run,
        user_id=user_id,
        public_id=public_id,
        current_tick=current_tick,
        read_only=run.status == "finished",
        discount_type=safe_discount_type,
        status_value=safe_status,
        search_field=safe_search_field,
        keyword=safe_keyword,
        date_from_raw=date_from,
        date_to_raw=date_to,
        page=page,
        page_size=page_size,
    )
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_DISCOUNT_BOOTSTRAP_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/discount/campaigns", response_model=ShopeeDiscountCampaignListResponse)
def list_shopee_discount_campaigns(
    run_id: int,
    discount_type: str = Query(default="all"),
    status_value: str = Query(default="all", alias="status"),
    search_field: str = Query(default="campaign_name"),
    keyword: str = Query(default=""),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDiscountCampaignListResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_discount_list_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    safe_discount_type = _resolve_discount_type(discount_type)
    safe_status = _resolve_discount_status(status_value)
    safe_search_field = _resolve_discount_search_field(search_field)
    safe_keyword = keyword.strip()
    cache_key = _shopee_discount_list_cache_key(
        run_id=run.id,
        user_id=user_id,
        discount_type=safe_discount_type,
        status_value=safe_status,
        search_field=safe_search_field,
        keyword=safe_keyword,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeDiscountCampaignListResponse.model_validate(cached_payload)

    current_tick = _resolve_game_tick(db, run.id, user_id)
    payload = _build_discount_campaign_list_response(
        db=db,
        run=run,
        user_id=user_id,
        discount_type=safe_discount_type,
        status_value=safe_status,
        search_field=safe_search_field,
        keyword=safe_keyword,
        date_from=_parse_discount_date(date_from),
        date_to=_parse_discount_date(date_to),
        current_tick=current_tick,
        page=page,
        page_size=page_size,
        read_only=run.status == "finished",
    )
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_DISCOUNT_LIST_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/discount/campaigns/{campaign_id}/detail", response_model=ShopeeDiscountDetailResponse)
def get_shopee_discount_campaign_detail(
    run_id: int,
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDiscountDetailResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_discount_detail_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    cache_key = _shopee_discount_detail_cache_key(
        run_id=run.id,
        user_id=user_id,
        campaign_id=campaign_id,
        section="main",
        page=1,
        page_size=10,
    )
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeDiscountDetailResponse.model_validate(cached_payload)

    campaign = _load_discount_campaign_or_404(db, run_id=run.id, user_id=user_id, campaign_id=campaign_id)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    payload = _build_discount_detail_response(
        db=db,
        run=run,
        user_id=user_id,
        campaign=campaign,
        current_tick=current_tick,
    )
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_DISCOUNT_DETAIL_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/discount/campaigns/{campaign_id}/data", response_model=ShopeeDiscountDataResponse)
def get_shopee_discount_campaign_data(
    run_id: int,
    campaign_id: int,
    time_basis: str = Query(default="order_time"),
    game_year: int = Query(default=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDiscountDataResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_discount_data_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    safe_time_basis = _resolve_discount_data_time_basis(time_basis)
    cache_key = _shopee_discount_data_cache_key(run_id=run.id, user_id=user_id, campaign_id=campaign_id, time_basis=safe_time_basis, game_year=game_year)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeDiscountDataResponse.model_validate(cached_payload)

    campaign = _load_discount_campaign_or_404(db, run_id=run.id, user_id=user_id, campaign_id=campaign_id)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    payload = _build_discount_data_response(db=db, run=run, user_id=user_id, campaign=campaign, current_tick=current_tick, time_basis=safe_time_basis, selected_game_year=game_year)
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_DISCOUNT_DETAIL_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/discount/campaigns/{campaign_id}/data/trend", response_model=ShopeeDiscountDataTrendResponse)
def get_shopee_discount_campaign_data_trend(
    run_id: int,
    campaign_id: int,
    metric: str = Query(default="sales_amount"),
    time_basis: str = Query(default="order_time"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDiscountDataTrendResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_discount_data_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    safe_time_basis = _resolve_discount_data_time_basis(time_basis)
    safe_metric = metric if metric in {"sales_amount", "units_sold", "orders_count", "buyers_count", "items_sold"} else "sales_amount"
    cache_key = _shopee_discount_data_trend_cache_key(run_id=run.id, user_id=user_id, campaign_id=campaign_id, metric=safe_metric, time_basis=safe_time_basis)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeDiscountDataTrendResponse.model_validate(cached_payload)
    campaign = _load_discount_campaign_or_404(db, run_id=run.id, user_id=user_id, campaign_id=campaign_id)
    if campaign.campaign_type == "add_on":
        addon_campaign = _load_addon_campaign_by_source_or_404(db, run_id=run.id, user_id=user_id, source_campaign_id=campaign.id)
        _cards, trend, _ranking_stats = _build_addon_data_analytics(db=db, run=run, user_id=user_id, campaign=addon_campaign, time_basis=safe_time_basis)
    else:
        _cards, trend, _ranking_stats = _build_discount_data_analytics(db=db, run=run, user_id=user_id, campaign_id=campaign_id, time_basis=safe_time_basis)
    cache_set_json(cache_key, trend.model_dump(mode="json"), REDIS_CACHE_TTL_DISCOUNT_DETAIL_SEC)
    return trend


@router.get("/runs/{run_id}/marketing/discount/campaigns/{campaign_id}/data/ranking", response_model=ShopeeDiscountDataRankingListResponse)
def list_shopee_discount_campaign_data_ranking(
    run_id: int,
    campaign_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    sort: str = Query(default="sales_amount"),
    order: str = Query(default="desc"),
    time_basis: str = Query(default="order_time"),
    game_year: int = Query(default=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDiscountDataRankingListResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_discount_data_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    safe_time_basis = _resolve_discount_data_time_basis(time_basis)
    safe_sort = _resolve_discount_data_sort(sort)
    safe_order = _resolve_discount_data_order(order)
    cache_key = _shopee_discount_data_ranking_cache_key(
        run_id=run.id,
        user_id=user_id,
        campaign_id=campaign_id,
        page=page,
        page_size=page_size,
        sort=safe_sort,
        order=safe_order,
        time_basis=safe_time_basis,
        game_year=game_year,
    )
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeDiscountDataRankingListResponse.model_validate(cached_payload)
    campaign = _load_discount_campaign_or_404(db, run_id=run.id, user_id=user_id, campaign_id=campaign_id)
    addon_campaign = _load_addon_campaign_by_source_or_404(db, run_id=run.id, user_id=user_id, source_campaign_id=campaign.id) if campaign.campaign_type == "add_on" else None
    current_tick = _resolve_game_tick(db, run.id, user_id)
    current_game_text = _format_discount_game_datetime(current_tick, run=run)
    current_game_date = datetime.strptime(current_game_text[:10], "%Y-%m-%d").date() if current_game_text else current_tick.date()
    campaign_range = _addon_data_campaign_game_date_range(addon_campaign, run=run) if addon_campaign else _discount_data_campaign_game_date_range(campaign, run=run)
    if campaign_range:
        first_year = campaign_range[0].year
        last_year = max(campaign_range[1].year, current_game_date.year)
    else:
        first_year = run.created_at.year
        last_year = current_game_date.year
    safe_game_year = game_year if first_year <= game_year <= last_year else current_game_date.year
    if safe_game_year < first_year or safe_game_year > last_year:
        safe_game_year = last_year
    if addon_campaign:
        _cards, _trend, ranking_stats = _build_addon_data_analytics(
            db=db,
            run=run,
            user_id=user_id,
            campaign=addon_campaign,
            time_basis=safe_time_basis,
            date_from=date(safe_game_year, 1, 1),
            date_to=date(safe_game_year + 1, 1, 1),
        )
        payload = _build_addon_data_ranking_response(
            campaign=addon_campaign,
            ranking_stats=ranking_stats,
            page=page,
            page_size=page_size,
            sort=safe_sort,
            order=safe_order,
        )
    else:
        _cards, _trend, ranking_stats = _build_discount_data_analytics(
            db=db,
            run=run,
            user_id=user_id,
            campaign_id=campaign_id,
            time_basis=safe_time_basis,
            date_from=date(safe_game_year, 1, 1),
            date_to=date(safe_game_year + 1, 1, 1),
        )
        payload = _build_discount_data_ranking_response(
            db=db,
            campaign_id=campaign_id,
            ranking_stats=ranking_stats,
            page=page,
            page_size=page_size,
            sort=safe_sort,
            order=safe_order,
        )
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_DISCOUNT_DETAIL_SEC)
    return payload


@router.post("/runs/{run_id}/marketing/discount/campaigns/{campaign_id}/data/export", response_model=ShopeeDiscountDataExportResponse)
def export_shopee_discount_campaign_data(
    run_id: int,
    campaign_id: int,
    payload: ShopeeDiscountDataExportRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDiscountDataExportResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_discount_data_export_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    campaign = _load_discount_campaign_or_404(db, run_id=run.id, user_id=user_id, campaign_id=campaign_id)
    safe_time_basis = _resolve_discount_data_time_basis(payload.time_basis)
    safe_export_type = (payload.export_type or "csv").strip().lower()
    if safe_export_type != "csv":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前仅支持 CSV 导出")
    if campaign.campaign_type == "add_on":
        addon_campaign = _load_addon_campaign_by_source_or_404(db, run_id=run.id, user_id=user_id, source_campaign_id=campaign.id)
        _cards, _trend, ranking_stats = _build_addon_data_analytics(db=db, run=run, user_id=user_id, campaign=addon_campaign, time_basis=safe_time_basis)
        total_items = len(addon_campaign.reward_items or [])
        ranking = _build_addon_data_ranking_response(
            campaign=addon_campaign,
            ranking_stats=ranking_stats,
            page=1,
            page_size=max(1, total_items),
            sort="sales_amount",
            order="desc",
        )
    else:
        _cards, _trend, ranking_stats = _build_discount_data_analytics(db=db, run=run, user_id=user_id, campaign_id=campaign.id, time_basis=safe_time_basis)
        total_items = db.query(ShopeeDiscountCampaignItem).filter(ShopeeDiscountCampaignItem.campaign_id == campaign.id).count()
        ranking = _build_discount_data_ranking_response(
            db=db,
            campaign_id=campaign.id,
            ranking_stats=ranking_stats,
            page=1,
            page_size=max(1, total_items),
            sort="sales_amount",
            order="desc",
        )

    def csv_cell(value: Any) -> str:
        text = str(value)
        if text[:1] in {"=", "+", "-", "@"}:
            text = f"'{text}"
        return f'"{text.replace(chr(34), chr(34) + chr(34))}"'

    csv_lines = ["rank,product_name,variation_name,original_price,discount_label,discounted_price,units_sold,buyers_count,sales_amount"]
    for row in ranking.rows:
        values = [
            row.rank,
            row.product_name,
            row.variation_name or "",
            f"{row.original_price:.2f}",
            row.discount_label,
            "" if row.discounted_price is None else f"{row.discounted_price:.2f}",
            row.units_sold,
            row.buyers_count,
            f"{row.sales_amount:.2f}",
        ]
        csv_lines.append(",".join(csv_cell(value) for value in values))
    csv_content = "\ufeff" + "\n".join(csv_lines)
    return ShopeeDiscountDataExportResponse(
        export_id=str(uuid4()),
        status="ready",
        download_url=f"data:text/csv;charset=utf-8,{quote(csv_content)}",
        expires_at=None,
    )


@router.get("/runs/{run_id}/marketing/discount/campaigns/{campaign_id}/items", response_model=ShopeeDiscountDetailItemListResponse)
def list_shopee_discount_campaign_detail_items(
    run_id: int,
    campaign_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDiscountDetailItemListResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_discount_detail_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    campaign = _load_discount_campaign_or_404(db, run_id=run.id, user_id=user_id, campaign_id=campaign_id)
    cache_key = _shopee_discount_detail_cache_key(
        run_id=run.id,
        user_id=user_id,
        campaign_id=campaign_id,
        section="items",
        page=page,
        page_size=page_size,
    )
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeDiscountDetailItemListResponse.model_validate(cached_payload)
    if campaign.campaign_type == "add_on":
        addon_campaign = _load_addon_campaign_by_source_or_404(db, run_id=run.id, user_id=user_id, source_campaign_id=campaign.id)
        payload = _build_addon_detail_items_response(db=db, campaign=addon_campaign, page=page, page_size=page_size)
    else:
        payload = _build_discount_detail_items_response(db=db, campaign_id=campaign_id, page=page, page_size=page_size)
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_DISCOUNT_DETAIL_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/discount/campaigns/{campaign_id}/daily", response_model=ShopeeDiscountDetailDailyListResponse)
def list_shopee_discount_campaign_detail_daily(
    run_id: int,
    campaign_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDiscountDetailDailyListResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_discount_detail_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    _load_discount_campaign_or_404(db, run_id=run.id, user_id=user_id, campaign_id=campaign_id)
    cache_key = _shopee_discount_detail_cache_key(
        run_id=run.id,
        user_id=user_id,
        campaign_id=campaign_id,
        section="daily",
        page=page,
        page_size=page_size,
    )
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeDiscountDetailDailyListResponse.model_validate(cached_payload)
    payload = _build_discount_detail_daily_response(db=db, run_id=run.id, user_id=user_id, campaign_id=campaign_id, page=page, page_size=page_size)
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_DISCOUNT_DETAIL_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/discount/campaigns/{campaign_id}/orders", response_model=ShopeeDiscountDetailOrderListResponse)
def list_shopee_discount_campaign_detail_orders(
    run_id: int,
    campaign_id: int,
    status_value: str = Query(default="all", alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDiscountDetailOrderListResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_discount_detail_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    campaign = _load_discount_campaign_or_404(db, run_id=run.id, user_id=user_id, campaign_id=campaign_id)
    addon_campaign = _load_addon_campaign_by_source_or_404(db, run_id=run.id, user_id=user_id, source_campaign_id=campaign.id) if campaign.campaign_type == "add_on" else None
    safe_status = _resolve_discount_order_status(status_value)
    cache_key = _shopee_discount_detail_cache_key(
        run_id=run.id,
        user_id=user_id,
        campaign_id=campaign_id,
        section="orders",
        page=page,
        page_size=page_size,
        status_value=safe_status,
    )
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeDiscountDetailOrderListResponse.model_validate(cached_payload)
    payload = _build_discount_detail_orders_response(db=db, run_id=run.id, user_id=user_id, campaign_id=campaign_id, page=page, page_size=page_size, status_value=safe_status, addon_campaign=addon_campaign)
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_DISCOUNT_DETAIL_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/bundle/campaigns/{campaign_id}/orders", response_model=ShopeeBundleOrdersResponse)
def get_shopee_bundle_campaign_orders(
    run_id: int,
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeBundleOrdersResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_orders_list_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    campaign = _load_discount_campaign_or_404(db, run_id=run.id, user_id=user_id, campaign_id=campaign_id)
    if campaign.campaign_type != "bundle":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="套餐优惠活动不存在")
    cache_key = _shopee_bundle_orders_cache_key(run_id=run.id, user_id=user_id, campaign_id=campaign_id)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeBundleOrdersResponse.model_validate(cached_payload)
    payload = _build_bundle_orders_response(db=db, run=run, user_id=user_id, campaign=campaign)
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_ORDERS_LIST_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/add-on/campaigns/{campaign_id}/orders", response_model=ShopeeAddonOrdersResponse)
def get_shopee_addon_campaign_orders(
    run_id: int,
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeAddonOrdersResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_orders_list_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    campaign = _load_addon_campaign_by_source_or_404(db, run_id=run.id, user_id=user_id, source_campaign_id=campaign_id)
    cache_key = _shopee_addon_orders_cache_key(run_id=run.id, user_id=user_id, source_campaign_id=campaign_id)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeAddonOrdersResponse.model_validate(cached_payload)
    payload = _build_addon_orders_response(db=db, run=run, user_id=user_id, campaign=campaign)
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_ORDERS_LIST_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/flash-sale/create/bootstrap", response_model=ShopeeFlashSaleCreateBootstrapResponse)
def get_shopee_flash_sale_create_bootstrap(
    run_id: int,
    draft_id: int | None = Query(default=None),
    source_campaign_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeFlashSaleCreateBootstrapResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_flash_sale_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    cache_key = _shopee_flash_sale_bootstrap_cache_key(run_id=run.id, user_id=user_id, draft_id=draft_id, source_campaign_id=source_campaign_id)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeFlashSaleCreateBootstrapResponse.model_validate(cached_payload)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    category_payload = _build_flash_sale_stocked_category_rules_response(db, run=run, user_id=user_id)
    selected_products: list[ShopeeFlashSaleProductRowResponse] = []
    selected_slot = None
    campaign_name = ""
    if draft_id:
        draft = db.query(ShopeeFlashSaleDraft).filter(ShopeeFlashSaleDraft.id == draft_id, ShopeeFlashSaleDraft.run_id == run.id, ShopeeFlashSaleDraft.user_id == user_id).first()
        if not draft:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="限时抢购草稿不存在")
        detail = _build_flash_sale_draft_detail_response(db, draft)
        selected_products = detail.items
        campaign_name = draft.campaign_name
        if draft.slot_date and draft.slot_key:
            slot = next((row for row in _load_flash_sale_slots(db, run.market) if row.slot_key == draft.slot_key), None)
            if slot:
                selected_slot = _build_flash_sale_slot_response(db, run=run, user_id=user_id, slot_date=draft.slot_date, slot=slot, current_tick=current_tick)
    payload = ShopeeFlashSaleCreateBootstrapResponse(
        meta=ShopeeFlashSaleMetaResponse(
            run_id=run.id,
            user_id=user_id,
            market=(run.market or "MY"),
            read_only=run.status == "finished",
            current_tick=current_tick,
            current_game_time=_format_discount_game_datetime(current_tick, run=run) or current_tick.strftime("%Y-%m-%dT%H:%M"),
        ),
        form=ShopeeFlashSaleCreateFormResponse(campaign_name=campaign_name, selected_slot=selected_slot),
        rules=ShopeeFlashSaleRulesResponse(),
        categories=category_payload.categories,
        category_rules=category_payload.category_rules,
        selected_products=selected_products,
    )
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_FLASH_SALE_BOOTSTRAP_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/flash-sale/slots", response_model=ShopeeFlashSaleSlotsResponse)
def list_shopee_flash_sale_slots(
    run_id: int,
    date_value: str = Query(alias="date"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeFlashSaleSlotsResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_flash_sale_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    parsed_date = _parse_flash_sale_date(date_value)
    if not parsed_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="日期格式应为 YYYY-MM-DD")
    cache_key = _shopee_flash_sale_slots_cache_key(run_id=run.id, date_value=parsed_date.isoformat())
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeFlashSaleSlotsResponse.model_validate(cached_payload)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    slots = [_build_flash_sale_slot_response(db, run=run, user_id=user_id, slot_date=parsed_date, slot=slot, current_tick=current_tick) for slot in _load_flash_sale_slots(db, run.market)]
    payload = ShopeeFlashSaleSlotsResponse(date=parsed_date.isoformat(), slots=slots)
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_FLASH_SALE_BOOTSTRAP_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/flash-sale/category-rules", response_model=ShopeeFlashSaleCategoryRulesResponse)
def get_shopee_flash_sale_category_rules(
    run_id: int,
    category_key: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeFlashSaleCategoryRulesResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_flash_sale_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    cache_key = _shopee_flash_sale_category_rules_cache_key(market=(run.market or "MY"))
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        payload = ShopeeFlashSaleCategoryRulesResponse.model_validate(cached_payload)
    else:
        payload = _build_flash_sale_category_rules_response(db, market=run.market)
        cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_FLASH_SALE_BOOTSTRAP_SEC)
    if category_key:
        if category_key not in {category.key for category in payload.categories}:
            payload.categories = [*payload.categories, ShopeeFlashSaleCategoryResponse(key=category_key, label=category_key)]
        payload.category_rules = {category_key: payload.category_rules.get(category_key) or payload.category_rules.get("all", [])}
    return payload


@router.get("/runs/{run_id}/marketing/flash-sale/eligible-products", response_model=ShopeeFlashSaleEligibleProductsResponse)
def list_shopee_flash_sale_eligible_products(
    run_id: int,
    slot_date: str = Query(default=""),
    slot_key: str = Query(default=""),
    category_key: str = Query(default="all"),
    keyword: str = Query(default=""),
    search_field: str = Query(default="product_name"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeFlashSaleEligibleProductsResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_flash_sale_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    parsed_date = _parse_flash_sale_date(slot_date)
    if not parsed_date or not slot_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先选择限时抢购时间段")
    cache_key = _shopee_flash_sale_eligible_cache_key(run_id=run.id, user_id=user_id, slot_date=parsed_date.isoformat(), slot_key=slot_key, category_key=category_key, keyword=keyword, search_field=search_field, page=page, page_size=page_size)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeFlashSaleEligibleProductsResponse.model_validate(cached_payload)
    payload = _build_flash_sale_eligible_products_response(db=db, run=run, user_id=user_id, slot_date=parsed_date, slot_key=slot_key, category_key=category_key, keyword=keyword, search_field=search_field, page=page, page_size=page_size)
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_FLASH_SALE_ELIGIBLE_PRODUCTS_SEC)
    return payload


@router.post("/runs/{run_id}/marketing/flash-sale/drafts", response_model=ShopeeFlashSaleDraftUpsertResponse)
def upsert_shopee_flash_sale_draft(
    run_id: int,
    payload: ShopeeFlashSaleDraftUpsertRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeFlashSaleDraftUpsertResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_flash_sale_rate_limit(user_id=user_id, create=True)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    parsed_date = _parse_flash_sale_date(payload.slot_date)
    if payload.items and (not parsed_date or not payload.slot_key):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先选择限时抢购时间段")
    if parsed_date and payload.slot_key and payload.items:
        _validate_flash_sale_items(db=db, run=run, user_id=user_id, slot_date=parsed_date, slot_key=payload.slot_key, items=payload.items)
    draft = db.query(ShopeeFlashSaleDraft).filter(ShopeeFlashSaleDraft.id == payload.draft_id, ShopeeFlashSaleDraft.run_id == run.id, ShopeeFlashSaleDraft.user_id == user_id).first() if payload.draft_id else None
    if not draft:
        draft = ShopeeFlashSaleDraft(run_id=run.id, user_id=user_id)
        db.add(draft)
        db.flush()
    draft.campaign_name = payload.campaign_name.strip()
    draft.slot_date = parsed_date
    draft.slot_key = payload.slot_key or None
    draft.payload_json = payload.model_dump_json()
    draft.items.clear()
    for item in payload.items:
        draft.items.append(ShopeeFlashSaleDraftItem(listing_id=item.listing_id, variant_id=item.variant_id, flash_price=item.flash_price, activity_stock_limit=item.activity_stock_limit, purchase_limit_per_buyer=item.purchase_limit_per_buyer))
    db.commit()
    db.refresh(draft)
    _invalidate_shopee_flash_sale_cache(run_id=run.id, user_id=user_id, draft_id=draft.id)
    return ShopeeFlashSaleDraftUpsertResponse(draft_id=draft.id, saved_at=draft.updated_at)


@router.get("/runs/{run_id}/marketing/flash-sale/drafts/{draft_id}", response_model=ShopeeFlashSaleDraftDetailResponse)
def get_shopee_flash_sale_draft(
    run_id: int,
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeFlashSaleDraftDetailResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    cache_key = _shopee_flash_sale_draft_cache_key(run_id=run.id, user_id=user_id, draft_id=draft_id)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeFlashSaleDraftDetailResponse.model_validate(cached_payload)
    draft = db.query(ShopeeFlashSaleDraft).filter(ShopeeFlashSaleDraft.id == draft_id, ShopeeFlashSaleDraft.run_id == run.id, ShopeeFlashSaleDraft.user_id == user_id).first()
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="限时抢购草稿不存在")
    payload = _build_flash_sale_draft_detail_response(db, draft)
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_FLASH_SALE_DRAFT_SEC)
    return payload


@router.post("/runs/{run_id}/marketing/flash-sale/campaigns", response_model=ShopeeFlashSaleCampaignCreateResponse, status_code=status.HTTP_201_CREATED)
def create_shopee_flash_sale_campaign(
    run_id: int,
    payload: ShopeeFlashSaleCampaignCreateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeFlashSaleCampaignCreateResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_flash_sale_rate_limit(user_id=user_id, create=True)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    campaign_name = payload.campaign_name.strip() or "店铺限时抢购活动"
    if len(campaign_name) > 60:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="活动名称不能超过 60 个字符")
    parsed_date = _parse_flash_sale_date(payload.slot_date)
    if not parsed_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="日期格式应为 YYYY-MM-DD")
    slot, listing_map, variant_map = _validate_flash_sale_items(db=db, run=run, user_id=user_id, slot_date=parsed_date, slot_key=payload.slot_key, items=payload.items)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    start_tick, end_tick = _flash_sale_slot_ticks(parsed_date, slot, run=run)
    if end_tick <= current_tick:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已结束时间段不可创建")
    campaign = ShopeeFlashSaleCampaign(run_id=run.id, user_id=user_id, campaign_name=campaign_name, slot_date=parsed_date, slot_key=slot.slot_key, start_tick=start_tick, end_tick=end_tick, status="active", total_product_limit=int(slot.product_limit or 50))
    db.add(campaign)
    db.flush()
    for item in payload.items:
        listing = listing_map[item.listing_id]
        variant = variant_map.get(item.variant_id) if item.variant_id else None
        original_price = float(variant.price if variant else listing.price)
        discount_percent = round((1 - float(item.flash_price) / original_price) * 100, 2)
        db.add(ShopeeFlashSaleCampaignItem(campaign_id=campaign.id, run_id=run.id, user_id=user_id, listing_id=listing.id, variant_id=variant.id if variant else None, product_id=listing.product_id, product_name_snapshot=listing.title, variant_name_snapshot=variant.option_value if variant else None, sku_snapshot=variant.sku if variant else listing.sku_code, image_url_snapshot=variant.image_url if variant and variant.image_url else listing.cover_url, original_price=original_price, flash_price=round(float(item.flash_price), 2), discount_percent=discount_percent, activity_stock_limit=int(item.activity_stock_limit), sold_qty=0, purchase_limit_per_buyer=int(item.purchase_limit_per_buyer or 1), status=item.status))
    if payload.draft_id:
        draft = db.query(ShopeeFlashSaleDraft).filter(ShopeeFlashSaleDraft.id == payload.draft_id, ShopeeFlashSaleDraft.run_id == run.id, ShopeeFlashSaleDraft.user_id == user_id).first()
        if draft:
            db.delete(draft)
    db.commit()
    db.refresh(campaign)
    _invalidate_shopee_flash_sale_cache(run_id=run.id, user_id=user_id, draft_id=payload.draft_id, campaign_id=campaign.id)
    return ShopeeFlashSaleCampaignCreateResponse(campaign_id=campaign.id, status=_flash_sale_status(campaign, current_tick=current_tick))


@router.get("/runs/{run_id}/marketing/flash-sale/campaigns/{campaign_id}/data", response_model=ShopeeFlashSaleDataResponse)
def get_shopee_flash_sale_campaign_data(
    run_id: int,
    campaign_id: int,
    order_type: str = Query(default="confirmed"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeFlashSaleDataResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_flash_sale_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    safe_order_type = _resolve_flash_sale_data_order_type(order_type)
    cache_key = _shopee_flash_sale_data_cache_key(run_id=run.id, user_id=user_id, campaign_id=campaign_id, order_type=safe_order_type)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeFlashSaleDataResponse.model_validate(cached_payload)
    campaign = _load_flash_sale_campaign_or_404(db, run_id=run.id, user_id=user_id, campaign_id=campaign_id)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    payload = ShopeeFlashSaleDataResponse(
        campaign=_build_flash_sale_data_campaign(campaign, run=run, current_tick=current_tick),
        order_type=safe_order_type,
        metrics=_build_flash_sale_data_metrics(db, run=run, user_id=user_id, campaign=campaign, order_type=safe_order_type),
    )
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_FLASH_SALE_DETAIL_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/flash-sale/campaigns/{campaign_id}/data/products", response_model=ShopeeFlashSaleDataProductsResponse)
def list_shopee_flash_sale_campaign_data_products(
    run_id: int,
    campaign_id: int,
    order_type: str = Query(default="confirmed"),
    sort_by: str = Query(default="sales_amount"),
    sort_order: str = Query(default="desc"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeFlashSaleDataProductsResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_flash_sale_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    safe_order_type = _resolve_flash_sale_data_order_type(order_type)
    safe_sort_by = _resolve_flash_sale_data_sort(sort_by)
    safe_sort_order = _resolve_flash_sale_data_sort_order(sort_order)
    cache_key = _shopee_flash_sale_data_products_cache_key(run_id=run.id, user_id=user_id, campaign_id=campaign_id, order_type=safe_order_type, sort_by=safe_sort_by, sort_order=safe_sort_order)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeFlashSaleDataProductsResponse.model_validate(cached_payload)
    campaign = _load_flash_sale_campaign_or_404(db, run_id=run.id, user_id=user_id, campaign_id=campaign_id)
    payload = _build_flash_sale_data_products(db, run=run, user_id=user_id, campaign=campaign, order_type=safe_order_type, sort_by=safe_sort_by, sort_order=safe_sort_order)
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_FLASH_SALE_DETAIL_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/flash-sale/campaigns/{campaign_id}/data/export", response_model=ShopeeFlashSaleDataExportResponse)
def export_shopee_flash_sale_campaign_data(
    run_id: int,
    campaign_id: int,
    order_type: str = Query(default="confirmed"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeFlashSaleDataExportResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    if run.status == "finished":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="历史对局回溯模式下不可导出数据")
    safe_order_type = _resolve_flash_sale_data_order_type(order_type)
    campaign = _load_flash_sale_campaign_or_404(db, run_id=run.id, user_id=user_id, campaign_id=campaign_id)
    products = _build_flash_sale_data_products(db, run=run, user_id=user_id, campaign=campaign, order_type=safe_order_type, sort_by="sales_amount", sort_order="desc")
    csv_lines = ["活动ID,活动名称,订单类型,商品ID,商品名称,变体ID,变体名称,活动库存,折后价,销售额,订单数,售出件数"]
    order_type_label = "已下单" if safe_order_type == "placed" else "已确认订单"
    for product in products.items:
        for variation in product.variations:
            csv_lines.append(
                ",".join(
                    [
                        str(campaign.id),
                        campaign.campaign_name,
                        order_type_label,
                        str(product.listing_id),
                        product.name,
                        str(variation.variant_id or ""),
                        variation.variation_name,
                        str(variation.activity_stock),
                        f"{variation.flash_price:.2f}",
                        f"{variation.sales_amount:.2f}",
                        str(variation.order_count),
                        str(variation.unit_count),
                    ]
                )
            )
    csv_content = "\ufeff" + "\n".join(csv_lines)
    return ShopeeFlashSaleDataExportResponse(export_id=str(uuid4()), status="ready", download_url=f"data:text/csv;charset=utf-8,{quote(csv_content)}")


@router.get("/runs/{run_id}/marketing/flash-sale/performance", response_model=ShopeeFlashSalePerformanceResponse)
def get_shopee_flash_sale_performance(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeFlashSalePerformanceResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_flash_sale_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    cache_key = _shopee_flash_sale_performance_cache_key(run_id=run.id, user_id=user_id)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeFlashSalePerformanceResponse.model_validate(cached_payload)
    payload = _build_flash_sale_performance(db=db, run=run, user_id=user_id, current_tick=current_tick)
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_FLASH_SALE_LIST_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/flash-sale/campaigns", response_model=ShopeeFlashSaleCampaignListResponse)
def list_shopee_flash_sale_campaigns(
    run_id: int,
    status_value: str = Query(default="all", alias="status"),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeFlashSaleCampaignListResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_flash_sale_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    cache_key = _shopee_flash_sale_list_cache_key(run_id=run.id, user_id=user_id, status=status_value, date_from=date_from, date_to=date_to, page=page, page_size=page_size)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeFlashSaleCampaignListResponse.model_validate(cached_payload)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    query = db.query(ShopeeFlashSaleCampaign).options(selectinload(ShopeeFlashSaleCampaign.items), selectinload(ShopeeFlashSaleCampaign.run)).filter(ShopeeFlashSaleCampaign.run_id == run.id, ShopeeFlashSaleCampaign.user_id == user_id)
    parsed_from = _parse_flash_sale_date(date_from)
    parsed_to = _parse_flash_sale_date(date_to)
    if parsed_from:
        query = query.filter(ShopeeFlashSaleCampaign.slot_date >= parsed_from)
    if parsed_to:
        query = query.filter(ShopeeFlashSaleCampaign.slot_date <= parsed_to)
    rows_all = query.order_by(desc(ShopeeFlashSaleCampaign.start_tick), desc(ShopeeFlashSaleCampaign.id)).all()
    if status_value != "all":
        rows_all = [row for row in rows_all if _flash_sale_status(row, current_tick=current_tick) == status_value]
    total = len(rows_all)
    page_rows = rows_all[(page - 1) * page_size: page * page_size]
    rows = []
    for row in page_rows:
        display_status = _flash_sale_status(row, current_tick=current_tick)
        rows.append(ShopeeFlashSaleCampaignRowResponse(id=row.id, slot_date=row.slot_date.isoformat(), display_time=_flash_sale_campaign_display_time(row, run=run), product_enabled_count=len([item for item in row.items if item.status == "active"]), product_limit=row.total_product_limit, reminder_count=row.reminder_count, click_count=row.click_count, status=display_status, status_label=_flash_sale_status_label(display_status), enabled=row.status == "active", actions=["detail", "copy", "data"]))
    payload = ShopeeFlashSaleCampaignListResponse(page=page, page_size=page_size, total=total, rows=rows)
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_FLASH_SALE_LIST_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/flash-sale/campaigns/{campaign_id}", response_model=ShopeeFlashSaleCampaignDetailResponse)
def get_shopee_flash_sale_campaign_detail(
    run_id: int,
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeFlashSaleCampaignDetailResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_flash_sale_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    cache_key = _shopee_flash_sale_detail_cache_key(run_id=run.id, campaign_id=campaign_id)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeFlashSaleCampaignDetailResponse.model_validate(cached_payload)
    campaign = _load_flash_sale_campaign_or_404(db, run_id=run.id, user_id=user_id, campaign_id=campaign_id)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    display_status = _flash_sale_status(campaign, current_tick=current_tick)
    rules = _load_flash_sale_category_rules(db, run.market)
    label_by_key = {rule.category_key: rule.category_label for rule in rules}
    category_by_product_id = _flash_sale_market_category_by_product_id(db, run_id=run.id)
    if not category_by_product_id:
        category_by_product_id = {
            int(product_id): str(category)
            for product_id, category in db.query(MarketProduct.id, MarketProduct.category).all()
            if product_id and category
        }
    listing_ids = {item.listing_id for item in campaign.items}
    listing_map = {
        row.id: row
        for row in db.query(ShopeeListing).filter(ShopeeListing.id.in_(listing_ids)).all()
    } if listing_ids else {}
    items = []
    for item in campaign.items:
        listing = listing_map.get(item.listing_id)
        category_key = _flash_sale_category_key_for_listing(listing, rules, category_by_product_id) if listing else "all"
        product_id = listing.product_id if listing else item.product_id
        category_label = category_by_product_id.get(product_id or 0) or label_by_key.get(category_key, "全部")
        image_url = listing.cover_url if listing and listing.cover_url else item.image_url_snapshot
        items.append(ShopeeFlashSaleProductRowResponse(listing_id=item.listing_id, variant_id=item.variant_id, product_id=item.product_id, product_name=item.product_name_snapshot, variant_name=item.variant_name_snapshot or "", sku=item.sku_snapshot, image_url=image_url, category_key=category_key, category_label=category_label, original_price=item.original_price, stock_available=max(0, item.activity_stock_limit - item.sold_qty), flash_price=item.flash_price, activity_stock_limit=item.activity_stock_limit, purchase_limit_per_buyer=item.purchase_limit_per_buyer, status=item.status, suggested_flash_price=item.flash_price))
    payload = ShopeeFlashSaleCampaignDetailResponse(id=campaign.id, campaign_name=campaign.campaign_name, slot_date=campaign.slot_date.isoformat(), slot_key=campaign.slot_key, display_time=_flash_sale_campaign_display_time(campaign, run=run), status=display_status, status_label=_flash_sale_status_label(display_status), enabled=campaign.status == "active", items=items, reminder_count=campaign.reminder_count, click_count=campaign.click_count, order_count=campaign.order_count, sales_amount=float(campaign.sales_amount or 0))
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_FLASH_SALE_DETAIL_SEC)
    return payload


@router.post("/runs/{run_id}/marketing/flash-sale/campaigns/{campaign_id}/toggle", response_model=ShopeeFlashSaleCampaignRowResponse)
def toggle_shopee_flash_sale_campaign(
    run_id: int,
    campaign_id: int,
    payload: ShopeeFlashSaleToggleRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeFlashSaleCampaignRowResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_flash_sale_rate_limit(user_id=user_id, create=True)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    campaign = _load_flash_sale_campaign_or_404(db, run_id=run.id, user_id=user_id, campaign_id=campaign_id)
    campaign.status = "active" if payload.enabled else "disabled"
    db.commit()
    db.refresh(campaign)
    _invalidate_shopee_flash_sale_cache(run_id=run.id, user_id=user_id, campaign_id=campaign.id)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    display_status = _flash_sale_status(campaign, current_tick=current_tick)
    return ShopeeFlashSaleCampaignRowResponse(id=campaign.id, slot_date=campaign.slot_date.isoformat(), display_time=_flash_sale_campaign_display_time(campaign, run=run), product_enabled_count=len([item for item in campaign.items if item.status == "active"]), product_limit=campaign.total_product_limit, reminder_count=campaign.reminder_count, click_count=campaign.click_count, status=display_status, status_label=_flash_sale_status_label(display_status), enabled=campaign.status == "active", actions=["detail", "copy", "data"])


@router.post("/runs/{run_id}/marketing/discount/preferences", response_model=ShopeeDiscountPreferencesResponse)
def update_shopee_discount_preferences(
    run_id: int,
    payload: ShopeeDiscountPreferencesUpdateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDiscountPreferencesResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    pref = (
        db.query(ShopeeUserDiscountPreference)
        .filter(
            ShopeeUserDiscountPreference.run_id == run.id,
            ShopeeUserDiscountPreference.user_id == user_id,
        )
        .first()
    )
    now = datetime.now()
    if not pref:
        pref = ShopeeUserDiscountPreference(run_id=run.id, user_id=user_id)
        db.add(pref)
    pref.selected_discount_type = _resolve_discount_type(payload.selected_discount_type)
    pref.selected_status = _resolve_discount_status(payload.selected_status)
    pref.search_field = _resolve_discount_search_field(payload.search_field)
    pref.keyword = payload.keyword.strip() or None
    parsed_date_from = _parse_discount_date(payload.date_from)
    parsed_date_to = _parse_discount_date(payload.date_to)
    pref.date_from = datetime.combine(parsed_date_from, datetime.min.time()) if parsed_date_from else None
    pref.date_to = datetime.combine(parsed_date_to, datetime.min.time()) if parsed_date_to else None
    pref.last_viewed_at = now
    db.commit()
    db.refresh(pref)
    _invalidate_shopee_discount_cache(run_id=run.id, user_id=user_id)
    return ShopeeDiscountPreferencesResponse(
        selected_discount_type=pref.selected_discount_type,
        selected_status=pref.selected_status,
        search_field=pref.search_field,
        keyword=pref.keyword or "",
        date_from=pref.date_from,
        date_to=pref.date_to,
        last_viewed_at=pref.last_viewed_at,
    )


@router.get("/runs/{run_id}/marketing/discount/create/bootstrap", response_model=ShopeeDiscountCreateBootstrapResponse)
def get_shopee_discount_create_bootstrap(
    run_id: int,
    campaign_type: str = Query(default="discount"),
    draft_id: int | None = Query(default=None),
    source_campaign_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDiscountCreateBootstrapResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_discount_create_bootstrap_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    safe_campaign_type = _resolve_discount_type(campaign_type)
    if safe_campaign_type != "discount":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前仅支持单品折扣创建页")
    cache_key = _shopee_discount_create_bootstrap_cache_key(
        run_id=run.id,
        user_id=user_id,
        campaign_type=safe_campaign_type,
        draft_id=draft_id,
        source_campaign_id=source_campaign_id,
    )
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeDiscountCreateBootstrapResponse.model_validate(cached_payload)

    current_tick = _resolve_game_tick(db, run.id, user_id)
    draft = _load_discount_draft_or_404(db, draft_id=draft_id, run_id=run.id, user_id=user_id) if draft_id else None
    payload = _build_discount_create_bootstrap_payload(
        db=db,
        run=run,
        user_id=user_id,
        current_tick=current_tick,
        read_only=run.status == "finished",
        campaign_type=safe_campaign_type,
        draft=draft,
    )
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_DISCOUNT_CREATE_BOOTSTRAP_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/discount/eligible-products", response_model=ShopeeDiscountEligibleProductsResponse)
def list_shopee_discount_eligible_products(
    run_id: int,
    keyword: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDiscountEligibleProductsResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_discount_eligible_products_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    cache_key = _shopee_discount_eligible_products_cache_key(
        run_id=run.id,
        user_id=user_id,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeDiscountEligibleProductsResponse.model_validate(cached_payload)

    payload = _build_discount_eligible_products_response(
        db=db,
        run=run,
        user_id=user_id,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_DISCOUNT_ELIGIBLE_PRODUCTS_SEC)
    return payload


@router.get("/runs/{run_id}/customer-service/model-settings", response_model=ShopeeCustomerServiceModelSettingResponse)
def get_shopee_customer_service_model_settings(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeCustomerServiceModelSettingResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    return _serialize_customer_service_model_setting(_get_customer_service_model_setting(db, run_id=run.id, user_id=user_id))


@router.put("/runs/{run_id}/customer-service/model-settings", response_model=ShopeeCustomerServiceModelSettingUpdateResponse)
def update_shopee_customer_service_model_settings(
    run_id: int,
    payload: ShopeeCustomerServiceModelSettingUpdateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeCustomerServiceModelSettingUpdateResponse:
    user_id = int(current_user["id"])
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    provider = payload.provider.strip() or "lm_studio"
    model_name = payload.model_name.strip()
    if not model_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="客服模型名称不能为空")
    base_url = (payload.base_url or "http://localhost:1234/v1").strip().rstrip("/")
    if not base_url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="客服模型 Base URL 不能为空")
    row = db.query(ShopeeCustomerServiceModelSetting).filter(ShopeeCustomerServiceModelSetting.run_id == run.id, ShopeeCustomerServiceModelSetting.user_id == user_id).first()
    if row is None:
        row = ShopeeCustomerServiceModelSetting(run_id=run.id, user_id=user_id)
        db.add(row)
    row.provider = provider
    row.model_name = model_name
    row.base_url = base_url
    row.api_key_ref = payload.api_key_ref.strip() if payload.api_key_ref else None
    row.temperature = float(payload.temperature)
    row.max_tokens = int(payload.max_tokens)
    row.enabled = bool(payload.enabled)
    db.commit()
    db.refresh(row)
    _invalidate_customer_service_cache(run_id=run.id, user_id=user_id)
    return ShopeeCustomerServiceModelSettingUpdateResponse(setting=_serialize_customer_service_model_setting(row))


@router.get("/runs/{run_id}/customer-service/conversations", response_model=ShopeeCustomerServiceConversationListResponse)
def list_shopee_customer_service_conversations(
    run_id: int,
    scenario: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeCustomerServiceConversationListResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_customer_service_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    cache_key = _customer_service_list_cache_key(run_id=run.id, user_id=user_id, status_filter=status_filter, page=page, page_size=page_size)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeCustomerServiceConversationListResponse.model_validate(cached_payload)
    query = db.query(ShopeeCustomerServiceConversation).options(selectinload(ShopeeCustomerServiceConversation.messages), selectinload(ShopeeCustomerServiceConversation.scenario)).filter(ShopeeCustomerServiceConversation.run_id == run.id, ShopeeCustomerServiceConversation.user_id == user_id)
    if scenario:
        query = query.filter(ShopeeCustomerServiceConversation.scenario_code == scenario)
    if status_filter:
        if status_filter == "open":
            query = query.filter(ShopeeCustomerServiceConversation.status.in_(CUSTOMER_SERVICE_OPEN_STATUSES))
        else:
            query = query.filter(ShopeeCustomerServiceConversation.status == status_filter)
    total = query.count()
    rows = query.order_by(ShopeeCustomerServiceConversation.updated_at.desc(), ShopeeCustomerServiceConversation.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    setting = _get_customer_service_model_setting(db, run_id=run.id, user_id=user_id)
    ready, message = _customer_service_model_ready(setting)
    payload = ShopeeCustomerServiceConversationListResponse(items=[_serialize_customer_service_summary(row) for row in rows], total=total, page=page, page_size=page_size, model_ready=ready, model_message=message)
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_SHOPEE_CUSTOMER_SERVICE_LIST_SEC)
    return payload


@router.get("/runs/{run_id}/customer-service/conversations/{conversation_id}", response_model=ShopeeCustomerServiceConversationDetailResponse)
def get_shopee_customer_service_conversation(
    run_id: int,
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeCustomerServiceConversationDetailResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_customer_service_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    cache_key = _customer_service_detail_cache_key(conversation_id=conversation_id)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeCustomerServiceConversationDetailResponse.model_validate(cached_payload)
    row = db.query(ShopeeCustomerServiceConversation).options(selectinload(ShopeeCustomerServiceConversation.messages), selectinload(ShopeeCustomerServiceConversation.scenario)).filter(ShopeeCustomerServiceConversation.id == conversation_id, ShopeeCustomerServiceConversation.run_id == run.id, ShopeeCustomerServiceConversation.user_id == user_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="客服会话不存在")
    payload = _serialize_customer_service_detail(db, run=run, user_id=user_id, row=row)
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_SHOPEE_CUSTOMER_SERVICE_DETAIL_SEC)
    return payload


@router.post("/runs/{run_id}/customer-service/conversations/{conversation_id}/messages", response_model=ShopeeCustomerServiceConversationDetailResponse)
def send_shopee_customer_service_message(
    run_id: int,
    conversation_id: int,
    payload: ShopeeCustomerServiceSendMessageRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeCustomerServiceConversationDetailResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_customer_service_rate_limit(user_id=user_id)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    row = db.query(ShopeeCustomerServiceConversation).options(selectinload(ShopeeCustomerServiceConversation.messages), selectinload(ShopeeCustomerServiceConversation.scenario)).filter(ShopeeCustomerServiceConversation.id == conversation_id, ShopeeCustomerServiceConversation.run_id == run.id, ShopeeCustomerServiceConversation.user_id == user_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="客服会话不存在")
    if row.status not in CUSTOMER_SERVICE_OPEN_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前会话已结束，不能继续回复")
    messages = sorted(row.messages, key=lambda item: (item.sent_game_at, item.id))
    if len(messages) >= CUSTOMER_SERVICE_MAX_MESSAGES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前会话已达到最多 10 条消息，请结束会话或查看评分")
    setting = _get_customer_service_model_setting(db, run_id=run.id, user_id=user_id)
    ready, message = _customer_service_model_ready(setting)
    if not ready or setting is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message or "客服模型未配置")
    game_now = _resolve_game_tick(db, run.id, user_id)
    seller_message = ShopeeCustomerServiceMessage(conversation_id=row.id, run_id=run.id, user_id=user_id, sender_type="seller", message_type="text", content=payload.content.strip(), sent_game_at=game_now)
    db.add(seller_message)
    db.flush()
    row.status = "waiting_seller"
    messages.append(seller_message)
    if len(messages) < CUSTOMER_SERVICE_MAX_MESSAGES:
        buyer_content = _build_buyer_message(db, setting=setting, conversation=row, messages=messages)
        db.add(ShopeeCustomerServiceMessage(conversation_id=row.id, run_id=run.id, user_id=user_id, sender_type="buyer", message_type="text", content=buyer_content, sent_game_at=game_now))
        row.status = "open"
    db.commit()
    _invalidate_customer_service_cache(run_id=run.id, user_id=user_id, conversation_id=row.id)
    row = db.query(ShopeeCustomerServiceConversation).options(selectinload(ShopeeCustomerServiceConversation.messages), selectinload(ShopeeCustomerServiceConversation.scenario)).filter(ShopeeCustomerServiceConversation.id == row.id).first()
    return _serialize_customer_service_detail(db, run=run, user_id=user_id, row=row)


@router.post("/runs/{run_id}/customer-service/conversations/{conversation_id}/resolve", response_model=ShopeeCustomerServiceResolveResponse)
def resolve_shopee_customer_service_conversation(
    run_id: int,
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeCustomerServiceResolveResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_customer_service_rate_limit(user_id=user_id)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    row = db.query(ShopeeCustomerServiceConversation).options(selectinload(ShopeeCustomerServiceConversation.messages), selectinload(ShopeeCustomerServiceConversation.scenario)).filter(ShopeeCustomerServiceConversation.id == conversation_id, ShopeeCustomerServiceConversation.run_id == run.id, ShopeeCustomerServiceConversation.user_id == user_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="客服会话不存在")
    if row.status not in CUSTOMER_SERVICE_OPEN_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前会话已结束")
    setting = _get_customer_service_model_setting(db, run_id=run.id, user_id=user_id)
    messages = sorted(row.messages, key=lambda item: (item.sent_game_at, item.id))
    score, level, detail = _score_customer_service_conversation(db, setting=setting, conversation=row, messages=messages)
    row.status = "resolved"
    row.closed_game_at = _resolve_game_tick(db, run.id, user_id)
    row.satisfaction_score = score
    row.satisfaction_level = level
    row.score_detail_json = json.dumps(detail, ensure_ascii=False)
    db.commit()
    _invalidate_customer_service_cache(run_id=run.id, user_id=user_id, conversation_id=row.id)
    row = db.query(ShopeeCustomerServiceConversation).options(selectinload(ShopeeCustomerServiceConversation.messages), selectinload(ShopeeCustomerServiceConversation.scenario)).filter(ShopeeCustomerServiceConversation.id == row.id).first()
    return ShopeeCustomerServiceResolveResponse(conversation=_serialize_customer_service_detail(db, run=run, user_id=user_id, row=row))


@router.get("/runs/{run_id}/customer-service/auto-replies", response_model=ShopeeAutoReplySettingsResponse)
def get_shopee_auto_replies(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeAutoReplySettingsResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_auto_reply_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    cache_key = _shopee_auto_reply_settings_cache_key(run_id=run.id, user_id=user_id)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeAutoReplySettingsResponse.model_validate(cached_payload)
    payload = _build_auto_reply_settings_response(db, run=run, user_id=user_id)
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_SHOPEE_AUTO_REPLY_SETTINGS_SEC)
    return payload


@router.put("/runs/{run_id}/customer-service/auto-replies/{reply_type}", response_model=ShopeeAutoReplyUpdateResponse)
def update_shopee_auto_reply(
    run_id: int,
    reply_type: str,
    payload: ShopeeAutoReplyUpdateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeAutoReplyUpdateResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_auto_reply_rate_limit(user_id=user_id, update=True)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    if reply_type not in AUTO_REPLY_TYPES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="自动回复类型不存在")

    settings = _ensure_auto_reply_settings(db, run=run, user_id=user_id)
    row = settings[reply_type]
    next_enabled, next_message, next_start_time, next_end_time = _validate_auto_reply_update(reply_type, payload, row)
    row.enabled = next_enabled
    row.message = next_message
    row.work_time_enabled = reply_type == "off_work"
    row.work_start_time = next_start_time
    row.work_end_time = next_end_time
    row.timezone = "game_time"
    row.trigger_interval_minutes = 1440
    row.trigger_once_per_game_day = reply_type == "off_work"
    db.commit()
    db.refresh(row)
    _invalidate_shopee_auto_reply_cache(run_id=run.id, user_id=user_id)
    return ShopeeAutoReplyUpdateResponse(setting=_serialize_auto_reply_setting(row, reply_type=reply_type))


@router.get("/runs/{run_id}/customer-service/quick-replies", response_model=ShopeeQuickReplyListResponse)
def get_shopee_quick_replies(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeQuickReplyListResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_quick_reply_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    cache_key = _shopee_quick_reply_list_cache_key(run_id=run.id, user_id=user_id)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeQuickReplyListResponse.model_validate(cached_payload)
    payload = _build_quick_reply_list_response(db, run=run, user_id=user_id)
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_SHOPEE_QUICK_REPLY_LIST_SEC)
    return payload


@router.put("/runs/{run_id}/customer-service/quick-replies/preference", response_model=ShopeeQuickReplyPreferenceUpdateResponse)
def update_shopee_quick_reply_preference(
    run_id: int,
    payload: ShopeeQuickReplyPreferenceUpdateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeQuickReplyPreferenceUpdateResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_quick_reply_rate_limit(user_id=user_id, update=True)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    preference, _groups = _ensure_quick_reply_data(db, run=run, user_id=user_id)
    if preference is None:
        preference = ShopeeQuickReplyPreference(run_id=run.id, user_id=user_id, auto_hint_enabled=payload.auto_hint_enabled)
        db.add(preference)
    else:
        preference.auto_hint_enabled = payload.auto_hint_enabled
    db.commit()
    db.refresh(preference)
    _invalidate_shopee_quick_reply_cache(run_id=run.id, user_id=user_id)
    return ShopeeQuickReplyPreferenceUpdateResponse(preference=ShopeeQuickReplyPreferenceResponse(auto_hint_enabled=bool(preference.auto_hint_enabled)))


@router.post("/runs/{run_id}/customer-service/quick-reply-groups", response_model=ShopeeQuickReplyGroupCreateResponse, status_code=status.HTTP_201_CREATED)
def create_shopee_quick_reply_group(
    run_id: int,
    payload: ShopeeQuickReplyCreateGroupRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeQuickReplyGroupCreateResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_quick_reply_rate_limit(user_id=user_id, update=True)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    _ensure_quick_reply_data(db, run=run, user_id=user_id)
    group_name, messages = _validate_quick_reply_create_payload(db, run_id=run.id, user_id=user_id, payload=payload)
    max_sort = db.query(func.max(ShopeeQuickReplyGroup.sort_order)).filter(ShopeeQuickReplyGroup.run_id == run.id, ShopeeQuickReplyGroup.user_id == user_id).scalar() or 0
    group = ShopeeQuickReplyGroup(
        run_id=run.id,
        user_id=user_id,
        group_name=group_name,
        enabled=payload.enabled,
        sort_order=int(max_sort) + 1,
        message_count=len(messages),
    )
    db.add(group)
    db.flush()
    for index, (message, tags) in enumerate(messages, start=1):
        db.add(
            ShopeeQuickReplyMessage(
                group_id=group.id,
                run_id=run.id,
                user_id=user_id,
                message=message,
                tags_json=json.dumps(tags, ensure_ascii=False),
                sort_order=index,
            )
        )
    db.commit()
    db.refresh(group)
    group = (
        db.query(ShopeeQuickReplyGroup)
        .options(selectinload(ShopeeQuickReplyGroup.messages))
        .filter(ShopeeQuickReplyGroup.id == group.id, ShopeeQuickReplyGroup.run_id == run.id, ShopeeQuickReplyGroup.user_id == user_id)
        .first()
    )
    _invalidate_shopee_quick_reply_cache(run_id=run.id, user_id=user_id)
    return ShopeeQuickReplyGroupCreateResponse(group=_serialize_quick_reply_group(group))


@router.put("/runs/{run_id}/customer-service/quick-reply-groups/reorder", response_model=ShopeeQuickReplyListResponse)
def reorder_shopee_quick_reply_groups(
    run_id: int,
    payload: ShopeeQuickReplyGroupReorderRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeQuickReplyListResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_quick_reply_rate_limit(user_id=user_id, update=True)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    groups = (
        db.query(ShopeeQuickReplyGroup)
        .filter(ShopeeQuickReplyGroup.run_id == run.id, ShopeeQuickReplyGroup.user_id == user_id)
        .all()
    )
    existing_ids = {group.id for group in groups}
    requested_ids = payload.group_ids
    if len(requested_ids) != len(existing_ids) or set(requested_ids) != existing_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="排序分组列表与当前快捷回复分组不一致")
    for index, group_id in enumerate(requested_ids, start=1):
        for group in groups:
            if group.id == group_id:
                group.sort_order = index
                break
    db.commit()
    _invalidate_shopee_quick_reply_cache(run_id=run.id, user_id=user_id)
    return _build_quick_reply_list_response(db, run=run, user_id=user_id)


@router.put("/runs/{run_id}/customer-service/quick-reply-groups/{group_id}", response_model=ShopeeQuickReplyGroupCreateResponse)
def update_shopee_quick_reply_group(
    run_id: int,
    group_id: int,
    payload: ShopeeQuickReplyUpdateGroupRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeQuickReplyGroupCreateResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_quick_reply_rate_limit(user_id=user_id, update=True)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    group = (
        db.query(ShopeeQuickReplyGroup)
        .options(selectinload(ShopeeQuickReplyGroup.messages))
        .filter(ShopeeQuickReplyGroup.id == group_id, ShopeeQuickReplyGroup.run_id == run.id, ShopeeQuickReplyGroup.user_id == user_id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="快捷回复分组不存在")
    group_name, messages = _validate_quick_reply_payload(payload)
    group.group_name = group_name
    group.enabled = payload.enabled
    group.message_count = len(messages)
    for message in list(group.messages):
        db.delete(message)
    db.flush()
    for index, (message, tags) in enumerate(messages, start=1):
        db.add(
            ShopeeQuickReplyMessage(
                group_id=group.id,
                run_id=run.id,
                user_id=user_id,
                message=message,
                tags_json=json.dumps(tags, ensure_ascii=False),
                sort_order=index,
            )
        )
    db.commit()
    group = (
        db.query(ShopeeQuickReplyGroup)
        .options(selectinload(ShopeeQuickReplyGroup.messages))
        .filter(ShopeeQuickReplyGroup.id == group_id, ShopeeQuickReplyGroup.run_id == run.id, ShopeeQuickReplyGroup.user_id == user_id)
        .first()
    )
    _invalidate_shopee_quick_reply_cache(run_id=run.id, user_id=user_id)
    return ShopeeQuickReplyGroupCreateResponse(group=_serialize_quick_reply_group(group))


@router.delete("/runs/{run_id}/customer-service/quick-reply-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shopee_quick_reply_group(
    run_id: int,
    group_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> None:
    user_id = int(current_user["id"])
    _enforce_shopee_quick_reply_rate_limit(user_id=user_id, update=True)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    group = (
        db.query(ShopeeQuickReplyGroup)
        .filter(ShopeeQuickReplyGroup.id == group_id, ShopeeQuickReplyGroup.run_id == run.id, ShopeeQuickReplyGroup.user_id == user_id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="快捷回复分组不存在")
    db.delete(group)
    db.commit()
    remaining_groups = (
        db.query(ShopeeQuickReplyGroup)
        .filter(ShopeeQuickReplyGroup.run_id == run.id, ShopeeQuickReplyGroup.user_id == user_id)
        .order_by(ShopeeQuickReplyGroup.sort_order.asc(), ShopeeQuickReplyGroup.id.asc())
        .all()
    )
    for index, item in enumerate(remaining_groups, start=1):
        item.sort_order = index
    db.commit()
    _invalidate_shopee_quick_reply_cache(run_id=run.id, user_id=user_id)
    return None


@router.patch("/runs/{run_id}/customer-service/quick-reply-groups/{group_id}/enabled", response_model=ShopeeQuickReplyGroupCreateResponse)
def update_shopee_quick_reply_group_enabled(
    run_id: int,
    group_id: int,
    payload: ShopeeQuickReplyGroupEnabledRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeQuickReplyGroupCreateResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_quick_reply_rate_limit(user_id=user_id, update=True)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    group = (
        db.query(ShopeeQuickReplyGroup)
        .options(selectinload(ShopeeQuickReplyGroup.messages))
        .filter(ShopeeQuickReplyGroup.id == group_id, ShopeeQuickReplyGroup.run_id == run.id, ShopeeQuickReplyGroup.user_id == user_id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="快捷回复分组不存在")
    group.enabled = payload.enabled
    db.commit()
    db.refresh(group)
    _invalidate_shopee_quick_reply_cache(run_id=run.id, user_id=user_id)
    return ShopeeQuickReplyGroupCreateResponse(group=_serialize_quick_reply_group(group))


@router.patch("/runs/{run_id}/customer-service/quick-reply-groups/{group_id}/sort", response_model=ShopeeQuickReplyListResponse)
def sort_shopee_quick_reply_group(
    run_id: int,
    group_id: int,
    payload: ShopeeQuickReplyGroupSortRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeQuickReplyListResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_quick_reply_rate_limit(user_id=user_id, update=True)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    groups = (
        db.query(ShopeeQuickReplyGroup)
        .options(selectinload(ShopeeQuickReplyGroup.messages))
        .filter(ShopeeQuickReplyGroup.run_id == run.id, ShopeeQuickReplyGroup.user_id == user_id)
        .order_by(ShopeeQuickReplyGroup.sort_order.asc(), ShopeeQuickReplyGroup.id.asc())
        .all()
    )
    current_index = next((index for index, item in enumerate(groups) if item.id == group_id), -1)
    if current_index < 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="快捷回复分组不存在")
    direction = payload.direction.strip().lower()
    if direction not in {"up", "down"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="排序方向仅支持 up 或 down")
    target_index = current_index - 1 if direction == "up" else current_index + 1
    if target_index < 0 or target_index >= len(groups):
        return _build_quick_reply_list_response(db, run=run, user_id=user_id)
    groups[current_index], groups[target_index] = groups[target_index], groups[current_index]
    for index, item in enumerate(groups, start=1):
        item.sort_order = index
    db.commit()
    _invalidate_shopee_quick_reply_cache(run_id=run.id, user_id=user_id)
    return _build_quick_reply_list_response(db, run=run, user_id=user_id)


@router.get("/runs/{run_id}/marketing/shipping-fee-promotion/create/bootstrap", response_model=ShopeeShippingFeePromotionCreateBootstrapResponse)
def get_shopee_shipping_fee_promotion_create_bootstrap(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeShippingFeePromotionCreateBootstrapResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_shipping_fee_promotion_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    cache_key = _shopee_shipping_fee_promotion_bootstrap_cache_key(run_id=run.id, user_id=user_id)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeShippingFeePromotionCreateBootstrapResponse.model_validate(cached_payload)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    payload = _build_shipping_fee_promotion_create_bootstrap_payload(
        run=run,
        user_id=user_id,
        current_tick=current_tick,
        read_only=run.status == "finished",
    )
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_SHOPEE_SHIPPING_FEE_PROMOTION_BOOTSTRAP_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/shipping-fee-promotions", response_model=ShopeeShippingFeePromotionListResponse)
def list_shopee_shipping_fee_promotions(
    run_id: int,
    status_value: str = Query(default="all", alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeShippingFeePromotionListResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_shipping_fee_promotion_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    safe_status = (status_value or "all").strip().lower()
    if safe_status not in {"all", "ongoing", "upcoming", "ended"}:
        safe_status = "all"
    cache_key = _shopee_shipping_fee_promotion_list_cache_key(run_id=run.id, user_id=user_id, status_value=safe_status, page=page, page_size=page_size)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeShippingFeePromotionListResponse.model_validate(cached_payload)
    payload = _build_shipping_fee_promotion_list_response(db=db, run=run, user_id=user_id, status_value=safe_status, page=page, page_size=page_size)
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_SHOPEE_SHIPPING_FEE_PROMOTION_LIST_SEC)
    return payload


@router.post("/runs/{run_id}/marketing/shipping-fee-promotions", response_model=ShopeeShippingFeePromotionCreateResponse, status_code=status.HTTP_201_CREATED)
def create_shopee_shipping_fee_promotion(
    run_id: int,
    payload: ShopeeShippingFeePromotionCreateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeShippingFeePromotionCreateResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_shipping_fee_promotion_create_rate_limit(user_id=user_id)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    start_at = _parse_discount_game_datetime(payload.start_at, run=run) if payload.start_at else current_tick
    end_at = _parse_discount_game_datetime(payload.end_at, run=run) if payload.end_at else None
    sorted_tiers = _validate_shipping_fee_promotion_create_payload(payload=payload, start_at=start_at, end_at=end_at)
    campaign = ShopeeShippingFeePromotionCampaign(
        run_id=run.id,
        user_id=user_id,
        promotion_name=payload.promotion_name.strip(),
        period_type=payload.period_type,
        start_at=start_at or current_tick,
        end_at=end_at if payload.period_type == "selected" else None,
        budget_type=payload.budget_type,
        budget_limit=payload.budget_limit if payload.budget_type == "selected" else None,
        budget_used=0,
    )
    campaign.status = _resolve_shipping_fee_promotion_status(campaign, current_tick=current_tick)
    campaign.channels = [
        ShopeeShippingFeePromotionChannel(
            run_id=run.id,
            user_id=user_id,
            channel_key=channel_key,
            channel_label=SHOPEE_SHIPPING_FEE_PROMOTION_CHANNELS[channel_key],
        )
        for channel_key in payload.channels
    ]
    campaign.tiers = [
        ShopeeShippingFeePromotionTier(
            run_id=run.id,
            user_id=user_id,
            tier_index=index,
            min_spend_amount=tier.min_spend_amount,
            fee_type=tier.fee_type,
            fixed_fee_amount=tier.fixed_fee_amount if tier.fee_type == "fixed_fee" else None,
        )
        for index, tier in enumerate(sorted_tiers, start=1)
    ]
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    _invalidate_shopee_shipping_fee_promotion_cache(run_id=run.id, user_id=user_id)
    return ShopeeShippingFeePromotionCreateResponse(id=campaign.id, status=campaign.status)


@router.get("/runs/{run_id}/marketing/vouchers", response_model=ShopeeVoucherListResponse)
def list_shopee_vouchers(
    run_id: int,
    status_value: str = Query(default="all", alias="status"),
    keyword: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeVoucherListResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    safe_status = (status_value or "all").strip().lower()
    if safe_status not in {"all", "ongoing", "upcoming", "ended", "sold_out", "stopped"}:
        safe_status = "all"
    cache_key = _shopee_voucher_list_cache_key(run_id=run.id, user_id=user_id, status_value=safe_status, keyword=keyword, page=page, page_size=page_size)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeVoucherListResponse.model_validate(cached_payload)
    payload = _build_shop_voucher_list_response(db=db, run=run, user_id=user_id, status_value=safe_status, keyword=keyword, page=page, page_size=page_size)
    cache_set_json(cache_key, payload.model_dump(mode="json"), 60)
    return payload


@router.get("/runs/{run_id}/marketing/vouchers/{voucher_type}/{campaign_id}/orders", response_model=ShopeeVoucherOrdersResponse)
def get_shopee_voucher_orders(
    run_id: int,
    voucher_type: str,
    campaign_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeVoucherOrdersResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    safe_voucher_type = (voucher_type or "").strip().lower()
    cache_key = _shopee_voucher_orders_cache_key(
        run_id=run.id,
        user_id=user_id,
        voucher_type=safe_voucher_type,
        campaign_id=campaign_id,
        page=page,
        page_size=page_size,
    )
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeVoucherOrdersResponse.model_validate(cached_payload)
    payload = _build_voucher_orders_response(
        db=db,
        run=run,
        user_id=user_id,
        voucher_type=safe_voucher_type,
        campaign_id=campaign_id,
        page=page,
        page_size=page_size,
    )
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_ORDERS_LIST_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/vouchers/detail/{voucher_type}/{campaign_id}", response_model=ShopeeVoucherDetailResponse)
def get_shopee_voucher_detail(
    run_id: int,
    voucher_type: str,
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeVoucherDetailResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    safe_voucher_type = (voucher_type or "").strip().lower()
    current_tick = _resolve_game_tick(db, run.id, user_id)
    status_labels = {
        "upcoming": "即将开始",
        "ongoing": "进行中",
        "sold_out": "已抢完",
        "ended": "已结束",
        "stopped": "已停止",
    }

    campaign_config = _voucher_campaign_config()
    if safe_voucher_type not in campaign_config:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="代金券类型不支持")

    model, items_relation, _type_label = campaign_config[safe_voucher_type]
    query = db.query(model)
    if items_relation is not None:
        query = query.options(selectinload(items_relation))
    row = query.filter(model.id == campaign_id, model.run_id == run.id, model.user_id == user_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="代金券不存在")

    if safe_voucher_type == "follow_voucher":
        status_value = _resolve_follow_voucher_status(
            claim_start_at=row.claim_start_at,
            claim_end_at=row.claim_end_at,
            current_tick=current_tick,
            claimed_count=row.claimed_count,
            usage_limit=row.usage_limit,
        )
    else:
        status_value = _resolve_shop_voucher_status(
            start_at=row.start_at,
            end_at=row.end_at,
            current_tick=current_tick,
            used_count=row.used_count,
            usage_limit=row.usage_limit,
        )
    return _build_voucher_detail_response(
        row=row,
        run=run,
        user_id=user_id,
        voucher_type=safe_voucher_type,
        status_value=status_value,
        status_label=status_labels.get(status_value, status_value),
        current_tick=current_tick,
    )


@router.get("/runs/{run_id}/marketing/vouchers/create/bootstrap", response_model=ShopeeVoucherCreateBootstrapResponse)
def get_shopee_voucher_create_bootstrap(
    run_id: int,
    voucher_type: str = Query(default="shop_voucher"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeVoucherCreateBootstrapResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_voucher_create_bootstrap_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    safe_voucher_type = (voucher_type or "shop_voucher").strip().lower()
    if safe_voucher_type != "shop_voucher":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前仅支持店铺代金券")
    cache_key = _shopee_voucher_create_bootstrap_cache_key(run_id=run.id, user_id=user_id, voucher_type=safe_voucher_type)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeVoucherCreateBootstrapResponse.model_validate(cached_payload)

    current_tick = _resolve_game_tick(db, run.id, user_id)
    payload = _build_voucher_create_bootstrap_payload(
        run=run,
        user_id=user_id,
        current_tick=current_tick,
        read_only=run.status == "finished",
        voucher_type=safe_voucher_type,
    )
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_SHOPEE_VOUCHER_CREATE_BOOTSTRAP_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/vouchers/follow-create/bootstrap", response_model=ShopeeFollowVoucherCreateBootstrapResponse)
def get_shopee_follow_voucher_create_bootstrap(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeFollowVoucherCreateBootstrapResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_voucher_create_bootstrap_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    cache_key = _shopee_voucher_create_bootstrap_cache_key(run_id=run.id, user_id=user_id, voucher_type="follow_voucher")
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeFollowVoucherCreateBootstrapResponse.model_validate(cached_payload)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    payload = _build_follow_voucher_create_bootstrap_payload(
        run=run,
        user_id=user_id,
        current_tick=current_tick,
        read_only=run.status == "finished",
    )
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_SHOPEE_VOUCHER_CREATE_BOOTSTRAP_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/vouchers/product-create/bootstrap", response_model=ShopeeVoucherCreateBootstrapResponse)
def get_shopee_product_voucher_create_bootstrap(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeVoucherCreateBootstrapResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_voucher_create_bootstrap_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    cache_key = _shopee_voucher_create_bootstrap_cache_key(run_id=run.id, user_id=user_id, voucher_type="product_voucher")
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeVoucherCreateBootstrapResponse.model_validate(cached_payload)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    payload = _build_voucher_create_bootstrap_payload(
        run=run,
        user_id=user_id,
        current_tick=current_tick,
        read_only=run.status == "finished",
        voucher_type="product_voucher",
    )
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_SHOPEE_VOUCHER_CREATE_BOOTSTRAP_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/vouchers/product-create/eligible-products", response_model=ShopeeProductVoucherEligibleProductsResponse)
def list_shopee_product_voucher_eligible_products(
    run_id: int,
    keyword: str = Query(default=""),
    search_field: str = Query(default="product_name"),
    category_key: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeProductVoucherEligibleProductsResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    safe_search_field = (search_field or "product_name").strip().lower()
    if safe_search_field not in {"product_name", "product_id"}:
        safe_search_field = "product_name"
    safe_category_key = (category_key or "all").strip() or "all"
    cache_key = _shopee_voucher_eligible_products_cache_key(
        run_id=run.id,
        user_id=user_id,
        voucher_type="product_voucher",
        search_field=safe_search_field,
        category_key=safe_category_key,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeProductVoucherEligibleProductsResponse.model_validate(cached_payload)
    payload = _build_product_voucher_eligible_products_response(
        db=db,
        run=run,
        user_id=user_id,
        search_field=safe_search_field,
        category_key=safe_category_key,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_DISCOUNT_ELIGIBLE_PRODUCTS_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/vouchers/live-create/bootstrap", response_model=ShopeeVoucherCreateBootstrapResponse)
def get_shopee_live_voucher_create_bootstrap(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeVoucherCreateBootstrapResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_voucher_create_bootstrap_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    cache_key = _shopee_voucher_create_bootstrap_cache_key(run_id=run.id, user_id=user_id, voucher_type="live_voucher")
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeVoucherCreateBootstrapResponse.model_validate(cached_payload)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    payload = _build_voucher_create_bootstrap_payload(
        run=run,
        user_id=user_id,
        current_tick=current_tick,
        read_only=run.status == "finished",
        voucher_type="live_voucher",
    )
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_SHOPEE_VOUCHER_CREATE_BOOTSTRAP_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/vouchers/live-create/eligible-products", response_model=ShopeeProductVoucherEligibleProductsResponse)
def list_shopee_live_voucher_eligible_products(
    run_id: int,
    keyword: str = Query(default=""),
    search_field: str = Query(default="product_name"),
    category_key: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeProductVoucherEligibleProductsResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    return _list_scene_voucher_eligible_products(
        db=db,
        run=run,
        user_id=user_id,
        voucher_type="live_voucher",
        keyword=keyword,
        search_field=search_field,
        category_key=category_key,
        page=page,
        page_size=page_size,
    )


@router.get("/runs/{run_id}/marketing/vouchers/video-create/bootstrap", response_model=ShopeeVoucherCreateBootstrapResponse)
def get_shopee_video_voucher_create_bootstrap(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeVoucherCreateBootstrapResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_voucher_create_bootstrap_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    cache_key = _shopee_voucher_create_bootstrap_cache_key(run_id=run.id, user_id=user_id, voucher_type="video_voucher")
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeVoucherCreateBootstrapResponse.model_validate(cached_payload)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    payload = _build_voucher_create_bootstrap_payload(
        run=run,
        user_id=user_id,
        current_tick=current_tick,
        read_only=run.status == "finished",
        voucher_type="video_voucher",
    )
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_SHOPEE_VOUCHER_CREATE_BOOTSTRAP_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/vouchers/video-create/eligible-products", response_model=ShopeeProductVoucherEligibleProductsResponse)
def list_shopee_video_voucher_eligible_products(
    run_id: int,
    keyword: str = Query(default=""),
    search_field: str = Query(default="product_name"),
    category_key: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeProductVoucherEligibleProductsResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    return _list_scene_voucher_eligible_products(
        db=db,
        run=run,
        user_id=user_id,
        voucher_type="video_voucher",
        keyword=keyword,
        search_field=search_field,
        category_key=category_key,
        page=page,
        page_size=page_size,
    )


def _list_scene_voucher_eligible_products(
    *,
    db: Session,
    run: GameRun,
    user_id: int,
    voucher_type: str,
    keyword: str,
    search_field: str,
    category_key: str,
    page: int,
    page_size: int,
) -> ShopeeProductVoucherEligibleProductsResponse:
    safe_search_field = (search_field or "product_name").strip().lower()
    if safe_search_field not in {"product_name", "product_id"}:
        safe_search_field = "product_name"
    safe_category_key = (category_key or "all").strip() or "all"
    cache_key = _shopee_voucher_eligible_products_cache_key(
        run_id=run.id,
        user_id=user_id,
        voucher_type=voucher_type,
        search_field=safe_search_field,
        category_key=safe_category_key,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeProductVoucherEligibleProductsResponse.model_validate(cached_payload)
    payload = _build_product_voucher_eligible_products_response(
        db=db,
        run=run,
        user_id=user_id,
        search_field=safe_search_field,
        category_key=safe_category_key,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_DISCOUNT_ELIGIBLE_PRODUCTS_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/vouchers/private-create/bootstrap", response_model=ShopeeVoucherCreateBootstrapResponse)
def get_shopee_private_voucher_create_bootstrap(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeVoucherCreateBootstrapResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_voucher_create_bootstrap_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    cache_key = _shopee_voucher_create_bootstrap_cache_key(run_id=run.id, user_id=user_id, voucher_type="private_voucher")
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeVoucherCreateBootstrapResponse.model_validate(cached_payload)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    payload = _build_voucher_create_bootstrap_payload(
        run=run,
        user_id=user_id,
        current_tick=current_tick,
        read_only=run.status == "finished",
        voucher_type="private_voucher",
    )
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_SHOPEE_VOUCHER_CREATE_BOOTSTRAP_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/vouchers/private-create/eligible-products", response_model=ShopeeProductVoucherEligibleProductsResponse)
def list_shopee_private_voucher_eligible_products(
    run_id: int,
    keyword: str = Query(default=""),
    search_field: str = Query(default="product_name"),
    category_key: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeProductVoucherEligibleProductsResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    safe_search_field = (search_field or "product_name").strip().lower()
    if safe_search_field not in {"product_name", "product_id"}:
        safe_search_field = "product_name"
    safe_category_key = (category_key or "all").strip() or "all"
    cache_key = _shopee_voucher_eligible_products_cache_key(
        run_id=run.id,
        user_id=user_id,
        voucher_type="private_voucher",
        search_field=safe_search_field,
        category_key=safe_category_key,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeProductVoucherEligibleProductsResponse.model_validate(cached_payload)
    payload = _build_product_voucher_eligible_products_response(
        db=db,
        run=run,
        user_id=user_id,
        search_field=safe_search_field,
        category_key=safe_category_key,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_DISCOUNT_ELIGIBLE_PRODUCTS_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/vouchers/code/check", response_model=ShopeeVoucherCodeCheckResponse)
def check_shopee_voucher_code(
    run_id: int,
    voucher_type: str = Query(default="shop_voucher"),
    code_suffix: str = Query(default=""),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeVoucherCodeCheckResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_voucher_code_check_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    safe_voucher_type = (voucher_type or "shop_voucher").strip().lower()
    if safe_voucher_type not in {"shop_voucher", "product_voucher", "private_voucher", "live_voucher"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前仅支持店铺代金券、商品代金券、专属代金券和直播代金券")
    try:
        normalized_suffix = _normalize_shop_voucher_code_suffix(code_suffix)
    except HTTPException as exc:
        raw_suffix = (code_suffix or "").strip().upper()
        return ShopeeVoucherCodeCheckResponse(
            code_prefix="HOME",
            code_suffix=raw_suffix,
            voucher_code=f"HOME{raw_suffix}",
            available=False,
            message=str(exc.detail),
        )
    cache_key = _shopee_voucher_code_check_cache_key(run_id=run.id, user_id=user_id, voucher_type=safe_voucher_type, code_suffix=normalized_suffix)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeVoucherCodeCheckResponse.model_validate(cached_payload)
    voucher_code = f"HOME{normalized_suffix}"
    exists = _resolve_voucher_code_exists(db=db, run=run, user_id=user_id, voucher_code=voucher_code)
    response = ShopeeVoucherCodeCheckResponse(
        code_prefix="HOME",
        code_suffix=normalized_suffix,
        voucher_code=voucher_code,
        available=not exists,
        message="代金券代码可用" if not exists else "该代金券代码已存在，请更换后缀",
    )
    cache_set_json(cache_key, response.model_dump(mode="json"), REDIS_CACHE_TTL_SHOPEE_VOUCHER_CODE_CHECK_SEC)
    return response


@router.post("/runs/{run_id}/marketing/vouchers/campaigns", response_model=ShopeeVoucherCampaignCreateResponse, status_code=status.HTTP_201_CREATED)
def create_shopee_voucher_campaign(
    run_id: int,
    payload: ShopeeVoucherCampaignCreateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeVoucherCampaignCreateResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_voucher_create_rate_limit(user_id=user_id)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    start_at = _parse_discount_game_datetime(payload.start_at, run=run)
    end_at = _parse_discount_game_datetime(payload.end_at, run=run)
    display_start_at = _parse_discount_game_datetime(payload.display_start_at, run=run)
    code_suffix = _validate_shop_voucher_create_payload(
        db=db,
        run=run,
        user_id=user_id,
        payload=payload,
        start_at=start_at,
        end_at=end_at,
        display_start_at=display_start_at,
    )
    assert start_at is not None
    assert end_at is not None
    discount_type = (payload.discount_type or "").strip().lower()
    max_discount_type = (payload.max_discount_type or "").strip().lower()
    display_type = (payload.display_type or "").strip().lower()
    current_tick = _resolve_game_tick(db, run.id, user_id)
    campaign_status = _resolve_shop_voucher_status(start_at=start_at, end_at=end_at, current_tick=current_tick, usage_limit=payload.usage_limit)
    campaign = ShopeeShopVoucherCampaign(
        run_id=run.id,
        user_id=user_id,
        voucher_type="shop_voucher",
        voucher_name=payload.voucher_name.strip(),
        voucher_code=f"HOME{code_suffix}",
        code_prefix="HOME",
        code_suffix=code_suffix,
        status=campaign_status,
        start_at=start_at,
        end_at=end_at,
        display_before_start=payload.display_before_start,
        display_start_at=display_start_at if payload.display_before_start else None,
        reward_type="discount",
        discount_type=discount_type,
        discount_amount=payload.discount_amount if discount_type == "fixed_amount" else None,
        discount_percent=payload.discount_percent if discount_type == "percent" else None,
        max_discount_type=max_discount_type if discount_type == "percent" else "set_amount",
        max_discount_amount=payload.max_discount_amount if discount_type == "percent" and max_discount_type == "set_amount" else None,
        min_spend_amount=payload.min_spend_amount,
        usage_limit=payload.usage_limit,
        per_buyer_limit=payload.per_buyer_limit,
        display_type=display_type,
        display_channels=json.dumps(payload.display_channels or [], ensure_ascii=False),
        applicable_scope="all_shop_products",
    )
    try:
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该代金券代码已存在，请更换后缀") from None
    _invalidate_shopee_voucher_cache(run_id=run.id, user_id=user_id, campaign_id=campaign.id)
    return ShopeeVoucherCampaignCreateResponse(campaign_id=campaign.id, voucher_type=campaign.voucher_type, status=campaign.status)


@router.post("/runs/{run_id}/marketing/vouchers/product-campaigns", response_model=ShopeeVoucherCampaignCreateResponse, status_code=status.HTTP_201_CREATED)
def create_shopee_product_voucher_campaign(
    run_id: int,
    payload: ShopeeVoucherCampaignCreateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeVoucherCampaignCreateResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_voucher_create_rate_limit(user_id=user_id)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    payload.voucher_type = "product_voucher"
    start_at = _parse_discount_game_datetime(payload.start_at, run=run)
    end_at = _parse_discount_game_datetime(payload.end_at, run=run)
    display_start_at = _parse_discount_game_datetime(payload.display_start_at, run=run)
    code_suffix = _validate_shop_voucher_create_payload(
        db=db,
        run=run,
        user_id=user_id,
        payload=payload,
        start_at=start_at,
        end_at=end_at,
        display_start_at=display_start_at,
    )
    assert start_at is not None
    assert end_at is not None
    items = _resolve_product_voucher_item_snapshots(db=db, run=run, user_id=user_id, selected_products=payload.selected_products)
    discount_type = (payload.discount_type or "").strip().lower()
    max_discount_type = (payload.max_discount_type or "").strip().lower()
    display_type = (payload.display_type or "").strip().lower()
    current_tick = _resolve_game_tick(db, run.id, user_id)
    campaign_status = _resolve_shop_voucher_status(start_at=start_at, end_at=end_at, current_tick=current_tick, usage_limit=payload.usage_limit)
    campaign = ShopeeProductVoucherCampaign(
        run_id=run.id,
        user_id=user_id,
        voucher_type="product_voucher",
        voucher_name=payload.voucher_name.strip(),
        voucher_code=f"HOME{code_suffix}",
        code_prefix="HOME",
        code_suffix=code_suffix,
        status=campaign_status,
        start_at=start_at,
        end_at=end_at,
        display_before_start=payload.display_before_start,
        display_start_at=display_start_at if payload.display_before_start else None,
        reward_type="discount",
        discount_type=discount_type,
        discount_amount=payload.discount_amount if discount_type == "fixed_amount" else None,
        discount_percent=payload.discount_percent if discount_type == "percent" else None,
        max_discount_type=max_discount_type if discount_type == "percent" else "set_amount",
        max_discount_amount=payload.max_discount_amount if discount_type == "percent" and max_discount_type == "set_amount" else None,
        min_spend_amount=payload.min_spend_amount,
        usage_limit=payload.usage_limit,
        per_buyer_limit=payload.per_buyer_limit,
        display_type=display_type,
        display_channels=json.dumps(payload.display_channels or [], ensure_ascii=False),
        applicable_scope="selected_products",
        selected_product_count=len(items),
    )
    campaign.items = items
    try:
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该代金券代码已存在，请更换后缀") from None
    _invalidate_shopee_voucher_cache(run_id=run.id, user_id=user_id, campaign_id=campaign.id)
    return ShopeeVoucherCampaignCreateResponse(campaign_id=campaign.id, voucher_type=campaign.voucher_type, status=campaign.status)


@router.post("/runs/{run_id}/marketing/vouchers/live-campaigns", response_model=ShopeeVoucherCampaignCreateResponse, status_code=status.HTTP_201_CREATED)
def create_shopee_live_voucher_campaign(
    run_id: int,
    payload: ShopeeVoucherCampaignCreateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeVoucherCampaignCreateResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_voucher_create_rate_limit(user_id=user_id)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    payload.voucher_type = "live_voucher"
    payload.display_type = "live_stream"
    payload.display_channels = ["shopee_live"]
    payload.live_scope = "all_live_sessions"
    start_at = _parse_discount_game_datetime(payload.start_at, run=run)
    end_at = _parse_discount_game_datetime(payload.end_at, run=run)
    display_start_at = _parse_discount_game_datetime(payload.display_start_at, run=run)
    code_suffix = _validate_shop_voucher_create_payload(
        db=db,
        run=run,
        user_id=user_id,
        payload=payload,
        start_at=start_at,
        end_at=end_at,
        display_start_at=display_start_at,
    )
    assert start_at is not None
    assert end_at is not None
    applicable_scope = (payload.applicable_scope or "all_products").strip().lower()
    items = []
    if applicable_scope == "selected_products":
        items = _resolve_live_voucher_item_snapshots(db=db, run=run, user_id=user_id, selected_products=payload.selected_products)
    discount_type = (payload.discount_type or "").strip().lower()
    max_discount_type = (payload.max_discount_type or "").strip().lower()
    current_tick = _resolve_game_tick(db, run.id, user_id)
    campaign_status = _resolve_shop_voucher_status(start_at=start_at, end_at=end_at, current_tick=current_tick, usage_limit=payload.usage_limit)
    campaign = ShopeeLiveVoucherCampaign(
        run_id=run.id,
        user_id=user_id,
        voucher_type="live_voucher",
        voucher_name=payload.voucher_name.strip(),
        voucher_code=f"HOME{code_suffix}",
        code_prefix="HOME",
        code_suffix=code_suffix,
        status=campaign_status,
        start_at=start_at,
        end_at=end_at,
        display_before_start=payload.display_before_start,
        display_start_at=display_start_at if payload.display_before_start else None,
        reward_type="discount",
        discount_type=discount_type,
        discount_amount=payload.discount_amount if discount_type == "fixed_amount" else None,
        discount_percent=payload.discount_percent if discount_type == "percent" else None,
        max_discount_type=max_discount_type if discount_type == "percent" else "set_amount",
        max_discount_amount=payload.max_discount_amount if discount_type == "percent" and max_discount_type == "set_amount" else None,
        min_spend_amount=payload.min_spend_amount,
        usage_limit=payload.usage_limit,
        per_buyer_limit=payload.per_buyer_limit,
        display_type="live_stream",
        display_channels=json.dumps(["shopee_live"], ensure_ascii=False),
        applicable_scope=applicable_scope,
        selected_product_count=len(items),
        live_scope="all_live_sessions",
    )
    campaign.items = items
    try:
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该代金券代码已存在，请更换后缀") from None
    _invalidate_shopee_voucher_cache(run_id=run.id, user_id=user_id, campaign_id=campaign.id)
    return ShopeeVoucherCampaignCreateResponse(campaign_id=campaign.id, voucher_type=campaign.voucher_type, status=campaign.status)


@router.post("/runs/{run_id}/marketing/vouchers/video-campaigns", response_model=ShopeeVoucherCampaignCreateResponse, status_code=status.HTTP_201_CREATED)
def create_shopee_video_voucher_campaign(
    run_id: int,
    payload: ShopeeVoucherCampaignCreateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeVoucherCampaignCreateResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_voucher_create_rate_limit(user_id=user_id)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    payload.voucher_type = "video_voucher"
    payload.display_type = "video_stream"
    payload.display_channels = ["shopee_video"]
    payload.video_scope = "all_videos"
    start_at = _parse_discount_game_datetime(payload.start_at, run=run)
    end_at = _parse_discount_game_datetime(payload.end_at, run=run)
    display_start_at = _parse_discount_game_datetime(payload.display_start_at, run=run)
    _validate_shop_voucher_create_payload(
        db=db,
        run=run,
        user_id=user_id,
        payload=payload,
        start_at=start_at,
        end_at=end_at,
        display_start_at=display_start_at,
    )
    assert start_at is not None
    assert end_at is not None
    applicable_scope = (payload.applicable_scope or "all_products").strip().lower()
    items = []
    if applicable_scope == "selected_products":
        items = _resolve_video_voucher_item_snapshots(db=db, run=run, user_id=user_id, selected_products=payload.selected_products)
    discount_type = (payload.discount_type or "").strip().lower()
    max_discount_type = (payload.max_discount_type or "").strip().lower()
    current_tick = _resolve_game_tick(db, run.id, user_id)
    campaign_status = _resolve_shop_voucher_status(start_at=start_at, end_at=end_at, current_tick=current_tick, usage_limit=payload.usage_limit)
    voucher_code = f"VIDEO{uuid4().hex[:8].upper()}"
    while _resolve_voucher_code_exists(db=db, run=run, user_id=user_id, voucher_code=voucher_code):
        voucher_code = f"VIDEO{uuid4().hex[:8].upper()}"
    campaign = ShopeeVideoVoucherCampaign(
        run_id=run.id,
        user_id=user_id,
        voucher_type="video_voucher",
        voucher_name=payload.voucher_name.strip(),
        voucher_code=voucher_code,
        status=campaign_status,
        start_at=start_at,
        end_at=end_at,
        display_before_start=payload.display_before_start,
        display_start_at=display_start_at if payload.display_before_start else None,
        reward_type="discount",
        discount_type=discount_type,
        discount_amount=payload.discount_amount if discount_type == "fixed_amount" else None,
        discount_percent=payload.discount_percent if discount_type == "percent" else None,
        max_discount_type=max_discount_type if discount_type == "percent" else "set_amount",
        max_discount_amount=payload.max_discount_amount if discount_type == "percent" and max_discount_type == "set_amount" else None,
        min_spend_amount=payload.min_spend_amount,
        usage_limit=payload.usage_limit,
        per_buyer_limit=payload.per_buyer_limit,
        display_type="video_stream",
        display_channels=json.dumps(["shopee_video"], ensure_ascii=False),
        applicable_scope=applicable_scope,
        selected_product_count=len(items),
        video_scope="all_videos",
    )
    campaign.items = items
    try:
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="视频代金券编号已存在，请重试") from None
    _invalidate_shopee_voucher_cache(run_id=run.id, user_id=user_id, campaign_id=campaign.id)
    return ShopeeVoucherCampaignCreateResponse(campaign_id=campaign.id, voucher_type=campaign.voucher_type, status=campaign.status)


@router.post("/runs/{run_id}/marketing/vouchers/follow-campaigns", response_model=ShopeeVoucherCampaignCreateResponse, status_code=status.HTTP_201_CREATED)
def create_shopee_follow_voucher_campaign(
    run_id: int,
    payload: ShopeeFollowVoucherCampaignCreateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeVoucherCampaignCreateResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_voucher_create_rate_limit(user_id=user_id)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    claim_start_at = _parse_discount_game_datetime(payload.claim_start_at, run=run)
    claim_end_at = _parse_discount_game_datetime(payload.claim_end_at, run=run)
    _validate_follow_voucher_create_payload(payload=payload, claim_start_at=claim_start_at, claim_end_at=claim_end_at)
    assert claim_start_at is not None
    assert claim_end_at is not None
    discount_type = (payload.discount_type or "").strip().lower()
    max_discount_type = (payload.max_discount_type or "").strip().lower()
    current_tick = _resolve_game_tick(db, run.id, user_id)
    campaign_status = _resolve_follow_voucher_status(
        claim_start_at=claim_start_at,
        claim_end_at=claim_end_at,
        current_tick=current_tick,
        usage_limit=payload.usage_limit,
    )
    voucher_code = f"FOLLOW{uuid4().hex[:8].upper()}"
    while _resolve_voucher_code_exists(db=db, run=run, user_id=user_id, voucher_code=voucher_code):
        voucher_code = f"FOLLOW{uuid4().hex[:8].upper()}"
    campaign = ShopeeFollowVoucherCampaign(
        run_id=run.id,
        user_id=user_id,
        voucher_type="follow_voucher",
        voucher_name=payload.voucher_name.strip(),
        voucher_code=voucher_code,
        status=campaign_status,
        claim_start_at=claim_start_at,
        claim_end_at=claim_end_at,
        valid_days_after_claim=7,
        reward_type="discount",
        discount_type=discount_type,
        discount_amount=payload.discount_amount if discount_type == "fixed_amount" else None,
        discount_percent=payload.discount_percent if discount_type == "percent" else None,
        max_discount_type=max_discount_type if discount_type == "percent" else "set_amount",
        max_discount_amount=payload.max_discount_amount if discount_type == "percent" and max_discount_type == "set_amount" else None,
        min_spend_amount=payload.min_spend_amount,
        usage_limit=payload.usage_limit,
        per_buyer_limit=payload.per_buyer_limit,
        trigger_type="follow_shop",
        display_type="follow_reward",
        display_channels=json.dumps(["follow_prize"], ensure_ascii=False),
        applicable_scope="all_products",
    )
    try:
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="关注礼代金券编号已存在，请重试") from None
    _invalidate_shopee_voucher_cache(run_id=run.id, user_id=user_id, campaign_id=campaign.id)
    return ShopeeVoucherCampaignCreateResponse(campaign_id=campaign.id, voucher_type=campaign.voucher_type, status=campaign.status)


@router.post("/runs/{run_id}/marketing/vouchers/private-campaigns", response_model=ShopeeVoucherCampaignCreateResponse, status_code=status.HTTP_201_CREATED)
def create_shopee_private_voucher_campaign(
    run_id: int,
    payload: ShopeeVoucherCampaignCreateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeVoucherCampaignCreateResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_voucher_create_rate_limit(user_id=user_id)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    payload.voucher_type = "private_voucher"
    payload.display_type = "code_only"
    payload.display_before_start = False
    payload.display_start_at = None
    start_at = _parse_discount_game_datetime(payload.start_at, run=run)
    end_at = _parse_discount_game_datetime(payload.end_at, run=run)
    code_suffix = _validate_shop_voucher_create_payload(
        db=db,
        run=run,
        user_id=user_id,
        payload=payload,
        start_at=start_at,
        end_at=end_at,
        display_start_at=None,
    )
    assert start_at is not None
    assert end_at is not None
    applicable_scope = (payload.applicable_scope or "all_products").strip().lower()
    items = []
    if applicable_scope == "selected_products":
        items = _resolve_private_voucher_item_snapshots(db=db, run=run, user_id=user_id, selected_products=payload.selected_products)
    discount_type = (payload.discount_type or "").strip().lower()
    max_discount_type = (payload.max_discount_type or "").strip().lower()
    current_tick = _resolve_game_tick(db, run.id, user_id)
    campaign_status = _resolve_shop_voucher_status(start_at=start_at, end_at=end_at, current_tick=current_tick, usage_limit=payload.usage_limit)
    campaign = ShopeePrivateVoucherCampaign(
        run_id=run.id,
        user_id=user_id,
        voucher_type="private_voucher",
        voucher_name=payload.voucher_name.strip(),
        voucher_code=f"HOME{code_suffix}",
        code_prefix="HOME",
        code_suffix=code_suffix,
        status=campaign_status,
        start_at=start_at,
        end_at=end_at,
        reward_type="discount",
        discount_type=discount_type,
        discount_amount=payload.discount_amount if discount_type == "fixed_amount" else None,
        discount_percent=payload.discount_percent if discount_type == "percent" else None,
        max_discount_type=max_discount_type if discount_type == "percent" else "set_amount",
        max_discount_amount=payload.max_discount_amount if discount_type == "percent" and max_discount_type == "set_amount" else None,
        min_spend_amount=payload.min_spend_amount,
        usage_limit=payload.usage_limit,
        per_buyer_limit=payload.per_buyer_limit,
        display_type="code_only",
        applicable_scope=applicable_scope,
        selected_product_count=len(items),
        audience_scope="private_code",
    )
    campaign.items = items
    try:
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该代金券代码已存在，请更换后缀") from None
    _invalidate_shopee_voucher_cache(run_id=run.id, user_id=user_id, campaign_id=campaign.id)
    return ShopeeVoucherCampaignCreateResponse(campaign_id=campaign.id, voucher_type=campaign.voucher_type, status=campaign.status)


@router.get("/runs/{run_id}/marketing/bundle/create/bootstrap", response_model=ShopeeBundleCreateBootstrapResponse)
def get_shopee_bundle_create_bootstrap(
    run_id: int,
    campaign_type: str = Query(default="bundle"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeBundleCreateBootstrapResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_discount_create_bootstrap_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    if _resolve_discount_type(campaign_type) != "bundle":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前仅支持套餐优惠创建页")
    cache_key = _shopee_discount_create_bootstrap_cache_key(
        run_id=run.id,
        user_id=user_id,
        campaign_type="bundle",
        draft_id=None,
        source_campaign_id=None,
    )
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeBundleCreateBootstrapResponse.model_validate(cached_payload)

    current_tick = _resolve_game_tick(db, run.id, user_id)
    payload = _build_bundle_create_bootstrap_payload(
        db=db,
        run=run,
        user_id=user_id,
        current_tick=current_tick,
        read_only=run.status == "finished",
    )
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_DISCOUNT_CREATE_BOOTSTRAP_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/bundle/eligible-products", response_model=ShopeeDiscountEligibleProductsResponse)
def list_shopee_bundle_eligible_products(
    run_id: int,
    keyword: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDiscountEligibleProductsResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_discount_eligible_products_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    cache_key = _shopee_discount_eligible_products_cache_key(
        run_id=run.id,
        user_id=user_id,
        keyword=f"bundle:{keyword}",
        page=page,
        page_size=page_size,
    )
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeDiscountEligibleProductsResponse.model_validate(cached_payload)

    payload = _build_discount_eligible_products_response(
        db=db,
        run=run,
        user_id=user_id,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_DISCOUNT_ELIGIBLE_PRODUCTS_SEC)
    return payload


@router.post("/runs/{run_id}/marketing/discount/drafts", response_model=ShopeeDiscountDraftDetailResponse)
def upsert_shopee_discount_draft(
    run_id: int,
    payload: ShopeeDiscountDraftUpsertRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDiscountDraftDetailResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_discount_drafts_rate_limit(user_id=user_id)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    safe_campaign_type = _resolve_discount_type(payload.campaign_type)
    if safe_campaign_type != "discount":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前仅支持单品折扣草稿")
    start_at = _parse_discount_game_datetime(payload.start_at, run=run)
    end_at = _parse_discount_game_datetime(payload.end_at, run=run)
    if payload.campaign_name.strip() or start_at or end_at or payload.items:
        _validate_discount_create_payload(
            db=db,
            run=run,
            user_id=user_id,
            campaign_name=payload.campaign_name,
            start_at=start_at,
            end_at=end_at,
            items=payload.items,
        )

    draft = _load_discount_draft_or_404(db, draft_id=payload.draft_id, run_id=run.id, user_id=user_id) if payload.draft_id else None
    if not draft:
        draft = ShopeeDiscountDraft(
            run_id=run.id,
            user_id=user_id,
            campaign_type=safe_campaign_type,
            status="draft",
        )
        db.add(draft)
        db.flush()

    draft.campaign_name = payload.campaign_name.strip()
    draft.start_at = start_at
    draft.end_at = end_at
    draft.campaign_type = safe_campaign_type
    draft.status = "draft"
    draft.items.clear()

    listing_ids = {item.listing_id for item in payload.items}
    variant_ids = {item.variant_id for item in payload.items if item.variant_id}
    listing_map = {row.id: row for row in db.query(ShopeeListing).filter(ShopeeListing.id.in_(listing_ids)).all()} if listing_ids else {}
    variant_map = {row.id: row for row in db.query(ShopeeListingVariant).filter(ShopeeListingVariant.id.in_(variant_ids)).all()} if variant_ids else {}

    for index, item in enumerate(payload.items):
        listing = listing_map.get(item.listing_id)
        if not listing:
            continue
        variant = variant_map.get(item.variant_id) if item.variant_id else None
        computed_percent, computed_final_price = _compute_discount_final_price(
            original_price=float(variant.price if variant else listing.price),
            discount_mode=item.discount_mode,
            discount_percent=item.discount_percent,
            final_price=item.final_price,
        )
        draft.items.append(
            ShopeeDiscountDraftItem(
                listing_id=listing.id,
                variant_id=variant.id if variant else None,
                product_name_snapshot=listing.title,
                image_url_snapshot=(variant.image_url if variant and variant.image_url else listing.cover_url),
                sku_snapshot=(variant.sku if variant else listing.sku_code),
                original_price=float(variant.price if variant else listing.price),
                discount_mode=item.discount_mode if item.discount_mode in {"percent", "final_price"} else "percent",
                discount_percent=computed_percent,
                final_price=computed_final_price,
                activity_stock_limit=item.activity_stock_limit,
                sort_order=index,
            )
        )

    db.commit()
    db.refresh(draft)
    _invalidate_shopee_discount_create_cache(run_id=run.id, user_id=user_id, draft_id=draft.id)
    _invalidate_shopee_discount_cache(run_id=run.id, user_id=user_id)
    response = _build_discount_draft_detail_response(db, draft)
    cache_set_json(
        _shopee_discount_draft_cache_key(run_id=run.id, user_id=user_id, draft_id=draft.id),
        response.model_dump(mode="json"),
        REDIS_CACHE_TTL_DISCOUNT_DRAFT_SEC,
    )
    return response


@router.get("/runs/{run_id}/marketing/discount/drafts/{draft_id}", response_model=ShopeeDiscountDraftDetailResponse)
def get_shopee_discount_draft(
    run_id: int,
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDiscountDraftDetailResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    cache_key = _shopee_discount_draft_cache_key(run_id=run.id, user_id=user_id, draft_id=draft_id)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeDiscountDraftDetailResponse.model_validate(cached_payload)
    draft = _load_discount_draft_or_404(db, draft_id=draft_id, run_id=run.id, user_id=user_id)
    response = _build_discount_draft_detail_response(db, draft)
    cache_set_json(cache_key, response.model_dump(mode="json"), REDIS_CACHE_TTL_DISCOUNT_DRAFT_SEC)
    return response


@router.post("/runs/{run_id}/marketing/discount/campaigns", response_model=ShopeeDiscountCampaignCreateResponse, status_code=status.HTTP_201_CREATED)
def create_shopee_discount_campaign(
    run_id: int,
    payload: ShopeeDiscountCampaignCreateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDiscountCampaignCreateResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_discount_create_rate_limit(user_id=user_id)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    safe_campaign_type = _resolve_discount_type(payload.campaign_type)
    if safe_campaign_type != "discount":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前仅支持创建单品折扣活动")
    start_at = _parse_discount_game_datetime(payload.start_at, run=run)
    end_at = _parse_discount_game_datetime(payload.end_at, run=run)
    _validate_discount_create_payload(
        db=db,
        run=run,
        user_id=user_id,
        campaign_name=payload.campaign_name,
        start_at=start_at,
        end_at=end_at,
        items=payload.items,
    )
    assert start_at is not None
    assert end_at is not None

    current_tick = _resolve_game_tick(db, run.id, user_id)
    campaign_status = "upcoming" if start_at > current_tick else "ongoing"
    campaign = ShopeeDiscountCampaign(
        run_id=run.id,
        user_id=user_id,
        campaign_type=safe_campaign_type,
        campaign_name=payload.campaign_name.strip(),
        campaign_status=campaign_status,
        start_at=start_at,
        end_at=end_at,
        market=(run.market or "MY").strip().upper() or "MY",
        currency="RM",
        rules_json=json.dumps(
            {
                "campaign_scope": "single_product_discount",
                "discount_mode_summary": sorted({item.discount_mode for item in payload.items}) or ["percent"],
                "max_duration_days": 180,
            },
            ensure_ascii=False,
        ),
    )
    db.add(campaign)
    db.flush()

    listing_ids = {item.listing_id for item in payload.items}
    variant_ids = {item.variant_id for item in payload.items if item.variant_id}
    listing_map = {row.id: row for row in db.query(ShopeeListing).filter(ShopeeListing.id.in_(listing_ids)).all()} if listing_ids else {}
    variant_map = {row.id: row for row in db.query(ShopeeListingVariant).filter(ShopeeListingVariant.id.in_(variant_ids)).all()} if variant_ids else {}

    for index, item in enumerate(payload.items):
        listing = listing_map.get(item.listing_id)
        if not listing:
            continue
        variant = variant_map.get(item.variant_id) if item.variant_id else None
        computed_percent, computed_final_price = _compute_discount_final_price(
            original_price=float(variant.price if variant else listing.price),
            discount_mode=item.discount_mode,
            discount_percent=item.discount_percent,
            final_price=item.final_price,
        )
        db.add(
            ShopeeDiscountCampaignItem(
                campaign_id=campaign.id,
                listing_id=listing.id,
                variant_id=variant.id if variant else None,
                product_name_snapshot=listing.title,
                image_url_snapshot=(variant.image_url if variant and variant.image_url else listing.cover_url),
                sku_snapshot=(variant.sku if variant else listing.sku_code),
                original_price=float(variant.price if variant else listing.price),
                discount_type=item.discount_mode if item.discount_mode in {"percent", "final_price"} else "percent",
                discount_value=computed_percent or 0,
                final_price=computed_final_price,
                sort_order=index,
            )
        )

    db.commit()
    db.refresh(campaign)
    _invalidate_shopee_discount_create_cache(run_id=run.id, user_id=user_id)
    _invalidate_shopee_discount_cache(run_id=run.id, user_id=user_id)
    return ShopeeDiscountCampaignCreateResponse(
        campaign_id=campaign.id,
        campaign_name=campaign.campaign_name,
        campaign_status=campaign.campaign_status,
        item_count=len(payload.items),
        start_at=campaign.start_at or start_at,
        end_at=campaign.end_at or end_at,
    )


@router.get("/runs/{run_id}/marketing/add-on/create/bootstrap", response_model=ShopeeAddonCreateBootstrapResponse)
def get_shopee_addon_create_bootstrap(
    run_id: int,
    promotion_type: str = Query(default="add_on"),
    draft_id: int | None = Query(default=None),
    source_campaign_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeAddonCreateBootstrapResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_addon_bootstrap_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    safe_promotion_type = _resolve_addon_promotion_type(promotion_type)
    cache_key = _shopee_addon_bootstrap_cache_key(run_id=run.id, user_id=user_id, promotion_type=safe_promotion_type, draft_id=draft_id, source_campaign_id=source_campaign_id)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeAddonCreateBootstrapResponse.model_validate(cached_payload)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    draft = _load_addon_draft_or_404(db, draft_id=draft_id, run_id=run.id, user_id=user_id) if draft_id else None
    payload = _build_addon_create_bootstrap_payload(db=db, run=run, user_id=user_id, current_tick=current_tick, read_only=run.status == "finished", promotion_type=safe_promotion_type, draft=draft)
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_ADDON_BOOTSTRAP_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/add-on/eligible-main-products", response_model=ShopeeAddonEligibleProductsResponse)
def list_shopee_addon_eligible_main_products(
    run_id: int,
    keyword: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    promotion_type: str = Query(default="add_on"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeAddonEligibleProductsResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_addon_eligible_products_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    safe_promotion_type = _resolve_addon_promotion_type(promotion_type)
    cache_key = _shopee_addon_eligible_products_cache_key(run_id=run.id, user_id=user_id, role="main", promotion_type=safe_promotion_type, keyword=keyword, page=page, page_size=page_size)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeAddonEligibleProductsResponse.model_validate(cached_payload)
    payload = _build_addon_eligible_products_response(db=db, run=run, user_id=user_id, keyword=keyword, page=page, page_size=page_size, promotion_type=safe_promotion_type)
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_ADDON_ELIGIBLE_PRODUCTS_SEC)
    return payload


@router.get("/runs/{run_id}/marketing/add-on/eligible-reward-products", response_model=ShopeeAddonEligibleProductsResponse)
def list_shopee_addon_eligible_reward_products(
    run_id: int,
    keyword: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    promotion_type: str = Query(default="add_on"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeAddonEligibleProductsResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_addon_eligible_products_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    safe_promotion_type = _resolve_addon_promotion_type(promotion_type)
    cache_key = _shopee_addon_eligible_products_cache_key(run_id=run.id, user_id=user_id, role="reward", promotion_type=safe_promotion_type, keyword=keyword, page=page, page_size=page_size)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeAddonEligibleProductsResponse.model_validate(cached_payload)
    payload = _build_addon_eligible_products_response(db=db, run=run, user_id=user_id, keyword=keyword, page=page, page_size=page_size, promotion_type=safe_promotion_type)
    cache_set_json(cache_key, payload.model_dump(mode="json"), REDIS_CACHE_TTL_ADDON_ELIGIBLE_PRODUCTS_SEC)
    return payload


@router.post("/runs/{run_id}/marketing/add-on/drafts", response_model=ShopeeAddonDraftDetailResponse)
def upsert_shopee_addon_draft(
    run_id: int,
    payload: ShopeeAddonDraftUpsertRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeAddonDraftDetailResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_addon_drafts_rate_limit(user_id=user_id)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    safe_promotion_type = _resolve_addon_promotion_type(payload.promotion_type)
    start_at = _parse_discount_game_datetime(payload.start_at, run=run)
    end_at = _parse_discount_game_datetime(payload.end_at, run=run)
    if payload.main_products or payload.reward_products:
        _validate_addon_payload(db=db, run=run, user_id=user_id, promotion_type=safe_promotion_type, campaign_name=payload.campaign_name, start_at=start_at, end_at=end_at, addon_purchase_limit=payload.addon_purchase_limit, gift_min_spend=payload.gift_min_spend, main_products=payload.main_products, reward_products=payload.reward_products)
    elif payload.campaign_name.strip() and len(payload.campaign_name.strip()) > 25:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="活动名称不能超过 25 个字符")
    draft = _load_addon_draft_or_404(db, draft_id=payload.draft_id, run_id=run.id, user_id=user_id) if payload.draft_id else None
    if not draft:
        draft = ShopeeAddonDraft(run_id=run.id, user_id=user_id, promotion_type=safe_promotion_type, draft_status="editing")
        db.add(draft)
        db.flush()
    draft.promotion_type = safe_promotion_type
    draft.campaign_name = payload.campaign_name.strip()
    draft.start_at = start_at
    draft.end_at = end_at
    draft.addon_purchase_limit = payload.addon_purchase_limit if safe_promotion_type == "add_on" else None
    draft.gift_min_spend = payload.gift_min_spend if safe_promotion_type == "gift" else None
    draft.draft_status = "editing"
    draft.main_items.clear()
    draft.reward_items.clear()
    listing_map, variant_map = _hydrate_addon_payload_products(db=db, run=run, user_id=user_id, main_products=payload.main_products, reward_products=payload.reward_products)
    for index, item in enumerate(payload.main_products):
        listing = listing_map.get(item.listing_id)
        if listing:
            variant = variant_map.get(item.variant_id) if item.variant_id else None
            draft.main_items.append(ShopeeAddonDraftMainItem(run_id=run.id, listing_id=listing.id, variant_id=variant.id if variant else None, product_id=listing.product_id, sort_order=index))
    for index, item in enumerate(payload.reward_products):
        listing = listing_map.get(item.listing_id)
        if listing:
            variant = variant_map.get(item.variant_id) if item.variant_id else None
            draft.reward_items.append(ShopeeAddonDraftRewardItem(run_id=run.id, listing_id=listing.id, variant_id=variant.id if variant else None, product_id=listing.product_id, addon_price=item.addon_price if safe_promotion_type == "add_on" else None, reward_qty=max(1, int(item.reward_qty or 1)), sort_order=index))
    db.commit()
    db.refresh(draft)
    _invalidate_shopee_addon_cache(run_id=run.id, user_id=user_id, draft_id=draft.id)
    response = _build_addon_draft_detail_response(db, draft)
    cache_set_json(_shopee_addon_draft_cache_key(run_id=run.id, user_id=user_id, draft_id=draft.id), response.model_dump(mode="json"), REDIS_CACHE_TTL_ADDON_DRAFT_SEC)
    return response


@router.get("/runs/{run_id}/marketing/add-on/drafts/{draft_id}", response_model=ShopeeAddonDraftDetailResponse)
def get_shopee_addon_draft(
    run_id: int,
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeAddonDraftDetailResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    cache_key = _shopee_addon_draft_cache_key(run_id=run.id, user_id=user_id, draft_id=draft_id)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeAddonDraftDetailResponse.model_validate(cached_payload)
    draft = _load_addon_draft_or_404(db, draft_id=draft_id, run_id=run.id, user_id=user_id)
    response = _build_addon_draft_detail_response(db, draft)
    cache_set_json(cache_key, response.model_dump(mode="json"), REDIS_CACHE_TTL_ADDON_DRAFT_SEC)
    return response


@router.post("/runs/{run_id}/marketing/add-on/campaigns", response_model=ShopeeAddonCampaignCreateResponse, status_code=status.HTTP_201_CREATED)
def create_shopee_addon_campaign(
    run_id: int,
    payload: ShopeeAddonCampaignCreateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeAddonCampaignCreateResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_addon_create_rate_limit(user_id=user_id)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    safe_promotion_type = _resolve_addon_promotion_type(payload.promotion_type)
    start_at = _parse_discount_game_datetime(payload.start_at, run=run)
    end_at = _parse_discount_game_datetime(payload.end_at, run=run)
    _validate_addon_payload(db=db, run=run, user_id=user_id, promotion_type=safe_promotion_type, campaign_name=payload.campaign_name, start_at=start_at, end_at=end_at, addon_purchase_limit=payload.addon_purchase_limit, gift_min_spend=payload.gift_min_spend, main_products=payload.main_products, reward_products=payload.reward_products)
    assert start_at is not None
    assert end_at is not None
    current_tick = _resolve_game_tick(db, run.id, user_id)
    campaign_status = "upcoming" if start_at > current_tick else "ongoing"
    campaign = ShopeeAddonCampaign(run_id=run.id, user_id=user_id, campaign_code=f"ADDON{uuid4().hex[:12].upper()}", campaign_name=payload.campaign_name.strip(), promotion_type=safe_promotion_type, campaign_status=campaign_status, start_at=start_at, end_at=end_at, addon_purchase_limit=payload.addon_purchase_limit if safe_promotion_type == "add_on" else None, gift_min_spend=payload.gift_min_spend if safe_promotion_type == "gift" else None, market=(run.market or "MY").strip().upper() or "MY", currency="RM", rules_json=json.dumps({"promotion_type": safe_promotion_type, "main_product_limit": 100, "reward_product_limit": 100}, ensure_ascii=False))
    db.add(campaign)
    discount_campaign = ShopeeDiscountCampaign(
        run_id=run.id,
        user_id=user_id,
        campaign_type="add_on",
        campaign_name=payload.campaign_name.strip(),
        campaign_status=campaign_status,
        start_at=start_at,
        end_at=end_at,
        market=(run.market or "MY").strip().upper() or "MY",
        currency="RM",
        rules_json=json.dumps({"campaign_scope": "add_on_deal", "promotion_type": safe_promotion_type}, ensure_ascii=False),
    )
    db.add(discount_campaign)
    db.flush()
    campaign.source_campaign_id = discount_campaign.id
    listing_map, variant_map = _hydrate_addon_payload_products(db=db, run=run, user_id=user_id, main_products=payload.main_products, reward_products=payload.reward_products)
    for index, item in enumerate(payload.main_products):
        listing = listing_map[item.listing_id]
        variant = variant_map.get(item.variant_id) if item.variant_id else None
        original_price = float(variant.price if variant else listing.price)
        db.add(ShopeeAddonCampaignMainItem(campaign_id=campaign.id, run_id=run.id, listing_id=listing.id, variant_id=variant.id if variant else None, product_id=listing.product_id, product_name_snapshot=listing.title, variant_name_snapshot=variant.option_value if variant else None, sku_snapshot=variant.sku if variant else listing.sku_code, image_url_snapshot=variant.image_url if variant and variant.image_url else listing.cover_url, original_price_snapshot=original_price, stock_snapshot=int(variant.stock if variant else listing.stock_available), sort_order=index))
        db.add(ShopeeDiscountCampaignItem(campaign_id=discount_campaign.id, listing_id=listing.id, variant_id=variant.id if variant else None, product_name_snapshot=listing.title, image_url_snapshot=variant.image_url if variant and variant.image_url else listing.cover_url, sku_snapshot=variant.sku if variant else listing.sku_code, original_price=original_price, discount_type="add_on", discount_value=0, final_price=original_price, sort_order=index))
    for index, item in enumerate(payload.reward_products):
        listing = listing_map[item.listing_id]
        variant = variant_map.get(item.variant_id) if item.variant_id else None
        db.add(ShopeeAddonCampaignRewardItem(campaign_id=campaign.id, run_id=run.id, listing_id=listing.id, variant_id=variant.id if variant else None, product_id=listing.product_id, product_name_snapshot=listing.title, variant_name_snapshot=variant.option_value if variant else None, sku_snapshot=variant.sku if variant else listing.sku_code, image_url_snapshot=variant.image_url if variant and variant.image_url else listing.cover_url, original_price_snapshot=float(variant.price if variant else listing.price), addon_price=item.addon_price if safe_promotion_type == "add_on" else None, reward_qty=max(1, int(item.reward_qty or 1)), stock_snapshot=int(variant.stock if variant else listing.stock_available), sort_order=index))
    db.commit()
    db.refresh(campaign)
    _invalidate_shopee_addon_cache(run_id=run.id, user_id=user_id, campaign_id=campaign.id)
    _invalidate_shopee_discount_cache(run_id=run.id, user_id=user_id)
    return ShopeeAddonCampaignCreateResponse(campaign_id=campaign.id, campaign_name=campaign.campaign_name, promotion_type=campaign.promotion_type, campaign_status=campaign.campaign_status, main_product_count=len(payload.main_products), reward_product_count=len(payload.reward_products), start_at=campaign.start_at, end_at=campaign.end_at)


@router.get("/runs/{run_id}/marketing/add-on/campaigns/{campaign_id}", response_model=ShopeeAddonCampaignDetailResponse)
def get_shopee_addon_campaign(
    run_id: int,
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeAddonCampaignDetailResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    cache_key = _shopee_addon_detail_cache_key(run_id=run.id, user_id=user_id, campaign_id=campaign_id)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return ShopeeAddonCampaignDetailResponse.model_validate(cached_payload)
    campaign = _load_addon_campaign_or_404(db, campaign_id=campaign_id, run_id=run.id, user_id=user_id)
    current_tick = _resolve_game_tick(db, run.id, user_id)
    response = _build_addon_campaign_detail_response(db, campaign, current_tick=current_tick)
    cache_set_json(cache_key, response.model_dump(mode="json"), REDIS_CACHE_TTL_ADDON_DETAIL_SEC)
    return response


@router.post("/runs/{run_id}/marketing/bundle/campaigns", response_model=ShopeeDiscountCampaignCreateResponse, status_code=status.HTTP_201_CREATED)
def create_shopee_bundle_campaign(
    run_id: int,
    payload: ShopeeBundleCampaignCreateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDiscountCampaignCreateResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_discount_create_rate_limit(user_id=user_id)
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    if _resolve_discount_type(payload.campaign_type) != "bundle":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前仅支持创建套餐优惠活动")

    start_at = _parse_discount_game_datetime(payload.start_at, run=run)
    end_at = _parse_discount_game_datetime(payload.end_at, run=run)
    safe_bundle_type = _resolve_bundle_discount_type(payload.bundle_type)
    normalized_tiers = _validate_bundle_create_payload(
        db=db,
        run=run,
        user_id=user_id,
        campaign_name=payload.campaign_name,
        start_at=start_at,
        end_at=end_at,
        bundle_type=safe_bundle_type,
        purchase_limit=payload.purchase_limit,
        tiers=payload.tiers,
        items=payload.items,
    )
    assert start_at is not None
    assert end_at is not None

    current_tick = _resolve_game_tick(db, run.id, user_id)
    campaign_status = "upcoming" if start_at > current_tick else "ongoing"
    campaign = ShopeeDiscountCampaign(
        run_id=run.id,
        user_id=user_id,
        campaign_type="bundle",
        campaign_name=payload.campaign_name.strip(),
        campaign_status=campaign_status,
        start_at=start_at,
        end_at=end_at,
        market=(run.market or "MY").strip().upper() or "MY",
        currency="RM",
        rules_json=json.dumps(
            {
                "campaign_scope": "bundle_deal",
                "bundle_type": safe_bundle_type,
                "purchase_limit": int(payload.purchase_limit) if payload.purchase_limit is not None else None,
                "tiers": [tier.model_dump(mode="json") for tier in normalized_tiers],
                "max_duration_days": 180,
            },
            ensure_ascii=False,
        ),
    )
    db.add(campaign)
    db.flush()

    listing_ids = {item.listing_id for item in payload.items}
    variant_ids = {item.variant_id for item in payload.items if item.variant_id}
    listing_map = {row.id: row for row in db.query(ShopeeListing).filter(ShopeeListing.id.in_(listing_ids)).all()} if listing_ids else {}
    variant_map = {row.id: row for row in db.query(ShopeeListingVariant).filter(ShopeeListingVariant.id.in_(variant_ids)).all()} if variant_ids else {}

    first_tier_value = normalized_tiers[0].discount_value if normalized_tiers else 0.0
    for index, item in enumerate(payload.items):
        listing = listing_map.get(item.listing_id)
        if not listing:
            continue
        variant = variant_map.get(item.variant_id) if item.variant_id else None
        original_price = float(variant.price if variant else listing.price)
        if safe_bundle_type == "percent":
            discount_value = first_tier_value
            final_price = round(original_price * (100 - first_tier_value) / 100, 2)
        elif safe_bundle_type == "fixed_amount":
            discount_value = first_tier_value
            final_price = max(round(original_price - first_tier_value, 2), 0.01)
        else:
            discount_value = first_tier_value
            final_price = round(first_tier_value, 2)

        db.add(
            ShopeeDiscountCampaignItem(
                campaign_id=campaign.id,
                listing_id=listing.id,
                variant_id=variant.id if variant else None,
                product_name_snapshot=listing.title,
                image_url_snapshot=(variant.image_url if variant and variant.image_url else listing.cover_url),
                sku_snapshot=(variant.sku if variant else listing.sku_code),
                original_price=original_price,
                discount_type=safe_bundle_type,
                discount_value=discount_value,
                final_price=final_price,
                sort_order=index,
            )
        )

    db.commit()
    db.refresh(campaign)
    _invalidate_shopee_discount_create_cache(run_id=run.id, user_id=user_id)
    _invalidate_shopee_discount_cache(run_id=run.id, user_id=user_id)
    return ShopeeDiscountCampaignCreateResponse(
        campaign_id=campaign.id,
        campaign_name=campaign.campaign_name,
        campaign_status=campaign.campaign_status,
        item_count=len(payload.items),
        start_at=campaign.start_at or start_at,
        end_at=campaign.end_at or end_at,
    )


@router.post("/runs/{run_id}/orders/simulate", response_model=ShopeeSimulateOrdersResponse)
def simulate_shopee_orders(
    run_id: int,
    tick_time: datetime | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeSimulateOrdersResponse:
    user_id = int(current_user["id"])
    _enforce_shopee_simulate_rate_limit(user_id=user_id)
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)
    effective_tick_time = tick_time
    if effective_tick_time is None:
        latest_tick_time = (
            db.query(func.max(ShopeeOrderGenerationLog.tick_time))
            .filter(
                ShopeeOrderGenerationLog.run_id == run.id,
                ShopeeOrderGenerationLog.user_id == user_id,
            )
            .scalar()
        )
        if latest_tick_time:
            effective_tick_time = latest_tick_time + timedelta(hours=1)
        else:
            effective_tick_time = datetime.now()
    guard_tick = effective_tick_time if tick_time is not None else _resolve_game_hour_tick_by_run(run)
    _ensure_run_writable_or_400(db, run, tick_time=guard_tick)
    lock_key, lock_token = _acquire_shopee_simulate_lock_or_409(run_id=run.id, user_id=user_id)

    try:
        result = simulate_orders_for_run(db, run_id=run.id, user_id=user_id, tick_time=effective_tick_time)
        _invalidate_shopee_orders_cache_for_user(run_id=run.id, user_id=user_id)
        _invalidate_shopee_flash_sale_cache(run_id=run.id, user_id=user_id)
        return ShopeeSimulateOrdersResponse(
            tick_time=result["tick_time"],
            active_buyer_count=result["active_buyer_count"],
            candidate_product_count=result["candidate_product_count"],
            generated_order_count=result["generated_order_count"],
            flash_sale_traffic=result.get("flash_sale_traffic") or {},
            skip_reasons=result["skip_reasons"],
            shop_context={
                "run_id": run.id,
                "user_id": user_id,
                "username": current_user.get("username"),
                "market": run.market,
                "status": run.status,
            },
            buyer_journeys=result.get("buyer_journeys") or [],
        )
    finally:
        release_distributed_lock(lock_key, lock_token)


@router.get("/runs/{run_id}/products", response_model=ShopeeListingsListResponse)
def list_shopee_products(
    run_id: int,
    type: str = Query(default="all"),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeListingsListResponse:
    user_id = int(current_user["id"])
    run = _get_owned_order_readable_run_or_404(db, run_id, user_id)

    base_query = db.query(ShopeeListing).filter(ShopeeListing.run_id == run.id, ShopeeListing.user_id == user_id)
    counts = ShopeeListingsCountsResponse(
        all=base_query.count(),
        live=base_query.filter(ShopeeListing.status == "live").count(),
        violation=base_query.filter(ShopeeListing.status == "violation").count(),
        review=base_query.filter(ShopeeListing.status == "review").count(),
        unpublished=base_query.filter(ShopeeListing.status == "unpublished").count(),
    )

    query = base_query
    if type and type != "all":
        query = query.filter(ShopeeListing.status == type)

    if keyword:
        kw = keyword.strip()
        if kw:
            query = query.filter(ShopeeListing.title.ilike(f"%{kw}%"))

    query = query.options(selectinload(ShopeeListing.variants)).order_by(ShopeeListing.created_at.desc(), ShopeeListing.id.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()

    return ShopeeListingsListResponse(
        counts=counts,
        page=page,
        page_size=page_size,
        total=total,
        listings=[
            ShopeeListingRowResponse(
                id=row.id,
                title=row.title,
                category=row.category,
                sku_code=row.sku_code,
                model_id=row.model_id,
                cover_url=row.cover_url,
                sales_count=row.sales_count,
                price=row.price,
                original_price=row.original_price,
                stock_available=row.stock_available,
                quality_status=row.quality_status,
                quality_total_score=row.quality_total_score,
                quality_scored_at=row.quality_scored_at,
                quality_score_version=row.quality_score_version,
                status=row.status,
                created_at=row.created_at,
                variants=[
                    ShopeeListingVariantPreviewResponse(
                        id=variant.id,
                        option_value=variant.option_value,
                        option_note=variant.option_note,
                        price=variant.price,
                        stock=variant.stock,
                        sales_count=int(variant.sales_count or 0),
                        oversell_limit=int(variant.oversell_limit or 0),
                        oversell_used=int(variant.oversell_used or 0),
                        sku=variant.sku,
                        image_url=variant.image_url,
                    )
                    for variant in sorted(row.variants or [], key=lambda x: (x.sort_order, x.id))
                ],
            )
            for row in rows
        ],
    )


@router.get("/runs/{run_id}/listings/{listing_id}/quality", response_model=ShopeeListingQualityDetailResponse)
def get_shopee_listing_quality(
    run_id: int,
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeListingQualityDetailResponse:
    user_id = int(current_user["id"])
    _get_owned_order_readable_run_or_404(db, run_id, user_id)
    listing = (
        db.query(ShopeeListing)
        .filter(
            ShopeeListing.id == listing_id,
            ShopeeListing.run_id == run_id,
            ShopeeListing.user_id == user_id,
        )
        .first()
    )
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")

    latest = (
        db.query(ShopeeListingQualityScore)
        .filter(
            ShopeeListingQualityScore.listing_id == listing_id,
            ShopeeListingQualityScore.is_latest == True,
        )
        .order_by(ShopeeListingQualityScore.id.desc())
        .first()
    )
    if not latest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="尚无评分记录")

    return ShopeeListingQualityDetailResponse(
        listing_id=listing_id,
        score_version=latest.score_version,
        provider=latest.provider,
        text_model=latest.text_model,
        vision_model=latest.vision_model,
        summary=_extract_quality_summary(latest.raw_result_json),
        total_score=int(latest.total_score or 0),
        quality_status=latest.quality_status,
        rule_score=int(latest.rule_score or 0),
        vision_score=int(latest.vision_score or 0),
        text_score=int(latest.text_score or 0),
        consistency_score=int(latest.consistency_score or 0),
        scoring_dimensions={
            "rule_score": ["基础结构完整度", "类目与价格有效性", "图片数量门槛", "变体字段完整性"],
            "vision_score": ["清晰度", "主体完整度", "构图", "背景干净度", "违规视觉元素"],
            "text_score": ["标题信息密度", "描述完整性", "表达可读性", "文案合规性"],
            "consistency_score": ["标题与图片一致性", "类目与图片一致性", "变体与图片一致性"],
        },
        reasons=_safe_load_json_list(latest.reasons_json),
        suggestions=_safe_load_json_list(latest.suggestions_json),
        image_feedback=_extract_image_feedback(latest.raw_result_json),
        quality_scored_at=latest.created_at,
    )


@router.post("/runs/{run_id}/listings/{listing_id}/quality/recompute", response_model=ShopeeListingQualityRecomputeResponse)
def recompute_shopee_listing_quality(
    run_id: int,
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeListingQualityRecomputeResponse:
    user_id = int(current_user["id"])
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    _ensure_run_writable_or_400(db, run)
    listing = (
        db.query(ShopeeListing)
        .filter(
            ShopeeListing.id == listing_id,
            ShopeeListing.run_id == run_id,
            ShopeeListing.user_id == user_id,
        )
        .first()
    )
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")

    snapshot = recompute_listing_quality(
        db,
        listing_id=listing_id,
        run_id=run_id,
        user_id=user_id,
        force_recompute=True,
    )
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="重评失败")
    db.commit()

    return ShopeeListingQualityRecomputeResponse(
        listing_id=listing_id,
        total_score=int(snapshot.total_score or 0),
        quality_status=snapshot.quality_status,
        score_version=snapshot.score_version,
        scored_at=snapshot.created_at,
    )


@router.get("/runs/{run_id}/warehouse-link-products", response_model=ShopeeWarehouseLinkProductsResponse)
def list_warehouse_link_products(
    run_id: int,
    keyword: str | None = Query(default=None, max_length=64),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeWarehouseLinkProductsResponse:
    user_id = int(current_user["id"])
    run = _get_owned_running_run_or_404(db, run_id, user_id)

    query = (
        db.query(
            InventoryLot.product_id.label("product_id"),
            func.max(MarketProduct.product_name).label("product_name"),
            func.coalesce(func.sum(InventoryLot.quantity_available), 0).label("available_qty"),
            func.coalesce(func.sum(InventoryLot.reserved_qty), 0).label("reserved_qty"),
            func.coalesce(func.sum(InventoryLot.backorder_qty), 0).label("backorder_qty"),
            func.count(InventoryLot.id).label("inbound_lot_count"),
        )
        .join(MarketProduct, MarketProduct.id == InventoryLot.product_id)
        .filter(InventoryLot.run_id == run.id)
    )

    kw = (keyword or "").strip()
    if kw:
        query = query.filter(
            or_(
                MarketProduct.product_name.like(f"%{kw}%"),
                cast(InventoryLot.product_id, String).like(f"%{kw}%"),
            )
        )

    grouped = query.group_by(InventoryLot.product_id)
    grouped_subq = grouped.subquery()
    total = int(db.query(func.count()).select_from(grouped_subq).scalar() or 0)
    rows = (
        db.query(grouped_subq)
        .order_by(grouped_subq.c.available_qty.desc(), grouped_subq.c.product_id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ShopeeWarehouseLinkProductsResponse(
        page=page,
        page_size=page_size,
        total=total,
        rows=[
            ShopeeWarehouseLinkProductRowResponse(
                product_id=int(row.product_id),
                product_name=str(row.product_name or f"商品#{row.product_id}"),
                available_qty=int(row.available_qty or 0),
                reserved_qty=int(row.reserved_qty or 0),
                backorder_qty=int(row.backorder_qty or 0),
                inbound_lot_count=int(row.inbound_lot_count or 0),
            )
            for row in rows
        ],
    )


@router.post("/runs/{run_id}/products/batch-action", response_model=ShopeeProductsBatchActionResponse)
def batch_action_shopee_products(
    run_id: int,
    payload: ShopeeProductsBatchActionRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeProductsBatchActionResponse:
    user_id = int(current_user["id"])
    run = _get_owned_running_run_or_404(db, run_id, user_id)

    listing_ids = sorted({int(i) for i in payload.listing_ids if int(i) > 0})
    if not listing_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择至少一个商品")

    action = (payload.action or "").strip().lower()
    if action not in {"delete", "unpublish"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的批量操作")

    rows = db.query(ShopeeListing).filter(
        ShopeeListing.run_id == run.id,
        ShopeeListing.user_id == user_id,
        ShopeeListing.id.in_(listing_ids),
    ).all()
    if not rows:
        return ShopeeProductsBatchActionResponse(success=True, affected=0, action=action)

    affected = 0
    if action == "delete":
        for row in rows:
            db.delete(row)
            affected += 1
    else:
        for row in rows:
            if row.status != "unpublished":
                row.status = "unpublished"
                affected += 1
            elif row.status == "unpublished":
                affected += 1

    db.commit()
    return ShopeeProductsBatchActionResponse(success=True, affected=affected, action=action)


@router.post("/runs/{run_id}/products/{listing_id}/edit-draft", response_model=ShopeeEditBootstrapResponse)
def bootstrap_shopee_product_edit(
    run_id: int,
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeEditBootstrapResponse:
    user_id = int(current_user["id"])
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    listing = _get_owned_listing_or_404(db, listing_id, run.id, user_id)

    draft = ShopeeListingDraft(
        run_id=run.id,
        user_id=user_id,
        category_id=listing.category_id,
        title=listing.title,
        category=listing.category,
        gtin=listing.gtin,
        description=listing.description,
        video_url=listing.video_url,
        cover_url=listing.cover_url,
        status="drafting",
    )
    db.add(draft)
    db.flush()

    for img in sorted(listing.images or [], key=lambda x: (x.sort_order, x.id)):
        db.add(
            ShopeeListingDraftImage(
                draft_id=draft.id,
                image_url=img.image_url,
                image_ratio=img.image_ratio,
                sort_order=img.sort_order,
                is_cover=img.is_cover,
            )
        )

    for spec in sorted(listing.specs or [], key=lambda x: (x.attr_key, x.id)):
        db.add(
            ShopeeListingDraftSpecValue(
                draft_id=draft.id,
                attr_key=spec.attr_key,
                attr_label=spec.attr_label,
                attr_value=spec.attr_value,
            )
        )

    db.commit()
    draft = _get_owned_draft_or_404(db, draft.id, run.id, user_id)
    listing = _get_owned_listing_or_404(db, listing_id, run.id, user_id)
    return ShopeeEditBootstrapResponse(
        draft=_build_draft_response(draft),
        listing=_build_listing_detail_response(listing),
    )


@router.get("/spec-templates", response_model=ShopeeSpecTemplateResponse)
def get_shopee_spec_template(
    category_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeSpecTemplateResponse:
    _ = current_user
    category_node = db.query(ShopeeCategoryNode).filter(
        ShopeeCategoryNode.id == category_id,
        ShopeeCategoryNode.is_active == True,
    ).first()
    if not category_node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="类目不存在")
    templates = _load_spec_templates(db, category_id)
    return ShopeeSpecTemplateResponse(
        category_id=category_node.id,
        category_path=category_node.path,
        fields=[
            ShopeeSpecTemplateFieldResponse(
                attr_key=row.field_key,
                attr_label=row.field_label,
                input_type=row.field_type,
                options=[opt.option_value for opt in sorted([o for o in row.options if o.is_active], key=lambda x: x.sort_order)],
                is_required=row.is_required,
                sort_order=row.sort_order,
            )
            for row in templates
        ],
    )


@router.get("/categories/tree", response_model=list[ShopeeCategoryNodeResponse])
def get_shopee_categories_tree(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> list[ShopeeCategoryNodeResponse]:
    _ = current_user
    rows = (
        db.query(ShopeeCategoryNode)
        .filter(ShopeeCategoryNode.is_active == True)
        .order_by(ShopeeCategoryNode.level.asc(), ShopeeCategoryNode.sort_order.asc(), ShopeeCategoryNode.id.asc())
        .all()
    )
    node_map: dict[int, dict] = {
        row.id: {"id": row.id, "name": row.name, "level": row.level, "path": row.path, "children": []}
        for row in rows
    }
    roots: list[dict] = []
    for row in rows:
        current = node_map[row.id]
        if row.parent_id and row.parent_id in node_map:
            node_map[row.parent_id]["children"].append(current)
        else:
            roots.append(current)
    return [ShopeeCategoryNodeResponse(**item) for item in roots]


@router.post("/runs/{run_id}/product-drafts", response_model=ShopeeDraftDetailResponse, status_code=status.HTTP_201_CREATED)
def create_shopee_product_draft(
    run_id: int,
    title: str = Form(..., min_length=2, max_length=120),
    category_id: int | None = Form(default=None),
    category: str | None = Form(default=None),
    gtin: str | None = Form(default=None),
    description: str | None = Form(default=None),
    video: UploadFile | None = File(default=None),
    cover_index: int = Form(default=0, ge=0),
    cover_index_34: int = Form(default=0, ge=0),
    images: list[UploadFile] = File(default=[]),
    images_34: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDraftDetailResponse:
    user_id = int(current_user["id"])
    run = _get_owned_running_run_or_404(db, run_id, user_id)

    resolved_category_id, resolved_category_path = _resolve_category_or_400(db, category_id, category)

    valid_images_11 = [img for img in images if img and (img.filename or "").strip()]
    valid_images_34 = [img for img in images_34 if img and (img.filename or "").strip()]
    if not valid_images_11:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="至少上传 1 张 1:1 商品图")
    if len(valid_images_11) > 9 or len(valid_images_34) > 9:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="1:1 与 3:4 均最多上传 9 张图片")

    upload_urls_11 = [_save_shopee_image(db, img) for img in valid_images_11]
    upload_urls_34 = [_save_shopee_image(db, img) for img in valid_images_34]
    video_url = None
    if video and (video.filename or "").strip():
        video_url = _save_shopee_video(db, video)
    cover_idx_11 = min(max(cover_index, 0), max(len(upload_urls_11) - 1, 0))
    cover_idx_34 = min(max(cover_index_34, 0), max(len(upload_urls_34) - 1, 0))

    cover_url = upload_urls_11[cover_idx_11] if upload_urls_11 else None
    if not cover_url and upload_urls_34:
        cover_url = upload_urls_34[cover_idx_34]

    draft = ShopeeListingDraft(
        run_id=run.id,
        user_id=user_id,
        category_id=resolved_category_id,
        title=title.strip(),
        category=resolved_category_path,
        gtin=(gtin or "").strip() or None,
        description=(description or "").strip() or None,
        video_url=video_url,
        cover_url=cover_url,
        status="drafting",
    )
    db.add(draft)
    db.flush()

    for idx, image_url in enumerate(upload_urls_11):
        db.add(
            ShopeeListingDraftImage(
                draft_id=draft.id,
                image_url=image_url,
                image_ratio="1:1",
                sort_order=idx,
                is_cover=(idx == cover_idx_11),
            )
        )

    for idx, image_url in enumerate(upload_urls_34):
        db.add(
            ShopeeListingDraftImage(
                draft_id=draft.id,
                image_url=image_url,
                image_ratio="3:4",
                sort_order=idx,
                is_cover=(not upload_urls_11 and idx == cover_idx_34),
            )
        )

    db.commit()
    db.refresh(draft)
    draft = _get_owned_draft_or_404(db, draft.id, run.id, user_id)
    return _build_draft_response(draft)


@router.get("/runs/{run_id}/product-drafts/{draft_id}", response_model=ShopeeDraftDetailResponse)
def get_shopee_product_draft(
    run_id: int,
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDraftDetailResponse:
    user_id = int(current_user["id"])
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    draft = _get_owned_draft_or_404(db, draft_id, run.id, user_id)
    return _build_draft_response(draft)


@router.put("/runs/{run_id}/product-drafts/{draft_id}", response_model=ShopeeDraftDetailResponse)
def update_shopee_product_draft(
    run_id: int,
    draft_id: int,
    payload: ShopeeDraftUpdatePayload,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDraftDetailResponse:
    user_id = int(current_user["id"])
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    draft = _get_owned_draft_or_404(db, draft_id, run.id, user_id)

    resolved_category_id, resolved_category_path = _resolve_category_or_400(db, payload.category_id, payload.category)

    draft.title = payload.title.strip()
    if len(draft.title) < 2 or len(draft.title) > 120:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="商品名称长度需在 2~120 字符")
    draft.category_id = resolved_category_id
    draft.category = resolved_category_path
    draft.gtin = (payload.gtin or "").strip() or None
    draft.description = (payload.description or "").strip() or None

    if payload.spec_values is not None:
        templates = _load_spec_templates(db, draft.category_id)
        template_map = {row.field_key: row for row in templates}
        existing_rows = {row.attr_key: row for row in draft.specs}
        for attr_key, row in existing_rows.items():
            if attr_key not in template_map:
                db.delete(row)
        for attr_key, template in template_map.items():
            value = (payload.spec_values.get(attr_key, "") if payload.spec_values else "").strip()
            existing = existing_rows.get(attr_key)
            if existing:
                existing.attr_label = template.field_label
                existing.attr_value = value or None
            else:
                db.add(
                    ShopeeListingDraftSpecValue(
                        draft_id=draft.id,
                        attr_key=attr_key,
                        attr_label=template.field_label,
                        attr_value=value or None,
                    )
                )

    db.commit()
    db.refresh(draft)
    draft = _get_owned_draft_or_404(db, draft.id, run.id, user_id)
    return _build_draft_response(draft)


@router.post("/runs/{run_id}/product-drafts/{draft_id}/assets", response_model=ShopeeDraftDetailResponse)
def append_shopee_product_draft_assets(
    run_id: int,
    draft_id: int,
    cover_index_11: int = Form(default=-1),
    cover_index_34: int = Form(default=-1),
    images: list[UploadFile] = File(default=[]),
    images_34: list[UploadFile] = File(default=[]),
    video: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDraftDetailResponse:
    user_id = int(current_user["id"])
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    draft = _get_owned_draft_or_404(db, draft_id, run.id, user_id)

    valid_images_11 = [img for img in images if img and (img.filename or "").strip()]
    valid_images_34 = [img for img in images_34 if img and (img.filename or "").strip()]

    current_11 = sorted([row for row in draft.images if row.image_ratio == "1:1"], key=lambda row: row.sort_order)
    current_34 = sorted([row for row in draft.images if row.image_ratio == "3:4"], key=lambda row: row.sort_order)
    if len(current_11) + len(valid_images_11) > 9 or len(current_34) + len(valid_images_34) > 9:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="1:1 与 3:4 均最多上传 9 张图片")

    upload_urls_11 = [_save_shopee_image(db, img) for img in valid_images_11]
    upload_urls_34 = [_save_shopee_image(db, img) for img in valid_images_34]

    start_11 = len(current_11)
    for idx, image_url in enumerate(upload_urls_11):
        db.add(
            ShopeeListingDraftImage(
                draft_id=draft.id,
                image_url=image_url,
                image_ratio="1:1",
                sort_order=start_11 + idx,
                is_cover=False,
            )
        )

    start_34 = len(current_34)
    for idx, image_url in enumerate(upload_urls_34):
        db.add(
            ShopeeListingDraftImage(
                draft_id=draft.id,
                image_url=image_url,
                image_ratio="3:4",
                sort_order=start_34 + idx,
                is_cover=False,
            )
        )

    if video and (video.filename or "").strip():
        draft.video_url = _save_shopee_video(db, video)

    db.flush()
    draft = _get_owned_draft_or_404(db, draft.id, run.id, user_id)
    images_after_11 = sorted([row for row in draft.images if row.image_ratio == "1:1"], key=lambda row: row.sort_order)
    images_after_34 = sorted([row for row in draft.images if row.image_ratio == "3:4"], key=lambda row: row.sort_order)

    if images_after_11:
        if cover_index_11 >= 0:
            target_11 = min(max(cover_index_11, 0), len(images_after_11) - 1)
            for idx, row in enumerate(images_after_11):
                row.is_cover = idx == target_11
        current_cover_11 = next((row for row in images_after_11 if row.is_cover), None)
        draft.cover_url = (current_cover_11 or images_after_11[0]).image_url

    if images_after_34 and not images_after_11:
        if cover_index_34 >= 0:
            target_34 = min(max(cover_index_34, 0), len(images_after_34) - 1)
            for idx, row in enumerate(images_after_34):
                row.is_cover = idx == target_34
        current_cover_34 = next((row for row in images_after_34 if row.is_cover), None)
        draft.cover_url = (current_cover_34 or images_after_34[0]).image_url

    db.commit()
    draft = _get_owned_draft_or_404(db, draft.id, run.id, user_id)
    return _build_draft_response(draft)


@router.delete("/runs/{run_id}/product-drafts/{draft_id}/images/{image_id}", response_model=ShopeeDraftDetailResponse)
def remove_shopee_product_draft_image(
    run_id: int,
    draft_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDraftDetailResponse:
    user_id = int(current_user["id"])
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    draft = _get_owned_draft_or_404(db, draft_id, run.id, user_id)

    target = db.query(ShopeeListingDraftImage).filter(
        ShopeeListingDraftImage.id == image_id,
        ShopeeListingDraftImage.draft_id == draft.id,
    ).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="草稿图片不存在")

    ratio = target.image_ratio
    db.delete(target)
    db.flush()

    same_ratio_rows = db.query(ShopeeListingDraftImage).filter(
        ShopeeListingDraftImage.draft_id == draft.id,
        ShopeeListingDraftImage.image_ratio == ratio,
    ).order_by(ShopeeListingDraftImage.sort_order.asc(), ShopeeListingDraftImage.id.asc()).all()
    for idx, row in enumerate(same_ratio_rows):
        row.sort_order = idx
        row.is_cover = idx == 0

    all_11 = [row for row in draft.images if row.image_ratio == "1:1" and row.id != image_id]
    all_34 = [row for row in draft.images if row.image_ratio == "3:4" and row.id != image_id]
    if all_11:
        sorted_11 = sorted(all_11, key=lambda row: row.sort_order)
        draft.cover_url = sorted_11[0].image_url
    elif all_34:
        sorted_34 = sorted(all_34, key=lambda row: row.sort_order)
        draft.cover_url = sorted_34[0].image_url
    else:
        draft.cover_url = None

    db.commit()
    draft = _get_owned_draft_or_404(db, draft.id, run.id, user_id)
    return _build_draft_response(draft)


@router.delete("/runs/{run_id}/product-drafts/{draft_id}/video", response_model=ShopeeDraftDetailResponse)
def remove_shopee_product_draft_video(
    run_id: int,
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDraftDetailResponse:
    user_id = int(current_user["id"])
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    draft = _get_owned_draft_or_404(db, draft_id, run.id, user_id)
    draft.video_url = None
    db.commit()
    draft = _get_owned_draft_or_404(db, draft.id, run.id, user_id)
    return _build_draft_response(draft)


@router.post(
    "/runs/{run_id}/product-drafts/{draft_id}/publish",
    response_model=ShopeeDraftPublishResponse,
    status_code=status.HTTP_201_CREATED,
)
def publish_shopee_product_draft(
    run_id: int,
    draft_id: int,
    status_value: str = Form(default="live"),
    quality_status: str = Form(default="内容待完善"),
    price: int = Form(default=0, ge=0),
    stock_available: int = Form(default=0, ge=0),
    min_purchase_qty: int = Form(default=1, ge=1),
    max_purchase_qty: int | None = Form(default=None),
    max_purchase_mode: str = Form(default="none"),
    max_purchase_period_start_date: date | None = Form(default=None),
    max_purchase_period_end_date: date | None = Form(default=None),
    max_purchase_period_qty: int | None = Form(default=None),
    max_purchase_period_days: int | None = Form(default=None),
    max_purchase_period_model: str | None = Form(default=None),
    weight_kg: float | None = Form(default=None),
    parcel_length_cm: int | None = Form(default=None),
    parcel_width_cm: int | None = Form(default=None),
    parcel_height_cm: int | None = Form(default=None),
    shipping_variation_dimension_enabled: bool = Form(default=False),
    shipping_standard_bulk: bool = Form(default=False),
    shipping_standard: bool = Form(default=False),
    shipping_express: bool = Form(default=False),
    preorder_enabled: bool = Form(default=False),
    insurance_enabled: bool = Form(default=False),
    condition_label: str | None = Form(default=None),
    schedule_publish_at: datetime | None = Form(default=None),
    parent_sku: str | None = Form(default=None),
    source_product_id: int | None = Form(default=None),
    source_listing_id: int | None = Form(default=None),
    variations_payload: str | None = Form(default=None),
    wholesale_tiers_payload: str | None = Form(default=None),
    variant_images: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeDraftPublishResponse:
    user_id = int(current_user["id"])
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    draft = _get_owned_draft_or_404(db, draft_id, run.id, user_id)

    status_white_list = {"live", "unpublished"}
    keep_status = (status_value == "keep")
    final_status = status_value if status_value in status_white_list else "live"
    requested_product_id = int(source_product_id) if source_product_id and int(source_product_id) > 0 else None
    if requested_product_id is not None:
        _validate_linkable_product_or_400(db, run_id=run.id, product_id=requested_product_id)
    if not draft.category_id or not (draft.category or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择商品类目后再发布")

    images_11 = [img for img in draft.images if img.image_ratio == "1:1"]
    images_34 = [img for img in draft.images if img.image_ratio == "3:4"]
    variant_rows = _parse_variants_payload(variations_payload)
    wholesale_tier_rows = _parse_wholesale_tiers_payload(wholesale_tiers_payload)
    valid_variant_images = [img for img in variant_images if img and (img.filename or "").strip()]

    existing_variant_by_id: dict[int, ShopeeListingVariant] = {}
    existing_variant_by_sku: dict[str, ShopeeListingVariant] = {}
    existing_variant_by_option: dict[tuple[str, str], ShopeeListingVariant] = {}
    listing: ShopeeListing
    if source_listing_id and source_listing_id > 0:
        listing = _get_owned_listing_or_404(db, source_listing_id, run.id, user_id)
        if requested_product_id is not None:
            listing.product_id = requested_product_id
        existing_variants = list(listing.variants or [])
        existing_variant_by_id = {v.id: v for v in existing_variants}
        existing_variant_by_sku = {str(v.sku or "").strip(): v for v in existing_variants if str(v.sku or "").strip()}
        existing_variant_by_option = {
            (str(v.option_value or "").strip(), str(v.option_note or "").strip()): v
            for v in existing_variants
        }
        if keep_status:
            final_status = (listing.status or "live").strip() or "live"
        listing.category_id = draft.category_id
        listing.title = draft.title
        listing.category = draft.category
        listing.gtin = draft.gtin
        listing.sku_code = draft.gtin
        listing.description = draft.description
        listing.video_url = draft.video_url
        listing.cover_url = draft.cover_url
        listing.price = price
        listing.original_price = price
        listing.stock_available = stock_available
        listing.min_purchase_qty = max(min_purchase_qty, 1)
        listing.max_purchase_qty = max_purchase_qty if (max_purchase_qty is None or max_purchase_qty > 0) else None
        listing.max_purchase_mode = max_purchase_mode if max_purchase_mode in {"none", "per_order", "per_time_period"} else "none"
        listing.max_purchase_period_start_date = max_purchase_period_start_date
        listing.max_purchase_period_end_date = max_purchase_period_end_date
        listing.max_purchase_period_qty = max_purchase_period_qty if (max_purchase_period_qty is None or max_purchase_period_qty > 0) else None
        listing.max_purchase_period_days = max_purchase_period_days if (max_purchase_period_days is None or max_purchase_period_days > 0) else None
        listing.max_purchase_period_model = max_purchase_period_model if max_purchase_period_model in {"single", "recurring"} else None
        listing.weight_kg = weight_kg
        listing.parcel_length_cm = parcel_length_cm if (parcel_length_cm is None or parcel_length_cm > 0) else None
        listing.parcel_width_cm = parcel_width_cm if (parcel_width_cm is None or parcel_width_cm > 0) else None
        listing.parcel_height_cm = parcel_height_cm if (parcel_height_cm is None or parcel_height_cm > 0) else None
        listing.shipping_variation_dimension_enabled = shipping_variation_dimension_enabled
        listing.shipping_standard_bulk = shipping_standard_bulk
        listing.shipping_standard = shipping_standard
        listing.shipping_express = shipping_express
        listing.preorder_enabled = preorder_enabled
        listing.insurance_enabled = insurance_enabled
        listing.condition_label = (condition_label or "").strip() or "全新"
        listing.schedule_publish_at = schedule_publish_at
        listing.parent_sku = (parent_sku or "").strip() or None
        listing.status = final_status
        listing.quality_status = (quality_status or "").strip() or "内容待完善"
        listing.images.clear()
        listing.specs.clear()
        listing.wholesale_tiers.clear()
        db.flush()
    else:
        if final_status == "live" and requested_product_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先关联仓库商品后发布")
        listing = ShopeeListing(
            run_id=run.id,
            user_id=user_id,
            product_id=requested_product_id,
            category_id=draft.category_id,
            title=draft.title,
            category=draft.category,
            gtin=draft.gtin,
            sku_code=draft.gtin,
            model_id=None,
            description=draft.description,
            video_url=draft.video_url,
            cover_url=draft.cover_url,
            price=price,
            original_price=price,
            sales_count=0,
            stock_available=stock_available,
            min_purchase_qty=max(min_purchase_qty, 1),
            max_purchase_qty=max_purchase_qty if (max_purchase_qty is None or max_purchase_qty > 0) else None,
            max_purchase_mode=max_purchase_mode if max_purchase_mode in {"none", "per_order", "per_time_period"} else "none",
            max_purchase_period_start_date=max_purchase_period_start_date,
            max_purchase_period_end_date=max_purchase_period_end_date,
            max_purchase_period_qty=max_purchase_period_qty if (max_purchase_period_qty is None or max_purchase_period_qty > 0) else None,
            max_purchase_period_days=max_purchase_period_days if (max_purchase_period_days is None or max_purchase_period_days > 0) else None,
            max_purchase_period_model=max_purchase_period_model if max_purchase_period_model in {"single", "recurring"} else None,
            weight_kg=weight_kg,
            parcel_length_cm=parcel_length_cm if (parcel_length_cm is None or parcel_length_cm > 0) else None,
            parcel_width_cm=parcel_width_cm if (parcel_width_cm is None or parcel_width_cm > 0) else None,
            parcel_height_cm=parcel_height_cm if (parcel_height_cm is None or parcel_height_cm > 0) else None,
            shipping_variation_dimension_enabled=shipping_variation_dimension_enabled,
            shipping_standard_bulk=shipping_standard_bulk,
            shipping_standard=shipping_standard,
            shipping_express=shipping_express,
            preorder_enabled=preorder_enabled,
            insurance_enabled=insurance_enabled,
            condition_label=(condition_label or "").strip() or "全新",
            schedule_publish_at=schedule_publish_at,
            parent_sku=(parent_sku or "").strip() or None,
            status=final_status,
            quality_status=(quality_status or "").strip() or "内容待完善",
        )
        db.add(listing)
        db.flush()

    if source_listing_id and source_listing_id > 0 and final_status == "live" and listing.product_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先关联仓库商品后发布")

    for img in sorted(images_11, key=lambda row: row.sort_order):
        db.add(
            ShopeeListingImage(
                listing_id=listing.id,
                image_url=img.image_url,
                image_ratio="1:1",
                sort_order=img.sort_order,
                is_cover=img.is_cover,
            )
        )

    for img in sorted(images_34, key=lambda row: row.sort_order):
        db.add(
            ShopeeListingImage(
                listing_id=listing.id,
                image_url=img.image_url,
                image_ratio="3:4",
                sort_order=img.sort_order,
                is_cover=img.is_cover and not images_11,
            )
        )

    for spec in draft.specs:
        db.add(
            ShopeeListingSpecValue(
                listing_id=listing.id,
                attr_key=spec.attr_key,
                attr_label=spec.attr_label,
                attr_value=spec.attr_value,
            )
        )

    matched_existing_variant_ids: set[int] = set()
    for row in variant_rows:
        existing_variant: ShopeeListingVariant | None = None
        source_variant_id = row.get("source_variant_id")
        if isinstance(source_variant_id, int) and source_variant_id > 0:
            existing_variant = existing_variant_by_id.get(source_variant_id)
        if not existing_variant:
            sku_key = str(row.get("sku") or "").strip()
            if sku_key:
                existing_variant = existing_variant_by_sku.get(sku_key)
        if not existing_variant:
            option_key = (
                str(row.get("option_value") or "").strip(),
                str(row.get("option_note") or "").strip(),
            )
            existing_variant = existing_variant_by_option.get(option_key)

        image_url = row.get("image_url")
        image_idx = row.get("image_file_index")
        if image_idx is not None:
            if not isinstance(image_idx, int) or image_idx < 0 or image_idx >= len(valid_variant_images):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="变体图片索引无效")
            image_url = _save_shopee_image(db, valid_variant_images[image_idx])
        if not image_url and existing_variant and existing_variant.image_url:
            image_url = existing_variant.image_url
        if source_listing_id and source_listing_id > 0 and existing_variant:
            existing_variant.variant_name = row["variant_name"]
            existing_variant.option_value = row["option_value"]
            existing_variant.option_note = row["option_note"]
            existing_variant.price = row["price"]
            existing_variant.stock = row["stock"]
            existing_variant.sku = row["sku"]
            existing_variant.gtin = row["gtin"]
            existing_variant.item_without_gtin = row["item_without_gtin"]
            existing_variant.weight_kg = row["weight_kg"]
            existing_variant.parcel_length_cm = row["parcel_length_cm"]
            existing_variant.parcel_width_cm = row["parcel_width_cm"]
            existing_variant.parcel_height_cm = row["parcel_height_cm"]
            existing_variant.image_url = image_url
            existing_variant.sort_order = row["sort_order"]
            matched_existing_variant_ids.add(existing_variant.id)
        else:
            db.add(
                ShopeeListingVariant(
                    listing_id=listing.id,
                    variant_name=row["variant_name"],
                    option_value=row["option_value"],
                    option_note=row["option_note"],
                    price=row["price"],
                    stock=row["stock"],
                    sales_count=0,
                    sku=row["sku"],
                    gtin=row["gtin"],
                    item_without_gtin=row["item_without_gtin"],
                    weight_kg=row["weight_kg"],
                    parcel_length_cm=row["parcel_length_cm"],
                    parcel_width_cm=row["parcel_width_cm"],
                    parcel_height_cm=row["parcel_height_cm"],
                    image_url=image_url,
                    sort_order=row["sort_order"],
                )
            )

    if source_listing_id and source_listing_id > 0:
        for existing in existing_variants:
            if existing.id not in matched_existing_variant_ids:
                db.delete(existing)

    for row in wholesale_tier_rows:
        db.add(
            ShopeeListingWholesaleTier(
                listing_id=listing.id,
                tier_no=row["tier_no"],
                min_qty=row["min_qty"],
                max_qty=row["max_qty"],
                unit_price=row["unit_price"],
            )
        )

    draft_id_value = draft.id
    # Release storage by removing draft after successful publish.
    # ShopeeListingDraft relationships use ORM cascade to delete images/spec rows together.
    db.delete(draft)
    db.commit()
    _try_recompute_listing_quality(
        db,
        listing_id=int(listing.id),
        run_id=int(run.id),
        user_id=user_id,
        force_recompute=True,
    )
    return ShopeeDraftPublishResponse(draft_id=draft_id_value, listing_id=listing.id, status=final_status)


@router.post("/runs/{run_id}/products", response_model=ShopeeCreateListingResponse, status_code=status.HTTP_201_CREATED)
def create_shopee_product(
    run_id: int,
    title: str = Form(..., min_length=2, max_length=120),
    category_id: int | None = Form(default=None),
    category: str | None = Form(default=None),
    gtin: str | None = Form(default=None),
    sku_code: str | None = Form(default=None),
    model_id: str | None = Form(default=None),
    description: str | None = Form(default=None),
    video: UploadFile | None = File(default=None),
    price: int = Form(default=0, ge=0),
    original_price: int = Form(default=0, ge=0),
    stock_available: int = Form(default=0, ge=0),
    min_purchase_qty: int = Form(default=1, ge=1),
    max_purchase_qty: int | None = Form(default=None),
    max_purchase_mode: str = Form(default="none"),
    max_purchase_period_start_date: date | None = Form(default=None),
    max_purchase_period_end_date: date | None = Form(default=None),
    max_purchase_period_qty: int | None = Form(default=None),
    max_purchase_period_days: int | None = Form(default=None),
    max_purchase_period_model: str | None = Form(default=None),
    weight_kg: float | None = Form(default=None),
    parcel_length_cm: int | None = Form(default=None),
    parcel_width_cm: int | None = Form(default=None),
    parcel_height_cm: int | None = Form(default=None),
    shipping_variation_dimension_enabled: bool = Form(default=False),
    shipping_standard_bulk: bool = Form(default=False),
    shipping_standard: bool = Form(default=False),
    shipping_express: bool = Form(default=False),
    preorder_enabled: bool = Form(default=False),
    insurance_enabled: bool = Form(default=False),
    condition_label: str | None = Form(default=None),
    schedule_publish_at: datetime | None = Form(default=None),
    parent_sku: str | None = Form(default=None),
    quality_status: str = Form(default="内容待完善"),
    status_value: str = Form(default="unpublished"),
    cover_index: int = Form(default=0, ge=0),
    cover_index_34: int = Form(default=0, ge=0),
    images: list[UploadFile] = File(default=[]),
    images_34: list[UploadFile] = File(default=[]),
    wholesale_tiers_payload: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeCreateListingResponse:
    user_id = int(current_user["id"])
    run = _get_owned_running_run_or_404(db, run_id, user_id)

    resolved_category_id, resolved_category_path = _resolve_category_or_400(db, category_id, category)

    status_white_list = {"live", "violation", "review", "unpublished"}
    status_key = status_value if status_value in status_white_list else "unpublished"
    wholesale_tier_rows = _parse_wholesale_tiers_payload(wholesale_tiers_payload)
    valid_images_11 = [img for img in images if img and (img.filename or "").strip()]
    valid_images_34 = [img for img in images_34 if img and (img.filename or "").strip()]
    if len(valid_images_11) > 9 or len(valid_images_34) > 9:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="1:1 与 3:4 均最多上传 9 张图片")

    upload_urls_11 = [_save_shopee_image(db, img) for img in valid_images_11]
    upload_urls_34 = [_save_shopee_image(db, img) for img in valid_images_34]
    video_url = None
    if video and (video.filename or "").strip():
        video_url = _save_shopee_video(db, video)

    cover_idx_11 = min(max(cover_index, 0), max(len(upload_urls_11) - 1, 0))
    cover_idx_34 = min(max(cover_index_34, 0), max(len(upload_urls_34) - 1, 0))

    cover_url = None
    if upload_urls_11:
        cover_url = upload_urls_11[cover_idx_11]
    elif upload_urls_34:
        cover_url = upload_urls_34[cover_idx_34]

    row = ShopeeListing(
        run_id=run.id,
        user_id=user_id,
        product_id=None,
        category_id=resolved_category_id,
        title=title.strip(),
        category=resolved_category_path or "未分类",
        gtin=(gtin or "").strip() or None,
        sku_code=(sku_code or "").strip() or None,
        model_id=(model_id or "").strip() or None,
        description=(description or "").strip() or None,
        video_url=video_url,
        cover_url=cover_url,
        price=price,
        original_price=original_price if original_price > 0 else price,
        sales_count=0,
        stock_available=stock_available,
        min_purchase_qty=max(min_purchase_qty, 1),
        max_purchase_qty=max_purchase_qty if (max_purchase_qty is None or max_purchase_qty > 0) else None,
        max_purchase_mode=max_purchase_mode if max_purchase_mode in {"none", "per_order", "per_time_period"} else "none",
        max_purchase_period_start_date=max_purchase_period_start_date,
        max_purchase_period_end_date=max_purchase_period_end_date,
        max_purchase_period_qty=max_purchase_period_qty if (max_purchase_period_qty is None or max_purchase_period_qty > 0) else None,
        max_purchase_period_days=max_purchase_period_days if (max_purchase_period_days is None or max_purchase_period_days > 0) else None,
        max_purchase_period_model=max_purchase_period_model if max_purchase_period_model in {"single", "recurring"} else None,
        weight_kg=weight_kg,
        parcel_length_cm=parcel_length_cm if (parcel_length_cm is None or parcel_length_cm > 0) else None,
        parcel_width_cm=parcel_width_cm if (parcel_width_cm is None or parcel_width_cm > 0) else None,
        parcel_height_cm=parcel_height_cm if (parcel_height_cm is None or parcel_height_cm > 0) else None,
        shipping_variation_dimension_enabled=shipping_variation_dimension_enabled,
        shipping_standard_bulk=shipping_standard_bulk,
        shipping_standard=shipping_standard,
        shipping_express=shipping_express,
        preorder_enabled=preorder_enabled,
        insurance_enabled=insurance_enabled,
        condition_label=(condition_label or "").strip() or "全新",
        schedule_publish_at=schedule_publish_at,
        parent_sku=(parent_sku or "").strip() or None,
        status=status_key,
        quality_status=(quality_status or "").strip() or "内容待完善",
    )
    db.add(row)
    db.flush()

    for idx, image_url in enumerate(upload_urls_11):
        db.add(
            ShopeeListingImage(
                listing_id=row.id,
                image_url=image_url,
                image_ratio="1:1",
                sort_order=idx,
                is_cover=(idx == cover_idx_11),
            )
        )

    for idx, image_url in enumerate(upload_urls_34):
        db.add(
            ShopeeListingImage(
                listing_id=row.id,
                image_url=image_url,
                image_ratio="3:4",
                sort_order=idx,
                is_cover=(not upload_urls_11 and idx == cover_idx_34),
            )
        )

    for tier in wholesale_tier_rows:
        db.add(
            ShopeeListingWholesaleTier(
                listing_id=row.id,
                tier_no=tier["tier_no"],
                min_qty=tier["min_qty"],
                max_qty=tier["max_qty"],
                unit_price=tier["unit_price"],
            )
        )

    db.commit()
    db.refresh(row)
    _try_recompute_listing_quality(
        db,
        listing_id=int(row.id),
        run_id=int(run.id),
        user_id=user_id,
        force_recompute=True,
    )
    return ShopeeCreateListingResponse(id=row.id, title=row.title, cover_url=row.cover_url)

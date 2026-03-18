from datetime import date, datetime, timedelta
import json
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session, selectinload

from app.core.security import get_current_user
from app.db import get_db
from app.models import (
    GameRun,
    OssStorageConfig,
    ShopeeCategoryNode,
    ShopeeListing,
    ShopeeListingDraft,
    ShopeeListingDraftImage,
    ShopeeListingDraftSpecValue,
    ShopeeListingImage,
    ShopeeListingVariant,
    ShopeeListingWholesaleTier,
    ShopeeListingSpecValue,
    ShopeeOrder,
    ShopeeOrderGenerationLog,
    ShopeeSpecTemplate,
    ShopeeSpecTemplateOption,
)
from app.services.shopee_order_simulator import simulate_orders_for_run


router = APIRouter(prefix="/shopee", tags=["shopee"])


class ShopeeOrderItemResponse(BaseModel):
    product_name: str
    variant_name: str
    quantity: int
    unit_price: int
    image_url: str | None


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
    created_at: datetime
    items: list[ShopeeOrderItemResponse]


class ShopeeOrderTabCounts(BaseModel):
    all: int
    unpaid: int
    toship: int
    shipping: int
    completed: int


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
    skip_reasons: dict[str, int] = Field(default_factory=dict)
    shop_context: dict[str, Any] = Field(default_factory=dict)
    buyer_journeys: list[dict[str, Any]] = Field(default_factory=list)


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
    status: str
    created_at: datetime
    variants: list["ShopeeListingVariantPreviewResponse"] = Field(default_factory=list)


class ShopeeListingVariantPreviewResponse(BaseModel):
    id: int
    option_value: str
    option_note: str | None
    price: int
    stock: int
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

    object_key = f"shopee/{datetime.utcnow().strftime('%Y%m%d')}/{uuid4().hex}{suffix}"
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

    object_key = f"shopee/{datetime.utcnow().strftime('%Y%m%d')}/{uuid4().hex}{suffix}"
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
        query = query.filter(ShopeeOrder.type_bucket == type_value)

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
                "price": max(int(row.get("price", 0) or 0), 0),
                "stock": max(int(row.get("stock", 0) or 0), 0),
                "sku": str(row.get("sku", "")).strip() or None,
                "gtin": str(row.get("gtin", "")).strip() or None,
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


@router.get("/runs/{run_id}/orders", response_model=ShopeeOrdersListResponse)
def list_shopee_orders(
    run_id: int,
    type: str = Query(default="all"),
    source: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    order: str = Query(default="asc"),
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
    run = _get_owned_running_run_or_404(db, run_id, user_id)

    base_query = db.query(ShopeeOrder).filter(ShopeeOrder.run_id == run.id, ShopeeOrder.user_id == user_id)
    counts = ShopeeOrderTabCounts(
        all=base_query.count(),
        unpaid=base_query.filter(ShopeeOrder.type_bucket == "unpaid").count(),
        toship=base_query.filter(ShopeeOrder.type_bucket == "toship").count(),
        shipping=base_query.filter(ShopeeOrder.type_bucket == "shipping").count(),
        completed=base_query.filter(ShopeeOrder.type_bucket == "completed").count(),
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
    recent_window_start = datetime.utcnow() - timedelta(hours=1)
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
    last_log = (
        db.query(ShopeeOrderGenerationLog)
        .filter(
            ShopeeOrderGenerationLog.run_id == run.id,
            ShopeeOrderGenerationLog.user_id == user_id,
        )
        .order_by(ShopeeOrderGenerationLog.created_at.desc())
        .first()
    )

    return ShopeeOrdersListResponse(
        counts=counts,
        page=page,
        page_size=page_size,
        total=total,
        simulated_recent_1h=int(simulated_recent_1h),
        last_simulated_at=last_log.created_at if last_log else None,
        orders=[
            ShopeeOrderResponse(
                id=row.id,
                order_no=row.order_no,
                buyer_name=row.buyer_name,
                buyer_payment=row.buyer_payment,
                order_type=row.order_type,
                type_bucket=row.type_bucket,
                process_status=row.process_status,
                shipping_priority=row.shipping_priority,
                shipping_channel=row.shipping_channel,
                destination=row.destination,
                countdown_text=row.countdown_text,
                action_text=row.action_text,
                ship_by_date=row.ship_by_date,
                created_at=row.created_at,
                items=[
                    ShopeeOrderItemResponse(
                        product_name=item.product_name,
                        variant_name=item.variant_name,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                        image_url=item.image_url,
                    )
                    for item in row.items
                ],
            )
            for row in rows
        ],
    )


@router.post("/runs/{run_id}/orders/simulate", response_model=ShopeeSimulateOrdersResponse)
def simulate_shopee_orders(
    run_id: int,
    tick_time: datetime | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ShopeeSimulateOrdersResponse:
    user_id = int(current_user["id"])
    run = _get_owned_running_run_or_404(db, run_id, user_id)
    effective_tick_time = tick_time
    if effective_tick_time is None:
        last_log = (
            db.query(ShopeeOrderGenerationLog)
            .filter(
                ShopeeOrderGenerationLog.run_id == run.id,
                ShopeeOrderGenerationLog.user_id == user_id,
            )
            .order_by(ShopeeOrderGenerationLog.tick_time.desc(), ShopeeOrderGenerationLog.id.desc())
            .first()
        )
        if last_log and last_log.tick_time:
            effective_tick_time = last_log.tick_time + timedelta(hours=1)
        else:
            effective_tick_time = datetime.utcnow()

    result = simulate_orders_for_run(db, run_id=run.id, user_id=user_id, tick_time=effective_tick_time)
    return ShopeeSimulateOrdersResponse(
        tick_time=result["tick_time"],
        active_buyer_count=result["active_buyer_count"],
        candidate_product_count=result["candidate_product_count"],
        generated_order_count=result["generated_order_count"],
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
    run = _get_owned_running_run_or_404(db, run_id, user_id)

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
                status=row.status,
                created_at=row.created_at,
                variants=[
                    ShopeeListingVariantPreviewResponse(
                        id=variant.id,
                        option_value=variant.option_value,
                        option_note=variant.option_note,
                        price=variant.price,
                        stock=variant.stock,
                        sku=variant.sku,
                        image_url=variant.image_url,
                    )
                    for variant in sorted(row.variants or [], key=lambda x: (x.sort_order, x.id))
                ],
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
    final_status = status_value if status_value in status_white_list else "live"
    if not draft.category_id or not (draft.category or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择商品类目后再发布")

    images_11 = [img for img in draft.images if img.image_ratio == "1:1"]
    images_34 = [img for img in draft.images if img.image_ratio == "3:4"]
    variant_rows = _parse_variants_payload(variations_payload)
    wholesale_tier_rows = _parse_wholesale_tiers_payload(wholesale_tiers_payload)
    valid_variant_images = [img for img in variant_images if img and (img.filename or "").strip()]

    listing: ShopeeListing
    if source_listing_id and source_listing_id > 0:
        listing = _get_owned_listing_or_404(db, source_listing_id, run.id, user_id)
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
        listing.variants.clear()
        listing.wholesale_tiers.clear()
        db.flush()
    else:
        listing = ShopeeListing(
            run_id=run.id,
            user_id=user_id,
            product_id=None,
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

    for row in variant_rows:
        image_url = None
        image_idx = row.get("image_file_index")
        if image_idx is not None:
            if not isinstance(image_idx, int) or image_idx < 0 or image_idx >= len(valid_variant_images):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="变体图片索引无效")
            image_url = _save_shopee_image(db, valid_variant_images[image_idx])
        db.add(
            ShopeeListingVariant(
                listing_id=listing.id,
                variant_name=row["variant_name"],
                option_value=row["option_value"],
                option_note=row["option_note"],
                price=row["price"],
                stock=row["stock"],
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
    return ShopeeCreateListingResponse(id=row.id, title=row.title, cover_url=row.cover_url)

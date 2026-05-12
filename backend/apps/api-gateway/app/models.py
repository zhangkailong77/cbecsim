from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="player")
    school_id: Mapped[int | None] = mapped_column(ForeignKey("schools.id"), nullable=True)
    major: Mapped[str | None] = mapped_column(String(128), nullable=True)
    class_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    school = relationship("School", back_populates="users")
    game_runs = relationship("GameRun", back_populates="user")


class OssStorageConfig(Base):
    __tablename__ = "oss_storage_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="s3")
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    bucket: Mapped[str] = mapped_column(String(128), nullable=False)
    access_key: Mapped[str] = mapped_column(String(255), nullable=False)
    access_secret: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class School(Base):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    users = relationship("User", back_populates="school")


class GameRun(Base):
    __tablename__ = "game_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    initial_cash: Mapped[int] = mapped_column(Integer, nullable=False)
    market: Mapped[str] = mapped_column(String(16), nullable=False, default="MY")
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365)
    base_real_duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    base_game_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_game_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    manual_end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    day_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user = relationship("User", back_populates="game_runs")
    procurement_orders = relationship("ProcurementOrder", back_populates="run")
    logistics_shipments = relationship("LogisticsShipment", back_populates="run")
    shopee_listings = relationship("ShopeeListing", back_populates="run")
    shopee_listing_drafts = relationship("ShopeeListingDraft", back_populates="run")
    shopee_orders = relationship("ShopeeOrder", back_populates="run")
    shopee_order_logistics_events = relationship("ShopeeOrderLogisticsEvent", back_populates="run")
    shopee_order_settlements = relationship("ShopeeOrderSettlement", back_populates="run")
    shopee_finance_ledger_entries = relationship("ShopeeFinanceLedgerEntry", back_populates="run")
    cash_adjustments = relationship("GameRunCashAdjustment", back_populates="run")
    shopee_bank_accounts = relationship("ShopeeBankAccount", back_populates="run")
    shopee_order_generation_logs = relationship("ShopeeOrderGenerationLog", back_populates="run")
    shopee_marketing_preferences = relationship("ShopeeUserMarketingPreference", back_populates="run")
    shopee_discount_preferences = relationship("ShopeeUserDiscountPreference", back_populates="run")
    shopee_discount_campaigns = relationship("ShopeeDiscountCampaign", back_populates="run")
    shopee_discount_drafts = relationship("ShopeeDiscountDraft", back_populates="run")
    shopee_addon_campaigns = relationship("ShopeeAddonCampaign", back_populates="run")
    shopee_addon_drafts = relationship("ShopeeAddonDraft", back_populates="run")
    shopee_flash_sale_campaigns = relationship("ShopeeFlashSaleCampaign", back_populates="run")
    shopee_flash_sale_drafts = relationship("ShopeeFlashSaleDraft", back_populates="run")
    shopee_shop_voucher_campaigns = relationship("ShopeeShopVoucherCampaign", back_populates="run")
    shopee_product_voucher_campaigns = relationship("ShopeeProductVoucherCampaign", back_populates="run")
    shopee_private_voucher_campaigns = relationship("ShopeePrivateVoucherCampaign", back_populates="run")
    shopee_live_voucher_campaigns = relationship("ShopeeLiveVoucherCampaign", back_populates="run")
    shopee_video_voucher_campaigns = relationship("ShopeeVideoVoucherCampaign", back_populates="run")
    shopee_follow_voucher_campaigns = relationship("ShopeeFollowVoucherCampaign", back_populates="run")
    shopee_buyer_follow_states = relationship("ShopeeBuyerFollowState", back_populates="run")
    shopee_shipping_fee_promotion_campaigns = relationship("ShopeeShippingFeePromotionCampaign", back_populates="run")
    shopee_auto_reply_settings = relationship("ShopeeAutoReplySetting", back_populates="run")
    shopee_quick_reply_preferences = relationship("ShopeeQuickReplyPreference", back_populates="run")
    shopee_quick_reply_groups = relationship("ShopeeQuickReplyGroup", back_populates="run")
    shopee_quick_reply_messages = relationship("ShopeeQuickReplyMessage", back_populates="run")


class MarketProduct(Base):
    __tablename__ = "market_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    market: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    board_type: Mapped[str] = mapped_column(String(16), nullable=False, default="sales", index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    supplier_price: Mapped[int] = mapped_column(Integer, nullable=False)
    suggested_price: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_sales: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    monthly_revenue: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    hot_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    growth_rate: Mapped[float] = mapped_column(nullable=False, default=0.0)
    competition_level: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    cover_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ProcurementOrder(Base):
    __tablename__ = "procurement_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    total_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    run = relationship("GameRun", back_populates="procurement_orders")
    items = relationship("ProcurementOrderItem", back_populates="order")
    logistics_links = relationship("LogisticsShipmentOrder", back_populates="procurement_order")


class ProcurementOrderItem(Base):
    __tablename__ = "procurement_order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("procurement_orders.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("market_products.id"), nullable=False, index=True)
    product_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total: Mapped[int] = mapped_column(Integer, nullable=False)

    order = relationship("ProcurementOrder", back_populates="items")


class LogisticsShipment(Base):
    __tablename__ = "logistics_shipments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(16), nullable=False, default="MY")
    forwarder_key: Mapped[str] = mapped_column(String(32), nullable=False)
    forwarder_label: Mapped[str] = mapped_column(String(64), nullable=False)
    customs_key: Mapped[str] = mapped_column(String(32), nullable=False)
    customs_label: Mapped[str] = mapped_column(String(64), nullable=False)
    cargo_value: Mapped[int] = mapped_column(Integer, nullable=False)
    logistics_fee: Mapped[int] = mapped_column(Integer, nullable=False)
    customs_fee: Mapped[int] = mapped_column(Integer, nullable=False)
    total_fee: Mapped[int] = mapped_column(Integer, nullable=False)
    transport_days: Mapped[int] = mapped_column(Integer, nullable=False)
    customs_days: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    run = relationship("GameRun", back_populates="logistics_shipments")
    orders = relationship("LogisticsShipmentOrder", back_populates="shipment")
    inbound_orders = relationship("WarehouseInboundOrder", back_populates="shipment")


class LogisticsShipmentOrder(Base):
    __tablename__ = "logistics_shipment_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("logistics_shipments.id"), nullable=False, index=True)
    procurement_order_id: Mapped[int] = mapped_column(ForeignKey("procurement_orders.id"), nullable=False, index=True)
    order_total_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    order_total_quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    shipment = relationship("LogisticsShipment", back_populates="orders")
    procurement_order = relationship("ProcurementOrder", back_populates="logistics_links")


class WarehouseStrategy(Base):
    __tablename__ = "warehouse_strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(16), nullable=False, default="MY")
    warehouse_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    warehouse_location: Mapped[str] = mapped_column(String(32), nullable=False)
    one_time_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inbound_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rent_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivery_eta_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fulfillment_accuracy: Mapped[float] = mapped_column(nullable=False, default=0.0)
    warehouse_cost_per_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    inbound_orders = relationship("WarehouseInboundOrder", back_populates="strategy")


class WarehouseInboundOrder(Base):
    __tablename__ = "warehouse_inbound_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    strategy_id: Mapped[int] = mapped_column(ForeignKey("warehouse_strategies.id"), nullable=False, index=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("logistics_shipments.id"), nullable=False, unique=True, index=True)
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    total_value: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="completed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    strategy = relationship("WarehouseStrategy", back_populates="inbound_orders")
    shipment = relationship("LogisticsShipment", back_populates="inbound_orders")
    inventory_lots = relationship("InventoryLot", back_populates="inbound_order")


class InventoryLot(Base):
    __tablename__ = "inventory_lots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("market_products.id"), nullable=False, index=True)
    inbound_order_id: Mapped[int] = mapped_column(ForeignKey("warehouse_inbound_orders.id"), nullable=False, index=True)
    quantity_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_locked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    backorder_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    last_restocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    inbound_order = relationship("WarehouseInboundOrder", back_populates="inventory_lots")


class InventoryStockMovement(Base):
    __tablename__ = "inventory_stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("market_products.id"), nullable=True, index=True)
    listing_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_listings.id"), nullable=True, index=True)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_listing_variants.id"), nullable=True, index=True)
    inventory_lot_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_lots.id"), nullable=True, index=True)
    biz_order_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_orders.id"), nullable=True, index=True)
    movement_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    qty_delta_on_hand: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qty_delta_reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qty_delta_backorder: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    biz_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )


class ShopeeListing(Base):
    __tablename__ = "shopee_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("market_products.id"), nullable=True, index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_category_nodes.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gtin: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sku_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    original_price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sales_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stock_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_purchase_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_purchase_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_purchase_mode: Mapped[str] = mapped_column(String(24), nullable=False, default="none")
    max_purchase_period_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    max_purchase_period_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    max_purchase_period_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_purchase_period_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_purchase_period_model: Mapped[str | None] = mapped_column(String(24), nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    parcel_length_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parcel_width_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parcel_height_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shipping_variation_dimension_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    shipping_standard_bulk: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    shipping_standard: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    shipping_express: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    preorder_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    insurance_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    condition_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    schedule_publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    parent_sku: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="live", index=True)
    quality_status: Mapped[str] = mapped_column(String(64), nullable=False, default="内容合格")
    quality_total_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quality_score_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_listings")
    images = relationship("ShopeeListingImage", back_populates="listing", cascade="all, delete-orphan")
    specs = relationship("ShopeeListingSpecValue", back_populates="listing", cascade="all, delete-orphan")
    variants = relationship("ShopeeListingVariant", back_populates="listing", cascade="all, delete-orphan")
    wholesale_tiers = relationship("ShopeeListingWholesaleTier", back_populates="listing", cascade="all, delete-orphan")
    quality_scores = relationship("ShopeeListingQualityScore", back_populates="listing", cascade="all, delete-orphan")


class ShopeeListingQualityScore(Base):
    __tablename__ = "shopee_listing_quality_scores"
    __table_args__ = (
        Index("ix_shopee_listing_quality_scores_listing_latest", "listing_id", "is_latest"),
        Index("ix_shopee_listing_quality_scores_run_user_created", "run_id", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("shopee_listings.id"), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    score_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    text_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    vision_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rule_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vision_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    text_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consistency_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quality_status: Mapped[str] = mapped_column(String(32), nullable=False, default="内容待完善")
    reasons_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    suggestions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    raw_result_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    listing = relationship("ShopeeListing", back_populates="quality_scores")


class ShopeeListingDraft(Base):
    __tablename__ = "shopee_listing_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_category_nodes.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gtin: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="drafting", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_listing_drafts")
    images = relationship("ShopeeListingDraftImage", back_populates="draft", cascade="all, delete-orphan")
    specs = relationship("ShopeeListingDraftSpecValue", back_populates="draft", cascade="all, delete-orphan")


class ShopeeListingDraftImage(Base):
    __tablename__ = "shopee_listing_draft_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("shopee_listing_drafts.id"), nullable=False, index=True)
    image_url: Mapped[str] = mapped_column(String(255), nullable=False)
    image_ratio: Mapped[str] = mapped_column(String(16), nullable=False, default="1:1")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_cover: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    draft = relationship("ShopeeListingDraft", back_populates="images")


class ShopeeSpecTemplate(Base):
    __tablename__ = "shopee_spec_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Backward-compatible with legacy schema; new logic uses category_id.
    category_root: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    category_id: Mapped[int] = mapped_column(ForeignKey("shopee_category_nodes.id"), nullable=False, index=True)
    field_key: Mapped[str] = mapped_column("attr_key", String(64), nullable=False, index=True)
    field_label: Mapped[str] = mapped_column("attr_label", String(128), nullable=False)
    field_type: Mapped[str] = mapped_column("input_type", String(16), nullable=False, default="select")
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    options = relationship("ShopeeSpecTemplateOption", back_populates="template", cascade="all, delete-orphan")


class ShopeeSpecTemplateOption(Base):
    __tablename__ = "shopee_spec_template_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("shopee_spec_templates.id"), nullable=False, index=True)
    option_value: Mapped[str] = mapped_column(String(128), nullable=False)
    option_label: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    template = relationship("ShopeeSpecTemplate", back_populates="options")


class ShopeeCategoryNode(Base):
    __tablename__ = "shopee_category_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_category_nodes.id"), nullable=True, index=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ShopeeListingDraftSpecValue(Base):
    __tablename__ = "shopee_listing_draft_spec_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("shopee_listing_drafts.id"), nullable=False, index=True)
    attr_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    attr_label: Mapped[str] = mapped_column(String(128), nullable=False)
    attr_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    draft = relationship("ShopeeListingDraft", back_populates="specs")


class ShopeeListingSpecValue(Base):
    __tablename__ = "shopee_listing_spec_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("shopee_listings.id"), nullable=False, index=True)
    attr_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    attr_label: Mapped[str] = mapped_column(String(128), nullable=False)
    attr_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    listing = relationship("ShopeeListing", back_populates="specs")


class ShopeeListingImage(Base):
    __tablename__ = "shopee_listing_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("shopee_listings.id"), nullable=False, index=True)
    image_url: Mapped[str] = mapped_column(String(255), nullable=False)
    image_ratio: Mapped[str] = mapped_column(String(16), nullable=False, default="1:1")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_cover: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    listing = relationship("ShopeeListing", back_populates="images")


class ShopeeListingVariant(Base):
    __tablename__ = "shopee_listing_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("shopee_listings.id"), nullable=False, index=True)
    variant_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    option_value: Mapped[str] = mapped_column(String(128), nullable=False)
    option_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sales_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    oversell_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=2000)
    oversell_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sku: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gtin: Mapped[str | None] = mapped_column(String(64), nullable=True)
    item_without_gtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    parcel_length_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parcel_width_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parcel_height_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    listing = relationship("ShopeeListing", back_populates="variants")


class ShopeeListingWholesaleTier(Base):
    __tablename__ = "shopee_listing_wholesale_tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("shopee_listings.id"), nullable=False, index=True)
    tier_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    min_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    listing = relationship("ShopeeListing", back_populates="wholesale_tiers")


class ShopeeOrder(Base):
    __tablename__ = "shopee_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    order_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    buyer_name: Mapped[str] = mapped_column(String(64), nullable=False)
    buyer_payment: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    order_type: Mapped[str] = mapped_column(String(24), nullable=False, default="order", index=True)
    listing_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_listings.id"), nullable=True, index=True)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_listing_variants.id"), nullable=True, index=True)
    type_bucket: Mapped[str] = mapped_column(String(24), nullable=False, default="toship", index=True)
    process_status: Mapped[str] = mapped_column(String(24), nullable=False, default="processing", index=True)
    stock_fulfillment_status: Mapped[str] = mapped_column(String(24), nullable=False, default="in_stock", index=True)
    backorder_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    must_restock_before_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    shipping_priority: Mapped[str] = mapped_column(String(24), nullable=False, default="today", index=True)
    shipping_channel: Mapped[str] = mapped_column(String(64), nullable=False, default="SPX快递")
    delivery_line_key: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    delivery_line_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    destination: Mapped[str] = mapped_column(String(128), nullable=False, default="吉隆坡")
    countdown_text: Mapped[str] = mapped_column(String(128), nullable=False, default="请在今日内处理")
    action_text: Mapped[str] = mapped_column(String(64), nullable=False, default="查看详情")
    ship_by_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    tracking_no: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    waybill_no: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    ship_by_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    eta_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    eta_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    cancel_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cancel_source: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    marketing_campaign_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    marketing_campaign_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    marketing_campaign_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    order_subtotal_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    voucher_campaign_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    voucher_campaign_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    voucher_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    voucher_code_snapshot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    voucher_discount_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    shipping_promotion_campaign_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    shipping_promotion_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shipping_promotion_tier_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shipping_fee_before_promotion: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    shipping_fee_after_promotion: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    shipping_promotion_discount_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_orders")
    items = relationship("ShopeeOrderItem", back_populates="order")
    logistics_events = relationship("ShopeeOrderLogisticsEvent", back_populates="order")
    settlement = relationship("ShopeeOrderSettlement", back_populates="order", uselist=False)
    finance_ledger_entries = relationship("ShopeeFinanceLedgerEntry", back_populates="order")


class ShopeeOrderItem(Base):
    __tablename__ = "shopee_order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("shopee_orders.id"), nullable=False, index=True)
    listing_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_listings.id"), nullable=True, index=True)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_listing_variants.id"), nullable=True, index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("market_products.id"), nullable=True, index=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    variant_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stock_fulfillment_status: Mapped[str] = mapped_column(String(24), nullable=False, default="in_stock")
    backorder_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    marketing_campaign_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    marketing_campaign_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    marketing_campaign_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    line_role: Mapped[str] = mapped_column(String(32), nullable=False, default="main", index=True)
    original_unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    discounted_unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    order = relationship("ShopeeOrder", back_populates="items")


class ShopeeOrderLogisticsEvent(Base):
    __tablename__ = "shopee_order_logistics_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("shopee_orders.id"), nullable=False, index=True)
    event_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    event_title: Mapped[str] = mapped_column(String(64), nullable=False)
    event_desc: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_order_logistics_events")
    order = relationship("ShopeeOrder", back_populates="logistics_events")


class ShopeeOrderSettlement(Base):
    __tablename__ = "shopee_order_settlements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("shopee_orders.id"), nullable=False, unique=True, index=True)
    buyer_payment: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    platform_commission_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    payment_fee_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    shipping_cost_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    shipping_subsidy_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    shipping_promotion_discount_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    net_income_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    settlement_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", index=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_order_settlements")
    order = relationship("ShopeeOrder", back_populates="settlement")


class ShopeeOrderGenerationLog(Base):
    __tablename__ = "shopee_order_generation_logs"
    __table_args__ = (
        Index(
            "ix_shopee_order_generation_logs_run_user_tick_id",
            "run_id",
            "user_id",
            "tick_time",
            "id",
        ),
        Index(
            "ix_shopee_order_generation_logs_run_user_created_at",
            "run_id",
            "user_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    tick_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    active_buyer_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    candidate_product_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generated_order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skip_reasons_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    debug_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_order_generation_logs")


class ShopeeFinanceLedgerEntry(Base):
    __tablename__ = "shopee_finance_ledger_entries"
    __table_args__ = (
        UniqueConstraint("order_id", "entry_type", name="uq_shopee_finance_ledger_order_entry_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_orders.id"), nullable=True, index=True)
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True, default="income_from_order")
    direction: Mapped[str] = mapped_column(String(8), nullable=False, index=True, default="in")
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    balance_after: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True, default="completed")
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_finance_ledger_entries")
    order = relationship("ShopeeOrder", back_populates="finance_ledger_entries")


class GameRunCashAdjustment(Base):
    __tablename__ = "game_run_cash_adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True, default="manual_adjustment")
    direction: Mapped[str] = mapped_column(String(8), nullable=False, index=True, default="in")
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)
    related_ledger_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_finance_ledger_entries.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    run = relationship("GameRun", back_populates="cash_adjustments")


class ShopeeBankAccount(Base):
    __tablename__ = "shopee_bank_accounts"
    __table_args__ = (
        UniqueConstraint("run_id", "user_id", "account_no", name="uq_shopee_bank_accounts_run_user_account"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    bank_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    account_holder: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    account_no: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    account_no_masked: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="RM")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    verify_status: Mapped[str] = mapped_column(String(16), nullable=False, default="verified", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_bank_accounts")


class ShopeeMarketingAnnouncement(Base):
    __tablename__ = "shopee_marketing_announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    market: Mapped[str] = mapped_column(String(16), nullable=False, index=True, default="MY")
    lang: Mapped[str] = mapped_column(String(16), nullable=False, index=True, default="zh-CN")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    badge_text: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="published", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ShopeeMarketingTool(Base):
    __tablename__ = "shopee_marketing_tools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tool_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    tag_type: Mapped[str] = mapped_column(String(64), nullable=False, default="boost_sales")
    description: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    icon_key: Mapped[str] = mapped_column(String(64), nullable=False, default="megaphone")
    target_route: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ShopeeMarketingEvent(Base):
    __tablename__ = "shopee_marketing_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    market: Mapped[str] = mapped_column(String(16), nullable=False, index=True, default="MY")
    lang: Mapped[str] = mapped_column(String(16), nullable=False, index=True, default="zh-CN")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    image_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    jump_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ongoing", index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ShopeeUserMarketingPreference(Base):
    __tablename__ = "shopee_user_marketing_preferences"
    __table_args__ = (
        UniqueConstraint("run_id", "user_id", name="uq_shopee_user_marketing_preferences_run_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    tools_collapsed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_marketing_preferences")


class ShopeeDiscountCampaign(Base):
    __tablename__ = "shopee_discount_campaigns"
    __table_args__ = (
        Index("ix_shopee_discount_campaigns_run_user_status", "run_id", "user_id", "campaign_status"),
        Index("ix_shopee_discount_campaigns_run_user_type", "run_id", "user_id", "campaign_type"),
        Index("ix_shopee_discount_campaigns_run_user_start", "run_id", "user_id", "start_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    campaign_type: Mapped[str] = mapped_column(String(32), nullable=False, default="discount")
    campaign_name: Mapped[str] = mapped_column(String(255), nullable=False)
    campaign_status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    market: Mapped[str] = mapped_column(String(16), nullable=False, default="MY")
    currency: Mapped[str] = mapped_column(String(16), nullable=False, default="RM")
    rules_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    share_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_campaign_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_discount_campaigns")
    items = relationship("ShopeeDiscountCampaignItem", back_populates="campaign", cascade="all, delete-orphan")
    performance_daily = relationship("ShopeeDiscountPerformanceDaily", back_populates="campaign", cascade="all, delete-orphan")


class ShopeeDiscountCampaignItem(Base):
    __tablename__ = "shopee_discount_campaign_items"
    __table_args__ = (
        Index("ix_shopee_discount_campaign_items_campaign_sort", "campaign_id", "sort_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("shopee_discount_campaigns.id"), nullable=False, index=True)
    listing_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_listings.id"), nullable=True, index=True)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_listing_variants.id"), nullable=True, index=True)
    product_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    image_url_snapshot: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    sku_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    original_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    discount_type: Mapped[str] = mapped_column(String(32), nullable=False, default="percent")
    discount_value: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    final_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    campaign = relationship("ShopeeDiscountCampaign", back_populates="items")


class ShopeeDiscountPerformanceDaily(Base):
    __tablename__ = "shopee_discount_performance_daily"
    __table_args__ = (
        UniqueConstraint("campaign_id", "stat_date", name="uq_shopee_discount_performance_daily_campaign_date"),
        Index("ix_shopee_discount_performance_daily_run_user_date", "run_id", "user_id", "stat_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("shopee_discount_campaigns.id"), nullable=False, index=True)
    stat_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    sales_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    orders_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    units_sold: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    buyers_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    campaign = relationship("ShopeeDiscountCampaign", back_populates="performance_daily")


class ShopeeUserDiscountPreference(Base):
    __tablename__ = "shopee_user_discount_preferences"
    __table_args__ = (
        UniqueConstraint("run_id", "user_id", name="uq_shopee_user_discount_preferences_run_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    selected_discount_type: Mapped[str] = mapped_column(String(32), nullable=False, default="all")
    selected_status: Mapped[str] = mapped_column(String(32), nullable=False, default="all")
    search_field: Mapped[str] = mapped_column(String(32), nullable=False, default="campaign_name")
    keyword: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    date_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_discount_preferences")


class ShopeeDiscountDraft(Base):
    __tablename__ = "shopee_discount_drafts"
    __table_args__ = (
        Index("ix_shopee_discount_drafts_run_user_type", "run_id", "user_id", "campaign_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    campaign_type: Mapped[str] = mapped_column(String(32), nullable=False, default="discount")
    campaign_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    source_campaign_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_discount_drafts")
    items = relationship("ShopeeDiscountDraftItem", back_populates="draft", cascade="all, delete-orphan")


class ShopeeDiscountDraftItem(Base):
    __tablename__ = "shopee_discount_draft_items"
    __table_args__ = (
        Index("ix_shopee_discount_draft_items_draft_sort", "draft_id", "sort_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("shopee_discount_drafts.id"), nullable=False, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("shopee_listings.id"), nullable=False, index=True)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_listing_variants.id"), nullable=True, index=True)
    product_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    image_url_snapshot: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    sku_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    original_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    discount_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="percent")
    discount_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_stock_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    draft = relationship("ShopeeDiscountDraft", back_populates="items")


class ShopeeShopVoucherCampaign(Base):
    __tablename__ = "shopee_shop_voucher_campaigns"
    __table_args__ = (
        Index("ix_shopee_shop_vouchers_run_user_status", "run_id", "user_id", "status"),
        Index("ix_shopee_shop_vouchers_run_user_time", "run_id", "user_id", "start_at", "end_at"),
        Index("ix_shopee_shop_vouchers_run_user_code", "run_id", "user_id", "voucher_code", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    voucher_type: Mapped[str] = mapped_column(String(32), nullable=False, default="shop_voucher")
    voucher_name: Mapped[str] = mapped_column(String(255), nullable=False)
    voucher_code: Mapped[str] = mapped_column(String(32), nullable=False)
    code_prefix: Mapped[str] = mapped_column(String(16), nullable=False, default="HOME")
    code_suffix: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="upcoming", index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    display_before_start: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reward_type: Mapped[str] = mapped_column(String(32), nullable=False, default="discount")
    discount_type: Mapped[str] = mapped_column(String(32), nullable=False, default="fixed_amount")
    discount_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_discount_type: Mapped[str] = mapped_column(String(32), nullable=False, default="set_amount")
    max_discount_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_spend_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    usage_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    per_buyer_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    display_type: Mapped[str] = mapped_column(String(32), nullable=False, default="all_pages")
    display_channels: Mapped[str | None] = mapped_column(Text, nullable=True)
    applicable_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="all_shop_products")
    sales_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    buyer_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_shop_voucher_campaigns")


class ShopeeProductVoucherCampaign(Base):
    __tablename__ = "shopee_product_voucher_campaigns"
    __table_args__ = (
        Index("ix_shopee_product_vouchers_run_user_status", "run_id", "user_id", "status"),
        Index("ix_shopee_product_vouchers_run_user_time", "run_id", "user_id", "start_at", "end_at"),
        Index("ix_shopee_product_vouchers_run_user_code", "run_id", "user_id", "voucher_code", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    voucher_type: Mapped[str] = mapped_column(String(32), nullable=False, default="product_voucher")
    voucher_name: Mapped[str] = mapped_column(String(255), nullable=False)
    voucher_code: Mapped[str] = mapped_column(String(32), nullable=False)
    code_prefix: Mapped[str] = mapped_column(String(16), nullable=False, default="HOME")
    code_suffix: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="upcoming", index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    display_before_start: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reward_type: Mapped[str] = mapped_column(String(32), nullable=False, default="discount")
    discount_type: Mapped[str] = mapped_column(String(32), nullable=False, default="fixed_amount")
    discount_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_discount_type: Mapped[str] = mapped_column(String(32), nullable=False, default="set_amount")
    max_discount_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_spend_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    usage_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    per_buyer_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    display_type: Mapped[str] = mapped_column(String(32), nullable=False, default="all_pages")
    display_channels: Mapped[str | None] = mapped_column(Text, nullable=True)
    applicable_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="selected_products")
    selected_product_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sales_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    buyer_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_product_voucher_campaigns")
    items = relationship("ShopeeProductVoucherItem", back_populates="campaign", cascade="all, delete-orphan")


class ShopeeProductVoucherItem(Base):
    __tablename__ = "shopee_product_voucher_items"
    __table_args__ = (
        UniqueConstraint("campaign_id", "listing_id", "variant_id", name="uq_shopee_product_voucher_item_variant"),
        Index("ix_shopee_product_voucher_items_campaign", "campaign_id"),
        Index("ix_shopee_product_voucher_items_listing", "run_id", "user_id", "listing_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("shopee_product_voucher_campaigns.id"), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("shopee_listings.id"), nullable=False, index=True)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_listing_variants.id"), nullable=True, index=True)
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    product_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    variant_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sku_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    image_url_snapshot: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    category_key_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    category_label_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_price_snapshot: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    stock_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    campaign = relationship("ShopeeProductVoucherCampaign", back_populates="items")


class ShopeePrivateVoucherCampaign(Base):
    __tablename__ = "shopee_private_voucher_campaigns"
    __table_args__ = (
        Index("ix_shopee_private_vouchers_run_user_status", "run_id", "user_id", "status"),
        Index("ix_shopee_private_vouchers_run_user_time", "run_id", "user_id", "start_at", "end_at"),
        Index("ix_shopee_private_vouchers_run_user_code", "run_id", "user_id", "voucher_code", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    voucher_type: Mapped[str] = mapped_column(String(32), nullable=False, default="private_voucher")
    voucher_name: Mapped[str] = mapped_column(String(255), nullable=False)
    voucher_code: Mapped[str] = mapped_column(String(32), nullable=False)
    code_prefix: Mapped[str] = mapped_column(String(16), nullable=False, default="HOME")
    code_suffix: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="upcoming", index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    reward_type: Mapped[str] = mapped_column(String(32), nullable=False, default="discount")
    discount_type: Mapped[str] = mapped_column(String(32), nullable=False, default="fixed_amount")
    discount_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_discount_type: Mapped[str] = mapped_column(String(32), nullable=False, default="set_amount")
    max_discount_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_spend_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    usage_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    per_buyer_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    display_type: Mapped[str] = mapped_column(String(32), nullable=False, default="code_only")
    applicable_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="all_products")
    selected_product_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    audience_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="private_code")
    audience_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    sales_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    buyer_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_private_voucher_campaigns")
    items = relationship("ShopeePrivateVoucherItem", back_populates="campaign", cascade="all, delete-orphan")


class ShopeePrivateVoucherItem(Base):
    __tablename__ = "shopee_private_voucher_items"
    __table_args__ = (
        UniqueConstraint("campaign_id", "listing_id", "variant_id", name="uq_shopee_private_voucher_item_variant"),
        Index("ix_shopee_private_voucher_items_campaign", "campaign_id"),
        Index("ix_shopee_private_voucher_items_listing", "run_id", "user_id", "listing_id"),
        Index("ix_shopee_private_voucher_items_product", "product_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("shopee_private_voucher_campaigns.id"), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("shopee_listings.id"), nullable=False, index=True)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_listing_variants.id"), nullable=True, index=True)
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    product_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    variant_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sku_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    image_url_snapshot: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    category_key_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    category_label_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_price_snapshot: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    stock_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    campaign = relationship("ShopeePrivateVoucherCampaign", back_populates="items")


class ShopeeLiveVoucherCampaign(Base):
    __tablename__ = "shopee_live_voucher_campaigns"
    __table_args__ = (
        Index("ix_shopee_live_vouchers_run_user_status", "run_id", "user_id", "status"),
        Index("ix_shopee_live_vouchers_run_user_time", "run_id", "user_id", "start_at", "end_at"),
        Index("ix_shopee_live_vouchers_run_user_code", "run_id", "user_id", "voucher_code", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    voucher_type: Mapped[str] = mapped_column(String(32), nullable=False, default="live_voucher")
    voucher_name: Mapped[str] = mapped_column(String(255), nullable=False)
    voucher_code: Mapped[str] = mapped_column(String(32), nullable=False)
    code_prefix: Mapped[str] = mapped_column(String(16), nullable=False, default="HOME")
    code_suffix: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="upcoming", index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    display_before_start: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reward_type: Mapped[str] = mapped_column(String(32), nullable=False, default="discount")
    discount_type: Mapped[str] = mapped_column(String(32), nullable=False, default="fixed_amount")
    discount_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_discount_type: Mapped[str] = mapped_column(String(32), nullable=False, default="set_amount")
    max_discount_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_spend_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    usage_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    per_buyer_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    display_type: Mapped[str] = mapped_column(String(32), nullable=False, default="live_stream")
    display_channels: Mapped[str | None] = mapped_column(Text, nullable=True)
    applicable_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="all_products")
    selected_product_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    live_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="all_live_sessions")
    live_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    sales_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    buyer_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_live_voucher_campaigns")
    items = relationship("ShopeeLiveVoucherItem", back_populates="campaign", cascade="all, delete-orphan")


class ShopeeLiveVoucherItem(Base):
    __tablename__ = "shopee_live_voucher_items"
    __table_args__ = (
        UniqueConstraint("campaign_id", "listing_id", "variant_id", name="uq_shopee_live_voucher_item_variant"),
        Index("ix_shopee_live_voucher_items_campaign", "campaign_id"),
        Index("ix_shopee_live_voucher_items_listing", "run_id", "user_id", "listing_id"),
        Index("ix_shopee_live_voucher_items_product", "product_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("shopee_live_voucher_campaigns.id"), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("shopee_listings.id"), nullable=False, index=True)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_listing_variants.id"), nullable=True, index=True)
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    product_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    variant_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sku_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    image_url_snapshot: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    category_key_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    category_label_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_price_snapshot: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    stock_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    campaign = relationship("ShopeeLiveVoucherCampaign", back_populates="items")


class ShopeeVideoVoucherCampaign(Base):
    __tablename__ = "shopee_video_voucher_campaigns"
    __table_args__ = (
        Index("ix_shopee_video_vouchers_run_user_status", "run_id", "user_id", "status"),
        Index("ix_shopee_video_vouchers_run_user_time", "run_id", "user_id", "start_at", "end_at"),
        Index("ix_shopee_video_vouchers_run_user_code", "run_id", "user_id", "voucher_code", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    voucher_type: Mapped[str] = mapped_column(String(32), nullable=False, default="video_voucher")
    voucher_name: Mapped[str] = mapped_column(String(255), nullable=False)
    voucher_code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="upcoming", index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    display_before_start: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reward_type: Mapped[str] = mapped_column(String(32), nullable=False, default="discount")
    discount_type: Mapped[str] = mapped_column(String(32), nullable=False, default="fixed_amount")
    discount_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_discount_type: Mapped[str] = mapped_column(String(32), nullable=False, default="set_amount")
    max_discount_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_spend_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    usage_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    per_buyer_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    display_type: Mapped[str] = mapped_column(String(32), nullable=False, default="video_stream")
    display_channels: Mapped[str | None] = mapped_column(Text, nullable=True)
    applicable_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="all_products")
    selected_product_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    video_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="all_videos")
    video_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    sales_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    buyer_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_video_voucher_campaigns")
    items = relationship("ShopeeVideoVoucherItem", back_populates="campaign", cascade="all, delete-orphan")


class ShopeeFollowVoucherCampaign(Base):
    __tablename__ = "shopee_follow_voucher_campaigns"
    __table_args__ = (
        Index("ix_shopee_follow_vouchers_run_user_status", "run_id", "user_id", "status"),
        Index("ix_shopee_follow_vouchers_run_user_claim_time", "run_id", "user_id", "claim_start_at", "claim_end_at"),
        Index("ix_shopee_follow_vouchers_run_user_code", "run_id", "user_id", "voucher_code", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    voucher_type: Mapped[str] = mapped_column(String(32), nullable=False, default="follow_voucher")
    voucher_name: Mapped[str] = mapped_column(String(255), nullable=False)
    voucher_code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="upcoming", index=True)
    claim_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    claim_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    valid_days_after_claim: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    reward_type: Mapped[str] = mapped_column(String(32), nullable=False, default="discount")
    discount_type: Mapped[str] = mapped_column(String(32), nullable=False, default="fixed_amount")
    discount_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_discount_type: Mapped[str] = mapped_column(String(32), nullable=False, default="set_amount")
    max_discount_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_spend_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    usage_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    claimed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    per_buyer_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False, default="follow_shop")
    display_type: Mapped[str] = mapped_column(String(32), nullable=False, default="follow_reward")
    display_channels: Mapped[str | None] = mapped_column(Text, nullable=True)
    applicable_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="all_products")
    sales_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    buyer_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_follow_voucher_campaigns")


class ShopeeBuyerFollowState(Base):
    __tablename__ = "shopee_buyer_follow_states"
    __table_args__ = (
        UniqueConstraint("run_id", "user_id", "buyer_name", name="uq_shopee_buyer_follow_states_run_user_buyer"),
        Index("ix_shopee_buyer_follow_states_run_user", "run_id", "user_id"),
        Index("ix_shopee_buyer_follow_states_source_campaign", "source_campaign_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    buyer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_following: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    first_followed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    follow_source: Mapped[str] = mapped_column(String(32), nullable=False, default="follow_voucher")
    source_campaign_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_buyer_follow_states")


class ShopeeAutoReplySetting(Base):
    __tablename__ = "shopee_auto_reply_settings"
    __table_args__ = (
        UniqueConstraint("run_id", "user_id", "reply_type", name="uq_shopee_auto_reply_settings_run_user_type"),
        Index("ix_shopee_auto_reply_settings_run_user_enabled", "run_id", "user_id", "enabled"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    reply_type: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    work_time_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    work_start_time: Mapped[str | None] = mapped_column(String(8), nullable=True)
    work_end_time: Mapped[str | None] = mapped_column(String(8), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="game_time")
    trigger_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=1440)
    trigger_once_per_game_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_sent_game_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_auto_reply_settings")


class ShopeeQuickReplyPreference(Base):
    __tablename__ = "shopee_quick_reply_preferences"
    __table_args__ = (
        UniqueConstraint("run_id", "user_id", name="uq_shopee_quick_reply_preferences_run_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    auto_hint_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_quick_reply_preferences")


class ShopeeQuickReplyGroup(Base):
    __tablename__ = "shopee_quick_reply_groups"
    __table_args__ = (
        Index("ix_shopee_quick_reply_groups_run_user_sort", "run_id", "user_id", "sort_order"),
        Index("ix_shopee_quick_reply_groups_run_user_enabled", "run_id", "user_id", "enabled"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    group_name: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_quick_reply_groups")
    messages = relationship("ShopeeQuickReplyMessage", back_populates="group", cascade="all, delete-orphan")


class ShopeeQuickReplyMessage(Base):
    __tablename__ = "shopee_quick_reply_messages"
    __table_args__ = (
        Index("ix_shopee_quick_reply_messages_group_sort", "group_id", "sort_order"),
        Index("ix_shopee_quick_reply_messages_run_user", "run_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("shopee_quick_reply_groups.id"), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    tags_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_quick_reply_messages")
    group = relationship("ShopeeQuickReplyGroup", back_populates="messages")


class ShopeeShippingFeePromotionCampaign(Base):
    __tablename__ = "shopee_shipping_fee_promotion_campaigns"
    __table_args__ = (
        Index("ix_shopee_shipping_fee_promotions_run_user_status", "run_id", "user_id", "status"),
        Index("ix_shopee_shipping_fee_promotions_run_user_time", "run_id", "user_id", "start_at", "end_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    promotion_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ongoing", index=True)
    period_type: Mapped[str] = mapped_column(String(32), nullable=False, default="no_limit")
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    budget_type: Mapped[str] = mapped_column(String(32), nullable=False, default="no_limit")
    budget_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    budget_used: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    buyer_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sales_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    shipping_discount_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_shipping_fee_promotion_campaigns")
    channels = relationship("ShopeeShippingFeePromotionChannel", back_populates="campaign", cascade="all, delete-orphan")
    tiers = relationship("ShopeeShippingFeePromotionTier", back_populates="campaign", cascade="all, delete-orphan")


class ShopeeShippingFeePromotionChannel(Base):
    __tablename__ = "shopee_shipping_fee_promotion_channels"
    __table_args__ = (
        UniqueConstraint("campaign_id", "channel_key", name="uq_shopee_shipping_fee_promotion_channel"),
        Index("ix_shopee_shipping_fee_promotion_channels_campaign", "campaign_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("shopee_shipping_fee_promotion_campaigns.id"), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    channel_key: Mapped[str] = mapped_column(String(32), nullable=False)
    channel_label: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    campaign = relationship("ShopeeShippingFeePromotionCampaign", back_populates="channels")


class ShopeeShippingFeePromotionTier(Base):
    __tablename__ = "shopee_shipping_fee_promotion_tiers"
    __table_args__ = (
        UniqueConstraint("campaign_id", "tier_index", name="uq_shopee_shipping_fee_promotion_tier_index"),
        UniqueConstraint("campaign_id", "min_spend_amount", name="uq_shopee_shipping_fee_promotion_tier_min_spend"),
        Index("ix_shopee_shipping_fee_promotion_tiers_campaign", "campaign_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("shopee_shipping_fee_promotion_campaigns.id"), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    tier_index: Mapped[int] = mapped_column(Integer, nullable=False)
    min_spend_amount: Mapped[float] = mapped_column(Float, nullable=False)
    fee_type: Mapped[str] = mapped_column(String(32), nullable=False)
    fixed_fee_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    campaign = relationship("ShopeeShippingFeePromotionCampaign", back_populates="tiers")


class ShopeeVideoVoucherItem(Base):
    __tablename__ = "shopee_video_voucher_items"
    __table_args__ = (
        UniqueConstraint("campaign_id", "listing_id", "variant_id", name="uq_shopee_video_voucher_item_variant"),
        Index("ix_shopee_video_voucher_items_campaign", "campaign_id"),
        Index("ix_shopee_video_voucher_items_listing", "run_id", "user_id", "listing_id"),
        Index("ix_shopee_video_voucher_items_product", "product_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("shopee_video_voucher_campaigns.id"), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("shopee_listings.id"), nullable=False, index=True)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_listing_variants.id"), nullable=True, index=True)
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    product_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    variant_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sku_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    image_url_snapshot: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    category_key_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    category_label_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_price_snapshot: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    stock_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    campaign = relationship("ShopeeVideoVoucherCampaign", back_populates="items")


class ShopeeAddonCampaign(Base):
    __tablename__ = "shopee_addon_campaigns"
    __table_args__ = (
        Index("ix_shopee_addon_campaigns_run_user_status", "run_id", "user_id", "campaign_status"),
        Index("ix_shopee_addon_campaigns_run_user_type", "run_id", "user_id", "promotion_type"),
        Index("ix_shopee_addon_campaigns_run_user_time", "run_id", "user_id", "start_at", "end_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    campaign_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    campaign_name: Mapped[str] = mapped_column(String(64), nullable=False)
    promotion_type: Mapped[str] = mapped_column(String(16), nullable=False, default="add_on", index=True)
    campaign_status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    addon_purchase_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gift_min_spend: Mapped[float | None] = mapped_column(Float, nullable=True)
    market: Mapped[str] = mapped_column(String(16), nullable=False, default="MY")
    currency: Mapped[str] = mapped_column(String(16), nullable=False, default="RM")
    rules_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    source_campaign_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_addon_campaigns")
    main_items = relationship("ShopeeAddonCampaignMainItem", back_populates="campaign", cascade="all, delete-orphan")
    reward_items = relationship("ShopeeAddonCampaignRewardItem", back_populates="campaign", cascade="all, delete-orphan")


class ShopeeAddonCampaignMainItem(Base):
    __tablename__ = "shopee_addon_campaign_main_items"
    __table_args__ = (
        UniqueConstraint("campaign_id", "listing_id", "variant_id", name="uq_shopee_addon_main_campaign_listing_variant"),
        Index("ix_shopee_addon_main_items_campaign_sort", "campaign_id", "sort_order"),
        Index("ix_shopee_addon_main_items_run_listing", "run_id", "listing_id", "variant_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("shopee_addon_campaigns.id"), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("shopee_listings.id"), nullable=False, index=True)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_listing_variants.id"), nullable=True, index=True)
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    product_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    variant_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sku_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    image_url_snapshot: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    original_price_snapshot: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    stock_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    campaign = relationship("ShopeeAddonCampaign", back_populates="main_items")


class ShopeeAddonCampaignRewardItem(Base):
    __tablename__ = "shopee_addon_campaign_reward_items"
    __table_args__ = (
        UniqueConstraint("campaign_id", "listing_id", "variant_id", name="uq_shopee_addon_reward_campaign_listing_variant"),
        Index("ix_shopee_addon_reward_items_campaign_sort", "campaign_id", "sort_order"),
        Index("ix_shopee_addon_reward_items_run_listing", "run_id", "listing_id", "variant_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("shopee_addon_campaigns.id"), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("shopee_listings.id"), nullable=False, index=True)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_listing_variants.id"), nullable=True, index=True)
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    product_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    variant_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sku_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    image_url_snapshot: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    original_price_snapshot: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    addon_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    reward_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    stock_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    campaign = relationship("ShopeeAddonCampaign", back_populates="reward_items")


class ShopeeAddonDraft(Base):
    __tablename__ = "shopee_addon_drafts"
    __table_args__ = (
        Index("ix_shopee_addon_drafts_run_user_type", "run_id", "user_id", "promotion_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    promotion_type: Mapped[str] = mapped_column(String(16), nullable=False, default="add_on", index=True)
    campaign_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    addon_purchase_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gift_min_spend: Mapped[float | None] = mapped_column(Float, nullable=True)
    draft_status: Mapped[str] = mapped_column(String(16), nullable=False, default="editing", index=True)
    submitted_campaign_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source_campaign_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    run = relationship("GameRun", back_populates="shopee_addon_drafts")
    main_items = relationship("ShopeeAddonDraftMainItem", back_populates="draft", cascade="all, delete-orphan")
    reward_items = relationship("ShopeeAddonDraftRewardItem", back_populates="draft", cascade="all, delete-orphan")


class ShopeeAddonDraftMainItem(Base):
    __tablename__ = "shopee_addon_draft_main_items"
    __table_args__ = (
        Index("ix_shopee_addon_draft_main_items_draft_sort", "draft_id", "sort_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("shopee_addon_drafts.id"), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("shopee_listings.id"), nullable=False, index=True)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_listing_variants.id"), nullable=True, index=True)
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    draft = relationship("ShopeeAddonDraft", back_populates="main_items")


class ShopeeAddonDraftRewardItem(Base):
    __tablename__ = "shopee_addon_draft_reward_items"
    __table_args__ = (
        Index("ix_shopee_addon_draft_reward_items_draft_sort", "draft_id", "sort_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("shopee_addon_drafts.id"), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("shopee_listings.id"), nullable=False, index=True)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_listing_variants.id"), nullable=True, index=True)
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    addon_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    reward_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    draft = relationship("ShopeeAddonDraft", back_populates="reward_items")


class ShopeeFlashSaleCampaign(Base):
    __tablename__ = "shopee_flash_sale_campaigns"
    __table_args__ = (
        Index("idx_flash_sale_campaign_run_user", "run_id", "user_id"),
        Index("idx_flash_sale_campaign_slot", "run_id", "user_id", "slot_date", "slot_key"),
        Index("idx_flash_sale_campaign_time", "run_id", "start_tick", "end_tick"),
        Index("idx_flash_sale_campaign_status", "run_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    campaign_name: Mapped[str] = mapped_column(String(100), nullable=False)
    slot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    slot_key: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    start_tick: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_tick: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    total_product_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    reminder_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    click_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sales_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    run = relationship("GameRun", back_populates="shopee_flash_sale_campaigns")
    items = relationship("ShopeeFlashSaleCampaignItem", back_populates="campaign", cascade="all, delete-orphan")


class ShopeeFlashSaleCampaignItem(Base):
    __tablename__ = "shopee_flash_sale_campaign_items"
    __table_args__ = (
        Index("idx_flash_sale_item_campaign", "campaign_id"),
        Index("idx_flash_sale_item_sku", "run_id", "listing_id", "variant_id"),
        Index("idx_flash_sale_item_user", "run_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("shopee_flash_sale_campaigns.id"), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("shopee_listings.id"), nullable=False, index=True)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_listing_variants.id"), nullable=True, index=True)
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    product_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    variant_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sku_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    image_url_snapshot: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    original_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    flash_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    discount_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    activity_stock_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sold_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    purchase_limit_per_buyer: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    campaign = relationship("ShopeeFlashSaleCampaign", back_populates="items")


class ShopeeFlashSaleTrafficEvent(Base):
    __tablename__ = "shopee_flash_sale_traffic_events"
    __table_args__ = (
        Index("idx_flash_sale_traffic_campaign_event", "run_id", "user_id", "campaign_id", "event_type", "event_tick"),
        Index("idx_flash_sale_traffic_item_buyer", "run_id", "user_id", "campaign_item_id", "buyer_code", "event_type", "event_tick"),
        Index("idx_flash_sale_traffic_listing", "run_id", "user_id", "listing_id", "variant_id", "event_type"),
        UniqueConstraint("run_id", "user_id", "campaign_item_id", "buyer_code", "event_type", "event_tick", name="uq_flash_sale_traffic_tick_buyer_item_event"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("shopee_flash_sale_campaigns.id"), nullable=False, index=True)
    campaign_item_id: Mapped[int] = mapped_column(ForeignKey("shopee_flash_sale_campaign_items.id"), nullable=False, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("shopee_listings.id"), nullable=False, index=True)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_listing_variants.id"), nullable=True, index=True)
    buyer_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    event_tick: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="simulator")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ShopeeFlashSaleDraft(Base):
    __tablename__ = "shopee_flash_sale_drafts"
    __table_args__ = (
        Index("idx_flash_sale_draft_run_user", "run_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("game_runs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    campaign_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    slot_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    slot_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    run = relationship("GameRun", back_populates="shopee_flash_sale_drafts")
    items = relationship("ShopeeFlashSaleDraftItem", back_populates="draft", cascade="all, delete-orphan")


class ShopeeFlashSaleDraftItem(Base):
    __tablename__ = "shopee_flash_sale_draft_items"
    __table_args__ = (
        Index("idx_flash_sale_draft_item_draft", "draft_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("shopee_flash_sale_drafts.id"), nullable=False, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("shopee_listings.id"), nullable=False, index=True)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("shopee_listing_variants.id"), nullable=True, index=True)
    flash_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_stock_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    purchase_limit_per_buyer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    draft = relationship("ShopeeFlashSaleDraft", back_populates="items")


class ShopeeFlashSaleSlot(Base):
    __tablename__ = "shopee_flash_sale_slots"
    __table_args__ = (
        Index("idx_flash_sale_slot_market", "market", "is_active", "sort_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    market: Mapped[str] = mapped_column(String(16), nullable=False, default="MY", index=True)
    slot_key: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    cross_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    product_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ShopeeFlashSaleCategoryRule(Base):
    __tablename__ = "shopee_flash_sale_category_rules"
    __table_args__ = (
        Index("idx_flash_sale_category_rule_market", "market", "is_active", "sort_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    market: Mapped[str] = mapped_column(String(16), nullable=False, default="MY", index=True)
    category_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    category_label: Mapped[str] = mapped_column(String(100), nullable=False)
    min_activity_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    max_activity_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=10000)
    min_discount_percent: Mapped[float] = mapped_column(Float, nullable=False, default=5)
    max_discount_percent: Mapped[float] = mapped_column(Float, nullable=False, default=99)
    min_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_30d_orders: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_ship_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allow_preorder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    repeat_control_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class SimBuyerProfile(Base):
    __tablename__ = "sim_buyer_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    buyer_code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    nickname: Mapped[str] = mapped_column(String(64), nullable=False)
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    city: Mapped[str | None] = mapped_column(String(64), nullable=True)
    city_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    occupation: Mapped[str | None] = mapped_column(String(64), nullable=True)
    background: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_categories_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    active_hours_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    weekday_factors_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    base_buy_intent: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)
    price_sensitivity: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    quality_sensitivity: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    brand_sensitivity: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    impulse_level: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    purchase_power: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class WarehouseLandmark(Base):
    __tablename__ = "warehouse_landmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    market: Mapped[str] = mapped_column(String(16), nullable=False, index=True, default="MY")
    warehouse_mode: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    warehouse_location: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    point_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    point_name: Mapped[str] = mapped_column(String(128), nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

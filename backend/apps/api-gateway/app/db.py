import json
import os
from datetime import time
from random import Random
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker


DB_NAME = os.getenv("DB_NAME", "cbec_sim")
RAW_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:teaching2024@112.124.32.196:13306",
)
OSS_PROVIDER = os.getenv("OSS_PROVIDER", "s3")
OSS_ENDPOINT = os.getenv("OSS_ENDPOINT")
OSS_DOMAIN = os.getenv("OSS_DOMAIN")
OSS_BUCKET = os.getenv("OSS_BUCKET")
OSS_ACCESS_KEY = os.getenv("OSS_ACCESS_KEY")
OSS_ACCESS_SECRET = os.getenv("OSS_ACCESS_SECRET")


def _build_database_url(raw_url: str) -> str:
    if raw_url.startswith("sqlite"):
        return raw_url

    parsed = urlparse(raw_url)
    if parsed.path in ("", "/"):
        return f"{raw_url.rstrip('/')}/{DB_NAME}"
    return raw_url


DATABASE_URL = _build_database_url(RAW_DATABASE_URL)


def generate_public_user_id() -> str:
    return f"usr_{uuid4().hex}"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_database_if_not_exists():
    if DATABASE_URL.startswith("sqlite"):
        return

    admin_url = RAW_DATABASE_URL.rstrip("/")
    admin_engine = create_engine(admin_url, pool_pre_ping=True)
    with admin_engine.begin() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}"))
    admin_engine.dispose()


def init_database():
    from app.models import (
        MarketProduct,
        OssStorageConfig,
        School,
        SimBuyerProfile,
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
        ShopeeFlashSaleCategoryRule,
        ShopeeFlashSaleSlot,
        ShopeeShopVoucherCampaign,
        ShopeeProductVoucherCampaign,
        ShopeeFollowVoucherCampaign,
        ShopeeBuyerFollowState,
        ShopeeAutoReplySetting,
        ShopeeQuickReplyPreference,
        ShopeeQuickReplyGroup,
        ShopeeQuickReplyMessage,
        ShopeeShippingFeePromotionCampaign,
        ShopeeShippingFeePromotionChannel,
        ShopeeShippingFeePromotionTier,
        ShopeeProductVoucherItem,
        ShopeeLiveVoucherCampaign,
        ShopeeLiveVoucherItem,
        ShopeeVideoVoucherCampaign,
        ShopeeVideoVoucherItem,
        ShopeeMarketingAnnouncement,
        ShopeeMarketingEvent,
        ShopeeMarketingTool,
        ShopeeCategoryNode,
        ShopeeSpecTemplate,
        ShopeeSpecTemplateOption,
        ShopeeUserDiscountPreference,
        User,
        WarehouseLandmark,
    )
    from app.core.security import hash_password

    create_database_if_not_exists()
    Base.metadata.create_all(bind=engine)
    _ensure_users_columns()
    _ensure_market_products_columns()
    _ensure_inventory_lots_columns()
    _ensure_shopee_listing_images_columns()
    _ensure_shopee_listing_variants_columns()
    _ensure_shopee_listing_wholesale_tiers_columns()
    _ensure_shopee_listings_columns()
    _ensure_shopee_listing_quality_scores_table()
    _ensure_shopee_listing_drafts_columns()
    _ensure_shopee_spec_templates_columns()
    _ensure_sim_buyer_profiles_columns()
    _ensure_shopee_orders_fulfillment_columns()
    _ensure_shopee_order_items_fulfillment_columns()
    _ensure_shopee_orders_marketing_columns()
    _ensure_shopee_orders_voucher_columns()
    _ensure_shopee_orders_shipping_promotion_columns()
    _ensure_shopee_shop_voucher_campaigns_columns()
    _ensure_shopee_product_voucher_tables()
    _ensure_shopee_private_voucher_tables()
    _ensure_shopee_live_voucher_tables()
    _ensure_shopee_video_voucher_tables()
    _ensure_shopee_follow_voucher_tables()
    _ensure_shopee_buyer_follow_state_table()
    _ensure_shopee_auto_reply_settings_table()
    _ensure_shopee_quick_reply_tables()
    _ensure_shopee_shipping_fee_promotion_tables()
    _ensure_shopee_order_generation_log_indexes()
    _cleanup_game_runs_legacy_columns()
    _ensure_table_comments()
    _ensure_column_comments()

    seed_school_names = [
        "清华大学",
        "北京大学",
        "中国人民大学",
        "北京师范大学",
        "复旦大学",
        "上海交通大学",
        "同济大学",
        "浙江大学",
        "南京大学",
        "武汉大学",
        "中山大学",
        "华中科技大学",
        "西安交通大学",
        "四川大学",
        "厦门大学",
        "山东大学",
        "吉林大学",
        "南开大学",
        "天津大学",
        "电子科技大学",
    ]

    admin_username = os.getenv("SUPER_ADMIN_USERNAME", "yzcube")
    admin_password = os.getenv("SUPER_ADMIN_INIT_PASSWORD", "Yanzhi2026.")

    with Session(engine) as db:
        existing_school_names = {s.name for s in db.query(School).all()}
        for school_name in seed_school_names:
            if school_name not in existing_school_names:
                db.add(School(name=school_name))

        existing = db.query(User).filter(User.username == admin_username).first()
        if not existing:
            db.add(
                User(
                    public_id=generate_public_user_id(),
                    username=admin_username,
                    password_hash=hash_password(admin_password),
                    role="super_admin",
                    is_active=True,
                )
            )

        target_boards = {
            "sales": {
                "name_map": {
                    "美妆个护": "销量榜·美妆个护热销款",
                    "手机与数码": "销量榜·数码配件爆款",
                    "服饰配件": "销量榜·服饰配件趋势款",
                }
            },
            "new": {
                "name_map": {
                    "美妆个护": "新品榜·美妆个护上新款",
                    "手机与数码": "新品榜·数码配件上新款",
                    "服饰配件": "新品榜·服饰配件上新款",
                }
            },
            "hot": {
                "name_map": {
                    "美妆个护": "热推榜·美妆个护爆红款",
                    "手机与数码": "热推榜·数码配件爆红款",
                    "服饰配件": "热推榜·服饰配件爆红款",
                }
            },
        }
        target_per_category = 30

        existing_products = {
            (p.market, p.board_type, p.category, p.product_name)
            for p in db.query(
                MarketProduct.market,
                MarketProduct.board_type,
                MarketProduct.category,
                MarketProduct.product_name,
            ).all()
        }
        for board_type, board_config in target_boards.items():
            for category, name_prefix in board_config["name_map"].items():
                existing_count = (
                    db.query(MarketProduct)
                    .filter(
                        MarketProduct.market == "MY",
                        MarketProduct.board_type == board_type,
                        MarketProduct.category == category,
                    )
                    .count()
                )
                start = existing_count + 1
                for i in range(start, target_per_category + 1):
                    product_name = f"{name_prefix} {i:02d}"
                    key = ("MY", board_type, category, product_name)
                    if key in existing_products:
                        continue

                    supplier_price = 8 + ((i * 3) % 35)
                    price_spread = 10 + (i % 15)
                    suggested_price = supplier_price + price_spread

                    if board_type == "sales":
                        monthly_sales = 7000 + i * 520 + (i % 7) * 130
                        growth_rate = round(5.2 + (i % 8) * 0.7, 2)
                        new_score = round(40 + (i % 18) * 1.8, 2)
                        hot_score = round(55 + (i % 14) * 1.6, 2)
                    elif board_type == "new":
                        monthly_sales = 2800 + i * 190 + (i % 5) * 110
                        growth_rate = round(18 + (i % 10) * 1.9, 2)
                        new_score = round(78 + (i % 12) * 1.5, 2)
                        hot_score = round(46 + (i % 9) * 1.7, 2)
                    else:  # hot
                        monthly_sales = 4200 + i * 320 + (i % 6) * 140
                        growth_rate = round(10 + (i % 9) * 1.6, 2)
                        new_score = round(48 + (i % 11) * 1.3, 2)
                        hot_score = round(82 + (i % 10) * 1.4, 2)

                    monthly_revenue = monthly_sales * suggested_price
                    competition_level = "high" if i % 3 == 0 else ("medium" if i % 3 == 1 else "low")

                    db.add(
                        MarketProduct(
                            market="MY",
                            board_type=board_type,
                            category=category,
                            product_name=product_name,
                            supplier_price=supplier_price,
                            suggested_price=suggested_price,
                            monthly_sales=monthly_sales,
                            monthly_revenue=monthly_revenue,
                            new_score=new_score,
                            hot_score=hot_score,
                            growth_rate=growth_rate,
                            competition_level=competition_level,
                        )
                    )

        seed_landmarks = [
            ("MY", "official", "near_kl", "off-nk-1", "KLCC 北侧点", 101.7068, 3.1543, 1),
            ("MY", "official", "near_kl", "off-nk-2", "安邦路东点", 101.7161, 3.1608, 2),
            ("MY", "official", "near_kl", "off-nk-3", "金三角西点", 101.6987, 3.1457, 3),
            ("MY", "third_party", "near_kl", "tp-nk-1", "中央车站西点", 101.6912, 3.1429, 1),
            ("MY", "third_party", "near_kl", "tp-nk-2", "武吉免登南点", 101.6810, 3.1364, 2),
            ("MY", "third_party", "near_kl", "tp-nk-3", "茨厂街东点", 101.7029, 3.1322, 3),
            ("MY", "self_built", "near_kl", "sb-nk-1", "谷中城北点", 101.6715, 3.1312, 1),
            ("MY", "self_built", "near_kl", "sb-nk-2", "旧皇宫西点", 101.6620, 3.1198, 2),
            ("MY", "self_built", "near_kl", "sb-nk-3", "孟沙南点", 101.6788, 3.1122, 3),
            ("MY", "official", "far_kl", "off-fk-1", "巴生北点", 101.5230, 3.0230, 1),
            ("MY", "official", "far_kl", "off-fk-2", "港口中点", 101.5070, 3.0090, 2),
            ("MY", "official", "far_kl", "off-fk-3", "巴生南点", 101.5380, 3.0010, 3),
            ("MY", "third_party", "far_kl", "tp-fk-1", "雪邦北点", 101.4880, 2.9970, 1),
            ("MY", "third_party", "far_kl", "tp-fk-2", "机场西点", 101.4710, 2.9820, 2),
            ("MY", "third_party", "far_kl", "tp-fk-3", "雪邦南点", 101.5020, 2.9720, 3),
            ("MY", "self_built", "far_kl", "sb-fk-1", "丹绒士拔北点", 101.4290, 2.9790, 1),
            ("MY", "self_built", "far_kl", "sb-fk-2", "丹绒士拔中点", 101.4120, 2.9620, 2),
            ("MY", "self_built", "far_kl", "sb-fk-3", "丹绒士拔南点", 101.4460, 2.9490, 3),
        ]
        existing_codes = {
            row.point_code: row
            for row in db.query(WarehouseLandmark).filter(WarehouseLandmark.market == "MY").all()
        }
        for market, mode, location, point_code, point_name, lng, lat, sort_order in seed_landmarks:
            row = existing_codes.get(point_code)
            if row:
                row.warehouse_mode = mode
                row.warehouse_location = location
                row.point_name = point_name
                row.lng = lng
                row.lat = lat
                row.sort_order = sort_order
                row.is_active = True
            else:
                db.add(
                    WarehouseLandmark(
                        market=market,
                        warehouse_mode=mode,
                        warehouse_location=location,
                        point_code=point_code,
                        point_name=point_name,
                        lng=lng,
                        lat=lat,
                        sort_order=sort_order,
                        is_active=True,
                    )
                )

        if all([OSS_ENDPOINT, OSS_DOMAIN, OSS_BUCKET, OSS_ACCESS_KEY, OSS_ACCESS_SECRET]):
            existing_active = db.query(OssStorageConfig).filter(OssStorageConfig.is_active == True).first()
            if not existing_active:
                db.add(
                    OssStorageConfig(
                        provider=OSS_PROVIDER,
                        endpoint=OSS_ENDPOINT,
                        domain=OSS_DOMAIN,
                        bucket=OSS_BUCKET,
                        access_key=OSS_ACCESS_KEY,
                        access_secret=OSS_ACCESS_SECRET,
                        is_active=True,
                    )
                )

        category_seed = {
            "美妆个护": {
                "彩妆": ["底妆", "唇妆", "眼妆"],
                "护肤": ["洁面", "面膜", "精华"],
                "个护": ["洗发护发", "身体护理", "香氛护理"],
            },
            "手机与数码": {
                "手机配件": ["手机壳", "数据线", "充电器"],
                "智能设备": ["蓝牙耳机", "智能手表", "智能音箱"],
                "电脑配件": ["键盘", "鼠标", "拓展坞"],
            },
            "服饰配件": {
                "女装": ["T恤", "连衣裙", "外套"],
                "男装": ["T恤", "衬衫", "裤装"],
                "配饰": ["项链", "帽子", "腰带"],
            },
        }
        base_specs_by_l1 = {
            "美妆个护": [
                ("brand", "品牌", "text", [], True, 1),
                ("effect", "功效", "select", ["补水", "控油", "舒缓", "提亮"], True, 2),
                ("skin_type", "适用肤质", "select", ["干性", "油性", "混合性", "敏感肌"], False, 3),
                ("volume", "规格", "text", [], True, 4),
                ("shelf_life", "保质期", "text", [], False, 5),
            ],
            "手机与数码": [
                ("brand", "品牌", "text", [], True, 1),
                ("model_fit", "适配型号", "text", [], True, 2),
                ("material", "材质", "select", ["硅胶", "TPU", "PC", "金属", "复合材质"], False, 3),
                ("color", "颜色", "text", [], False, 4),
                ("warranty", "质保", "select", ["7天", "30天", "90天", "1年"], False, 5),
            ],
            "服饰配件": [
                ("brand", "品牌", "text", [], True, 1),
                ("size", "尺码", "select", ["S", "M", "L", "XL", "均码"], True, 2),
                ("color", "颜色", "text", [], True, 3),
                ("fabric", "面料", "select", ["棉", "涤纶", "针织", "牛仔", "混纺"], False, 4),
                ("season", "适用季节", "select", ["春", "夏", "秋", "冬", "四季"], False, 5),
            ],
        }
        leaf_specs_seed: dict[str, list[tuple[str, str, str, list[str], bool, int]]] = {}
        for l1, l2_map in category_seed.items():
            base_specs = base_specs_by_l1.get(l1, [])
            for l2, l3_list in l2_map.items():
                for l3 in l3_list:
                    path = f"{l1} > {l2} > {l3}"
                    fields = list(base_specs)
                    if l1 == "美妆个护":
                        fields.append(("target_area", "适用部位", "select", ["面部", "眼部", "唇部", "身体"], False, 6))
                    elif l1 == "手机与数码":
                        fields.append(("package_content", "包装清单", "text", [], False, 6))
                    elif l1 == "服饰配件":
                        fields.append(("fit", "版型", "select", ["修身", "标准", "宽松"], False, 6))
                    leaf_specs_seed[path] = fields

        # Beauty > Makeup > Foundation: use a richer dedicated spec template.
        leaf_specs_seed["美妆个护 > 彩妆 > 底妆"] = [
            ("brand", "品牌", "select", ["Maybelline", "L'Oreal", "NARS", "Estee Lauder", "Shiseido", "No brand"], True, 1),
            ("shade_code", "色号", "text", [], True, 2),
            ("tone", "色调", "select", ["冷调", "暖调", "中性"], True, 3),
            ("finish", "妆效", "select", ["自然", "哑光", "光泽", "奶油肌"], True, 4),
            ("coverage", "遮瑕度", "select", ["轻度", "中度", "高度"], True, 5),
            ("texture", "质地", "select", ["液体", "霜状", "粉状", "气垫"], False, 6),
            ("skin_type", "适用肤质", "select", ["干性", "油性", "混合性", "敏感肌"], True, 7),
            ("net_content_value", "净含量", "text", [], True, 8),
            ("net_content_unit", "净含量单位", "select", ["ml", "g"], True, 9),
            ("weight_value", "重量", "text", [], False, 10),
            ("weight_unit", "重量单位", "select", ["g", "kg"], False, 11),
            ("spf", "SPF", "select", ["无", "SPF15", "SPF30", "SPF50+"], False, 12),
            ("pa_level", "PA等级", "select", ["无", "PA+", "PA++", "PA+++"], False, 13),
            ("waterproof_level", "防水等级", "select", ["不防水", "防汗", "防水"], False, 14),
            ("lasting_hours", "持妆时长", "select", ["4小时", "8小时", "12小时以上"], False, 15),
            ("origin_country", "原产地", "select", ["中国", "日本", "韩国", "法国", "美国", "其他"], False, 16),
            ("shelf_life", "保质期", "select", ["1个月", "2个月", "3个月", "6个月", "12个月", "24个月"], True, 17),
            ("expiry_date", "到期日", "text", [], False, 18),
            ("fda_reg_no", "FDA注册号", "text", [], False, 19),
            ("ingredient", "主要成分", "text", [], False, 20),
            ("condition_label", "商品状况", "select", ["全新", "二手-近新", "二手-良好"], False, 21),
            ("customizable", "是否可定制", "select", ["否", "是"], False, 22),
        ]

        existing_nodes = {row.path: row for row in db.query(ShopeeCategoryNode).all()}
        sort_l1 = 1
        for l1, l2_map in category_seed.items():
            l1_path = l1
            node_l1 = existing_nodes.get(l1_path)
            if not node_l1:
                node_l1 = ShopeeCategoryNode(parent_id=None, level=1, name=l1, path=l1_path, sort_order=sort_l1, is_active=True)
                db.add(node_l1)
                db.flush()
                existing_nodes[l1_path] = node_l1
            sort_l2 = 1
            for l2, l3_list in l2_map.items():
                l2_path = f"{l1} > {l2}"
                node_l2 = existing_nodes.get(l2_path)
                if not node_l2:
                    node_l2 = ShopeeCategoryNode(parent_id=node_l1.id, level=2, name=l2, path=l2_path, sort_order=sort_l2, is_active=True)
                    db.add(node_l2)
                    db.flush()
                    existing_nodes[l2_path] = node_l2
                sort_l3 = 1
                for l3 in l3_list:
                    l3_path = f"{l1} > {l2} > {l3}"
                    node_l3 = existing_nodes.get(l3_path)
                    if not node_l3:
                        node_l3 = ShopeeCategoryNode(parent_id=node_l2.id, level=3, name=l3, path=l3_path, sort_order=sort_l3, is_active=True)
                        db.add(node_l3)
                        db.flush()
                        existing_nodes[l3_path] = node_l3
                    sort_l3 += 1
                sort_l2 += 1
            sort_l1 += 1

        existing_templates = {
            (row.category_id, row.field_key): row
            for row in db.query(ShopeeSpecTemplate).all()
            if row.category_id
        }
        for path, fields in leaf_specs_seed.items():
            node = existing_nodes.get(path)
            if not node:
                continue
            category_root = path.split(" > ", 1)[0]
            field_key_set = {item[0] for item in fields}
            category_existing_rows = db.query(ShopeeSpecTemplate).filter(ShopeeSpecTemplate.category_id == node.id).all()
            for row in category_existing_rows:
                if row.field_key not in field_key_set:
                    row.is_active = False
            for field_key, field_label, field_type, options, is_required, sort_order in fields:
                key = (node.id, field_key)
                existing = existing_templates.get(key)
                if existing:
                    existing.category_root = category_root
                    existing.field_label = field_label
                    existing.field_type = field_type
                    existing.is_required = is_required
                    existing.sort_order = sort_order
                    existing.is_active = True
                    template = existing
                else:
                    template = ShopeeSpecTemplate(
                        category_root=category_root,
                        category_id=node.id,
                        field_key=field_key,
                        field_label=field_label,
                        field_type=field_type,
                        is_required=is_required,
                        sort_order=sort_order,
                        is_active=True,
                    )
                    db.add(template)
                    db.flush()
                if field_type == "select":
                    existing_options = {
                        row.option_value: row
                        for row in db.query(ShopeeSpecTemplateOption)
                        .filter(ShopeeSpecTemplateOption.template_id == template.id)
                        .all()
                    }
                    active_option_set = set(options)
                    for option_row in existing_options.values():
                        if option_row.option_value not in active_option_set:
                            option_row.is_active = False
                    for idx, opt in enumerate(options, start=1):
                        row = existing_options.get(opt)
                        if row:
                            row.option_label = opt
                            row.sort_order = idx
                            row.is_active = True
                        else:
                            db.add(
                                ShopeeSpecTemplateOption(
                                    template_id=template.id,
                                    option_value=opt,
                                    option_label=opt,
                                    sort_order=idx,
                                    is_active=True,
                                )
                            )

        rng = Random(20260318)
        english_names = [
            "Liam Carter", "Olivia Morgan", "Noah Bennett", "Emma Brooks", "Mason Turner",
            "Ava Collins", "Ethan Parker", "Sophia Reed", "Lucas Ward", "Mia Foster",
            "Logan Hughes", "Isabella Gray", "James Hayes", "Charlotte Cook", "Benjamin Price",
            "Amelia Bell", "Elijah Long", "Harper Perry", "Jacob Ross", "Evelyn Sanders",
            "Michael Bailey", "Abigail Rivera", "Daniel Stewart", "Emily Cooper", "Henry Bryant",
            "Ella Simmons", "Jackson Powell", "Scarlett Butler", "Sebastian Barnes", "Aria Coleman",
            "Aiden Henderson", "Lily Jenkins", "Matthew Patterson", "Grace Russell", "Samuel Peterson",
            "Chloe Griffin", "David Ramirez", "Zoey Kelly", "Joseph Wood", "Nora Howard",
            "Carter Watson", "Hannah Richardson", "Owen Brooks", "Layla Cox", "Wyatt Flores",
            "Stella Ward", "John Myers", "Lucy Marshall", "Luke Graham", "Aurora Ellis",
        ]
        cities = [
            "Kuala Lumpur", "Selangor", "Penang", "Johor Bahru", "Ipoh",
            "Malacca", "Kedah", "Sabah", "Sarawak", "Shah Alam",
        ]
        city_geo_map = {
            "Kuala Lumpur": {"city_code": "MY-KUL", "lat": 3.1390, "lng": 101.6869},
            "Selangor": {"city_code": "MY-SGR", "lat": 3.0738, "lng": 101.5183},
            "Penang": {"city_code": "MY-PNG", "lat": 5.4141, "lng": 100.3288},
            "Johor Bahru": {"city_code": "MY-JHB", "lat": 1.4927, "lng": 103.7414},
            "Ipoh": {"city_code": "MY-IPH", "lat": 4.5975, "lng": 101.0901},
            "Malacca": {"city_code": "MY-MLK", "lat": 2.1896, "lng": 102.2501},
            "Kedah": {"city_code": "MY-KDH", "lat": 6.1184, "lng": 100.3685},
            "Sabah": {"city_code": "MY-SBH", "lat": 5.9804, "lng": 116.0735},
            "Sarawak": {"city_code": "MY-SWK", "lat": 1.5533, "lng": 110.3592},
            "Shah Alam": {"city_code": "MY-SAM", "lat": 3.0733, "lng": 101.5185},
        }
        occupations = [
            "University Student", "Software Engineer", "E-commerce Agent", "Retail Owner", "Designer",
            "Logistics Planner", "Teacher", "Content Creator", "Sales Executive", "Purchasing Manager",
        ]
        backgrounds = [
            "Value-driven shopper focused on practical daily-use products.",
            "Quality-oriented buyer who compares specs before ordering.",
            "Trend-sensitive shopper influenced by social content and promotions.",
            "Stable replenishment buyer who values stock reliability and shipping speed.",
            "Brand-aware buyer willing to pay for trust and consistency.",
        ]
        category_groups = [
            ["美妆个护", "服饰配件"],
            ["手机与数码", "服饰配件"],
            ["美妆个护", "手机与数码"],
            ["服饰配件"],
            ["手机与数码"],
        ]

        def _in_sleep_window(hour_idx: int, sleep_start: int, sleep_len: int) -> bool:
            sleep_end = (sleep_start + sleep_len) % 24
            if sleep_start < sleep_end:
                return sleep_start <= hour_idx < sleep_end
            return hour_idx >= sleep_start or hour_idx < sleep_end

        def _hour_distance_circular(a: int, b: int) -> int:
            diff = abs(a - b)
            return min(diff, 24 - diff)

        def _build_sleep_aware_hours(seed_idx: int) -> list[float]:
            local_rng = Random(7000 + seed_idx)
            chrono_roll = local_rng.random()
            # 连续作息窗口（非离散随机置零）：更接近真实用户行为
            if chrono_roll < 0.20:
                # 早睡早起
                sleep_start = 22 + local_rng.randint(-1, 0)
                sleep_len = 7 + local_rng.randint(0, 1)
                peaks = [
                    (7 + local_rng.randint(-1, 1), 0.11 + local_rng.random() * 0.05, 2),
                    (12 + local_rng.randint(-1, 1), 0.09 + local_rng.random() * 0.04, 2),
                    (19 + local_rng.randint(-1, 1), 0.10 + local_rng.random() * 0.04, 3),
                ]
            elif chrono_roll < 0.75:
                # 常规作息
                sleep_start = 23 + local_rng.randint(0, 1)
                sleep_len = 6 + local_rng.randint(0, 2)
                peaks = [
                    (8 + local_rng.randint(-1, 1), 0.10 + local_rng.random() * 0.04, 2),
                    (13 + local_rng.randint(-1, 1), 0.08 + local_rng.random() * 0.04, 2),
                    (21 + local_rng.randint(-1, 1), 0.13 + local_rng.random() * 0.05, 3),
                ]
            elif chrono_roll < 0.93:
                # 夜猫
                sleep_start = 1 + local_rng.randint(0, 1)
                sleep_len = 6 + local_rng.randint(0, 1)
                peaks = [
                    (10 + local_rng.randint(-1, 1), 0.07 + local_rng.random() * 0.03, 2),
                    (15 + local_rng.randint(-1, 1), 0.09 + local_rng.random() * 0.04, 2),
                    (23 + local_rng.randint(-1, 1), 0.14 + local_rng.random() * 0.05, 3),
                ]
            else:
                # 轮班（深夜活跃但仍有连续低谷）
                sleep_start = 4 + local_rng.randint(0, 1)
                sleep_len = 5 + local_rng.randint(0, 1)
                peaks = [
                    (1 + local_rng.randint(-1, 1), 0.12 + local_rng.random() * 0.04, 2),
                    (10 + local_rng.randint(-1, 1), 0.08 + local_rng.random() * 0.03, 2),
                    (20 + local_rng.randint(-1, 1), 0.10 + local_rng.random() * 0.04, 2),
                ]

            values: list[float] = []
            for hour_idx in range(24):
                if _in_sleep_window(hour_idx, sleep_start, sleep_len):
                    values.append(0.0)
                    continue

                val = 0.010 + local_rng.random() * 0.010

                # 睡眠窗口前后1小时设为“软低活跃”
                if _hour_distance_circular(hour_idx, sleep_start) == 1 or _hour_distance_circular(
                    hour_idx, (sleep_start + sleep_len) % 24
                ) == 1:
                    val = min(val, 0.015 + local_rng.random() * 0.010)

                for peak_center, peak_amp, width in peaks:
                    distance = _hour_distance_circular(hour_idx, peak_center)
                    if distance <= width:
                        val += peak_amp * (1 - distance / (width + 1))

                values.append(round(max(0.0, min(0.35, val)), 3))
            return values

        buyer_seed = []
        for idx in range(50):
            buyer_seed.append(
                {
                    "buyer_code": f"BYR{idx + 1:03d}",
                    "nickname": english_names[idx],
                    "gender": "female" if idx % 2 else "male",
                    "age": 21 + (idx % 24),
                    "city": cities[idx % len(cities)],
                    "occupation": occupations[idx % len(occupations)],
                    "background": backgrounds[idx % len(backgrounds)],
                    "preferred_categories": category_groups[idx % len(category_groups)],
                    "active_hours": _build_sleep_aware_hours(idx),
                    "weekday_factors": [
                        round(0.95 + rng.random() * 0.12, 2),
                        round(0.95 + rng.random() * 0.12, 2),
                        round(0.95 + rng.random() * 0.12, 2),
                        round(0.95 + rng.random() * 0.12, 2),
                        round(0.95 + rng.random() * 0.12, 2),
                        round(1.00 + rng.random() * 0.18, 2),
                        round(1.00 + rng.random() * 0.18, 2),
                    ],
                    "base_buy_intent": round(0.16 + rng.random() * 0.12, 2),
                    "price_sensitivity": round(0.30 + rng.random() * 0.60, 2),
                    "quality_sensitivity": round(0.35 + rng.random() * 0.55, 2),
                    "brand_sensitivity": round(0.25 + rng.random() * 0.60, 2),
                    "impulse_level": round(0.20 + rng.random() * 0.65, 2),
                    "purchase_power": round(0.30 + rng.random() * 0.55, 2),
                }
            )
        existing_buyers = {row.buyer_code: row for row in db.query(SimBuyerProfile).all()}
        seed_buyer_codes = {item["buyer_code"] for item in buyer_seed}
        for buyer_code, buyer_row in existing_buyers.items():
            if buyer_code.startswith("BYR") and buyer_code not in seed_buyer_codes:
                buyer_row.is_active = False
        for item in buyer_seed:
            profile = existing_buyers.get(item["buyer_code"])
            payload = {
                "nickname": item["nickname"],
                "gender": item["gender"],
                "age": item["age"],
                "city": item["city"],
                "city_code": city_geo_map.get(item["city"], {}).get("city_code"),
                "lat": city_geo_map.get(item["city"], {}).get("lat"),
                "lng": city_geo_map.get(item["city"], {}).get("lng"),
                "occupation": item["occupation"],
                "background": item["background"],
                "preferred_categories_json": json.dumps(item["preferred_categories"], ensure_ascii=False),
                "active_hours_json": json.dumps(item["active_hours"], ensure_ascii=False),
                "weekday_factors_json": json.dumps(item["weekday_factors"], ensure_ascii=False),
                "base_buy_intent": item["base_buy_intent"],
                "price_sensitivity": item["price_sensitivity"],
                "quality_sensitivity": item["quality_sensitivity"],
                "brand_sensitivity": item["brand_sensitivity"],
                "impulse_level": item["impulse_level"],
                "purchase_power": item["purchase_power"],
                "is_active": True,
            }
            if profile:
                for field_name, field_value in payload.items():
                    setattr(profile, field_name, field_value)
            else:
                db.add(
                    SimBuyerProfile(
                        buyer_code=item["buyer_code"],
                        **payload,
                    )
                )

        marketing_tools = [
            {
                "tool_key": "discount",
                "tool_name": "Discount",
                "tag_type": "boost_sales",
                "description": "Set discounts on your products to boost sales",
                "icon_key": "badge-percent",
                "target_route": "/u/{public_id}/shopee/marketing/discount",
                "sort_order": 10,
            },
            {
                "tool_key": "flash_sale",
                "tool_name": "My Shop's Flash Sale",
                "tag_type": "boost_sales",
                "description": "Boost product sales by creating limited-time discount offers in your shop",
                "icon_key": "store",
                "target_route": "/u/{public_id}/shopee/marketing/flash-sale",
                "sort_order": 20,
            },
            {
                "tool_key": "vouchers",
                "tool_name": "Vouchers",
                "tag_type": "boost_sales",
                "description": "Increase orders by offering buyers reduced prices at checkout with vouchers",
                "icon_key": "ticket",
                "target_route": "/u/{public_id}/shopee/marketing/vouchers",
                "sort_order": 30,
            },
            {
                "tool_key": "shopee_ads",
                "tool_name": "Shopee Ads",
                "tag_type": "increase_traffic",
                "description": "Increase exposure and drive sales in high traffic areas on Shopee with ads",
                "icon_key": "badge-dollar-sign",
                "target_route": "/u/{public_id}/shopee/marketing/shopee-ads",
                "sort_order": 40,
            },
            {
                "tool_key": "affiliate_marketing",
                "tool_name": "Affiliate Marketing Solution",
                "tag_type": "increase_traffic",
                "description": "Leverage on Shopee's extensive network of affiliate partners to boost your store promotion",
                "icon_key": "users-round",
                "target_route": "/u/{public_id}/shopee/marketing/affiliate-marketing",
                "sort_order": 50,
            },
            {
                "tool_key": "shipping_fee_promotion",
                "tool_name": "Shipping Fee Promotion",
                "tag_type": "boost_sales",
                "description": "Set shipping fee discounts to attract shoppers to make orders",
                "icon_key": "truck",
                "target_route": "/u/{public_id}/shopee/marketing/shipping-fee-promotion",
                "sort_order": 60,
            },
            {
                "tool_key": "live_streaming",
                "tool_name": "Live Streaming",
                "tag_type": "improve_engagement",
                "description": "Connect Live with your audience and answer shopper questions easily",
                "icon_key": "video",
                "target_route": "/u/{public_id}/shopee/marketing/live-video",
                "sort_order": 70,
            },
            {
                "tool_key": "off_platform_ads",
                "tool_name": "Off-Platform Ads",
                "tag_type": "increase_traffic",
                "description": "Advertise your products on Meta and Google platforms including Facebook, Instagram, Google Search and YouTube",
                "icon_key": "globe",
                "target_route": "/u/{public_id}/shopee/marketing/off-platform-ads",
                "sort_order": 80,
            },
            {
                "tool_key": "review_prize",
                "tool_name": "Review Prize",
                "tag_type": "improve_engagement",
                "description": "Attract customers to leave better reviews by rewarding coins",
                "icon_key": "message-square-heart",
                "target_route": "/u/{public_id}/shopee/marketing/review-prize",
                "sort_order": 90,
            },
            {
                "tool_key": "international_platform",
                "tool_name": "Shopee International Platform",
                "tag_type": "boost_sales",
                "description": "Helps you to sell on overseas Shopee platforms without any additional effort",
                "icon_key": "earth",
                "target_route": "/u/{public_id}/shopee/marketing/international-platform",
                "sort_order": 100,
            },
            {
                "tool_key": "seller_coins",
                "tool_name": "Seller Coins",
                "tag_type": "improve_engagement",
                "description": "Top up seller coins as a reward to encourage shoppers to join shop activities",
                "icon_key": "coins",
                "target_route": "/u/{public_id}/shopee/marketing/seller-coins",
                "sort_order": 110,
            },
            {
                "tool_key": "live_streaming_promotion",
                "tool_name": "Live Streaming Promotion",
                "tag_type": "increase_traffic",
                "description": "Nominate your products to be featured in Shopee Livestream",
                "icon_key": "radio",
                "target_route": "/u/{public_id}/shopee/marketing/live-streaming-promotion",
                "sort_order": 120,
            },
            {
                "tool_key": "marketing_solution",
                "tool_name": "Marketing Solution",
                "tag_type": "increase_traffic",
                "description": "Combined marketing tools for optimized engagement and returns with mission rewards from completion",
                "icon_key": "chart-no-axes-combined",
                "target_route": "/u/{public_id}/shopee/marketing/marketing-solution",
                "sort_order": 130,
            },
        ]
        existing_tool_keys = {row.tool_key for row in db.query(ShopeeMarketingTool).all()}
        for item in marketing_tools:
            if item["tool_key"] in existing_tool_keys:
                continue
            db.add(ShopeeMarketingTool(**item))

        announcement_seed = [
            {
                "market": "MY",
                "lang": "zh-CN",
                "title": "免费！推广奖励升级",
                "summary": "新增营销激励包，完成活动门槛后可获得额外曝光位。",
                "badge_text": "HOT",
                "priority": 100,
                "status": "published",
            },
            {
                "market": "MY",
                "lang": "zh-CN",
                "title": "季中大促排期开放",
                "summary": "请尽快完成折扣、券和活动报名，抢占平台营销流量入口。",
                "badge_text": "SALE",
                "priority": 90,
                "status": "published",
            },
            {
                "market": "MY",
                "lang": "zh-CN",
                "title": "Google Ads 联动能力上线",
                "summary": "站外投放数据将逐步纳入营销中心，后续支持效果归因。",
                "badge_text": "NEW",
                "priority": 80,
                "status": "published",
            },
        ]
        existing_announcement_titles = {row.title for row in db.query(ShopeeMarketingAnnouncement).all()}
        for item in announcement_seed:
            if item["title"] in existing_announcement_titles:
                continue
            db.add(ShopeeMarketingAnnouncement(**item))

        event_seed = [
            {
                "market": "MY",
                "lang": "zh-CN",
                "title": "Super Voucher Day",
                "image_url": "marketing-event-super-voucher-day",
                "jump_url": "/u/{public_id}/shopee/marketing/campaign",
                "status": "ongoing",
                "sort_order": 10,
            },
            {
                "market": "MY",
                "lang": "zh-CN",
                "title": "Mega Campaign Payday",
                "image_url": "marketing-event-mega-payday",
                "jump_url": "/u/{public_id}/shopee/marketing/flash-sale",
                "status": "ongoing",
                "sort_order": 20,
            },
            {
                "market": "MY",
                "lang": "zh-CN",
                "title": "Seller Growth Week",
                "image_url": "marketing-event-growth-week",
                "jump_url": "/u/{public_id}/shopee/marketing/shopee-ads",
                "status": "upcoming",
                "sort_order": 30,
            },
        ]
        existing_event_titles = {row.title for row in db.query(ShopeeMarketingEvent).all()}
        for item in event_seed:
            if item["title"] in existing_event_titles:
                continue
            db.add(ShopeeMarketingEvent(**item))

        flash_sale_slot_seed = [
            ("00_12", time(0, 0), time(12, 0), False, 50, 1),
            ("12_18", time(12, 0), time(18, 0), False, 50, 2),
            ("18_21", time(18, 0), time(21, 0), False, 50, 3),
            ("21_00", time(21, 0), time(0, 0), True, 50, 4),
        ]
        existing_flash_sale_slots = {(row.market, row.slot_key): row for row in db.query(ShopeeFlashSaleSlot).filter(ShopeeFlashSaleSlot.market == "MY").all()}
        for slot_key, start_time, end_time, cross_day, product_limit, sort_order in flash_sale_slot_seed:
            row = existing_flash_sale_slots.get(("MY", slot_key))
            if row:
                row.start_time = start_time
                row.end_time = end_time
                row.cross_day = cross_day
                row.product_limit = product_limit
                row.is_active = True
                row.sort_order = sort_order
            else:
                db.add(ShopeeFlashSaleSlot(market="MY", slot_key=slot_key, start_time=start_time, end_time=end_time, cross_day=cross_day, product_limit=product_limit, is_active=True, sort_order=sort_order))

        flash_sale_rule_seed = [
            ("baby", "母婴", 1),
            ("tools_home", "工具与家装", 2),
            ("kitchen", "厨房用品", 3),
            ("storage", "收纳整理", 4),
            ("tv_accessories", "电视及配件", 5),
            ("beauty", "美容护肤", 6),
            ("furniture", "家具", 7),
            ("all", "全部", 8),
        ]
        existing_flash_sale_rules = {(row.market, row.category_key): row for row in db.query(ShopeeFlashSaleCategoryRule).filter(ShopeeFlashSaleCategoryRule.market == "MY").all()}
        for category_key, category_label, sort_order in flash_sale_rule_seed:
            row = existing_flash_sale_rules.get(("MY", category_key))
            if row:
                row.category_label = category_label
                row.min_activity_stock = 5
                row.max_activity_stock = 10000
                row.min_discount_percent = 5
                row.max_discount_percent = 99
                row.allow_preorder = True
                row.is_active = True
                row.sort_order = sort_order
            else:
                db.add(ShopeeFlashSaleCategoryRule(market="MY", category_key=category_key, category_label=category_label, min_activity_stock=5, max_activity_stock=10000, min_discount_percent=5, max_discount_percent=99, allow_preorder=True, is_active=True, sort_order=sort_order))
        db.commit()


def _ensure_users_columns():
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("users")}
    missing_sql = []
    if "public_id" not in existing_columns:
        missing_sql.append("ALTER TABLE users ADD COLUMN public_id VARCHAR(64) NULL")
    if "school_id" not in existing_columns:
        missing_sql.append("ALTER TABLE users ADD COLUMN school_id INTEGER NULL")
    if "major" not in existing_columns:
        missing_sql.append("ALTER TABLE users ADD COLUMN major VARCHAR(128) NULL")
    if "class_name" not in existing_columns:
        missing_sql.append("ALTER TABLE users ADD COLUMN class_name VARCHAR(128) NULL")
    if "full_name" not in existing_columns:
        missing_sql.append("ALTER TABLE users ADD COLUMN full_name VARCHAR(64) NULL")

    if not missing_sql:
        return

    with engine.begin() as conn:
        for sql in missing_sql:
            conn.execute(text(sql))

    inspector = inspect(engine)
    refreshed_columns = {col["name"] for col in inspector.get_columns("users")}
    if "public_id" not in refreshed_columns:
        return

    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id FROM users WHERE public_id IS NULL OR public_id = ''")).fetchall()
        for row in rows:
            conn.execute(
                text("UPDATE users SET public_id = :public_id WHERE id = :id"),
                {"public_id": generate_public_user_id(), "id": row[0]},
            )

        index_names = {idx["name"] for idx in inspector.get_indexes("users")}
        if "ix_users_public_id" not in index_names:
            conn.execute(text("CREATE UNIQUE INDEX ix_users_public_id ON users (public_id)"))

        if not DATABASE_URL.startswith("sqlite"):
            conn.execute(text("ALTER TABLE users MODIFY COLUMN public_id VARCHAR(64) NOT NULL"))


def _cleanup_game_runs_legacy_columns():
    inspector = inspect(engine)
    if "game_runs" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("game_runs")}
    add_sql = []
    if "base_real_duration_days" not in existing_columns:
        add_sql.append("ALTER TABLE game_runs ADD COLUMN base_real_duration_days INTEGER NULL")
    if "base_game_days" not in existing_columns:
        add_sql.append("ALTER TABLE game_runs ADD COLUMN base_game_days INTEGER NULL")
    if "total_game_days" not in existing_columns:
        add_sql.append("ALTER TABLE game_runs ADD COLUMN total_game_days INTEGER NULL")
    if "manual_end_time" not in existing_columns:
        add_sql.append("ALTER TABLE game_runs ADD COLUMN manual_end_time DATETIME NULL")

    with engine.begin() as conn:
        for sql in add_sql:
            conn.execute(text(sql))
        conn.execute(
            text(
                "UPDATE game_runs SET "
                "base_real_duration_days = COALESCE(base_real_duration_days, 7), "
                "base_game_days = COALESCE(base_game_days, 365), "
                "total_game_days = COALESCE(total_game_days, 365), "
                "day_index = COALESCE(day_index, 1)"
            )
        )

    # sqlite does not support DROP COLUMN in older compatibility paths used by tests;
    # legacy columns are safely ignored there.
    if DATABASE_URL.startswith("sqlite"):
        return

    inspector = inspect(engine)
    existing_columns = {col["name"] for col in inspector.get_columns("game_runs")}
    drop_sql = []
    if "procurement_budget" in existing_columns:
        drop_sql.append("ALTER TABLE game_runs DROP COLUMN procurement_budget")
    if "logistics_budget" in existing_columns:
        drop_sql.append("ALTER TABLE game_runs DROP COLUMN logistics_budget")
    if "warehousing_budget" in existing_columns:
        drop_sql.append("ALTER TABLE game_runs DROP COLUMN warehousing_budget")
    if "marketing_budget" in existing_columns:
        drop_sql.append("ALTER TABLE game_runs DROP COLUMN marketing_budget")

    if not drop_sql:
        return

    with engine.begin() as conn:
        for sql in drop_sql:
            conn.execute(text(sql))


def _ensure_market_products_columns():
    inspector = inspect(engine)
    if "market_products" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("market_products")}
    missing_sql = []
    if "board_type" not in existing_columns:
        missing_sql.append("ALTER TABLE market_products ADD COLUMN board_type VARCHAR(16) NOT NULL DEFAULT 'sales'")
    if "new_score" not in existing_columns:
        missing_sql.append("ALTER TABLE market_products ADD COLUMN new_score FLOAT NOT NULL DEFAULT 0")
    if "hot_score" not in existing_columns:
        missing_sql.append("ALTER TABLE market_products ADD COLUMN hot_score FLOAT NOT NULL DEFAULT 0")

    if not missing_sql:
        return

    with engine.begin() as conn:
        for sql in missing_sql:
            conn.execute(text(sql))


def _ensure_inventory_lots_columns():
    inspector = inspect(engine)
    if "inventory_lots" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("inventory_lots")}
    missing_sql = []
    if "reserved_qty" not in existing_columns:
        missing_sql.append("ALTER TABLE inventory_lots ADD COLUMN reserved_qty INTEGER NOT NULL DEFAULT 0")
    if "backorder_qty" not in existing_columns:
        missing_sql.append("ALTER TABLE inventory_lots ADD COLUMN backorder_qty INTEGER NOT NULL DEFAULT 0")
    if "last_restocked_at" not in existing_columns:
        missing_sql.append("ALTER TABLE inventory_lots ADD COLUMN last_restocked_at DATETIME NULL")

    if not missing_sql:
        return

    with engine.begin() as conn:
        for sql in missing_sql:
            conn.execute(text(sql))


def _ensure_shopee_listing_images_columns():
    inspector = inspect(engine)
    if "shopee_listing_images" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("shopee_listing_images")}
    if "image_ratio" in existing_columns:
        return

    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE shopee_listing_images "
                "ADD COLUMN image_ratio VARCHAR(16) NOT NULL DEFAULT '1:1'"
            )
        )


def _ensure_shopee_listing_variants_columns():
    inspector = inspect(engine)
    if "shopee_listing_variants" not in inspector.get_table_names():
        Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables["shopee_listing_variants"]])
        return

    existing_columns = {col["name"] for col in inspector.get_columns("shopee_listing_variants")}
    missing_sql = []
    if "weight_kg" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listing_variants ADD COLUMN weight_kg FLOAT NULL")
    if "parcel_length_cm" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listing_variants ADD COLUMN parcel_length_cm INTEGER NULL")
    if "parcel_width_cm" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listing_variants ADD COLUMN parcel_width_cm INTEGER NULL")
    if "parcel_height_cm" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listing_variants ADD COLUMN parcel_height_cm INTEGER NULL")
    if "sales_count" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listing_variants ADD COLUMN sales_count INTEGER NOT NULL DEFAULT 0")
    if "oversell_limit" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listing_variants ADD COLUMN oversell_limit INTEGER NOT NULL DEFAULT 2000")
    if "oversell_used" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listing_variants ADD COLUMN oversell_used INTEGER NOT NULL DEFAULT 0")

    if not missing_sql:
        return

    with engine.begin() as conn:
        for sql in missing_sql:
            conn.execute(text(sql))


def _ensure_shopee_listing_wholesale_tiers_columns():
    inspector = inspect(engine)
    if "shopee_listing_wholesale_tiers" in inspector.get_table_names():
        return
    Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables["shopee_listing_wholesale_tiers"]])


def _ensure_shopee_listings_columns():
    inspector = inspect(engine)
    if "shopee_listings" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("shopee_listings")}
    missing_sql = []
    if "gtin" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN gtin VARCHAR(64) NULL")
    if "description" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN description VARCHAR(5000) NULL")
    if "video_url" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN video_url VARCHAR(255) NULL")
    if "min_purchase_qty" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN min_purchase_qty INTEGER NOT NULL DEFAULT 1")
    if "max_purchase_qty" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN max_purchase_qty INTEGER NULL")
    if "max_purchase_mode" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN max_purchase_mode VARCHAR(24) NOT NULL DEFAULT 'none'")
    if "max_purchase_period_start_date" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN max_purchase_period_start_date DATE NULL")
    if "max_purchase_period_end_date" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN max_purchase_period_end_date DATE NULL")
    if "max_purchase_period_qty" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN max_purchase_period_qty INTEGER NULL")
    if "max_purchase_period_days" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN max_purchase_period_days INTEGER NULL")
    if "max_purchase_period_model" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN max_purchase_period_model VARCHAR(24) NULL")
    if "weight_kg" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN weight_kg FLOAT NULL")
    if "parcel_length_cm" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN parcel_length_cm INTEGER NULL")
    if "parcel_width_cm" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN parcel_width_cm INTEGER NULL")
    if "parcel_height_cm" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN parcel_height_cm INTEGER NULL")
    if "shipping_variation_dimension_enabled" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN shipping_variation_dimension_enabled BOOLEAN NOT NULL DEFAULT 0")
    if "shipping_standard_bulk" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN shipping_standard_bulk BOOLEAN NOT NULL DEFAULT 0")
    if "shipping_standard" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN shipping_standard BOOLEAN NOT NULL DEFAULT 0")
    if "shipping_express" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN shipping_express BOOLEAN NOT NULL DEFAULT 0")
    if "preorder_enabled" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN preorder_enabled BOOLEAN NOT NULL DEFAULT 0")
    if "insurance_enabled" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN insurance_enabled BOOLEAN NOT NULL DEFAULT 0")
    if "condition_label" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN condition_label VARCHAR(32) NULL")
    if "schedule_publish_at" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN schedule_publish_at DATETIME NULL")
    if "parent_sku" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN parent_sku VARCHAR(64) NULL")
    if "quality_total_score" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN quality_total_score INTEGER NULL")
    if "quality_scored_at" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN quality_scored_at DATETIME NULL")
    if "quality_score_version" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listings ADD COLUMN quality_score_version VARCHAR(32) NULL")

    if not missing_sql:
        return

    with engine.begin() as conn:
        for sql in missing_sql:
            conn.execute(text(sql))


def _ensure_shopee_listing_quality_scores_table():
    inspector = inspect(engine)
    if "shopee_listing_quality_scores" in inspector.get_table_names():
        return
    Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables["shopee_listing_quality_scores"]])


def _ensure_shopee_listing_drafts_columns():
    inspector = inspect(engine)
    if "shopee_listing_drafts" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("shopee_listing_drafts")}
    missing_sql = []
    if "video_url" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_listing_drafts ADD COLUMN video_url VARCHAR(255) NULL")

    if not missing_sql:
        return

    with engine.begin() as conn:
        for sql in missing_sql:
            conn.execute(text(sql))


def _ensure_shopee_spec_templates_columns():
    inspector = inspect(engine)

    if "shopee_listings" in inspector.get_table_names():
        listing_cols = {col["name"] for col in inspector.get_columns("shopee_listings")}
        if "category_id" not in listing_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE shopee_listings ADD COLUMN category_id INTEGER NULL"))

    if "shopee_listing_drafts" in inspector.get_table_names():
        draft_cols = {col["name"] for col in inspector.get_columns("shopee_listing_drafts")}
        if "category_id" not in draft_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE shopee_listing_drafts ADD COLUMN category_id INTEGER NULL"))

    if "shopee_spec_templates" in inspector.get_table_names():
        spec_cols = {col["name"] for col in inspector.get_columns("shopee_spec_templates")}
        missing_sql = []
        if "category_id" not in spec_cols:
            missing_sql.append("ALTER TABLE shopee_spec_templates ADD COLUMN category_id INTEGER NULL")
        if "attr_key" not in spec_cols:
            missing_sql.append("ALTER TABLE shopee_spec_templates ADD COLUMN attr_key VARCHAR(64) NULL")
        if "attr_label" not in spec_cols:
            missing_sql.append("ALTER TABLE shopee_spec_templates ADD COLUMN attr_label VARCHAR(128) NULL")
        if "input_type" not in spec_cols:
            missing_sql.append("ALTER TABLE shopee_spec_templates ADD COLUMN input_type VARCHAR(16) NOT NULL DEFAULT 'select'")
        if missing_sql:
            with engine.begin() as conn:
                for sql in missing_sql:
                    conn.execute(text(sql))


def _ensure_sim_buyer_profiles_columns():
    inspector = inspect(engine)
    if "sim_buyer_profiles" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("sim_buyer_profiles")}
    missing_sql = []
    if "city_code" not in existing_columns:
        missing_sql.append("ALTER TABLE sim_buyer_profiles ADD COLUMN city_code VARCHAR(32) NULL")
    if "lat" not in existing_columns:
        missing_sql.append("ALTER TABLE sim_buyer_profiles ADD COLUMN lat FLOAT NULL")
    if "lng" not in existing_columns:
        missing_sql.append("ALTER TABLE sim_buyer_profiles ADD COLUMN lng FLOAT NULL")

    if not missing_sql:
        return

    with engine.begin() as conn:
        for sql in missing_sql:
            conn.execute(text(sql))


def _ensure_shopee_orders_fulfillment_columns():
    inspector = inspect(engine)
    if "shopee_orders" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("shopee_orders")}
    missing_sql = []
    if "tracking_no" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN tracking_no VARCHAR(64) NULL")
    if "waybill_no" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN waybill_no VARCHAR(64) NULL")
    if "ship_by_at" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN ship_by_at DATETIME NULL")
    if "shipped_at" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN shipped_at DATETIME NULL")
    if "delivered_at" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN delivered_at DATETIME NULL")
    if "eta_start_at" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN eta_start_at DATETIME NULL")
    if "eta_end_at" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN eta_end_at DATETIME NULL")
    if "distance_km" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN distance_km FLOAT NULL")
    if "cancelled_at" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN cancelled_at DATETIME NULL")
    if "cancel_reason" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN cancel_reason VARCHAR(64) NULL")
    if "cancel_source" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN cancel_source VARCHAR(32) NULL")
    if "delivery_line_key" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN delivery_line_key VARCHAR(32) NULL")
    if "delivery_line_label" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN delivery_line_label VARCHAR(64) NULL")
    if "listing_id" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN listing_id INTEGER NULL")
    if "variant_id" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN variant_id INTEGER NULL")
    if "stock_fulfillment_status" not in existing_columns:
        missing_sql.append(
            "ALTER TABLE shopee_orders ADD COLUMN stock_fulfillment_status VARCHAR(24) NOT NULL DEFAULT 'in_stock'"
        )
    if "backorder_qty" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN backorder_qty INTEGER NOT NULL DEFAULT 0")
    if "must_restock_before_at" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN must_restock_before_at DATETIME NULL")

    if not missing_sql:
        return

    with engine.begin() as conn:
        for sql in missing_sql:
            conn.execute(text(sql))
        # Best-effort index creation for newly added fulfillment columns.
        if "listing_id" not in existing_columns:
            try:
                conn.execute(text("CREATE INDEX ix_shopee_orders_listing_id ON shopee_orders (listing_id)"))
            except Exception:
                pass
        if "variant_id" not in existing_columns:
            try:
                conn.execute(text("CREATE INDEX ix_shopee_orders_variant_id ON shopee_orders (variant_id)"))
            except Exception:
                pass
        if "must_restock_before_at" not in existing_columns:
            try:
                conn.execute(text("CREATE INDEX ix_shopee_orders_must_restock_before_at ON shopee_orders (must_restock_before_at)"))
            except Exception:
                pass


def _ensure_shopee_order_items_fulfillment_columns():
    inspector = inspect(engine)
    if "shopee_order_items" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("shopee_order_items")}
    missing_sql = []
    if "listing_id" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_order_items ADD COLUMN listing_id INTEGER NULL")
    if "variant_id" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_order_items ADD COLUMN variant_id INTEGER NULL")
    if "product_id" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_order_items ADD COLUMN product_id INTEGER NULL")
    if "stock_fulfillment_status" not in existing_columns:
        missing_sql.append(
            "ALTER TABLE shopee_order_items ADD COLUMN stock_fulfillment_status VARCHAR(24) NOT NULL DEFAULT 'in_stock'"
        )
    if "backorder_qty" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_order_items ADD COLUMN backorder_qty INTEGER NOT NULL DEFAULT 0")
    if "marketing_campaign_type" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_order_items ADD COLUMN marketing_campaign_type VARCHAR(32) NULL")
    if "marketing_campaign_id" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_order_items ADD COLUMN marketing_campaign_id INTEGER NULL")
    if "marketing_campaign_name_snapshot" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_order_items ADD COLUMN marketing_campaign_name_snapshot VARCHAR(255) NULL")
    if "line_role" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_order_items ADD COLUMN line_role VARCHAR(32) NOT NULL DEFAULT 'main'")
    if "original_unit_price" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_order_items ADD COLUMN original_unit_price FLOAT NOT NULL DEFAULT 0")
    if "discounted_unit_price" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_order_items ADD COLUMN discounted_unit_price FLOAT NOT NULL DEFAULT 0")

    if not missing_sql:
        return

    with engine.begin() as conn:
        for sql in missing_sql:
            conn.execute(text(sql))
        if "listing_id" not in existing_columns:
            try:
                conn.execute(text("CREATE INDEX ix_shopee_order_items_listing_id ON shopee_order_items (listing_id)"))
            except Exception:
                pass
        if "variant_id" not in existing_columns:
            try:
                conn.execute(text("CREATE INDEX ix_shopee_order_items_variant_id ON shopee_order_items (variant_id)"))
            except Exception:
                pass
        if "product_id" not in existing_columns:
            try:
                conn.execute(text("CREATE INDEX ix_shopee_order_items_product_id ON shopee_order_items (product_id)"))
            except Exception:
                pass
        if "marketing_campaign_type" not in existing_columns:
            try:
                conn.execute(text("CREATE INDEX ix_shopee_order_items_marketing_campaign_type ON shopee_order_items (marketing_campaign_type)"))
            except Exception:
                pass
        if "marketing_campaign_id" not in existing_columns:
            try:
                conn.execute(text("CREATE INDEX ix_shopee_order_items_marketing_campaign_id ON shopee_order_items (marketing_campaign_id)"))
            except Exception:
                pass
        if "line_role" not in existing_columns:
            try:
                conn.execute(text("CREATE INDEX ix_shopee_order_items_line_role ON shopee_order_items (line_role)"))
            except Exception:
                pass



def _ensure_shopee_orders_marketing_columns():
    inspector = inspect(engine)
    if "shopee_orders" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("shopee_orders")}
    missing_sql = []
    if "marketing_campaign_type" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN marketing_campaign_type VARCHAR(32) NULL")
    if "marketing_campaign_id" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN marketing_campaign_id INTEGER NULL")
    if "marketing_campaign_name_snapshot" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN marketing_campaign_name_snapshot VARCHAR(255) NULL")

    if not missing_sql:
        return

    with engine.begin() as conn:
        for sql in missing_sql:
            conn.execute(text(sql))
        if "marketing_campaign_type" not in existing_columns:
            try:
                conn.execute(text("CREATE INDEX ix_shopee_orders_marketing_campaign_type ON shopee_orders (marketing_campaign_type)"))
            except Exception:
                pass
        if "marketing_campaign_id" not in existing_columns:
            try:
                conn.execute(text("CREATE INDEX ix_shopee_orders_marketing_campaign_id ON shopee_orders (marketing_campaign_id)"))
            except Exception:
                pass


def _ensure_shopee_orders_voucher_columns():
    inspector = inspect(engine)
    if "shopee_orders" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("shopee_orders")}
    missing_sql = []
    if "order_subtotal_amount" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN order_subtotal_amount FLOAT NOT NULL DEFAULT 0")
    if "voucher_campaign_type" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN voucher_campaign_type VARCHAR(32) NULL")
    if "voucher_campaign_id" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN voucher_campaign_id INTEGER NULL")
    if "voucher_name_snapshot" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN voucher_name_snapshot VARCHAR(255) NULL")
    if "voucher_code_snapshot" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN voucher_code_snapshot VARCHAR(64) NULL")
    if "voucher_discount_amount" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN voucher_discount_amount FLOAT NOT NULL DEFAULT 0")

    if not missing_sql:
        return

    with engine.begin() as conn:
        for sql in missing_sql:
            conn.execute(text(sql))
        if "voucher_campaign_type" not in existing_columns:
            try:
                conn.execute(text("CREATE INDEX ix_shopee_orders_voucher_campaign_type ON shopee_orders (voucher_campaign_type)"))
            except Exception:
                pass
        if "voucher_campaign_id" not in existing_columns:
            try:
                conn.execute(text("CREATE INDEX ix_shopee_orders_voucher_campaign_id ON shopee_orders (voucher_campaign_id)"))
            except Exception:
                pass



def _ensure_shopee_orders_shipping_promotion_columns():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    missing_sql = []

    if "shopee_orders" in table_names:
        order_columns = {col["name"] for col in inspector.get_columns("shopee_orders")}
        if "shipping_promotion_campaign_id" not in order_columns:
            missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN shipping_promotion_campaign_id INTEGER NULL")
        if "shipping_promotion_name_snapshot" not in order_columns:
            missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN shipping_promotion_name_snapshot VARCHAR(255) NULL")
        if "shipping_promotion_tier_index" not in order_columns:
            missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN shipping_promotion_tier_index INTEGER NULL")
        if "shipping_fee_before_promotion" not in order_columns:
            missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN shipping_fee_before_promotion FLOAT NOT NULL DEFAULT 0")
        if "shipping_fee_after_promotion" not in order_columns:
            missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN shipping_fee_after_promotion FLOAT NOT NULL DEFAULT 0")
        if "shipping_promotion_discount_amount" not in order_columns:
            missing_sql.append("ALTER TABLE shopee_orders ADD COLUMN shipping_promotion_discount_amount FLOAT NOT NULL DEFAULT 0")
    else:
        order_columns = set()

    if "shopee_order_settlements" in table_names:
        settlement_columns = {col["name"] for col in inspector.get_columns("shopee_order_settlements")}
        if "shipping_promotion_discount_amount" not in settlement_columns:
            missing_sql.append("ALTER TABLE shopee_order_settlements ADD COLUMN shipping_promotion_discount_amount FLOAT NOT NULL DEFAULT 0")
    else:
        settlement_columns = set()

    with engine.begin() as conn:
        for sql in missing_sql:
            conn.execute(text(sql))
        if "shopee_orders" in table_names and "shipping_promotion_campaign_id" not in order_columns:
            try:
                conn.execute(text("CREATE INDEX ix_shopee_orders_shipping_promotion_campaign_id ON shopee_orders (shipping_promotion_campaign_id)"))
            except Exception:
                pass


def _ensure_shopee_shop_voucher_campaigns_columns():
    inspector = inspect(engine)
    if "shopee_shop_voucher_campaigns" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("shopee_shop_voucher_campaigns")}
    missing_sql = []
    if "display_start_at" not in existing_columns:
        missing_sql.append("ALTER TABLE shopee_shop_voucher_campaigns ADD COLUMN display_start_at DATETIME NULL")

    if not missing_sql:
        return

    with engine.begin() as conn:
        for sql in missing_sql:
            conn.execute(text(sql))


def _ensure_shopee_product_voucher_tables():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "shopee_product_voucher_campaigns" not in table_names or "shopee_product_voucher_items" not in table_names:
        return

    campaign_columns = {col["name"] for col in inspector.get_columns("shopee_product_voucher_campaigns")}
    campaign_missing_sql = []
    if "display_start_at" not in campaign_columns:
        campaign_missing_sql.append("ALTER TABLE shopee_product_voucher_campaigns ADD COLUMN display_start_at DATETIME NULL")
    if "selected_product_count" not in campaign_columns:
        campaign_missing_sql.append("ALTER TABLE shopee_product_voucher_campaigns ADD COLUMN selected_product_count INT NOT NULL DEFAULT 0")

    item_columns = {col["name"] for col in inspector.get_columns("shopee_product_voucher_items")}
    item_missing_sql = []
    if "category_key_snapshot" not in item_columns:
        item_missing_sql.append("ALTER TABLE shopee_product_voucher_items ADD COLUMN category_key_snapshot VARCHAR(128) NULL")
    if "category_label_snapshot" not in item_columns:
        item_missing_sql.append("ALTER TABLE shopee_product_voucher_items ADD COLUMN category_label_snapshot VARCHAR(255) NULL")
    if "user_id" not in item_columns:
        item_missing_sql.append("ALTER TABLE shopee_product_voucher_items ADD COLUMN user_id INT NOT NULL DEFAULT 0")
    if "product_id" not in item_columns:
        item_missing_sql.append("ALTER TABLE shopee_product_voucher_items ADD COLUMN product_id INT NULL")
    if "stock_snapshot" not in item_columns:
        item_missing_sql.append("ALTER TABLE shopee_product_voucher_items ADD COLUMN stock_snapshot INT NOT NULL DEFAULT 0")

    if not campaign_missing_sql and not item_missing_sql:
        return

    with engine.begin() as conn:
        for sql in campaign_missing_sql + item_missing_sql:
            conn.execute(text(sql))


def _ensure_shopee_private_voucher_tables():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "shopee_private_voucher_campaigns" not in table_names or "shopee_private_voucher_items" not in table_names:
        return

    campaign_columns = {col["name"] for col in inspector.get_columns("shopee_private_voucher_campaigns")}
    campaign_missing_sql = []
    if "selected_product_count" not in campaign_columns:
        campaign_missing_sql.append("ALTER TABLE shopee_private_voucher_campaigns ADD COLUMN selected_product_count INT NOT NULL DEFAULT 0")
    if "audience_scope" not in campaign_columns:
        campaign_missing_sql.append("ALTER TABLE shopee_private_voucher_campaigns ADD COLUMN audience_scope VARCHAR(32) NOT NULL DEFAULT 'private_code'")
    if "audience_payload" not in campaign_columns:
        campaign_missing_sql.append("ALTER TABLE shopee_private_voucher_campaigns ADD COLUMN audience_payload TEXT NULL")

    item_columns = {col["name"] for col in inspector.get_columns("shopee_private_voucher_items")}
    item_missing_sql = []
    if "category_key_snapshot" not in item_columns:
        item_missing_sql.append("ALTER TABLE shopee_private_voucher_items ADD COLUMN category_key_snapshot VARCHAR(128) NULL")
    if "category_label_snapshot" not in item_columns:
        item_missing_sql.append("ALTER TABLE shopee_private_voucher_items ADD COLUMN category_label_snapshot VARCHAR(255) NULL")
    if "user_id" not in item_columns:
        item_missing_sql.append("ALTER TABLE shopee_private_voucher_items ADD COLUMN user_id INT NOT NULL DEFAULT 0")
    if "product_id" not in item_columns:
        item_missing_sql.append("ALTER TABLE shopee_private_voucher_items ADD COLUMN product_id INT NULL")
    if "stock_snapshot" not in item_columns:
        item_missing_sql.append("ALTER TABLE shopee_private_voucher_items ADD COLUMN stock_snapshot INT NOT NULL DEFAULT 0")

    if not campaign_missing_sql and not item_missing_sql:
        return

    with engine.begin() as conn:
        for sql in campaign_missing_sql + item_missing_sql:
            conn.execute(text(sql))


def _ensure_shopee_live_voucher_tables():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "shopee_live_voucher_campaigns" not in table_names or "shopee_live_voucher_items" not in table_names:
        return

    campaign_columns = {col["name"] for col in inspector.get_columns("shopee_live_voucher_campaigns")}
    campaign_missing_sql = []
    if "display_start_at" not in campaign_columns:
        campaign_missing_sql.append("ALTER TABLE shopee_live_voucher_campaigns ADD COLUMN display_start_at DATETIME NULL")
    if "selected_product_count" not in campaign_columns:
        campaign_missing_sql.append("ALTER TABLE shopee_live_voucher_campaigns ADD COLUMN selected_product_count INT NOT NULL DEFAULT 0")
    if "live_scope" not in campaign_columns:
        campaign_missing_sql.append("ALTER TABLE shopee_live_voucher_campaigns ADD COLUMN live_scope VARCHAR(32) NOT NULL DEFAULT 'all_live_sessions'")
    if "live_payload" not in campaign_columns:
        campaign_missing_sql.append("ALTER TABLE shopee_live_voucher_campaigns ADD COLUMN live_payload TEXT NULL")

    item_columns = {col["name"] for col in inspector.get_columns("shopee_live_voucher_items")}
    item_missing_sql = []
    if "category_key_snapshot" not in item_columns:
        item_missing_sql.append("ALTER TABLE shopee_live_voucher_items ADD COLUMN category_key_snapshot VARCHAR(128) NULL")
    if "category_label_snapshot" not in item_columns:
        item_missing_sql.append("ALTER TABLE shopee_live_voucher_items ADD COLUMN category_label_snapshot VARCHAR(255) NULL")
    if "user_id" not in item_columns:
        item_missing_sql.append("ALTER TABLE shopee_live_voucher_items ADD COLUMN user_id INT NOT NULL DEFAULT 0")
    if "product_id" not in item_columns:
        item_missing_sql.append("ALTER TABLE shopee_live_voucher_items ADD COLUMN product_id INT NULL")
    if "stock_snapshot" not in item_columns:
        item_missing_sql.append("ALTER TABLE shopee_live_voucher_items ADD COLUMN stock_snapshot INT NOT NULL DEFAULT 0")

    if not campaign_missing_sql and not item_missing_sql:
        return

    with engine.begin() as conn:
        for sql in campaign_missing_sql + item_missing_sql:
            conn.execute(text(sql))



def _ensure_shopee_video_voucher_tables():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "shopee_video_voucher_campaigns" not in table_names or "shopee_video_voucher_items" not in table_names:
        return

    campaign_columns = {col["name"] for col in inspector.get_columns("shopee_video_voucher_campaigns")}
    campaign_missing_sql = []
    if "display_start_at" not in campaign_columns:
        campaign_missing_sql.append("ALTER TABLE shopee_video_voucher_campaigns ADD COLUMN display_start_at DATETIME NULL")
    if "selected_product_count" not in campaign_columns:
        campaign_missing_sql.append("ALTER TABLE shopee_video_voucher_campaigns ADD COLUMN selected_product_count INT NOT NULL DEFAULT 0")
    if "video_scope" not in campaign_columns:
        campaign_missing_sql.append("ALTER TABLE shopee_video_voucher_campaigns ADD COLUMN video_scope VARCHAR(32) NOT NULL DEFAULT 'all_videos'")
    if "video_payload" not in campaign_columns:
        campaign_missing_sql.append("ALTER TABLE shopee_video_voucher_campaigns ADD COLUMN video_payload TEXT NULL")

    item_columns = {col["name"] for col in inspector.get_columns("shopee_video_voucher_items")}
    item_missing_sql = []
    if "category_key_snapshot" not in item_columns:
        item_missing_sql.append("ALTER TABLE shopee_video_voucher_items ADD COLUMN category_key_snapshot VARCHAR(128) NULL")
    if "category_label_snapshot" not in item_columns:
        item_missing_sql.append("ALTER TABLE shopee_video_voucher_items ADD COLUMN category_label_snapshot VARCHAR(255) NULL")
    if "user_id" not in item_columns:
        item_missing_sql.append("ALTER TABLE shopee_video_voucher_items ADD COLUMN user_id INT NOT NULL DEFAULT 0")
    if "product_id" not in item_columns:
        item_missing_sql.append("ALTER TABLE shopee_video_voucher_items ADD COLUMN product_id INT NULL")
    if "stock_snapshot" not in item_columns:
        item_missing_sql.append("ALTER TABLE shopee_video_voucher_items ADD COLUMN stock_snapshot INT NOT NULL DEFAULT 0")

    if not campaign_missing_sql and not item_missing_sql:
        return

    with engine.begin() as conn:
        for sql in campaign_missing_sql + item_missing_sql:
            conn.execute(text(sql))



def _ensure_shopee_follow_voucher_tables():
    inspector = inspect(engine)
    if "shopee_follow_voucher_campaigns" not in inspector.get_table_names():
        return

    campaign_columns = {col["name"] for col in inspector.get_columns("shopee_follow_voucher_campaigns")}
    missing_sql = []
    expected_columns = {
        "valid_days_after_claim": "ALTER TABLE shopee_follow_voucher_campaigns ADD COLUMN valid_days_after_claim INT NOT NULL DEFAULT 7",
        "claimed_count": "ALTER TABLE shopee_follow_voucher_campaigns ADD COLUMN claimed_count INT NOT NULL DEFAULT 0",
        "trigger_type": "ALTER TABLE shopee_follow_voucher_campaigns ADD COLUMN trigger_type VARCHAR(32) NOT NULL DEFAULT 'follow_shop'",
        "display_channels": "ALTER TABLE shopee_follow_voucher_campaigns ADD COLUMN display_channels TEXT NULL",
        "sales_amount": "ALTER TABLE shopee_follow_voucher_campaigns ADD COLUMN sales_amount DOUBLE NOT NULL DEFAULT 0",
        "order_count": "ALTER TABLE shopee_follow_voucher_campaigns ADD COLUMN order_count INT NOT NULL DEFAULT 0",
        "buyer_count": "ALTER TABLE shopee_follow_voucher_campaigns ADD COLUMN buyer_count INT NOT NULL DEFAULT 0",
    }
    for column_name, sql in expected_columns.items():
        if column_name not in campaign_columns:
            missing_sql.append(sql)

    if not missing_sql:
        return

    with engine.begin() as conn:
        for sql in missing_sql:
            conn.execute(text(sql))


def _ensure_shopee_buyer_follow_state_table():
    inspector = inspect(engine)
    if "shopee_buyer_follow_states" not in inspector.get_table_names():
        return

    existing_indexes = {idx["name"] for idx in inspector.get_indexes("shopee_buyer_follow_states")}
    with engine.begin() as conn:
        if "ix_shopee_buyer_follow_states_run_user" not in existing_indexes:
            try:
                conn.execute(text("CREATE INDEX ix_shopee_buyer_follow_states_run_user ON shopee_buyer_follow_states (run_id, user_id)"))
            except Exception:
                pass
        if "ix_shopee_buyer_follow_states_source_campaign" not in existing_indexes:
            try:
                conn.execute(text("CREATE INDEX ix_shopee_buyer_follow_states_source_campaign ON shopee_buyer_follow_states (source_campaign_id)"))
            except Exception:
                pass



def _ensure_shopee_auto_reply_settings_table():
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    if "shopee_auto_reply_settings" not in existing_tables:
        return

    existing_indexes = {idx["name"] for idx in inspector.get_indexes("shopee_auto_reply_settings")}
    with engine.begin() as conn:
        if "ix_shopee_auto_reply_settings_run_user_enabled" not in existing_indexes:
            try:
                conn.execute(text("CREATE INDEX ix_shopee_auto_reply_settings_run_user_enabled ON shopee_auto_reply_settings (run_id, user_id, enabled)"))
            except Exception:
                pass



def _ensure_shopee_quick_reply_tables():
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        if "shopee_quick_reply_groups" in existing_tables:
            group_indexes = {idx["name"] for idx in inspector.get_indexes("shopee_quick_reply_groups")}
            if "ix_shopee_quick_reply_groups_run_user_sort" not in group_indexes:
                try:
                    conn.execute(text("CREATE INDEX ix_shopee_quick_reply_groups_run_user_sort ON shopee_quick_reply_groups (run_id, user_id, sort_order)"))
                except Exception:
                    pass
            if "ix_shopee_quick_reply_groups_run_user_enabled" not in group_indexes:
                try:
                    conn.execute(text("CREATE INDEX ix_shopee_quick_reply_groups_run_user_enabled ON shopee_quick_reply_groups (run_id, user_id, enabled)"))
                except Exception:
                    pass
        if "shopee_quick_reply_messages" in existing_tables:
            message_indexes = {idx["name"] for idx in inspector.get_indexes("shopee_quick_reply_messages")}
            if "ix_shopee_quick_reply_messages_group_sort" not in message_indexes:
                try:
                    conn.execute(text("CREATE INDEX ix_shopee_quick_reply_messages_group_sort ON shopee_quick_reply_messages (group_id, sort_order)"))
                except Exception:
                    pass
            if "ix_shopee_quick_reply_messages_run_user" not in message_indexes:
                try:
                    conn.execute(text("CREATE INDEX ix_shopee_quick_reply_messages_run_user ON shopee_quick_reply_messages (run_id, user_id)"))
                except Exception:
                    pass



def _ensure_shopee_shipping_fee_promotion_tables():
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        if "shopee_shipping_fee_promotion_campaigns" in existing_tables:
            campaign_indexes = {idx["name"] for idx in inspector.get_indexes("shopee_shipping_fee_promotion_campaigns")}
            if "ix_shopee_shipping_fee_promotions_run_user_status" not in campaign_indexes:
                try:
                    conn.execute(text("CREATE INDEX ix_shopee_shipping_fee_promotions_run_user_status ON shopee_shipping_fee_promotion_campaigns (run_id, user_id, status)"))
                except Exception:
                    pass
            if "ix_shopee_shipping_fee_promotions_run_user_time" not in campaign_indexes:
                try:
                    conn.execute(text("CREATE INDEX ix_shopee_shipping_fee_promotions_run_user_time ON shopee_shipping_fee_promotion_campaigns (run_id, user_id, start_at, end_at)"))
                except Exception:
                    pass
        if "shopee_shipping_fee_promotion_channels" in existing_tables:
            channel_indexes = {idx["name"] for idx in inspector.get_indexes("shopee_shipping_fee_promotion_channels")}
            if "ix_shopee_shipping_fee_promotion_channels_campaign" not in channel_indexes:
                try:
                    conn.execute(text("CREATE INDEX ix_shopee_shipping_fee_promotion_channels_campaign ON shopee_shipping_fee_promotion_channels (campaign_id)"))
                except Exception:
                    pass
        if "shopee_shipping_fee_promotion_tiers" in existing_tables:
            tier_indexes = {idx["name"] for idx in inspector.get_indexes("shopee_shipping_fee_promotion_tiers")}
            if "ix_shopee_shipping_fee_promotion_tiers_campaign" not in tier_indexes:
                try:
                    conn.execute(text("CREATE INDEX ix_shopee_shipping_fee_promotion_tiers_campaign ON shopee_shipping_fee_promotion_tiers (campaign_id)"))
                except Exception:
                    pass



def _ensure_shopee_order_generation_log_indexes():
    if DATABASE_URL.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "shopee_order_generation_logs" not in inspector.get_table_names():
        return

    existing_indexes = {
        idx["name"] for idx in inspector.get_indexes("shopee_order_generation_logs")
    }
    with engine.begin() as conn:
        if "ix_shopee_order_generation_logs_run_user_tick_id" not in existing_indexes:
            try:
                conn.execute(
                    text(
                        "CREATE INDEX ix_shopee_order_generation_logs_run_user_tick_id "
                        "ON shopee_order_generation_logs (run_id, user_id, tick_time, id)"
                    )
                )
            except Exception:
                pass
        if "ix_shopee_order_generation_logs_run_user_created_at" not in existing_indexes:
            try:
                conn.execute(
                    text(
                        "CREATE INDEX ix_shopee_order_generation_logs_run_user_created_at "
                        "ON shopee_order_generation_logs (run_id, user_id, created_at)"
                    )
                )
            except Exception:
                pass


def _ensure_table_comments():
    if DATABASE_URL.startswith("sqlite"):
        return

    table_comments = {
        "users": "系统用户表（管理员/学生账号）",
        "oss_storage_configs": "OSS 存储配置表（MinIO/S3）",
        "schools": "学校信息表",
        "game_runs": "模拟对局运行主表",
        "market_products": "选品市场商品池",
        "procurement_orders": "采购订单主表",
        "procurement_order_items": "采购订单明细表",
        "logistics_shipments": "国际物流运单主表",
        "logistics_shipment_orders": "物流运单与采购订单关联表",
        "warehouse_strategies": "海外仓策略配置表",
        "warehouse_inbound_orders": "海外仓入库订单表",
        "inventory_lots": "库存批次表",
        "inventory_stock_movements": "库存变动流水表（采购入库/订单占用/取消释放/补货冲减）",
        "shopee_listings": "Shopee 正式商品表",
        "shopee_listing_quality_scores": "Shopee 商品内容质量评分记录表",
        "shopee_listing_drafts": "Shopee 商品草稿主表",
        "shopee_listing_draft_images": "Shopee 草稿图片表",
        "shopee_spec_templates": "Shopee 类目规格模板字段定义表",
        "shopee_spec_template_options": "Shopee 规格模板下拉选项表",
        "shopee_category_nodes": "Shopee 类目树节点表",
        "shopee_listing_draft_spec_values": "Shopee 草稿规格值表",
        "shopee_listing_spec_values": "Shopee 正式商品规格值表",
        "shopee_listing_images": "Shopee 正式商品图片表",
        "shopee_listing_variants": "Shopee 正式商品变体表",
        "shopee_listing_wholesale_tiers": "Shopee 正式商品批发价阶梯表",
        "shopee_orders": "Shopee 店铺订单主表",
        "shopee_order_items": "Shopee 订单明细表",
        "shopee_order_logistics_events": "Shopee 订单物流轨迹事件表",
        "shopee_order_settlements": "Shopee 订单结算明细表",
        "shopee_finance_ledger_entries": "Shopee 财务流水明细表（回款/支出）",
        "game_run_cash_adjustments": "工作台资金调账记录表（含 Shopee 提现转入）",
        "shopee_bank_accounts": "Shopee 银行账户表（收款账户管理）",
        "shopee_marketing_announcements": "Shopee 营销中心公告表",
        "shopee_marketing_tools": "Shopee 营销工具配置表",
        "shopee_marketing_events": "Shopee 营销活动横幅表",
        "shopee_user_marketing_preferences": "Shopee 营销中心用户偏好表",
        "shopee_discount_campaigns": "Shopee 折扣活动主表",
        "shopee_discount_campaign_items": "Shopee 折扣活动商品明细表",
        "shopee_discount_drafts": "Shopee 折扣创建页草稿主表",
        "shopee_discount_draft_items": "Shopee 折扣创建页草稿商品明细表",
        "shopee_discount_performance_daily": "Shopee 折扣活动日表现快照表",
        "shopee_user_discount_preferences": "Shopee 折扣页用户筛选偏好表",
        "shopee_addon_campaigns": "Shopee 加价购/满额赠活动主表",
        "shopee_addon_campaign_main_items": "Shopee 加价购/满额赠主商品明细表",
        "shopee_addon_campaign_reward_items": "Shopee 加价购商品/满额赠赠品明细表",
        "shopee_addon_drafts": "Shopee 加价购/满额赠创建页草稿主表",
        "shopee_addon_draft_main_items": "Shopee 加价购/满额赠草稿主商品明细表",
        "shopee_addon_draft_reward_items": "Shopee 加价购/满额赠草稿加购商品/赠品明细表",
        "shopee_flash_sale_campaigns": "Shopee 我的店铺限时抢购活动主表",
        "shopee_flash_sale_campaign_items": "Shopee 我的店铺限时抢购活动商品表",
        "shopee_flash_sale_traffic_events": "Shopee 我的店铺限时抢购浏览/点击模拟事件表",
        "shopee_flash_sale_drafts": "Shopee 我的店铺限时抢购草稿主表",
        "shopee_flash_sale_draft_items": "Shopee 我的店铺限时抢购草稿商品表",
        "shopee_flash_sale_slots": "Shopee 我的店铺限时抢购时间段配置表",
        "shopee_flash_sale_category_rules": "Shopee 我的店铺限时抢购类目商品条件配置表",
        "shopee_shop_voucher_campaigns": "Shopee 店铺代金券活动表",
        "shopee_product_voucher_campaigns": "Shopee 商品代金券活动表",
        "shopee_product_voucher_items": "Shopee 商品代金券适用商品明细表",
        "shopee_private_voucher_campaigns": "Shopee 专属代金券活动表",
        "shopee_private_voucher_items": "Shopee 专属代金券适用商品明细表",
        "shopee_live_voucher_campaigns": "Shopee 直播代金券活动表",
        "shopee_live_voucher_items": "Shopee 直播代金券适用商品明细表",
        "shopee_video_voucher_campaigns": "Shopee 视频代金券活动表",
        "shopee_video_voucher_items": "Shopee 视频代金券适用商品明细表",
        "shopee_follow_voucher_campaigns": "Shopee 关注礼代金券活动表",
        "shopee_buyer_follow_states": "Shopee 模拟买家店铺关注状态表",
        "shopee_auto_reply_settings": "Shopee 自动回复配置表",
        "shopee_quick_reply_preferences": "Shopee 快捷回复用户偏好表",
        "shopee_quick_reply_groups": "Shopee 快捷回复分组表",
        "shopee_quick_reply_messages": "Shopee 快捷回复消息表",
        "shopee_shipping_fee_promotion_campaigns": "Shopee 运费促销活动主表",
        "shopee_shipping_fee_promotion_channels": "Shopee 运费促销适用物流渠道表",
        "shopee_shipping_fee_promotion_tiers": "Shopee 运费促销门槛层级表",
        "shopee_order_generation_logs": "Shopee 订单模拟生成日志表",
        "warehouse_landmarks": "海外仓地标点位表",
        "sim_buyer_profiles": "买家画像池表（模拟订单买家）",
    }

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table_name, comment in table_comments.items():
            if table_name not in existing_tables:
                continue
            conn.execute(text(f"ALTER TABLE `{table_name}` COMMENT = :comment"), {"comment": comment})


def _ensure_column_comments():
    if DATABASE_URL.startswith("sqlite"):
        return

    column_comments = {
        "users": {
            "id": "主键ID",
            "public_id": "外显用户ID",
            "username": "登录用户名",
            "password_hash": "密码哈希",
            "role": "用户角色",
            "school_id": "学校ID",
            "major": "专业",
            "class_name": "班级",
            "full_name": "姓名",
            "is_active": "是否启用",
            "created_at": "创建时间",
        },
        "oss_storage_configs": {
            "id": "主键ID",
            "provider": "存储提供商",
            "endpoint": "OSS访问端点",
            "domain": "资源访问域名",
            "bucket": "Bucket名称",
            "access_key": "访问密钥ID",
            "access_secret": "访问密钥Secret",
            "is_active": "是否启用",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "schools": {"id": "主键ID", "name": "学校名称", "created_at": "创建时间"},
        "game_runs": {
            "id": "主键ID",
            "user_id": "用户ID",
            "initial_cash": "初始资金",
            "market": "目标市场",
            "duration_days": "兼容展示的真实运行天数",
            "base_real_duration_days": "初始真实运行天数快照",
            "base_game_days": "初始游戏天数快照",
            "total_game_days": "当前总游戏天数",
            "manual_end_time": "管理员手动指定的有效结束时间",
            "day_index": "当前游戏日快照",
            "status": "对局状态",
            "created_at": "创建时间",
        },
        "market_products": {
            "id": "主键ID",
            "market": "市场",
            "board_type": "榜单类型",
            "category": "商品类目",
            "product_name": "商品名称",
            "supplier_price": "供货价",
            "suggested_price": "建议售价",
            "monthly_sales": "月销量",
            "monthly_revenue": "月销售额",
            "new_score": "新品指数",
            "hot_score": "热度指数",
            "growth_rate": "增长率",
            "competition_level": "竞争等级",
            "cover_url": "封面图地址",
            "created_at": "创建时间",
        },
        "procurement_orders": {
            "id": "主键ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "total_amount": "采购总金额",
            "created_at": "创建时间",
        },
        "procurement_order_items": {
            "id": "主键ID",
            "order_id": "采购订单ID",
            "product_id": "商品池商品ID",
            "product_name_snapshot": "下单时商品名快照",
            "unit_price": "单价",
            "quantity": "数量",
            "line_total": "行项目总价",
        },
        "logistics_shipments": {
            "id": "主键ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "market": "市场",
            "forwarder_key": "货代方案Key",
            "forwarder_label": "货代方案名称",
            "customs_key": "清关方案Key",
            "customs_label": "清关方案名称",
            "cargo_value": "货值",
            "logistics_fee": "物流费用",
            "customs_fee": "清关费用",
            "total_fee": "总费用",
            "transport_days": "运输时效(天)",
            "customs_days": "清关时效(天)",
            "created_at": "创建时间",
        },
        "logistics_shipment_orders": {
            "id": "主键ID",
            "shipment_id": "运单ID",
            "procurement_order_id": "采购订单ID",
            "order_total_amount": "订单总金额",
            "order_total_quantity": "订单总数量",
        },
        "warehouse_strategies": {
            "id": "主键ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "market": "市场",
            "warehouse_mode": "仓储模式",
            "warehouse_location": "仓库位置",
            "one_time_cost": "一次性成本",
            "inbound_cost": "入仓成本",
            "rent_cost": "租金成本",
            "total_cost": "总成本",
            "delivery_eta_score": "配送时效评分",
            "fulfillment_accuracy": "履约准确率",
            "warehouse_cost_per_order": "单均仓储成本",
            "status": "状态",
            "created_at": "创建时间",
        },
        "warehouse_inbound_orders": {
            "id": "主键ID",
            "run_id": "对局ID",
            "strategy_id": "仓储策略ID",
            "shipment_id": "物流运单ID",
            "total_quantity": "入库总数量",
            "total_value": "入库总货值",
            "status": "入库状态",
            "created_at": "创建时间",
            "completed_at": "完成时间",
        },
        "inventory_lots": {
            "id": "主键ID",
            "run_id": "对局ID",
            "product_id": "商品池商品ID",
            "inbound_order_id": "入库订单ID",
            "quantity_available": "可用库存",
            "quantity_locked": "锁定库存",
            "reserved_qty": "预占库存数量（已被订单占用未出库）",
            "backorder_qty": "缺货待补数量",
            "unit_cost": "单位成本",
            "last_restocked_at": "最近补货时间",
            "created_at": "创建时间",
        },
        "inventory_stock_movements": {
            "id": "主键ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "product_id": "商品池商品ID",
            "listing_id": "Shopee商品ID",
            "variant_id": "Shopee变体ID",
            "inventory_lot_id": "库存批次ID",
            "biz_order_id": "业务订单ID",
            "movement_type": "库存变动类型(purchase_in/order_reserve/order_ship/cancel_release/restock_fill)",
            "qty_delta_on_hand": "现货库存变动量",
            "qty_delta_reserved": "预占库存变动量",
            "qty_delta_backorder": "缺货待补变动量",
            "biz_ref": "业务单号(采购单号/订单号)",
            "remark": "备注",
            "created_at": "创建时间",
        },
        "shopee_listings": {
            "id": "主键ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "product_id": "商品池商品ID",
            "category_id": "类目节点ID",
            "title": "商品标题",
            "category": "类目路径",
            "gtin": "GTIN编码",
            "sku_code": "SKU编码",
            "model_id": "款式ID",
            "description": "商品描述",
            "video_url": "视频地址",
            "cover_url": "封面图地址",
            "price": "售价",
            "original_price": "原价",
            "sales_count": "销量",
            "stock_available": "可售库存",
            "min_purchase_qty": "最低购买数量",
            "max_purchase_qty": "最高购买数量",
            "max_purchase_mode": "最高购买数量模式(none/per_order/per_time_period)",
            "max_purchase_period_start_date": "时间段限购开始日期",
            "max_purchase_period_end_date": "时间段限购结束日期",
            "max_purchase_period_qty": "时间段限购数量",
            "max_purchase_period_days": "时间段周期天数",
            "max_purchase_period_model": "时间段周期模式(single/recurring)",
            "weight_kg": "商品重量(kg)",
            "parcel_length_cm": "包裹长度(cm)",
            "parcel_width_cm": "包裹宽度(cm)",
            "parcel_height_cm": "包裹高度(cm)",
            "shipping_variation_dimension_enabled": "变体是否使用不同重量/尺寸",
            "shipping_standard_bulk": "是否启用标准配送(大件)",
            "shipping_standard": "是否启用标准配送(国内)",
            "shipping_express": "是否启用快速配送",
            "preorder_enabled": "是否启用预售",
            "insurance_enabled": "是否启用运费险",
            "condition_label": "商品状况",
            "schedule_publish_at": "定时上架时间",
            "parent_sku": "父SKU",
            "status": "商品状态",
            "quality_status": "质检状态",
            "quality_total_score": "内容质量总分",
            "quality_scored_at": "最近评分时间",
            "quality_score_version": "评分规则版本",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_listing_quality_scores": {
            "id": "主键ID",
            "listing_id": "商品ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "score_version": "评分版本",
            "provider": "评分提供方",
            "text_model": "文本评分模型",
            "vision_model": "视觉评分模型",
            "prompt_hash": "评分提示词哈希",
            "content_hash": "内容哈希",
            "rule_score": "规则评分",
            "vision_score": "视觉评分",
            "text_score": "文案评分",
            "consistency_score": "图文一致性评分",
            "total_score": "总分",
            "quality_status": "内容质量状态",
            "reasons_json": "扣分原因JSON",
            "suggestions_json": "优化建议JSON",
            "raw_result_json": "模型原始结果JSON",
            "is_latest": "是否为最新评分",
            "created_at": "创建时间",
        },
        "shopee_listing_drafts": {
            "id": "主键ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "category_id": "类目节点ID",
            "title": "商品标题",
            "category": "类目路径",
            "gtin": "GTIN编码",
            "description": "商品描述",
            "video_url": "视频地址",
            "cover_url": "封面图地址",
            "status": "草稿状态",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_listing_draft_images": {
            "id": "主键ID",
            "draft_id": "草稿ID",
            "image_url": "图片地址",
            "image_ratio": "图片比例",
            "sort_order": "排序号",
            "is_cover": "是否封面",
            "created_at": "创建时间",
        },
        "shopee_spec_templates": {
            "id": "主键ID",
            "category_root": "一级类目(兼容旧字段)",
            "category_id": "类目节点ID",
            "attr_key": "字段键",
            "attr_label": "字段名",
            "input_type": "字段类型(text/select)",
            "is_required": "是否必填",
            "sort_order": "排序号",
            "is_active": "是否启用",
            "created_at": "创建时间",
        },
        "shopee_spec_template_options": {
            "id": "主键ID",
            "template_id": "模板字段ID",
            "option_value": "选项值",
            "option_label": "选项展示名",
            "sort_order": "排序号",
            "is_active": "是否启用",
            "created_at": "创建时间",
        },
        "shopee_category_nodes": {
            "id": "主键ID",
            "parent_id": "父节点ID",
            "level": "层级",
            "name": "节点名称",
            "path": "完整路径",
            "sort_order": "排序号",
            "is_active": "是否启用",
            "created_at": "创建时间",
        },
        "shopee_listing_draft_spec_values": {
            "id": "主键ID",
            "draft_id": "草稿ID",
            "attr_key": "字段键",
            "attr_label": "字段名",
            "attr_value": "字段值",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_listing_spec_values": {
            "id": "主键ID",
            "listing_id": "正式商品ID",
            "attr_key": "字段键",
            "attr_label": "字段名",
            "attr_value": "字段值",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_listing_images": {
            "id": "主键ID",
            "listing_id": "正式商品ID",
            "image_url": "图片地址",
            "image_ratio": "图片比例",
            "sort_order": "排序号",
            "is_cover": "是否封面",
            "created_at": "创建时间",
        },
        "shopee_listing_variants": {
            "id": "主键ID",
            "listing_id": "正式商品ID",
            "variant_name": "变体名称",
            "option_value": "变体选项值",
            "option_note": "变体选项说明",
            "price": "变体价格",
            "stock": "变体库存",
            "sales_count": "变体销量",
            "oversell_limit": "变体超卖上限（件）",
            "oversell_used": "变体已用超卖数量（件）",
            "sku": "变体SKU",
            "gtin": "变体GTIN",
            "item_without_gtin": "是否无GTIN",
            "weight_kg": "变体重量(kg)",
            "parcel_length_cm": "变体包裹长(cm)",
            "parcel_width_cm": "变体包裹宽(cm)",
            "parcel_height_cm": "变体包裹高(cm)",
            "image_url": "变体图片地址",
            "sort_order": "排序号",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_listing_wholesale_tiers": {
            "id": "主键ID",
            "listing_id": "正式商品ID",
            "tier_no": "价格阶梯序号",
            "min_qty": "最小购买量",
            "max_qty": "最大购买量",
            "unit_price": "阶梯单价",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_orders": {
            "id": "主键ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "order_no": "订单号",
            "buyer_name": "买家名称",
            "buyer_payment": "买家支付金额",
            "order_type": "订单类型",
            "listing_id": "关联商品ID",
            "variant_id": "关联变体ID",
            "type_bucket": "订单分组",
            "process_status": "处理状态",
            "stock_fulfillment_status": "库存履约状态(in_stock/backorder/restocked)",
            "backorder_qty": "待补货数量（件）",
            "must_restock_before_at": "最晚补货时间（游戏时间）",
            "shipping_priority": "发货优先级",
            "shipping_channel": "物流渠道",
            "delivery_line_key": "履约线路键(economy/standard/express)",
            "delivery_line_label": "履约线路展示名(如快速线/标准线/经济线)",
            "destination": "收货地区",
            "countdown_text": "倒计时文案",
            "action_text": "操作文案",
            "ship_by_date": "最晚发货时间",
            "tracking_no": "快递追踪号",
            "waybill_no": "面单号",
            "ship_by_at": "最晚发货时间",
            "shipped_at": "实际发货时间",
            "delivered_at": "签收时间",
            "eta_start_at": "预计送达开始时间",
            "eta_end_at": "预计送达结束时间",
            "distance_km": "仓点至买家距离(公里)",
            "cancelled_at": "取消时间",
            "cancel_reason": "取消原因",
            "cancel_source": "取消来源",
            "marketing_campaign_type": "命中的营销活动类型(discount/bundle/add_on/gift)",
            "marketing_campaign_id": "命中的营销活动ID",
            "marketing_campaign_name_snapshot": "下单时命中的营销活动名称快照",
            "order_subtotal_amount": "代金券抵扣前订单商品小计，单位RM",
            "voucher_campaign_type": "订单使用的代金券类型(shop_voucher/product_voucher/private_voucher/live_voucher/video_voucher/follow_voucher)",
            "voucher_campaign_id": "订单使用的代金券活动ID",
            "voucher_name_snapshot": "下单时使用的代金券名称快照",
            "voucher_code_snapshot": "下单时使用的代金券代码快照",
            "voucher_discount_amount": "本单代金券抵扣金额，单位RM",
            "shipping_promotion_campaign_id": "命中的运费促销活动ID",
            "shipping_promotion_name_snapshot": "命中的运费促销名称快照",
            "shipping_promotion_tier_index": "命中的运费促销层级序号",
            "shipping_fee_before_promotion": "运费促销前买家侧原始运费，单位RM",
            "shipping_fee_after_promotion": "运费促销后买家侧应付运费，单位RM",
            "shipping_promotion_discount_amount": "本单运费促销优惠金额，单位RM",
            "created_at": "创建时间",
        },
        "shopee_order_items": {
            "id": "主键ID",
            "order_id": "订单ID",
            "listing_id": "订单项对应的Shopee商品ID",
            "variant_id": "订单项对应的Shopee变体ID",
            "product_id": "订单项对应的库存商品ID",
            "product_name": "商品名称",
            "variant_name": "规格名称",
            "quantity": "购买数量",
            "unit_price": "成交单价",
            "image_url": "商品图地址",
            "stock_fulfillment_status": "订单项库存履约状态(in_stock/backorder/restocked)",
            "backorder_qty": "订单项待补货数量（件）",
            "marketing_campaign_type": "订单明细命中的营销活动类型(discount/bundle/add_on/gift)",
            "marketing_campaign_id": "订单明细命中的营销活动ID",
            "marketing_campaign_name_snapshot": "订单明细命中的营销活动名称快照",
            "line_role": "订单明细角色(main/add_on/gift/bundle_component)",
            "original_unit_price": "订单明细原始单价",
            "discounted_unit_price": "订单明细实际成交单价，赠品为0",
        },
        "shopee_order_logistics_events": {
            "id": "主键ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "order_id": "订单ID",
            "event_code": "事件编码",
            "event_title": "事件标题",
            "event_desc": "事件描述",
            "event_time": "事件时间",
            "created_at": "创建时间",
        },
        "shopee_order_settlements": {
            "id": "主键ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "order_id": "订单ID",
            "buyer_payment": "买家实付金额",
            "platform_commission_amount": "平台佣金金额",
            "payment_fee_amount": "支付手续费金额",
            "shipping_cost_amount": "运费成本金额",
            "shipping_subsidy_amount": "运费补贴金额",
            "shipping_promotion_discount_amount": "卖家承担的运费促销优惠金额，单位RM",
            "net_income_amount": "净收入金额（已扣除运费促销优惠）",
            "settlement_status": "结算状态",
            "settled_at": "结算时间",
            "created_at": "创建时间",
        },
        "shopee_finance_ledger_entries": {
            "id": "主键ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "order_id": "关联订单ID（非订单流水可为空）",
            "entry_type": "流水类型（income_from_order/adjustment/withdrawal）",
            "direction": "资金方向（in/out）",
            "amount": "流水金额",
            "balance_after": "该笔流水后余额快照",
            "status": "流水状态（completed/pending/voided）",
            "remark": "备注",
            "credited_at": "入账时间（游戏时间）",
            "created_at": "创建时间",
        },
        "game_run_cash_adjustments": {
            "id": "主键ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "source": "调账来源（如 shopee_withdrawal）",
            "direction": "资金方向（in/out）",
            "amount": "调账金额（RMB）",
            "remark": "备注",
            "related_ledger_id": "关联 Shopee 财务流水ID",
            "created_at": "创建时间",
        },
        "shopee_bank_accounts": {
            "id": "主键ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "bank_name": "银行名称",
            "account_holder": "持卡人姓名",
            "account_no": "银行卡号（完整值）",
            "account_no_masked": "银行卡号脱敏值",
            "currency": "币种（RM）",
            "is_default": "是否默认收款账户",
            "verify_status": "校验状态（verified/pending）",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_marketing_announcements": {
            "id": "主键ID",
            "market": "市场",
            "lang": "语言",
            "title": "公告标题",
            "summary": "公告摘要",
            "badge_text": "徽标文案",
            "priority": "优先级（越高越靠前）",
            "start_at": "开始展示时间",
            "end_at": "结束展示时间",
            "status": "状态(draft/published/offline)",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_marketing_tools": {
            "id": "主键ID",
            "tool_key": "工具唯一键",
            "tool_name": "工具名称",
            "tag_type": "能力标签类型(boost_sales/increase_traffic/improve_engagement)",
            "description": "工具描述",
            "icon_key": "图标键",
            "target_route": "目标路由",
            "sort_order": "排序号",
            "is_enabled": "是否启用",
            "is_visible": "是否显示",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_marketing_events": {
            "id": "主键ID",
            "market": "市场",
            "lang": "语言",
            "title": "活动标题",
            "image_url": "横幅图片地址或标识",
            "jump_url": "点击跳转地址",
            "start_at": "开始时间",
            "end_at": "结束时间",
            "status": "状态(upcoming/ongoing/ended/offline)",
            "sort_order": "排序号",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_user_marketing_preferences": {
            "id": "主键ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "tools_collapsed": "营销工具区是否折叠",
            "last_viewed_at": "最近查看时间",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_discount_campaigns": {
            "id": "主键ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "campaign_type": "活动类型(discount/bundle/add_on)",
            "campaign_name": "活动名称",
            "campaign_status": "活动状态(draft/upcoming/ongoing/ended/disabled)",
            "start_at": "活动开始时间",
            "end_at": "活动结束时间",
            "market": "市场",
            "currency": "币种",
            "rules_json": "活动规则JSON",
            "share_token": "分享标识Token",
            "source_campaign_id": "来源活动ID(复制场景)",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_discount_campaign_items": {
            "id": "主键ID",
            "campaign_id": "折扣活动ID",
            "listing_id": "Shopee商品ID",
            "variant_id": "Shopee变体ID",
            "product_name_snapshot": "活动商品名称快照",
            "image_url_snapshot": "活动商品图片快照",
            "sku_snapshot": "活动商品SKU快照",
            "original_price": "原始售价",
            "discount_type": "折扣规则类型(percent/fixed_price/bundle/add_on)",
            "discount_value": "折扣值",
            "final_price": "活动最终价",
            "sort_order": "排序号",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_discount_drafts": {
            "id": "主键ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "campaign_type": "活动类型(discount)",
            "campaign_name": "活动名称",
            "start_at": "活动开始时间",
            "end_at": "活动结束时间",
            "status": "草稿状态(draft)",
            "source_campaign_id": "来源活动ID(复制场景)",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_discount_draft_items": {
            "id": "主键ID",
            "draft_id": "草稿ID",
            "listing_id": "Shopee商品ID",
            "variant_id": "Shopee变体ID",
            "product_name_snapshot": "草稿商品名称快照",
            "image_url_snapshot": "草稿商品图片快照",
            "sku_snapshot": "草稿商品SKU快照",
            "original_price": "原始售价",
            "discount_mode": "折扣模式(percent/final_price)",
            "discount_percent": "折扣比例",
            "final_price": "折后价",
            "activity_stock_limit": "活动库存上限",
            "sort_order": "排序号",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_discount_performance_daily": {
            "id": "主键ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "campaign_id": "折扣活动ID",
            "stat_date": "统计日期",
            "sales_amount": "销售额",
            "orders_count": "订单数",
            "units_sold": "售出件数",
            "buyers_count": "买家数",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_user_discount_preferences": {
            "id": "主键ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "selected_discount_type": "最近选择的活动类型筛选",
            "selected_status": "最近选择的状态筛选",
            "search_field": "最近选择的搜索字段",
            "keyword": "最近输入的关键字",
            "date_from": "最近选择的开始时间",
            "date_to": "最近选择的结束时间",
            "last_viewed_at": "最近查看时间",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_addon_campaigns": {
            "id": "主键ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "campaign_code": "活动编码",
            "campaign_name": "活动名称",
            "promotion_type": "促销类型(add_on/gift)",
            "campaign_status": "活动状态(draft/upcoming/ongoing/ended/disabled)",
            "start_at": "活动真实开始时间",
            "end_at": "活动真实结束时间",
            "addon_purchase_limit": "加价购每笔订单限购数量",
            "gift_min_spend": "满额赠最低消费门槛",
            "market": "市场",
            "currency": "币种",
            "rules_json": "活动规则JSON",
            "source_campaign_id": "来源活动ID(复制场景)",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_addon_campaign_main_items": {
            "id": "主键ID",
            "campaign_id": "加价购/满额赠活动ID",
            "run_id": "对局ID",
            "listing_id": "Shopee主商品ID",
            "variant_id": "Shopee主商品变体ID",
            "product_id": "源商品ID",
            "product_name_snapshot": "主商品名称快照",
            "variant_name_snapshot": "主商品规格名称快照",
            "sku_snapshot": "主商品SKU快照",
            "image_url_snapshot": "主商品图片快照",
            "original_price_snapshot": "主商品原价快照",
            "stock_snapshot": "主商品可售库存快照",
            "sort_order": "排序号",
            "created_at": "创建时间",
        },
        "shopee_addon_campaign_reward_items": {
            "id": "主键ID",
            "campaign_id": "加价购/满额赠活动ID",
            "run_id": "对局ID",
            "listing_id": "加购商品或赠品ID",
            "variant_id": "加购商品或赠品变体ID",
            "product_id": "源商品ID",
            "product_name_snapshot": "商品名称快照",
            "variant_name_snapshot": "商品规格名称快照",
            "sku_snapshot": "商品SKU快照",
            "image_url_snapshot": "商品图片快照",
            "original_price_snapshot": "商品原价快照",
            "addon_price": "加价购成交价",
            "reward_qty": "加购或赠送数量",
            "stock_snapshot": "商品可售库存快照",
            "sort_order": "排序号",
            "created_at": "创建时间",
        },
        "shopee_addon_drafts": {
            "id": "主键ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "promotion_type": "促销类型(add_on/gift)",
            "campaign_name": "草稿活动名称",
            "start_at": "草稿活动真实开始时间",
            "end_at": "草稿活动真实结束时间",
            "addon_purchase_limit": "草稿加价购限购数量",
            "gift_min_spend": "草稿满额赠最低消费门槛",
            "draft_status": "草稿状态(editing/abandoned/submitted)",
            "submitted_campaign_id": "提交后生成的正式活动ID",
            "source_campaign_id": "来源活动ID(复制场景)",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_addon_draft_main_items": {
            "id": "主键ID",
            "draft_id": "加价购/满额赠草稿ID",
            "run_id": "对局ID",
            "listing_id": "草稿主商品ID",
            "variant_id": "草稿主商品变体ID",
            "product_id": "源商品ID",
            "sort_order": "排序号",
            "created_at": "创建时间",
        },
        "shopee_addon_draft_reward_items": {
            "id": "主键ID",
            "draft_id": "加价购/满额赠草稿ID",
            "run_id": "对局ID",
            "listing_id": "草稿加购商品或赠品ID",
            "variant_id": "草稿加购商品或赠品变体ID",
            "product_id": "源商品ID",
            "addon_price": "草稿加价购成交价",
            "reward_qty": "草稿加购或赠送数量",
            "sort_order": "排序号",
            "created_at": "创建时间",
        },
        "shopee_flash_sale_campaigns": {
            "id": "活动ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "campaign_name": "限时抢购活动名称",
            "slot_date": "活动日期（游戏时间日期）",
            "slot_key": "时间段键",
            "start_tick": "活动开始游戏时间",
            "end_tick": "活动结束游戏时间",
            "status": "存储状态(active/disabled)",
            "total_product_limit": "该时间段商品上限",
            "reminder_count": "提醒设置数",
            "click_count": "商品点击数",
            "order_count": "活动订单数",
            "sales_amount": "活动销售额",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_flash_sale_campaign_items": {
            "id": "明细ID",
            "campaign_id": "限时抢购活动ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "listing_id": "Shopee商品ID",
            "variant_id": "Shopee变体ID",
            "product_id": "源商品ID",
            "product_name_snapshot": "商品名称快照",
            "variant_name_snapshot": "规格名称快照",
            "sku_snapshot": "SKU快照",
            "image_url_snapshot": "商品图片快照",
            "original_price": "创建时原价快照",
            "flash_price": "限时抢购成交价",
            "discount_percent": "折扣比例快照",
            "activity_stock_limit": "活动库存上限",
            "sold_qty": "已售数量",
            "purchase_limit_per_buyer": "每位买家限购数量",
            "status": "商品活动状态(active/disabled/sold_out)",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_flash_sale_traffic_events": {
            "id": "事件ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "campaign_id": "限时抢购活动ID",
            "campaign_item_id": "限时抢购活动商品ID",
            "listing_id": "Shopee商品ID",
            "variant_id": "Shopee变体ID，单规格商品可为空",
            "buyer_code": "买家画像编号",
            "event_type": "事件类型(view/click)",
            "event_tick": "事件发生游戏时间",
            "source": "事件来源(simulator)",
            "created_at": "创建时间",
        },
        "shopee_flash_sale_drafts": {
            "id": "草稿ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "campaign_name": "草稿活动名称",
            "slot_date": "草稿选择的活动日期",
            "slot_key": "草稿选择的时间段键",
            "payload_json": "前端表单快照JSON",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_flash_sale_draft_items": {
            "id": "草稿商品ID",
            "draft_id": "限时抢购草稿ID",
            "listing_id": "Shopee商品ID",
            "variant_id": "Shopee变体ID",
            "flash_price": "草稿限时抢购价",
            "activity_stock_limit": "草稿活动库存",
            "purchase_limit_per_buyer": "草稿限购数量",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_flash_sale_slots": {
            "id": "时间段配置ID",
            "market": "站点",
            "slot_key": "时间段键",
            "start_time": "每日开始时间",
            "end_time": "每日结束时间",
            "cross_day": "是否跨天",
            "product_limit": "该时间段商品总可用数量",
            "is_active": "是否启用",
            "sort_order": "排序号",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_flash_sale_category_rules": {
            "id": "条件配置ID",
            "market": "站点",
            "category_key": "类目键",
            "category_label": "类目显示名称",
            "min_activity_stock": "最小活动库存",
            "max_activity_stock": "最大活动库存",
            "min_discount_percent": "最小折扣百分比",
            "max_discount_percent": "最大折扣百分比",
            "min_rating": "最低商品评分",
            "min_likes": "最低点赞数",
            "min_30d_orders": "过去30天最低订单量",
            "max_ship_days": "最大发货天数",
            "allow_preorder": "是否允许预购商品",
            "repeat_control_days": "重复参加控制天数",
            "is_active": "是否启用",
            "sort_order": "排序号",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_shop_voucher_campaigns": {
            "id": "店铺代金券活动ID",
            "run_id": "所属对局ID",
            "user_id": "所属卖家用户ID",
            "voucher_type": "代金券类型，V1固定为shop_voucher",
            "voucher_name": "卖家可见的代金券名称",
            "voucher_code": "完整代金券代码，如HOME12345",
            "code_prefix": "代金券代码前缀",
            "code_suffix": "卖家输入的代码后缀",
            "status": "状态：upcoming/ongoing/sold_out/ended/stopped",
            "start_at": "代金券可使用开始游戏时间映射后的系统时间",
            "end_at": "代金券可使用结束游戏时间映射后的系统时间",
            "display_before_start": "是否提前展示代金券",
            "display_start_at": "提前展示开始游戏时间映射后的系统时间；未提前展示时为空",
            "reward_type": "奖励类型，V1固定为discount",
            "discount_type": "折扣类型：fixed_amount/percent",
            "discount_amount": "固定金额优惠，单位为店铺币种",
            "discount_percent": "百分比优惠，单位为百分比",
            "max_discount_type": "最大折扣金额类型：set_amount/no_limit",
            "max_discount_amount": "百分比优惠最高抵扣金额，单位为店铺币种；无限制时为空",
            "min_spend_amount": "最低消费金额，单位为店铺币种",
            "usage_limit": "所有买家可使用总代金券数量",
            "used_count": "已使用数量",
            "per_buyer_limit": "每位买家可使用次数上限",
            "display_type": "展示方式：all_pages/specific_channels/code_only",
            "display_channels": "特定渠道配置JSON，V1支持checkout_page",
            "applicable_scope": "适用商品范围，V1固定全店商品",
            "sales_amount": "代金券归因销售额，单位为店铺币种",
            "order_count": "代金券归因订单数",
            "buyer_count": "使用代金券买家数",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_product_voucher_campaigns": {
            "id": "商品代金券活动ID",
            "run_id": "所属对局ID",
            "user_id": "所属卖家用户ID",
            "voucher_type": "代金券类型，V1固定为product_voucher",
            "voucher_name": "卖家可见的代金券名称",
            "voucher_code": "完整代金券代码，如HOME12345",
            "code_prefix": "代金券代码前缀",
            "code_suffix": "卖家输入的代码后缀",
            "status": "状态：upcoming/ongoing/sold_out/ended/stopped",
            "start_at": "代金券可使用开始游戏时间映射后的系统时间",
            "end_at": "代金券可使用结束游戏时间映射后的系统时间",
            "display_before_start": "是否提前展示代金券",
            "display_start_at": "提前展示开始游戏时间映射后的系统时间；未提前展示时为空",
            "reward_type": "奖励类型，V1固定为discount",
            "discount_type": "折扣类型：fixed_amount/percent",
            "discount_amount": "固定金额优惠，单位为店铺币种",
            "discount_percent": "百分比优惠，单位为百分比",
            "max_discount_type": "最大折扣金额类型：set_amount/no_limit",
            "max_discount_amount": "百分比优惠最高抵扣金额，单位为店铺币种；无限制时为空",
            "min_spend_amount": "最低消费金额，单位为店铺币种",
            "usage_limit": "所有买家可使用总代金券数量",
            "used_count": "已使用数量",
            "per_buyer_limit": "每位买家可使用次数上限",
            "display_type": "展示方式：all_pages/specific_channels/code_only",
            "display_channels": "特定渠道配置JSON，V1支持checkout_page",
            "applicable_scope": "适用范围，商品代金券固定指定商品",
            "selected_product_count": "已选择适用商品数量",
            "sales_amount": "代金券归因销售额，单位为店铺币种",
            "order_count": "代金券归因订单数",
            "buyer_count": "使用代金券买家数",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_product_voucher_items": {
            "id": "商品代金券明细ID",
            "campaign_id": "所属商品代金券活动ID",
            "run_id": "所属对局ID",
            "user_id": "所属卖家用户ID",
            "listing_id": "商品listing ID",
            "variant_id": "商品变体ID；单规格商品为空",
            "product_id": "关联选品池商品ID",
            "product_name_snapshot": "创建时商品名称快照",
            "variant_name_snapshot": "创建时变体名称快照",
            "sku_snapshot": "创建时SKU快照",
            "image_url_snapshot": "创建时商品图片快照",
            "category_key_snapshot": "创建时商品分类key快照",
            "category_label_snapshot": "创建时商品分类标签快照",
            "original_price_snapshot": "创建时商品原价快照",
            "stock_snapshot": "创建时可用库存快照",
            "sort_order": "页面展示排序",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_private_voucher_campaigns": {
            "id": "专属代金券活动ID",
            "run_id": "所属对局ID",
            "user_id": "所属卖家用户ID",
            "voucher_type": "代金券类型，V1固定为private_voucher",
            "voucher_name": "卖家可见的代金券名称",
            "voucher_code": "完整代金券代码，如HOMEVIP01",
            "code_prefix": "代金券代码前缀",
            "code_suffix": "卖家输入的代码后缀",
            "status": "状态：upcoming/ongoing/sold_out/ended/stopped",
            "start_at": "代金券可使用开始游戏时间映射后的系统时间",
            "end_at": "代金券可使用结束游戏时间映射后的系统时间",
            "reward_type": "奖励类型，V1固定为discount",
            "discount_type": "折扣类型：fixed_amount/percent",
            "discount_amount": "固定金额优惠，单位为店铺币种",
            "discount_percent": "百分比优惠，单位为百分比",
            "max_discount_type": "最大折扣金额类型：set_amount/no_limit",
            "max_discount_amount": "百分比优惠最高抵扣金额，单位为店铺币种；无限制时为空",
            "min_spend_amount": "最低消费金额，单位为店铺币种",
            "usage_limit": "所有买家可使用总代金券数量",
            "used_count": "已使用数量",
            "per_buyer_limit": "每位买家可使用次数上限",
            "display_type": "展示方式，专属代金券V1固定代码分享",
            "applicable_scope": "适用商品范围：all_products/selected_products",
            "selected_product_count": "已选择适用商品数量",
            "audience_scope": "买家定向范围，V1固定私有码口径",
            "audience_payload": "买家定向配置JSON，V1预留为空",
            "sales_amount": "代金券归因销售额，单位为店铺币种",
            "order_count": "代金券归因订单数",
            "buyer_count": "使用代金券买家数",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_private_voucher_items": {
            "id": "专属代金券明细ID",
            "campaign_id": "所属专属代金券活动ID",
            "run_id": "所属对局ID",
            "user_id": "所属卖家用户ID",
            "listing_id": "商品listing ID",
            "variant_id": "商品变体ID；单规格商品为空",
            "product_id": "关联选品池商品ID",
            "product_name_snapshot": "创建时商品名称快照",
            "variant_name_snapshot": "创建时变体名称快照",
            "sku_snapshot": "创建时SKU快照",
            "image_url_snapshot": "创建时商品图片快照",
            "category_key_snapshot": "创建时商品分类key快照",
            "category_label_snapshot": "创建时商品分类标签快照",
            "original_price_snapshot": "创建时商品原价快照",
            "stock_snapshot": "创建时可用库存快照",
            "sort_order": "页面展示排序",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_live_voucher_campaigns": {
            "id": "直播代金券活动ID",
            "run_id": "所属对局ID",
            "user_id": "所属卖家用户ID",
            "voucher_type": "代金券类型，V1固定为live_voucher",
            "voucher_name": "卖家可见的代金券名称",
            "voucher_code": "完整代金券代码，如HOMELIVE1",
            "code_prefix": "代金券代码前缀",
            "code_suffix": "卖家输入的代码后缀",
            "status": "状态：upcoming/ongoing/sold_out/ended/stopped",
            "start_at": "代金券可使用开始游戏时间映射后的系统时间",
            "end_at": "代金券可使用结束游戏时间映射后的系统时间",
            "display_before_start": "是否提前展示代金券",
            "display_start_at": "提前展示开始游戏时间映射后的系统时间；未提前展示时为空",
            "reward_type": "奖励类型，V1固定为discount",
            "discount_type": "折扣类型：fixed_amount/percent",
            "discount_amount": "固定金额优惠，单位为店铺币种",
            "discount_percent": "百分比优惠，单位为百分比",
            "max_discount_type": "最大折扣金额类型：set_amount/no_limit",
            "max_discount_amount": "百分比优惠最高抵扣金额，单位为店铺币种；无限制时为空",
            "min_spend_amount": "最低消费金额，单位为店铺币种",
            "usage_limit": "所有买家可使用总代金券数量",
            "used_count": "已使用数量",
            "per_buyer_limit": "每位买家可使用次数上限",
            "display_type": "展示方式，直播代金券V1固定直播间展示",
            "display_channels": "展示渠道配置JSON，V1固定shopee_live",
            "applicable_scope": "适用商品范围：all_products/selected_products",
            "selected_product_count": "已选择适用商品数量",
            "live_scope": "直播适用范围，V1固定全部直播场次",
            "live_payload": "直播场次绑定配置JSON，V1预留为空",
            "sales_amount": "代金券归因销售额，单位为店铺币种",
            "order_count": "代金券归因订单数",
            "buyer_count": "使用代金券买家数",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_live_voucher_items": {
            "id": "直播代金券明细ID",
            "campaign_id": "所属直播代金券活动ID",
            "run_id": "所属对局ID",
            "user_id": "所属卖家用户ID",
            "listing_id": "商品listing ID",
            "variant_id": "商品变体ID；单规格商品为空",
            "product_id": "关联选品池商品ID",
            "product_name_snapshot": "创建时商品名称快照",
            "variant_name_snapshot": "创建时变体名称快照",
            "sku_snapshot": "创建时SKU快照",
            "image_url_snapshot": "创建时商品图片快照",
            "category_key_snapshot": "创建时商品分类key快照",
            "category_label_snapshot": "创建时商品分类标签快照",
            "original_price_snapshot": "创建时商品原价快照",
            "stock_snapshot": "创建时可用库存快照",
            "sort_order": "页面展示排序",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_video_voucher_campaigns": {
            "id": "视频代金券活动ID",
            "run_id": "所属对局ID",
            "user_id": "所属卖家用户ID",
            "voucher_type": "代金券类型，V1固定为video_voucher",
            "voucher_name": "卖家可见的代金券名称",
            "voucher_code": "后端生成的视频代金券内部唯一编号",
            "status": "状态：upcoming/ongoing/sold_out/ended/stopped",
            "start_at": "代金券可使用开始游戏时间映射后的系统时间",
            "end_at": "代金券可使用结束游戏时间映射后的系统时间",
            "display_before_start": "是否提前展示代金券",
            "display_start_at": "提前展示开始游戏时间映射后的系统时间；未提前展示时为空",
            "reward_type": "奖励类型，V1固定为discount",
            "discount_type": "折扣类型：fixed_amount/percent",
            "discount_amount": "固定金额优惠，单位为店铺币种",
            "discount_percent": "百分比优惠，单位为百分比",
            "max_discount_type": "最大折扣金额类型：set_amount/no_limit",
            "max_discount_amount": "百分比优惠最高抵扣金额，单位为店铺币种；无限制时为空",
            "min_spend_amount": "最低消费金额，单位为店铺币种",
            "usage_limit": "所有买家可使用总代金券数量",
            "used_count": "已使用数量",
            "per_buyer_limit": "每位买家可使用次数上限",
            "display_type": "展示方式，视频代金券V1固定Shopee视频展示",
            "display_channels": "展示渠道配置JSON，V1固定shopee_video",
            "applicable_scope": "适用商品范围：all_products/selected_products",
            "selected_product_count": "已选择适用商品数量",
            "video_scope": "视频适用范围，V1固定全部视频场景",
            "video_payload": "视频内容绑定配置JSON，V1预留为空",
            "sales_amount": "代金券归因销售额，单位为店铺币种",
            "order_count": "代金券归因订单数",
            "buyer_count": "使用代金券买家数",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_video_voucher_items": {
            "id": "视频代金券明细ID",
            "campaign_id": "所属视频代金券活动ID",
            "run_id": "所属对局ID",
            "user_id": "所属卖家用户ID",
            "listing_id": "商品listing ID",
            "variant_id": "商品变体ID；单规格商品为空",
            "product_id": "关联选品池商品ID",
            "product_name_snapshot": "创建时商品名称快照",
            "variant_name_snapshot": "创建时变体名称快照",
            "sku_snapshot": "创建时SKU快照",
            "image_url_snapshot": "创建时商品图片快照",
            "category_key_snapshot": "创建时商品分类key快照",
            "category_label_snapshot": "创建时商品分类标签快照",
            "original_price_snapshot": "创建时商品原价快照",
            "stock_snapshot": "创建时可用库存快照",
            "sort_order": "页面展示排序",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_follow_voucher_campaigns": {
            "id": "关注礼代金券活动ID",
            "run_id": "所属对局ID",
            "user_id": "所属卖家用户ID",
            "voucher_type": "代金券类型，V1固定为follow_voucher",
            "voucher_name": "卖家可见的代金券名称",
            "voucher_code": "后端生成的关注礼内部唯一编号",
            "status": "状态：upcoming/ongoing/sold_out/ended/stopped",
            "claim_start_at": "关注礼可领取开始游戏时间映射后的系统时间",
            "claim_end_at": "关注礼可领取结束游戏时间映射后的系统时间",
            "valid_days_after_claim": "买家领取后有效游戏天数，V1固定7",
            "reward_type": "奖励类型，V1固定为discount",
            "discount_type": "折扣类型：fixed_amount/percent",
            "discount_amount": "固定金额优惠，单位为店铺币种",
            "discount_percent": "百分比优惠，单位为百分比",
            "max_discount_type": "最大折扣金额类型：set_amount/no_limit",
            "max_discount_amount": "百分比优惠最高抵扣金额，单位为店铺币种；无限制时为空",
            "min_spend_amount": "最低消费金额，单位为店铺币种",
            "usage_limit": "最大可领取并使用代金券数量",
            "claimed_count": "已发放/已领取数量",
            "used_count": "已使用数量",
            "per_buyer_limit": "每位买家可使用次数上限",
            "trigger_type": "触发类型，V1固定关注店铺",
            "display_type": "展示/发放方式，关注礼V1固定关注奖励",
            "display_channels": "展示渠道配置JSON，V1固定follow_prize",
            "applicable_scope": "适用范围，V1固定全部商品",
            "sales_amount": "代金券归因销售额，单位为店铺币种",
            "order_count": "代金券归因订单数",
            "buyer_count": "使用代金券买家数",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_buyer_follow_states": {
            "id": "主键ID",
            "run_id": "所属对局ID",
            "user_id": "所属卖家用户ID",
            "buyer_name": "模拟买家标识",
            "is_following": "当前是否关注店铺",
            "first_followed_at": "首次关注时间，对应订单模拟游戏tick",
            "follow_source": "首次关注来源，关注礼场景为follow_voucher",
            "source_campaign_id": "促成首次关注的关注礼活动ID",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_auto_reply_settings": {
            "id": "自动回复配置ID",
            "run_id": "所属对局ID",
            "user_id": "所属卖家用户ID",
            "reply_type": "自动回复类型：default/off_work",
            "enabled": "是否启用该自动回复",
            "message": "自动回复消息内容",
            "work_time_enabled": "是否启用工作时间判断",
            "work_start_time": "工作开始时间，格式HH:mm",
            "work_end_time": "工作结束时间，格式HH:mm",
            "timezone": "时间解释口径，V1固定对局游戏时间",
            "trigger_interval_minutes": "同买家触发间隔分钟数",
            "trigger_once_per_game_day": "是否按游戏日限制每天一次",
            "sent_count": "已触发发送次数",
            "last_sent_game_at": "最近一次触发的游戏时间",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_quick_reply_preferences": {
            "id": "快捷回复偏好ID",
            "run_id": "所属对局ID",
            "user_id": "所属卖家用户ID",
            "auto_hint_enabled": "是否开启输入时自动显示快捷回复提示",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_quick_reply_groups": {
            "id": "快捷回复分组ID",
            "run_id": "所属对局ID",
            "user_id": "所属卖家用户ID",
            "group_name": "快捷回复分组名称",
            "enabled": "分组是否启用",
            "sort_order": "分组排序值",
            "message_count": "分组内消息数量冗余计数",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_quick_reply_messages": {
            "id": "快捷回复消息ID",
            "group_id": "所属快捷回复分组ID",
            "run_id": "所属对局ID",
            "user_id": "所属卖家用户ID",
            "message": "快捷回复消息内容",
            "tags_json": "标签JSON数组，最多3个",
            "sort_order": "消息排序值",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_shipping_fee_promotion_campaigns": {
            "id": "运费促销活动ID",
            "run_id": "所属对局ID",
            "user_id": "所属卖家用户ID",
            "promotion_name": "运费促销名称，仅卖家可见",
            "status": "状态：upcoming/ongoing/ended/budget_exhausted/stopped",
            "period_type": "期限类型：no_limit/selected",
            "start_at": "活动开始游戏时间映射后的系统时间",
            "end_at": "活动结束游戏时间映射后的系统时间；无期限为空",
            "budget_type": "预算类型：no_limit/selected",
            "budget_limit": "预算上限，单位RM；无预算限制为空",
            "budget_used": "已使用预算，单位RM",
            "order_count": "归因订单数",
            "buyer_count": "归因买家数",
            "sales_amount": "归因销售额，单位RM",
            "shipping_discount_amount": "已产生运费优惠总额，单位RM",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_shipping_fee_promotion_channels": {
            "id": "主键ID",
            "campaign_id": "所属运费促销活动ID",
            "run_id": "所属对局ID",
            "user_id": "所属卖家用户ID",
            "channel_key": "物流渠道key：standard/bulky",
            "channel_label": "物流渠道展示名",
            "created_at": "创建时间",
        },
        "shopee_shipping_fee_promotion_tiers": {
            "id": "主键ID",
            "campaign_id": "所属运费促销活动ID",
            "run_id": "所属对局ID",
            "user_id": "所属卖家用户ID",
            "tier_index": "层级序号，从1开始",
            "min_spend_amount": "最低消费金额，单位RM",
            "fee_type": "运费类型：fixed_fee/free_shipping",
            "fixed_fee_amount": "固定运费金额，单位RM；免运费时为空",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
        "shopee_order_generation_logs": {
            "id": "主键ID",
            "run_id": "对局ID",
            "user_id": "用户ID",
            "tick_time": "模拟时刻",
            "active_buyer_count": "活跃买家数",
            "candidate_product_count": "候选商品数",
            "generated_order_count": "生成订单数",
            "skip_reasons_json": "跳过原因统计JSON",
            "debug_payload_json": "调试信息JSON",
            "created_at": "创建时间",
        },
        "warehouse_landmarks": {
            "id": "主键ID",
            "market": "市场",
            "warehouse_mode": "仓储模式",
            "warehouse_location": "仓库位置",
            "point_code": "点位编码",
            "point_name": "点位名称",
            "lng": "经度",
            "lat": "纬度",
            "sort_order": "排序号",
            "is_active": "是否启用",
            "created_at": "创建时间",
        },
        "sim_buyer_profiles": {
            "id": "主键ID",
            "buyer_code": "买家编码",
            "nickname": "买家昵称",
            "gender": "性别",
            "age": "年龄",
            "city": "城市",
            "city_code": "城市编码",
            "lat": "纬度",
            "lng": "经度",
            "occupation": "职业",
            "background": "人物背景",
            "preferred_categories_json": "偏好类目JSON",
            "active_hours_json": "24小时活跃概率JSON",
            "weekday_factors_json": "周内活跃修正JSON",
            "base_buy_intent": "基础购买意愿",
            "price_sensitivity": "价格敏感度",
            "quality_sensitivity": "质量敏感度",
            "brand_sensitivity": "品牌敏感度",
            "impulse_level": "冲动购买倾向",
            "purchase_power": "购买力水平",
            "is_active": "是否启用",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        },
    }

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table_name, comments in column_comments.items():
            if table_name not in existing_tables:
                continue
            rows = conn.execute(text(f"SHOW FULL COLUMNS FROM `{table_name}`")).mappings().all()
            for row in rows:
                column_name = row["Field"]
                comment = comments.get(column_name)
                if not comment:
                    continue
                if (row.get("Comment") or "") == comment:
                    continue
                col_type = row["Type"]
                nullable_sql = "NULL" if row["Null"] == "YES" else "NOT NULL"
                default_val = row["Default"]
                extra_raw = (row.get("Extra") or "").strip()
                extra_sql_parts: list[str] = []
                extra_lower = extra_raw.lower()
                if "auto_increment" in extra_lower:
                    extra_sql_parts.append("AUTO_INCREMENT")
                if "on update" in extra_lower:
                    normalized_extra = " ".join(extra_raw.split())
                    start = normalized_extra.lower().find("on update")
                    if start >= 0:
                        extra_sql_parts.append(normalized_extra[start:])
                extra_sql = f" {' '.join(extra_sql_parts)}" if extra_sql_parts else ""
                if default_val is None:
                    default_sql = ""
                else:
                    default_text = str(default_val)
                    upper = default_text.upper()
                    lower = default_text.lower()
                    if lower in {"now()", "current_timestamp()", "current_timestamp"} or lower.startswith("current_timestamp"):
                        default_sql = f" DEFAULT {default_text}"
                    elif upper == "NULL":
                        default_sql = " DEFAULT NULL"
                    else:
                        escaped_default = default_text.replace("\\", "\\\\").replace("'", "''")
                        default_sql = f" DEFAULT '{escaped_default}'"
                escaped_comment = comment.replace("\\", "\\\\").replace("'", "''")
                conn.execute(
                    text(
                        f"ALTER TABLE `{table_name}` MODIFY COLUMN `{column_name}` "
                        f"{col_type} {nullable_sql}{default_sql}{extra_sql} COMMENT '{escaped_comment}'"
                    )
                )

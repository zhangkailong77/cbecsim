# 32-Shopee 我的店铺限时抢购前后端数据库 Redis 打通设计

> 创建日期：2026-04-29  
> 状态：设计完成，待实现

## 1. 目标

打通 Shopee `营销中心 -> 我的店铺限时抢购 -> 创建` 链路的前端、后端、数据库与 Redis，使卖家可以在当前对局中选择官方限时抢购时间段、查看商品准入条件、添加商品并创建店铺限时抢购活动。

本设计以当前前端页面 `/shopee/marketing/flash-sale/create` 为入口，优先完成数据闭环：

- 创建页初始化数据来自后端。
- 时间段、类目条件、商品候选、已选商品、草稿与正式活动落库。
- 列表页读取真实活动数据。
- Redis 缓存创建页、商品候选、活动列表与活动详情。
- 创建正式活动后，为后续订单模拟和活动数据统计预留营销归因字段与缓存失效口径。

## 2. 范围与非范围

### 2.1 本期范围（V1）

- 新增限时抢购创建页后端接口：
  - bootstrap 初始化。
  - 可选时间段列表。
  - 商品准入条件配置。
  - 商品候选列表。
  - 草稿保存与回填。
  - 正式活动创建。
- 新增限时抢购列表页后端接口：
  - 活动列表。
  - 活动状态与基础指标。
- 新增数据库表：
  - 限时抢购活动主表。
  - 限时抢购商品表。
  - 限时抢购草稿主表。
  - 限时抢购草稿商品表。
  - 限时抢购时间段配置表。
  - 限时抢购类目商品条件配置表。
- Redis 支持：
  - 创建页 bootstrap 缓存。
  - 时间段缓存。
  - 商品条件缓存。
  - 商品候选缓存。
  - 草稿缓存。
  - 活动列表/详情缓存。
  - 创建、编辑、停用后失效相关缓存。
- 前端接入：
  - `/shopee/marketing/flash-sale/create` 调用真实接口。
  - 时间段弹窗读取后端时间段。
  - 商品条件按类目从后端读取。
  - 添加商品弹窗读取候选商品。
  - 确认创建调用正式活动接口。
  - `/shopee/marketing/flash-sale` 列表页读取真实活动列表。

### 2.2 非范围（V1 不做）

- 不实现买家端真实限时抢购页面。
- 不实现 Shopee 平台级大促提报，仅实现店铺内限时抢购。
- 不实现复杂编辑流程；V1 可支持创建与详情，编辑可后续单独接入。
- 不实现复制活动。
- 不实现 CSV/Excel 批量导入商品。
- 不在本设计内完整接入订单模拟概率；仅预留营销归因与后续模拟入口。
- 不改变现有单品折扣、套餐优惠、加价购/满额赠活动逻辑。

## 3. 页面流程

### 3.1 创建页流程

1. 用户进入 `/shopee/marketing/flash-sale/create`。
2. 前端调用 bootstrap 接口，加载：
   - 当前游戏时间。
   - 默认可选日期。
   - 时间段列表。
   - 类目 Tab。
   - 各类目商品准入条件。
   - 规则限制。
   - 草稿回填数据（如有）。
3. 用户点击“选择时间段”。
4. 前端打开时间段弹窗：
   - 左侧选择活动日期。
   - 右侧展示可选时间段。
   - 已满额或不可用时间段禁用。
5. 用户选择时间段后，主页面展示已选时间段。
6. 用户查看商品条件，并点击“添加商品”。
7. 前端调用商品候选接口，展示符合当前时间段与类目条件的商品。
8. 用户选择商品并设置：
   - 活动库存。
   - 限时抢购价格或折扣。
   - 每人限购数量。
9. 用户点击“确认”。
10. 后端校验并创建正式活动。
11. 创建成功后跳转回 `/shopee/marketing/flash-sale` 列表页，并刷新活动列表。

### 3.2 列表页流程

1. 用户进入 `/shopee/marketing/flash-sale`。
2. 前端调用活动列表接口，按状态 Tab 加载数据。
3. 列表展示：
   - 时间段。
   - 商品可用数量。
   - 提醒设置数。
   - 商品点击数。
   - 状态。
   - 启用/停用。
   - 详情/复制/数据等预留操作。
4. 列表指标区域读取活动表现接口或列表 bootstrap 聚合数据。

## 4. 业务规则

### 4.1 活动时间段规则

- 时间段按游戏时间口径生成，不按真实时间口径展示。
- V1 可按每日固定时段生成：
  - `00:00:00 - 12:00:00`
  - `12:00:00 - 18:00:00`
  - `18:00:00 - 21:00:00`
  - `21:00:00 - 00:00:00 +1`
- 仅允许选择当前游戏时间之后的时间段。
- 一个限时抢购活动只能绑定一个时间段。
- 同一时间段最多允许 `50` 个活动商品，作为官方页面“总可用 50”的模拟口径。
- 已结束时间段不可创建。
- 历史回溯只读模式不可创建、保存、停用。

### 4.2 商品准入规则

商品必须满足：

- 属于当前 `run_id` 与当前用户。
- Shopee listing 状态为上架中。
- 有可售库存。
- 原价大于 0。
- 未处于违规/审核失败状态。
- 当前选择时间段内未参加另一个限时抢购活动。
- 活动库存范围：`5 ~ 10000`，且不得超过当前可售库存。
- 折扣限制：`5% ~ 99%`。
- 商品评分、点赞数、过去 30 天订单量、发货天数、预购商品、重复控制等条件先按配置表返回，V1 可只展示并做基础过滤，后续可逐步强化。

### 4.3 价格与库存规则

- `flash_price` 必须大于 0 且小于原价。
- 折扣比例根据 `original_price` 与 `flash_price` 自动计算。
- `activity_stock_limit` 必须在 `5 ~ 10000` 范围内，并小于等于可售库存。
- `purchase_limit_per_buyer` 默认为 1，可配置范围 `1 ~ 99`。
- 活动创建后不立即扣减仓库库存，只在订单模拟真实成交时扣减。
- 活动库存用于限制该活动可售件数；订单模拟命中后需要累计 `sold_qty`。

### 4.4 活动状态规则

活动状态由当前游戏时间和字段共同计算：

| 状态 | 条件 |
| --- | --- |
| `draft` | 草稿，未正式创建 |
| `upcoming` | 已创建，当前游戏时间早于 `start_tick` |
| `ongoing` | 当前游戏时间在 `start_tick <= now < end_tick` |
| `ended` | 当前游戏时间大于等于 `end_tick` |
| `disabled` | 卖家手动停用 |

### 4.5 营销叠加规则（V1 预留）

- 限时抢购与单品折扣同时覆盖同一 SKU 时，订单模拟后续应优先采用更低成交价，且营销归因优先标记为 `flash_sale`。
- 限时抢购与套餐优惠、加价购/满额赠的叠加优先级后续在订单模拟设计中单独确认。
- 本期创建数据时只做同类限时抢购活动时间冲突校验，不阻止商品参加其他营销活动。

## 5. 数据模型设计

> 数据库表与字段必须添加 table comment / column comment；若通过初始化脚本或迁移脚本创建，也必须同步维护注释。

### 5.1 `shopee_flash_sale_campaigns`

限时抢购活动主表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint pk | 活动 ID |
| `run_id` | bigint | 对局 ID |
| `user_id` | bigint | 用户 ID |
| `campaign_name` | varchar(100) | 活动名称，仅卖家可见 |
| `slot_date` | date | 活动日期，游戏时间日期 |
| `slot_key` | varchar(32) | 时间段 key，例如 `12_18` |
| `start_tick` | datetime | 活动开始游戏时间 |
| `end_tick` | datetime | 活动结束游戏时间 |
| `status` | varchar(32) | 存储状态：`active/disabled`，展示状态动态计算 |
| `total_product_limit` | int | 该时间段可加入商品上限，默认 50 |
| `reminder_count` | int | 提醒设置数，V1 默认 0 |
| `click_count` | int | 商品点击数，V1 默认 0 |
| `order_count` | int | 活动订单数，订单模拟接入后回填 |
| `sales_amount` | decimal(12,2) | 活动销售额，订单模拟接入后回填 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

索引：

- `idx_flash_sale_campaign_run_user`：`run_id, user_id`
- `idx_flash_sale_campaign_slot`：`run_id, user_id, slot_date, slot_key`
- `idx_flash_sale_campaign_time`：`run_id, start_tick, end_tick`
- `idx_flash_sale_campaign_status`：`run_id, status`

### 5.2 `shopee_flash_sale_campaign_items`

限时抢购活动商品表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint pk | 明细 ID |
| `campaign_id` | bigint | 限时抢购活动 ID |
| `run_id` | bigint | 对局 ID，冗余便于查询 |
| `user_id` | bigint | 用户 ID，冗余便于查询 |
| `listing_id` | bigint | Shopee listing ID |
| `variant_id` | bigint null | 规格 ID，单规格为空 |
| `product_id` | bigint null | 商品 ID |
| `original_price` | decimal(12,2) | 创建时原价快照 |
| `flash_price` | decimal(12,2) | 限时抢购成交价 |
| `discount_percent` | decimal(5,2) | 折扣比例快照 |
| `activity_stock_limit` | int | 活动库存上限 |
| `sold_qty` | int | 已售数量 |
| `purchase_limit_per_buyer` | int | 每位买家限购数量 |
| `status` | varchar(32) | 商品活动状态：`active/disabled/sold_out` |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

索引：

- `idx_flash_sale_item_campaign`：`campaign_id`
- `idx_flash_sale_item_sku`：`run_id, listing_id, variant_id`
- `idx_flash_sale_item_user`：`run_id, user_id`

### 5.3 `shopee_flash_sale_drafts`

限时抢购草稿主表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint pk | 草稿 ID |
| `run_id` | bigint | 对局 ID |
| `user_id` | bigint | 用户 ID |
| `campaign_name` | varchar(100) | 草稿活动名称 |
| `slot_date` | date null | 草稿选择的活动日期 |
| `slot_key` | varchar(32) null | 草稿选择的时间段 key |
| `payload_json` | json | 前端表单快照，便于兼容后续字段 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

### 5.4 `shopee_flash_sale_draft_items`

限时抢购草稿商品表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint pk | 草稿商品 ID |
| `draft_id` | bigint | 草稿 ID |
| `listing_id` | bigint | Shopee listing ID |
| `variant_id` | bigint null | 规格 ID |
| `flash_price` | decimal(12,2) null | 草稿限时抢购价 |
| `activity_stock_limit` | int null | 草稿活动库存 |
| `purchase_limit_per_buyer` | int null | 草稿限购数量 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

### 5.5 `shopee_flash_sale_slots`

限时抢购时间段配置表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint pk | 时间段配置 ID |
| `market` | varchar(16) | 站点，例如 `MY` |
| `slot_key` | varchar(32) | 时间段 key |
| `start_time` | time | 每日开始时间 |
| `end_time` | time | 每日结束时间 |
| `cross_day` | boolean | 是否跨天 |
| `product_limit` | int | 该时间段商品总可用数量 |
| `is_active` | boolean | 是否启用 |
| `sort_order` | int | 排序 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

### 5.6 `shopee_flash_sale_category_rules`

限时抢购类目商品条件配置表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint pk | 条件配置 ID |
| `market` | varchar(16) | 站点，例如 `MY` |
| `category_key` | varchar(64) | 类目 key |
| `category_label` | varchar(100) | 类目显示名称 |
| `min_activity_stock` | int | 最小活动库存 |
| `max_activity_stock` | int | 最大活动库存 |
| `min_discount_percent` | decimal(5,2) | 最小折扣百分比 |
| `max_discount_percent` | decimal(5,2) | 最大折扣百分比 |
| `min_rating` | decimal(3,2) null | 最低商品评分，空表示无限制 |
| `min_likes` | int null | 最低点赞数，空表示无限制 |
| `min_30d_orders` | int null | 过去 30 天最低订单量，空表示无限制 |
| `max_ship_days` | int null | 最大发货天数，空表示无限制 |
| `allow_preorder` | boolean | 是否允许预购商品 |
| `repeat_control_days` | int null | 重复参加控制天数，空表示无限制 |
| `is_active` | boolean | 是否启用 |
| `sort_order` | int | 排序 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

## 6. 后端接口设计（FastAPI）

统一延续现有风格：`/shopee/runs/{run_id}/...`

### 6.1 创建页 bootstrap

`GET /shopee/runs/{run_id}/marketing/flash-sale/create/bootstrap`

参数：

- `draft_id` 可选，用于草稿回填。
- `source_campaign_id` 可选，后续复制活动预留。

返回示例：

```json
{
  "meta": {
    "run_id": 6,
    "user_id": 3,
    "market": "MY",
    "read_only": false,
    "current_tick": "2026-04-29T10:00:00"
  },
  "form": {
    "campaign_name": "",
    "name_max_length": 60,
    "selected_slot": null
  },
  "rules": {
    "product_limit_per_slot": 50,
    "activity_stock_range": [5, 10000],
    "discount_percent_range": [5, 99],
    "purchase_limit_range": [1, 99]
  },
  "categories": [
    {"key": "baby", "label": "母婴"},
    {"key": "tools_home", "label": "工具与家装"},
    {"key": "all", "label": "全部"}
  ],
  "category_rules": {
    "baby": [
      {"label": "活动库存", "value": "5 ~ 10000"},
      {"label": "折扣限制", "value": "5% ~ 99%"}
    ]
  },
  "selected_products": []
}
```

### 6.2 时间段列表

`GET /shopee/runs/{run_id}/marketing/flash-sale/slots`

参数：

- `date`：游戏日期，格式 `YYYY-MM-DD`。

返回字段：

- `slot_key`
- `display_time`
- `start_tick`
- `end_tick`
- `cross_day`
- `product_limit`
- `used_product_count`
- `available_product_count`
- `selectable`
- `disabled_reason`

### 6.3 商品条件

`GET /shopee/runs/{run_id}/marketing/flash-sale/category-rules`

参数：

- `category_key` 可选，不传返回全部。

返回：

- 类目列表。
- 每个类目的商品条件展示项。
- 后端可执行校验字段。

### 6.4 商品候选列表

`GET /shopee/runs/{run_id}/marketing/flash-sale/eligible-products`

参数：

- `slot_date`
- `slot_key`
- `category_key`
- `keyword`
- `search_field=product_name|product_id|sku`
- `page`
- `page_size`

返回字段：

- `listing_id`
- `variant_id`
- `product_id`
- `product_name`
- `variant_name`
- `sku`
- `image_url`
- `category_key`
- `category_label`
- `original_price`
- `stock_available`
- `rating`
- `likes_count`
- `orders_30d`
- `ship_days`
- `is_preorder`
- `conflict`
- `conflict_reason`
- `suggested_flash_price`

### 6.5 草稿保存

`POST /shopee/runs/{run_id}/marketing/flash-sale/drafts`

入参示例：

```json
{
  "draft_id": null,
  "campaign_name": "店铺限时抢购活动",
  "slot_date": "2026-04-29",
  "slot_key": "12_18",
  "items": [
    {
      "listing_id": 101,
      "variant_id": 1001,
      "flash_price": 19.9,
      "activity_stock_limit": 20,
      "purchase_limit_per_buyer": 1
    }
  ]
}
```

返回：

- `draft_id`
- `saved_at`

### 6.6 草稿详情

`GET /shopee/runs/{run_id}/marketing/flash-sale/drafts/{draft_id}`

用途：回填创建页。

### 6.7 创建正式活动

`POST /shopee/runs/{run_id}/marketing/flash-sale/campaigns`

后端职责：

1. 校验当前对局归属与只读状态。
2. 校验时间段存在且可选。
3. 校验商品数量不超过时间段剩余可用数量。
4. 校验每个 SKU 准入条件、价格、库存与限购数量。
5. 校验同一 SKU 在所选时间段内未参加其他限时抢购活动。
6. 写入活动主表与活动商品表。
7. 清理草稿（如由草稿创建）。
8. 失效相关 Redis 缓存。
9. 返回活动 ID 与跳转目标。

返回示例：

```json
{
  "campaign_id": 12,
  "status": "upcoming",
  "redirect_url": "/shopee/marketing/flash-sale"
}
```

### 6.8 活动列表

`GET /shopee/runs/{run_id}/marketing/flash-sale/campaigns`

参数：

- `status=all|upcoming|ongoing|ended|disabled`
- `date_from`
- `date_to`
- `page`
- `page_size`

返回字段：

- `id`
- `slot_date`
- `display_time`
- `product_enabled_count`
- `product_limit`
- `reminder_count`
- `click_count`
- `status`
- `status_label`
- `enabled`
- `actions`

### 6.9 活动详情

`GET /shopee/runs/{run_id}/marketing/flash-sale/campaigns/{campaign_id}`

返回活动基础信息、商品明细与统计快照。

### 6.10 启用/停用

`POST /shopee/runs/{run_id}/marketing/flash-sale/campaigns/{campaign_id}/toggle`

入参：

```json
{"enabled": false}
```

## 7. Redis 缓存设计

### 7.1 Key 设计

| Key | TTL | 说明 |
| --- | --- | --- |
| `shopee:flash_sale:create_bootstrap:{run_id}:{user_id}` | 5 分钟 | 创建页初始化 |
| `shopee:flash_sale:slots:{run_id}:{date}` | 5 分钟 | 某日期可选时间段 |
| `shopee:flash_sale:category_rules:{market}` | 30 分钟 | 类目商品条件配置 |
| `shopee:flash_sale:eligible:{run_id}:{user_id}:{hash}` | 2 分钟 | 商品候选列表 |
| `shopee:flash_sale:draft:{run_id}:{user_id}:{draft_id}` | 30 分钟 | 草稿详情缓存 |
| `shopee:flash_sale:list:{run_id}:{user_id}:{hash}` | 2 分钟 | 活动列表 |
| `shopee:flash_sale:detail:{run_id}:{campaign_id}` | 2 分钟 | 活动详情 |
| `shopee:flash_sale:active_map:{run_id}` | 1 分钟 | 订单模拟后续读取的有效活动映射 |

### 7.2 失效策略

以下操作必须失效缓存：

- 创建正式活动：
  - `create_bootstrap`
  - `slots`
  - `eligible`
  - `list`
  - `detail`
  - `active_map`
- 保存草稿：
  - 对应 `draft`
- 停用活动：
  - `list`
  - `detail`
  - `active_map`
- 订单模拟生成限时抢购订单后：
  - `list`
  - `detail`
  - 后续数据页缓存（如实现）

## 8. 前端接入设计

### 8.1 创建页 `/shopee/marketing/flash-sale/create`

当前页面已经具备：

- 时间段选择弹窗。
- 类目 Tab 与商品条件展示。
- 限时抢购商品区。
- 底部取消/确认按钮。

接入后端后：

- 页面加载调用 `create/bootstrap`。
- 时间段弹窗按日期调用 `slots`。
- 类目和商品条件来自 `category-rules` 或 bootstrap。
- 点击“添加商品”打开商品选择弹窗并调用 `eligible-products`。
- 确认按钮调用 `campaigns` 创建正式活动。
- 取消按钮返回 `/shopee/marketing/flash-sale`。

### 8.2 列表页 `/shopee/marketing/flash-sale`

- 页面加载调用 `campaigns`。
- Tab 切换传 `status`。
- 时间段筛选传 `date_from/date_to`。
- 创建成功返回后刷新列表。
- 启用/停用调用 `toggle`。

## 9. 订单模拟预留口径

后续订单模拟接入时：

- 当前游戏时间命中 `start_tick <= now < end_tick` 的活动才有效。
- 买家自然选择到活动 SKU 时，使用 `flash_price` 作为成交价候选。
- 活动库存 `sold_qty < activity_stock_limit` 才可成交。
- 买家维度限购需检查该买家在当前活动下已购买数量。
- 订单头或订单明细营销归因建议：
  - `marketing_campaign_type = "flash_sale"`
  - `marketing_campaign_id = campaign_id`
  - item 级记录 `original_unit_price` 与 `final_unit_price`。
- 订单生成后增加活动商品 `sold_qty`，并失效活动列表、详情与后续数据页缓存。

## 10. 验收标准

1. `/shopee/marketing/flash-sale/create` 打开后能从后端加载创建页 bootstrap。
2. 时间段弹窗能按游戏日期展示可选时间段，并正确禁用不可选时间段。
3. 商品条件按类目展示，且配置来自后端或数据库初始化数据。
4. 添加商品弹窗只展示符合当前用户、当前对局、当前时间段准入条件的商品。
5. 创建正式活动后写入活动主表和活动商品表。
6. 活动列表页能读取并展示真实限时抢购活动。
7. 同一 SKU 在同一时间段重复参加限时抢购时，后端拦截并返回明确错误。
8. Redis 命中时页面加载正常；创建、停用、保存草稿后相关缓存正确失效。
9. 历史回溯只读模式下禁止创建、保存、停用。
10. 数据库新增表和字段均有 table comment / column comment，并同步维护初始化脚本与 SQL 快照。
11. 不影响现有单品折扣、套餐优惠、加价购/满额赠页面与接口。

## 11. 实施顺序建议

1. 数据库模型与初始化脚本：新增表、字段注释、索引和默认时间段/类目条件配置。
2. 后端 schema 与基础查询工具：活动状态解析、时间段生成、商品准入校验。
3. 创建页接口：bootstrap、slots、category-rules、eligible-products、drafts、campaigns。
4. 列表页接口：campaigns list、detail、toggle。
5. Redis 缓存与失效前缀接入。
6. 前端创建页接入真实接口。
7. 前端列表页接入真实活动数据。
8. 验证创建、列表、冲突校验、缓存失效和只读模式。

## 12. 待确认事项

1. 时间段是否固定为每日 4 档，还是后续需要按站点/活动日动态配置。
2. 商品条件中的评分、点赞、30 天订单量、发货天数是否 V1 就做强校验，还是先展示并只校验库存/价格/状态。
3. 限时抢购是否需要与单品折扣互斥，还是允许叠加并在订单模拟中按最低价归因。
4. 每人限购是否 V1 必须实现，还是先仅实现活动库存限制。
5. 列表页“详情 / 复制 / 数据”入口本期是否需要真实页面，还是仅保留占位。

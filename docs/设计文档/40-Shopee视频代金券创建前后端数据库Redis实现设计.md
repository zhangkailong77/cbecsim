# 40-Shopee 视频代金券创建前后端数据库 Redis 实现设计

> 创建日期：2026-05-07  
> 状态：设计完成，待实现

## 1. 目标

为 Shopee 营销中心代金券模块接入“视频代金券”创建能力，使 `/shopee/marketing/vouchers/video-create` 页面从前端静态表单升级为可读取初始化数据、校验输入、选择适用商品、提交创建并落库的完整流程。

本期重点是接口、数据库和 Redis 数据闭环：

- 前端样式和布局沿用用户已手动调整后的 `VideoVoucherCreateView.tsx`，不重做视觉结构、颜色、间距、右侧预览或基础表单布局。
- 代金券使用期限和提前展示时间必须由后端按对局游戏时间初始化，前端 `DateTimePicker` 展示和提交游戏时间，不展示真实世界时间。
- “添加商品”区域参考已完成的商品代金券、专属代金券和直播代金券创建页：复用添加商品按钮、商品选择弹窗、已选商品表格和多变体展开提交逻辑。
- 前端仅补接口对接、受控字段初始化、商品选择数据来源、表单校验和创建提交。
- 后端新增视频代金券创建页 bootstrap、可选商品、创建提交接口，并扩展代金券列表兼容 `video_voucher`。
- 数据库新增视频代金券活动表与适用商品表，保存影响经营结果的代金券规则、视频展示范围和商品快照。
- Redis 用于创建页 bootstrap、商品选择列表、代金券列表缓存、创建限流和创建后缓存失效。
- 买家端 Shopee Video 领券、视频场景下单命中与订单归因先预留字段，不在本期实现。

## 2. 范围与非范围

### 2.1 本期范围

- 视频代金券类型：实现 `video_voucher`。
- 前端 `/shopee/marketing/vouchers/video-create` 接口对接：
  - 初始化表单默认值。
  - 代金券使用期限和提前展示时间按游戏时间展示与提交。
  - 支持适用商品选择：全部商品 / 指定商品。
  - 指定商品模式复用商品代金券已实现的商品选择弹窗、商品表格和提交展开逻辑。
  - 提交创建视频代金券。
  - 创建成功后返回 `/shopee/marketing/vouchers`。
- 后端接口：
  - 视频代金券创建页 bootstrap。
  - 视频代金券可选商品列表。
  - 创建视频代金券。
  - 代金券列表接口兼容返回视频代金券。
- 数据库：
  - 新增视频代金券活动表。
  - 新增视频代金券适用商品表。
  - 补齐表注释和字段注释。
- Redis：
  - 创建页 bootstrap 缓存。
  - 可选商品列表缓存。
  - 代金券列表缓存失效。
  - 创建接口频率限制。

### 2.2 非范围

- 不重做视频代金券创建页前端布局、颜色、间距、右侧预览图和基础表单视觉。
- 不接入真实 Shopee 平台 API。
- 不实现真实 Shopee Video 发布、观看、挂车、视频商品点击或买家端领券行为。
- 不实现视频代金券详情、编辑、复制、停止、删除和数据页。
- 不在本期改订单模拟下单概率、代金券命中、价格改写或订单归因；仅预留后续接入口径。
- 不实现上传商品列表的真实解析流程；上传 Tab 如复用弹窗，本期保留界面占位。
- 视频代金券创建页当前无“代金券代码”字段，本期不要求前端补代码输入，也不接入代码可用性检查。

## 3. 游戏时间口径

视频代金券所有面向前端的时间字段必须统一使用游戏时间：

| 场景 | 口径 |
| --- | --- |
| 创建页默认时间 | 后端根据当前对局 tick 返回游戏时间字符串 |
| 前端日期选择器展示 | 展示游戏时间，不展示真实世界时间 |
| 前端提交 `start_at/end_at/display_start_at` | 提交 `YYYY-MM-DDTHH:mm` 游戏时间字符串 |
| 后端解析 | 使用现有游戏时间解析函数映射为系统时间落库 |
| 后端返回列表/详情 | 将落库系统时间反向格式化为游戏时间 |
| 状态计算 | 基于当前游戏 tick 与代金券游戏时间比较 |
| Redis 缓存 payload | 缓存对外返回的游戏时间字符串，不缓存真实时间给前端展示 |

建议复用现有时间转换函数：

- `_format_discount_game_datetime(value, run=run)`：系统时间 -> 游戏时间字符串。
- `_parse_discount_game_datetime(raw_value, run=run)`：游戏时间字符串 -> 系统时间。
- `_resolve_game_tick(db, run_id, user_id)`：解析当前对局游戏 tick。

前端要求：

- `VideoVoucherCreateView.tsx` 的 `DateTimePicker` 初始值必须来自 bootstrap 返回的 `form.start_at`、`form.end_at` 和 `form.display_start_at`。
- 不允许在空值时让 `DateTimePicker` 回落到浏览器真实当前时间作为业务默认值。
- 若勾选“提前展示代金券”且后端未返回 `display_start_at`，前端可基于后端返回的游戏开始时间向前 1 小时生成游戏时间默认值；不能使用浏览器真实当前时间。
- 若后端未返回使用期限，应显示空值并阻止提交，提示“创建页初始化失败”或“请选择代金券使用期限”。

## 4. 业务规则

### 4.1 视频代金券定义

视频代金券用于 Shopee Video 场景。买家只能在 Shopee Video 场景中获得或使用该代金券，V1 创建流程只保存规则和商品范围，后续视频领券与订单命中统一接入。

| 字段 | 规则 |
| --- | --- |
| 代金券类型 | 固定为 `video_voucher` |
| 代金券名称 | 卖家可见，最多 100 字符 |
| 代金券代码 | 前端不展示代码字段；后端可生成内部唯一编号用于列表与后续归因，不作为买家输入码 |
| 使用期限 | `start_at < end_at`，按游戏时间显示、提交、解析和校验 |
| 提前展示 | 开启后必须填写 `display_start_at`，且 `display_start_at < start_at`，均为游戏时间 |
| 奖励类型 | V1 固定 `discount` |
| 折扣类型 | 支持 `fixed_amount` 和 `percent` |
| 固定金额 | `discount_type=fixed_amount` 时必填且大于 0 |
| 百分比 | `discount_type=percent` 时必填，建议范围 `1-100` |
| 最大折扣金额 | 百分比模式支持 `set_amount/no_limit`；`set_amount` 时金额必填且大于 0 |
| 最低消费金额 | 必填且大于 0；固定金额模式下建议 `min_spend_amount >= discount_amount` |
| 使用数量 | 所有买家可使用总代金券数量，必须为正整数 |
| 每位买家最大发放量 | 必须为正整数，且不超过使用数量 |
| 展示设置 | V1 固定 `video_stream`，前端文案为“仅在 Shopee 视频展示” |
| 适用商品 | 支持 `all_products` / `selected_products`；指定商品模式至少选择 1 个商品 |
| 视频范围 | V1 预留 `video_scope=all_videos`，不绑定具体视频内容 |

### 4.2 适用商品规则

- `applicable_scope=all_products`：视频代金券适用于当前卖家同一 `run_id/user_id` 下所有可售商品；创建时不写商品明细。
- `applicable_scope=selected_products`：必须选择至少 1 个商品，最多建议 100 个商品。
- 可选商品来自当前卖家同一 `run_id/user_id` 下已上架且可售的 Shopee 商品。
- 商品库存必须大于 0，售价必须大于 0。
- 已删除、下架、无库存、无有效售价的商品不可选。
- 指定商品弹窗样式和行为参考商品代金券：
  - 商品行展示主图、商品名称、ID/变体数、原价、库存。
  - 支持选择商品 / 上传商品列表 Tab。
  - 支持分类下拉、商品名称/商品 ID 搜索、仅显示可参与活动商品。
  - 多变体商品默认展示主商品行，接口返回 `variant_ids`。
  - 前端确认添加后保存主商品行用于展示。
  - 提交创建时将主商品自动展开为全部可售 `variant_id`，与商品代金券保持一致。
- 创建后适用商品快照保存商品名称、图片、SKU/变体名、分类、原价和库存，用于后续详情/订单归因稳定展示。

### 4.3 状态规则

代金券状态由当前游戏时间、使用量和手动停止状态计算。

| 状态 | 条件 |
| --- | --- |
| `upcoming` | 当前游戏时间早于 `start_at` |
| `ongoing` | `start_at <= 当前游戏时间 < end_at` 且未售罄、未停止 |
| `sold_out` | `used_count >= usage_limit` |
| `ended` | 当前游戏时间晚于等于 `end_at` |
| `stopped` | 卖家手动结束，后续扩展 |

数据库可保存 `status` 快照，接口返回时按当前游戏 tick 动态修正展示状态。

### 4.4 与订单模拟的关系

本期创建流程只落库，不改订单模拟；后续统一接入代金券影响时按以下口径使用：

- 命中条件：订单属于同一 `run_id/user_id` 店铺，订单游戏时间在代金券使用期限内，买家来源或商品来源命中 Shopee Video 场景，订单商品命中适用范围，订单金额满足 `min_spend_amount`。
- `all_products`：订单内所有视频场景可售商品小计可参与优惠。
- `selected_products`：仅命中适用商品明细的商品小计参与优惠。
- 优惠计算：
  - 固定金额：`discount_amount = min(voucher_amount, eligible_subtotal)`。
  - 百分比：`discount_amount = eligible_subtotal * discount_percent / 100`；若 `max_discount_type=set_amount`，再取 `min(discount_amount, max_discount_amount)`。
- 数量扣减：订单成功归因后增加 `used_count`。
- 买家限用：同一买家对同一视频代金券累计使用次数不超过 `per_buyer_limit`。
- 归因字段：后续订单级写入 `marketing_campaign_type='video_voucher'`、`marketing_campaign_id`、`marketing_campaign_name_snapshot`。

## 5. 数据模型设计

### 5.1 新增 ORM：`ShopeeVideoVoucherCampaign`

建议新增表：`shopee_video_voucher_campaigns`。

> 数据库 Schema Rules 要求：新建表必须添加表注释，新增字段必须添加字段注释。

| 字段 | 类型 | 约束 | 注释 |
| --- | --- | --- | --- |
| `id` | Integer | PK | 视频代金券活动 ID |
| `run_id` | Integer | FK `game_runs.id`, index | 所属对局 ID |
| `user_id` | Integer | FK `users.id`, index | 所属卖家用户 ID |
| `voucher_type` | String(32) | not null, default `video_voucher` | 代金券类型，V1 固定视频代金券 |
| `voucher_name` | String(255) | not null | 卖家可见的代金券名称 |
| `voucher_code` | String(64) | not null | 后端生成的内部唯一编号，用于列表和后续归因 |
| `status` | String(32) | not null, index | 状态：upcoming/ongoing/sold_out/ended/stopped |
| `start_at` | DateTime(timezone=True) | not null, index | 代金券可使用开始游戏时间映射后的系统时间 |
| `end_at` | DateTime(timezone=True) | not null, index | 代金券可使用结束游戏时间映射后的系统时间 |
| `display_before_start` | Boolean | not null, default false | 是否提前展示代金券 |
| `display_start_at` | DateTime(timezone=True) | nullable | 提前展示开始游戏时间映射后的系统时间；未提前展示时为空 |
| `reward_type` | String(32) | not null, default `discount` | 奖励类型，V1 固定折扣 |
| `discount_type` | String(32) | not null, default `fixed_amount` | 折扣类型：fixed_amount/percent |
| `discount_amount` | Float | nullable | 固定金额优惠，单位为店铺币种 |
| `discount_percent` | Float | nullable | 百分比优惠，单位为百分比 |
| `max_discount_type` | String(32) | not null, default `set_amount` | 最大折扣金额类型：set_amount/no_limit |
| `max_discount_amount` | Float | nullable | 百分比优惠最高抵扣金额，单位为店铺币种；无限制时为空 |
| `min_spend_amount` | Float | not null, default 0 | 最低消费金额，单位为店铺币种 |
| `usage_limit` | Integer | not null | 所有买家可使用总代金券数量 |
| `used_count` | Integer | not null, default 0 | 已使用数量 |
| `per_buyer_limit` | Integer | not null, default 1 | 每位买家可使用次数上限 |
| `display_type` | String(32) | not null, default `video_stream` | 展示方式，视频代金券 V1 固定 Shopee 视频展示 |
| `display_channels` | Text | nullable | 展示渠道配置 JSON，V1 固定 `["shopee_video"]` |
| `applicable_scope` | String(32) | not null, default `all_products` | 适用范围：all_products/selected_products |
| `selected_product_count` | Integer | not null, default 0 | 已选择适用商品数量 |
| `video_scope` | String(32) | not null, default `all_videos` | 视频适用范围，V1 固定全部视频场景 |
| `video_payload` | Text | nullable | 视频内容绑定配置 JSON，V1 预留为空 |
| `sales_amount` | Float | not null, default 0 | 代金券归因销售额，单位为店铺币种 |
| `order_count` | Integer | not null, default 0 | 代金券归因订单数 |
| `buyer_count` | Integer | not null, default 0 | 使用代金券买家数 |
| `created_at` | DateTime(timezone=True) | not null | 创建时间 |
| `updated_at` | DateTime(timezone=True) | not null | 更新时间 |

建议索引：

```python
Index("ix_shopee_video_vouchers_run_user_status", "run_id", "user_id", "status")
Index("ix_shopee_video_vouchers_run_user_time", "run_id", "user_id", "start_at", "end_at")
Index("ix_shopee_video_vouchers_run_user_code", "run_id", "user_id", "voucher_code", unique=True)
```

### 5.2 新增 ORM：`ShopeeVideoVoucherItem`

建议新增表：`shopee_video_voucher_items`。

| 字段 | 类型 | 约束 | 注释 |
| --- | --- | --- | --- |
| `id` | Integer | PK | 视频代金券适用商品记录 ID |
| `campaign_id` | Integer | FK `shopee_video_voucher_campaigns.id`, index | 视频代金券活动 ID |
| `run_id` | Integer | FK `game_runs.id`, index | 所属对局 ID |
| `user_id` | Integer | FK `users.id`, index | 所属卖家用户 ID |
| `listing_id` | Integer | FK `shopee_listings.id`, not null, index | Shopee 商品 listing ID |
| `variant_id` | Integer | FK `shopee_listing_variants.id`, nullable, index | Shopee 商品变体 ID；整商品适用时为空 |
| `product_id` | Integer | nullable, index | 关联选品池商品 ID |
| `product_name_snapshot` | String(255) | not null | 创建时商品名称快照 |
| `variant_name_snapshot` | String(255) | nullable | 创建时变体名称快照 |
| `sku_snapshot` | String(128) | nullable | 创建时 SKU 快照 |
| `image_url_snapshot` | String(1024) | nullable | 创建时商品图片 URL 快照 |
| `category_key_snapshot` | String(128) | nullable | 创建时商品分类 key 快照 |
| `category_label_snapshot` | String(255) | nullable | 创建时商品分类名称快照 |
| `original_price_snapshot` | Float | not null, default 0 | 创建时商品原价快照 |
| `stock_snapshot` | Integer | not null, default 0 | 创建时可用库存快照 |
| `sort_order` | Integer | not null, default 0 | 页面展示排序 |
| `created_at` | DateTime(timezone=True) | not null | 创建时间 |
| `updated_at` | DateTime(timezone=True) | not null | 更新时间 |

建议索引/约束：

```python
UniqueConstraint("campaign_id", "listing_id", "variant_id", name="uq_shopee_video_voucher_item_variant")
Index("ix_shopee_video_voucher_items_campaign", "campaign_id")
Index("ix_shopee_video_voucher_items_listing", "run_id", "user_id", "listing_id")
Index("ix_shopee_video_voucher_items_product", "product_id")
```

说明：字段命名应直接使用当前商品代金券已验证可落库的 `stock_snapshot`，不要再引入 `stock_available_snapshot`。

## 6. 后端接口设计

接口文件沿用：`backend/apps/api-gateway/app/api/routes/shopee.py`。

### 6.1 创建页 Bootstrap

```http
GET /shopee/runs/{run_id}/marketing/vouchers/video-create/bootstrap
```

用途：为视频代金券创建页提供游戏时间默认值、表单规则、只读状态和商品选择配置。

响应示例：

```json
{
  "meta": {
    "run_id": 1,
    "user_id": 2,
    "voucher_type": "video_voucher",
    "read_only": false,
    "current_tick": "2026-06-05T08:32",
    "currency": "RM",
    "market": "MY"
  },
  "form": {
    "voucher_name": "",
    "start_at": "2026-06-05T09:00",
    "end_at": "2026-06-06T09:00",
    "display_before_start": false,
    "display_start_at": null,
    "reward_type": "discount",
    "discount_type": "fixed_amount",
    "discount_amount": null,
    "discount_percent": null,
    "max_discount_type": "set_amount",
    "max_discount_amount": null,
    "min_spend_amount": null,
    "usage_limit": null,
    "per_buyer_limit": 1,
    "display_type": "video_stream",
    "display_channels": ["shopee_video"],
    "applicable_scope": "all_products",
    "video_scope": "all_videos"
  },
  "rules": {
    "name_max_length": 100,
    "discount_percent_range": [1, 100],
    "max_selected_products": 100,
    "display_modes": ["video_stream"],
    "applicable_scopes": ["all_products", "selected_products"]
  },
  "product_picker": {
    "default_page_size": 10,
    "supports_upload": false,
    "available_only_default": true
  }
}
```

后端逻辑：

- 校验 `run_id/user_id` 权限。
- 读取当前游戏 tick。
- 默认 `start_at` 建议为当前游戏时间向后取整 30 分钟或 1 小时，`end_at` 为 `start_at + 24h`，均返回游戏时间字符串。
- 只读历史对局返回 `read_only=true`。
- Redis 缓存 bootstrap payload。

### 6.2 可选商品列表

```http
GET /shopee/runs/{run_id}/marketing/vouchers/video-create/eligible-products
```

查询参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `page` | int | 页码，默认 1 |
| `page_size` | int | 每页数量，默认 10 |
| `keyword` | string | 搜索关键字 |
| `search_field` | string | `product_name/product_id` |
| `category` | string | 分类 key，默认 all |
| `available_only` | bool | 是否仅显示可参与商品，默认 true |

响应示例：

```json
{
  "page": 1,
  "page_size": 10,
  "total": 1,
  "items": [
    {
      "listing_id": 101,
      "variant_id": null,
      "variant_ids": [1001, 1002],
      "product_id": 88,
      "product_name": "Video Bag",
      "variant_name": null,
      "category": "Women Bags",
      "image_url": "https://...",
      "sku": "BAG-VIDEO",
      "original_price": 29.9,
      "stock_available": 120,
      "available": true,
      "unavailable_reason": null
    }
  ]
}
```

后端逻辑：

- 查询当前卖家同一 `run_id/user_id` 下已上架商品。
- 聚合主商品行，并返回可售 `variant_ids`，支持前端主商品行展示和提交展开。
- 过滤无库存、无有效售价、下架和删除商品。
- Redis 按筛选条件缓存可选商品列表。

### 6.3 创建视频代金券

```http
POST /shopee/runs/{run_id}/marketing/vouchers/video-campaigns
```

请求体示例：

```json
{
  "voucher_type": "video_voucher",
  "voucher_name": "视频专享券",
  "start_at": "2026-06-05T09:00",
  "end_at": "2026-06-06T09:00",
  "display_before_start": true,
  "display_start_at": "2026-06-05T08:00",
  "reward_type": "discount",
  "discount_type": "fixed_amount",
  "discount_amount": 3,
  "discount_percent": null,
  "max_discount_type": "set_amount",
  "max_discount_amount": null,
  "min_spend_amount": 20,
  "usage_limit": 100,
  "per_buyer_limit": 1,
  "display_type": "video_stream",
  "display_channels": ["shopee_video"],
  "applicable_scope": "selected_products",
  "video_scope": "all_videos",
  "selected_products": [
    { "listing_id": 101, "variant_id": 1001 },
    { "listing_id": 101, "variant_id": 1002 }
  ]
}
```

校验规则：

- 历史对局只读时禁止创建。
- `voucher_type` 强制为 `video_voucher`，不信任前端传入其他类型。
- `display_type` 强制为 `video_stream`，`display_channels` 强制为 `["shopee_video"]`。
- `voucher_name` 必填且不超过 100 字符。
- `start_at/end_at/display_start_at` 按游戏时间解析；`start_at < end_at`；提前展示时 `display_start_at < start_at`。
- 固定金额、百分比、最大折扣、最低消费、使用数量、买家限用按通用代金券规则校验。
- `applicable_scope=selected_products` 时 `selected_products` 必须非空。
- `applicable_scope=all_products` 时忽略 `selected_products`，不写商品明细。
- `selected_products` 内商品必须属于当前 `run_id/user_id` 且可售。
- 多变体商品提交时按 `(listing_id, variant_id)` 去重。
- 后端生成内部唯一 `voucher_code`，建议格式为 `VIDEO-{campaign_id}` 或创建前生成 `VIDEO{短随机码}`，只用于列表展示和后续归因，不要求买家输入。

创建逻辑：

1. 获取 Redis 创建限流锁。
2. 解析并校验请求。
3. 创建 `ShopeeVideoVoucherCampaign`。
4. 若指定商品，批量创建 `ShopeeVideoVoucherItem` 快照。
5. 提交事务。
6. 清理代金券列表、视频代金券创建页和可选商品相关缓存。
7. 返回创建结果。

响应示例：

```json
{
  "id": 501,
  "voucher_type": "video_voucher",
  "voucher_name": "视频专享券",
  "voucher_code": "VIDEO501",
  "status": "upcoming",
  "start_at": "2026-06-05T09:00",
  "end_at": "2026-06-06T09:00",
  "selected_product_count": 2
}
```

### 6.4 代金券列表兼容

`GET /shopee/runs/{run_id}/marketing/vouchers` 需要合并返回视频代金券：

- `voucher_type=video_voucher`
- `voucher_type_label=视频代金券`
- `display_type_label=Shopee Video`
- `period_text` 使用游戏时间。
- `products` 使用 `shopee_video_voucher_items` 商品快照；全部商品时展示“全部商品”。
- 若列表展示代码列，视频代金券可展示内部编号或 `-`，不要求前端创建页补代码输入。

## 7. 前端接口接入设计

### 7.1 页面状态

`VideoVoucherCreateView.tsx` 保留现有布局，在现有 state 基础上补充：

- `runId: number | null` prop，用于调用后端接口；`ShopeePage.tsx` 进入视频代金券创建页时传入 `run?.id ?? null`。
- `loading/saving/error/serverReadOnly`。
- `currency` 从 bootstrap 返回，不再硬编码业务币种。
- `selectedProducts`：已选商品表格数据。
- `productPickerOpen/productPickerRows/productPickerSelections/productPickerFilters`：复用商品代金券选择弹窗模式。

### 7.2 Bootstrap 对接

页面挂载后：

```ts
GET /shopee/runs/${runId}/marketing/vouchers/video-create/bootstrap
```

前端处理：

- 将 `form.start_at/end_at/display_start_at` 直接填入 `DateTimePicker`。
- 不使用 `new Date()` 或浏览器当前时间作为默认值。
- `display_before_start=true` 时显示提前展示时间选择器。
- 初始化币种、默认折扣类型、使用数量、展示方式和适用范围。
- `meta.read_only=true` 时禁用所有输入与提交。

### 7.3 日期选择器

- 继续复用 `frontend/src/modules/shopee/components/DateTimePicker`。
- `voucherStartAt` 的 `maxValue` 为 `voucherEndAt`。
- `voucherEndAt` 的 `minValue` 为 `voucherStartAt`。
- `displayStartAt` 的 `maxValue` 为 `voucherStartAt`。
- 显示文案保留：`这里显示和提交的时间均为当前对局的游戏时间。`
- 提交时直接传 `YYYY-MM-DDTHH:mm` 游戏时间字符串。

### 7.4 添加商品

当 `applicableProductType === 'specific'` 时，点击“添加商品”：

- 打开商品选择弹窗。
- 弹窗 UI 和交互参考商品代金券：
  - 选择商品 / 上传商品列表 Tab。
  - 分类下拉。
  - 搜索字段：商品名称 / 商品 ID。
  - 关键词输入。
  - 仅显示可参与活动商品。
  - 商品表格。
  - 空状态。
  - 取消 / 确认按钮。
- 可选商品接口：

```ts
GET /shopee/runs/${runId}/marketing/vouchers/video-create/eligible-products
```

- 确认添加后，在“适用商品”区域展示已选商品表格，包含：
  - Products：主图、商品名、ID/变体数。
  - Original Price：原价。
  - Stock：库存。
  - Action：删除。
- 提交时：
  - `all_products`：提交 `applicable_scope='all_products'` 且 `selected_products=[]`。
  - `selected_products`：将带 `variant_ids` 的主商品展开为多个 `{ listing_id, variant_id }`。

### 7.5 创建提交

提交接口：

```ts
POST /shopee/runs/${runId}/marketing/vouchers/video-campaigns
```

前端 payload：

```ts
{
  voucher_type: 'video_voucher',
  voucher_name: voucherName.trim(),
  start_at: voucherStartAt,
  end_at: voucherEndAt,
  display_before_start: displayBeforeStart,
  display_start_at: displayBeforeStart ? displayStartAt : null,
  reward_type: 'discount',
  discount_type: discountType,
  discount_amount: discountType === 'fixed_amount' ? Number(discountAmount) : null,
  discount_percent: discountType === 'percent' ? Number(discountPercent) : null,
  max_discount_type: discountType === 'percent' ? maxDiscountType : 'set_amount',
  max_discount_amount: discountType === 'percent' && maxDiscountType === 'set_amount' ? Number(maxDiscountAmount) : null,
  min_spend_amount: Number(minSpendAmount),
  usage_limit: Number(usageLimit),
  per_buyer_limit: Number(perBuyerLimit),
  display_type: 'video_stream',
  display_channels: ['shopee_video'],
  applicable_scope: applicableProductType === 'specific' ? 'selected_products' : 'all_products',
  video_scope: 'all_videos',
  selected_products: applicableProductType === 'specific' ? expandedSelectedProducts : []
}
```

成功后：

- 清空本地错误。
- 返回 `/shopee/marketing/vouchers`。
- 代金券列表接口应能看到新建视频代金券。

## 8. Redis 设计

### 8.1 Key 设计

| Key | TTL | 用途 |
| --- | --- | --- |
| `shopee:vouchers:video:create:bootstrap:{run_id}:{user_id}` | 5 分钟 | 视频代金券创建页初始化数据 |
| `shopee:vouchers:video:create:eligible:{run_id}:{user_id}:{hash}` | 2 分钟 | 可选商品列表 |
| `shopee:vouchers:list:{run_id}:{user_id}:{hash}` | 2 分钟 | 代金券列表缓存，需兼容视频代金券 |
| `shopee:vouchers:video:create:limit:{run_id}:{user_id}` | 10 秒 | 创建接口限流 |

### 8.2 缓存失效

创建视频代金券成功后清理：

- `shopee:vouchers:list:{run_id}:{user_id}:*`
- `shopee:vouchers:video:create:bootstrap:{run_id}:{user_id}`
- `shopee:vouchers:video:create:eligible:{run_id}:{user_id}:*`

后续实现编辑、停止、删除、订单归因时也必须清理列表和统计缓存。

### 8.3 限流

- 创建接口按 `run_id/user_id` 维度加短 TTL 限流，避免重复点击创建多条相同代金券。
- 命中限流时返回 429 或业务错误文案：`操作过于频繁，请稍后再试。`

## 9. 数据一致性与事务

- 创建活动和商品明细必须在同一个数据库事务内完成。
- 视频代金券虽然不要求前端输入代码，但后端内部编号仍需数据库唯一索引兜底。
- 商品明细批量写入前应重新校验商品归属、库存和售价，不能只信任前端快照。
- `selected_product_count` 应以最终落库明细或选择主商品数计算，需与列表展示口径一致。
- 创建成功后再清理缓存；事务失败不得清理列表缓存。

## 10. 验收标准

- 访问 `/shopee/marketing/vouchers/video-create` 时，页面保持用户现有视频代金券创建页布局。
- 创建页 bootstrap 成功后，使用期限和提前展示时间显示游戏时间，不显示真实世界当前时间。
- 勾选“提前展示代金券”时，提前展示时间必须早于使用开始时间。
- 指定商品模式下，点击“添加商品”可打开与商品代金券一致的商品选择弹窗。
- 添加商品后，“适用商品”区域展示已选商品表格。
- 提交指定商品时，多变体主商品会展开为多个 `{ listing_id, variant_id }`。
- `POST /video-campaigns` 创建成功后，活动和商品明细落库，缓存正确失效，并返回代金券列表。
- `/shopee/marketing/vouchers` 列表可展示视频代金券。
- 历史对局回溯模式下可浏览创建页，但无法创建。
- 后端新增表和字段均补齐表注释、字段注释、索引和唯一约束。

## 11. 后续扩展

- 接入 Shopee Video 真实领券、视频商品曝光、视频挂车和买家观看行为。
- 接入订单模拟命中视频代金券、优惠金额改写和归因统计。
- 增加视频代金券详情、编辑、复制、停止、删除和数据页。
- 上传商品列表解析和批量选择。
- 视频内容维度的代金券绑定，如 `video_scope=specific_videos`。

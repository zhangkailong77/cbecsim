# 37-Shopee 商品代金券创建前后端数据库 Redis 实现设计

> 创建日期：2026-05-06  
> 状态：设计完成，待实现

## 1. 目标

为 Shopee 营销中心代金券模块接入“商品代金券”创建能力，使 `/shopee/marketing/vouchers/product-create` 页面从前端静态/临时选品状态升级为可读取初始化数据、校验输入、选择适用商品、提交创建并落库的完整流程。

本期重点是接口、数据库和 Redis 数据闭环：

- 前端布局和视觉界面不再调整，沿用用户已手动优化后的 `ProductVoucherCreateView.tsx`。
- 前端仅补接口对接、受控字段初始化、商品选择数据来源、代码校验和创建提交。
- 所有页面显示、接口提交和后端校验的使用期限、提前展示时间、当前时间都按对局游戏时间口径处理，不显示真实世界时间。
- 数据库新增商品代金券活动表与适用商品表，保存影响经营结果的代金券规则和商品范围。
- Redis 用于创建页 bootstrap、商品选择列表、代码检查、代金券列表缓存、创建限流和创建后缓存失效。
- 订单模拟命中代金券、使用记录和下单概率影响先预留字段与接口边界，等其他代金券类型完成后统一接入。

## 2. 范围与非范围

### 2.1 本期范围

- 商品代金券类型：实现 `product_voucher`。
- 前端 `/shopee/marketing/vouchers/product-create` 接口对接：
  - 初始化表单默认值。
  - 加载可选商品列表。
  - 临时选择适用商品并提交商品范围。
  - 校验代金券代码可用性。
  - 提交创建商品代金券。
  - 创建成功后返回 `/shopee/marketing/vouchers`。
- 后端接口：
  - 商品代金券创建页 bootstrap。
  - 商品代金券可选商品列表。
  - 代金券代码可用性检查支持 `product_voucher`。
  - 创建商品代金券。
  - 代金券列表接口兼容返回商品代金券。
- 数据库：
  - 新增商品代金券活动表。
  - 新增商品代金券适用商品表。
  - 补齐表注释和字段注释。
- Redis：
  - 创建页 bootstrap 缓存。
  - 可选商品列表缓存。
  - 代码检查缓存。
  - 代金券列表缓存失效。
  - 创建接口频率限制。

### 2.2 非范围

- 不再修改商品代金券创建页前端布局、颜色、间距和弹窗样式。
- 不接入真实 Shopee 平台 API。
- 不实现买家端领券页面或买家主动领券行为。
- 不在本期改订单模拟下单概率、代金券命中、价格改写或订单归因；仅预留后续接入口径。
- 不实现商品代金券详情、编辑、复制、停止、删除和数据页。
- 不实现上传商品列表的真实解析流程；上传 Tab 本期保留界面占位。

## 3. 游戏时间口径

商品代金券所有时间字段必须统一使用游戏时间：

| 场景 | 口径 |
| --- | --- |
| 创建页默认时间 | 后端根据当前对局 tick 返回游戏时间字符串 |
| 前端日期选择器展示 | 展示游戏时间，不展示真实世界时间 |
| 前端提交 `start_at/end_at/display_start_at` | 提交 `YYYY-MM-DDTHH:mm` 游戏时间字符串 |
| 后端解析 | 使用现有游戏时间解析函数映射为系统时间落库 |
| 后端返回列表/详情 | 将落库系统时间反向格式化为游戏时间 |
| 状态计算 | 基于当前游戏 tick 与代金券游戏时间比较 |
| Redis 缓存 payload | 缓存对外返回的游戏时间字符串，不缓存真实时间给前端展示 |

建议复用店铺代金券已实现的时间转换函数：

- `_format_discount_game_datetime(value, run=run)`：系统时间 -> 游戏时间字符串。
- `_parse_discount_game_datetime(raw_value, run=run)`：游戏时间字符串 -> 系统时间。
- `_resolve_game_tick(db, run_id, user_id)`：解析当前对局游戏 tick。

约束：接口响应中面向前端的时间字段均使用 `YYYY-MM-DDTHH:mm` 或带时区的游戏 tick 字符串；不要返回真实世界时间给创建页展示。

## 4. 业务规则

### 4.1 商品代金券定义

商品代金券仅适用于卖家选择的指定商品。订单满足最低消费金额后，买家可在指定商品上使用固定金额或百分比优惠。

| 字段 | 规则 |
| --- | --- |
| 代金券类型 | 固定为 `product_voucher` |
| 代金券名称 | 卖家可见，买家不展示，最多 100 字符 |
| 代金券代码 | `HOME` 前缀 + 卖家输入后缀；后缀仅允许 `A-Z`、`0-9`，最多 5 字符 |
| 使用期限 | `start_at < end_at`，按游戏时间显示、提交、解析和校验 |
| 提前展示 | 开启后必须填写 `display_start_at`，且 `display_start_at < start_at`，均为游戏时间 |
| 奖励类型 | V1 固定 `discount` |
| 折扣类型 | 支持 `fixed_amount` 和 `percent` |
| 固定金额 | `discount_type=fixed_amount` 时必填且大于 0 |
| 百分比 | `discount_type=percent` 时必填，建议范围 `1-100` |
| 最大折扣金额 | 百分比模式支持 `set_amount/no_limit`；`set_amount` 时金额必填且大于 0 |
| 最低消费金额 | 必填且大于 0；固定金额模式下建议 `min_spend_amount >= discount_amount` |
| 使用数量 | 所有买家可使用总数，必须为正整数 |
| 每位买家最大发放量 | 必须为正整数，且不超过使用数量 |
| 展示设置 | 支持 `all_pages/specific_channels/code_only`；特定渠道 V1 支持 `checkout_page` |
| 适用商品 | 至少选择 1 个商品；按 listing 维度保存，必要时支持 variant 维度扩展 |

### 4.2 适用商品规则

- 可选商品来自当前卖家同一 `run_id/user_id` 下已上架且可售的 Shopee 商品。
- 商品库存必须大于 0。
- 已删除、下架、无库存、无有效售价的商品不可选。
- 同一商品不可重复加入同一个商品代金券。
- V1 建议按 `listing_id` 维度适用整商品；若前端选择弹窗返回 `variant_id`，后端可保存但订单命中时优先按 `listing_id` 判断。
- 创建后适用商品快照保存商品名称、图片、SKU/变体名、原价和库存，用于列表/详情展示稳定，不依赖商品后续修改。

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

- 命中条件：订单属于同一 `run_id/user_id` 店铺，订单游戏时间在代金券使用期限内，订单商品命中商品代金券适用商品，订单商品小计满足 `min_spend_amount`。
- 优惠计算：
  - 固定金额：`discount_amount = min(voucher_amount, eligible_product_subtotal)`。
  - 百分比：`discount_amount = eligible_product_subtotal * discount_percent / 100`；若 `max_discount_type=set_amount`，再取 `min(discount_amount, max_discount_amount)`。
- 数量扣减：订单成功归因后增加 `used_count`。
- 买家限用：同一买家对同一商品代金券累计使用次数不超过 `per_buyer_limit`。
- 归因字段：后续订单级写入 `marketing_campaign_type='product_voucher'`、`marketing_campaign_id`、`marketing_campaign_name_snapshot`。

## 5. 数据模型设计

### 5.1 新增 ORM：`ShopeeProductVoucherCampaign`

建议新增表：`shopee_product_voucher_campaigns`。

> 数据库 Schema Rules 要求：新建表必须添加表注释，新增字段必须添加字段注释。

| 字段 | 类型 | 约束 | 注释 |
| --- | --- | --- | --- |
| `id` | Integer | PK | 商品代金券活动 ID |
| `run_id` | Integer | FK `game_runs.id`, index | 所属对局 ID |
| `user_id` | Integer | FK `users.id`, index | 所属卖家用户 ID |
| `voucher_type` | String(32) | not null, default `product_voucher` | 代金券类型，V1 固定商品代金券 |
| `voucher_name` | String(255) | not null | 卖家可见的代金券名称 |
| `voucher_code` | String(32) | not null | 完整代金券代码，如 `HOMEP1234` |
| `code_prefix` | String(16) | not null, default `HOME` | 代金券代码前缀 |
| `code_suffix` | String(16) | not null | 卖家输入的代码后缀 |
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
| `display_type` | String(32) | not null, default `all_pages` | 展示方式：all_pages/specific_channels/code_only |
| `display_channels` | Text | nullable | 特定渠道配置 JSON，V1 支持 checkout_page |
| `applicable_scope` | String(32) | not null, default `selected_products` | 适用范围，商品代金券固定指定商品 |
| `selected_product_count` | Integer | not null, default 0 | 已选择适用商品数量 |
| `sales_amount` | Float | not null, default 0 | 代金券归因销售额，单位为店铺币种 |
| `order_count` | Integer | not null, default 0 | 代金券归因订单数 |
| `buyer_count` | Integer | not null, default 0 | 使用代金券买家数 |
| `created_at` | DateTime(timezone=True) | not null | 创建时间 |
| `updated_at` | DateTime(timezone=True) | not null | 更新时间 |

建议索引：

```python
Index("ix_shopee_product_vouchers_run_user_status", "run_id", "user_id", "status")
Index("ix_shopee_product_vouchers_run_user_time", "run_id", "user_id", "start_at", "end_at")
Index("ix_shopee_product_vouchers_run_user_code", "run_id", "user_id", "voucher_code", unique=True)
```

### 5.2 新增 ORM：`ShopeeProductVoucherItem`

建议新增表：`shopee_product_voucher_items`。

| 字段 | 类型 | 约束 | 注释 |
| --- | --- | --- | --- |
| `id` | Integer | PK | 商品代金券适用商品记录 ID |
| `campaign_id` | Integer | FK `shopee_product_voucher_campaigns.id`, index | 商品代金券活动 ID |
| `run_id` | Integer | FK `game_runs.id`, index | 所属对局 ID |
| `user_id` | Integer | FK `users.id`, index | 所属卖家用户 ID |
| `listing_id` | Integer | not null, index | Shopee 商品 listing ID |
| `variant_id` | Integer | nullable, index | Shopee 商品变体 ID；整商品适用时为空 |
| `product_name_snapshot` | String(255) | not null | 创建时商品名称快照 |
| `variant_name_snapshot` | String(255) | nullable | 创建时变体名称快照 |
| `sku_snapshot` | String(128) | nullable | 创建时 SKU 快照 |
| `image_url_snapshot` | Text | nullable | 创建时商品图片 URL 快照 |
| `category_key_snapshot` | String(128) | nullable | 创建时商品分类 key 快照 |
| `category_label_snapshot` | String(255) | nullable | 创建时商品分类名称快照 |
| `original_price_snapshot` | Float | not null | 创建时商品原价快照 |
| `stock_available_snapshot` | Integer | not null, default 0 | 创建时可用库存快照 |
| `created_at` | DateTime(timezone=True) | not null | 创建时间 |
| `updated_at` | DateTime(timezone=True) | not null | 更新时间 |

建议索引/约束：

```python
Index("ix_shopee_product_voucher_items_campaign", "campaign_id")
Index("ix_shopee_product_voucher_items_listing", "run_id", "user_id", "listing_id")
UniqueConstraint("campaign_id", "listing_id", "variant_id", name="uq_shopee_product_voucher_item_variant")
```

若 MySQL 对 nullable `variant_id` 唯一约束不满足整商品去重，可将整商品适用的 `variant_id` 统一存为 `0`，或增加 `variant_key` 字段保存 `variant_id or 0`。

## 6. 后端接口设计

接口文件沿用：`backend/apps/api-gateway/app/api/routes/shopee.py`。

### 6.1 创建页 Bootstrap

```http
GET /shopee/runs/{run_id}/marketing/vouchers/product-create/bootstrap
```

用途：为商品代金券创建页提供游戏时间默认值、表单规则、只读状态和商品选择配置。

响应示例：

```json
{
  "meta": {
    "run_id": 1,
    "user_id": 2,
    "voucher_type": "product_voucher",
    "read_only": false,
    "current_tick": "2026-06-05T08:32",
    "currency": "RM"
  },
  "form": {
    "voucher_name": "",
    "code_prefix": "HOME",
    "code_suffix_max_length": 5,
    "start_at": "2026-06-05T08:32",
    "end_at": "2026-06-05T09:32",
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
    "display_type": "all_pages",
    "display_channels": [],
    "applicable_scope": "selected_products"
  },
  "rules": {
    "voucher_name_max_length": 100,
    "code_suffix_pattern": "^[A-Z0-9]{1,5}$",
    "min_duration_minutes": 1,
    "max_duration_days": 180,
    "discount_types": ["fixed_amount", "percent"],
    "max_discount_types": ["set_amount", "no_limit"],
    "display_types": ["all_pages", "specific_channels", "code_only"],
    "display_channels": ["checkout_page"],
    "min_selected_products": 1,
    "max_selected_products": 100
  },
  "product_picker": {
    "default_page_size": 20,
    "search_fields": ["product_name", "product_id"],
    "available_only_default": true
  },
  "selected_products": []
}
```

时间要求：`current_tick/start_at/end_at/display_start_at` 均为游戏时间字符串。

### 6.2 商品代金券可选商品

```http
GET /shopee/runs/{run_id}/marketing/vouchers/product-create/eligible-products?keyword=&search_field=product_name&category_key=all&page=1&page_size=20
```

用途：为商品代金券“添加商品”弹窗提供可选商品数据。

请求参数：

| 参数 | 说明 |
| --- | --- |
| `keyword` | 搜索关键词，可为空 |
| `search_field` | `product_name/product_id` |
| `category_key` | `all` 或店铺分类 key |
| `page/page_size` | 分页参数，`page_size` 建议最大 50 |

响应示例：

```json
{
  "page": 1,
  "page_size": 20,
  "total": 2,
  "items": [
    {
      "listing_id": 1001,
      "variant_id": null,
      "product_name": "儿童水杯",
      "variant_name": "",
      "sku": "CUP-001",
      "image_url": "https://...",
      "category_key": "kids_cup",
      "category_label": "母婴 > 水杯",
      "original_price": 19.9,
      "price_range_label": "RM 19.90",
      "stock_available": 120,
      "likes_count": 0,
      "conflict": false,
      "conflict_reason": null
    }
  ]
}
```

可复用现有单品折扣/限时抢购商品查询逻辑，但应新建商品代金券专属接口，避免继续依赖 `/marketing/discount/eligible-products` 的业务语义。

### 6.3 代金券代码可用性检查

沿用并扩展现有接口：

```http
GET /shopee/runs/{run_id}/marketing/vouchers/code/check?voucher_type=product_voucher&code_suffix=P1234
```

规则：

- `voucher_type` 支持 `shop_voucher/product_voucher`。
- `code_suffix` 后端统一转大写后校验 `^[A-Z0-9]{1,5}$`。
- 完整代码按 `HOME + code_suffix` 生成。
- 同一 `run_id/user_id` 下建议所有代金券类型共享 `voucher_code` 唯一性，避免买家输入同一码产生歧义。
- 若继续分表保存店铺代金券和商品代金券，代码检查和创建提交必须同时查两张表。

### 6.4 创建商品代金券

```http
POST /shopee/runs/{run_id}/marketing/vouchers/product-campaigns
```

请求示例：

```json
{
  "voucher_type": "product_voucher",
  "voucher_name": "儿童水杯专属券",
  "code_suffix": "P1234",
  "start_at": "2026-06-05T08:32",
  "end_at": "2026-06-05T09:32",
  "display_before_start": true,
  "display_start_at": "2026-06-05T08:00",
  "reward_type": "discount",
  "discount_type": "fixed_amount",
  "discount_amount": 5,
  "discount_percent": null,
  "max_discount_type": "set_amount",
  "max_discount_amount": null,
  "min_spend_amount": 20,
  "usage_limit": 1000,
  "per_buyer_limit": 1,
  "display_type": "specific_channels",
  "display_channels": ["checkout_page"],
  "selected_products": [
    { "listing_id": 1001, "variant_id": null }
  ]
}
```

响应示例：

```json
{
  "campaign_id": 456,
  "voucher_type": "product_voucher",
  "status": "upcoming",
  "redirect_url": "/shopee/marketing/vouchers"
}
```

校验规则：

- `run_id` 必须属于当前用户可操作对局。
- 历史回溯只读模式禁止创建。
- `voucher_type` 仅允许 `product_voucher`。
- `voucher_name` 必填且不超过 100 字符。
- `code_suffix` 转大写后匹配 `^[A-Z0-9]{1,5}$`。
- 同一 `run_id/user_id` 下完整 `voucher_code` 不可与任意代金券重复。
- `start_at/end_at/display_start_at` 均按游戏时间解析。
- `start_at < end_at`，且使用期限不超过 180 个游戏天。
- `display_before_start=true` 时 `display_start_at` 必填且早于 `start_at`。
- `display_before_start=false` 时 `display_start_at` 必须为空。
- `discount_type=fixed_amount` 时 `discount_amount > 0`，`discount_percent/max_discount_amount` 不参与计算。
- `discount_type=percent` 时 `0 < discount_percent <= 100`，`discount_amount` 不参与计算。
- `max_discount_type=no_limit` 时 `max_discount_amount` 必须为空。
- `min_spend_amount > 0`；固定金额模式下建议 `min_spend_amount >= discount_amount`。
- `usage_limit > 0`，`per_buyer_limit > 0`，且 `per_buyer_limit <= usage_limit`。
- `display_type=specific_channels` 时 `display_channels` 至少包含一个合法渠道；V1 仅允许 `checkout_page`。
- `selected_products` 至少 1 个，最多 100 个。
- 所选商品必须属于当前 `run_id/user_id`，且当前可售。

### 6.5 代金券列表兼容

现有列表接口继续使用：

```http
GET /shopee/runs/{run_id}/marketing/vouchers?status=all&keyword=&page=1&page_size=20
```

新增商品代金券后，列表应同时返回店铺代金券和商品代金券。

商品代金券行示例：

```json
{
  "id": 456,
  "voucher_name": "儿童水杯专属券",
  "voucher_code": "HOMEP1234",
  "voucher_type": "Product Voucher",
  "voucher_type_label": "商品代金券",
  "discount_type": "fixed_amount",
  "discount_label": "RM 5",
  "status": "upcoming",
  "status_label": "即将开始",
  "scope_label": "指定商品 1 个",
  "selected_product_count": 1,
  "usage_limit": 1000,
  "used_count": 0,
  "period": "05/06/2026 08:32 - 05/06/2026 09:32"
}
```

`period` 必须由游戏时间格式化得到，不展示真实世界时间。

## 7. 前端对接设计

### 7.1 页面文件

主要文件：`frontend/src/modules/shopee/views/ProductVoucherCreateView.tsx`。

前端布局、视觉样式和弹窗结构不再修改，只补以下接口逻辑：

- `loading`：创建页 bootstrap 加载状态。
- `saving`：创建提交状态。
- `error`：接口或校验错误。
- `serverReadOnly`：后端只读状态。
- `currency`：后端返回币种。
- `codeChecking/codeCheck`：代码检查状态。
- `selectedProducts`：从弹窗确认后的适用商品列表。

### 7.2 初始化流程

页面挂载后：

1. 读取 `ACCESS_TOKEN_KEY`。
2. 请求 `GET /shopee/runs/{run_id}/marketing/vouchers/product-create/bootstrap`。
3. 将响应 `form` 写入当前页面已有状态。
4. 所有日期字段直接设置为后端返回的游戏时间字符串，传给现有 `DateTimePicker`。
5. 若接口失败，展示错误提示，但不改变页面布局。

### 7.3 商品选择弹窗

当前弹窗界面已复刻限时抢购商品选择弹窗，后续只替换数据源：

- 打开弹窗时请求商品代金券专属可选商品接口。
- 搜索、分类、仅显示可参与活动商品走接口参数或前端二次过滤。
- 点击“确认”后将选择结果写入 `selectedProducts`。
- 创建提交时只提交 `listing_id/variant_id`，商品快照由后端重新查询并保存，避免信任前端传入的价格/库存/名称。

### 7.4 提交流程

点击“确认”按钮：

1. 前端做轻量校验：名称、代码、时间、折扣、数量、展示设置、至少一个商品。
2. 请求 `POST /shopee/runs/{run_id}/marketing/vouchers/product-campaigns`。
3. 请求体内时间字段保持游戏时间字符串。
4. 成功后调用 `onBackToVouchers()` 返回列表页。
5. 失败时展示后端错误，不改变表单内容。

## 8. Redis 设计

建议 key：

| 用途 | Key | TTL |
| --- | --- | --- |
| 创建页 bootstrap | `cbec:cache:shopee:product-voucher:create:bootstrap:{run_id}:{user_id}` | 60s |
| 可选商品列表 | `cbec:cache:shopee:product-voucher:eligible-products:{run_id}:{user_id}:{hash}` | 30s |
| 代码检查 | `cbec:cache:shopee:vouchers:code-check:{run_id}:{user_id}:{voucher_type}:{code_suffix}` | 30s |
| 代金券列表 | `cbec:cache:shopee:vouchers:list:{run_id}:{user_id}:{hash}` | 30s |
| 创建限流 | `cbec:ratelimit:shopee:product-voucher:create:user:{user_id}` | 60s window |

创建成功后必须失效：

- 商品代金券创建页 bootstrap。
- 商品代金券可选商品缓存。
- 代金券代码检查缓存。
- 统一代金券列表/表现缓存。

缓存 payload 面向前端时只保存游戏时间字符串；后端内部如缓存 ORM 派生数据，不得直接透出真实时间给前端创建页。

## 9. 实施步骤

1. 后端模型：新增 `ShopeeProductVoucherCampaign`、`ShopeeProductVoucherItem`，补齐表注释、字段注释、索引和旧库初始化逻辑。
2. 后端 schema：新增商品代金券 bootstrap、eligible products、create request/response Pydantic 模型。
3. 后端接口：实现 bootstrap、eligible-products、product-campaigns，并扩展 code check 和 vouchers list。
4. 时间逻辑：复用店铺代金券游戏时间解析/格式化函数，确保前端无真实时间展示。
5. Redis：新增缓存 key、限流和创建后失效。
6. 前端接口：`ProductVoucherCreateView.tsx` 接 bootstrap、eligible-products、code check 和 create submit；不调整布局。
7. 文档：同步 `docs/当前进度.md`、`docs/change-log.md`。

## 10. 验收标准

- 访问 `/shopee/marketing/vouchers/product-create` 时，默认使用期限显示当前对局游戏时间。
- 前端创建页不出现真实世界时间默认值。
- “添加商品”弹窗从商品代金券专属接口读取可选商品。
- 未选择商品时禁止提交。
- 选择商品后可提交创建商品代金券，并在数据库写入活动表和适用商品表。
- 创建成功返回 `/shopee/marketing/vouchers`，列表可展示“商品代金券”和指定商品数量。
- 同一对局同一卖家的代金券代码不可重复。
- Redis 创建限流生效，创建后列表缓存失效。
- 新表和新增字段均有表注释/字段注释。
- 不改变订单模拟下单概率和营销归因逻辑。

## 11. 验证建议

- 后端：
  - `python -m py_compile backend/apps/api-gateway/app/models.py backend/apps/api-gateway/app/db.py backend/apps/api-gateway/app/api/routes/shopee.py`
  - 手动请求 bootstrap，确认返回时间为游戏时间字符串。
  - 手动创建商品代金券，检查 `shopee_product_voucher_campaigns` 与 `shopee_product_voucher_items`。
- 前端：
  - `npm run build --prefix frontend`
  - LSP 检查 `ProductVoucherCreateView.tsx` 与 `ShopeePage.tsx`。
  - 浏览器访问 `/shopee/marketing/vouchers/product-create`，确认默认时间、选品弹窗和提交错误提示。
- 数据库：
  - 检查新表存在，表注释和字段注释完整。
- Redis：
  - 创建前后检查 bootstrap/list/code-check 缓存命中和失效。

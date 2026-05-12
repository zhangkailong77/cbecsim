# 38-Shopee 专属代金券创建前后端数据库 Redis 实现设计

> 创建日期：2026-05-07  
> 状态：设计完成，待实现

## 1. 目标

为 Shopee 营销中心代金券模块接入“专属代金券”创建能力，使 `/shopee/marketing/vouchers/private-create` 页面从前端静态表单升级为可读取初始化数据、校验输入、选择适用商品、提交创建并落库的完整流程。

本期重点是接口、数据库和 Redis 数据闭环：

- 前端样式和布局沿用用户已手动调整后的 `PrivateVoucherCreateView.tsx`，不重做视觉结构。
- 代金券使用期限必须由后端按对局游戏时间初始化，前端日期选择器展示和提交游戏时间，不展示真实世界时间。
- “添加商品”区域参考已完成的商品代金券创建页：复用商品代金券的添加商品按钮样式、商品选择弹窗、已选商品表格和前端接口交互模式。
- 前端仅补接口对接、受控字段初始化、代码校验、商品选择数据来源、表单校验和创建提交。
- 后端新增专属代金券创建页 bootstrap、可选商品、创建提交接口，并扩展代金券列表与代码检查兼容 `private_voucher`。
- 数据库新增专属代金券活动表与适用商品表，保存影响经营结果的代金券规则、适用范围和商品快照。
- Redis 用于创建页 bootstrap、商品选择列表、代码检查、代金券列表缓存、创建限流和创建后缓存失效。
- 买家群体定向、买家主动领券、订单模拟命中与归因先预留字段，不在本期实现。

## 2. 范围与非范围

### 2.1 本期范围

- 专属代金券类型：实现 `private_voucher`。
- 前端 `/shopee/marketing/vouchers/private-create` 接口对接：
  - 初始化表单默认值。
  - 代金券使用期限按游戏时间展示与提交。
  - 校验代金券代码可用性。
  - 支持适用商品选择：全部商品 / 指定商品。
  - 指定商品模式复用商品代金券已实现的商品选择弹窗、商品表格和提交展开逻辑。
  - 提交创建专属代金券。
  - 创建成功后返回 `/shopee/marketing/vouchers`。
- 后端接口：
  - 专属代金券创建页 bootstrap。
  - 专属代金券可选商品列表。
  - 代金券代码可用性检查支持 `private_voucher`。
  - 创建专属代金券。
  - 代金券列表接口兼容返回专属代金券。
- 数据库：
  - 新增专属代金券活动表。
  - 新增专属代金券适用商品表。
  - 补齐表注释和字段注释。
- Redis：
  - 创建页 bootstrap 缓存。
  - 可选商品列表缓存。
  - 代码检查缓存。
  - 代金券列表缓存失效。
  - 创建接口频率限制。

### 2.2 非范围

- 不重做专属代金券创建页前端布局、颜色、间距和基础表单视觉。
- 不接入真实 Shopee 平台 API。
- 不实现买家端领券页面、买家主动领取、站内信/聊天推送或外部分享链路。
- 不实现买家分组、人群包、指定买家账号导入；本期 `audience_scope` 固定为预留口径。
- 不在本期改订单模拟下单概率、代金券命中、价格改写或订单归因；仅预留后续接入口径。
- 不实现专属代金券详情、编辑、复制、停止、删除和数据页。
- 不实现上传商品列表的真实解析流程；上传 Tab 如复用弹窗，本期保留界面占位。

## 3. 游戏时间口径

专属代金券所有面向前端的时间字段必须统一使用游戏时间：

| 场景 | 口径 |
| --- | --- |
| 创建页默认时间 | 后端根据当前对局 tick 返回游戏时间字符串 |
| 前端日期选择器展示 | 展示游戏时间，不展示真实世界时间 |
| 前端提交 `start_at/end_at` | 提交 `YYYY-MM-DDTHH:mm` 游戏时间字符串 |
| 后端解析 | 使用现有游戏时间解析函数映射为系统时间落库 |
| 后端返回列表/详情 | 将落库系统时间反向格式化为游戏时间 |
| 状态计算 | 基于当前游戏 tick 与代金券游戏时间比较 |
| Redis 缓存 payload | 缓存对外返回的游戏时间字符串，不缓存真实时间给前端展示 |

建议复用现有代金券/折扣时间转换函数：

- `_format_discount_game_datetime(value, run=run)`：系统时间 -> 游戏时间字符串。
- `_parse_discount_game_datetime(raw_value, run=run)`：游戏时间字符串 -> 系统时间。
- `_resolve_game_tick(db, run_id, user_id)`：解析当前对局游戏 tick。

前端要求：

- `PrivateVoucherCreateView.tsx` 的 `DateTimePicker` 初始值必须来自 bootstrap 返回的 `form.start_at` 和 `form.end_at`。
- 不允许在空值时让 `DateTimePicker` 回落到浏览器真实当前时间作为业务默认值。
- 若后端未返回时间，应显示空值并阻止提交，提示“创建页初始化失败”或“请选择代金券使用期限”。

## 4. 业务规则

### 4.1 专属代金券定义

专属代金券用于卖家通过代金券代码定向分享给特定买家或私域渠道。买家获得代码后可在满足条件的订单中使用。

| 字段 | 规则 |
| --- | --- |
| 代金券类型 | 固定为 `private_voucher` |
| 代金券名称 | 卖家可见，买家不展示，最多 100 字符 |
| 代金券代码 | `HOME` 前缀 + 卖家输入后缀；后缀仅允许 `A-Z`、`0-9`，最多 5 字符 |
| 使用期限 | `start_at < end_at`，按游戏时间显示、提交、解析和校验 |
| 奖励类型 | V1 固定 `discount` |
| 折扣类型 | 支持 `fixed_amount` 和 `percent` |
| 固定金额 | `discount_type=fixed_amount` 时必填且大于 0 |
| 百分比 | `discount_type=percent` 时必填，建议范围 `1-100` |
| 最大折扣金额 | 百分比模式支持 `set_amount/no_limit`；`set_amount` 时金额必填且大于 0 |
| 最低消费金额 | 必填且大于 0；固定金额模式下建议 `min_spend_amount >= discount_amount` |
| 使用数量 | 所有买家可使用总代金券数量，必须为正整数 |
| 每位买家最大发放量 | 必须为正整数，且不超过使用数量 |
| 展示设置 | V1 固定 `code_only`，前端文案为“通过代金券代码分享” |
| 适用商品 | 支持 `all_products` / `selected_products`；指定商品模式至少选择 1 个商品 |
| 买家定向 | V1 预留 `audience_scope=private_code`，不实现买家名单 |

### 4.2 适用商品规则

- `applicable_scope=all_products`：专属代金券适用于当前卖家同一 `run_id/user_id` 下所有可售商品，创建时不写商品明细。
- `applicable_scope=selected_products`：必须选择至少 1 个商品，最多建议 100 个商品。
- 可选商品来自当前卖家同一 `run_id/user_id` 下已上架且可售的 Shopee 商品。
- 商品库存必须大于 0，售价必须大于 0。
- 已删除、下架、无库存、无有效售价的商品不可选。
- 指定商品弹窗样式和行为参考商品代金券：
  - 商品行展示主图、商品名称、ID/变体数、原价、库存。
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

- 命中条件：订单属于同一 `run_id/user_id` 店铺，订单游戏时间在代金券使用期限内，买家获得该专属代码，订单商品命中适用范围，订单金额满足 `min_spend_amount`。
- `all_products`：订单内所有可售商品小计可参与优惠。
- `selected_products`：仅命中适用商品明细的商品小计参与优惠。
- 优惠计算：
  - 固定金额：`discount_amount = min(voucher_amount, eligible_subtotal)`。
  - 百分比：`discount_amount = eligible_subtotal * discount_percent / 100`；若 `max_discount_type=set_amount`，再取 `min(discount_amount, max_discount_amount)`。
- 数量扣减：订单成功归因后增加 `used_count`。
- 买家限用：同一买家对同一专属代金券累计使用次数不超过 `per_buyer_limit`。
- 归因字段：后续订单级写入 `marketing_campaign_type='private_voucher'`、`marketing_campaign_id`、`marketing_campaign_name_snapshot`。

## 5. 数据模型设计

### 5.1 新增 ORM：`ShopeePrivateVoucherCampaign`

建议新增表：`shopee_private_voucher_campaigns`。

> 数据库 Schema Rules 要求：新建表必须添加表注释，新增字段必须添加字段注释。

| 字段 | 类型 | 约束 | 注释 |
| --- | --- | --- | --- |
| `id` | Integer | PK | 专属代金券活动 ID |
| `run_id` | Integer | FK `game_runs.id`, index | 所属对局 ID |
| `user_id` | Integer | FK `users.id`, index | 所属卖家用户 ID |
| `voucher_type` | String(32) | not null, default `private_voucher` | 代金券类型，V1 固定专属代金券 |
| `voucher_name` | String(255) | not null | 卖家可见的代金券名称 |
| `voucher_code` | String(32) | not null | 完整代金券代码，如 `HOMEVIP01` |
| `code_prefix` | String(16) | not null, default `HOME` | 代金券代码前缀 |
| `code_suffix` | String(16) | not null | 卖家输入的代码后缀 |
| `status` | String(32) | not null, index | 状态：upcoming/ongoing/sold_out/ended/stopped |
| `start_at` | DateTime(timezone=True) | not null, index | 代金券可使用开始游戏时间映射后的系统时间 |
| `end_at` | DateTime(timezone=True) | not null, index | 代金券可使用结束游戏时间映射后的系统时间 |
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
| `display_type` | String(32) | not null, default `code_only` | 展示方式，专属代金券 V1 固定代码分享 |
| `applicable_scope` | String(32) | not null, default `all_products` | 适用范围：all_products/selected_products |
| `selected_product_count` | Integer | not null, default 0 | 已选择适用商品数量 |
| `audience_scope` | String(32) | not null, default `private_code` | 买家定向范围，V1 固定私有码口径 |
| `audience_payload` | Text | nullable | 买家定向配置 JSON，V1 预留为空 |
| `sales_amount` | Float | not null, default 0 | 代金券归因销售额，单位为店铺币种 |
| `order_count` | Integer | not null, default 0 | 代金券归因订单数 |
| `buyer_count` | Integer | not null, default 0 | 使用代金券买家数 |
| `created_at` | DateTime(timezone=True) | not null | 创建时间 |
| `updated_at` | DateTime(timezone=True) | not null | 更新时间 |

建议索引：

```python
Index("ix_shopee_private_vouchers_run_user_status", "run_id", "user_id", "status")
Index("ix_shopee_private_vouchers_run_user_time", "run_id", "user_id", "start_at", "end_at")
Index("ix_shopee_private_vouchers_run_user_code", "run_id", "user_id", "voucher_code", unique=True)
```

### 5.2 新增 ORM：`ShopeePrivateVoucherItem`

建议新增表：`shopee_private_voucher_items`。

| 字段 | 类型 | 约束 | 注释 |
| --- | --- | --- | --- |
| `id` | Integer | PK | 专属代金券适用商品记录 ID |
| `campaign_id` | Integer | FK `shopee_private_voucher_campaigns.id`, index | 专属代金券活动 ID |
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
UniqueConstraint("campaign_id", "listing_id", "variant_id", name="uq_shopee_private_voucher_item_variant")
Index("ix_shopee_private_voucher_items_campaign", "campaign_id")
Index("ix_shopee_private_voucher_items_listing", "run_id", "user_id", "listing_id")
Index("ix_shopee_private_voucher_items_product", "product_id")
```

说明：字段命名应直接使用当前商品代金券已验证可落库的 `stock_snapshot`，不要再引入 `stock_available_snapshot`。

## 6. 后端接口设计

接口文件沿用：`backend/apps/api-gateway/app/api/routes/shopee.py`。

### 6.1 创建页 Bootstrap

```http
GET /shopee/runs/{run_id}/marketing/vouchers/private-create/bootstrap
```

用途：为专属代金券创建页提供游戏时间默认值、表单规则、只读状态和商品选择配置。

响应示例：

```json
{
  "meta": {
    "run_id": 1,
    "user_id": 2,
    "voucher_type": "private_voucher",
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
    "reward_type": "discount",
    "discount_type": "fixed_amount",
    "discount_amount": null,
    "discount_percent": null,
    "max_discount_type": "set_amount",
    "max_discount_amount": null,
    "min_spend_amount": null,
    "usage_limit": null,
    "per_buyer_limit": 1,
    "display_type": "code_only",
    "applicable_scope": "all_products",
    "audience_scope": "private_code"
  },
  "rules": {
    "code_suffix_pattern": "^[A-Z0-9]{1,5}$",
    "voucher_name_max_length": 100,
    "min_usage_limit": 1,
    "min_per_buyer_limit": 1,
    "max_selected_products": 100
  },
  "product_picker": {
    "enabled": true,
    "default_page_size": 20,
    "search_fields": ["product_name", "product_id"],
    "available_only_default": true
  },
  "selected_products": []
}
```

后端处理：

- 校验当前用户可访问 `run_id`。
- 读取当前对局 tick，生成游戏时间默认 `start_at/end_at`。
- 历史对局或只读模式返回 `read_only=true`。
- 返回值中的所有时间均为游戏时间字符串。
- 可缓存到 Redis，缓存 key 需包含 `run_id/user_id`。

### 6.2 可选商品列表

```http
GET /shopee/runs/{run_id}/marketing/vouchers/private-create/eligible-products?keyword=&search_field=product_name&category=all&available_only=true&page=1&page_size=20
```

用途：为“指定商品”弹窗加载可选商品。接口响应结构建议与商品代金券保持一致，便于前端复用弹窗组件和状态逻辑。

响应示例：

```json
{
  "items": [
    {
      "listing_id": 101,
      "variant_id": null,
      "variant_ids": [1001, 1002],
      "product_name": "Women Shoulder Bag",
      "variant_name": "",
      "sku": "BAG-001",
      "image_url": "https://.../image.jpg",
      "category_key": "bags",
      "category_label": "女包",
      "original_price": 29.9,
      "price_range_label": "RM 29.90 - RM 35.90",
      "stock_available": 120,
      "likes_count": 0,
      "conflict": false,
      "conflict_reason": null
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

规则：

- 查询当前 `run_id/user_id` 下 `ShopeeListing`。
- 仅返回已上架、可售、有库存、有有效价格的商品。
- 多变体商品返回一行主商品，`variant_ids` 包含全部可售变体。
- 单规格商品可返回 `variant_id=null`、`variant_ids=[]`。
- `keyword` 支持商品名称和商品 ID 搜索。
- `category` 支持沿用商品代金券弹窗的分类筛选。
- `conflict` 本期默认 false；后续可用于提示正在参与互斥活动。

### 6.3 代金券代码检查

沿用统一接口并扩展 `voucher_type`：

```http
GET /shopee/runs/{run_id}/marketing/vouchers/code/check?voucher_type=private_voucher&code_suffix=VIP01
```

规则：

- `voucher_type` 支持 `shop_voucher/product_voucher/private_voucher`。
- `code_suffix` 强制大写，匹配 `^[A-Z0-9]{1,5}$`。
- 完整代码为 `HOME + code_suffix`。
- 代码唯一性应按同一 `run_id/user_id` 在所有代金券表中共享检查，避免店铺代金券、商品代金券和专属代金券代码重复。
- Redis 可缓存短 TTL 结果，创建成功后清理代码检查缓存。

响应示例：

```json
{
  "available": true,
  "message": "代金券代码可用"
}
```

### 6.4 创建专属代金券

```http
POST /shopee/runs/{run_id}/marketing/vouchers/private-campaigns
```

请求示例：

```json
{
  "voucher_name": "VIP Buyer Voucher",
  "code_suffix": "VIP01",
  "start_at": "2026-06-05T08:32",
  "end_at": "2026-06-05T09:32",
  "reward_type": "discount",
  "discount_type": "fixed_amount",
  "discount_amount": 5,
  "discount_percent": null,
  "max_discount_type": "set_amount",
  "max_discount_amount": null,
  "min_spend_amount": 30,
  "usage_limit": 100,
  "per_buyer_limit": 1,
  "display_type": "code_only",
  "applicable_scope": "selected_products",
  "selected_products": [
    { "listing_id": 101, "variant_id": 1001 },
    { "listing_id": 101, "variant_id": 1002 }
  ]
}
```

后端创建步骤：

1. 校验 `run_id/user_id` 权限与只读状态。
2. 校验代码后缀格式，拼接完整 `voucher_code`。
3. 检查 `voucher_code` 在店铺/商品/专属代金券中唯一。
4. 使用游戏时间解析函数解析 `start_at/end_at`。
5. 校验奖励设置、最低消费、使用数量、每买家限用。
6. 校验 `applicable_scope`：
   - `all_products`：忽略 `selected_products`，`selected_product_count=0`。
   - `selected_products`：必须有商品，最多 100 个；后端重新读取商品并生成快照，不能信任前端价格/库存。
7. 插入 `shopee_private_voucher_campaigns`。
8. 指定商品模式下批量插入 `shopee_private_voucher_items`。
9. 提交事务后清理代金券列表、bootstrap、可选商品和代码检查缓存。
10. 返回创建成功结果。

响应示例：

```json
{
  "id": 501,
  "voucher_type": "private_voucher",
  "voucher_code": "HOMEVIP01",
  "status": "upcoming",
  "message": "专属代金券创建成功"
}
```

### 6.5 代金券列表兼容

现有列表接口：

```http
GET /shopee/runs/{run_id}/marketing/vouchers
```

需合并返回专属代金券：

- `voucher_type=private_voucher`。
- 名称、代码、状态、使用期限、使用量、销售额、订单数、买家数与现有卡片字段保持一致。
- `display_type` 对外展示为“通过代金券代码分享”。
- `applicable_scope=all_products` 时显示“全部商品”。
- `applicable_scope=selected_products` 时显示选中商品数量。
- 时间字段返回游戏时间字符串。

## 7. 前端对接设计

文件：`frontend/src/modules/shopee/views/PrivateVoucherCreateView.tsx`。

### 7.1 保留现有布局，只补数据逻辑

当前页面已包含：

- 基础信息：代金券类型、名称、代码、使用期限。
- 奖励设置：折扣类型、金额、最大折扣、最低消费、使用数量、每位买家最大发放量。
- 展示与适用商品：代码分享、全部商品/指定商品。
- 底部取消/确认操作栏。

实现时不重做这些布局，只补：

- `runId` props，与商品代金券创建页一致。
- `API_BASE_URL`、`ACCESS_TOKEN_KEY`。
- bootstrap 初始化。
- code check。
- 商品 picker 状态与弹窗。
- 表单校验和提交。
- loading/error/saving/readOnly 状态。

### 7.2 游戏时间日期选择器

- 页面加载后调用 bootstrap，使用 `form.start_at/form.end_at` 设置：
  - `voucherStartAt`
  - `voucherEndAt`
- `DateTimePicker` 继续复用现有组件：
  - 开始时间 `maxValue={voucherEndAt || undefined}`。
  - 结束时间 `minValue={voucherStartAt || undefined}`。
- 不要使用 `new Date()` 生成业务默认值。
- 若 `voucherStartAt` 或 `voucherEndAt` 为空，不允许提交。

### 7.3 添加商品样式与弹窗复用

指定商品模式下的 UI 参考商品代金券创建页已实现效果：

- 未选择商品时：显示“添加商品”按钮。
- 已选择商品时：显示选中数量 + 右侧“添加商品”按钮。
- 下方显示已选商品表格：
  - 商品主图。
  - 商品名称。
  - ID/变体数。
  - 原价。
  - 库存。
  - 删除操作。
- 商品选择弹窗参考 `ProductVoucherCreateView.tsx`：
  - Tab：选择商品 / 上传商品列表。
  - 分类筛选。
  - 搜索字段：商品名称 / 商品 ID。
  - 仅显示可参与活动商品。
  - 商品表格、空状态、确认/取消。
- 前端可先复制商品代金券当前逻辑；后续再抽成共享组件，不在本期强制重构。

### 7.4 前端接口调用

| 场景 | 方法 | URL |
| --- | --- | --- |
| 初始化 | GET | `/shopee/runs/${runId}/marketing/vouchers/private-create/bootstrap` |
| 代码检查 | GET | `/shopee/runs/${runId}/marketing/vouchers/code/check?voucher_type=private_voucher&code_suffix=${suffix}` |
| 商品列表 | GET | `/shopee/runs/${runId}/marketing/vouchers/private-create/eligible-products?...` |
| 创建提交 | POST | `/shopee/runs/${runId}/marketing/vouchers/private-campaigns` |

### 7.5 前端提交 payload

- `applicableProductType === 'all'`：
  - `applicable_scope='all_products'`
  - `selected_products=[]`
- `applicableProductType === 'specific'`：
  - `applicable_scope='selected_products'`
  - `selected_products` 使用商品代金券同样的展开逻辑：

```ts
selected_products: selectedProducts.flatMap((item) => {
  if (item.variant_ids?.length) {
    return item.variant_ids.map((variantId) => ({ listing_id: item.listing_id, variant_id: variantId }));
  }
  return [{ listing_id: item.listing_id, variant_id: item.variant_id }];
})
```

### 7.6 前端校验

提交前校验：

- `runId` 存在。
- 非只读模式。
- 代金券名称非空且不超过 100 字符。
- 代码后缀匹配 `^[A-Z0-9]{1,5}$` 且代码检查可用。
- `voucherStartAt` 与 `voucherEndAt` 均非空且开始早于结束。
- 固定金额模式：`discount_amount > 0`。
- 百分比模式：`discount_percent > 0`，且 `<= 100`。
- 百分比最大折扣 `set_amount` 时 `max_discount_amount > 0`。
- `min_spend_amount > 0`。
- `usage_limit > 0`。
- `per_buyer_limit > 0` 且不超过 `usage_limit`。
- 指定商品模式至少选择 1 个商品。

## 8. Redis 设计

建议沿用现有 `REDIS_PREFIX` 与代金券缓存封装。

| 用途 | Key 建议 | TTL |
| --- | --- | --- |
| 创建页 bootstrap | `{prefix}:cache:shopee:private-voucher:create-bootstrap:{run_id}:{user_id}` | 60s |
| 可选商品列表 | `{prefix}:cache:shopee:private-voucher:eligible-products:{run_id}:{user_id}:{digest}` | 60s |
| 代码检查 | `{prefix}:cache:shopee:voucher-code-check:{run_id}:{user_id}:private_voucher:{code_suffix}` | 30s |
| 代金券列表 | 沿用现有 voucher list key | 30-60s |
| 创建限流 | `{prefix}:rate:shopee:private-voucher:create:{run_id}:{user_id}` | 60s |

创建成功后清理：

- 专属代金券 bootstrap 缓存。
- 专属代金券 eligible-products 缓存。
- 统一 voucher list 缓存。
- voucher code check 缓存。

创建接口频率建议：

- 同一 `run_id/user_id` 每 60 秒最多 10 次创建请求。
- 超限返回 429，提示“操作过于频繁，请稍后再试”。

## 9. 验收标准

### 9.1 前端验收

- 从代金券页点击“专属代金券 > 创建”进入 `/shopee/marketing/vouchers/private-create`。
- 创建页初始化后，使用期限显示后端返回的游戏时间，不显示真实世界当前时间。
- 修改使用期限后，提交 payload 中仍为 `YYYY-MM-DDTHH:mm` 游戏时间字符串。
- 代码输入自动大写并过滤非 `A-Z0-9` 字符，最多 5 位。
- 代码检查可提示可用/不可用。
- 选择“全部商品”时可直接创建，不要求添加商品。
- 选择“指定商品”时显示商品代金券同款添加商品按钮、弹窗和已选商品表格。
- 多变体商品添加后展示主商品行，提交时展开为全部可售变体。
- 创建成功后返回代金券列表，并能看到专属代金券记录。
- 历史对局回溯模式下表单和创建按钮不可操作。

### 9.2 后端验收

- bootstrap 接口返回游戏时间默认值、规则和商品选择配置。
- eligible-products 接口仅返回当前卖家可售商品，并支持关键词、搜索字段、分类和分页。
- code/check 支持 `private_voucher`，并与店铺/商品代金券共享唯一性检查。
- 创建接口能落库 `shopee_private_voucher_campaigns`。
- 指定商品模式能落库 `shopee_private_voucher_items` 快照。
- 全部商品模式不写商品明细，`selected_product_count=0`。
- 所有新增表和字段都有表注释/字段注释。
- 创建成功后相关 Redis 缓存失效。

### 9.3 验证命令

建议实现后至少执行：

```bash
python -m py_compile backend/apps/api-gateway/app/models.py backend/apps/api-gateway/app/db.py backend/apps/api-gateway/app/api/routes/shopee.py
npm run build --prefix frontend
```

并通过浏览器手工联调：

1. 打开 `/shopee/marketing/vouchers/private-create`。
2. 确认时间为游戏时间。
3. 创建全部商品专属代金券。
4. 创建指定商品专属代金券。
5. 回到 `/shopee/marketing/vouchers` 确认列表展示。

## 10. 后续扩展

- 专属买家名单、人群包、买家分层定向。
- 买家领取/使用记录表。
- 专属代金券详情、编辑、停止、复制、删除。
- 上传商品列表真实解析。
- 订单模拟命中专属代金券、优惠金额改写和销售归因。
- 与聊天、直播、关注礼等私域渠道联动。
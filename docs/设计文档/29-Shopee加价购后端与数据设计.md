# 29-Shopee加价购后端与数据设计

> 创建日期：2026-04-28  
> 状态：设计完成，待实现

## 1. 目标

在 Shopee `营销中心 -> 折扣 -> 创建加价购` 链路中，补齐加价购（Add-on Deal）与满额赠（Gift with Purchase）的后端逻辑、数据库结构、Redis 缓存和订单模拟影响口径。

本设计仅覆盖后端、数据库、Redis 与经营模拟，不调整当前前端页面样式。

## 2. 范围与非范围

### 2.1 本期范围（V1）

- 支持两类促销：
  - `add_on`：加价购，买主商品后可用优惠加价购买指定加购商品。
  - `gift`：满额赠，订单达到最低消费门槛后赠送指定商品。
- 提供创建页需要的后端接口：
  - bootstrap 初始化。
  - 主商品候选列表。
  - 加购/赠品候选列表。
  - 草稿保存与回填。
  - 正式活动创建。
  - 活动详情回填。
- 新增数据库表：
  - 活动主表。
  - 主商品表。
  - 加购/赠品商品表。
  - 草稿主表。
  - 草稿主商品表。
  - 草稿加购/赠品商品表。
- Redis 支持：
  - 创建页 bootstrap 缓存。
  - 商品选择器缓存。
  - 草稿缓存。
  - 活动详情缓存。
  - 创建后折扣首页、订单模拟营销缓存失效。
- 订单模拟接入：
  - `add_on` 影响订单明细数量、成交价与营销归因。
  - `gift` 在满足门槛时追加赠品明细，赠品金额为 0。
  - 普通订单、单品折扣、套餐优惠原有链路不被替换。

### 2.2 非范围（V1 不做）

- 不实现前端视觉继续优化。
- 不实现复杂营销叠加引擎，例如券、限时抢购、跨店满减的完整优先级。
- 不实现买家端真实页面，只服务当前卖家端创建、列表和订单模拟。
- 不实现 Excel/CSV 批量导入商品。
- 不实现跨站点加价购。

## 3. 业务概念

| 概念 | 说明 |
|---|---|
| 主商品 | 买家必须先购买的商品池。只有订单命中主商品，才可能触发加价购。 |
| 加购商品 | `add_on` 类型下，买家购买主商品后可加价购买的商品。 |
| 赠品商品 | `gift` 类型下，订单金额达到门槛后免费赠送的商品。 |
| 加价购价 | 加购商品在该活动下的成交单价。 |
| 最低消费门槛 | `gift` 类型下订单商品金额达到该值后可获得赠品。 |
| 加购限购数量 | 每笔订单或每位买家在该活动下可购买的加购商品数量上限。首版按每笔订单限制。 |

## 4. 业务规则

### 4.1 活动类型

- `add_on`：加价购。
- `gift`：满额赠。

两者共用活动主表，通过 `promotion_type` 区分。

### 4.2 基础校验

- 活动名称不能为空，长度 `<= 25`。
- 开始时间必须早于结束时间。
- 结束时间必须晚于开始时间至少 1 小时。
- 活动保存成功后，后续编辑只允许缩短活动时间，不允许延长（V1 可先在设计中预留，编辑期实现）。
- 活动状态按当前游戏时间解析为：`draft / upcoming / ongoing / ended / disabled`。
- 历史回溯只读模式下禁止创建、保存草稿、编辑、停用。

### 4.3 主商品规则

- 至少选择 1 个主商品。
- 同一个活动最多选择 100 个主商品。
- 主商品必须满足：
  - 属于当前 `run_id` 与当前用户。
  - 上架状态为 `live`。
  - 有可售库存。
  - 价格有效且大于 0。
- 同一 SKU 在相同时间段内不得同时作为两个 ongoing/upcoming 加价购活动的主商品。
- 主商品可同时存在单品折扣，但价格口径需按营销优先级统一计算，见第 9 节。

### 4.4 加价购商品规则（`add_on`）

- 至少选择 1 个加购商品。
- 同一个活动最多选择 100 个加购商品。
- 加购商品必须满足：
  - 属于当前 `run_id` 与当前用户。
  - 上架状态为 `live`。
  - 有可售库存。
  - 原价有效且大于 0。
  - 加价购价大于 0，且必须小于原价。
- 加购限购数量：
  - 必填。
  - 正整数。
  - 范围：`1 ~ 99`。
  - V1 表示每笔订单最多可购买的加购商品总件数。

### 4.5 满额赠规则（`gift`）

- 至少选择 1 个赠品商品。
- 最低消费门槛必填。
- 门槛金额必须大于 0。
- 赠品数量上限：V1 每笔订单最多赠送 1 件；后续可扩展为多件赠品或按门槛阶梯赠送。
- 赠品商品需有可售库存；赠品出库按 0 元订单明细记录，仍占用库存。

## 5. 后端接口设计（FastAPI）

统一延续现有风格：`/shopee/runs/{run_id}/...`

### 5.1 创建页 bootstrap

`GET /shopee/runs/{run_id}/marketing/add-on/create/bootstrap`

参数：
- `promotion_type=add_on|gift`，默认 `add_on`。
- `draft_id` 可选，用于草稿回填。
- `source_campaign_id` 可选，用于复制活动。

返回：
```json
{
  "meta": {
    "run_id": 6,
    "user_id": 1,
    "promotion_type": "add_on",
    "read_only": false,
    "current_tick": "2026-04-28T10:00:00"
  },
  "form": {
    "campaign_name": "",
    "name_max_length": 25,
    "start_at": "2026-04-28T10:00",
    "end_at": "2026-04-28T11:00",
    "addon_purchase_limit": 1,
    "gift_min_spend": null
  },
  "rules": {
    "promotion_types": ["add_on", "gift"],
    "main_product_limit": 100,
    "addon_product_limit": 100,
    "addon_purchase_limit_range": [1, 99],
    "min_duration_minutes": 60
  },
  "selected_main_products": [],
  "selected_reward_products": [],
  "product_picker": {
    "default_page_size": 20
  }
}
```

### 5.2 主商品候选列表

`GET /shopee/runs/{run_id}/marketing/add-on/eligible-main-products`

参数：
- `keyword`
- `search_field=name|product_id|sku`
- `category`
- `page`
- `page_size`
- `exclude_campaign_id` 可选，编辑时排除自身冲突。

返回字段：
- `listing_id`
- `variant_id`
- `product_id`
- `product_name`
- `variant_name`
- `sku`
- `image_url`
- `original_price`
- `stock_available`
- `status`
- `conflict`
- `conflict_reason`

### 5.3 加购/赠品候选列表

`GET /shopee/runs/{run_id}/marketing/add-on/eligible-reward-products`

参数与主商品候选列表一致，额外支持：
- `promotion_type=add_on|gift`

返回字段在主商品基础上增加：
- `suggested_addon_price`：建议加价购价，仅 `add_on` 返回。
- `can_be_gift`：是否允许作为赠品，仅 `gift` 返回。

### 5.4 草稿保存

`POST /shopee/runs/{run_id}/marketing/add-on/drafts`

入参：
```json
{
  "draft_id": null,
  "promotion_type": "add_on",
  "campaign_name": "加价购活动",
  "start_at": "2026-04-28T10:00",
  "end_at": "2026-04-28T11:00",
  "addon_purchase_limit": 2,
  "gift_min_spend": null,
  "main_products": [
    {"listing_id": 1, "variant_id": null}
  ],
  "reward_products": [
    {"listing_id": 2, "variant_id": null, "addon_price": 9.9, "reward_qty": 1}
  ]
}
```

返回：
- `draft_id`
- `saved_at`

### 5.5 草稿详情

`GET /shopee/runs/{run_id}/marketing/add-on/drafts/{draft_id}`

用途：回填创建页。

### 5.6 创建正式活动

`POST /shopee/runs/{run_id}/marketing/add-on/campaigns`

后端职责：
1. 校验基础信息。
2. 将游戏时间转换为真实时间存储。
3. 校验主商品、加购/赠品商品准入。
4. 校验活动时间冲突。
5. 保存活动主表、主商品表、加购/赠品商品表。
6. 写入商品快照。
7. 失效折扣首页、活动详情、订单模拟营销映射相关缓存。

返回：
- `campaign_id`
- `campaign_name`
- `promotion_type`
- `status`
- `start_at`
- `end_at`

### 5.7 活动详情

`GET /shopee/runs/{run_id}/marketing/add-on/campaigns/{campaign_id}`

用途：详情查看、复制活动、后续编辑回填。

### 5.8 活动停用

`POST /shopee/runs/{run_id}/marketing/add-on/campaigns/{campaign_id}/disable`

用途：手动停用未结束活动。

## 6. 数据模型设计

> 仓库规则：新表必须添加 table comment；新增字段必须添加 column comment。以下字段在 SQLAlchemy model、初始化脚本或迁移脚本中都必须同步维护注释。

### 6.1 活动主表：`shopee_addon_campaigns`

用途：存储加价购/满额赠活动主记录。

| 字段 | 类型建议 | 说明 |
|---|---|---|
| `id` | bigint PK | 活动主键。 |
| `run_id` | bigint not null | 对局 ID。 |
| `user_id` | bigint not null | 用户 ID。 |
| `campaign_code` | varchar(64) | 活动编码，用于展示和排查。 |
| `campaign_name` | varchar(64) not null | 活动名称，仅卖家可见。 |
| `promotion_type` | varchar(16) not null | `add_on` 加价购；`gift` 满额赠。 |
| `campaign_status` | varchar(16) not null | `draft/scheduled/ongoing/ended/disabled`。 |
| `start_at` | datetime not null | 活动真实开始时间，由游戏时间转换。 |
| `end_at` | datetime not null | 活动真实结束时间，由游戏时间转换。 |
| `addon_purchase_limit` | integer null | 加价购每笔订单限购数量，仅 `add_on` 有效。 |
| `gift_min_spend` | numeric(12,2) null | 满额赠最低消费门槛，仅 `gift` 有效。 |
| `currency` | varchar(8) not null | 币种，默认 `RM`。 |
| `created_at` | datetime not null | 创建时间。 |
| `updated_at` | datetime not null | 更新时间。 |

索引建议：
- `(run_id, user_id, campaign_status)`
- `(run_id, user_id, start_at, end_at)`
- `(run_id, promotion_type, start_at, end_at)`

### 6.2 主商品表：`shopee_addon_campaign_main_items`

用途：记录触发加价购/满额赠的主商品池。

| 字段 | 类型建议 | 说明 |
|---|---|---|
| `id` | bigint PK | 主键。 |
| `campaign_id` | bigint not null | 关联 `shopee_addon_campaigns.id`。 |
| `run_id` | bigint not null | 对局 ID，便于查询隔离。 |
| `listing_id` | bigint not null | Shopee 上架商品 ID。 |
| `variant_id` | bigint null | SKU/规格 ID，无规格商品为空。 |
| `product_id` | bigint null | 源商品 ID。 |
| `product_name_snapshot` | varchar(255) not null | 活动创建时商品名称快照。 |
| `variant_name_snapshot` | varchar(255) null | 活动创建时规格名称快照。 |
| `sku_snapshot` | varchar(128) null | 活动创建时 SKU 快照。 |
| `image_url_snapshot` | text null | 商品图片快照。 |
| `original_price_snapshot` | numeric(12,2) not null | 活动创建时原价快照。 |
| `stock_snapshot` | integer not null | 活动创建时可售库存快照。 |
| `sort_order` | integer not null | 前端展示顺序。 |
| `created_at` | datetime not null | 创建时间。 |

约束建议：
- `unique(campaign_id, listing_id, variant_id)`。

### 6.3 加购/赠品商品表：`shopee_addon_campaign_reward_items`

用途：记录加价购商品或满额赠赠品商品。

| 字段 | 类型建议 | 说明 |
|---|---|---|
| `id` | bigint PK | 主键。 |
| `campaign_id` | bigint not null | 关联 `shopee_addon_campaigns.id`。 |
| `run_id` | bigint not null | 对局 ID。 |
| `listing_id` | bigint not null | 加购/赠品上架商品 ID。 |
| `variant_id` | bigint null | SKU/规格 ID。 |
| `product_id` | bigint null | 源商品 ID。 |
| `product_name_snapshot` | varchar(255) not null | 商品名称快照。 |
| `variant_name_snapshot` | varchar(255) null | 规格名称快照。 |
| `sku_snapshot` | varchar(128) null | SKU 快照。 |
| `image_url_snapshot` | text null | 商品图片快照。 |
| `original_price_snapshot` | numeric(12,2) not null | 原价快照。 |
| `addon_price` | numeric(12,2) null | 加价购成交价，仅 `add_on` 有效。 |
| `reward_qty` | integer not null | 赠送/加购数量，V1 默认为 1。 |
| `stock_snapshot` | integer not null | 活动创建时可售库存快照。 |
| `sort_order` | integer not null | 前端展示顺序。 |
| `created_at` | datetime not null | 创建时间。 |

约束建议：
- `unique(campaign_id, listing_id, variant_id)`。
- `addon_price > 0` 仅 `promotion_type=add_on` 时校验。

### 6.4 草稿主表：`shopee_addon_drafts`

用途：保存加价购/满额赠创建页未提交草稿。

字段与活动主表基本一致，增加：
- `draft_status`：`editing/abandoned/submitted`。
- `submitted_campaign_id`：提交成功后关联正式活动。

### 6.5 草稿主商品表：`shopee_addon_draft_main_items`

用途：保存草稿中的主商品池。

字段建议：
- `id`
- `draft_id`
- `run_id`
- `listing_id`
- `variant_id`
- `product_id`
- `sort_order`
- `created_at`

### 6.6 草稿加购/赠品表：`shopee_addon_draft_reward_items`

用途：保存草稿中的加购商品或赠品商品。

字段建议：
- `id`
- `draft_id`
- `run_id`
- `listing_id`
- `variant_id`
- `product_id`
- `addon_price`
- `reward_qty`
- `sort_order`
- `created_at`

### 6.7 与现有订单表的关系

优先复用已有订单归因字段：
- `shopee_orders.marketing_campaign_type`
- `shopee_orders.marketing_campaign_id`
- `shopee_orders.marketing_campaign_name_snapshot`
- `shopee_order_items` 的 item 级 SKU 字段

订单明细建议补充或复用字段时遵循：
- 加价购商品明细：`marketing_campaign_type="add_on"`，成交单价为 `addon_price`。
- 满额赠赠品明细：`marketing_campaign_type="gift"`，成交单价为 `0`，仍扣减库存。

如现有 `shopee_order_items` 尚无 item 级营销归因字段，后续实现时建议新增：
- `marketing_campaign_type`：订单明细级营销类型。
- `marketing_campaign_id`：订单明细级营销活动 ID。
- `is_gift`：是否赠品明细。
- `original_unit_price_snapshot`：原价快照。
- `discount_unit_price_snapshot`：营销后成交单价快照。

## 7. Redis 设计

### 7.1 Key 设计

| Key | 用途 | TTL |
|---|---|---|
| `cbec:cache:shopee:add-on:create:bootstrap:{run_id}:{user_id}:{promotion_type}:{draft_id}` | 创建页初始化 | 60s |
| `cbec:cache:shopee:add-on:eligible-main-products:{run_id}:{user_id}:{hash}` | 主商品候选列表 | 60s |
| `cbec:cache:shopee:add-on:eligible-reward-products:{run_id}:{user_id}:{promotion_type}:{hash}` | 加购/赠品候选列表 | 60s |
| `cbec:cache:shopee:add-on:draft:{run_id}:{draft_id}` | 草稿详情 | 300s |
| `cbec:cache:shopee:add-on:detail:{run_id}:{campaign_id}` | 活动详情 | 120s |
| `cbec:cache:shopee:add-on:active-map:{run_id}:{user_id}` | 订单模拟用活动映射 | 30s |

### 7.2 失效策略

创建、编辑、停用、删除活动后必须失效：
- 折扣首页 bootstrap/list/performance 缓存。
- `add-on:detail:{run_id}:{campaign_id}`。
- `add-on:active-map:{run_id}:{user_id}`。
- 当前用户创建页 bootstrap 缓存。
- 相关商品候选列表缓存。

草稿保存后必须失效：
- 对应 `add-on:draft:{run_id}:{draft_id}`。
- 对应 bootstrap 缓存。

订单生成、发货、取消后：
- 沿用订单列表缓存失效。
- 若订单命中 `add_on/gift`，同步失效折扣活动数据页或促销表现缓存。

### 7.3 限流建议

| 接口 | 限流建议 |
|---|---|
| bootstrap | `60 req/min/user` |
| 商品候选列表 | `120 req/min/user` |
| 草稿保存 | `30 req/min/user` |
| 正式创建 | `20 req/min/user` |
| 停用活动 | `20 req/min/user` |

## 8. 订单模拟接入设计

### 8.1 总体流程

加价购/满额赠在现有订单模拟中插入到“已选出主商品并决定下单”之后：

```text
买家激活
  -> 候选商品评分
  -> 选出 best_listing / variant
  -> 单品折扣或套餐优惠原有逻辑
  -> 确认基础订单会生成
  -> 查询 add_on/gift active_map
  -> 若 best_listing 命中主商品：尝试追加加购商品或赠品
  -> 创建订单头与多条订单明细
```

设计原则：
- 加价购不改变买家最初选择主商品的逻辑。
- 加价购只在主商品已被自然选中后触发。
- 满额赠不改变主商品成交价，只追加 0 元赠品明细。
- 套餐优惠的 bundle 组合购买优先级高于加价购；同一订单不同时触发 bundle 与 add_on/gift，避免一笔订单过度复杂。

### 8.2 `add_on` 触发条件

- 当前游戏时间内存在 ongoing `promotion_type="add_on"` 活动。
- 订单主商品的 `listing_id/variant_id` 命中活动主商品池。
- 活动至少存在 1 个有库存的加购商品。
- 买家预算允许支付主商品金额 + 加购商品金额。
- 未超过 `addon_purchase_limit`。

### 8.3 `add_on` 概率建议

```python
savings_rate = clamp((original_price - addon_price) / original_price, 0.0, 0.95)
budget_factor = clamp(buyer_budget / (main_order_amount + addon_price), 0.50, 1.0)
addon_prob = clamp(
    0.10
    + savings_rate * (0.75 + buyer.price_sensitivity * 0.60)
    + buyer.impulse_level * 0.10,
    0.0,
    0.70,
) * budget_factor
```

说明：
- `add_on` 是附加购买，不应强行替代基础订单概率。
- 优惠越大、价格敏感度越高、冲动系数越高，越容易加购。
- 预算不足时降低触发概率，但不低于 0.50 约束，避免完全失效。

### 8.4 `gift` 触发条件

- 当前游戏时间内存在 ongoing `promotion_type="gift"` 活动。
- 订单主商品命中活动主商品池。
- 订单商品金额 `>= gift_min_spend`。
- 活动赠品有库存。

### 8.5 `gift` 处理方式

- 满足条件时直接追加赠品明细，不额外抽概率。
- 赠品 `unit_price=0`，`buyer_payment` 不增加。
- 赠品仍需预占库存、发货扣减库存、取消释放库存。

### 8.6 订单归因

订单头归因：
- 若触发 `add_on`：
  - `marketing_campaign_type="add_on"`
  - `marketing_campaign_id=campaign.id`
  - `marketing_campaign_name_snapshot=campaign.campaign_name`
- 若触发 `gift`：
  - `marketing_campaign_type="gift"`
  - `marketing_campaign_id=campaign.id`
  - `marketing_campaign_name_snapshot=campaign.campaign_name`

订单明细归因：
- 主商品保持原营销归因或为空。
- 加购商品明细标记 `add_on`。
- 赠品明细标记 `gift` 且 `is_gift=true`。

### 8.7 与现有营销优先级

V1 建议优先级：

| 优先级 | 类型 | 说明 |
|---|---|---|
| 1 | `bundle` | 套餐优惠会生成组合 SKU 订单，命中后不再叠加加价购/满额赠。 |
| 2 | `discount` | 单品折扣可影响主商品成交价与下单概率。 |
| 3 | `add_on` | 在主商品已下单后追加加购商品。 |
| 4 | `gift` | 在主商品已下单且达到门槛后追加赠品。 |

同一订单首版最多触发一种附加型活动：`add_on` 或 `gift`。若同一主商品同时命中多个活动，选择活动开始时间最近且创建时间最早的一条，避免随机不可复现。

## 9. 列表与数据页口径

折扣首页活动类型 Tab 已预留 `add_on`，后端列表需支持：
- `discount_type=add_on` 返回加价购与满额赠活动。
- `campaign_type_label`：
  - `add_on` 展示 `加价购`。
  - `gift` 展示 `满额赠`。

促销表现统计：
- `add_on` 销售额包含主订单金额 + 加购商品金额。
- `gift` 销售额只包含主订单金额，不包含赠品 0 元金额。
- 售出件数：
  - `add_on` 包含加购商品件数。
  - `gift` 可单独统计赠品件数，默认不计入售出商品数，避免 0 元赠品拉高销售件数。

## 10. 验收标准

1. 新设计文档明确加价购与满额赠的后端接口、数据库、Redis 与订单模拟口径。
2. 所有新表和字段均有业务用途说明，后续实现时必须同步 table comment / column comment。
3. 创建页 bootstrap、商品选择器、草稿、正式创建、详情接口路径与字段完整。
4. `add_on` 能在订单模拟中追加加购商品明细，并按加价购价计入订单金额。
5. `gift` 能在订单模拟中追加 0 元赠品明细，并参与库存预占、发货扣减和取消释放。
6. 创建/停用活动后能失效折扣首页、活动详情和订单模拟 active map 缓存。
7. 历史回溯只读模式下不会产生写操作。
8. 不修改当前前端页面样式。

## 11. 分期建议

- Phase 1：数据库表、bootstrap、商品候选、草稿、正式创建。
- Phase 2：折扣首页列表接入 `add_on/gift` 活动展示。
- Phase 3：订单模拟接入 add_on/gift、库存扣减与取消释放。
- Phase 4：详情页、复制、编辑、数据页统计。

## 12. 与现有文档的衔接

- 与 [19-Shopee折扣页复刻设计.md](./19-Shopee折扣页复刻设计.md) 衔接：作为折扣首页 `add_on` 类型创建入口的后端落地。
- 与 [21-Shopee套餐优惠创建页设计.md](./21-Shopee套餐优惠创建页设计.md) 衔接：复用创建页 bootstrap、商品选择器、草稿和缓存设计模式。
- 与 [27-套餐优惠概率计算设计.md](./27-套餐优惠概率计算设计.md) 衔接：订单模拟中 bundle 优先，加价购/满额赠作为主商品成交后的附加型营销。
- 与 [28-Shopee套餐优惠组合购买改造设计.md](./28-Shopee套餐优惠组合购买改造设计.md) 衔接：复用 item 级 SKU 明细、库存预占、发货扣减、取消释放的多明细处理能力。

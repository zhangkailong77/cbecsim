# 28 - Shopee 套餐优惠组合购买改造设计

> 创建日期：2026-04-27  
> 状态：已实现首版；2026-04-27 修正 purchase_limit 为买家维度限购

## 目标

将 Shopee 套餐优惠从“单 SKU 多件加购优惠”修正为“多 SKU 组合购买优惠”：买家命中套餐优惠后，必须购买套餐活动内的组合 SKU，不允许只购买其中一个 SKU；我的订单列表和详情页需要清晰展示组合内所有 SKU。

本设计要求在不影响普通订单、单品折扣订单、现有随机购买数量逻辑的前提下，为 `marketing_campaign_type="bundle"` 的订单建立按订单项逐 SKU 处理的独立链路。

## 背景

当前 27 号设计和实现已将套餐优惠接入订单模拟概率链路，但现有实现仍把 bundle 当作“某个 SKU 买 N 件享优惠”：

- `_load_ongoing_bundle_map` 按 `(listing_id, variant_id)` 建立套餐映射；
- `_resolve_bundle_upgrade` 返回单 SKU 的 `quantity/unit_price`；
- 订单落库时只创建 1 条 `ShopeeOrderItem`；
- 我的订单列表只展示 `row.items[0]`，详情页虽支持多 items，但订单源数据本身只有 1 条 item；
- 发货、取消、补货链路主要依赖 `ShopeeOrder.listing_id/variant_id/backorder_qty`，不具备真实多 SKU 组合订单的库存处理能力。

因此如果只改前端展示，会造成“看起来是套餐，库存仍只扣一个 SKU”的错账风险。正确改法必须让 `ShopeeOrderItem` 成为套餐订单的 SKU 真相来源。

## 设计原则

| 原则 | 说明 |
|---|---|
| 普通订单不改语义 | 普通订单继续沿用现有随机数量 `rng.randint(min_qty, max_qty)` 链路 |
| 单品折扣不改语义 | 单品折扣继续影响成交单价和下单概率，不参与组合购买 |
| 套餐订单独立分支 | 仅 `marketing_campaign_type="bundle"` 的订单按多 SKU 订单项处理 |
| 订单项是真相来源 | 套餐订单的库存、发货、取消、补货均以 `ShopeeOrderItem` 的 item 级 SKU 字段为准 |
| 不允许半套购买 | 套餐组合内任一 SKU 不满足购买条件时，本次套餐订单不生成或降级为非套餐流程 |
| 展示不替代数据 | 前端展示组合 SKU 之前，后端必须真实返回多条订单项 |

## 流程

### 当前错误流程

```text
买家激活
  → 选择 best_listing / variant
  → 命中 bundle_map
  → 将单个 SKU 的 quantity 提升到套餐阶梯数量
  → 创建 1 条 ShopeeOrderItem
  → 我的订单只显示这个 SKU
```

问题：套餐活动中的其他 SKU 没有进入订单，也不会扣库存。

### 目标流程

```text
买家激活
  → 候选商品评分
  → 命中某个 bundle campaign
  → 读取该 campaign 下所有 ShopeeDiscountCampaignItem
  → 校验组合内每个 SKU 都可购买
      → 全部可购买：生成套餐订单
          → 每个组合 SKU 创建 1 条 ShopeeOrderItem
          → buyer_payment = sum(item.unit_price × item.quantity)
          → 库存按 item 逐项预占
      → 任一 SKU 不可购买：不生成半套订单，回退普通/单品折扣流程或跳过本次套餐命中
  → 我的订单列表展示套餐摘要
  → 我的订单详情展示完整组合 SKU
```

## 业务规则

### 1. 套餐组合购买规则

- 套餐优惠订单必须包含活动内的组合 SKU。
- 不允许只购买组合中的单个 SKU。
- MVP 阶段按“一个套餐活动的已选商品 = 一个组合包”处理。
- 组合包数量默认为 1 套；后续可扩展为随机购买多套。

### 2. 随机购买数量规则

普通订单和单品折扣订单继续使用现有随机购买数量：

```python
quantity = rng.randint(min_qty, max_qty)
```

套餐优惠订单不再随机单个 SKU 数量，而是随机或固定“套餐套数”：

```python
bundle_set_qty = 1
for bundle_item in campaign_items:
    order_item.quantity = bundle_set_qty
```

后续如需支持买 2 套套餐，可扩展为：

```python
bundle_set_qty = rng.randint(1, max_bundle_sets)
# A x2 + B x2，而不是只买 A 或只买 B
```

### 3. 库存规则

- 套餐订单库存检查必须逐 SKU 执行。
- 任一 SKU 库存与可超卖额度不足时，不允许生成半套订单。
- 套餐订单的 `stock_fulfillment_status` 可由订单项聚合：
  - 全部 item 现货：`in_stock`
  - 任一 item 缺货：`backorder`
  - 缺货补齐后：`restocked`
- `ShopeeOrder.backorder_qty` 可保留为订单级汇总值；真实缺货分布记录在 `ShopeeOrderItem.backorder_qty`。

### 4. 价格规则

套餐活动的三种价格类型继续沿用 27 号设计：

| 类型 | 规则 |
|---|---|
| `percent` | 每个组合 SKU 按比例折扣计算成交价 |
| `fixed_amount` | 固定减免金额按组合 SKU 原价占比分摊，或 MVP 阶段按件数均摊 |
| `bundle_price` | 套餐价按组合 SKU 原价占比分摊，或 MVP 阶段按件数均摊 |

推荐 MVP 使用“按原价占比分摊”，避免高价 SKU 和低价 SKU 被均摊成同价导致财务展示失真：

```python
item_unit_price = round(bundle_total_price * item_original_price / total_original_price)
```

### 5. 订单归因规则

- 套餐订单写入：
  - `ShopeeOrder.marketing_campaign_type = "bundle"`
  - `ShopeeOrder.marketing_campaign_id = campaign.id`
  - `ShopeeOrder.marketing_campaign_name_snapshot = campaign.campaign_name`
- `ShopeeOrder.listing_id/variant_id` 保留为组合首项，作为旧链路兼容字段，不作为套餐订单库存真相。
- 套餐订单库存与展示以 `ShopeeOrder.items` 为准。

## 数据模型

### shopee_order_items 字段扩展

为支持套餐订单逐 SKU 处理，建议给 `shopee_order_items` 新增 item 级字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `listing_id` | Integer nullable | 订单项对应 Shopee 商品 ID |
| `variant_id` | Integer nullable | 订单项对应规格 ID，无规格商品为空 |
| `product_id` | Integer nullable | 订单项对应库存商品 ID，用于库存批次扣减 |
| `stock_fulfillment_status` | String(24) | 订单项履约状态：`in_stock/backorder/restocked` |
| `backorder_qty` | Integer | 订单项缺货数量 |

数据库规则：新增字段需要在迁移或初始化脚本内同步添加字段注释；若本次迁移触碰历史表结构，应补齐表注释和新增字段注释。

### 兼容策略

- 新订单：普通订单、单品折扣订单、套餐订单均写入 item 级字段。
- 历史订单：若 item 级字段为空，非 bundle 链路仍可回退使用 `ShopeeOrder.listing_id/variant_id/backorder_qty`。
- 套餐订单：必须要求 item 级字段完整，否则发货/取消应阻断并提示数据不完整。

## 接口影响

### 订单列表接口

接口：`GET /shopee/runs/{run_id}/orders`

响应中的 `items` 继续返回数组，但每个 item 建议补充：

```json
{
  "listing_id": 123,
  "variant_id": 456,
  "product_id": 789,
  "product_name": "SKU A",
  "variant_name": "Black",
  "quantity": 1,
  "unit_price": 45,
  "image_url": "...",
  "stock_fulfillment_status": "in_stock",
  "backorder_qty": 0
}
```

前端列表展示规则：

- 普通订单：保持当前单商品展示。
- 套餐订单：展示“套餐优惠：商品 A + 商品 B”，规格行展示“共 N 个商品 / M 件”。

### 订单详情接口

接口：`GET /shopee/runs/{run_id}/orders/{order_id}`

详情页已具备 `order.items.map(...)` 渲染基础，只需确保后端返回真实多条 items，并在活动标识处显示“套餐优惠：活动名”。

### 发货接口

接口：`POST /shopee/runs/{run_id}/orders/{order_id}/ship`

处理规则：

```python
if order.marketing_campaign_type == "bundle":
    for item in order.items:
        consume inventory by item.product_id and item.quantity
        write InventoryStockMovement with item.listing_id/item.variant_id
else:
    keep existing single listing flow
```

### 取消与补货

- 取消订单：bundle 分支逐 item 释放库存、回退销量和超卖占用。
- 缺货补齐：bundle 分支逐 item 检查 `backorder_qty`，逐 SKU 补齐。
- 非 bundle 订单继续保留现有逻辑，降低回归风险。

## 前端展示

### 我的订单列表

目标文件：`frontend/src/modules/shopee/views/MyOrdersView.tsx`

当前只展示首个 item。改造后：

- `row.marketing_campaign_type === 'bundle' && row.items.length > 1`：
  - 商品名：`套餐优惠：{item1.product_name} + {item2.product_name}`，超过 2 个显示“等 N 个商品”；
  - 规格行：`共 {row.items.length} 个商品 / {sum(quantity)} 件`；
  - 金额仍展示 `buyer_payment`。
- 其他订单保持原展示。

### 我的订单详情

目标文件：`frontend/src/modules/shopee/views/MyOrderDetailView.tsx`

- 商品表格继续使用 `order.items.map(...)`。
- 顶部活动标识显示“套餐优惠：活动名”。
- 顶部头像仍可取首个 item 图片，不作为业务真相。

## 验收标准

### 数据与订单生成

- 创建包含两个不同 SKU 的套餐优惠活动后，命中套餐时生成 1 个订单，且该订单包含 2 条 `ShopeeOrderItem`。
- 套餐订单的 `buyer_payment` 等于所有订单项小计之和。
- 不存在只包含组合内单个 SKU 的套餐优惠订单。
- 普通订单和单品折扣订单仍可生成 1 条或多件同 SKU 订单，随机购买数量逻辑不变。

### 库存与履约

- 套餐订单发货时，组合内每个 SKU 的库存都被正确扣减。
- 套餐订单取消时，组合内每个 SKU 的库存、销量、超卖占用都正确回滚。
- 任一组合 SKU 库存不足时，不允许生成半套套餐订单；如允许缺货单，则缺货数量必须记录到对应订单项。
- 普通订单发货、取消、补货不受 bundle 分支影响。

### 页面展示

- 我的订单列表中，套餐订单显示组合商品摘要，不再只显示其中一个 SKU。
- 我的订单详情中，套餐订单展示组合内所有 SKU、各自数量、单价和小计。
- 单品折扣订单继续显示折扣活动与折扣比例，不被误标为套餐优惠。

### 回归验证

- 后端至少验证：普通订单生成、单品折扣订单生成、套餐订单生成、套餐发货、套餐取消。
- 前端至少验证：我的订单列表套餐摘要、订单详情多 SKU 表格。
- 文档同步更新 `docs/当前进度.md` 与 `docs/change-log.md`。

## 实施边界

本设计只定义改造方案，不在本次文档提交中直接修改业务代码。

后续实现时建议按以下顺序拆分：

1. 数据库字段扩展与模型/schema 更新；
2. 普通订单写入 item 级字段，保证兼容；
3. 套餐订单生成多条 `ShopeeOrderItem`；
4. 发货/取消/补货增加 bundle 分支；
5. 我的订单列表与收入列表展示摘要增强；
6. 窄范围回归验证并更新进度台账。

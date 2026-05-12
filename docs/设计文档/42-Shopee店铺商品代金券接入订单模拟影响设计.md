# 42-Shopee 店铺/商品代金券接入订单模拟影响设计

> 创建日期：2026-05-08  
> 状态：设计完成，待实现

## 1. 目标

将已完成创建闭环的 Shopee 店铺代金券与商品代金券接入订单模拟，使模拟买家在下单决策和订单生成阶段感知代金券优惠。

本设计只覆盖：

- 店铺代金券 `shop_voucher`
- 商品代金券 `product_voucher`
- 订单模拟中的命中、优惠、下单概率、实付金额、归因和统计回写

不覆盖专属代金券、直播代金券、视频代金券、关注礼代金券。这些类型涉及领取渠道、场景来源或买家资格，应在后续单独接入。

## 2. 游戏时间口径

代金券对订单模拟的所有时间判断统一使用对局游戏时间口径。

| 场景 | 口径 |
| --- | --- |
| 活动开始/结束判断 | 使用订单模拟 tick 对应的游戏时间，与 `start_at/end_at` 比较 |
| 订单用券发生时间 | 使用当前订单模拟 tick 时间 |
| 活动状态刷新 | 按当前游戏 tick 动态判断 `upcoming/ongoing/ended/sold_out` |
| 日志记录 | `buyer_journeys` 中记录当前 tick 与命中结果 |
| 统计口径 | 按游戏时间生成订单时同步更新活动统计 |

实现上继续复用现有时间函数：

- `_resolve_game_tick(db, run_id, user_id)`：解析当前对局 tick。
- `_parse_discount_game_datetime(raw_value, run=run)`：创建时已将游戏时间映射为系统时间落库。
- `_align_compare_time(current_tick, row.start_at/end_at)`：比较时对齐时区/时间基准。

订单模拟入口 `simulate_orders_for_run(..., tick_time=now)` 中的 `now` 视为本次模拟 tick。代金券加载、状态判断和使用记录均以该 tick 为准，不使用服务器真实当前时间另行判断。

## 3. 范围与非范围

### 3.1 本期范围

- 加载当前游戏 tick 下进行中的店铺代金券和商品代金券。
- 判断订单候选商品和订单小计是否满足代金券使用条件。
- 对可用代金券计算订单级优惠金额。
- 多张券同时可用时，每单最多使用一张券；若存在可用券，则必须使用一张最优可用券。
- 代金券提升价格敏感买家的下单意愿，但不直接改商品行成交单价。
- 生成订单时若存在生效可用券，则扣减 `buyer_payment`，并保存订单级代金券快照字段。
- 成功生成订单后回写代金券 `used_count/order_count/sales_amount/buyer_count`。
- 在订单生成日志 `buyer_journeys` 中记录代金券候选、命中和优惠过程。
- 更新相关数据库字段注释与历史库补字段逻辑。

### 3.2 非范围

- 不实现买家主动领券、领券库存、券包或个人券实例。
- 不接入专属/直播/视频/关注礼代金券。
- 不实现代金券详情页、数据页、编辑、停止、复制、删除。
- 不新增前端页面。
- 不接入真实 Shopee 平台 API。
- 不做复杂平台级优惠叠加规则配置。

## 4. 核心业务规则

### 4.1 店铺代金券命中规则

店铺代金券适用于店铺内所有可售商品。订单模拟中满足以下条件时可作为候选券：

1. `run_id/user_id` 与当前对局和卖家一致。
2. 当前游戏 tick 满足 `start_at <= tick < end_at`。
3. `used_count < usage_limit`。
4. 订单小计 `order_subtotal >= min_spend_amount`。
5. 当前买家对该券历史使用次数小于 `per_buyer_limit`。
6. 本单不是限时抢购订单。

### 4.2 商品代金券命中规则

商品代金券仅适用于所选商品。除满足店铺代金券的时间、用量和买家限用条件外，还必须命中适用商品范围。

| 商品券明细 | 订单商品 | 是否命中 |
| --- | --- | --- |
| `listing_id=A, variant_id=null` | listing A 任意变体 | 命中 |
| `listing_id=A, variant_id=V1` | listing A + variant V1 | 命中 |
| `listing_id=A, variant_id=V1` | listing A + variant V2 | 不命中 |
| `listing_id=A` | listing B | 不命中 |

商品券第一版按订单主商品命中。若后续订单包含多个普通商品行，可扩展为按可用商品行小计计算。

### 4.3 每单最多一张，存在可用券时必须使用最优券

第一版每个模拟订单最多使用一张代金券；若买家在下单时存在生效且满足条件的店铺代金券或商品代金券，则必须使用其中一张最优可用券，不再引入“是否使用代金券”的随机判断。

选择规则：

1. 收集所有可用店铺券和商品券。
2. 计算每张券的优惠金额。
3. 选择优惠金额最大的券。
4. 优惠金额相同时，优先选择商品代金券，再选择店铺代金券。
5. 若仍相同，选择创建时间更早或 ID 更小的活动，保证结果稳定。
6. 如果没有任何可用券，则订单按无代金券逻辑生成。

### 4.4 优惠计算

代金券作为订单级优惠，不改变商品行 `unit_price`。

```text
order_subtotal = sum(line.unit_price * line.quantity)

if order_subtotal < voucher.min_spend_amount:
    voucher 不可用

if discount_type == fixed_amount:
    voucher_discount = discount_amount

if discount_type == percent:
    voucher_discount = order_subtotal * discount_percent / 100
    if max_discount_type == set_amount:
        voucher_discount = min(voucher_discount, max_discount_amount)

voucher_discount = min(voucher_discount, order_subtotal - 1)
buyer_payment = order_subtotal - voucher_discount
```

保留至少 1 RM 实付，避免 0 元订单影响现有订单、结算、库存和财务链路。

### 4.5 与已有营销活动的叠加关系

| 已有活动 | 第一版是否叠加代金券 | 说明 |
| --- | --- | --- |
| 单品折扣 `discount` | 是 | 商品先按折扣价成交，订单结算再用券 |
| 套餐优惠 `bundle` | 是 | 套餐优惠后的订单小计再判断券门槛 |
| 加价购 `add_on` | 是 | 加价购商品计入订单小计 |
| 满额赠 `gift` | 是 | 赠品 0 元行不增加可抵扣金额 |
| 限时抢购 `flash_sale` | 否 | 限时抢购已有强促销权重，第一版避免爆量和归因混乱 |

## 5. 订单模拟接入设计

### 5.1 加载代金券上下文

在 `simulate_orders_for_run()` 中新增：

```python
voucher_context = _load_ongoing_voucher_context(
    db,
    run_id=run_id,
    user_id=user_id,
    tick_time=now,
)
```

建议返回结构：

```python
{
    "shop_vouchers": [ ... ],
    "product_vouchers_by_listing": {
        (listing_id, variant_id): [ ... ],
        (listing_id, None): [ ... ],
    },
    "campaign_by_key": {
        (voucher_type, campaign_id): row,
    },
}
```

加载条件：

```text
run_id == 当前 run_id
user_id == 当前 user_id
start_at <= 当前游戏 tick < end_at
used_count < usage_limit
reward_type == discount
```

商品券加载时通过 `selectinload(ShopeeProductVoucherCampaign.items)` 预取适用商品，避免订单循环内频繁查询。

### 5.2 买家限用统计

在模拟 tick 开始前，按当前进行中代金券 ID 查询历史订单中的买家使用次数。

推荐新增订单级 voucher 字段后按如下维度统计：

```text
buyer_voucher_usage_counts[(buyer_name, voucher_type, voucher_campaign_id)] = count(order.id)
```

统计条件：

```text
ShopeeOrder.run_id == run_id
ShopeeOrder.user_id == user_id
ShopeeOrder.voucher_campaign_type in ('shop_voucher', 'product_voucher')
ShopeeOrder.voucher_campaign_id in 当前活动 ID 集合
```

### 5.3 候选商品评分阶段

候选商品评分时可计算“预计到手价”，用于提升价格感知：

```text
preview_order_subtotal = effective_price * min_purchase_qty
preview_voucher_discount = 可用券预计抵扣
preview_checkout_price = preview_order_subtotal - preview_voucher_discount
```

但为了保持现有折扣、套餐、加价购逻辑稳定，第一版不改 `_pick_variant_for_buyer()` 的实际成交价语义，只在候选日志和后续 `order_prob` 中体现 voucher bonus。

### 5.4 下单概率影响

代金券命中后，根据优惠比例给订单概率增加小幅 bonus。这里模拟的是“有券降低到手价后提升下单意愿”，不是模拟“是否使用代金券”。实际订单生成阶段每单最多使用一张券；若存在可用券，则必须使用一张最优可用券。

```python
voucher_savings_rate = voucher_discount / max(order_subtotal, 1)
voucher_order_bonus = _clamp(
    0.02 + voucher_savings_rate * 0.10 + buyer_price_sensitivity * voucher_savings_rate * 0.08,
    0.0,
    0.08,
)
order_prob = _clamp(order_prob + voucher_order_bonus, order_prob, 0.92)
```

设计原则：

- 代金券能提升转化，但不压过限时抢购等强促销。
- 价格敏感买家对代金券反应更明显。
- 下单概率 bonus 只影响是否下单；一旦生成订单，有可用券就确定性使用。
- 上限控制在 8%，避免订单量异常放大。

### 5.5 生成订单阶段

在 `order_lines` 确定后、创建 `ShopeeOrder` 之前计算：

```text
order_subtotal = sum(line.unit_price * line.quantity)
selected_voucher = _resolve_best_voucher_for_order(...)
voucher_discount_amount = selected_voucher.discount_amount or 0
payment = order_subtotal - voucher_discount_amount
```

`_resolve_best_voucher_for_order(...)` 只负责从满足时间、范围、门槛、用量和买家限用条件的券中选择最优券；只要返回非空，就必须应用到本单，不再做二次概率判断。

若 `flash_sale_hit` 为真，跳过代金券匹配，`payment = order_subtotal`。

订单商品行：

- `ShopeeOrderItem.unit_price` 保持商品活动后的成交单价。
- `original_unit_price/discounted_unit_price` 继续表示商品级促销，不被代金券改写。

订单主表：

- `buyer_payment` 保存扣减代金券后的实付金额。
- 新增订单级代金券快照字段保存用券信息。

## 6. 数据模型设计

### 6.1 `ShopeeOrder` 新增字段

建议在 `shopee_orders` 新增订单级 voucher 字段，而不是复用 `marketing_campaign_type`。

| 字段 | 类型 | 注释 |
| --- | --- | --- |
| `order_subtotal_amount` | Float | 代金券抵扣前订单商品小计，单位 RM |
| `voucher_campaign_type` | String(32), nullable, index | 订单使用的代金券类型：shop_voucher/product_voucher |
| `voucher_campaign_id` | Integer, nullable, index | 订单使用的代金券活动 ID |
| `voucher_name_snapshot` | String(255), nullable | 下单时的代金券名称快照 |
| `voucher_code_snapshot` | String(64), nullable | 下单时的代金券代码快照 |
| `voucher_discount_amount` | Float, not null default 0 | 本单代金券抵扣金额，单位 RM |

保留现有 `marketing_campaign_type/id/name_snapshot` 用于商品级主活动归因，避免代金券覆盖单品折扣、套餐、加价购等原有归因。

### 6.2 历史库补字段与注释

`db.py` 需要新增历史库补字段逻辑：

- 若 `shopee_orders` 缺少上述字段，则 `ALTER TABLE` 补齐。
- MySQL 环境同步维护字段注释。
- 新增索引：
  - `ix_shopee_orders_voucher_campaign_type`
  - `ix_shopee_orders_voucher_campaign_id`

## 7. 统计回写设计

订单成功创建后，若命中代金券，更新对应活动：

| 字段 | 更新规则 |
| --- | --- |
| `used_count` | 每个成功用券订单 +1 |
| `order_count` | 每个成功用券订单 +1 |
| `sales_amount` | 增加该订单实付金额 `buyer_payment` |
| `buyer_count` | 买家首次使用该券时 +1 |

买家首次使用判断：

```text
如果 buyer_voucher_usage_counts[(buyer_name, voucher_type, campaign_id)] == 0:
    buyer_count += 1
```

订单创建成功后同步更新本 tick 内内存计数，避免同一 tick 中同一买家连续订单突破 `per_buyer_limit`。

## 8. 日志设计

在 `buyer_journeys` 的 `selected_candidate` 和 `generated_order` 中补充：

```json
{
  "voucher_candidates": [
    {
      "voucher_type": "shop_voucher",
      "campaign_id": 1,
      "voucher_name": "满50减5",
      "min_spend_amount": 50,
      "discount_amount": 5,
      "savings_rate": 0.1,
      "eligible": true,
      "reason": "eligible"
    }
  ],
  "voucher_hit": true,
  "voucher_campaign_type": "shop_voucher",
  "voucher_campaign_id": 1,
  "voucher_discount_amount": 5,
  "voucher_order_bonus": 0.04,
  "order_subtotal": 50,
  "buyer_payment_after_voucher": 45
}
```

不可用原因建议枚举：

| reason | 含义 |
| --- | --- |
| `below_min_spend` | 未达到最低消费金额 |
| `usage_limit_reached` | 总使用量已满 |
| `buyer_limit_reached` | 当前买家已达使用上限 |
| `product_not_matched` | 商品券适用商品不匹配 |
| `flash_sale_excluded` | 限时抢购订单第一版不叠加代金券 |

## 9. 验收标准

1. 当前游戏 tick 未到 `start_at` 的券不会命中。
2. 当前游戏 tick 已到 `end_at` 的券不会命中。
3. 店铺券满足门槛后可命中任意普通订单。
4. 商品券只命中适用 listing/variant 的订单。
5. 店铺券和商品券同时可用时，必须选择优惠金额最大的一张；同额优先商品券。
6. 订单生成时每单最多使用一张券；若存在生效可用券，则必须使用一张最优可用券，不存在“是否使用券”的随机概率。
7. 代金券不改变 `ShopeeOrderItem.unit_price`。
7. `ShopeeOrder.buyer_payment` 等于订单小计扣减代金券后的实付金额。
8. 用券订单保存订单级 voucher 快照字段。
9. `used_count/order_count/sales_amount/buyer_count` 在订单生成成功后更新。
10. `usage_limit` 用完后后续订单不再命中该券。
11. 同一买家达到 `per_buyer_limit` 后后续订单不再命中该券。
12. 限时抢购订单第一版不叠加代金券。
13. `buyer_journeys` 能看到候选券、命中券、优惠金额和概率 bonus。
14. 没有代金券时订单模拟行为保持原有逻辑。

## 10. 实施顺序

1. 在 `ShopeeOrder` 和 `db.py` 增加订单级 voucher 字段、索引、表注释/字段注释和历史库补字段。
2. 在 `shopee_order_simulator.py` 增加代金券上下文加载函数。
3. 增加代金券候选匹配、优惠计算、最优券选择和买家限用判断函数。
4. 在订单模拟决策阶段加入代金券概率 bonus 和日志。
5. 在订单生成阶段扣减 `buyer_payment` 并写入订单级 voucher 快照。
6. 在订单创建成功后回写店铺/商品代金券统计。
7. 补充文档、进度和变更日志。

## 11. 风险与约束

- `sales_amount` 采用用券订单实付金额，不采用抵扣前小计，避免虚增收入。
- 第一版不做买家领券库存，因此 `used_count` 表示实际用券次数，不表示领取次数。
- 商品券第一版按主商品命中，若后续出现多主商品订单，需要扩展为逐行计算可抵扣小计。
- 限时抢购暂不叠加代金券，避免订单概率叠加过强。
- 新增订单字段后，订单列表/详情如需展示代金券优惠，可后续单独设计前端展示。
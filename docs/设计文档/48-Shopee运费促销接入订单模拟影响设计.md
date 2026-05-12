# 48-Shopee 运费促销接入订单模拟影响设计

> 创建日期：2026-05-09  
> 状态：设计完成，待实现

## 1. 目标

将已完成创建与列表闭环的 Shopee 运费促销接入订单模拟，使模拟订单在生成时能够按当前对局游戏时间、物流渠道、订单小计和活动预算命中运费优惠，并将命中结果持久化到订单、结算与活动统计中。

本设计承接：

- `docs/设计文档/47-Shopee运费促销创建前后端数据库Redis实现设计.md`
- 现有订单模拟：`backend/apps/api-gateway/app/services/shopee_order_simulator.py`
- 现有物流/结算口径：`backend/apps/api-gateway/app/services/shopee_fulfillment.py`

## 2. 范围与非范围

### 2.1 本期范围

- 订单模拟加载当前游戏 tick 下可用的运费促销活动。
- 按订单物流渠道和商品小计匹配运费促销层级。
- 在不改变商品行价格、不改变基础物流成本的前提下，计算买家侧运费优惠。
- 将订单级运费促销命中结果持久化到 `shopee_orders`。
- 将运费促销优惠纳入订单结算，影响卖家净收入。
- 回写运费促销活动统计：预算使用、订单数、买家数、销售额和运费优惠金额。
- 在 `buyer_journeys` 调试日志中记录候选活动、命中活动、原始运费、优惠后买家运费和预算扣减。
- 维护数据库字段注释和历史库补字段逻辑。
- 创建成功、订单生成、预算耗尽后清理相关 Redis 缓存。

### 2.2 非范围

- 不改变现有物流渠道、发货时限、运输时长和配送线路。
- 不替代平台运费补贴 `shipping_subsidy_amount`。
- 不接入真实 Shopee 平台运费促销 API。
- 不实现买家端真实运费券领取页面。
- 不实现运费促销编辑、停止、删除、复制和详情页。
- 不做复杂跨店包邮、平台补贴与店铺运费促销叠加配置。

## 3. 游戏时间口径

运费促销对订单模拟的所有判断均使用订单模拟 tick 的游戏时间，不使用服务器真实当前时间。

| 场景 | 口径 |
| --- | --- |
| 活动开始/结束判断 | 使用订单模拟传入的 `tick_time` 与活动 `start_at/end_at` 比较 |
| 活动状态刷新 | 按当前游戏 tick 动态判断 `upcoming/ongoing/ended/budget_exhausted/stopped` |
| 订单命中时间 | 使用订单创建时的游戏 tick |
| 预算扣减时间 | 使用订单生成时的游戏 tick |
| 活动统计回写 | 随订单生成同步回写，统计口径归属当前游戏 tick |
| 日志记录 | `buyer_journeys` 记录当前 tick、候选与命中结果 |

实现时继续复用现有时间工具：

- `_resolve_game_tick(db, run_id, user_id)`：解析当前对局 tick。
- `_align_compare_time(current_tick, row_time)`：比较活动开始/结束时间。
- 订单模拟入口 `simulate_orders_for_run(..., tick_time=now)` 中的 `now` 作为本次订单模拟游戏时间。

## 4. 与现有订单运费/结算链路的关系

当前已有物流和结算逻辑：

| 现有字段/函数 | 当前含义 | 运费促销接入方式 |
| --- | --- | --- |
| `ShopeeOrder.shipping_channel` | 订单物流渠道 | 用于匹配活动渠道，不改字段含义 |
| `ShopeeOrder.distance_km` | 仓库到买家距离 | 用于计算原始运费，不改字段含义 |
| `calc_shipping_cost(distance_km, shipping_channel)` | 计算卖家真实物流成本；计费距离按 80km 封顶，长距离只追加远程附加费 | 继续作为原始运费和卖家物流成本来源 |
| `calc_eta(distance_km, shipping_channel, shipped_at)` | 计算运输预计时间 | 运费促销不影响 |
| `ShopeeOrderSettlement.shipping_cost_amount` | 卖家真实物流成本 | 继续保存原始物流成本，不扣减促销优惠 |
| `ShopeeOrderSettlement.shipping_subsidy_amount` | 平台运费补贴 | 继续按平台补贴口径计算，不被运费促销替代 |
| `ShopeeOrderSettlement.net_income_amount` | 卖家净收入 | 需要额外扣除卖家承担的运费促销优惠 |

核心原则：

```text
原始运费成本 = calc_shipping_cost(distance_km, shipping_channel)
平台补贴 = calc_settlement(...) 现有口径
买家侧运费优惠 = 运费促销命中后产生的减免
卖家物流成本 = 原始运费成本，不因促销改变
卖家净收入 = 现有净收入 - 运费促销优惠
运输时长 = calc_eta(...)，不受促销影响
```

## 5. 命中规则

订单满足以下条件时，可以命中运费促销：

1. 活动 `run_id/user_id` 与当前订单模拟一致。
2. 当前订单模拟 tick 处于活动有效期内。
3. 活动未被手动停止。
4. 若活动有预算，则 `budget_used < budget_limit`。
5. 订单 `shipping_channel` 能映射到活动渠道。
6. 订单商品小计 `order_subtotal_amount` 满足至少一个层级的 `min_spend_amount`。
7. 同一订单只命中一个运费促销活动。

状态口径：

| 状态 | 是否可命中 |
| --- | --- |
| `ongoing` | 是 |
| `upcoming` | 否 |
| `ended` | 否 |
| `budget_exhausted` | 否 |
| `stopped` | 否 |

## 6. 渠道映射

创建页活动渠道使用前端 key：

| 活动渠道 key | 活动展示名 | 当前订单渠道匹配建议 |
| --- | --- | --- |
| `standard` | 标准快递 (Standard Delivery) | `标准快递`、`快捷快递` |
| `bulky` | 大件快递 (Standard Delivery Bulky) | `标准大件` |

若订单仍出现旧渠道名或其他渠道：

- `快捷快递` 按标准快递 `standard` 命中运费促销。
- 未知渠道不命中，并在 `buyer_journeys` 记录 `shipping_channel_not_matched`。

## 7. 活动选择规则

若同一订单同时满足多个运费促销活动：

1. 先按订单渠道筛选活动。
2. 每个活动内部选中满足门槛的最高 `min_spend_amount` 层级。
3. 计算每个候选活动可产生的优惠金额。
4. 选择优惠金额最大的活动。
5. 优惠金额相同时，选择门槛更高的活动。
6. 仍相同时，选择创建时间更早或 ID 更小的活动，保证结果稳定。

第一版不做随机选择：只要存在可用活动，就按上述规则命中最优活动。

## 8. 优惠计算

### 8.1 原始运费

```text
original_shipping_fee = calc_shipping_cost(order.distance_km, order.shipping_channel)
```

若订单生成阶段尚未写入 `distance_km`，则应先沿用当前订单物流逻辑确定距离，再计算原始运费。

### 8.2 层级命中

对每个活动层级：

```text
if order_subtotal >= tier.min_spend_amount:
    该层级可命中
```

命中活动内最高门槛层级。

### 8.3 买家侧运费

```text
if fee_type == "fixed_fee":
    shipping_promotion_discount_amount = min(original_shipping_fee, fixed_fee_amount)
    buyer_shipping_fee_after_promotion = original_shipping_fee - shipping_promotion_discount_amount

if fee_type == "free_shipping":
    shipping_promotion_discount_amount = original_shipping_fee
    buyer_shipping_fee_after_promotion = 0
```

如果运费减免金额高于原始运费，则最多减免到原始运费，优惠后买家运费为 0。

### 8.4 预算不足

若活动为自定义预算：

```text
remaining_budget = budget_limit - budget_used
actual_discount = min(shipping_promotion_discount_amount, remaining_budget)
buyer_shipping_fee_after_promotion = original_shipping_fee - actual_discount
```

预算不足时：

- 本单仍可使用剩余预算产生部分运费优惠。
- 活动 `budget_used` 增加 `actual_discount`。
- 若 `budget_used >= budget_limit`，活动状态更新为 `budget_exhausted`。

### 8.5 与商品代金券/营销优惠关系

运费促销只影响运费，不改变商品小计和商品行价格。

推荐订单金额拆分：

```text
商品小计 = order_subtotal_amount
商品/店铺/专属/直播/视频/关注礼代金券优惠 = voucher_discount_amount
商品实付 = buyer_payment 现有口径
原始运费 = shipping_fee_before_promotion
买家运费优惠 = shipping_promotion_discount_amount
优惠后买家运费 = shipping_fee_after_promotion
```

第一版可以不把买家承担运费加进 `ShopeeOrder.buyer_payment`，因为当前 `buyer_payment` 已作为商品支付口径使用；但必须单独保存运费优惠字段，避免混淆商品实付与运费优惠。

## 9. 数据模型设计

### 9.1 `shopee_orders` 新增字段

| 字段 | 类型 | 默认值 | 注释 |
| --- | --- | --- | --- |
| `shipping_promotion_campaign_id` | Integer, nullable, index | null | 命中的运费促销活动 ID |
| `shipping_promotion_name_snapshot` | String(255), nullable | null | 命中的运费促销名称快照 |
| `shipping_promotion_tier_index` | Integer, nullable | null | 命中的运费促销层级序号 |
| `shipping_fee_before_promotion` | Float, not null | 0 | 运费促销前买家侧原始运费，单位 RM |
| `shipping_fee_after_promotion` | Float, not null | 0 | 运费促销后买家侧应付运费，单位 RM |
| `shipping_promotion_discount_amount` | Float, not null | 0 | 本单运费促销优惠金额，单位 RM |

建议索引：

```python
Index("ix_shopee_orders_shipping_promotion_campaign", "shipping_promotion_campaign_id")
```

字段说明：

- `shipping_fee_before_promotion` 用于展示和调试原始买家运费。
- `shipping_fee_after_promotion` 用于展示买家促销后承担运费。
- `shipping_promotion_discount_amount` 用于活动预算扣减和卖家营销成本统计。
- 字段必须在 `db.py` 历史库补字段和字段注释逻辑中同步维护。

### 9.2 `shopee_order_settlements` 新增字段

| 字段 | 类型 | 默认值 | 注释 |
| --- | --- | --- | --- |
| `shipping_promotion_discount_amount` | Float, not null | 0 | 卖家承担的运费促销优惠金额，单位 RM |

结算净收入调整：

```text
net_income_amount = 原有净收入 - shipping_promotion_discount_amount
```

同时保留：

- `shipping_cost_amount`：原始物流成本。
- `shipping_subsidy_amount`：平台运费补贴。

### 9.3 运费促销活动统计字段

已在 `shopee_shipping_fee_promotion_campaigns` 中存在：

| 字段 | 回写口径 |
| --- | --- |
| `budget_used` | 累加实际本单运费促销优惠金额 |
| `order_count` | 命中活动订单数 +1 |
| `buyer_count` | 去重买家数，第一版可按活动下历史命中订单 distinct buyer 计算或用内存集合维护 |
| `sales_amount` | 累加命中订单商品小计或商品实付，建议第一版用 `order_subtotal_amount` |
| `shipping_discount_amount` | 累加实际本单运费促销优惠金额 |
| `status` | 预算耗尽时更新为 `budget_exhausted` |

## 10. 订单模拟接入点

建议在 `simulate_orders_for_run(...)` 中接入，顺序如下：

1. 进入订单模拟时加载当前 tick 可用运费促销活动、渠道和层级。
2. 订单候选商品、数量、营销活动和代金券计算完成后，得到 `order_subtotal`。
3. 确定订单 `shipping_channel` 后，计算 `original_shipping_fee`。
4. 调用运费促销匹配函数，返回：
   - `selected_shipping_promotion`
   - `shipping_fee_before_promotion`
   - `shipping_fee_after_promotion`
   - `shipping_promotion_discount_amount`
5. 创建 `ShopeeOrder` 时写入订单级运费促销字段。
6. 成功生成订单后回写活动统计与预算。
7. 在 `buyer_journeys` 的 `generated_order` 中记录运费促销命中结果。
8. 清理订单列表、运费促销列表和订单模拟活动缓存。

建议新增内部函数：

```python
def _load_active_shipping_fee_promotions(...):
    ...


def _resolve_best_shipping_fee_promotion_for_order(...):
    ...


def _apply_shipping_fee_promotion_stats(...):
    ...
```

## 11. 结算接入点

当前结算在 `_upsert_order_settlement(...)` 中通过：

```python
shipping_cost = calc_shipping_cost(float(order.distance_km or 0), order.shipping_channel)
settlement_data = calc_settlement(
    buyer_payment=float(order.buyer_payment or 0),
    shipping_cost=shipping_cost,
    shipping_channel=order.shipping_channel,
)
```

接入后：

```text
shipping_promotion_discount = order.shipping_promotion_discount_amount
settlement.shipping_cost_amount = 原始 shipping_cost
settlement.shipping_subsidy_amount = 原有平台补贴
settlement.shipping_promotion_discount_amount = shipping_promotion_discount
settlement.net_income_amount = settlement_data["net_income_amount"] - shipping_promotion_discount
```

这样可以保证：

- 平台补贴仍按原始物流成本计算。
- 卖家仍承担真实物流成本。
- 运费促销作为额外营销成本扣减净收入。

## 12. Redis 设计

沿用并扩展 47 号文档 key：

| 用途 | Key |
| --- | --- |
| 订单模拟可用运费促销 | `shopee:shipping_fee_promotion:active:{run_id}:{user_id}:{tick_bucket}` |
| 活动列表 | `shopee:shipping_fee_promotion:list:{run_id}:{user_id}:{status}:{page}:{page_size}` |
| 订单列表 | 复用现有订单列表缓存前缀 |

失效规则：

- 创建运费促销后：清理活动列表和订单模拟可用活动缓存。
- 订单命中运费促销后：清理活动列表缓存、订单列表缓存和当前 tick 订单模拟活动缓存。
- 预算耗尽后：清理活动列表缓存和订单模拟可用活动缓存。
- 后续编辑/停止/删除活动时：同样清理相关缓存。

## 13. 前端展示设计

### 13.1 我的订单列表

建议在“买家实付”或订单金额附近展示小字标注：

```text
运费促销：活动名称 -RM X.XX
```

同时可展示：

```text
运费：RM 原始运费 → RM 优惠后运费
```

第一版可只在订单详情或调试字段中展示，列表页若改动较大可后置。

### 13.2 运费促销列表

活动列表已有字段：

- `budget_used_text`
- `order_count`
- `shipping_discount_amount`

接入订单模拟后，应随订单生成刷新这些统计。

## 14. 日志与调试

`buyer_journeys` 建议新增字段：

```json
{
  "shipping_fee_promotion_candidates": [
    {
      "campaign_id": 12,
      "promotion_name": "满 RM50 运费优惠",
      "matched_channel": true,
      "matched_tier_index": 1,
      "min_spend_amount": 50,
      "fee_type": "fixed_fee",
      "fixed_fee_amount": 2,
      "original_shipping_fee": 8.4,
      "shipping_fee_after_promotion": 6.4,
      "shipping_discount_amount": 2
    }
  ],
  "selected_shipping_fee_promotion": {
    "campaign_id": 12,
    "tier_index": 1,
    "shipping_discount_amount": 6.4
  }
}
```

未命中时记录原因：

- `no_active_shipping_fee_promotion`
- `shipping_channel_not_matched`
- `order_subtotal_below_min_spend`
- `budget_exhausted`
- `zero_discount`

## 15. 验收标准

实现完成后应满足：

1. 当前游戏 tick 下进行中的运费促销能被订单模拟加载。
2. 订单物流渠道与活动渠道匹配时才可能命中。
3. 订单小计满足门槛时，命中最高门槛层级。
4. 运费减免和免运费均能正确计算买家侧运费优惠。
5. 预算不足时只使用剩余预算，并将活动状态更新为 `budget_exhausted`。
6. 订单级字段保存命中的活动 ID、名称快照、层级、优惠前后运费和优惠金额。
7. 结算中 `shipping_cost_amount` 和 `shipping_subsidy_amount` 保持原口径，`net_income_amount` 额外扣除运费促销优惠。
8. 活动统计回写 `budget_used/order_count/buyer_count/sales_amount/shipping_discount_amount`。
9. 列表页刷新后可看到预算使用和统计变化。
10. 所有时间判断使用游戏时间，不使用真实世界当前时间。
11. 数据库新增字段和表字段注释完整，历史库补字段逻辑同步维护。
12. Redis 缓存在创建、命中、预算耗尽后正确失效。

## 16. 建议验证用例

| 用例 | 设置 | 预期 |
| --- | --- | --- |
| 运费减免命中 | 原始运费 RM 8，运费减免 RM 2 | 优惠 RM 2，优惠后运费 RM 6 |
| 免运费命中 | 原始运费 RM 8，免运费 | 优惠 RM 8，优惠后运费 RM 0 |
| 门槛不足 | 订单小计 RM 40，门槛 RM 50 | 不命中 |
| 渠道不匹配 | 订单 `标准大件`，活动只选 `standard` | 不命中 |
| 多层级 | RM 50 固定 RM 4，RM 100 免运费，订单小计 RM 120 | 命中 RM 100 免运费层级 |
| 多活动 | 两个活动均可用 | 选择优惠金额最大活动 |
| 预算不足 | 剩余预算 RM 3，理论优惠 RM 6 | 实际优惠 RM 3，活动预算耗尽 |
| 已结束活动 | 当前 tick 晚于 `end_at` | 不命中 |

## 17. 后续待办

1. 按本文档实现订单模拟接入、订单字段、结算字段和统计回写。
2. 在“我的订单”列表或详情补充运费促销命中展示。
3. 后续补充运费促销详情、数据页、停止、编辑、删除和复制能力。

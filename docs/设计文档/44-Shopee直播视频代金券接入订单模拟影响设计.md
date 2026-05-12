# 44-Shopee 直播视频代金券接入订单模拟影响设计

> 创建日期：2026-05-08  
> 状态：设计完成，待实现

## 1. 目标

将已完成创建闭环的 Shopee 直播代金券 `live_voucher` 与视频代金券 `video_voucher` 接入订单模拟，使模拟买家在具备直播/视频场景触达资格后，能在下单决策、订单生成、实付金额、订单归因和活动统计中体现内容场景代金券影响。

本设计覆盖：

- 直播代金券 `live_voucher`
- 视频代金券 `video_voucher`
- 买家直播/视频内容场景触达资格模拟
- 订单模拟中的命中、优惠、下单概率、实付金额、归因和统计回写

不覆盖：

- 真实 Shopee Live 开播、观看、讲解商品、直播间领券接口
- 真实 Shopee Video 发布、观看、挂车点击、视频领券接口
- 直播/视频内容管理、场次管理、视频素材管理
- 买家个人券实例、领取记录、券包页面
- 直播/视频代金券详情、编辑、删除、停止、复制和数据页
- 关注礼代金券订单影响

## 2. 游戏时间口径

直播/视频代金券对订单模拟的所有时间判断统一使用对局游戏时间口径。

| 场景 | 口径 |
| --- | --- |
| 活动开始/结束判断 | 使用订单模拟 tick 对应的游戏时间，与 `start_at/end_at` 比较 |
| 提前展示判断 | 第一版订单模拟不单独使用 `display_start_at` 发券；只用于后续内容曝光扩展 |
| 买家获得内容场景资格时间 | 第一版使用当前模拟 tick 即时判定，不生成长期个人券实例 |
| 订单用券发生时间 | 使用当前订单模拟 tick 时间 |
| 活动状态刷新 | 按当前游戏 tick 动态判断 `upcoming/ongoing/ended/sold_out` |
| 日志记录 | `buyer_journeys` 中记录当前 tick、场景类型、资格来源、候选券和命中结果 |
| 统计口径 | 按游戏时间生成订单时同步更新活动统计 |

实现上继续复用现有时间函数：

- `_resolve_game_tick(db, run_id, user_id)`：解析当前对局 tick。
- `_align_compare_time(current_tick, row.start_at/end_at)`：比较时对齐时区/时间基准。
- `simulate_orders_for_run(..., tick_time=now)` 中的 `now` 视为本次模拟 tick。

## 3. 范围与非范围

### 3.1 本期范围

- 加载当前游戏 tick 下进行中的直播/视频代金券。
- 为模拟买家计算是否具备直播/视频内容场景触达资格。
- 判断订单候选商品和订单小计是否满足直播/视频券使用条件。
- 对可用直播/视频券计算订单级优惠金额。
- 与店铺券、商品券、专属券共用“每单最多一张券，存在可用券时必须使用最优券”的选择规则。
- 直播/视频券提升具备内容场景触达资格买家的下单意愿。
- 生成订单时若直播/视频券被选为最优券，则扣减 `buyer_payment`，并保存订单级 voucher 快照字段。
- 成功生成订单后回写直播/视频券 `used_count/order_count/sales_amount/buyer_count`。
- 在订单生成日志 `buyer_journeys` 中记录内容场景资格、候选、命中和优惠过程。

### 3.2 非范围

- 不新增买家个人券实例表。
- 不实现真实领券库存、券包、领取按钮或领取记录页面。
- 不实现直播间或视频详情页的真实买家行为链路。
- 不新增前端页面。
- 不接入真实 Shopee 平台 API。
- 不改变已有店铺券、商品券、专属券使用规则。

## 4. 核心业务规则

### 4.1 内容场景代金券可用前提

直播/视频代金券不同于公开店铺券/商品券，不是所有买家自然可用。订单模拟中必须先判断买家是否在本次 tick 中被直播或视频内容触达，再进入代金券候选池。

直播/视频券成为候选券需要同时满足：

1. `run_id/user_id` 与当前对局和卖家一致。
2. 当前游戏 tick 满足 `start_at <= tick < end_at`。
3. `reward_type == discount`。
4. `used_count < usage_limit`。
5. 当前买家具备该内容场景券资格。
6. 当前买家对该券历史使用次数小于 `per_buyer_limit`。
7. 订单商品命中适用范围。
8. 订单可抵扣小计满足 `min_spend_amount`。
9. 本单不是限时抢购订单。

### 4.2 买家内容场景资格模拟

第一版采用“模拟内容触达”方案：不生成真实直播观看记录、视频观看记录、领券记录或个人券实例；订单模拟按买家画像动态模拟“看过直播/视频、被内容种草、获得内容场景券资格”的买家集合。

建议资格概率按买家行为特征、内容场景和券吸引力综合计算：

```text
content_access_score =
  base_scene_rate
  + buyer.impulse_level * impulse_weight
  + buyer.price_sensitivity * 0.12
  + buyer.base_buy_intent * 0.10
  + voucher_savings_rate * 0.18
```

直播与视频差异：

| 场景 | base_scene_rate | impulse_weight | 设计含义 |
| --- | ---: | ---: | --- |
| `live_voucher` | 0.192 | 0.24 | 直播即时转化更强，更依赖冲动消费；为便于模拟测试，提高内容触达覆盖 |
| `video_voucher` | 0.156 | 0.168 | 视频触达比直播弱，但提高可见性以减少连续 miss |

资格概率限制在：

```text
live_access_prob = clamp(content_access_score, 0.096, 0.66)
video_access_prob = clamp(content_access_score, 0.084, 0.576)
```

设计含义：

- 直播/视频券不是所有买家都能用，只覆盖被内容场景触达的买家。
- 冲动型买家、价格敏感买家、基础购买意愿高的买家更容易具备资格。
- 优惠力度越明显，内容场景券越容易推动转化。
- 资格判定只决定买家是否拥有候选资格，不决定最终是否用券。

### 4.3 场景资格稳定性

为了避免同一个 tick 内预览阶段和订单生成阶段资格不一致，直播/视频资格必须在一次 `simulate_orders_for_run()` 调用中稳定。

建议维护内存缓存：

```python
content_voucher_access_cache[(buyer_name, voucher_type, campaign_id)] = {
    "content_access_hit": bool,
    "content_access_prob": float,
    "content_scene": "live" | "video",
}
```

同一次模拟中：

- 第一次判定后写入缓存。
- 后续候选评分、订单生成复用同一结果。
- 不跨请求持久化，避免新增个人券实例表。

### 4.4 适用商品规则

直播/视频代金券支持全部商品和指定商品。

| `applicable_scope` | 规则 |
| --- | --- |
| `all_products` | 当前订单全部普通商品行小计都可参与门槛和优惠计算 |
| `selected_products` | 仅命中对应 item 表的商品行参与门槛和优惠计算 |

对应 item 表：

| 券类型 | 活动表 | 商品表 |
| --- | --- | --- |
| `live_voucher` | `shopee_live_voucher_campaigns` | `shopee_live_voucher_items` |
| `video_voucher` | `shopee_video_voucher_campaigns` | `shopee_video_voucher_items` |

指定商品匹配规则与商品券/专属券一致：

| 券明细 | 订单商品 | 是否命中 |
| --- | --- | --- |
| `listing_id=A, variant_id=null` | listing A 任意变体 | 命中 |
| `listing_id=A, variant_id=V1` | listing A + variant V1 | 命中 |
| `listing_id=A, variant_id=V1` | listing A + variant V2 | 不命中 |
| `listing_id=A` | listing B | 不命中 |

### 4.5 每单最多一张，存在可用券时必须使用最优券

直播/视频券接入后，店铺券、商品券、专属券、直播券、视频券进入统一候选池。

选择规则：

1. 收集所有可用店铺券、商品券、专属券、直播券、视频券。
2. 计算每张券的优惠金额。
3. 选择优惠金额最大的券。
4. 优惠金额相同时，优先级建议：商品代金券 > 直播代金券 > 视频代金券 > 专属代金券 > 店铺代金券。
5. 若仍相同，选择创建时间更早或 ID 更小的活动，保证结果稳定。
6. 如果没有任何可用券，则订单按无代金券逻辑生成。

优先级说明：

- 商品券绑定具体商品，归因最明确。
- 直播券强场景、强即时转化，优先于视频券。
- 视频券也有内容场景来源，但即时性弱于直播。
- 专属券具备买家资格限制，但不代表具体内容场景。
- 店铺券作为公开兜底券优先级最低。

### 4.6 优惠计算

直播/视频代金券作为订单级优惠，不改变商品行 `unit_price`。

```text
eligible_subtotal = 命中适用范围的商品行小计

if eligible_subtotal < voucher.min_spend_amount:
    voucher 不可用

if discount_type == fixed_amount:
    voucher_discount = discount_amount

if discount_type == percent:
    voucher_discount = eligible_subtotal * discount_percent / 100
    if max_discount_type == set_amount:
        voucher_discount = min(voucher_discount, max_discount_amount)

voucher_discount = min(voucher_discount, order_subtotal - 1)
buyer_payment = order_subtotal - voucher_discount
```

保留至少 1 RM 实付，避免 0 元订单影响现有订单、结算、库存和财务链路。

### 4.7 与已有营销活动的叠加关系

| 已有活动 | 第一版是否叠加直播/视频券 | 说明 |
| --- | --- | --- |
| 单品折扣 `discount` | 是 | 商品先按折扣价成交，订单结算再用券 |
| 套餐优惠 `bundle` | 是 | 套餐优惠后的订单小计再判断券门槛 |
| 加价购 `add_on` | 是 | 加价购商品计入订单小计；指定商品券只按命中商品行计算可抵扣小计 |
| 满额赠 `gift` | 是 | 赠品 0 元行不增加可抵扣金额 |
| 限时抢购 `flash_sale` | 否 | 与其他代金券保持一致，第一版避免爆量和归因混乱 |

## 5. 订单模拟接入设计

### 5.1 加载内容场景代金券上下文

在 `simulate_orders_for_run()` 中扩展代金券上下文加载：

```python
voucher_context = _load_ongoing_voucher_context(
    db,
    run_id=run_id,
    user_id=user_id,
    tick_time=now,
    include_content_vouchers=True,
)
```

建议返回结构扩展为：

```python
{
    "shop_vouchers": [ ... ],
    "product_vouchers_by_listing": { ... },
    "private_vouchers": [ ... ],
    "private_vouchers_by_listing": { ... },
    "live_vouchers": [ ... ],
    "live_vouchers_by_listing": { ... },
    "video_vouchers": [ ... ],
    "video_vouchers_by_listing": { ... },
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

直播/视频券加载时分别通过 `selectinload(...items)` 预取适用商品，避免订单循环内频繁查询。

### 5.2 买家限用统计

在模拟 tick 开始前，按当前进行中代金券 ID 查询历史订单中的买家使用次数。

维度继续使用订单级 voucher 字段：

```text
buyer_voucher_usage_counts[(buyer_name, voucher_type, voucher_campaign_id)] = count(order.id)
```

统计条件扩展为：

```text
ShopeeOrder.run_id == run_id
ShopeeOrder.user_id == user_id
ShopeeOrder.voucher_campaign_type in (
  'shop_voucher',
  'product_voucher',
  'private_voucher',
  'live_voucher',
  'video_voucher'
)
ShopeeOrder.voucher_campaign_id in 当前活动 ID 集合
```

### 5.3 内容场景资格判定函数

建议新增：

```python
def _buyer_has_content_voucher_access(
    *,
    buyer,
    voucher: dict,
    order_subtotal: float,
    content_access_cache: dict[tuple[str, str, int], dict[str, Any]],
    rng: random.Random,
) -> dict[str, Any]:
    ...
```

输出：

```json
{
  "content_access_checked": true,
  "content_access_hit": true,
  "content_access_prob": 0.28,
  "content_scene": "live",
  "content_access_reason": "simulated_live_viewer"
}
```

不可用原因：

| reason | 含义 |
| --- | --- |
| `not_content_access` | 买家未被直播/视频内容触达 |
| `flash_sale_excluded` | 限时抢购订单不叠加代金券 |
| `usage_limit_reached` | 活动总使用量已达上限 |
| `buyer_limit_reached` | 买家使用次数已达上限 |
| `not_applicable_product` | 订单商品不在适用范围 |
| `below_min_spend` | 可抵扣小计未达到门槛 |
| `eligible` | 可用候选券 |

### 5.4 候选商品评分阶段

候选商品评分时可计算“预计到手价”，用于提升内容种草后的价格感知：

```text
preview_order_subtotal = effective_price * min_purchase_qty
preview_content_access = 买家是否具备直播/视频场景资格
preview_voucher_discount = 可用券预计抵扣
preview_checkout_price = preview_order_subtotal - preview_voucher_discount
```

如果直播/视频场景资格命中且对应券成为最优预览券，则给订单概率增加 bonus。

### 5.5 下单概率影响

直播/视频券命中后，根据场景、优惠比例和买家冲动程度给订单概率增加小幅 bonus。

```python
voucher_savings_rate = voucher_discount / max(order_subtotal, 1)
scene_base = 0.02 if voucher_type == "live_voucher" else 0.014
scene_multiplier = 1.10 if voucher_type == "live_voucher" else 0.85
content_voucher_order_bonus = _clamp(
    scene_base
    + voucher_savings_rate * 0.08 * scene_multiplier
    + buyer_impulse_level * voucher_savings_rate * 0.08,
    0.0,
    0.085 if voucher_type == "live_voucher" else 0.065,
)
order_prob = _clamp(order_prob + content_voucher_order_bonus, order_prob, 0.92)
```

设计原则：

- 直播券更偏即时转化，bonus 上限略高。
- 视频券更偏内容种草，bonus 上限略低。
- 下单概率 bonus 只影响是否下单；一旦订单生成，有可用券就确定性使用最优券。
- 内容场景资格覆盖面有限，避免直播/视频券导致订单量异常膨胀。

### 5.6 生成订单阶段

在 `order_lines` 确定后、创建 `ShopeeOrder` 之前计算：

```text
order_subtotal = sum(line.unit_price * line.quantity)
selected_voucher = _resolve_best_voucher_for_order(...)
voucher_discount_amount = selected_voucher.discount_amount or 0
payment = order_subtotal - voucher_discount_amount
```

`_resolve_best_voucher_for_order(...)` 需扩展支持：

- 直播/视频内容场景资格检查。
- 直播/视频券 `all_products/selected_products` 适用范围。
- 直播/视频券门槛和优惠计算。
- 直播/视频券参与统一最优券排序。

只要返回非空，就必须应用到本单，不再做二次概率判断。

### 5.7 订单字段归因

继续复用现有订单级 voucher 字段。

| 字段 | 直播券订单写入 | 视频券订单写入 |
| --- | --- | --- |
| `order_subtotal_amount` | 代金券抵扣前订单商品小计 | 代金券抵扣前订单商品小计 |
| `voucher_campaign_type` | `live_voucher` | `video_voucher` |
| `voucher_campaign_id` | 直播代金券活动 ID | 视频代金券活动 ID |
| `voucher_name_snapshot` | 下单时直播代金券名称 | 下单时视频代金券名称 |
| `voucher_code_snapshot` | 下单时代金券代码 | 下单时内部代金券编号 |
| `voucher_discount_amount` | 本单直播券抵扣金额 | 本单视频券抵扣金额 |
| `buyer_payment` | `order_subtotal_amount - voucher_discount_amount` | `order_subtotal_amount - voucher_discount_amount` |

不建议写入旧的 `marketing_campaign_type` 字段，避免与单品折扣、套餐、加价购、满额赠、限时抢购归因混淆。

## 6. 统计回写设计

成功生成订单且直播/视频券被选中后，更新对应活动表：

| 字段 | 更新规则 |
| --- | --- |
| `used_count` | `+1` |
| `order_count` | `+1` |
| `sales_amount` | `+ buyer_payment` |
| `buyer_count` | 若该买家此前未使用过该券，则 `+1` |

同时更新内存中的：

```text
buyer_voucher_usage_counts[(buyer_name, voucher_type, campaign_id)] += 1
selected_voucher.used_count += 1
```

确保同一次模拟 tick 内后续订单能感知用量和买家限用变化。

## 7. 日志设计

`buyer_journeys.debug_payload_json` 建议新增/扩展字段：

```json
{
  "voucher_candidates": [
    {
      "voucher_type": "live_voucher",
      "campaign_id": 15,
      "voucher_name": "Live Exclusive",
      "voucher_code": "HOMELIVE1",
      "eligible": true,
      "reason": "eligible",
      "content_scene": "live",
      "content_access_hit": true,
      "content_access_prob": 0.28,
      "content_access_reason": "simulated_live_viewer",
      "eligible_subtotal": 188,
      "discount_amount": 20
    }
  ],
  "voucher_hit": true,
  "voucher_campaign_type": "live_voucher",
  "voucher_campaign_id": 15,
  "voucher_discount_amount": 20,
  "voucher_order_bonus": 0.052
}
```

视频券同样记录 `content_scene=video`、`voucher_campaign_type=video_voucher`。

为便于后续测试，应将预览阶段和最终订单阶段的 `voucher_candidates` 都保留在 `buyer_journeys` 中；即使买家最终未下单，也能看到内容场景资格是否命中、为何未用券。

## 8. 与现有代金券逻辑的关系

直播/视频券应尽量复用 42、43 号设计已实现的公共逻辑：

| 能力 | 复用方式 |
| --- | --- |
| 时间判断 | 复用 `_align_compare_time` |
| 序列化字段 | 扩展 `_serialize_voucher()` 支持 `live_voucher`、`video_voucher` |
| 优惠计算 | 复用 `_calculate_voucher_discount` |
| 商品匹配 | 复用商品券 listing/variant 匹配逻辑 |
| 最优券选择 | 扩展 `_resolve_best_voucher_for_order` |
| 统计回写 | 扩展 `_apply_voucher_stats` 支持直播/视频 campaign row |
| 订单展示 | 复用订单级 voucher 字段和买家实付列标注 |

前端订单列表只需在已有 voucher 标注函数中补充：

```text
live_voucher -> 直播代金券
video_voucher -> 视频代金券
```

## 9. 风险与边界

| 风险 | 处理 |
| --- | --- |
| 没有真实直播/视频观看行为，场景资格偏模拟 | 第一版用买家画像概率模拟内容触达，不持久化个人券实例 |
| 直播券 bonus 过高导致订单量异常 | 限制直播资格最高 38%，订单 bonus 最高 8.5% |
| 视频券覆盖面过大 | 限制视频资格最高 32%，订单 bonus 最高 6.5% |
| 与公开券同时存在时归因不清 | 统一最优券规则；同额按商品 > 直播 > 视频 > 专属 > 店铺排序 |
| 限时抢购叠加导致爆量 | 第一版明确不叠加限时抢购订单 |
| 预览日志无法查未下单资格 | 实现时需保留预览阶段 `voucher_candidates` 到 journey 顶层 |

## 10. 实现步骤建议

1. 后端模型接入
   - 在订单模拟服务 import `ShopeeLiveVoucherCampaign`、`ShopeeVideoVoucherCampaign`。
   - 扩展 `_serialize_voucher()` 支持 `live_voucher`、`video_voucher`。
   - 扩展 `_load_ongoing_voucher_context()` 加载进行中的直播/视频券和适用商品。

2. 内容场景资格接入
   - 新增 `_buyer_has_content_voucher_access()`。
   - 在一次模拟调用内维护 `content_access_cache`。
   - 在候选日志中记录资格概率、场景和命中结果。

3. 最优券选择接入
   - 扩展 `_resolve_best_voucher_for_order()` 支持直播/视频券。
   - 支持 `live_voucher`、`video_voucher` 的全部商品/指定商品匹配。
   - 排序规则改为商品券 > 直播券 > 视频券 > 专属券 > 店铺券。

4. 订单生成接入
   - 订单级 voucher 字段写入 `live_voucher` 或 `video_voucher`。
   - `buyer_payment` 扣减直播/视频券优惠。
   - 回写对应活动统计。

5. 前端展示接入
   - 订单列表 voucher label 增加 `live_voucher -> 直播代金券`、`video_voucher -> 视频代金券`。
   - 保持买家实付列标注样式不变。

6. 文档与验证
   - 更新 `docs/当前进度.md` 与 `docs/change-log.md`。
   - 后端执行 `python -m py_compile backend/apps/api-gateway/app/services/shopee_order_simulator.py`。
   - 前端执行 `MyOrdersView.tsx` LSP 诊断或 `npm run build --prefix frontend`。
   - 用本地对局创建直播/视频券后验证订单 `voucher_campaign_type in ('live_voucher', 'video_voucher')`。

## 11. 验收标准

- 当前游戏 tick 未到 `start_at` 的直播/视频券不会进入候选。
- 当前游戏 tick 已到 `end_at` 的直播/视频券不会进入候选。
- `used_count >= usage_limit` 的直播/视频券不会进入候选。
- 未命中内容场景资格的买家不会使用直播/视频券。
- 命中内容场景资格的买家，在商品范围、门槛、买家限用均满足时可使用直播/视频券。
- `all_products` 直播/视频券可命中店铺内普通订单。
- `selected_products` 直播/视频券只命中适用 listing/variant。
- 限时抢购订单不叠加直播/视频券。
- 多张券可用时，每单最多使用一张最优券。
- 直播券与视频券同额时优先直播券。
- 直播/视频券与商品券同额时优先商品券。
- 直播/视频券与专属券同额时优先直播/视频券。
- 订单生成时若直播券被选中，`voucher_campaign_type='live_voucher'`。
- 订单生成时若视频券被选中，`voucher_campaign_type='video_voucher'`。
- `buyer_payment = order_subtotal_amount - voucher_discount_amount`。
- `ShopeeOrderItem.unit_price` 不被直播/视频券改写。
- 成功用券后回写对应活动 `used_count/order_count/sales_amount/buyer_count`。
- `buyer_journeys` 能看到内容场景资格、候选券、命中券、优惠金额和概率 bonus。
- 未下单买家的预览阶段日志也能看到直播/视频券资格是否命中。
- 我的订单列表买家实付列能展示“直播代金券/视频代金券：名称 -抵扣金额”。

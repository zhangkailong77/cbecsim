# 43-Shopee 专属代金券接入订单模拟影响设计

> 创建日期：2026-05-08  
> 状态：设计完成，待实现

## 1. 目标

将已完成创建闭环的 Shopee 专属代金券接入订单模拟，使模拟买家在具备专属券资格后，能在下单决策、订单生成、实付金额、订单归因和活动统计中体现专属代金券影响。

本设计只覆盖：

- 专属代金券 `private_voucher`
- 买家专属资格模拟
- 订单模拟中的命中、优惠、下单概率、实付金额、归因和统计回写

不覆盖：

- 真实 Shopee 买家领券接口
- 站内信、聊天、外部链接分享
- 买家名单导入、人群包配置
- 专属代金券详情、编辑、删除、停止、复制
- 直播/视频/关注礼代金券订单影响

## 2. 游戏时间口径

专属代金券对订单模拟的所有时间判断统一使用对局游戏时间口径。

| 场景 | 口径 |
| --- | --- |
| 专属券开始/结束判断 | 使用订单模拟 tick 对应的游戏时间，与 `start_at/end_at` 比较 |
| 买家获得专属资格时间 | 第一版使用当前模拟 tick 即时判定，不生成长期个人券实例 |
| 订单用券发生时间 | 使用当前订单模拟 tick 时间 |
| 活动状态刷新 | 按当前游戏 tick 动态判断 `upcoming/ongoing/ended/sold_out` |
| 日志记录 | `buyer_journeys` 中记录当前 tick、资格来源、候选券和命中结果 |
| 统计口径 | 按游戏时间生成订单时同步更新活动统计 |

实现上继续复用现有时间函数：

- `_resolve_game_tick(db, run_id, user_id)`：解析当前对局 tick。
- `_align_compare_time(current_tick, row.start_at/end_at)`：比较时对齐时区/时间基准。
- `simulate_orders_for_run(..., tick_time=now)` 中的 `now` 视为本次模拟 tick。

## 3. 范围与非范围

### 3.1 本期范围

- 加载当前游戏 tick 下进行中的专属代金券。
- 为模拟买家计算是否具备专属代金券资格。
- 判断订单候选商品和订单小计是否满足专属券使用条件。
- 对可用专属券计算订单级优惠金额。
- 与店铺/商品代金券共用“每单最多一张券，存在可用券时必须使用最优券”的选择规则。
- 专属券提升具备资格买家的下单意愿，价格敏感买家提升更明显。
- 生成订单时若专属券被选为最优券，则扣减 `buyer_payment`，并保存订单级 voucher 快照字段。
- 成功生成订单后回写专属券 `used_count/order_count/sales_amount/buyer_count`。
- 在订单生成日志 `buyer_journeys` 中记录专属券资格、候选、命中和优惠过程。

### 3.2 非范围

- 不新增买家个人券实例表。
- 不实现真实领券库存、券包、领取按钮或领取记录页面。
- 不实现指定买家名单、人群包导入或 CRM 分层后台。
- 不新增前端页面。
- 不接入真实 Shopee 平台 API。
- 不改变已有店铺券/商品券使用规则。

## 4. 核心业务规则

### 4.1 专属代金券可用前提

专属代金券不同于店铺券/商品券，不是公开可用券。订单模拟中必须先判断买家是否具备专属资格，再进入代金券候选池。

专属券成为候选券需要同时满足：

1. `run_id/user_id` 与当前对局和卖家一致。
2. 当前游戏 tick 满足 `start_at <= tick < end_at`。
3. `used_count < usage_limit`。
4. 当前买家具备该专属券资格。
5. 当前买家对该券历史使用次数小于 `per_buyer_limit`。
6. 订单商品命中适用范围。
7. 订单可抵扣小计满足 `min_spend_amount`。
8. 本单不是限时抢购订单。

### 4.2 买家专属资格模拟

第一版采用方案 A：模拟指定人群。卖家创建专属代金券时不手动选择具体买家、不维护买家分组、不导入买家名单，也不生成发券记录或个人券实例；订单模拟按买家画像动态模拟“被私域触达、知道专属代码、具备专属券资格”的买家集合。

也就是说，第一版的“指定买家”不是 UI 上勾选买家，而是系统根据买家价格敏感度、促销偏好、老客倾向和券优惠力度，模拟一批更可能被专属券触达的人群。后续如果需要真实指定买家，再单独设计买家名单、买家分组、发券记录和个人券实例表。

建议资格概率使用买家行为特征和券吸引力综合计算：

```text
private_access_score =
  0.10
  + buyer.price_sensitivity * 0.18
  + buyer.loyalty_score * 0.12
  + buyer.discount_affinity * 0.15
  + voucher_savings_rate * 0.20
```

若现有买家画像缺少某些字段，则按当前已有字段降级：

| 优先字段 | 含义 | 缺失时替代 |
| --- | --- | --- |
| `price_sensitivity` | 买家对价格/优惠敏感度 | 默认 `0.5` |
| `loyalty_score` | 对店铺或商品复购倾向 | 可用历史订单数归一化替代 |
| `discount_affinity` | 对促销/券偏好 | 可用 `price_sensitivity` 替代 |
| `voucher_savings_rate` | 预计优惠占订单小计比例 | 由候选订单小计和券规则计算 |

资格概率建议限制在：

```text
private_access_prob = clamp(private_access_score, 0.05, 0.45)
```

设计含义：

- 专属券不是所有买家都能用，最高也只覆盖一部分买家。
- 价格敏感买家、促销偏好买家、老客更容易具备专属资格。
- 优惠力度越明显，买家越可能从私域渠道或代码分享中获得并使用。
- 资格判定只决定买家是否拥有候选资格，不决定最终是否用券。

### 4.3 专属资格稳定性

为了避免同一个 tick 内预览阶段和订单生成阶段资格不一致，专属资格必须在一次 `simulate_orders_for_run()` 调用中稳定。

建议维护内存缓存：

```python
private_voucher_access_cache[(buyer_name, campaign_id)] = bool
```

同一次模拟中：

- 第一次判定后写入缓存。
- 后续候选评分、订单生成复用同一结果。
- 不跨请求持久化，避免新增个人券实例表。

若后续需要真实“领券后 N 天有效”或长期资格，再新增个人券实例表单独设计。

### 4.4 适用商品规则

专属代金券支持全部商品和指定商品。

| `applicable_scope` | 规则 |
| --- | --- |
| `all_products` | 当前订单全部普通商品行小计都可参与门槛和优惠计算 |
| `selected_products` | 仅命中 `shopee_private_voucher_items` 的商品行参与门槛和优惠计算 |

指定商品匹配规则：

| 专属券明细 | 订单商品 | 是否命中 |
| --- | --- | --- |
| `listing_id=A, variant_id=null` | listing A 任意变体 | 命中 |
| `listing_id=A, variant_id=V1` | listing A + variant V1 | 命中 |
| `listing_id=A, variant_id=V1` | listing A + variant V2 | 不命中 |
| `listing_id=A` | listing B | 不命中 |

第一版订单当前主要以单主商品为核心，可复用商品券 listing/variant 匹配逻辑。若后续订单包含多个普通商品行，应按命中的商品行小计计算 `eligible_subtotal`。

### 4.5 每单最多一张，存在可用券时必须使用最优券

专属券接入后，店铺券、商品券、专属券进入统一候选池。

第一版每个模拟订单最多使用一张代金券；若买家在下单时存在生效且满足条件的任一类型代金券，则必须使用其中一张最优可用券，不再引入“是否使用代金券”的随机判断。

选择规则：

1. 收集所有可用店铺券、商品券、专属券。
2. 计算每张券的优惠金额。
3. 选择优惠金额最大的券。
4. 优惠金额相同时，优先级建议：商品代金券 > 专属代金券 > 店铺代金券。
5. 若仍相同，选择创建时间更早或 ID 更小的活动，保证结果稳定。
6. 如果没有任何可用券，则订单按无代金券逻辑生成。

优先级说明：

- 商品券通常绑定具体商品，归因最明确。
- 专属券具备买家资格限制，应优先于公开店铺券。
- 店铺券作为公开兜底券优先级最低。

### 4.6 优惠计算

专属代金券作为订单级优惠，不改变商品行 `unit_price`。

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

| 已有活动 | 第一版是否叠加专属券 | 说明 |
| --- | --- | --- |
| 单品折扣 `discount` | 是 | 商品先按折扣价成交，订单结算再用券 |
| 套餐优惠 `bundle` | 是 | 套餐优惠后的订单小计再判断券门槛 |
| 加价购 `add_on` | 是 | 加价购商品计入订单小计；指定商品券只按命中商品行计算可抵扣小计 |
| 满额赠 `gift` | 是 | 赠品 0 元行不增加可抵扣金额 |
| 限时抢购 `flash_sale` | 否 | 与店铺/商品券保持一致，第一版避免爆量和归因混乱 |

## 5. 订单模拟接入设计

### 5.1 加载专属代金券上下文

在 `simulate_orders_for_run()` 中扩展代金券上下文加载：

```python
voucher_context = _load_ongoing_voucher_context(
    db,
    run_id=run_id,
    user_id=user_id,
    tick_time=now,
    include_private_vouchers=True,
)
```

建议返回结构扩展为：

```python
{
    "shop_vouchers": [ ... ],
    "product_vouchers_by_listing": {
        (listing_id, variant_id): [ ... ],
        (listing_id, None): [ ... ],
    },
    "private_vouchers": [ ... ],
    "private_vouchers_by_listing": {
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

专属券加载时通过 `selectinload(ShopeePrivateVoucherCampaign.items)` 预取适用商品，避免订单循环内频繁查询。

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
ShopeeOrder.voucher_campaign_type in ('shop_voucher', 'product_voucher', 'private_voucher')
ShopeeOrder.voucher_campaign_id in 当前活动 ID 集合
```

### 5.3 专属资格判定函数

建议新增：

```python
def _buyer_has_private_voucher_access(
    *,
    buyer,
    voucher: dict,
    order_subtotal: float,
    private_access_cache: dict[tuple[str, int], bool],
) -> bool:
    ...
```

输入：

- 买家画像。
- 专属券序列化信息。
- 预估订单小计或最终订单小计。
- 本次模拟调用内的资格缓存。

输出：

- `True`：买家具备专属券资格，可进入候选池。
- `False`：买家没有获得该专属代码，本单不能使用该券。

日志中记录：

```json
{
  "private_access_checked": true,
  "private_access_hit": true,
  "private_access_prob": 0.32,
  "private_access_reason": "price_sensitive_discount_affinity"
}
```

### 5.4 候选商品评分阶段

候选商品评分时可计算“预计到手价”，用于提升价格感知：

```text
preview_order_subtotal = effective_price * min_purchase_qty
preview_private_access = 买家是否具备专属券资格
preview_voucher_discount = 可用券预计抵扣
preview_checkout_price = preview_order_subtotal - preview_voucher_discount
```

如果专属券资格命中且专属券成为最优预览券，则给订单概率增加 bonus。

### 5.5 下单概率影响

专属券命中后，根据优惠比例和买家价格敏感度给订单概率增加小幅 bonus。

```python
voucher_savings_rate = voucher_discount / max(order_subtotal, 1)
private_voucher_order_bonus = _clamp(
    0.015 + voucher_savings_rate * 0.09 + buyer_price_sensitivity * voucher_savings_rate * 0.08,
    0.0,
    0.075,
)
order_prob = _clamp(order_prob + private_voucher_order_bonus, order_prob, 0.92)
```

设计原则：

- 专属券能提升转化，但覆盖买家范围小于公开券。
- 价格敏感买家对专属券反应更明显。
- 下单概率 bonus 只影响是否下单；一旦订单生成，有可用券就确定性使用最优券。
- 上限略低于公开店铺/商品券，避免“私域券”带来过大订单量膨胀。

### 5.6 生成订单阶段

在 `order_lines` 确定后、创建 `ShopeeOrder` 之前计算：

```text
order_subtotal = sum(line.unit_price * line.quantity)
selected_voucher = _resolve_best_voucher_for_order(...)
voucher_discount_amount = selected_voucher.discount_amount or 0
payment = order_subtotal - voucher_discount_amount
```

`_resolve_best_voucher_for_order(...)` 需扩展支持：

- 专属券资格检查。
- 专属券 `all_products/selected_products` 适用范围。
- 专属券门槛和优惠计算。
- 专属券参与统一最优券排序。

只要返回非空，就必须应用到本单，不再做二次概率判断。

### 5.7 订单字段归因

继续复用现有订单级 voucher 字段。

| 字段 | 专属券订单写入 |
| --- | --- |
| `order_subtotal_amount` | 代金券抵扣前订单商品小计 |
| `voucher_campaign_type` | `private_voucher` |
| `voucher_campaign_id` | 专属代金券活动 ID |
| `voucher_name_snapshot` | 下单时专属代金券名称 |
| `voucher_code_snapshot` | 下单时代金券代码 |
| `voucher_discount_amount` | 本单专属券抵扣金额 |
| `buyer_payment` | `order_subtotal_amount - voucher_discount_amount` |

不建议写入旧的 `marketing_campaign_type` 字段，避免与单品折扣、套餐、加价购、满额赠、限时抢购归因混淆。

## 6. 统计回写设计

成功生成订单且专属券被选中后，更新 `ShopeePrivateVoucherCampaign`：

| 字段 | 更新规则 |
| --- | --- |
| `used_count` | `+1` |
| `order_count` | `+1` |
| `sales_amount` | `+ buyer_payment` |
| `buyer_count` | 若该买家此前未使用过该券，则 `+1` |

同时更新内存中的：

```text
buyer_voucher_usage_counts[(buyer_name, 'private_voucher', campaign_id)] += 1
selected_voucher.used_count += 1
```

确保同一次模拟 tick 内后续订单能感知用量和买家限用变化。

## 7. 日志设计

`buyer_journeys.debug_payload_json` 建议新增/扩展字段：

```json
{
  "voucher_candidates": [
    {
      "voucher_type": "private_voucher",
      "campaign_id": 12,
      "voucher_name": "VIP Exclusive",
      "voucher_code": "HOMEVIP01",
      "eligible": true,
      "reason": "eligible",
      "private_access_hit": true,
      "private_access_prob": 0.32,
      "eligible_subtotal": 188,
      "discount_amount": 30
    }
  ],
  "voucher_hit": true,
  "voucher_campaign_type": "private_voucher",
  "voucher_campaign_id": 12,
  "voucher_discount_amount": 30,
  "voucher_order_bonus": 0.046
}
```

不可用原因建议枚举：

| reason | 含义 |
| --- | --- |
| `not_private_access` | 买家未获得专属代码资格 |
| `flash_sale_excluded` | 限时抢购订单不叠加代金券 |
| `usage_limit_reached` | 活动总使用量已达上限 |
| `buyer_limit_reached` | 买家使用次数已达上限 |
| `not_applicable_product` | 订单商品不在适用范围 |
| `below_min_spend` | 可抵扣小计未达到门槛 |
| `eligible` | 可用候选券 |

## 8. 与现有店铺/商品代金券逻辑的关系

专属券应尽量复用 42 号设计已实现的公共逻辑：

| 能力 | 复用方式 |
| --- | --- |
| 时间判断 | 复用 `_align_compare_time` |
| 序列化字段 | 扩展 `_serialize_voucher` 支持 `private_voucher` |
| 优惠计算 | 复用 `_calculate_voucher_discount`，但入参支持 `eligible_subtotal` |
| 商品匹配 | 复用商品券 listing/variant 匹配逻辑 |
| 最优券选择 | 扩展 `_resolve_best_voucher_for_order` |
| 统计回写 | 扩展 `_apply_voucher_stats` 支持专属券 campaign row |
| 订单展示 | 复用订单级 voucher 字段和买家实付列标注 |

前端订单列表只需在已有 voucher 标注函数中补充：

```text
private_voucher -> 专属代金券
```

## 9. 风险与边界

| 风险 | 处理 |
| --- | --- |
| 没有真实领券行为，专属资格偏模拟 | 第一版用买家画像概率模拟资格，不持久化个人券实例 |
| 专属券覆盖面过大导致订单量异常 | `private_access_prob` 限制最高 45%，下单 bonus 最高 7.5% |
| 与公开券同时存在时归因不清 | 统一最优券规则；同额优先商品券，其次专属券，再店铺券 |
| 指定商品多行订单优惠口径复杂 | 第一版按命中商品行小计；当前订单结构以主商品为主，可逐步扩展 |
| 限时抢购叠加导致爆量 | 第一版明确不叠加限时抢购订单 |

## 10. 实现步骤建议

1. 后端模型接入
   - 在订单模拟服务 import `ShopeePrivateVoucherCampaign`。
   - 扩展 `_serialize_voucher()` 支持 `private_voucher`。
   - 扩展 `_load_ongoing_voucher_context()` 加载进行中的专属券和适用商品。

2. 买家资格接入
   - 新增 `_buyer_has_private_voucher_access()`。
   - 在一次模拟调用内维护 `private_access_cache`。
   - 在候选日志中记录资格概率和命中结果。

3. 最优券选择接入
   - 扩展 `_resolve_best_voucher_for_order()` 支持专属券。
   - 支持 `private_voucher` 的全部商品/指定商品匹配。
   - 排序规则改为商品券 > 专属券 > 店铺券。

4. 订单生成接入
   - 订单级 voucher 字段写入 `private_voucher`。
   - `buyer_payment` 扣减专属券优惠。
   - 回写专属券统计。

5. 前端展示接入
   - 订单列表 voucher label 增加 `private_voucher -> 专属代金券`。
   - 保持买家实付列标注样式不变。

6. 文档与验证
   - 更新 `docs/当前进度.md` 与 `docs/change-log.md`。
   - 后端执行 `python -m py_compile backend/apps/api-gateway/app/services/shopee_order_simulator.py backend/apps/api-gateway/app/api/routes/shopee.py`。
   - 前端执行 `MyOrdersView.tsx` LSP 诊断或 `npm run build --prefix frontend`。
   - 用本地对局创建专属券后验证订单 `voucher_campaign_type='private_voucher'`。

## 11. 验收标准

- 当前游戏 tick 未到 `start_at` 的专属券不会进入候选。
- 当前游戏 tick 已到 `end_at` 的专属券不会进入候选。
- `used_count >= usage_limit` 的专属券不会进入候选。
- 未命中专属资格的买家不会使用专属券。
- 命中专属资格的买家，在商品范围、门槛、买家限用均满足时可使用专属券。
- `all_products` 专属券可命中店铺内普通订单。
- `selected_products` 专属券只命中适用 listing/variant。
- 限时抢购订单不叠加专属券。
- 多张券可用时，每单最多使用一张最优券。
- 专属券与店铺券同额时优先专属券；专属券与商品券同额时优先商品券。
- 订单生成时若专属券被选中，`voucher_campaign_type='private_voucher'`。
- `buyer_payment = order_subtotal_amount - voucher_discount_amount`。
- `ShopeeOrderItem.unit_price` 不被专属券改写。
- 成功用券后回写专属券 `used_count/order_count/sales_amount/buyer_count`。
- `buyer_journeys` 能看到专属券资格、候选券、命中券、优惠金额和概率 bonus。
- 我的订单列表买家实付列能展示“专属代金券：名称 -抵扣金额”。

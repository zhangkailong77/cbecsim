# 30-Shopee加价购/满额赠接入订单模拟概率设计

> 创建日期：2026-04-28  
> 状态：设计完成，待实现

## 1. 目标

将 Shopee 加价购（`add_on`）与满额赠（`gift`）接入订单模拟器，使已创建且处于有效期内的活动在买家下单时真实生效。

目标效果：

- 加价购：买家命中主商品后，有概率额外购买加购商品，影响订单明细、成交金额、库存与营销归因。
- 满额赠：买家订单金额达到或接近门槛时，有概率凑单并在满足门槛后追加 0 元赠品明细，影响订单明细、赠品库存与营销归因。
- 保持单品折扣、套餐优惠现有概率链路不被替换。

## 2. 背景

当前加价购/满额赠已具备：

- 创建页 bootstrap、商品候选、草稿保存、正式创建、详情接口。
- `shopee_addon_campaigns`、主商品表、加购/赠品商品表、草稿表等数据结构。
- 折扣列表兼容记录：正式创建时同步写入 `shopee_discount_campaigns.campaign_type = "add_on"`，用于折扣首页 Tab 与列表展示。

但订单模拟尚未消费 `shopee_addon_campaigns` 活动，因此不会影响下单概率、订单明细、赠品/加购库存和经营结果。

## 3. 设计原则

1. **分层影响，不直接替代单品折扣**  
   加价购/满额赠不是商品直降，不应直接复用单品折扣的折后价替换逻辑。

2. **主商品先成立，再触发加价购/满额赠**  
   先沿用现有订单模拟器选品、选规格、单品折扣/套餐优惠逻辑，再判断是否触发加价购或满额赠。

3. **概率提升要弱于直接降价**  
   加价购/满额赠主要提升客单价、件数和凑单意愿，对是否下单只做小幅正向影响，避免压过单品折扣和套餐优惠。

4. **订单明细记录真实优惠来源**  
   加价购商品、赠品应以订单明细形式体现，避免只在订单头写一个营销类型导致归因丢失。

5. **库存是硬约束**  
   加购商品、赠品库存不足时不触发；已触发后必须按订单明细预占库存、发货扣减、取消释放。

## 4. 现有流程与新增位置

### 4.1 现有订单模拟主流程

```text
买家激活
  → 候选商品评分
  → 选出 best_listing / best_variant
  → 单品折扣或套餐优惠影响价格、数量、下单概率
  → 随机判断是否下单
  → 创建订单与订单明细
```

### 4.2 新增加价购/满额赠步骤

```text
买家激活
  → 候选商品评分
  → 选出 best_listing / best_variant
  → 单品折扣/套餐优惠现有逻辑
  → 计算 base_order_prob
  → 查询当前 SKU 可触发的加价购/满额赠活动
  → 计算 add_on/gift 对下单概率的轻量加成
  → 随机判断是否下单
  → 若下单：
      → 创建主商品订单明细
      → 尝试追加加价购商品明细
      → 尝试追加满额赠赠品明细
      → 预占对应库存
```

## 5. 活动加载设计

新增 `_load_ongoing_addon_map`，按游戏时间加载当前有效活动。

### 5.1 查询范围

- `ShopeeAddonCampaign.run_id == run_id`
- `ShopeeAddonCampaign.user_id == user_id`
- `campaign_status in ("ongoing", "upcoming")`，实际生效以 `start_at <= tick_time <= end_at` 判断
- `start_at <= tick_time`
- `end_at >= tick_time`

### 5.2 返回结构

建议按主商品 SKU 建 map：

```python
{
    (listing_id, variant_id_or_0): [
        {
            "campaign_id": 1,
            "promotion_type": "add_on" | "gift",
            "campaign_name": "活动名称",
            "addon_purchase_limit": 1,
            "gift_min_spend": 80.0,
            "reward_items": [...],
        }
    ]
}
```

说明：

- 主商品命中后才读取对应活动。
- 同一主商品同时命中多个加价购/满额赠活动时，V1 选择吸引力最高的一个活动生效。
- `variant_id=None` 的主商品规则适用于该 listing 下所有规格；具体匹配时优先精确规格，其次 listing 级规则。

## 6. 加价购概率设计

### 6.1 触发前提

- 买家已选中主商品，并通过最终下单判断。
- 主商品在有效加价购活动的主商品池内。
- 至少存在 1 个可售加购商品。
- 加价购价 `addon_price` 大于 0 且小于原价。
- 买家预算允许订单增加该加购金额。

### 6.2 加购吸引力

```python
savings_rate = clamp((original_price - addon_price) / original_price, 0.0, 0.95)

relative_price_factor = clamp(main_unit_price / max(addon_price, 0.01), 0.40, 1.60)
budget_factor = clamp(buyer_budget / (base_order_amount + addon_price), 0.45, 1.0)

addon_attach_prob = clamp(
    0.08
    + savings_rate * (0.45 + buyer.price_sensitivity * 0.35)
    + buyer.impulse_level * 0.10
    + (relative_price_factor - 1.0) * 0.04,
    0.0,
    0.55,
) * budget_factor
```

口径说明：

- 基础兴趣低于套餐优惠，避免加价购过度提升下单量。
- 节省比例越高，越容易加购。
- 冲动型买家更容易顺手加购。
- 加购价相对主商品越便宜，触发概率越高。
- 预算不足时降低触发概率。

### 6.3 加购商品选择

对所有可用加购商品计算吸引力分：

```python
addon_item_score = (
    savings_rate * 0.45
    + stock_score * 0.15
    + buyer.price_sensitivity * savings_rate * 0.20
    + buyer.impulse_level * 0.20
)
```

V1 可按得分最高的商品尝试加购；后续可扩展为加权随机。

### 6.4 加购数量

V1 按每笔订单限制：

```python
max_addon_qty = min(
    campaign.addon_purchase_limit or 1,
    reward_item.stock_snapshot,
    buyer_budget_remaining // addon_price,
)

addon_qty = 1
if max_addon_qty >= 2:
    extra_qty_prob = clamp(addon_attach_prob * 0.35, 0.0, 0.25)
    while addon_qty < max_addon_qty and rng.random() < extra_qty_prob:
        addon_qty += 1
        extra_qty_prob *= 0.55
```

## 7. 满额赠概率设计

### 7.1 触发前提

- 买家已选中主商品。
- 主商品在有效满额赠活动的主商品池内。
- 至少存在 1 个可售赠品。
- 活动配置 `gift_min_spend > 0`。

### 7.2 两类场景

| 场景 | 处理 |
|---|---|
| 订单金额已达到门槛 | 下单后直接尝试追加赠品明细 |
| 订单金额未达到门槛但差距不大 | 计算凑单概率，可能提高购买数量或追加可购买商品以达到门槛 |

V1 建议先支持：

- 已达门槛：追加赠品。
- 未达门槛但差额小于主商品单价或买家预算可承受：提高下单概率，但不强制复杂跨商品凑单。

### 7.3 满额赠对下单概率的轻量加成

```python
base_amount = main_unit_price * main_qty
threshold = campaign.gift_min_spend
shortfall = max(threshold - base_amount, 0.0)

if shortfall <= 0:
    threshold_factor = 1.0
else:
    threshold_factor = clamp(1.0 - shortfall / max(threshold, 0.01), 0.0, 1.0)

gift_value_rate = clamp(gift_original_price / max(base_amount, 1.0), 0.0, 0.50)
budget_factor = clamp(buyer_budget / max(threshold, base_amount), 0.45, 1.0)

gift_order_bonus = clamp(
    threshold_factor * 0.04
    + gift_value_rate * (0.08 + buyer.price_sensitivity * 0.04)
    + buyer.impulse_level * 0.03,
    0.0,
    0.08,
) * budget_factor

order_prob = max(base_order_prob, clamp(base_order_prob + gift_order_bonus, 0.05, 0.92))
```

说明：

- 满额赠对下单概率提升上限低于单品折扣和套餐优惠。
- 订单越接近门槛，赠品越有吸引力。
- 赠品价值只作为心理吸引，不直接当现金折扣全额计算。

### 7.4 赠品追加规则

若最终订单金额达到门槛：

```python
if order_amount >= gift_min_spend and gift_stock > 0:
    add_gift_item(
        quantity=reward_qty,
        unit_price=0,
        marketing_campaign_type="gift",
        marketing_campaign_id=campaign.id,
    )
```

V1 每笔订单最多追加 1 类赠品；如果活动配置多个赠品，选择库存充足且价值最高的赠品。

## 8. 与现有营销活动的关系

### 8.1 单品折扣

- 主商品仍可先按单品折扣价计算下单概率。
- 加价购/满额赠在主商品选定后追加，不覆盖单品折扣价。
- 同一订单可以同时存在：主商品单品折扣 + 加价购商品/赠品。

### 8.2 套餐优惠

- 套餐优惠仍控制主商品购买数量和组合明细。
- 若订单已经命中 `bundle`，V1 默认不再叠加加价购，避免同一主商品同时触发两个加购类活动导致概率过强。
- 满额赠可在 bundle 订单金额满足门槛时追加赠品，但下单概率加成不再重复叠加，只追加赠品明细。

### 8.3 多活动冲突优先级

建议 V1 优先级：

1. 套餐优惠：改变主商品数量/组合。
2. 单品折扣：改变主商品成交价。
3. 满额赠：满足门槛后追加赠品。
4. 加价购：未命中 bundle 时尝试追加加购商品。

同一层级多个活动命中时，选择“买家实际收益最高”的活动。

## 9. 订单与库存数据设计

### 9.1 订单头

现有订单头字段可继续保留主归因：

- `marketing_campaign_type`
- `marketing_campaign_id`
- `marketing_campaign_name_snapshot`

建议 V1 主归因规则：

- 若命中 bundle：订单头为 `bundle`。
- 否则若主商品命中单品折扣：订单头为 `discount`。
- 否则若追加加价购：订单头为 `add_on`。
- 否则若追加赠品：订单头为 `gift`。
- 若多个营销同时存在，订单头记录影响主商品成交的主归因，明细记录附加归因。

### 9.2 订单明细

建议补充或复用 item 级字段表达优惠来源。若现有 `shopee_order_items` 暂无营销字段，后续实现应新增：

| 字段 | 类型 | 说明 |
|---|---|---|
| `marketing_campaign_type` | string nullable | 明细命中的营销类型：`discount/bundle/add_on/gift` |
| `marketing_campaign_id` | int nullable | 对应营销活动 ID |
| `marketing_campaign_name_snapshot` | string nullable | 活动名称快照 |
| `line_role` | string | `main/add_on/gift/bundle_component` |
| `original_unit_price` | float | 原始单价 |
| `discounted_unit_price` | float | 实际成交单价，赠品为 0 |

字段注释要求：新增字段必须同步维护 column comment。

### 9.3 库存处理

- 加价购商品：按真实购买数量预占库存，发货时扣减，取消时释放。
- 赠品商品：按 0 元订单明细预占库存，发货时扣减，取消时释放。
- 库存不足时不触发对应加价购/赠品，不允许产生负库存。

## 10. 买家决策流水

建议在买家决策日志中补充字段，便于排查：

| 字段 | 说明 |
|---|---|
| `addon_campaign_id` | 命中的加价购活动 ID |
| `addon_applied` | 是否追加加价购商品 |
| `addon_attach_prob` | 加购触发概率 |
| `addon_savings_rate` | 加购商品节省比例 |
| `gift_campaign_id` | 命中的满额赠活动 ID |
| `gift_applied` | 是否追加赠品 |
| `gift_order_bonus` | 满额赠对下单概率的加成 |
| `gift_threshold_shortfall` | 距离满额赠门槛的差额 |

## 11. 接口影响

### 11.1 不新增卖家端创建接口

本设计复用已完成的加价购/满额赠创建接口：

- `GET /shopee/runs/{run_id}/marketing/add-on/create/bootstrap`
- `GET /shopee/runs/{run_id}/marketing/add-on/eligible-main-products`
- `GET /shopee/runs/{run_id}/marketing/add-on/eligible-reward-products`
- `POST /shopee/runs/{run_id}/marketing/add-on/drafts`
- `POST /shopee/runs/{run_id}/marketing/add-on/campaigns`

### 11.2 订单接口返回

订单列表与详情应能展示：

- 主商品折扣/套餐归因。
- 加价购商品明细。
- 满额赠赠品明细。
- 赠品明细单价为 0，数量真实扣库存。

若前端展示字段不足，实现阶段需同步扩展订单列表/详情响应。

## 12. Redis 与缓存失效

新增或复用缓存：

- 加价购/满额赠 active map 缓存：按 `run_id/user_id/tick_time` 或活动版本缓存。
- 创建、停用、编辑活动后失效：
  - 折扣列表缓存。
  - 加价购详情缓存。
  - 订单模拟营销活动缓存。
  - 折扣数据页缓存（若后续统计 add_on/gift）。

订单模拟中不要为每个买家重复查库，应在单 tick 内复用活动 map。

## 13. 验收标准

### 13.1 加价购

- 创建有效加价购活动后，买家购买主商品时有概率追加加购商品明细。
- 加购商品成交价使用活动配置的 `addon_price`。
- 加购商品库存被预占、发货扣减、取消释放。
- 买家决策流水记录加购概率与命中状态。
- 未命中主商品、活动未到期/已过期、库存不足时不触发。

### 13.2 满额赠

- 创建有效满额赠活动后，订单金额达到门槛时追加 0 元赠品明细。
- 订单金额接近门槛时，下单概率有小幅正向提升。
- 赠品库存被预占、发货扣减、取消释放。
- 买家决策流水记录门槛差额、赠品价值与命中状态。
- 库存不足时不追加赠品。

### 13.3 回归

- 单品折扣原有概率保底不变。
- 套餐优惠组合购买逻辑不变。
- 普通订单无营销活动时概率、数量和库存逻辑不变。
- 订单列表、订单详情能正确展示加价购商品和满额赠赠品明细。

## 14. 实施顺序建议

1. 后端加载有效加价购/满额赠活动 map。
2. 在订单模拟器中接入加价购/满额赠概率计算，但先只记录决策日志。
3. 接入订单明细追加与库存预占。
4. 扩展订单列表/详情响应与前端展示。
5. 补充缓存失效与数据页统计口径。
6. 使用固定随机种子和真实活动做回归验证。

## 15. 风险与边界

- 加价购/满额赠若对下单概率加成过大，会掩盖单品折扣和套餐优惠效果，因此 V1 加成必须保守。
- 订单头单一营销归因不足以表达多营销叠加，后续应优先使用明细级归因。
- 满额赠复杂凑单可能引入跨商品选择逻辑，V1 先只做接近门槛的小幅概率加成和达标赠品追加。
- 赠品为 0 元但仍消耗库存，库存链路必须与普通商品一致。

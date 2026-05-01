# 33-Shopee 限时抢购接入订单模拟概率设计

## 目标

将 Shopee 我的店铺限时抢购活动接入订单模拟，使有效活动在游戏时间窗口内影响买家下单概率、成交价、活动库存与订单归因。

本设计重点解决：当前自动订单模拟默认每 8 个游戏小时补跑一次，而限时抢购存在 3 游戏小时短时间段，若继续使用 8 小时粒度，可能错过 `18:00 - 21:00`、`21:00 - 00:00` 等短活动窗口。

## 时间口径

当前系统时间压缩口径：

- 7 天真实时间 = 365 个游戏日。
- `REAL_SECONDS_PER_GAME_DAY = 604800 / 365`。
- 1 个游戏日约 27.62 分钟真实时间。
- 1 个游戏小时约 69.04 秒真实时间。
- 当前普通自动订单模拟粒度为 8 个游戏小时，约 9.21 分钟真实时间。

限时抢购默认时间段：

| slot_key | 游戏时间段 | 游戏内时长 | 真实时间约等于 |
| --- | --- | ---: | ---: |
| `00_12` | 00:00 - 12:00 | 12 小时 | 13.81 分钟 |
| `12_18` | 12:00 - 18:00 | 6 小时 | 6.90 分钟 |
| `18_21` | 18:00 - 21:00 | 3 小时 | 3.45 分钟 |
| `21_00` | 21:00 - 00:00 +1 | 3 小时 | 3.45 分钟 |

## 总体流程

1. 自动订单模拟仍以当前对局 `last_tick -> current_game_tick` 为补跑窗口。
2. 若补跑窗口内没有有效限时抢购活动，保持现有 8 游戏小时粒度。
3. 若补跑窗口与任一有效限时抢购活动区间有交集，本轮自动补跑临时切为 1 游戏小时粒度。
4. 每个模拟 tick 独立判断是否命中限时抢购活动。
5. 只有 tick 落在活动窗口内的 active 活动商品，才使用限时抢购价格和概率倍率。
6. 活动结束后，新订单不再应用限时抢购价格或概率；历史订单保留活动归因。

## 自动模拟粒度规则

### 默认规则

普通订单模拟保持现有逻辑：

```text
step_seconds = REAL_SECONDS_PER_GAME_HOUR * 8
```

### 限时抢购窗口规则

当 `last_tick ~ current_game_tick` 与任一限时抢购活动 `[start_tick, end_tick)` 有交集时，本轮自动补跑改为：

```text
step_seconds = REAL_SECONDS_PER_GAME_HOUR * 1
```

交集判断：

```text
campaign.status = active
campaign.start_tick < current_game_tick
campaign.end_tick > last_tick
```

该规则用于避免短时间限时抢购被 8 小时模拟粒度跳过。

### 为什么不全局改为 1 小时

- 普通时间无需提高模拟频率，避免订单量和计算量整体放大。
- 只有限时抢购窗口需要小时级模拟机会。
- 活动结束后恢复 8 小时粒度，保持现有性能与节奏。

## 活动匹配规则

订单模拟器在每个 tick 加载当前 tick 有效的限时抢购活动：

```text
campaign.run_id = run.id
campaign.user_id = user_id
campaign.status = active
campaign.start_tick <= tick_time < campaign.end_tick
item.status = active
item.sold_qty < item.activity_stock_limit
```

只加载 active 商品。`disabled` 商品仅作为活动配置历史保留，不参与订单模拟。

## 时间段倍率

限时抢购在命中活动窗口时，对买家下单概率施加强活动倍率。

| slot_key | 游戏时间段 | 概率倍率 | 说明 |
| --- | --- | ---: | --- |
| `00_12` | 00:00 - 12:00 | `2.00` | 基础限时抢购加成，时长最长，冲动感最低 |
| `12_18` | 12:00 - 18:00 | `2.20` | 午后/傍晚活跃度更高 |
| `18_21` | 18:00 - 21:00 | `2.80` | 黄金晚高峰，最强抢购转化 |
| `21_00` | 21:00 - 00:00 +1 | `2.50` | 夜间冲动消费强，略低于晚高峰 |

建议第一版设置概率上限：

```text
FLASH_SALE_PROBABILITY_CAP = 0.85
```

避免倍率过高导致命中活动后几乎必定下单。

## 概率公式

限时抢购不直接替换普通概率链路，而是在普通概率基础上做优惠增强。

```text
base_prob = 现有普通订单模拟概率
flash_sale_discount_boost = 折扣吸引力增强
slot_multiplier = 时间段倍率

flash_sale_prob = base_prob * flash_sale_discount_boost * slot_multiplier
final_prob = min(max(base_prob, flash_sale_prob), FLASH_SALE_PROBABILITY_CAP)
```

原则：

- 有效限时抢购不应降低原本下单概率，因此使用 `max(base_prob, flash_sale_prob)` 保底。
- 概率必须有上限，避免倍率组合导致订单失真。
- 折扣吸引力可参考现有单品折扣/套餐优惠概率链路，但限时抢购使用自己的 slot multiplier。

## 成交价规则

命中限时抢购时：

- 使用 `ShopeeFlashSaleCampaignItem.flash_price` 作为主商品成交价。
- 订单明细记录原价、成交价与限时抢购活动归因。
- 主商品不再应用单品折扣、套餐优惠、加价购、满额赠等其他营销活动。

未命中限时抢购时：

- 继续使用现有普通订单/其他营销活动逻辑。

## 营销活动优先级

第一版限时抢购优先级最高，且与其他营销活动互斥。

```text
限时抢购 > 套餐优惠 > 单品折扣 > 加价购/满额赠
```

执行点：

- 若订单主商品命中限时抢购，则主商品成交价固定使用 `flash_price`。
- 该主商品不再应用单品折扣、套餐优惠、加价购、满额赠。
- 订单主归因与主商品明细归因均以限时抢购为准。
- 未命中限时抢购的商品，才继续进入现有套餐优惠、单品折扣、加价购、满额赠逻辑。

原因：

- 限时抢购是明确时间窗口内的专属价格。
- `flash_price` 已经代表该时间段的最终促销价。
- 与其他营销活动叠加会使成交价、概率、活动库存和归因复杂化。

## 库存与限购规则

活动库存以创建限时抢购时设置的 `ShopeeFlashSaleCampaignItem.activity_stock_limit` 为准。下单前必须同时满足：

```text
item.status = active
item.sold_qty < item.activity_stock_limit
qty <= item.activity_stock_limit - item.sold_qty
商品真实库存 > 0
买家在该活动 SKU 下累计购买件数 < purchase_limit_per_buyer
qty <= purchase_limit_per_buyer - 买家在该活动 SKU 下累计购买件数
```

限购口径：

- 限时抢购更接近 SKU 限购，`purchase_limit_per_buyer` 按买家在该活动 SKU 下的累计购买件数统计。
- 统计维度优先使用 `buyer_name + campaign_item_id`；若第一版不新增 `campaign_item_id` 字段，则使用 `buyer_name + campaign_id + listing_id + variant_id` 等价识别。
- 不按订单数统计，避免单笔多件订单绕过 SKU 限购。

下单成功后，需在同一数据库事务内更新活动库存与活动统计：

```text
ShopeeFlashSaleCampaignItem.sold_qty += qty
ShopeeFlashSaleCampaign.order_count += 1
ShopeeFlashSaleCampaign.sales_amount += flash_price * qty
```

同时沿用现有订单库存预占/扣减链路，避免真实库存和活动库存不一致。

## 订单归因

限时抢购成交订单需要记录：

```text
marketing_campaign_type = flash_sale
marketing_campaign_id = campaign.id
marketing_campaign_name_snapshot = campaign.campaign_name
```

订单明细需要能识别：

- 该明细是否由限时抢购成交。
- 使用的 `campaign_item_id` 或等价 SKU 归因信息。
- 原价与限时抢购成交价。

若现有订单表/订单明细表字段已支持通用营销归因，可复用现有字段，不新增表结构。

## Redis 与缓存失效

限时抢购订单生成后需要失效：

- Shopee 订单列表缓存。
- Shopee 订单详情相关缓存。
- 限时抢购活动列表缓存。
- 限时抢购活动详情缓存。
- 后续若新增限时抢购数据页，需要同步失效数据页缓存。

缓存失效应在订单模拟成功提交后执行，保证读后立即可见。

## 验收标准

### 1. 模拟粒度验收

- 创建 `18_21` 限时抢购活动。
- 将对局推进到覆盖 `18:00 - 21:00` 的补跑窗口。
- 自动订单模拟本轮使用 1 游戏小时粒度补跑。
- 活动窗口外仍保持 8 游戏小时粒度。

### 2. 活动命中验收

- tick 落在 `campaign.start_tick <= tick_time < campaign.end_tick` 时，active 活动商品参与限时抢购概率计算。
- tick 不在活动窗口内时，不使用 `flash_price`，不应用限时抢购倍率。
- `disabled` 活动商品不参与订单模拟。

### 3. 概率验收

- `00_12` 使用倍率 `2.00`。
- `12_18` 使用倍率 `2.20`。
- `18_21` 使用倍率 `2.80`。
- `21_00` 使用倍率 `2.50`。
- 最终概率不超过 `0.85`。
- 有效限时抢购不降低原本下单概率。

### 4. 成交价与归因验收

- 命中限时抢购的订单明细使用 `flash_price`。
- 订单记录 `marketing_campaign_type=flash_sale`。
- 订单记录正确的活动 ID 与活动名称快照。
- 活动 `sold_qty/order_count/sales_amount` 随订单生成更新。

### 5. 库存与限购验收

- 活动库存以创建限时抢购时设置的 `activity_stock_limit` 为准。
- 活动剩余库存不足本次 `qty` 时不再命中该活动商品。
- 真实库存不足时不生成订单。
- 买家在该活动 SKU 下累计购买件数达到 `purchase_limit_per_buyer` 后不再命中该活动商品。
- 限购按累计购买件数统计，不按订单数统计。

## 风险与边界

- 倍率从 `2.00` 起步会明显提高订单量，需要概率上限保护。
- 1 游戏小时临时粒度会增加活动窗口内模拟次数，但只在补跑窗口覆盖限时抢购时生效，整体性能影响可控。
- 第一版不做活动叠加，避免成交价和归因复杂化。
- 若后续需要限时抢购数据页，应补充活动点击、提醒、销量、销售额趋势等统计口径。

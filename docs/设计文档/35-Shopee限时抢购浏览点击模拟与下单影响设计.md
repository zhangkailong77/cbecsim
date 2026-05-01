# 35-Shopee 限时抢购浏览点击模拟与下单影响设计

> 创建日期：2026-04-30  
> 状态：设计完成，待实现

## 1. 目标

为 Shopee 我的店铺限时抢购活动新增“浏览 / 点击”流量模拟能力，使数据页中的 `商品浏览量`、`商品点击数`、`点击率（CTR）` 不再依赖静态占位或订单反推，而是来自独立的买家行为模拟。

本设计同时定义浏览、点击对最终下单的间接影响：

- 浏览表示买家看到限时抢购活动商品，是轻量兴趣信号。
- 点击表示买家对活动商品产生更强兴趣，可提高后续候选商品权重与下单概率。
- 下单仍由现有订单模拟器决定，继续受价格、库存、买家画像、限购、营销互斥等规则约束。

提醒设置数本期不模拟，统一保持 `0`。

## 2. 范围与非范围

### 2.1 本期范围

- 新增限时抢购流量事件模型设计：
  - `view`：商品浏览。
  - `click`：商品点击。
- 新增浏览/点击模拟规则：
  - 活动未开始前可产生少量预热浏览/点击。
  - 活动进行中产生主要浏览/点击。
  - 活动结束后不再产生新流量事件。
- 新增浏览/点击对下单的间接影响：
  - 近期浏览轻微提高候选商品权重和下单概率。
  - 近期点击明显提高候选商品权重和下单概率。
  - 增强因子设置上限，避免点击后必定下单。
- 数据页指标口径调整：
  - `商品浏览量 = view 事件数`。
  - `商品点击数 = click 事件数`。
  - `CTR = click / view`，浏览量为 0 时为 `0.00%`。
  - `提醒设置数 = 0`。
- Redis 缓存失效：新增流量事件后失效限时抢购数据页缓存。

### 2.2 非范围

- 不模拟提醒设置行为，提醒设置数固定为 0。
- 不接入真实 Shopee 流量、曝光或广告 API。
- 不做站外广告、搜索推荐、自然流量来源拆分。
- 不实现真实买家端页面点击路径，只做后台经营数据需要的模拟事件。
- 不让点击直接生成订单；点击只作为订单模拟概率增强因素。
- 不改变现有限时抢购成交价、活动库存、买家限购和营销互斥优先级。

## 3. 业务漏斗

限时抢购活动采用简化漏斗：

```text
活动曝光机会 -> 商品浏览(view) -> 商品点击(click) -> 下单(order)
```

本期不加入 `reminder`：

```text
提醒设置数 = 0
```

| 行为 | 含义 | 与下单关系 |
| --- | --- | --- |
| `view` | 买家在限时抢购区域看到某个活动商品 | 轻微提高该买家后续选择该商品的概率 |
| `click` | 买家点击活动商品卡或进入商品详情 | 明显提高该买家后续选择该商品的概率 |
| `order` | 买家最终下单 | 仍由订单模拟器按库存、价格、买家画像等综合决策 |

基本约束：

```text
商品浏览量 >= 商品点击数
点击率 CTR = 商品点击数 / 商品浏览量
```

订单数不要求小于点击数，但在正常模拟参数下应与点击数保持同量级，不应长期出现“极少点击但大量订单”。

## 4. 模拟时段规则

### 4.1 未开始活动

未开始活动可以产生预热流量，但强度较低。

建议预热窗口：

```text
活动开始前 24 游戏小时内
```

规则：

- 距离开始时间越近，浏览概率越高。
- 未开始阶段只生成 `view/click`，不生成订单。
- 因本期不做提醒，点击不会转化为提醒设置。

预热因子建议：

| 距离开始时间 | `preheat_factor` |
| --- | ---: |
| `0 ~ 3` 游戏小时 | `0.70` |
| `3 ~ 6` 游戏小时 | `0.50` |
| `6 ~ 12` 游戏小时 | `0.30` |
| `12 ~ 24` 游戏小时 | `0.15` |
| 超过 24 游戏小时 | `0` |

### 4.2 进行中活动

进行中活动是浏览/点击主来源。

规则：

- 当前 tick 落在 `start_tick <= tick < end_tick` 的 active 活动参与流量模拟。
- 只模拟 active 活动商品；disabled 商品不生成新流量。
- 已售罄活动商品可保留少量浏览，但点击概率降低；V1 可直接跳过已售罄商品，降低复杂度。
- 时间段倍率沿用限时抢购订单模拟设计中的 slot 热度，但作用于流量概率。

建议流量时段倍率：

| slot_key | 游戏时间段 | `traffic_slot_multiplier` |
| --- | --- | ---: |
| `00_12` | 00:00 - 12:00 | `1.00` |
| `12_18` | 12:00 - 18:00 | `1.15` |
| `18_21` | 18:00 - 21:00 | `1.45` |
| `21_00` | 21:00 - 00:00 +1 | `1.30` |

### 4.3 已结束活动

活动结束后：

- 不再生成新的浏览/点击事件。
- 数据页继续读取历史流量事件和订单归因。
- 历史回溯只读模式仅查询，不触发补模拟。

## 5. 买家与商品评分规则

### 5.1 买家参与概率

流量模拟应复用现有买家池画像中的活跃概率、冲动系数、价格敏感度等字段。

建议基础公式：

```text
buyer_traffic_prob = active_probability
  * campaign_phase_factor
  * traffic_slot_multiplier
```

其中：

- `active_probability`：买家当前游戏小时活跃概率。
- `campaign_phase_factor`：未开始预热或进行中阶段因子。
- `traffic_slot_multiplier`：限时抢购时间段流量倍率。

### 5.2 商品浏览概率

单个活动商品的浏览概率由折扣吸引力、价格可接受度、库存状态与随机扰动组成。

建议公式：

```text
view_prob = base_view_prob
  * discount_attraction
  * price_affordability
  * stock_factor
  * buyer_interest_factor
```

建议取值：

| 因子 | 说明 |
| --- | --- |
| `base_view_prob` | 基础浏览概率，首版固定为 `0.30` |
| `discount_attraction` | 折扣越大越高，建议范围 `1.00 ~ 1.80` |
| `price_affordability` | 商品价格越贴合买家购买力越高，建议范围 `0.50 ~ 1.20` |
| `stock_factor` | 活动库存充足为 `1.00`，库存紧张可略增稀缺感但需限制上限 |
| `buyer_interest_factor` | 可复用买家类目偏好或随机兴趣，建议范围 `0.80 ~ 1.20` |

浏览概率上限建议：

```text
view_prob <= 0.75
```

说明：`base_view_prob=0.30` 是在“当前买家已活跃、活动商品具备展示资格”的前提下计算，不代表全买家无条件 30% 浏览；最终浏览量仍会受买家活跃抽样、活动阶段、时间段倍率、商品折扣和价格适配共同约束。

### 5.3 商品点击概率

点击必须建立在浏览基础上：

```text
只有生成 view 后，才判断是否生成 click
```

建议公式：

```text
click_prob = base_click_prob
  * discount_attraction
  * buyer_impulse_factor
  * price_affordability
```

建议取值：

| 因子 | 说明 |
| --- | --- |
| `base_click_prob` | 基础点击概率，建议 `0.08 ~ 0.18` |
| `discount_attraction` | 折扣越大越容易点击 |
| `buyer_impulse_factor` | 冲动型买家更容易点击 |
| `price_affordability` | 价格超出购买力时点击降低 |

点击概率上限建议：

```text
click_prob <= 0.45
```

## 6. 对下单模拟的间接影响

### 6.1 原则

浏览/点击是下单前的兴趣信号，但不直接生成订单。

订单模拟仍保持现有限时抢购规则：

- 有效活动窗口内才可命中限时抢购成交价。
- 活动库存必须充足。
- 买家限购必须满足。
- 与套餐优惠、单品折扣、加价购/满额赠按既有优先级互斥。
- 总下单概率仍受上限约束。

### 6.2 近期事件窗口

下单模拟读取近期事件作为增强因子。

建议窗口：

```text
当前 tick 前 24 游戏小时内
```

只统计同一买家、同一活动商品维度：

```text
buyer_code + campaign_item_id
```

若 `campaign_item_id` 不方便传递，可退化为：

```text
buyer_code + campaign_id + listing_id + variant_id
```

### 6.3 候选商品权重增强

如果买家近期看过或点过该活动商品，候选商品评分增强：

```text
traffic_candidate_boost = 1.00
  + min(view_count, 3) * 0.03
  + min(click_count, 2) * 0.10
```

上限：

```text
traffic_candidate_boost <= 1.30
```

候选评分应用：

```text
candidate_score *= traffic_candidate_boost
```

### 6.4 下单概率增强

最终下单概率增强：

```text
traffic_order_boost = 1.00
  + min(view_count, 3) * 0.02
  + min(click_count, 2) * 0.08
```

上限：

```text
traffic_order_boost <= 1.25
```

限时抢购最终概率：

```text
flash_sale_prob = base_prob
  * flash_sale_discount_boost
  * slot_multiplier
  * traffic_order_boost

final_prob = min(max(base_prob, flash_sale_prob), FLASH_SALE_PROBABILITY_CAP)
```

其中 `FLASH_SALE_PROBABILITY_CAP` 继续沿用 33 号设计建议的 `0.85`。

### 6.5 防止强耦合

必须避免以下错误口径：

- 不允许 `click` 直接创建订单。
- 不允许根据订单数反推点击数作为真实流量。
- 不允许点击后绕过库存、限购或营销互斥。
- 不允许流量增强使最终概率超过总上限。

## 7. 数据模型设计

> 若实现时新增数据库表或字段，必须同步添加 table comment / column comment，并在初始化脚本或迁移脚本中维护注释。

### 7.1 `shopee_flash_sale_traffic_events`

限时抢购流量事件表，用于记录模拟生成的浏览与点击。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint pk | 事件 ID |
| `run_id` | bigint | 对局 ID |
| `user_id` | bigint | 卖家用户 ID |
| `campaign_id` | bigint | 限时抢购活动 ID |
| `campaign_item_id` | bigint | 限时抢购活动商品 ID |
| `listing_id` | bigint | Shopee listing ID |
| `variant_id` | bigint null | Shopee 规格 ID，单规格可为空 |
| `buyer_code` | varchar(64) | 买家画像编号，例如 `BYR001` |
| `event_type` | varchar(16) | 事件类型：`view/click` |
| `event_tick` | datetime | 事件发生的游戏时间 |
| `source` | varchar(32) | 事件来源：`simulator` |
| `created_at` | datetime | 创建时间 |

约束建议：

- `event_type` 仅允许 `view/click`。
- `campaign_item_id` 必填，确保数据页可以按活动商品聚合。
- 同一买家同一 tick 对同一活动商品最多写入一次 `view` 和一次 `click`。

索引建议：

| 索引 | 字段 | 用途 |
| --- | --- | --- |
| `idx_flash_sale_traffic_campaign_event` | `run_id, user_id, campaign_id, event_type, event_tick` | 数据页按活动统计浏览/点击 |
| `idx_flash_sale_traffic_item_buyer` | `run_id, user_id, campaign_item_id, buyer_code, event_type, event_tick` | 下单模拟读取买家近期兴趣 |
| `idx_flash_sale_traffic_listing` | `run_id, user_id, listing_id, variant_id, event_type` | 商品维度聚合 |

### 7.2 数据页指标来源

34 号数据页设计中的指标调整为：

| 指标 | 来源 |
| --- | --- |
| 提醒设置数 | 固定 `0` |
| 商品浏览量 | `count(*) where event_type='view'` |
| 商品点击数 | `count(*) where event_type='click'` |
| CTR | `click_count / view_count`，`view_count=0` 时为 `0.00%` |
| 销售额 | 订单明细限时抢购归因统计 |
| 订单数 | 订单明细限时抢购归因去重订单数 |

### 7.3 商品排名扩展

商品排名表格可增加或内部返回以下字段，前端可按页面需要选择展示：

| 字段 | 说明 |
| --- | --- |
| `view_count` | 当前商品或变体浏览量 |
| `click_count` | 当前商品或变体点击量 |
| `ctr` | 点击率 |

当前前端截图列只展示销售额、订单数、件数，因此 V1 可先只在接口内部用于指标卡，不强制展示到商品排名列。

## 8. 后端流程设计

### 8.1 新增模拟函数

建议在订单模拟器中新增轻量函数：

```python
simulate_flash_sale_traffic_events(session, run, user_id, tick_time, buyers, active_campaigns)
```

职责：

1. 加载当前 tick 相关限时抢购活动：
   - 进行中活动。
   - 开始前 24 游戏小时内的 upcoming 活动。
2. 按买家活跃概率抽样。
3. 按活动商品计算 `view_prob`。
4. 命中 view 后写入 `view` 事件。
5. 在 view 基础上计算 `click_prob`。
6. 命中 click 后写入 `click` 事件。
7. 返回本 tick 的流量摘要，供管理员模拟日志展示或调试。

### 8.2 与订单模拟顺序

推荐顺序：

```text
1. 计算当前 tick
2. 模拟限时抢购 view/click 流量事件
3. 读取近期 view/click 事件
4. 进入现有下单候选商品评分
5. 对命中限时抢购活动商品应用 traffic boost
6. 按现有订单模拟规则决定是否下单
```

这样可以让同一 tick 刚产生的点击对本轮下单产生轻量影响，也可以只影响后续 tick。若担心同 tick 因果过强，可采用：

```text
只读取 event_tick < 当前 tick 的历史事件
```

首版建议读取 `<= 当前 tick`，但 traffic boost 上限保持较低。

### 8.3 事件写入限制

为避免事件量过大，增加硬限制：

| 限制 | 建议值 |
| --- | ---: |
| 每个 tick 最大参与买家数 | `20` |
| 每个买家每个 tick 最大浏览商品数 | `3` |
| 每个 tick 最大事件数 | `200` |
| 每个买家同一活动商品同一 tick 最大 view | `1` |
| 每个买家同一活动商品同一 tick 最大 click | `1` |

### 8.4 管理员模拟摘要

管理员“模拟一小时订单”摘要可后续补充流量统计：

```json
{
  "flash_sale_traffic": {
    "view_count": 18,
    "click_count": 4,
    "campaign_count": 1,
    "buyer_count": 12
  }
}
```

该摘要不是 V1 前端必须展示项，可先用于日志和调试。

## 9. Redis 与缓存失效

### 9.1 数据页缓存影响

新增流量事件后，应失效 34 号设计的数据页缓存：

```text
shopee:flash_sale:data:{run_id}:{user_id}:
shopee:flash_sale:data_products:{run_id}:{user_id}:
```

### 9.2 可选近期兴趣缓存

若查询近期事件影响订单模拟性能，可增加短 TTL 聚合缓存：

```text
shopee:flash_sale:traffic_interest:{run_id}:{user_id}:{buyer_code}:{campaign_item_id}
```

TTL：

```text
1 ~ 5 分钟真实时间
```

首版可直接查数据库，待数据量变大再加缓存。

### 9.3 限流与降级

- 流量模拟运行在订单模拟内部，不单独暴露用户调用接口。
- Redis 不可用时不影响事件写入和订单模拟。
- 数据页缓存失效失败只记录日志，不阻断模拟。

## 10. 验收标准

### 10.1 流量事件验收

- 有 upcoming 限时抢购活动且处于开始前 24 游戏小时内时，可以产生少量 `view/click`。
- 有 ongoing 限时抢购活动时，可以产生主要 `view/click`。
- ended 或 disabled 活动不再产生新事件。
- disabled 活动商品不产生新事件。
- `click` 事件必须有对应浏览判断过程，不允许脱离浏览直接批量生成点击。

### 10.2 数据页验收

- 提醒设置数固定显示 `0`。
- 商品浏览量读取 `view` 事件数。
- 商品点击数读取 `click` 事件数。
- CTR 在浏览量为 0 时显示 `0.00%`。
- 正常情况下浏览量大于等于点击数。
- 订单生成后，销售额/订单数仍按订单明细归因统计，不从流量事件反推。

### 10.3 下单影响验收

- 同一买家近期点击过的限时抢购活动商品，后续被选为候选商品的概率应高于未点击商品。
- 点击只提高概率，不保证成交。
- 无浏览/点击事件时，订单模拟仍可按现有限时抢购概率运行。
- traffic boost 不得使最终下单概率超过 `FLASH_SALE_PROBABILITY_CAP`。
- 库存不足、活动库存售罄、买家限购达到上限时，即使有点击也不能下单。

### 10.4 性能验收

- 单个 tick 写入事件数受上限控制。
- 数据页按活动统计浏览/点击有索引支撑。
- 订单模拟读取近期兴趣事件不会引入大表全表扫描。

## 11. 对现有设计文档的影响

### 11.1 对 34 号数据页设计的调整

34 号设计中的指标口径建议调整为：

```text
提醒设置数 = 0
商品浏览量 = shopee_flash_sale_traffic_events 中 view 数
商品点击数 = shopee_flash_sale_traffic_events 中 click 数
CTR = click / view
```

不再使用活动表 `reminder_count/click_count` 作为主口径；若历史活动无事件，则返回 0。

### 11.2 对 33 号订单模拟概率设计的补充

33 号设计中的限时抢购概率公式可追加 `traffic_order_boost`：

```text
flash_sale_prob = base_prob
  * flash_sale_discount_boost
  * slot_multiplier
  * traffic_order_boost
```

但总概率上限不变，仍建议：

```text
FLASH_SALE_PROBABILITY_CAP = 0.85
```

## 12. 后续扩展

- 增加提醒设置模拟，但本期不做。
- 增加流量来源拆分：活动页、商品详情、推荐位、搜索。
- 增加趋势图：按游戏小时展示浏览、点击、CTR、订单数和销售额。
- 增加买家兴趣记忆，让多次点击在更长游戏周期内影响同品类偏好。
- 增加管理员调参面板，配置基础浏览概率、点击概率和 traffic boost 上限。
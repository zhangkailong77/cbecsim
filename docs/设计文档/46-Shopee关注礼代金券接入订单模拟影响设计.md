# 46-Shopee 关注礼代金券接入订单模拟影响设计

## 1. 目标

将 Shopee 关注礼代金券 `follow_voucher` 接入订单模拟，使其在对局游戏时间内影响买家下单概率、订单实付、订单级代金券归因和活动统计。

本设计只定义后续实现方案，不在本次改动中修改前后端代码。

## 2. 背景

当前关注礼代金券已完成创建页、后端创建接口、数据库表、Redis 缓存、统一代金券列表、详情页和代金券订单页兼容，但尚未接入订单模拟。

已存在数据基础：

- `shopee_follow_voucher_campaigns`
  - 保存领取期限、领取后有效游戏天数、奖励规则、使用数量和归因统计。
- `shopee_orders`
  - 已具备订单级代金券归因字段：`voucher_campaign_type`、`voucher_campaign_id`、`voucher_name_snapshot`、`voucher_code_snapshot`、`voucher_discount_amount`、`order_subtotal_amount`。
- `shopee_order_simulator.py`
  - 已接入店铺、商品、专属、直播和视频代金券，但未包含 `follow_voucher`。

## 3. 范围

本期后续实现应覆盖：

1. 在订单模拟中加载当前游戏 tick 可领取/可使用的关注礼代金券。
2. 按买家画像模拟“关注店铺并领取关注礼”的资格。
3. 按 `valid_days_after_claim` 计算领取后个人有效期。
4. 将有效关注礼代金券纳入最优券候选池。
5. 影响下单概率、订单实付和订单级 voucher 归因。
6. 新增买家关注状态表，持久化每个模拟买家对当前店铺是否已关注、首次关注时间和关注来源。
7. 回写活动统计：`claimed_count`、`used_count`、`order_count`、`sales_amount`、`buyer_count`。
8. 在订单模拟日志中记录关注礼候选、关注状态、领取、有效期、命中和跳过原因。

## 4. 非范围

本期不做：

- 真实买家端关注店铺页面。
- 真实买家个人券实例表。
- 真实 Shopee 关注关系接口；本期新增的是模拟买家关注状态表，不对接外部平台。
- 手动买家名单、粉丝分组或消息推送。
- 关注礼编辑、停止、删除、复制。
- 买家跨对局、跨店铺的长期关注关系。

若后续需要更精确的个人券生命周期，可单独新增买家领券实例表；本期先持久化买家关注状态，并用活动统计与订单归因表达关注礼领取和使用结果。

## 5. 游戏时间口径

所有判断使用订单模拟 tick 的游戏时间，不使用服务器真实当前时间：

- 领取窗口：`claim_start_at <= tick_time < claim_end_at`。
- 首次关注时间：写入买家关注状态表时使用订单模拟 tick。
- 领取后有效期：首次关注领取游戏时间起 `valid_days_after_claim` 个游戏天。
- 下单使用：订单创建 tick 必须落在个人关注礼有效期内。
- 统计回写：随订单模拟 tick 发生，不用真实当前时间补算。

## 6. 数据模型设计

### 6.1 新增买家关注状态表

新增表：`shopee_buyer_follow_states`

用途：持久化模拟买家对玩家 Shopee 店铺的关注状态，保证“新关注者才能领取关注礼”跨多次订单模拟 tick 生效。

| 字段 | 类型 | 约束 | 含义 |
|---|---|---|---|
| `id` | Integer | PK | 主键 |
| `run_id` | Integer | not null, index | 对局 ID |
| `user_id` | Integer | not null, index | 玩家/店铺用户 ID |
| `buyer_name` | String(120) | not null | 模拟买家标识 |
| `is_following` | Boolean | not null, default true | 当前是否关注店铺 |
| `first_followed_at` | DateTime(timezone=True) | not null | 首次关注时间，对应订单模拟游戏 tick |
| `follow_source` | String(32) | not null, default `follow_voucher` | 首次关注来源 |
| `source_campaign_id` | Integer | nullable, index | 促成首次关注的关注礼活动 ID |
| `created_at` | DateTime(timezone=True) | not null | 记录创建时间 |
| `updated_at` | DateTime(timezone=True) | not null | 记录更新时间 |

唯一约束：

```text
(run_id, user_id, buyer_name)
```

每个模拟买家对每个玩家店铺只能有一条关注状态。只要该记录存在且 `is_following=true`，后续关注礼活动不再把该买家视为“新关注者”。

### 6.2 个人券实例表暂不新增

本期不新增买家个人券领取表。关注礼是否可用由以下信息共同判断：

- 买家关注状态表中的 `first_followed_at`。
- 首次关注来源 `follow_source/source_campaign_id`。
- 关注礼活动的 `valid_days_after_claim`。
- 订单历史中的 `voucher_campaign_type='follow_voucher'` 使用次数。

如果后续需要展示买家券包、领取但未下单的券明细、取消领取或多张关注礼并存，再新增个人券实例表。

## 7. 买家领取资格模拟

### 7.1 资格来源

关注礼不要求用户手动录入买家名单。订单模拟先读取 `shopee_buyer_follow_states` 判断买家是否已关注当前玩家店铺：

- 若已存在 `(run_id, user_id, buyer_name)` 且 `is_following=true`，该买家不是新关注者，不再因后续关注礼活动重复领取新关注奖励。
- 若不存在关注状态，才按买家画像和代金券吸引力模拟是否首次关注并领取关注礼。
- 首次关注命中后立即写入买家关注状态表，`first_followed_at` 使用当前订单模拟 tick，`source_campaign_id` 记录促成关注的关注礼活动。

建议影响首次关注概率的因子：

- `price_sensitivity`：价格敏感买家更容易领取优惠。
- `base_buy_intent`：基础购买意愿高的买家更容易关注。
- `impulse_level`：冲动型买家更容易被关注礼转化。
- `loyalty_level` 或等价画像字段：若存在，可提高关注概率。
- 代金券优惠力度：折扣越高、门槛越低，领取概率越高。

### 7.2 稳定判定

为避免同一模拟 tick 内同一买家重复随机结果不一致，应同时使用数据库关注状态和本次模拟缓存：

```text
follow_access_cache[(buyer_name, campaign_id)] = {
  follow_hit: bool,
  already_following_before_tick: bool,
  claim_game_time: tick_time,
  valid_until_game_time: tick_time + valid_days_after_claim
}
```

同一次订单模拟内，多次计算同一买家同一关注礼时必须复用结果；跨 tick 则以 `shopee_buyer_follow_states` 为准，保证已关注买家不会再次作为新关注者领取关注礼。

## 8. 候选券加载规则

订单模拟加载关注礼代金券时应满足：

- `run_id`、`user_id` 匹配。
- `status != stopped`。
- `claim_start_at <= tick_time < claim_end_at`，或买家已在此前模拟中领取且仍在个人有效期内。
- `used_count < usage_limit`。
- `applicable_scope = all_products`，第一版全部商品适用；若后续扩展指定商品，再补商品快照表或复用范围字段。

关注礼候选可放入：

```text
follow_vouchers: list[dict]
```

并加入 `campaign_by_key[("follow_voucher", campaign_id)]`，便于统一回写统计。

## 9. 命中规则

关注礼代金券进入最优券候选池前需同时满足：

1. 买家已模拟关注并领取该券。
2. 当前订单 tick 落在领取后的个人有效期内。
3. 活动总用量未达上限。
4. 同一买家对同一关注礼未超过 `per_buyer_limit`。
5. 订单可抵扣小计满足 `min_spend_amount`。
6. 未命中限时抢购订单；沿用现有规则，限时抢购不叠加代金券。

跳过原因建议记录：

- `not_followed`
- `claim_window_closed`
- `personal_validity_expired`
- `usage_limit_reached`
- `buyer_limit_reached`
- `below_min_spend`
- `flash_sale_no_stack`

## 10. 最优券排序

关注礼代金券应纳入统一最优券排序。

建议优先级：

```text
商品代金券 > 直播代金券 > 视频代金券 > 专属代金券 > 关注礼代金券 > 店铺代金券
```

理由：

- 商品券、直播/视频券、专属券通常具备更明确的商品或场景来源。
- 关注礼来源是粉丝关注转化，强于普通店铺券，但弱于更精准的专属/内容场景券。
- 每单最多使用一张代金券；若存在可用券，继续沿用“必须使用最优可用券”的口径。

## 11. 下单概率影响

关注礼可提高买家的下单概率。建议 bonus 与实际可抵扣比例、买家价格敏感度和关注命中结果相关：

```text
voucher_savings_rate = discount_amount / max(order_subtotal, 1)
follow_bonus = clamp(
  0.02 + price_sensitivity * 0.06 + voucher_savings_rate * 0.12,
  0.01,
  0.16
)
```

只有买家已关注并领取、且订单满足门槛时才参与概率 bonus。未领取或过期的关注礼不提高下单概率。

## 12. 订单生成与归因

订单生成命中关注礼时：

- `order_subtotal_amount`：保存抵扣前商品小计。
- `voucher_campaign_type = "follow_voucher"`。
- `voucher_campaign_id = campaign.id`。
- `voucher_name_snapshot = campaign.voucher_name`。
- `voucher_code_snapshot = campaign.voucher_code`。
- `voucher_discount_amount = discount_amount`。
- `buyer_payment = max(order_subtotal - discount_amount + shipping_fee, 0)`，沿用现有订单实付计算口径。

商品行单价不改写，关注礼作为订单级优惠记录。

## 13. 统计回写

### 13.1 领取统计

当买家首次在模拟中命中关注并领取时：

- `claimed_count += 1`

同一买家同一关注礼在个人有效期内不重复增加领取数。

### 13.2 使用统计

当订单最终使用关注礼时：

- `used_count += 1`
- `order_count += 1`
- `sales_amount += buyer_payment`
- 若该买家此前未使用过该关注礼，则 `buyer_count += 1`

### 13.3 买家限用统计

复用现有订单表历史统计：

```text
buyer_voucher_usage_counts[(buyer_name, "follow_voucher", campaign_id)]
```

统计范围应包含历史订单中 `voucher_campaign_type = "follow_voucher"` 的记录。

## 14. Redis 与缓存失效

关注礼命中订单后，应沿用订单模拟现有缓存失效链路：

- 清理 Shopee 订单列表缓存。
- 清理代金券列表缓存。
- 清理代金券详情缓存。
- 清理代金券订单页缓存。

如果后续新增关注礼领取实例缓存，再按 `run_id:user_id:campaign_id` 维度单独失效。

## 15. 日志与调试字段

`buyer_journeys` 建议新增或复用以下字段：

```json
{
  "follow_voucher_candidates": [],
  "follow_voucher_access": {
    "campaign_id": 1,
    "follow_hit": true,
    "claim_game_time": "2026-05-08T10:00",
    "valid_until_game_time": "2026-05-15T10:00",
    "probability": 0.42
  },
  "selected_voucher": {
    "voucher_type": "follow_voucher",
    "campaign_id": 1,
    "discount_amount": 20
  },
  "voucher_skip_reasons": {
    "below_min_spend": 2,
    "not_followed": 1
  }
}
```

日志内时间仍使用游戏时间字符串或订单模拟 tick 派生值，避免混入真实时间。

## 16. 验收标准

后续实现完成后应满足：

1. 创建关注礼代金券后，订单模拟能加载当前游戏 tick 下有效活动。
2. 买家关注/领取资格在同一模拟 tick 内稳定，并能跨 tick 复用 `shopee_buyer_follow_states`。
3. 首次关注命中后写入买家关注状态表，已关注买家不会重复作为新关注者领取关注礼。
4. 命中关注礼的订单写入 `voucher_campaign_type = "follow_voucher"`。
4. 买家实付扣减关注礼优惠金额。
6. 关注礼统计字段正确回写：`claimed_count`、`used_count`、`order_count`、`sales_amount`、`buyer_count`。
7. 买家限用和活动总用量生效。
8. 领取后有效期按 `valid_days_after_claim` 个游戏天计算。
9. 代金券订单页可展示关注礼归因订单。
10. 所有时间判断和展示均使用游戏时间。
11. `python -m py_compile backend/apps/api-gateway/app/services/shopee_order_simulator.py` 通过。

## 17. 风险与后续扩展

- 不新增个人券实例表会让“领取但未下单”的券实例明细无法独立查询；本期通过买家关注状态表保留首次关注时间与来源活动，足够支撑新关注者资格、个人有效期和订单归因。若后续需要展示买家券包或多张关注礼并存，应新增买家关注礼领取实例表。
- 当前设计以模拟关注行为代替真实关注关系，适合经营模拟，不适合作为真实 Shopee 关注系统。
- 若后续允许关注礼指定商品，需要新增适用商品快照表或扩展现有活动表结构。

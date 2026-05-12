# 41-Shopee 关注礼代金券创建前后端数据库 Redis 实现设计

> 创建日期：2026-05-07  
> 状态：设计完成，待实现

## 1. 目标

为 Shopee 营销中心代金券模块接入“关注礼代金券”创建能力，使 `/shopee/marketing/vouchers/follow-create` 页面从前端静态表单升级为可读取初始化数据、校验输入、提交创建并落库的完整流程。

本期重点是接口、数据库和 Redis 数据闭环：

- 前端布局和样式沿用用户已手动调整后的 `FollowVoucherCreateView.tsx`，不重做视觉结构、颜色、间距、右侧关注礼预览轮播或基础表单布局。
- 前端仅补接口对接、受控字段初始化、表单校验和创建提交。
- 领取期限必须由后端按对局游戏时间初始化，前端 `DateTimePicker` 展示和提交游戏时间，不展示真实世界时间。
- 有效期限 V1 固定为“领取代金券后 7 个游戏天内有效”，后端按游戏时间口径保存有效天数，不由前端选择真实日期。
- 后端新增关注礼代金券创建页 bootstrap、创建提交接口，并扩展代金券列表兼容 `follow_voucher`。
- 数据库新增关注礼代金券活动表，保存影响经营结果的关注奖励规则、领取期限、有效期、使用量和后续归因预留字段。
- Redis 用于创建页 bootstrap、代金券列表缓存、创建限流和创建后缓存失效。
- 买家关注店铺、自动发券、领券后有效期滚动计算、订单命中与归因先预留字段，不在本期实现。

## 2. 范围与非范围

### 2.1 本期范围

- 关注礼代金券类型：实现 `follow_voucher`。
- 前端 `/shopee/marketing/vouchers/follow-create` 接口对接：
  - 初始化表单默认值。
  - 领取期限按游戏时间展示与提交。
  - 固定展示“领取代金券后 7 天内有效”。
  - 提交创建关注礼代金券。
  - 创建成功后返回 `/shopee/marketing/vouchers`。
- 后端接口：
  - 关注礼代金券创建页 bootstrap。
  - 创建关注礼代金券。
  - 代金券列表接口兼容返回关注礼代金券。
- 数据库：
  - 新增关注礼代金券活动表。
  - 补齐表注释和字段注释。
- Redis：
  - 创建页 bootstrap 缓存。
  - 代金券列表缓存失效。
  - 创建接口频率限制。

### 2.2 非范围

- 不重做关注礼代金券创建页前端布局、颜色、间距、右侧预览轮播和基础表单视觉。
- 不接入真实 Shopee 平台 API。
- 不实现店铺关注行为、取消关注、重复关注限制、买家端领券入口或真实发券记录。
- 不实现关注礼代金券详情、编辑、复制、停止、删除和数据页。
- 不在本期改订单模拟下单概率、代金券命中、价格改写或订单归因；仅预留后续接入口径。
- 不实现适用商品选择；V1 固定适用于店铺全部商品。
- 不要求前端输入代金券代码；代码由后端生成内部唯一编号，用于列表与后续归因，不作为买家输入码。

## 3. 游戏时间口径

关注礼代金券所有面向前端的时间字段必须统一使用游戏时间：

| 场景 | 口径 |
| --- | --- |
| 创建页默认领取时间 | 后端根据当前对局 tick 返回游戏时间字符串 |
| 前端日期选择器展示 | 展示游戏时间，不展示真实世界时间 |
| 前端提交 `claim_start_at/claim_end_at` | 提交 `YYYY-MM-DDTHH:mm` 游戏时间字符串 |
| 后端解析 | 使用现有游戏时间解析函数映射为系统时间落库 |
| 有效期限 | 固定保存 `valid_days_after_claim=7`，语义为 7 个游戏天 |
| 后端返回列表/详情 | 将落库系统时间反向格式化为游戏时间 |
| 状态计算 | 基于当前游戏 tick 与领取期限比较 |
| Redis 缓存 payload | 缓存对外返回的游戏时间字符串，不缓存真实时间给前端展示 |

建议复用现有时间转换函数：

- `_format_discount_game_datetime(value, run=run)`：系统时间 -> 游戏时间字符串。
- `_parse_discount_game_datetime(raw_value, run=run)`：游戏时间字符串 -> 系统时间。
- `_resolve_game_tick(db, run_id, user_id)`：解析当前对局游戏 tick。

前端要求：

- `FollowVoucherCreateView.tsx` 的 `DateTimePicker` 初始值必须来自 bootstrap 返回的 `form.claim_start_at` 和 `form.claim_end_at`。
- 不允许在空值时让 `DateTimePicker` 回落到浏览器真实当前时间作为业务默认值。
- 若后端未返回领取期限，应显示空值并阻止提交，提示“创建页初始化失败”或“请选择领取期限”。
- “领取代金券后 7 天内有效”中的 7 天按游戏天解释，不按真实世界 7 天解释。

## 4. 业务规则

### 4.1 关注礼代金券定义

关注礼代金券用于奖励新关注店铺的买家。V1 创建流程只保存卖家配置的奖励规则和领取期限，后续关注事件触发发券与订单命中统一接入。

| 字段 | 规则 |
| --- | --- |
| 代金券类型 | 固定为 `follow_voucher` |
| 代金券名称 | 卖家可见，最多 100 字符；如前端仍限制 20 字，应在实现时统一为后端规则或明确沿用当前 UI 限制 |
| 代金券代码 | 前端不展示代码字段；后端生成内部唯一编号，用于列表和后续归因 |
| 领取期限 | `claim_start_at < claim_end_at`，按游戏时间显示、提交、解析和校验 |
| 有效期限 | 固定为领取后 7 个游戏天内有效 |
| 奖励类型 | V1 固定 `discount` |
| 折扣类型 | 支持 `fixed_amount` 和 `percent` |
| 固定金额 | `discount_type=fixed_amount` 时必填且大于 0 |
| 百分比 | `discount_type=percent` 时必填，范围 `1-100` |
| 最大折扣金额 | 百分比模式支持 `set_amount/no_limit`；`set_amount` 时金额必填且大于 0 |
| 最低消费金额 | 必填且大于 0；固定金额模式下建议 `min_spend_amount >= discount_amount` |
| 使用数量 | 最大可领取并使用代金券数量，必须为正整数 |
| 每位买家最大发放量 | V1 固定或默认 1；若前端不展示该字段，后端默认 `per_buyer_limit=1` |
| 展示/触发场景 | 固定 `follow_reward`，语义为买家关注店铺后获得 |
| 适用商品 | V1 固定全部商品，`applicable_scope=all_products` |

### 4.2 领取与发券规则

- 领取资格：后续买家在 `claim_start_at <= 当前游戏时间 < claim_end_at` 内首次关注店铺时，可获得关注礼代金券。
- 重复关注：同一买家对同一店铺同一关注礼活动最多获得 1 次，取消关注后再关注不重复发放。
- 发券有效期：买家获得代金券时计算 `buyer_voucher_valid_start_at=followed_at`，`buyer_voucher_valid_end_at=followed_at + 7 个游戏天`。
- 总量扣减：后续真实发券时增加 `claimed_count`；订单成功使用时增加 `used_count`。
- 售罄规则：`claimed_count >= usage_limit` 后不再给新关注买家发券；列表状态可展示 `sold_out`。
- V1 创建阶段不新增买家领券实例表；但设计需预留后续表 `shopee_follow_voucher_claims` 或统一 voucher claim 表承载买家维度发券记录。

### 4.3 状态规则

关注礼代金券状态由当前游戏时间、领取数量、使用量和手动停止状态计算。

| 状态 | 条件 |
| --- | --- |
| `upcoming` | 当前游戏时间早于 `claim_start_at` |
| `ongoing` | `claim_start_at <= 当前游戏时间 < claim_end_at` 且未领完、未停止 |
| `sold_out` | `claimed_count >= usage_limit` |
| `ended` | 当前游戏时间晚于等于 `claim_end_at` |
| `stopped` | 卖家手动结束，后续扩展 |

数据库可保存 `status` 快照，接口返回时按当前游戏 tick 动态修正展示状态。

### 4.4 与订单模拟的关系

本期创建流程只落库，不改订单模拟；后续统一接入代金券影响时按以下口径使用：

- 命中条件：订单属于同一 `run_id/user_id` 店铺，买家已在关注礼领取期限内关注并获得该代金券，订单游戏时间在买家个人 7 个游戏天有效期内，订单金额满足 `min_spend_amount`。
- 适用范围：V1 固定全部商品，订单内所有可售商品小计可参与优惠。
- 优惠计算：
  - 固定金额：`discount_amount = min(voucher_amount, eligible_subtotal)`。
  - 百分比：`discount_amount = eligible_subtotal * discount_percent / 100`；若 `max_discount_type=set_amount`，再取 `min(discount_amount, max_discount_amount)`。
- 数量扣减：后续发券成功后增加 `claimed_count`，订单成功归因后增加 `used_count`。
- 买家限用：同一买家对同一关注礼代金券累计使用次数不超过 `per_buyer_limit`。
- 归因字段：后续订单级写入 `marketing_campaign_type='follow_voucher'`、`marketing_campaign_id`、`marketing_campaign_name_snapshot`。

## 5. 数据模型设计

### 5.1 新增 ORM：`ShopeeFollowVoucherCampaign`

建议新增表：`shopee_follow_voucher_campaigns`。

> 数据库 Schema Rules 要求：新建表必须添加表注释，新增字段必须添加字段注释。

| 字段 | 类型 | 约束 | 注释 |
| --- | --- | --- | --- |
| `id` | Integer | PK | 关注礼代金券活动 ID |
| `run_id` | Integer | FK `game_runs.id`, index | 所属对局 ID |
| `user_id` | Integer | FK `users.id`, index | 所属卖家用户 ID |
| `voucher_type` | String(32) | not null, default `follow_voucher` | 代金券类型，V1 固定关注礼代金券 |
| `voucher_name` | String(255) | not null | 卖家可见的代金券名称 |
| `voucher_code` | String(64) | not null | 后端生成的关注礼内部唯一编号，用于列表和后续归因 |
| `status` | String(32) | not null, index | 状态：upcoming/ongoing/sold_out/ended/stopped |
| `claim_start_at` | DateTime(timezone=True) | not null, index | 关注礼可领取开始游戏时间映射后的系统时间 |
| `claim_end_at` | DateTime(timezone=True) | not null, index | 关注礼可领取结束游戏时间映射后的系统时间 |
| `valid_days_after_claim` | Integer | not null, default 7 | 买家领取后有效游戏天数，V1 固定 7 |
| `reward_type` | String(32) | not null, default `discount` | 奖励类型，V1 固定折扣 |
| `discount_type` | String(32) | not null, default `fixed_amount` | 折扣类型：fixed_amount/percent |
| `discount_amount` | Float | nullable | 固定金额优惠，单位为店铺币种 |
| `discount_percent` | Float | nullable | 百分比优惠，单位为百分比 |
| `max_discount_type` | String(32) | not null, default `set_amount` | 最大折扣金额类型：set_amount/no_limit |
| `max_discount_amount` | Float | nullable | 百分比优惠最高抵扣金额，单位为店铺币种；无限制时为空 |
| `min_spend_amount` | Float | not null, default 0 | 最低消费金额，单位为店铺币种 |
| `usage_limit` | Integer | not null | 最大可领取并使用代金券数量 |
| `claimed_count` | Integer | not null, default 0 | 已发放/已领取数量 |
| `used_count` | Integer | not null, default 0 | 已使用数量 |
| `per_buyer_limit` | Integer | not null, default 1 | 每位买家可使用次数上限 |
| `trigger_type` | String(32) | not null, default `follow_shop` | 触发类型，V1 固定关注店铺 |
| `display_type` | String(32) | not null, default `follow_reward` | 展示/发放方式，关注礼 V1 固定关注奖励 |
| `display_channels` | Text | nullable | 展示渠道配置 JSON，V1 可固定 `['follow_prize']` |
| `applicable_scope` | String(32) | not null, default `all_products` | 适用范围，V1 固定全部商品 |
| `sales_amount` | Float | not null, default 0 | 代金券归因销售额，单位为店铺币种 |
| `order_count` | Integer | not null, default 0 | 代金券归因订单数 |
| `buyer_count` | Integer | not null, default 0 | 使用代金券买家数 |
| `created_at` | DateTime(timezone=True) | not null | 创建时间 |
| `updated_at` | DateTime(timezone=True) | not null | 更新时间 |

建议索引：

```python
Index("ix_shopee_follow_vouchers_run_user_status", "run_id", "user_id", "status")
Index("ix_shopee_follow_vouchers_run_user_claim_time", "run_id", "user_id", "claim_start_at", "claim_end_at")
Index("ix_shopee_follow_vouchers_run_user_code", "run_id", "user_id", "voucher_code", unique=True)
```

### 5.2 后续预留：买家领取实例表

本期不实现，但订单归因接入时建议新增 `shopee_follow_voucher_claims` 或统一代金券领取表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `campaign_id` | Integer | 关注礼活动 ID |
| `run_id/user_id` | Integer | 对局与卖家 |
| `buyer_id` | Integer/String | 模拟买家 ID |
| `claimed_at` | DateTime | 关注并发券的游戏时间映射系统时间 |
| `valid_start_at` | DateTime | 买家个人代金券有效开始时间 |
| `valid_end_at` | DateTime | 买家个人代金券有效结束时间，领取后 7 个游戏天 |
| `used_count` | Integer | 买家已使用次数 |
| `status` | String | available/used/expired |

## 6. 后端接口设计

接口文件沿用：`backend/apps/api-gateway/app/api/routes/shopee.py`。

### 6.1 创建页 Bootstrap

```http
GET /shopee/runs/{run_id}/marketing/vouchers/follow-create/bootstrap
```

用途：为关注礼代金券创建页提供游戏时间默认值、表单规则和只读状态。

响应示例：

```json
{
  "meta": {
    "run_id": 1,
    "user_id": 2,
    "voucher_type": "follow_voucher",
    "read_only": false,
    "current_tick": "2026-05-07T09:00:00Z",
    "currency": "RM"
  },
  "form": {
    "voucher_name": "",
    "claim_start_at": "2026-05-07T09:00",
    "claim_end_at": "2026-05-07T10:00",
    "valid_days_after_claim": 7,
    "reward_type": "discount",
    "discount_type": "fixed_amount",
    "discount_amount": null,
    "discount_percent": null,
    "max_discount_type": "set_amount",
    "max_discount_amount": null,
    "min_spend_amount": null,
    "usage_limit": null,
    "per_buyer_limit": 1,
    "trigger_type": "follow_shop",
    "display_type": "follow_reward",
    "applicable_scope": "all_products"
  },
  "rules": {
    "voucher_name_max_length": 100,
    "valid_days_after_claim": 7,
    "min_duration_minutes": 1,
    "max_duration_days": 180,
    "discount_types": ["fixed_amount", "percent"],
    "max_discount_types": ["set_amount", "no_limit"],
    "requires_usage_limit": true
  }
}
```

设计要点：

- `claim_start_at` 默认当前游戏 tick。
- `claim_end_at` 默认当前游戏 tick + 1 个游戏小时，沿用其他代金券创建页默认区间口径。
- 响应给前端的领取时间必须是游戏时间字符串。
- 历史对局或已结束对局返回 `read_only=true`，前端禁用确认按钮。
- Redis key 建议：`{prefix}:cache:shopee:voucher:create:bootstrap:{run_id}:{user_id}:follow_voucher`。

### 6.2 创建关注礼代金券

```http
POST /shopee/runs/{run_id}/marketing/vouchers/follow-campaigns
```

请求示例：

```json
{
  "voucher_type": "follow_voucher",
  "voucher_name": "关注领取 RM5",
  "claim_start_at": "2026-05-07T09:00",
  "claim_end_at": "2026-05-07T10:00",
  "reward_type": "discount",
  "discount_type": "fixed_amount",
  "discount_amount": 5,
  "discount_percent": null,
  "max_discount_type": "set_amount",
  "max_discount_amount": null,
  "min_spend_amount": 10,
  "usage_limit": 100,
  "per_buyer_limit": 1
}
```

后端处理：

1. 校验当前对局属于当前用户且未结束。
2. 将 `claim_start_at/claim_end_at` 从游戏时间解析为系统时间。
3. 校验领取期限、折扣、最低消费、使用数量和买家限用规则。
4. 后端生成唯一内部 `voucher_code`，建议前缀 `FOLLOW` + 8 位随机码。
5. 写入 `shopee_follow_voucher_campaigns`。
6. 创建成功后清理代金券列表与关注礼 bootstrap 缓存。

响应示例：

```json
{
  "campaign_id": 12,
  "voucher_type": "follow_voucher",
  "status": "upcoming"
}
```

### 6.3 代金券列表兼容

现有接口继续使用：

```http
GET /shopee/runs/{run_id}/marketing/vouchers
```

需要扩展返回关注礼代金券：

| 字段 | 关注礼口径 |
| --- | --- |
| `voucher_type` | `Follow Voucher` |
| `voucher_type_label` | `关注礼代金券` |
| `voucher_code` | 后端内部编号，如 `FOLLOWA1B2C3D4` |
| `discount_label` | `RM 5` 或 `10%OFF` |
| `scope_label` | `全部商品` |
| `usage_limit` | 最大可领取并使用数量 |
| `used_count` | 已使用数量；如列表想展示发放量，可后续扩展 `claimed_count` |
| `period` | 领取期限，按游戏时间格式化 |

## 7. Redis 设计

| Key | 用途 | TTL/失效 |
| --- | --- | --- |
| `cbec:cache:shopee:voucher:create:bootstrap:{run_id}:{user_id}:follow_voucher` | 关注礼创建页默认值和规则 | 60 秒 |
| `cbec:cache:shopee:voucher:list:{run_id}:{user_id}:...` | 统一代金券列表缓存 | 创建成功后按前缀失效 |
| `cbec:ratelimit:shopee:voucher:create:user:{user_id}` | 创建接口限流 | 复用现有创建限流窗口 |

缓存内容要求：

- bootstrap payload 中的领取期限使用游戏时间字符串。
- 列表 payload 中的 `period` 使用游戏时间格式化结果。
- 创建成功后必须清理：
  - 关注礼 bootstrap 缓存前缀。
  - 统一代金券列表缓存前缀。
  - 营销中心相关汇总缓存（如列表表现面板复用该数据）。

## 8. 前端接入设计

文件：`frontend/src/modules/shopee/views/FollowVoucherCreateView.tsx`。

只做接口与状态接入，不重做用户已手动完成的布局样式。

### 8.1 Props

当前 `ShopeePage.tsx` 已接入 `/shopee/marketing/vouchers/follow-create` 路由。实现时建议补充 `runId`：

```tsx
interface FollowVoucherCreateViewProps {
  runId: number | null;
  readOnly?: boolean;
  onBackToVouchers: () => void;
}
```

并在 `ShopeePage.tsx` 中传入：

```tsx
<FollowVoucherCreateView runId={run?.id ?? null} readOnly={readOnly} onBackToVouchers={() => handleSelectView('marketing-vouchers')} />
```

### 8.2 Bootstrap 接入

- 进入页面后调用：`GET /shopee/runs/{run_id}/marketing/vouchers/follow-create/bootstrap`。
- 将 `form.claim_start_at` 写入 `claimStartAt`。
- 将 `form.claim_end_at` 写入 `claimEndAt`。
- 将 `meta.currency` 写入 `currency` 状态，不再硬编码为唯一来源。
- 若 `meta.read_only=true`，前端禁用表单与确认按钮。
- 加载失败时展示错误提示，不使用浏览器真实当前时间兜底。

### 8.3 提交校验

前端提交前校验：

- `voucherName.trim()` 非空。
- `claimStartAt` 与 `claimEndAt` 均非空。
- `claimStartAt < claimEndAt`。
- 固定金额模式：`discountAmount > 0`，且 `minSpendAmount >= discountAmount`。
- 百分比模式：`0 < discountPercent <= 100`；`maxDiscountType=set_amount` 时 `maxDiscountAmount > 0`。
- `minSpendAmount > 0`。
- `usageLimit` 为正整数。
- `perBuyerLimit` 默认 1 且不超过 `usageLimit`。

### 8.4 提交请求

确认按钮调用：`POST /shopee/runs/{run_id}/marketing/vouchers/follow-campaigns`。

提交字段：

```json
{
  "voucher_type": "follow_voucher",
  "voucher_name": "...",
  "claim_start_at": "YYYY-MM-DDTHH:mm",
  "claim_end_at": "YYYY-MM-DDTHH:mm",
  "reward_type": "discount",
  "discount_type": "fixed_amount|percent",
  "discount_amount": 5,
  "discount_percent": null,
  "max_discount_type": "set_amount|no_limit",
  "max_discount_amount": null,
  "min_spend_amount": 10,
  "usage_limit": 100,
  "per_buyer_limit": 1
}
```

创建成功后调用 `onBackToVouchers()` 返回统一代金券列表。

## 9. 初始化与历史库兼容

`backend/apps/api-gateway/app/db.py` 需要：

- 在 `init_database()` 的模型导入中加入 `ShopeeFollowVoucherCampaign`。
- `Base.metadata.create_all(bind=engine)` 自动创建新表。
- 新增 `_ensure_shopee_follow_voucher_tables()`，用于历史库补字段。
- `_ensure_table_comments()` 增加：
  - `shopee_follow_voucher_campaigns`: `Shopee 关注礼代金券活动表`。
- `_ensure_column_comments()` 为所有新增字段补齐字段注释。

## 10. 验收标准

- 设计文档已创建：`docs/设计文档/41-Shopee关注礼代金券创建前后端数据库Redis实现设计.md`。
- 后续实现完成后：
  - `/shopee/marketing/vouchers/follow-create` 页面读取后端 bootstrap。
  - 日期选择器展示的领取期限来自后端游戏时间，不使用真实世界当前时间兜底。
  - 固定“领取代金券后 7 天内有效”按 7 个游戏天口径保存。
  - 表单校验错误可在前端阻止提交。
  - 创建成功后 `shopee_follow_voucher_campaigns` 落库，并返回统一代金券列表。
  - `/shopee/marketing/vouchers` 列表可展示关注礼代金券。
  - Redis bootstrap/列表缓存、创建限流、创建后缓存失效可用。
  - 新表和新增字段具备表注释、字段注释。

## 11. 后续扩展

- 新增买家关注事件模拟与买家关注状态表。
- 新增关注礼发券记录表或统一代金券领取实例表。
- 订单模拟接入关注礼代金券命中、有效期判断、优惠抵扣和归因。
- 关注礼详情页、数据页、停止/删除/复制能力。
- 若后续需要支持指定买家群体或不同有效天数，再扩展 `audience_scope` 与 `valid_days_after_claim`，本期不做配置化。

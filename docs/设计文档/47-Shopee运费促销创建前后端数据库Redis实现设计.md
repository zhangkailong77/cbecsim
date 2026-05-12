# 47-Shopee 运费促销创建前后端数据库 Redis 实现设计

> 创建日期：2026-05-09  
> 状态：设计完成，待实现

## 1. 目标

为 Shopee `营销中心 -> 运费促销` 接入创建、列表、后端接口、数据库与 Redis 数据闭环，使卖家可以在当前对局中配置店铺运费优惠规则，并为后续订单模拟中的运费优惠、买家实付、卖家运费补贴和活动统计预留清晰口径。

本设计基于当前已手动完成的前端页面，不调整页面布局和视觉样式：

- 列表页：`frontend/src/modules/shopee/views/ShippingFeePromotionView.tsx`
- 创建页：`frontend/src/modules/shopee/views/ShippingFeePromotionCreateView.tsx`
- 路由：`/shopee/marketing/shipping-fee-promotion`、`/shopee/marketing/shipping-fee-promotion/create`

## 2. 范围与非范围

### 2.1 本期范围（V1）

- 前端接口接入：
  - 列表页加载真实活动列表、状态 Tab 与空状态。
  - 创建页加载 bootstrap 默认值、规则、当前游戏时间和物流渠道。
  - 创建页提交运费促销活动，成功后返回列表页。
- 后端接口：
  - 创建页 bootstrap。
  - 运费促销活动创建。
  - 运费促销列表查询。
- 数据库：
  - 新增运费促销活动主表。
  - 新增活动物流渠道表。
  - 新增活动运费层级表。
  - 表注释与字段注释必须同步维护。
- Redis：
  - 创建页 bootstrap 缓存。
  - 活动列表缓存。
  - 创建接口限流。
  - 创建成功后清理运费促销列表与订单模拟营销缓存。
- 订单模拟预留：
  - 按游戏时间判断活动有效。
  - 按物流渠道与订单商品小计匹配运费优惠层级。
  - 写入订单级运费促销归因字段或扩展统计字段。

### 2.2 非范围（V1 不做）

- 不重做用户已手动完成的前端样式和布局。
- 不接入真实 Shopee 平台运费促销 API。
- 不实现买家端真实运费券领取页面。
- 不实现复杂跨店包邮、平台补贴、平台券与店铺运费促销叠加。
- 不在本设计内立即实现订单模拟生效逻辑；仅定义后续接入口径。
- 不实现编辑、停止、删除、复制与详情页；可在后续设计中补充。

## 3. 当前前端布局观察

### 3.1 列表页

`ShippingFeePromotionView.tsx` 当前布局：

- 外层延续 Shopee 模块统一 `flex-1 overflow-y-auto bg-[#f6f6f6] px-9 py-6`。
- 内容区 `max-w-[1660px]`。
- 白色主体卡片展示：
  - 标题“促销列表”。
  - 说明文案“通过设置运费促销，您的店铺可以吸引更多买家！”。
  - 右上角 `+ 创建` 按钮，作为进入创建页的唯一主操作入口。
  - Tab：`全部 / 进行中 / 即将开始 / 已结束`。
  - 有数据时展示表格列：`运费促销名称 / 物流渠道 / 运费设置 / 预算 / 状态 / 活动时间 / 操作`。
  - 操作列保留 `编辑 / 结束` 文案入口，V1 仅展示，不实现编辑与结束逻辑。
  - 无数据时展示喇叭图标和“暂无运费促销活动”，不在空状态内额外放置创建按钮。
- 历史回溯模式下展示只读提示，创建按钮禁用。

后续接接口时应保留上述结构，只将当前模拟列表数据替换为真实接口数据；没有数据时继续使用现有空状态。

### 3.2 创建页

`ShippingFeePromotionCreateView.tsx` 当前布局：

- 内容区固定 `w-[1360px]`。
- 基础信息区：
  - 运费促销名称，最多 20 字。
  - 运费促销期限：无期限 / 自定义期限。
  - 自定义期限使用 Shopee 模块现有 `DateTimePicker`。
  - 促销预算：无预算限制 / 自定义预算。
  - 右侧预览图。
- 物流渠道与运费区：
  - 物流渠道：标准快递、大件快递。
  - 运费层级：最多 3 个层级。
  - 每个层级包含最低消费金额与运费类型：运费减免 / 免运费。
- 底部按钮：取消、确认。

后续接接口时只替换数据来源、校验与提交行为，不改动现有排版。

## 4. 业务规则

### 4.1 基础规则

| 字段 | 规则 |
| --- | --- |
| 活动类型 | 固定为 `shipping_fee_promotion` |
| 活动名称 | 卖家可见，最多 20 字，不能为空 |
| 活动期限 | 支持 `no_limit` 与 `selected` |
| 自定义期限 | `start_at < end_at`，按游戏时间存储与判断 |
| 无期限 | `start_at` 默认为创建时当前游戏时间，`end_at` 可为空 |
| 促销预算 | 支持 `no_limit` 与 `selected` |
| 自定义预算 | 必须大于 0，单位为店铺币种 RM |
| 物流渠道 | 至少选择 1 个渠道 |
| 运费层级 | 至少 1 个、最多 3 个 |
| 最低消费金额 | 每层必填，必须大于等于 0 |
| 层级排序 | 按最低消费金额从低到高生效 |
| 运费类型 | `fixed_fee` 运费减免、`free_shipping` 免运费 |
| 运费减免金额 | `fixed_fee` 时必填，必须大于等于 0 |

### 4.2 层级规则

- 同一活动内层级 `min_spend_amount` 不允许重复。
- 最低消费金额越高，优惠力度应不低于低层级：
  - `free_shipping` 优先级高于 `fixed_fee`。
  - 两个 `fixed_fee` 层级中，高门槛层级的运费减免金额应大于或等于低门槛层级。
- 订单命中时取满足 `order_subtotal >= min_spend_amount` 的最高门槛层级。
- 若没有任何层级满足门槛，则不产生运费促销优惠。

### 4.3 状态规则

状态由当前游戏时间、预算和手动状态共同计算。

| 状态 | 条件 |
| --- | --- |
| `upcoming` | 自定义期限且当前游戏时间早于 `start_at` |
| `ongoing` | 当前游戏时间在活动期限内，且预算未用尽、未停止 |
| `ended` | 自定义期限且当前游戏时间大于等于 `end_at` |
| `budget_exhausted` | 自定义预算且 `budget_used >= budget_limit` |
| `stopped` | 卖家手动停止，后续扩展 |

列表 Tab 映射：

- `全部`：全部状态。
- `进行中`：`ongoing`。
- `即将开始`：`upcoming`。
- `已结束`：`ended / budget_exhausted / stopped`。

### 4.4 游戏时间口径

运费促销所有时间口径均使用当前对局游戏时间：

- 创建页 bootstrap 返回的默认开始时间。
- 自定义期限开始/结束。
- 活动状态判断。
- 订单模拟命中时间。
- 预算扣减与统计回写时间。

前端不得用真实世界当前时间作为默认活动时间；DateTimePicker 只展示和提交后端给出的游戏时间字符串。

### 4.5 与现有订单运费/运输时长链路的关系

当前“我的订单”与发货链路中已经存在物流履约与结算运费口径，运费促销不得替换这部分基础逻辑。

现有基础链路：

| 现有内容 | 当前口径 | 运费促销关系 |
| --- | --- | --- |
| 物流渠道 | 订单保存 `shipping_channel`，订单列表展示物流渠道 | 运费促销按渠道匹配是否适用，不重新定义渠道 |
| 原始运费成本 | `calc_shipping_cost(distance_km, shipping_channel)` 按仓库到买家的距离和渠道计算 | 运费促销以该原始运费为基础计算买家侧减免 |
| 运输时长 | `calc_eta(distance_km, shipping_channel, shipped_at)` 按距离和渠道计算预计运输区间 | 运费促销不改变运输时长、配送线路和送达预估 |
| 发货时限 | `ship_by_at / ship_by_date` 控制待出货超时与取消 | 运费促销不改变发货时限 |
| 平台运费补贴 | `calc_settlement(...)` 按渠道计算 `shipping_subsidy_amount` | 运费促销不替代平台补贴，应单独记录卖家营销运费优惠 |
| 运费成本结算 | 结算保存 `shipping_cost_amount` 与 `shipping_subsidy_amount` | 运费促销只新增促销减免与预算消耗，不覆盖原字段含义 |

原始运费成本公式沿用现有实现，但为避免东马/跨州长距离订单被直线公里数放大，计费距离按 80km 封顶，超过 300km/800km 时只追加远程附加费：

```text
计费距离 = min(仓库到买家的距离公里数, 80km)
原始运费成本 = 渠道基础价 + 计费距离 × 渠道每公里费用 + 远程附加费
```

当前渠道默认口径：

| 物流渠道 | 基础价 | 每公里费用 | 300km+ 附加费 | 800km+ 附加费 |
| --- | ---: | ---: | ---: | ---: |
| 快捷快递 | RM 4.50 | RM 0.14/km | RM 4.00 | RM 8.00 |
| 标准大件 | RM 8.00 | RM 0.11/km | RM 6.00 | RM 18.00 |
| 标准快递 | RM 6.00 | RM 0.12/km | RM 4.00 | RM 10.00 |

因此运费促销后续接入订单模拟时，应在订单创建/结算阶段追加计算：

```text
原始运费 = calc_shipping_cost(distance_km, shipping_channel)
买家侧运费优惠 = 运费促销命中后减免的金额
卖家真实物流成本 = 原始运费成本，仍记录为 shipping_cost_amount
平台补贴 = 现有 shipping_subsidy_amount，继续按平台补贴口径计算
卖家促销预算消耗 = 买家侧运费优惠，单独记录为 shipping_promotion_discount_amount
运输时长 = calc_eta(...)，不受运费促销影响
```

## 5. 数据模型设计

> 新建表必须添加 table comment；新增字段必须添加 column comment。若通过初始化脚本或迁移脚本创建，也必须同步维护注释。

### 5.1 `shopee_shipping_fee_promotion_campaigns`

运费促销活动主表。

| 字段 | 类型 | 约束 | 注释 |
| --- | --- | --- | --- |
| `id` | Integer | PK | 运费促销活动 ID |
| `run_id` | Integer | FK `game_runs.id`, index | 所属对局 ID |
| `user_id` | Integer | FK `users.id`, index | 所属卖家用户 ID |
| `promotion_name` | String(120) | not null | 运费促销名称，仅卖家可见 |
| `status` | String(32) | not null, index | 状态：upcoming/ongoing/ended/budget_exhausted/stopped |
| `period_type` | String(32) | not null | 期限类型：no_limit/selected |
| `start_at` | DateTime(timezone=True) | not null, index | 活动开始游戏时间 |
| `end_at` | DateTime(timezone=True) | nullable, index | 活动结束游戏时间，无期限为空 |
| `budget_type` | String(32) | not null | 预算类型：no_limit/selected |
| `budget_limit` | Float | nullable | 预算上限，单位 RM |
| `budget_used` | Float | not null, default 0 | 已使用预算，单位 RM |
| `order_count` | Integer | not null, default 0 | 归因订单数 |
| `buyer_count` | Integer | not null, default 0 | 归因买家数 |
| `sales_amount` | Float | not null, default 0 | 归因销售额，单位 RM |
| `shipping_discount_amount` | Float | not null, default 0 | 已产生运费优惠总额，单位 RM |
| `created_at` | DateTime(timezone=True) | not null | 创建时间 |
| `updated_at` | DateTime(timezone=True) | not null | 更新时间 |

建议索引：

```python
Index("ix_shopee_shipping_fee_promotions_run_user_status", "run_id", "user_id", "status")
Index("ix_shopee_shipping_fee_promotions_run_user_time", "run_id", "user_id", "start_at", "end_at")
```

表注释：`Shopee 运费促销活动主表`。

### 5.2 `shopee_shipping_fee_promotion_channels`

运费促销适用物流渠道表。

| 字段 | 类型 | 约束 | 注释 |
| --- | --- | --- | --- |
| `id` | Integer | PK | 主键 ID |
| `campaign_id` | Integer | FK, index | 运费促销活动 ID |
| `run_id` | Integer | FK, index | 所属对局 ID |
| `user_id` | Integer | FK, index | 所属卖家用户 ID |
| `channel_key` | String(32) | not null | 物流渠道 key：standard/bulky |
| `channel_label` | String(120) | not null | 物流渠道展示名 |
| `created_at` | DateTime(timezone=True) | not null | 创建时间 |

建议唯一约束：`(campaign_id, channel_key)`。

表注释：`Shopee 运费促销适用物流渠道表`。

### 5.3 `shopee_shipping_fee_promotion_tiers`

运费促销门槛层级表。

| 字段 | 类型 | 约束 | 注释 |
| --- | --- | --- | --- |
| `id` | Integer | PK | 主键 ID |
| `campaign_id` | Integer | FK, index | 运费促销活动 ID |
| `run_id` | Integer | FK, index | 所属对局 ID |
| `user_id` | Integer | FK, index | 所属卖家用户 ID |
| `tier_index` | Integer | not null | 层级序号，从 1 开始 |
| `min_spend_amount` | Float | not null | 最低消费金额，单位 RM |
| `fee_type` | String(32) | not null | 运费类型：fixed_fee/free_shipping |
| `fixed_fee_amount` | Float | nullable | 运费减免金额，单位 RM；免运费时为空 |
| `created_at` | DateTime(timezone=True) | not null | 创建时间 |
| `updated_at` | DateTime(timezone=True) | not null | 更新时间 |

建议唯一约束：`(campaign_id, tier_index)`、`(campaign_id, min_spend_amount)`。

表注释：`Shopee 运费促销门槛层级表`。

## 6. 后端接口设计

接口文件沿用：`backend/apps/api-gateway/app/api/routes/shopee.py`。

### 6.1 创建页 Bootstrap

```http
GET /shopee/runs/{run_id}/marketing/shipping-fee-promotion/create/bootstrap
```

用途：提供创建页默认值、当前游戏时间、币种、物流渠道与规则；自定义期限的默认开始与结束时间均由后端按对局游戏时间生成。

响应示例：

```json
{
  "meta": {
    "run_id": 6,
    "user_id": 3,
    "read_only": false,
    "current_tick": "2026-05-09T10:00",
    "currency": "RM"
  },
  "form": {
    "promotion_name": "",
    "name_max_length": 20,
    "period_type": "no_limit",
    "start_at": "2026-05-09T10:00",
    "end_at": "2026-05-09T11:00",
    "budget_type": "no_limit",
    "budget_limit": null,
    "channels": ["standard"],
    "tiers": [
      {
        "tier_index": 1,
        "min_spend_amount": null,
        "fee_type": "fixed_fee",
        "fixed_fee_amount": null
      }
    ]
  },
  "channels": [
    { "key": "standard", "label": "标准快递 (Standard Delivery)", "enabled": true },
    { "key": "bulky", "label": "大件快递 (Standard Delivery Bulky)", "enabled": true }
  ],
  "rules": {
    "max_tier_count": 3,
    "min_tier_count": 1,
    "currency": "RM",
    "min_budget_amount": 0.01
  }
}
```

### 6.2 创建运费促销活动

```http
POST /shopee/runs/{run_id}/marketing/shipping-fee-promotions
```

请求示例：

```json
{
  "promotion_name": "满 RM50 运费优惠",
  "period_type": "selected",
  "start_at": "2026-05-09T10:00",
  "end_at": "2026-05-10T10:00",
  "budget_type": "selected",
  "budget_limit": 100,
  "channels": ["standard", "bulky"],
  "tiers": [
    {
      "tier_index": 1,
      "min_spend_amount": 50,
      "fee_type": "fixed_fee",
      "fixed_fee_amount": 2
    },
    {
      "tier_index": 2,
      "min_spend_amount": 100,
      "fee_type": "free_shipping",
      "fixed_fee_amount": null
    }
  ]
}
```

后端校验：

- `readOnly` 历史回溯模式禁止创建。
- 活动名称不能为空且不超过 20 字。
- 自定义期限必须提供开始/结束游戏时间，并满足 `start_at < end_at`。
- 自定义预算必须大于 0。
- 渠道必须在 bootstrap 返回的可用渠道内，且至少 1 个。
- 层级数量 `1 ~ 3`。
- 层级门槛不能重复，按金额升序保存。
- `fixed_fee` 必须提供 `fixed_fee_amount >= 0`。
- `free_shipping` 的 `fixed_fee_amount` 保存为空。

响应示例：

```json
{
  "id": 12,
  "status": "ongoing",
  "message": "运费促销创建成功"
}
```

### 6.3 运费促销列表

```http
GET /shopee/runs/{run_id}/marketing/shipping-fee-promotions?status=all&page=1&page_size=10
```

参数：

- `status=all|ongoing|upcoming|ended`
- `page` 默认 1。
- `page_size` 默认 10。

响应示例：

```json
{
  "tabs": [
    { "key": "全部", "status": "all", "count": 2 },
    { "key": "进行中", "status": "ongoing", "count": 1 },
    { "key": "即将开始", "status": "upcoming", "count": 1 },
    { "key": "已结束", "status": "ended", "count": 0 }
  ],
  "list": {
    "page": 1,
    "page_size": 10,
    "total": 2,
    "items": [
      {
        "id": 12,
        "promotion_name": "满 RM50 运费优惠",
        "status": "ongoing",
        "status_label": "进行中",
        "period": "2026-05-09 10:00 - 2026-05-10 10:00",
        "budget_text": "RM 100.00",
        "budget_used_text": "RM 0.00",
        "channels_text": "标准快递、大件快递",
        "tier_summary": "满 RM50 运费减免 RM2；满 RM100 免运费",
        "order_count": 0,
        "shipping_discount_amount": 0
      }
    ]
  }
}
```

## 7. Redis 设计

建议 key 前缀：

| 用途 | Key |
| --- | --- |
| 创建页 bootstrap | `shopee:shipping_fee_promotion:create:bootstrap:{run_id}:{user_id}` |
| 活动列表 | `shopee:shipping_fee_promotion:list:{run_id}:{user_id}:{status}:{page}:{page_size}` |
| 订单模拟可用活动 | `shopee:shipping_fee_promotion:active:{run_id}:{user_id}:{tick_bucket}` |
| 创建限流 | `shopee:shipping_fee_promotion:create:rate:{run_id}:{user_id}` |

失效规则：

- 创建成功后删除当前 `run_id/user_id` 的列表缓存。
- 创建成功后删除订单模拟营销活动缓存，避免新活动无法在后续 tick 生效。
- 后续编辑、停止、删除活动时同样清理列表、详情、订单模拟可用活动缓存。

## 8. 订单模拟预留口径

后续接入订单模拟时，建议新增独立设计文档；本期先约定字段和算法入口。

### 8.1 命中条件

订单满足以下条件时可命中运费促销：

1. 订单属于同一 `run_id/user_id`。
2. 订单创建时间为游戏 tick，且活动处于 `ongoing`。
3. 订单物流渠道在活动渠道内。
4. 订单商品小计满足至少一个层级的 `min_spend_amount`。
5. 若活动有预算，剩余预算大于 0。

### 8.2 优惠计算

- 先计算原始运费 `original_shipping_fee`，可复用现有 `calc_shipping_cost(...)` 口径。
- 命中最高门槛层级：
  - `fixed_fee`：买家运费减免 `min(original_shipping_fee, fixed_fee_amount)`，优惠后运费为 `original_shipping_fee - 减免金额`。
  - `free_shipping`：买家运费调整为 `0`。
- 运费促销优惠：
  - `shipping_discount = original_shipping_fee - buyer_shipping_fee_after_promotion`
  - 不允许小于 0。
- 若剩余预算不足：
  - V1 建议取 `min(shipping_discount, remaining_budget)`，预算用尽后活动状态转为 `budget_exhausted`。

### 8.3 订单归因预留

后续可在 `shopee_orders` 增加订单级字段：

| 字段 | 含义 |
| --- | --- |
| `shipping_promotion_campaign_id` | 命中的运费促销活动 ID |
| `shipping_promotion_name_snapshot` | 活动名称快照 |
| `shipping_promotion_discount_amount` | 本单运费优惠金额 |
| `shipping_fee_before_promotion` | 优惠前运费 |
| `shipping_fee_after_promotion` | 优惠后买家承担运费 |

若暂不新增订单字段，也可在 `buyer_journeys` 调试日志中先记录候选和命中结果，但最终经营结果必须落库，不能只存在前端本地状态。

## 9. 前端接入设计

### 9.1 列表页

`ShippingFeePromotionView.tsx` 后续接入：

- 新增 `runId` prop。
- 加载 `GET /marketing/shipping-fee-promotions`。
- Tab 点击改变 `status` 并重新请求。
- 有数据时在当前白色卡片内渲染列表；无数据时保留现有空状态。
- `立即创建` 保持跳转到 `/shopee/marketing/shipping-fee-promotion/create`。
- 历史回溯模式保持只读提示和创建按钮禁用。

### 9.2 创建页

`ShippingFeePromotionCreateView.tsx` 后续接入：

- 新增 `runId` prop。
- 页面加载时调用 bootstrap。
- 默认时间从 `current_tick` 或 `form.start_at` 读取，不使用真实时间。
- 物流渠道从后端 `channels` 渲染，当前 V1 可继续展示标准快递和大件快递。
- 提交前做前端基础校验，后端仍做最终校验。
- 点击确认调用创建接口；成功后返回列表页。
- 保留现有 `DateTimePicker`、层级表格和底部按钮布局。

## 10. 验收标准

- 设计文档完成后，本次不修改前后端业务代码。
- 后续实现时需满足：
  - `/shopee/marketing/shipping-fee-promotion` 可展示真实活动列表和空状态。
  - `/shopee/marketing/shipping-fee-promotion/create` 默认时间来自游戏时间。
  - 创建活动成功后落库，列表可看到活动。
  - 数据表、字段注释完整。
  - Redis 缓存创建页和列表，并在创建后失效。
  - 历史回溯模式不可创建。
  - 不改变用户已手动完成的前端布局和样式。

## 11. 后续待办

1. 按本文档实现前后端、数据库与 Redis。
2. 单独设计运费促销接入订单模拟的概率与经营结果影响。
3. 后续补充详情、编辑、停止、删除和复制活动。
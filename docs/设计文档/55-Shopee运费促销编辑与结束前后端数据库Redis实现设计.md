# 55-Shopee 运费促销编辑与结束前后端数据库 Redis 实现设计

> 创建日期：2026-05-13  
> 状态：设计完成，待实现

## 1. 目标

补齐 Shopee `营销中心 -> 运费促销` 列表操作列中的 `编辑` 与 `结束` 能力，使已创建的运费促销活动可以被卖家重新进入表单修改，或手动结束活动。

本设计基于既有运费促销创建与订单模拟设计，不重做页面风格：

- 列表页：`frontend/src/modules/shopee/views/ShippingFeePromotionView.tsx`
- 创建页：`frontend/src/modules/shopee/views/ShippingFeePromotionCreateView.tsx`
- 新增编辑路由：`/shopee/marketing/shipping-fee-promotion/update`
- 既有创建路由：`/shopee/marketing/shipping-fee-promotion/create`
- 既有列表路由：`/shopee/marketing/shipping-fee-promotion`
- 既有后端接口文件：`backend/apps/api-gateway/app/api/routes/shopee.py`

## 2. 范围与非范围

### 2.1 本期范围

- 列表页操作列：
  - `编辑` 点击后进入 `/shopee/marketing/shipping-fee-promotion/update`。
  - `结束` 点击后手动结束当前活动。
- 编辑页：
  - 页面布局与 `/shopee/marketing/shipping-fee-promotion/create` 完全一致。
  - 加载已创建活动内容并回填表单。
  - 支持修改活动名称、期限、预算、物流渠道和运费层级。
  - 保存成功后返回列表页并刷新数据。
- 后端接口：
  - 查询编辑页详情/bootstrap。
  - 更新运费促销活动。
  - 手动结束运费促销活动。
- 数据库：
  - 优先复用现有运费促销活动主表、渠道表和层级表。
  - 如现有主表已包含手动停止/状态字段，则不新增字段。
  - 若缺少 `stopped_at`、`stopped_by` 或状态标识字段，实现时需按数据库规则补齐字段注释与历史库保障。
- Redis：
  - 更新或结束活动后清理运费促销列表缓存。
  - 同步清理订单模拟可用活动缓存，避免已编辑或已结束活动继续被订单模拟命中。

### 2.2 非范围

- 不接入真实 Shopee 平台 API。
- 不新增运费促销复制、删除、详情页和数据页。
- 不改变订单模拟的运费促销命中优先级算法。
- 不修改商品折扣、店铺券、商品券或其他营销工具的叠加规则。
- 不重做创建页 UI，仅复用同一表单组件或同一页面布局。
- 不允许编辑已产生订单后的历史订单快照；已生成订单保留创建订单时的活动名称、层级和优惠金额快照。

## 3. 页面与路由设计

### 3.1 列表页操作列

`/shopee/marketing/shipping-fee-promotion` 表格操作列保留两个入口：

| 操作 | 可见条件 | 可点击条件 | 行为 |
| --- | --- | --- | --- |
| 编辑 | 所有活动显示 | `upcoming`、`ongoing` 可点击；`ended`、`budget_exhausted`、`stopped` 禁用或置灰 | 跳转编辑页 |
| 结束 | `upcoming`、`ongoing` 显示 | 历史对局只读时禁用 | 二次确认后调用结束接口 |

建议交互：

- `编辑` 跳转时携带活动 ID：
  - 推荐 URL：`/shopee/marketing/shipping-fee-promotion/update?id={campaign_id}`。
  - 若现有路由解析更适合路径参数，也可使用 `/update/{campaign_id}`，但用户指定的新路由基础路径必须存在。
- `结束` 必须有确认弹窗或轻量确认提示：
  - 标题：`结束运费促销？`
  - 文案：`结束后该活动不会再被新订单命中，已产生的订单优惠不受影响。`
  - 确认按钮：`结束活动`。

### 3.2 编辑页

编辑页与创建页一致：

- 标题可显示为 `编辑运费促销`。
- 表单区块、字段顺序、间距、预览图与创建页保持一致。
- 底部按钮：`取消`、`保存`。
- `取消` 返回列表页。
- `保存` 调用更新接口，成功后返回列表页。

回填字段：

| 字段 | 回填来源 | 说明 |
| --- | --- | --- |
| 运费促销名称 | `promotion_name` | 最多 20 字 |
| 期限类型 | `period_type` | `no_limit` 或 `selected` |
| 开始时间 | `start_at` | 按游戏时间展示 |
| 结束时间 | `end_at` | 无期限时为空或默认展示但不提交 |
| 预算类型 | `budget_type` | `no_limit` 或 `selected` |
| 预算金额 | `budget_limit` | 自定义预算时回填 |
| 已用预算 | `budget_used` | 只读展示或用于校验，不作为可编辑输入 |
| 物流渠道 | `channels` | 勾选已保存渠道 |
| 运费层级 | `tiers` | 按 `tier_index` 或门槛升序回填 |

### 3.3 历史对局只读

`readOnly=true` 时：

- 列表页 `编辑` 和 `结束` 禁用。
- 直接访问编辑路由时，表单可展示但所有输入禁用，底部保存按钮禁用。
- 后端更新和结束接口必须拒绝写操作。

## 4. 业务规则

### 4.1 编辑规则

| 场景 | 规则 |
| --- | --- |
| 未开始活动 `upcoming` | 允许完整编辑名称、期限、预算、渠道、层级 |
| 进行中活动 `ongoing` | 允许编辑名称、结束时间、预算上限、渠道和层级；开始时间原则上不允许改早/改晚影响已发生口径 |
| 已结束活动 `ended` | 不允许编辑 |
| 预算耗尽 `budget_exhausted` | 不允许编辑，除非后续明确支持追加预算；本期不做追加预算 |
| 已手动停止 `stopped` | 不允许编辑 |

进行中活动编辑的推荐约束：

- `start_at` 保持原值，不允许前端修改。
- `end_at` 可以延后或提前，但必须晚于当前游戏时间。
- 自定义预算的新 `budget_limit` 必须大于等于 `budget_used`。
- 若从 `selected` 预算切换为 `no_limit`，后续订单不再受预算上限约束。
- 渠道和层级更新只影响后续新订单；不回写已生成订单。

### 4.2 结束规则

手动结束活动后：

- 活动状态进入 `stopped`。
- 后续订单模拟不再命中该活动。
- 列表 `已结束` Tab 需要包含 `stopped`。
- 已经命中的订单、结算、预算使用和统计保留不变。
- 结束时间记录当前对局游戏时间，而不使用真实服务器时间。

### 4.3 游戏时间口径

所有活动状态判断、编辑校验、手动结束时间、缓存失效后的可用活动重算均使用当前对局游戏时间。

- 当前 tick 来源沿用既有 Shopee 对局时间解析逻辑。
- `stopped_at` 若落库，保存游戏时间。
- `updated_at` 若为系统审计字段，可继续使用数据库真实时间；业务判断不得依赖它。

## 5. 数据模型设计

优先复用 47/48 号文档中已定义并实现的表：

- `shopee_shipping_fee_promotion_campaigns`
- `shopee_shipping_fee_promotion_channels`
- `shopee_shipping_fee_promotion_tiers`

如现有主表已具备以下字段，可直接复用：

| 字段 | 用途 |
| --- | --- |
| `status` 或手动状态字段 | 标识手动停止、预算耗尽等状态 |
| `budget_used` | 校验预算不能低于已使用金额 |
| `order_count`、`buyer_count`、`sales_amount`、`shipping_discount_amount` | 编辑/结束后保留历史统计 |

若实现时发现缺少手动结束字段，建议补充：

| 字段 | 类型 | 约束 | 注释 |
| --- | --- | --- | --- |
| `manual_status` | String(32) | not null default `active` | 手动状态：`active` 正常，`stopped` 卖家手动结束 |
| `stopped_at` | DateTime | nullable | 卖家手动结束活动的对局游戏时间 |
| `stopped_by_user_id` | Integer | nullable, index | 执行手动结束操作的用户 ID |

数据库规则：新增字段必须补齐 column comment；历史库保障或迁移脚本也必须同步维护字段注释。

## 6. 后端接口设计

接口文件沿用：`backend/apps/api-gateway/app/api/routes/shopee.py`。

### 6.1 编辑页详情/bootstrap

```http
GET /shopee/runs/{run_id}/marketing/shipping-fee-promotions/{campaign_id}
```

用途：提供编辑页回填数据、当前游戏时间、只读状态、可用渠道和规则。

响应示例：

```json
{
  "meta": {
    "run_id": 6,
    "user_id": 3,
    "read_only": false,
    "current_tick": "2026-05-13T10:00:00",
    "currency": "RM",
    "editable": true,
    "editable_reason": null
  },
  "form": {
    "id": 12,
    "promotion_name": "满 RM50 运费优惠",
    "status": "ongoing",
    "period_type": "selected",
    "start_at": "2026-05-13T09:00:00",
    "end_at": "2026-05-14T09:00:00",
    "budget_type": "selected",
    "budget_limit": 100,
    "budget_used": 12,
    "channels": ["standard", "bulky"],
    "tiers": [
      {
        "tier_index": 1,
        "min_spend_amount": 50,
        "fee_type": "fixed_fee",
        "fixed_fee_amount": 2
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
    "name_max_length": 20,
    "currency": "RM"
  }
}
```

### 6.2 更新运费促销活动

```http
PUT /shopee/runs/{run_id}/marketing/shipping-fee-promotions/{campaign_id}
```

请求结构与创建接口一致，增加进行中活动的限制校验。

后端校验：

- 当前 run/user 必须匹配。
- 历史回溯模式禁止更新。
- `ended/budget_exhausted/stopped` 活动禁止更新。
- 活动名称不能为空且不超过 20 字。
- 自定义期限必须满足 `start_at < end_at`。
- 进行中活动的 `end_at` 必须晚于当前游戏时间。
- 自定义预算必须大于 0，且不得小于 `budget_used`。
- 至少选择 1 个可用物流渠道。
- 层级数量 `1 ~ 3`，门槛不可重复，按金额升序保存。
- `fixed_fee` 必须提供 `fixed_fee_amount >= 0`；`free_shipping` 保存为空。

保存策略：

- 主表更新基础字段。
- 渠道表采用“删除旧渠道后重建”或“差量更新”，以现有实现简单可靠为优先。
- 层级表采用“删除旧层级后重建”或“差量更新”，保持 `tier_index` 连续。
- 更新后清理列表缓存、详情缓存和订单模拟可用活动缓存。

响应示例：

```json
{
  "id": 12,
  "status": "ongoing",
  "message": "运费促销更新成功"
}
```

### 6.3 手动结束运费促销活动

```http
POST /shopee/runs/{run_id}/marketing/shipping-fee-promotions/{campaign_id}/end
```

后端校验：

- 当前 run/user 必须匹配。
- 历史回溯模式禁止结束。
- 仅 `upcoming/ongoing` 可结束。
- 已结束、预算耗尽或已停止活动重复结束时返回明确错误，或幂等返回当前状态；建议返回明确错误，避免学生误以为操作成功改变了状态。

处理逻辑：

- 写入手动停止状态。
- 写入 `stopped_at = current_game_tick`。
- 不修改历史订单、结算和活动已累计统计。
- 清理运费促销列表缓存、活动详情缓存和订单模拟可用活动缓存。

响应示例：

```json
{
  "id": 12,
  "status": "stopped",
  "status_label": "已结束",
  "message": "运费促销已结束"
}
```

## 7. Redis 缓存与限流

复用既有前缀，并补充详情缓存：

| 场景 | 建议 key | 失效时机 |
| --- | --- | --- |
| 列表缓存 | `shopee:shipping_fee_promotion:list:{run_id}:{user_id}:...` | 创建、更新、结束、订单命中、预算耗尽 |
| 编辑详情缓存 | `shopee:shipping_fee_promotion:detail:{run_id}:{user_id}:{campaign_id}` | 更新、结束 |
| 订单模拟可用活动缓存 | `shopee:shipping_fee_promotion:active:{run_id}:{user_id}:{tick_bucket}` | 创建、更新、结束、预算耗尽 |

限流：

- 查询详情可复用列表查询限流等级。
- 更新与结束属于写操作，复用创建接口写限流等级。

## 8. 前端实现设计

### 8.1 路由接入

`ShopeePage.tsx` 需新增视图枚举与路径识别：

- `marketing-shipping-fee-promotion-update`
- `/shopee/marketing/shipping-fee-promotion/update`

路由参数建议通过 query string 读取：

```text
/shopee/marketing/shipping-fee-promotion/update?id=12
```

若缺少 `id`：

- 展示错误提示 `缺少运费促销活动 ID`。
- 提供返回列表按钮。

### 8.2 表单复用

建议将 `ShippingFeePromotionCreateView.tsx` 调整为同时支持 create/update 两种模式，或抽出共用表单组件。

最低改动方案：

- 新增 `ShippingFeePromotionUpdateView.tsx`。
- 复用创建页布局与大部分 JSX。
- 初期可复制创建页结构后只替换数据加载、标题、提交接口和按钮文案。

更推荐方案：

- 抽出 `ShippingFeePromotionFormView` 或内部组件，接收：
  - `mode: 'create' | 'update'`
  - `campaignId?: number`
  - `readOnly?: boolean`
- 创建页和编辑页都使用同一表单，减少后续字段规则漂移。

### 8.3 列表页操作

`编辑`：

- 点击后调用页面导航进入 update 路由。
- 禁用状态展示灰色文字或禁止点击。

`结束`：

- 点击后弹出确认。
- 确认后调用 end 接口。
- 成功后刷新当前 Tab 列表与 Tab 计数。
- 如果当前 Tab 是 `进行中`，结束后的活动应从当前列表消失或状态刷新后进入 `已结束`。

## 9. 订单模拟影响

编辑和结束只影响后续新订单：

- 已生成订单保留订单级促销快照，不回写。
- 更新后的渠道、层级、预算和时间对后续订单模拟生效。
- 手动结束后，订单模拟加载可用活动时必须排除该活动。
- 若订单模拟与更新/结束并发，以数据库事务提交后的状态为准；缓存清理后下一次 tick 或下一次订单模拟读取新状态。

## 10. 验收标准

实现完成后应满足：

1. 列表页操作列 `编辑` 可进入 `/shopee/marketing/shipping-fee-promotion/update?id={id}`。
2. 编辑页布局与创建页一致，并正确回填名称、期限、预算、渠道和层级。
3. 编辑未开始活动后，列表展示新名称、新时间、新预算与新层级摘要。
4. 编辑进行中活动时，不允许将预算改到低于已使用预算。
5. 编辑进行中活动后，只影响后续新订单，不改写历史订单促销快照。
6. 点击 `结束` 需要确认，确认后活动状态进入 `stopped` 并归入 `已结束` Tab。
7. 已结束、预算耗尽、已停止活动不可编辑、不可重复结束。
8. 历史对局只读模式下，编辑与结束均不可写入。
9. 更新和结束后 Redis 列表缓存、详情缓存与订单模拟可用活动缓存失效。
10. 所有业务时间判断使用对局游戏时间。
11. 如新增数据库字段，表注释/字段注释与历史库保障同步维护。

## 11. 建议验证用例

| 用例 | 操作 | 预期 |
| --- | --- | --- |
| 编辑未开始活动 | 修改名称、预算、渠道、层级并保存 | 列表展示更新后的摘要 |
| 编辑进行中活动 | 延后结束时间并保存 | 后续订单继续可命中活动 |
| 预算低于已使用 | 将预算改为小于 `budget_used` | 后端拒绝并返回明确错误 |
| 结束进行中活动 | 点击结束并确认 | 状态变为 `stopped`，进入已结束 Tab |
| 结束后订单模拟 | 结束活动后推进订单模拟 | 新订单不再命中该活动 |
| 历史对局 | 回放模式点击编辑或结束 | 前端禁用，后端拒绝写入 |
| 缺少活动 ID | 直接访问 update 无 id | 展示错误并可返回列表 |

## 12. 后续待办

1. 按本文档实现编辑页路由、表单回填、更新接口与结束接口。
2. 后续补充运费促销详情页、数据页、复制和删除能力。
3. 若运营统计页需要展示编辑历史，可另行设计活动变更日志表。

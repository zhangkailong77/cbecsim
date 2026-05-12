# 36-Shopee 店铺代金券创建前后端数据库 Redis 实现设计

> 创建日期：2026-05-06  
> 状态：设计完成，待实现

## 1. 目标

为 Shopee 营销中心代金券模块接入“店铺代金券”创建能力，使 `/shopee/marketing/vouchers/create` 页面从前端静态表单升级为可读取初始化数据、校验输入、提交创建并落库的完整流程。

本期重点是接口对接和业务数据闭环：

- 前端样式和布局基本沿用现有 `ShopVoucherCreateView.tsx`，不做大规模视觉重构。
- 后端新增店铺代金券创建 bootstrap、创建提交、列表查询所需的数据结构和接口。
- 数据库新增店铺代金券活动表，保存影响经营结果的代金券规则与状态。
- Redis 用于创建页 bootstrap、代金券列表/表现缓存、频率限制和创建后缓存失效。
- 为后续订单模拟接入代金券优惠、订单归因和表现统计预留清晰字段。

## 2. 范围与非范围

### 2.1 本期范围

- 店铺代金券类型：仅实现 `shop_voucher`。
- 前端创建页接口对接：
  - 初始化表单默认值。
  - 提交创建店铺代金券。
  - 创建成功后返回代金券列表页。
- 后端接口：
  - 创建页 bootstrap。
  - 创建店铺代金券。
  - 代金券列表查询从 mock 切换到真实数据的接口预留。
- 数据库：
  - 新增店铺代金券表，并补齐表注释和字段注释。
  - 为后续订单归因和统计预留必要字段。
- Redis：
  - 创建页 bootstrap 缓存。
  - 列表/表现缓存。
  - 创建接口频率限制。
  - 创建成功后的缓存失效。

### 2.2 非范围

- 不重做 `/shopee/marketing/vouchers/create` 的前端布局和视觉样式。
- 不实现商品代金券、专属代金券、直播代金券、视频代金券、关注礼代金券。
- 不接入真实 Shopee 平台 API。
- 不实现买家端领券页面或买家主动领券行为。
- 不在本期完整实现订单模拟命中代金券后的价格改写；仅在设计中定义后续接入口径。
- 不实现复杂叠加优惠策略；本期先定义与其他营销活动的互斥优先级。

## 3. 业务规则

### 3.1 店铺代金券定义

店铺代金券适用于店铺内所有可售商品。订单满足最低消费金额后，可按固定金额或折扣比例减免。

| 字段 | 规则 |
| --- | --- |
| 代金券类型 | 固定为 `shop_voucher` |
| 代金券名称 | 卖家可见，买家不展示，最多 100 字符 |
| 代金券代码 | `HOME` 前缀 + 卖家输入后缀；后缀仅允许 `A-Z`、`0-9`，最多 5 字符 |
| 使用期限 | `start_at < end_at`，按游戏时间口径存储与判断 |
| 提前展示 | 仅影响后续列表/展示状态，不影响订单可用开始时间 |
| 奖励类型 | V1 仅启用折扣，不提交虾币返还 |
| 折扣类型 | 支持 `fixed_amount`（固定金额）和 `percent`（百分比） |
| 优惠金额 | 固定金额模式必填且大于 0，单位为店铺币种 |
| 优惠百分比 | 百分比模式必填且大于 0、小于等于 100，单位为 `%OFF` |
| 最大折扣金额 | 百分比模式可选 `set_amount`（设置金额）或 `no_limit`（无限制）；设置金额时必须大于 0 |
| 最低消费金额 | 固定金额模式必须大于等于优惠金额；百分比模式必须大于 0 |
| 使用数量 | 所有买家可使用总量，必须为正整数 |
| 每位买家最大发放量 | V1 默认 `1`，必须为正整数，且不超过使用数量 |
| 展示设置 | 支持 `all_pages`、`specific_channels`、`code_only`，特定渠道 V1 先支持订单支付页面展示 |
| 适用商品 | 店铺内所有商品 |

### 3.2 状态规则

代金券状态由当前游戏时间和库存/使用量计算。

| 状态 | 条件 |
| --- | --- |
| `upcoming` | 当前游戏时间早于 `start_at` |
| `ongoing` | `start_at <= 当前游戏时间 < end_at` 且未售罄、未停止 |
| `sold_out` | `used_count >= usage_limit` |
| `ended` | 当前游戏时间晚于等于 `end_at` |
| `stopped` | 卖家手动结束，后续扩展 |

数据库保存 `status` 快照，接口返回时可以按当前游戏时间动态修正展示状态，避免仅依赖旧状态。

### 3.3 与订单模拟的关系

本期创建流程只落库，不强制立即改订单模拟。但字段必须支持后续接入：

- 命中条件：订单属于同一 `run_id/user_id` 店铺，订单创建游戏时间在代金券使用期限内，订单商品为店铺商品，订单商品小计满足 `min_spend_amount`。
- 优惠计算：
  - 固定金额：`discount_amount = min(voucher_amount, order_subtotal)`。
  - 百分比：`discount_amount = order_subtotal * discount_percent / 100`；若 `max_discount_type=set_amount`，再取 `min(discount_amount, max_discount_amount)`；若 `max_discount_type=no_limit`，仅受订单小计上限约束。
- 数量扣减：订单成功归因后增加 `used_count`。
- 买家限用：同一买家对同一代金券累计使用次数不超过 `per_buyer_limit`。
- 归因字段：后续订单级写入 `marketing_campaign_type='shop_voucher'`、`marketing_campaign_id`、`marketing_campaign_name_snapshot`。

### 3.4 营销互斥优先级

为避免叠加规则复杂化，V1 建议使用互斥策略：

```text
限时抢购 > 单品折扣 / 套餐优惠 / 加价购 / 满额赠 > 店铺代金券
```

含义：

- 若订单主商品已经命中限时抢购、单品折扣、套餐优惠、加价购或满额赠，本期不再叠加店铺代金券。
- 店铺代金券主要用于未命中其他强活动的普通订单。
- 后续如需要叠加，可另开设计文档明确平台规则和统计口径。

## 4. 数据模型设计

### 4.1 新增 ORM：`ShopeeShopVoucherCampaign`

建议新增表：`shopee_shop_voucher_campaigns`。

> 数据库 Schema Rules 要求：新建表必须添加表注释，新增字段必须添加字段注释。

| 字段 | 类型 | 约束 | 注释 |
| --- | --- | --- | --- |
| `id` | Integer | PK | 店铺代金券活动 ID |
| `run_id` | Integer | FK `game_runs.id`, index | 所属对局 ID |
| `user_id` | Integer | FK `users.id`, index | 所属卖家用户 ID |
| `voucher_type` | String(32) | not null, default `shop_voucher` | 代金券类型，V1 固定店铺代金券 |
| `voucher_name` | String(255) | not null | 卖家可见的代金券名称 |
| `voucher_code` | String(32) | not null | 完整代金券代码，如 `HOME12345` |
| `code_prefix` | String(16) | not null, default `HOME` | 代金券代码前缀 |
| `code_suffix` | String(16) | not null | 卖家输入的代码后缀 |
| `status` | String(32) | not null, index | 状态：upcoming/ongoing/sold_out/ended/stopped |
| `start_at` | DateTime(timezone=True) | not null, index | 代金券可使用开始游戏时间 |
| `end_at` | DateTime(timezone=True) | not null, index | 代金券可使用结束游戏时间 |
| `display_before_start` | Boolean | not null, default false | 是否提前展示代金券 |
| `display_start_at` | DateTime(timezone=True) | nullable | 提前展示开始游戏时间；未提前展示时为空 |
| `reward_type` | String(32) | not null, default `discount` | 奖励类型，V1 固定折扣 |
| `discount_type` | String(32) | not null, default `fixed_amount` | 折扣类型：fixed_amount/percent |
| `discount_amount` | Float | nullable | 固定金额优惠，单位为店铺币种 |
| `discount_percent` | Float | nullable | 百分比优惠，单位为百分比 |
| `max_discount_type` | String(32) | not null, default `set_amount` | 最大折扣金额类型：set_amount/no_limit |
| `max_discount_amount` | Float | nullable | 百分比优惠最高抵扣金额，单位为店铺币种；无限制时为空 |
| `min_spend_amount` | Float | not null, default 0 | 最低消费金额，单位为店铺币种 |
| `usage_limit` | Integer | not null | 所有买家可使用总代金券数量 |
| `used_count` | Integer | not null, default 0 | 已使用数量 |
| `per_buyer_limit` | Integer | not null, default 1 | 每位买家可使用次数上限 |
| `display_type` | String(32) | not null, default `all_pages` | 展示方式：all_pages/specific_channels/code_only |
| `display_channels` | Text | nullable | 特定渠道配置 JSON，V1 支持 checkout_page |
| `applicable_scope` | String(32) | not null, default `all_shop_products` | 适用商品范围，V1 固定全店商品 |
| `sales_amount` | Float | not null, default 0 | 代金券归因销售额，单位为店铺币种 |
| `order_count` | Integer | not null, default 0 | 代金券归因订单数 |
| `buyer_count` | Integer | not null, default 0 | 使用代金券买家数 |
| `created_at` | DateTime(timezone=True) | not null | 创建时间 |
| `updated_at` | DateTime(timezone=True) | not null | 更新时间 |

建议索引：

```python
Index("ix_shopee_shop_vouchers_run_user_status", "run_id", "user_id", "status")
Index("ix_shopee_shop_vouchers_run_user_time", "run_id", "user_id", "start_at", "end_at")
Index("ix_shopee_shop_vouchers_run_user_code", "run_id", "user_id", "voucher_code", unique=True)
```

### 4.2 可选新增使用记录表：`ShopeeShopVoucherUsage`

若本期只做创建，可以不立即建使用记录表；若同步接订单模拟，建议新增：`shopee_shop_voucher_usages`。

| 字段 | 类型 | 约束 | 注释 |
| --- | --- | --- | --- |
| `id` | Integer | PK | 使用记录 ID |
| `campaign_id` | Integer | FK | 店铺代金券活动 ID |
| `run_id` | Integer | FK, index | 对局 ID |
| `user_id` | Integer | FK, index | 卖家用户 ID |
| `buyer_profile_id` | Integer | nullable, index | 模拟买家画像 ID |
| `order_id` | Integer | FK `shopee_orders.id`, index | 归因订单 ID |
| `discount_amount` | Float | not null | 本次抵扣金额 |
| `order_subtotal` | Float | not null | 抵扣前订单商品小计 |
| `used_at` | DateTime(timezone=True) | not null, index | 使用发生的游戏时间 |

用途：

- 计算每位买家限用。
- 统计买家数、使用率和订单归因。
- 避免同一订单重复扣减代金券数量。

## 5. 后端接口设计

接口文件沿用：`backend/apps/api-gateway/app/api/routes/shopee.py`。

### 5.1 创建页 Bootstrap

```http
GET /shopee/runs/{run_id}/marketing/vouchers/create/bootstrap?voucher_type=shop_voucher
```

用途：为前端创建页提供默认值、规则和只读状态。

响应示例：

```json
{
  "meta": {
    "run_id": 1,
    "user_id": 2,
    "voucher_type": "shop_voucher",
    "read_only": false,
    "current_tick": "2026-06-05T08:32:00+07:00",
    "currency": "RM"
  },
  "form": {
    "voucher_name": "",
    "code_prefix": "HOME",
    "code_suffix_max_length": 5,
    "start_at": "2026-06-05T08:32",
    "end_at": "2026-06-05T09:32",
    "display_before_start": false,
    "display_start_at": null,
    "reward_type": "discount",
    "discount_type": "fixed_amount",
    "discount_amount": null,
    "discount_percent": null,
    "max_discount_type": "set_amount",
    "max_discount_amount": null,
    "min_spend_amount": null,
    "usage_limit": null,
    "per_buyer_limit": 1,
    "display_type": "all_pages",
    "display_channels": [],
    "applicable_scope": "all_shop_products"
  },
  "rules": {
    "voucher_name_max_length": 100,
    "code_suffix_pattern": "^[A-Z0-9]{1,5}$",
    "min_duration_minutes": 1,
    "max_duration_days": 180,
    "discount_types": ["fixed_amount", "percent"],
    "max_discount_types": ["set_amount", "no_limit"],
    "display_types": ["all_pages", "specific_channels", "code_only"],
    "display_channels": ["checkout_page"],
    "requires_usage_limit": true
  }
}
```

### 5.2 代金券代码可用性检查

```http
GET /shopee/runs/{run_id}/marketing/vouchers/code/check?voucher_type=shop_voucher&code_suffix=JUN01
```

用途：前端在“代金券代码”输入后检查完整代码是否可用，避免用户提交时才发现重复。

请求规则：

- `voucher_type` V1 仅允许 `shop_voucher`。
- `code_suffix` 后端统一转大写后校验 `^[A-Z0-9]{1,5}$`。
- 完整代码按 `HOME + code_suffix` 生成。
- 同一 `run_id/user_id` 下 `voucher_code` 不可重复。

响应示例：

```json
{
  "code_prefix": "HOME",
  "code_suffix": "JUN01",
  "voucher_code": "HOMEJUN01",
  "available": true,
  "message": "代金券代码可用"
}
```

重复或格式错误时：

```json
{
  "code_prefix": "HOME",
  "code_suffix": "JUN01",
  "voucher_code": "HOMEJUN01",
  "available": false,
  "message": "该代金券代码已存在，请更换后缀"
}
```

该接口只做校验，不创建活动、不写入业务表；可加短 TTL 缓存，但创建提交仍必须再次做唯一性校验。

### 5.3 创建店铺代金券

```http
POST /shopee/runs/{run_id}/marketing/vouchers/campaigns
```

请求示例：

```json
{
  "voucher_type": "shop_voucher",
  "voucher_name": "6月店铺满减券",
  "code_suffix": "JUN01",
  "start_at": "2026-06-05T08:32",
  "end_at": "2026-06-05T09:32",
  "display_before_start": false,
  "display_start_at": null,
  "reward_type": "discount",
  "discount_type": "fixed_amount",
  "discount_amount": 45,
  "discount_percent": null,
  "max_discount_type": "set_amount",
  "max_discount_amount": null,
  "min_spend_amount": 1500,
  "usage_limit": 10000,
  "per_buyer_limit": 1,
  "display_type": "all_pages",
  "display_channels": []
}
```

响应示例：

```json
{
  "campaign_id": 123,
  "voucher_type": "shop_voucher",
  "status": "upcoming",
  "redirect_url": "/shopee/marketing/vouchers"
}
```

校验规则：

- `run_id` 必须属于当前用户可操作对局。
- 历史回溯只读模式禁止创建。
- `voucher_type` 仅允许 `shop_voucher`。
- `voucher_name` 必填且不超过 100 字符。
- `code_suffix` 转大写后匹配 `^[A-Z0-9]{1,5}$`。
- 同一 `run_id/user_id` 下 `voucher_code` 唯一。
- `start_at < end_at`，且活动时长不超过 `180` 天。
- `discount_type=fixed_amount` 时 `discount_amount > 0`，`discount_percent/max_discount_amount` 不参与计算。
- `discount_type=percent` 时 `0 < discount_percent <= 100`，`discount_amount` 不参与计算。
- `discount_type=percent` 且 `max_discount_type=set_amount` 时 `max_discount_amount > 0`。
- `discount_type=percent` 且 `max_discount_type=no_limit` 时 `max_discount_amount` 应为空。
- `min_spend_amount > 0`；固定金额模式下还需 `min_spend_amount >= discount_amount`。
- `usage_limit > 0`，`per_buyer_limit > 0`，且 `per_buyer_limit <= usage_limit`。
- `display_type` 仅允许 `all_pages/specific_channels/code_only`；`specific_channels` 模式下 `display_channels` 仅允许 `checkout_page`。

### 5.4 代金券列表接口预留

```http
GET /shopee/runs/{run_id}/marketing/vouchers?status=all&keyword=&page=1&page_size=20
```

响应中的列表字段应兼容现有前端列表展示：

```json
{
  "summary": {
    "sales_amount": 0,
    "order_count": 0,
    "usage_rate": 0,
    "buyer_count": 0
  },
  "tabs": [
    { "key": "all", "label": "全部", "count": 1 },
    { "key": "ongoing", "label": "进行中", "count": 0 },
    { "key": "upcoming", "label": "即将开始", "count": 1 },
    { "key": "ended", "label": "已结束", "count": 0 }
  ],
  "list": {
    "page": 1,
    "page_size": 20,
    "total": 1,
    "items": [
      {
        "id": 123,
        "voucher_name": "6月店铺满减券",
        "voucher_code": "HOMEJUN01",
        "voucher_type": "Shop Voucher",
        "voucher_type_label": "店铺代金券",
        "discount_type": "fixed_amount",
        "discount_label": "RM 45",
        "status": "upcoming",
        "status_label": "即将开始",
        "scope_label": "所有商品",
        "usage_limit": 10000,
        "used_count": 0,
        "period": "05/06/2026 08:32 - 05/06/2026 09:32"
      }
    ]
  }
}
```

## 6. 前端对接设计

### 6.1 页面文件

主要修改：`frontend/src/modules/shopee/views/ShopVoucherCreateView.tsx`。

保持现有布局，只新增状态、接口调用和提交逻辑：

- `loading`：bootstrap 加载状态。
- `saving`：提交状态。
- `error`：加载错误提示。
- 表单状态：
  - `voucherName`
  - `codeSuffix`
  - `startAt`
  - `endAt`
  - `displayBeforeStart`
  - `discountType`：`fixed_amount` / `percent`
  - `discountAmount`：固定金额模式使用
  - `discountPercent`：百分比模式使用
  - `maxDiscountType`：`set_amount` / `no_limit`
  - `maxDiscountAmount`：百分比且设置最大折扣金额时使用
  - `minSpendAmount`
  - `usageLimit`
  - `perBuyerLimit`
  - `displayType`：`all_pages` / `specific_channels` / `code_only`
  - `displayChannels`：特定渠道模式下使用，V1 支持 `checkout_page`

### 6.2 初始化流程

页面挂载后：

```text
读取 token -> GET create/bootstrap -> 填充默认值 -> 渲染表单 -> 代金券代码输入后调用 code/check 校验可用性
```

失败时展示顶部错误条，不破坏当前静态布局。

### 6.3 提交流程

点击“确认”后：

```text
前端轻校验 -> POST campaigns -> 成功 alert/提示 -> onBackToVouchers() -> 列表页后续刷新真实数据
```

前端只做必要用户体验校验；最终以后端校验为准。

### 6.4 保持不改的内容

- 不改页面整体双栏布局。
- 不改白色卡片、右侧说明卡、吸底操作栏样式。
- 不改已接入的 `DateTimePicker` 样式。
- 不实现商品选择弹窗，因为店铺代金券 V1 适用所有商品。

## 7. Redis 设计

沿用当前项目 Redis key 风格，使用 `REDIS_PREFIX` 前缀。

### 7.1 Bootstrap 缓存

```text
{REDIS_PREFIX}:cache:shopee:voucher:create:bootstrap:{run_id}:{user_id}:{voucher_type}
```

- TTL：建议 60 秒。
- 内容：创建页默认值和规则。
- 失效：通常无需主动失效；若创建后需要改变默认代码建议，可创建成功后删除。

### 7.2 列表缓存

```text
{REDIS_PREFIX}:cache:shopee:voucher:list:{run_id}:{user_id}:{status}:{page}:{digest}
```

- TTL：建议 30~60 秒。
- `digest` 包含 keyword、page_size 等筛选条件。
- 创建、编辑、结束、订单归因使用后失效。

### 7.3 表现缓存

```text
{REDIS_PREFIX}:cache:shopee:voucher:performance:{run_id}:{user_id}
```

- TTL：建议 60 秒。
- 数据：销售额、订单数、使用率、买家数。
- 创建代金券、订单模拟归因、订单取消/结算变动后失效。

### 7.4 频率限制

```text
{REDIS_PREFIX}:ratelimit:shopee:voucher:create:user:{user_id}
```

建议限制：每分钟 20 次创建请求。

### 7.5 统一失效函数

新增：

```python
def _invalidate_shopee_voucher_cache(*, run_id: int, user_id: int, campaign_id: int | None = None) -> None:
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:voucher:create:bootstrap:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:voucher:list:{run_id}:{user_id}:")
    cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:voucher:performance:{run_id}:{user_id}")
    if campaign_id:
        cache_delete_prefix(f"{REDIS_PREFIX}:cache:shopee:voucher:detail:{run_id}:{user_id}:{campaign_id}")
```

## 8. 后续订单模拟接入口径

当后续实现店铺代金券影响订单模拟时，在 `shopee_order_simulator.py` 中新增：

```python
def _load_ongoing_shop_voucher_map(db: Session, *, run_id: int, user_id: int, tick_time: datetime) -> list[dict[str, Any]]:
    ...
```

命中流程建议：

1. 加载当前游戏时间有效的 `ongoing` 店铺代金券。
2. 订单候选商品完成基础价格、库存和其他营销活动判断后，若未命中更高优先级营销活动，再尝试店铺代金券。
3. 判断订单商品小计是否满足 `min_spend_amount`。
4. 判断代金券剩余数量和买家限用。
5. 计算抵扣金额，写入订单归因字段和使用记录。
6. 更新 `used_count/order_count/sales_amount/buyer_count`。
7. 失效代金券列表和表现缓存。

注意：订单金额、资金、订单、经营结果属于必须落库数据，不能仅存在前端状态或 Redis。

## 9. 验收标准

### 9.1 创建页

- 访问 `/shopee/marketing/vouchers/create` 时能请求 bootstrap 并填充默认值。
- 日期选择器继续使用现有 `DateTimePicker`，样式不漂移。
- 只读回溯模式下创建按钮不可提交，并提示只读。
- 点击确认时会调用后端创建接口。
- 创建成功后返回 `/shopee/marketing/vouchers`。

### 9.2 后端与数据库

- 新增表包含表注释和所有字段注释。
- 创建接口能成功落库店铺代金券。
- 同一对局同一卖家下代金券代码唯一。
- 非法时间、非法代码、非法金额、非法使用数量均返回明确错误。
- 创建成功后 Redis 相关列表/表现缓存被失效。

### 9.3 列表与统计预留

- 代金券列表接口能返回真实店铺代金券数据。
- 状态 Tab 能按真实状态统计数量。
- 表现面板字段可以先返回 0，但来源结构应来自接口，不再依赖前端 mock。

### 9.4 验证命令

后端：

```bash
python -m py_compile backend/apps/api-gateway/app/models.py backend/apps/api-gateway/app/db.py backend/apps/api-gateway/app/api/routes/shopee.py
```

前端：

```bash
npm run build --prefix frontend
```

如新增测试，优先覆盖：

- 创建成功。
- 代码重复。
- 金额/门槛校验。
- 时间范围校验。
- 只读模式禁止创建。

## 10. 实施顺序建议

1. 数据库与 ORM：新增 `ShopeeShopVoucherCampaign`，补齐注释、索引和关系。
2. 后端 schema：新增 bootstrap、创建请求、创建响应、列表响应模型。
3. 后端接口：实现 bootstrap 和创建接口，接入 Redis 缓存和限流。
4. 前端创建页：在现有布局上接入 bootstrap、表单状态、校验和提交。
5. 代金券列表页：将 mock 列表和表现面板切换到真实接口。
6. 验证：执行 py_compile、前端构建和浏览器创建流程检查。
7. 后续扩展：另行接入订单模拟命中代金券、使用记录、订单归因和表现统计。

# 34-Shopee 限时抢购数据页前后端数据库 Redis 打通设计

> 创建日期：2026-04-30  
> 状态：设计完成，待实现

## 1. 目标

打通 Shopee `/shopee/marketing/flash-sale/data?campaign_id=...` 限时抢购数据页的前端、后端、数据库与 Redis，使已搭建好的官方风格前端页面从静态占位数据切换为真实活动经营数据。

本设计聚焦单个“我的店铺限时抢购”活动的数据详情页，目标是让卖家在活动进行中或结束后查看：

- 活动基础信息：状态、编辑期、活动期、活动商品数量。
- 关键指标：提醒设置数、商品浏览量、商品点击数、CTR、销售额、订单数。
- 商品排名：按主商品汇总，并下钻展示变体级活动库存、折后价、销售额、订单数、售出件数。
- 订单类型切换：`已下单` 与 `已确认订单` 两套统计口径。
- 数据导出：按当前活动与订单类型导出数据。

本期只设计实现路径，不执行代码修改。

## 2. 范围与非范围

### 2.1 本期范围

- 前端数据页接入真实接口：
  - 保留现有 `ShopFlashSaleDataView` 官方风格布局。
  - 替换静态指标卡与商品排名数据。
  - 接入加载态、空状态、错误提示与只读模式导出禁用。
- 后端新增限时抢购数据页接口：
  - 数据页概览接口。
  - 商品排名接口。
  - 数据导出接口。
- 数据统计口径：
  - 订单和销售额按订单明细营销归因 `marketing_campaign_type='flash_sale'` + `marketing_campaign_id=campaign_id` 统计。
  - 游戏时间作为活动时间、趋势与导出时间口径，不使用真实世界日期展示业务周期。
  - 支持 `placed`（已下单）与 `confirmed`（已确认订单）两种订单口径。
- 数据库：
  - 优先复用限时抢购活动表、活动商品表、订单表与订单明细表。
  - 如后续需要真实曝光/浏览埋点，可新增轻量事件表；本期接口可先由现有 `click_count/reminder_count` 与订单归因字段驱动。
- Redis：
  - 数据页概览缓存。
  - 商品排名缓存。
  - 导出限流。
  - 订单生成、活动启停、活动创建后缓存失效。

### 2.2 非范围

- 不接入真实 Shopee 商家后台 API。
- 不实现真实广告 ROAS 服务，顶部绿色横幅仍作为官方样式提示区。
- 不实现买家端曝光、浏览、点击埋点全链路；`商品浏览量` 与 `商品点击数` V1 可先使用活动表已有计数字段或后续事件表预留口径。
- 不实现复杂 BI 自定义报表、跨活动对比或多活动聚合。
- 不改变限时抢购订单模拟概率、成交价、库存扣减与营销互斥规则。
- 不新增异步导出任务中心；V1 导出可同步返回 CSV。

## 3. 页面流程

### 3.1 进入数据页

1. 用户在 `/shopee/marketing/flash-sale` 活动列表点击“数据”。
2. 前端跳转：

```text
/u/{public_id}/shopee/marketing/flash-sale/data?campaign_id={campaign_id}
```

3. `ShopeePage` 解析为 `marketing-flash-sale-data` 视图。
4. `Header` 面包屑展示：

```text
营销中心 > 我的店铺限时抢购 > 限时抢购数据
```

5. 页面隐藏左侧菜单栏，展示官方风格数据页主体。

### 3.2 首屏加载流程

1. 前端读取 URL 中的 `campaign_id`。
2. 若缺少或非法，显示空状态：`缺少限时抢购活动 ID`。
3. 调用概览接口加载：
   - 活动基础信息。
   - 订单类型选项与默认值。
   - 关键指标。
4. 调用商品排名接口加载：
   - 主商品汇总行。
   - 变体明细行。
5. 页面按返回数据渲染指标卡和商品排名。

### 3.3 订单类型切换流程

1. 用户打开“订单类型”下拉。
2. 选择 `已下单` 或 `已确认订单`。
3. 前端重新请求概览与商品排名接口，并携带：

```text
order_type=placed | confirmed
```

4. 后端按订单类型过滤订单状态后返回统计结果。

### 3.4 查看活动详情

现有页面标题区“查看活动详情”按钮应跳转到：

```text
/u/{public_id}/shopee/marketing/flash-sale/detail?campaign_id={campaign_id}
```

按钮语义是“从数据页查看活动详情”，不是返回列表。

### 3.5 导出数据

1. 用户点击“导出数据”。
2. 前端调用导出接口，携带 `campaign_id` 与当前 `order_type`。
3. 后端进行导出限流与权限校验。
4. 返回 CSV 文件，内容与商品排名口径一致。
5. 历史回溯只读模式下禁用导出按钮，并提示：`历史对局回溯模式下不可导出数据`。

## 4. 业务规则

### 4.1 权限与活动归属

所有接口必须校验：

```text
campaign.run_id = 当前 run_id
campaign.user_id = 当前用户
```

历史回溯模式允许读取数据，不允许导出或触发任何写入动作。

### 4.2 活动状态展示

活动展示状态由当前游戏 tick 与活动字段共同计算：

| 展示状态 | 条件 |
| --- | --- |
| `未开始` | `campaign.status='active'` 且 `current_tick < start_tick` |
| `进行中` | `campaign.status='active'` 且 `start_tick <= current_tick < end_tick` |
| `已结束` | `current_tick >= end_tick` |
| `已停用` | `campaign.status='disabled'` |

数据页应返回状态 label 与颜色语义，前端只负责展示。

### 4.3 订单类型口径

| 前端文案 | 参数值 | 统计范围 |
| --- | --- | --- |
| `已下单` | `placed` | 排除取消订单，包含待出货、运输中、已完成等已成功生成订单 |
| `已确认订单` | `confirmed` | 只统计已确认履约口径订单，建议包含 `toship/shipping/completed`，排除 `cancelled` |

说明：

- 若后续系统引入更细的支付确认状态，可将 `confirmed` 收口到支付/确认后的状态。
- 当前模拟订单创建即代表有效下单，因此 V1 中 `placed` 与 `confirmed` 可先保持同一过滤结果；接口仍保留参数，避免后续改前端契约。

### 4.4 指标口径

| 指标 | 口径 |
| --- | --- |
| 提醒设置数 | `shopee_flash_sale_campaigns.reminder_count` |
| 商品浏览量 | V1 使用活动表或事件表预留浏览计数；无数据时返回 `0` |
| 商品点击数 | `shopee_flash_sale_campaigns.click_count` 或事件表点击计数 |
| CTR | `click_count / max(product_view_count, 1)`，无浏览量时返回 `0.00%` |
| 销售额 | 命中活动的订单明细成交小计之和 |
| 订单数 | 命中活动的去重订单数 |
| 售出件数 | 命中活动的订单明细数量之和 |
| 买家数 | 命中活动的去重买家数，后续如页面需要可返回 |

销售额使用订单明细成交价：

```text
sum(shopee_order_items.deal_price * shopee_order_items.quantity)
```

若订单明细缺少 `deal_price`，可回退使用 `unit_price` 或订单模拟写入的成交单价字段，但实现时应优先使用当前代码中实际存在的成交价字段。

### 4.5 商品排名口径

商品排名按主商品 `listing_id` 聚合：

- 主商品行展示：商品图、商品名、Item ID、总销售额、总订单数、总售出件数。
- 变体行展示：变体名、活动库存、折后价、变体销售额、变体订单数、变体售出件数。
- 排序默认按销售额降序；销售额相同按订单数、售出件数、活动商品 ID 排序。
- 只展示当前活动下的活动商品，包括未售出的启用/停用变体。
- 未售出变体指标显示 0，但仍展示活动库存与折后价，便于对照官方页面。

### 4.6 时间口径

- 活动编辑期、活动期、导出文件中的时间均使用游戏时间展示。
- 活动期来自 `start_tick/end_tick` 转换后的游戏日期与时分。
- 数据统计不按真实世界日期截断，只按当前活动 ID 与订单归因筛选。
- 后续如增加趋势图，趋势横轴也必须使用游戏时间。

## 5. 前端设计

### 5.1 文件范围

当前前端页面已存在：

```text
frontend/src/modules/shopee/views/ShopFlashSaleDataView.tsx
```

后续实现时仅在必要范围内修改：

```text
frontend/src/modules/shopee/
├── ShopeePage.tsx
├── components/Header.tsx
└── views/ShopFlashSaleDataView.tsx
```

若现有路由与面包屑已接好，不重复调整。

### 5.2 组件输入

保持现有 props：

```typescript
interface ShopFlashSaleDataViewProps {
  campaignId: number | null;
  readOnly?: boolean;
  onBackToFlashSale: () => void;
}
```

建议后续将 `onBackToFlashSale` 语义改名为 `onViewFlashSaleDetail`，但若改名会扩大修改范围，可保留函数名，仅将实际跳转目标改为详情页。

### 5.3 前端状态

页面状态建议：

```typescript
type OrderType = 'placed' | 'confirmed';

interface FlashSaleDataState {
  loading: boolean;
  rankingLoading: boolean;
  error: string | null;
  overview: FlashSaleDataOverview | null;
  ranking: FlashSaleProductRankingRow[];
  selectedOrderType: OrderType;
}
```

### 5.4 展示结构

保持现有官方风格布局：

1. 顶部绿色提示横幅。
2. 活动基础信息卡片。
3. 关键指标卡片。
4. 商品排名表格。

本期不强制新增趋势图。若后续补趋势图，应放在关键指标与商品排名之间，并单独增加趋势接口。

### 5.5 空状态

| 场景 | 展示 |
| --- | --- |
| 缺少 `campaign_id` | `缺少限时抢购活动 ID` |
| 活动不存在或无权限 | `未找到该限时抢购活动` |
| 无订单但有活动商品 | 指标为 0，商品排名仍展示活动商品，销售额/订单/件数为 0 |
| 无活动商品 | 商品排名区展示 `暂无商品表现数据` |

## 6. 后端接口设计

统一前缀沿用现有限时抢购接口：

```text
/shopee/runs/{run_id}/marketing/flash-sale
```

### 6.1 数据页概览

```http
GET /shopee/runs/{run_id}/marketing/flash-sale/campaigns/{campaign_id}/data
```

Query：

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `order_type` | string | `confirmed` | `placed` 或 `confirmed` |

Response：

```json
{
  "campaign": {
    "id": 2,
    "name": "限时抢购活动",
    "status": "ended",
    "status_label": "已结束",
    "edit_period_label": "16-03-2026 09:15 - 17-03-2026 00:00 (GMT+07)",
    "activity_period_label": "17-03-2026 00:00 - 17-03-2026 12:00 (GMT+07)",
    "item_count": 6
  },
  "order_type": "confirmed",
  "metrics": {
    "reminder_count": 0,
    "product_view_count": 5,
    "product_click_count": 0,
    "ctr": 0.0,
    "sales_amount": 2475.0,
    "order_count": 4,
    "unit_count": 4,
    "buyer_count": 4
  }
}
```

### 6.2 商品排名

```http
GET /shopee/runs/{run_id}/marketing/flash-sale/campaigns/{campaign_id}/data/products
```

Query：

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `order_type` | string | `confirmed` | `placed` 或 `confirmed` |
| `sort_by` | string | `sales_amount` | `sales_amount/order_count/unit_count` |
| `sort_order` | string | `desc` | `asc/desc` |

Response：

```json
{
  "items": [
    {
      "listing_id": 123,
      "item_id_label": "26860864366",
      "name": "厨房收纳置物架 多层碗碟沥水架",
      "image_url": "...",
      "sales_amount": 2475.0,
      "order_count": 4,
      "unit_count": 4,
      "variations": [
        {
          "campaign_item_id": 10,
          "variant_id": 456,
          "variation_name": "【44.5cm】白色 3层带接水盘",
          "activity_stock": 20,
          "flash_price": 692.0,
          "sales_amount": 1354.0,
          "order_count": 2,
          "unit_count": 2
        }
      ]
    }
  ]
}
```

### 6.3 导出数据

```http
GET /shopee/runs/{run_id}/marketing/flash-sale/campaigns/{campaign_id}/data/export
```

Query：

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `order_type` | string | `confirmed` | `placed` 或 `confirmed` |

Response：

- `Content-Type: text/csv; charset=utf-8`
- 文件名建议：`flash_sale_data_{campaign_id}_{order_type}.csv`

CSV 字段：

| 字段 | 说明 |
| --- | --- |
| `活动ID` | 限时抢购活动 ID |
| `活动名称` | 活动名称 |
| `订单类型` | 已下单/已确认订单 |
| `商品ID` | listing/item ID |
| `商品名称` | 商品名 |
| `变体ID` | variant ID |
| `变体名称` | 规格名 |
| `活动库存` | 活动库存上限 |
| `折后价` | 限时抢购价格 |
| `销售额` | 变体销售额 |
| `订单数` | 变体订单数 |
| `售出件数` | 变体售出件数 |

## 7. 数据模型设计

### 7.1 复用表

本期优先复用已有数据表：

| 表 | 用途 |
| --- | --- |
| `shopee_flash_sale_campaigns` | 活动基础信息、提醒设置数、点击数、销售额/订单数快照 |
| `shopee_flash_sale_campaign_items` | 活动商品、变体、活动库存、折后价、已售数量 |
| `shopee_orders` | 订单头、买家、订单状态、活动归因兜底 |
| `shopee_order_items` | 明细级营销归因、成交价、数量、商品/变体维度统计 |
| `shopee_listings` | 商品名称、主图、展示 ID |
| `shopee_listing_variants` | 变体名称、SKU、当前库存等展示字段 |

### 7.2 订单归因要求

订单模拟已接入限时抢购后，数据页统计依赖以下字段：

```text
shopee_order_items.marketing_campaign_type = 'flash_sale'
shopee_order_items.marketing_campaign_id = campaign_id
```

如果订单头也写入了同样归因，仍以明细级归因为准，避免同一订单内混入其他营销商品时统计失真。

### 7.3 可选事件表预留

如后续需要将商品浏览量、商品点击数从活动表计数升级为事件流水，可新增：

```text
shopee_flash_sale_traffic_events
```

字段建议：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | bigint pk | 事件 ID |
| `run_id` | bigint | 对局 ID |
| `user_id` | bigint | 用户 ID |
| `campaign_id` | bigint | 限时抢购活动 ID |
| `campaign_item_id` | bigint null | 活动商品 ID |
| `listing_id` | bigint null | 商品 ID |
| `variant_id` | bigint null | 变体 ID |
| `event_type` | varchar(32) | `view/click/reminder` |
| `buyer_code` | varchar(64) null | 买家标识，可为空 |
| `event_tick` | datetime | 事件发生游戏时间 |
| `created_at` | datetime | 创建时间 |

该表不作为 V1 必需项；若创建，必须补齐 table comment 与 column comment。

## 8. Redis 设计

### 8.1 Key 设计

| 场景 | Key | TTL |
| --- | --- | --- |
| 数据页概览 | `shopee:flash_sale:data:{run_id}:{user_id}:{campaign_id}:{order_type}` | 30 秒 |
| 商品排名 | `shopee:flash_sale:data_products:{run_id}:{user_id}:{campaign_id}:{order_type}:{sort_by}:{sort_order}` | 30 秒 |
| 导出限流 | `rate:shopee:flash_sale:data_export:{user_id}` | 60 秒窗口 |

Key 中必须包含 `run_id/user_id/campaign_id/order_type`，避免不同对局、用户、活动或订单口径串数。

### 8.2 失效规则

以下动作发生后，应失效限时抢购数据页缓存：

- 创建限时抢购活动。
- 启用/停用限时抢购活动。
- 订单模拟生成命中 `flash_sale` 的订单。
- 取消命中 `flash_sale` 的订单。
- 物流或订单状态变化会影响 `confirmed` 口径时。
- 后续新增浏览/点击/提醒事件写入时。

建议复用现有限时抢购缓存失效函数，并增加数据页前缀：

```text
shopee:flash_sale:data:{run_id}:{user_id}:
shopee:flash_sale:data_products:{run_id}:{user_id}:
```

### 8.3 降级策略

- Redis 不可用时接口直接查数据库并返回，不阻断页面。
- 写缓存失败只记录日志，不影响响应。
- 导出限流 Redis 不可用时可降级为放行，但应记录 warning。

## 9. 验收标准

### 9.1 前端验收

- 访问 `/shopee/marketing/flash-sale/data?campaign_id=2` 可加载真实活动基础信息。
- 关键指标不再使用写死模拟数据。
- 商品排名按活动商品展示，未售出变体也能展示库存和折后价。
- 切换订单类型会刷新指标与商品排名。
- 点击“查看活动详情”进入对应详情页。
- 历史回溯只读模式下导出按钮禁用。

### 9.2 后端验收

- 非当前用户或非当前对局活动返回 404 或权限错误，不泄露数据。
- 销售额、订单数、售出件数按 `shopee_order_items` 明细级限时抢购归因统计。
- 已取消订单不计入销售额和订单数。
- 无订单活动返回 0 指标，但商品排名仍展示活动商品。
- 商品排行默认按销售额降序稳定排序。

### 9.3 Redis 验收

- 首次访问写入概览与商品排名缓存。
- 短时间重复访问命中缓存。
- 订单模拟生成限时抢购订单后，数据页缓存被失效，刷新可看到新订单指标。
- 导出接口具备用户级限流。

### 9.4 文档与维护验收

- 若实现时新增数据库表或字段，必须同步补齐表注释与字段注释。
- 实现完成后必须更新 `docs/当前进度.md`。
- 实现完成后必须更新 `docs/change-log.md`，写明涉及文件、统计口径与影响范围。

## 10. 后续扩展

- 增加趋势图接口，按游戏日或游戏小时展示销售额、订单数、点击数、CTR。
- 增加真实浏览/点击/提醒事件流水表，替代活动表计数快照。
- 增加 CSV 导出任务表，支持大数据量异步导出。
- 增加活动数据与订单明细页联动，从商品排名点击查看命中订单。
- 增加与普通单品折扣、套餐优惠、加价购数据页一致的报表组件复用。
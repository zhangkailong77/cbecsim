# 45-Shopee 代金券订单页面前后端数据库 Redis 实现设计

## 目标

在不改变现有 `VoucherOrdersView` 页面视觉布局的前提下，将代金券列表“订单”入口接入真实数据，形成前端页面、后端接口、数据库订单归因与 Redis 缓存闭环。页面内订单创建时间、代金券有效期等时间展示统一使用游戏时间，不展示真实世界时间。

## 流程

1. 用户在 Shopee 营销中心代金券列表点击“订单”。
2. 前端进入 `/shopee/marketing/vouchers/orders?voucher_type=...&campaign_id=...`，隐藏左侧菜单栏并保留 1360px 内容区。
3. `ShopeePage` 将 `runId`、`voucherType`、`campaignId` 传给 `VoucherOrdersView`。
4. `VoucherOrdersView` 请求后端代金券订单接口，填充基本信息、订单总数、订单列表和分页。
5. 后端从代金券活动表读取活动基础信息，从 `shopee_orders` / `shopee_order_items` 读取已使用该代金券的订单。
6. 后端将结果写入 Redis，订单或代金券变更时通过既有失效链路清理缓存。

## 规则

- 前端只替换 mock 数据来源，不改变页面卡片、表格、分页、折叠区的样式结构。
- 订单过滤条件以订单表已落库的 `voucher_campaign_type`、`voucher_campaign_id` 为准。
- 页面所有时间字段必须由后端按游戏时间格式化后返回：
  - 代金券使用期限使用 `_format_shop_voucher_period` 或 `_format_follow_voucher_period`。
  - 订单创建时间使用 `_format_discount_game_datetime(order.created_at, run=run)`。
- 订单金额沿用订单持久化结果：
  - 折扣金额：`voucher_discount_amount`。
  - 订单总金额：`buyer_payment`。
- 不新增本地前端状态作为真实来源，所有经营结果以数据库为准。

## 数据模型

本功能复用既有表，不新增数据库表：

- `shopee_orders`
  - `voucher_campaign_type`：代金券类型。
  - `voucher_campaign_id`：代金券活动 ID。
  - `voucher_name_snapshot`：下单时活动名称快照。
  - `voucher_code_snapshot`：下单时代金券代码快照。
  - `voucher_discount_amount`：订单使用代金券抵扣金额。
  - `order_subtotal_amount`：订单抵扣前商品小计。
- `shopee_order_items`
  - 提供订单商品图片和商品名。
- 代金券活动表
  - `shopee_shop_voucher_campaigns`
  - `shopee_product_voucher_campaigns`
  - `shopee_private_voucher_campaigns`
  - `shopee_live_voucher_campaigns`
  - `shopee_video_voucher_campaigns`
  - `shopee_follow_voucher_campaigns`

## 接口

### GET `/shopee/runs/{run_id}/marketing/vouchers/{voucher_type}/{campaign_id}/orders`

查询参数：

- `page`：页码，默认 1。
- `page_size`：每页数量，默认 10。

响应摘要：

```json
{
  "voucher": {
    "status_label": "已过期",
    "voucher_name": "400",
    "reward_type_label": "折扣",
    "min_spend_text": "RM500",
    "discount_text": "RM400",
    "period": "18/10/2025 08:58 - 19/10/2025 08:58",
    "voucher_code": "HOMEA4FTA",
    "voucher_type_label": "专属代金券",
    "applicable_scope_label": "1 件商品",
    "display_setting_label": "不展示",
    "usage_limit": 1,
    "claimed_count": 1,
    "used_count": 1
  },
  "page": 1,
  "page_size": 10,
  "total": 326,
  "orders": [
    {
      "id": 1,
      "order_no": "251023T92P5KC0",
      "products": [{ "image_url": "...", "product_name": "..." }],
      "discount_amount": 212,
      "total_amount": 588,
      "created_at_text": "2025-10-23",
      "status_label": "已完成"
    }
  ]
}
```

## Redis

- 缓存 Key 前缀：`{REDIS_PREFIX}:cache:shopee:voucher:orders:{run_id}:{user_id}:`
- 缓存维度：`voucher_type`、`campaign_id`、`page`、`page_size`。
- TTL：复用订单列表缓存 TTL。
- 失效：订单列表缓存失效时同步清理代金券订单缓存，保证新订单、取消、履约状态变化后页面可刷新到最新数据。

## 验收标准

- 点击任意代金券“订单”后进入无左侧菜单栏的 1360px 页面。
- 页面视觉布局与当前 `VoucherOrdersView` 保持一致。
- 基本信息、折叠信息、订单总数、表格和分页来自后端接口。
- 订单创建时间与代金券时间均为游戏时间口径。
- 后端接口支持 Redis 缓存，并在订单缓存失效链路中清理。
- TypeScript 与 Python 语法检查通过。

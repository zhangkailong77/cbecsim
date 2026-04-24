# 25 - Shopee 单品折扣活动详情页设计

> 最后更新：2026-04-24

## 1. 目标

为营销中心 > 折扣 > 活动列表中**已结束**（以及所有状态）的单品折扣活动提供"详情"页面，展示活动基础信息、参与商品与折扣规则、活动期间表现数据、归因订单列表，方便玩家复盘折扣效果。

## 2. 页面结构与布局

页面以独立视图 `DiscountDetailView` 承载，路由为：
```
/shopee/marketing/discount/detail?campaign_id={id}
```

从活动列表点击"详情"按钮时，前端 `handleActionClick` 识别 `action === '详情'`，携带 `campaign_id` 跳转。

### 2.0 内容区宽度

详情页中间内容区域宽度与单品折扣创建页（`DiscountCreateView`）保持一致：

```
外层容器：mx-auto max-w-[1360px]
```

进入详情页时隐藏左侧菜单栏，与创建页行为一致，留出完整内容宽度。

### 2.1 页面区块

```
┌──────────────────────────────────────────────────────────┐
│  面包屑：营销中心 > 折扣 > 活动详情                         │
│  [返回活动列表]                                           │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─ 活动基础信息卡片 ─────────────────────────────────┐  │
│  │ 活动名称：Summer Sale 2027                          │  │
│  │ 活动类型：单品折扣        活动状态：已结束            │  │
│  │ 活动时间：2027/01/15 08:00 - 2027/01/22 08:00      │  │
│  │ 创建时间：2027/01/14 10:30                          │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌─ 活动表现总览（4 张指标卡）─────────────────────────┐  │
│  │ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐│  │
│  │ │ 销售额   │ │ 订单数   │ │ 售出件数  │ │ 买家数   ││  │
│  │ │ RM 1,250 │ │    15    │ │    32    │ │    12    ││  │
│  │ └──────────┘ └──────────┘ └──────────┘ └──────────┘│  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌─ Tab 切换 ────────────────────────────────────────┐   │
│  │ [参与商品]  [表现趋势]  [归因订单]                   │  │
│  ├───────────────────────────────────────────────────┤   │
│  │                                                   │   │
│  │  （根据选中 Tab 展示下方内容区）                     │   │
│  │                                                   │   │
│  └───────────────────────────────────────────────────┘   │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### 2.2 各区块详细设计

#### A. 活动基础信息卡片

| 字段 | 数据来源 | 说明 |
|------|----------|------|
| 活动名称 | `campaign_name` | 原样展示 |
| 活动类型 | `campaign_type` | 中文映射：discount→单品折扣、bundle→套餐优惠、add_on→加价购 |
| 活动状态 | 运行时计算 | 与活动列表一致的状态判定逻辑（draft/upcoming/ongoing/ended/disabled），中文标签展示 |
| 活动时间 | `start_at` - `end_at` | 格式 `YYYY/MM/DD HH:mm - YYYY/MM/DD HH:mm` |
| 创建时间 | `created_at` | 格式 `YYYY/MM/DD HH:mm` |

#### B. 活动表现总览（4 张指标卡）

从 `shopee_discount_performance_daily` 按 `campaign_id` 聚合：

| 指标 | 聚合方式 | 单位 |
|------|----------|------|
| 销售额 | `SUM(sales_amount)` | RM，保留 2 位小数，千分位 |
| 订单数 | `SUM(orders_count)` | 整数 |
| 售出件数 | `SUM(units_sold)` | 整数 |
| 买家数 | `SUM(buyers_count)` | 整数（注意：跨天重复买家为近似值，取 SUM） |

> 若 `shopee_discount_performance_daily` 无数据（活动从未产生订单），4 张卡均显示 `0 / RM 0.00`。

#### C. Tab 区 - 参与商品

展示该活动关联的所有商品明细，来源于 `shopee_discount_campaign_items`：

| 列名 | 字段 | 说明 |
|------|------|------|
| 商品图片 | `image_url_snapshot` | 缩略图 50×50，缺失时占位图 |
| 商品名称 | `product_name_snapshot` | 文本截断展示 |
| SKU | `sku_snapshot` | 缺失时显示 `-` |
| 原价 | `original_price` | RM 格式 |
| 折扣方式 | `discount_type` | percent→"百分比折扣"，fixed→"固定价格" |
| 折扣值 | `discount_value` | percent 时显示 `X%`，fixed 时显示 `RM X` |
| 折后价 | `final_price` | RM 格式，粗体强调 |

支持分页（默认 `page_size=10`），无需筛选。

#### D. Tab 区 - 表现趋势

按 `shopee_discount_performance_daily` 的 `stat_date` 排序，展示每日趋势表格：

| 列名 | 字段 |
|------|------|
| 日期 | `stat_date`（YYYY/MM/DD） |
| 销售额 | `sales_amount` |
| 订单数 | `orders_count` |
| 售出件数 | `units_sold` |
| 买家数 | `buyers_count` |

支持分页（默认 `page_size=10`）。

> 后续可扩展为折线图可视化，MVP 阶段先用表格。

#### E. Tab 区 - 归因订单

按 `shopee_orders` 中 `marketing_campaign_id = campaign_id` 筛选：

| 列名 | 字段 | 说明 |
|------|------|------|
| 订单号 | `order_sn` | 可点击跳转订单详情 |
| 买家 | `buyer_nickname` | - |
| 商品 | 订单明细中商品名 | 多商品时换行展示 |
| 实付金额 | `total_amount` | RM 格式 |
| 折扣比例 | `discount_percent` | 如 `15%`，无折扣时显示 `-` |
| 订单状态 | 运行时计算 | 中文映射：toship→待出货、shipping→运输中、completed→已完成、cancelled→已取消 |
| 下单时间 | `created_at` | YYYY/MM/DD HH:mm |

支持分页（默认 `page_size=10`），支持按订单状态筛选。

## 3. 前端设计

### 3.1 文件结构

```
frontend/src/modules/shopee/
├── views/
│   └── DiscountDetailView.tsx     ← 新增，活动详情页
└── ShopeePage.tsx                 ← 修改，新增路由解析
```

### 3.2 路由接入

在 `ShopeePage.tsx` 的视图解析中新增：

```typescript
// 现有 ShopeeView 类型追加
type ShopeeView =
  | ... // 现有视图
  | 'marketing-discount-detail';  // 新增

// URL -> 视图映射
const viewFromPath = (path: string): ShopeeView | null => {
  // ...
  if (path.startsWith('/shopee/marketing/discount/detail')) {
    return 'marketing-discount-detail';
  }
  // ...
};
```

### 3.3 DiscountDetailView 职责

1. 从 URL query 读取 `campaign_id`
2. 调用 `GET /shopee/runs/{run_id}/marketing/discount/campaigns/{campaign_id}/detail`
3. 渲染：面包屑 + 返回按钮 + 基础信息卡 + 指标卡 + Tab 区
4. Tab 切换仅前端切换，详情接口一次返回所有 Tab 数据（参与商品 + 表现趋势 + 归因订单各自带分页信息）
5. 分页切换调用独立子接口（见下文）
6. 只读模式（历史对局）：隐藏编辑/复制等操作按钮，仅展示

### 3.4 活动列表 handleActionClick 修改

将现有 `window.alert('详情 功能页将在下一阶段继续接入。')` 替换为：

```typescript
if (action === '详情') {
  window.history.pushState(null, '', `/shopee/marketing/discount/detail?campaign_id=${row.campaign_id}`);
  window.dispatchEvent(new PopStateEvent('popstate'));
  return;
}
```

## 4. 后端接口设计

### 4.1 详情主接口

```
GET /shopee/runs/{run_id}/marketing/discount/campaigns/{campaign_id}/detail
```

**权限**：同现有折扣页，验证 `run_id` 归属当前用户。

**返回结构**：

```python
class ShopeeDiscountDetailResponse(BaseModel):
    # 基础信息
    campaign_id: int
    campaign_name: str
    campaign_type: str           # discount / bundle / add_on
    campaign_type_label: str     # "单品折扣" 等
    status: str                  # draft / upcoming / ongoing / ended / disabled
    status_label: str            # "已结束" 等
    start_at: str | None         # "2027/01/15 08:00"
    end_at: str | None
    created_at: str
    market: str
    currency: str

    # 表现总览
    performance: ShopeeDiscountDetailPerformance

    # 参与商品（首页）
    items: ShopeeDiscountDetailItemList

    # 表现趋势（首页）
    daily_performance: ShopeeDiscountDetailDailyList

    # 归因订单（首页）
    orders: ShopeeDiscountDetailOrderList


class ShopeeDiscountDetailPerformance(BaseModel):
    total_sales_amount: float    # SUM(sales_amount)
    total_orders_count: int      # SUM(orders_count)
    total_units_sold: int        # SUM(units_sold)
    total_buyers_count: int      # SUM(buyers_count)


class ShopeeDiscountDetailItemList(BaseModel):
    rows: list[ShopeeDiscountDetailItemRow]
    pagination: PaginationMeta


class ShopeeDiscountDetailItemRow(BaseModel):
    item_id: int
    product_name: str
    image_url: str | None
    sku: str | None
    original_price: float
    discount_type: str           # percent / fixed
    discount_type_label: str     # "百分比折扣" / "固定价格"
    discount_value: float
    final_price: float | None


class ShopeeDiscountDetailDailyList(BaseModel):
    rows: list[ShopeeDiscountDetailDailyRow]
    pagination: PaginationMeta


class ShopeeDiscountDetailDailyRow(BaseModel):
    stat_date: str               # "2027/01/15"
    sales_amount: float
    orders_count: int
    units_sold: int
    buyers_count: int


class ShopeeDiscountDetailOrderList(BaseModel):
    rows: list[ShopeeDiscountDetailOrderRow]
    pagination: PaginationMeta


class ShopeeDiscountDetailOrderRow(BaseModel):
    order_id: int
    order_sn: str
    buyer_nickname: str
    product_summary: str         # 商品名拼接，多商品逗号分隔
    total_amount: float
    discount_percent: float | None
    order_status: str            # toship / shipping / completed / cancelled
    order_status_label: str      # "待出货" 等
    created_at: str              # "2027/01/15 10:30"


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int
```

**实现要点**：

1. **基础信息**：查询 `ShopeeDiscountCampaign`，用 `_resolve_discount_campaign_status()` 计算实时状态
2. **表现总览**：对 `ShopeeDiscountPerformanceDaily` 执行 `func.sum()` 聚合
3. **参与商品**：查询 `ShopeeDiscountCampaignItem`，按 `sort_order` 排序，默认第 1 页
4. **表现趋势**：查询 `ShopeeDiscountPerformanceDaily`，按 `stat_date` 排序，默认第 1 页
5. **归因订单**：查询 `ShopeeOrder`，`filter(marketing_campaign_id == campaign_id)`，按 `created_at DESC`，默认第 1 页

### 4.2 Tab 分页子接口

参与商品、表现趋势、归因订单的 Tab 翻页由独立接口承载，避免主接口重复加载全量数据：

```
GET /shopee/runs/{run_id}/marketing/discount/campaigns/{campaign_id}/items?page=1&page_size=10
GET /shopee/runs/{run_id}/marketing/discount/campaigns/{campaign_id}/daily?page=1&page_size=10
GET /shopee/runs/{run_id}/marketing/discount/campaigns/{campaign_id}/orders?page=1&page_size=10&status=
```

各接口返回对应的 `rows + pagination` 结构（复用主接口中的 Row 和 PaginationMeta 模型）。

归因订单子接口支持可选 `status` 筛选参数。

## 5. 数据库设计

**无需新增表或字段**。详情页数据完全由现有表提供：

| 表 | 用途 |
|----|------|
| `shopee_discount_campaigns` | 活动基础信息 |
| `shopee_discount_campaign_items` | 参与商品与折扣规则 |
| `shopee_discount_performance_daily` | 每日表现趋势 |
| `shopee_orders` | 归因订单（通过 `marketing_campaign_id` 关联） |

### 5.1 建议补充索引

归因订单查询依赖 `marketing_campaign_id` 筛选，现有模型已在该字段上建立 `index=True`，无需额外补充。

## 6. Redis 缓存设计

### 6.1 缓存键

| 键模式 | TTL (秒) | 用途 |
|--------|----------|------|
| `{prefix}:cache:shopee:discount:detail:{run_id}:{user_id}:{campaign_id}` | 30 | 详情主接口缓存 |
| `{prefix}:cache:shopee:discount:detail-items:{run_id}:{user_id}:{campaign_id}:{page}:{page_size}` | 30 | 参与商品 Tab 分页缓存 |
| `{prefix}:cache:shopee:discount:detail-daily:{run_id}:{user_id}:{campaign_id}:{page}:{page_size}` | 30 | 表现趋势 Tab 分页缓存 |
| `{prefix}:cache:shopee:discount:detail-orders:{run_id}:{user_id}:{campaign_id}:{page}:{page_size}:{status}` | 30 | 归因订单 Tab 分页缓存 |

### 6.2 缓存失效

详情页数据为只读查询，缓存失效策略：

- **自然过期**：30 秒 TTL 自动过期
- **主动失效**：活动创建/编辑/状态变更时，按 `campaign_id` 清除该活动所有详情相关缓存键（使用 `cache_delete_prefix` 按 `detail:*:{campaign_id}` 前缀批量清除）

### 6.3 限流

| 端点 | 每分钟限制 | 说明 |
|------|-----------|------|
| 详情主接口 | 60 次 | 同 bootstrap 级别 |
| Tab 分页子接口 | 120 次 | 同活动列表级别 |

## 7. 历史对局只读模式

- 详情页在历史回溯模式下**允许进入**，展示该活动的历史快照数据
- 隐藏编辑/复制/分享等写操作入口
- 面包屑与返回按钮正常可用

## 8. 验收标准

| # | 验收项 | 验证方式 |
|---|--------|----------|
| 1 | 点击已结束活动"详情"按钮可跳转详情页 | 前端手动验证 |
| 2 | 详情页正确展示活动名称/类型/状态/时间/创建时间 | 对比数据库 |
| 3 | 4 张指标卡正确聚合销售额/订单数/件数/买家数 | 对比 `performance_daily` 聚合 |
| 4 | 参与商品 Tab 展示所有折扣商品及折扣规则 | 对比 `campaign_items` |
| 5 | 表现趋势 Tab 按日展示每日数据 | 对比 `performance_daily` |
| 6 | 归因订单 Tab 展示所有 `marketing_campaign_id` 匹配的订单 | 对比 `shopee_orders` |
| 7 | 三个 Tab 各自可翻页，分页参数正确 | 手动翻页验证 |
| 8 | 归因订单支持按状态筛选 | 选择不同状态验证 |
| 9 | 面包屑可返回折扣活动列表 | 点击面包屑验证 |
| 10 | 历史对局可进入详情页，不暴露写操作 | 历史局手动验证 |
| 11 | Redis 缓存命中与失效符合预期 | 查看缓存键与 TTL |
| 12 | 各状态（草稿/即将开始/进行中/已结束/已停用）的活动均可进入详情 | 逐一验证 |

## 9. 与现有设计的衔接

| 现有设计文档 | 衔接点 |
|-------------|--------|
| 19-折扣页复刻设计 | 活动列表页 → 详情页跳转入口 |
| 20-单品折扣创建页设计 | 创建成功后可从列表进入详情 |
| 23-单品折扣生效与订单影响设计 | 归因订单数据来源于订单模拟器的 `marketing_campaign_id` 写入 |
| 24-折扣对下单概率的影响设计 | 详情页指标展示验证了概率设计的实际效果 |

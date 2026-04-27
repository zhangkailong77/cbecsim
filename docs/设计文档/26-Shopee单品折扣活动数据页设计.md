# 26 - Shopee 单品折扣活动数据页设计

> 最后更新：2026-04-24

## 1. 目标

为 `营销中心 > 折扣 > 单品折扣 > 活动列表` 中点击“数据 / 查看数据”后的页面新增设计方案，复刻 Shopee 官方 `Promotion Data / Discount Data` 页面。

页面用于展示某个折扣活动在统计周期内的经营表现，包括关键指标、趋势图、商品排行与可导出数据，帮助玩家判断单品折扣活动是否带来销售额、订单数、销量与买家增长。

本设计只覆盖方案，不直接进入代码实现。

## 2. 范围与非范围

### 2.1 本期范围

- 新增单品折扣活动数据页路由：
  ```
  /u/{public_id}/shopee/marketing/discount/data?campaign_id={id}
  ```
- 从活动列表点击“数据 / 查看数据”进入该页。
- 复刻官方截图中的核心区域：
  - 顶部面包屑与页面标题 `折扣数据`
  - 店铺/站点选择器
  - 官方提示横幅
  - 活动标题与活动基础信息
  - 数据维度切换：`销量 / 买家 / 订单 / 售出件数 / 销售额`
  - 时间筛选：`订单时间 / 已完成订单`
  - 导出数据按钮
  - 关键指标卡片
  - 每日趋势折线图
  - 商品排行表格
- 后端提供活动数据聚合接口、趋势接口、商品排行接口与导出接口。
- 数据库复用现有折扣、订单与表现统计表，必要时补充轻量导出任务表。
- Redis 提供活动数据页缓存、图表缓存、排行缓存、导出限流与缓存失效策略。

### 2.2 非范围

- 不接入真实 Shopee 商家后台 API。
- 不实现曝光、点击、加购等当前订单模拟器无法真实产出的流量指标。
- 不实现复杂 BI 多维下钻，仅覆盖活动级总览、每日趋势、商品排行。
- 不新增与折扣业务无关的通用报表平台。

## 3. 页面结构与布局

页面以独立视图 `DiscountDataView` 承载。整体仍放在 Shopee 工作台内容区内，进入数据页时建议隐藏左侧菜单栏，与创建页、详情页保持一致，给图表和表格留出完整宽度。

### 3.1 路由

内部视图识别路径：

```
/shopee/marketing/discount/data?campaign_id={id}
```

实际浏览器路径：

```
/u/{public_id}/shopee/marketing/discount/data?campaign_id={id}
```

### 3.2 页面线框

```
┌────────────────────────────────────────────────────────────────────┐
│ Home > Marketing Centre > Discount > Data Details                  │
│                                                                    │
│ [当前店铺/站点选择器]                                                │
│ ┌────────────────────────────────────────────────────────────────┐ │
│ │ Congratulations! You have already gained free vouchers ...      │ │
│ │                                                [View Details >] │ │
│ └────────────────────────────────────────────────────────────────┘ │
│                                                                    │
│ 6.30新品折扣       Promotion Details >                             │
│ 活动时间：2026/09/09 00:00 - 2026/09/13 23:59                     │
│                                                                    │
│ [销量] [买家] [订单] [售出件数] [销售额]       [订单时间 v] [导出]  │
│                                                                    │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│ │ 销售额   │ │ 售出件数  │ │ 订单数   │ │ 买家数   │ │ 售出商品数│ │
│ │ RM...    │ │ ...       │ │ ...      │ │ ...      │ │ ...      │ │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
│                                                                    │
│ Trend Chart of Each Metric                                         │
│ ┌────────────────────────────────────────────────────────────────┐ │
│ │ 折线图：Sales / Units Sold / Orders / Buyers / Items Sold       │ │
│ │ 横轴日期，纵轴随当前指标切换，支持 hover tooltip                 │ │
│ └────────────────────────────────────────────────────────────────┘ │
│                                                                    │
│ Product Ranking                                                    │
│ ┌────────────────────────────────────────────────────────────────┐ │
│ │ Ranking | Product | Variation | Original Price | Discount ...   │ │
│ │    1    | 商品图 + 商品名 | 规格 | RM... | ... | ...            │ │
│ └────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

### 3.3 视觉复刻要点

- 页面背景使用浅灰，主体卡片使用白底。
- 顶部面包屑保持小字号灰色，末级为当前页。
- 横幅使用浅绿色/浅青色背景，左侧插画/图标，右侧绿色按钮。
- 活动标题区域紧凑展示：标题、`Promotion Details >` 链接、活动时间。
- 指标卡 5 列横排，卡片边框浅灰，数值加粗。
- 当前选中指标卡使用橙色顶边或橙色强调，贴近官方截图中的 Shopee 主色。
- 折线图区域白底，主线蓝色，选中/对比线可使用橙色、红色、灰色虚线。
- 商品排行表格列密集但字号偏小，商品列包含缩略图、商品名与商品 ID/规格信息。

### 3.4 内容区域宽度

数据页内容区延续现有创建页/详情页宽度节奏，外层容器使用：

```tsx
<div className="mx-auto max-w-[1360px] pb-10">
  {/* 数据页主体内容 */}
</div>
```

实现要求：

| 区域 | 宽度规则 | 说明 |
|------|----------|------|
| 页面主容器 | `mx-auto max-w-[1360px] pb-10` | 与单品折扣创建页、活动详情页保持同一内容宽度 |
| 顶部横幅 | 撑满主容器宽度 | 不额外设置更窄宽度 |
| 活动信息区 | 撑满主容器宽度 | 标题、详情链接、活动时间保持一行优先 |
| 指标卡区 | 5 列等宽 | 容器宽度不足时允许横向压缩，不换成多行卡片 |
| 趋势图区 | 撑满主容器宽度 | 图表高度建议 260-300px |
| 商品排行表 | 撑满主容器宽度 | 表格使用小字号和紧凑行高，避免横向滚动过早出现 |

### 3.5 字号与间距规范

为贴近官方 Shopee 后台数据页，整体采用偏小、信息密度高的后台字号体系，不使用大标题式营销页面字号。

| 元素 | Tailwind 建议 | 说明 |
|------|---------------|------|
| 面包屑 | `text-[12px] text-gray-500` | 官方截图顶部导航字号很小 |
| 页面/活动标题 | `text-[18px] font-semibold text-gray-900` | 只在活动标题处轻微强调 |
| 活动时间/辅助说明 | `text-[12px] text-gray-500` | 与官方灰色说明一致 |
| 顶部横幅主文案 | `text-[13px] font-medium` | 横幅文字不做大号展示 |
| 顶部横幅副文案 | `text-[12px] text-gray-500` | 作为补充说明 |
| 筛选/按钮文字 | `text-[12px]` | 与 Shopee 后台控件密度一致 |
| 指标卡标题 | `text-[12px] text-gray-500` | 如 Sales、Units Sold、Orders |
| 指标卡数值 | `text-[18px] font-semibold text-gray-900` | 比标题大，但不超过详情页主指标层级 |
| 图表标题 | `text-[13px] font-medium text-gray-700` | 保持轻量标题 |
| 图表坐标轴/Tooltip | `text-[11px]` / `text-[12px]` | 坐标轴更小，tooltip 可读即可 |
| 表格表头 | `text-[12px] font-medium text-gray-500` | 官方表格表头偏浅 |
| 表格正文 | `text-[12px] text-gray-700` | 商品名可加深，其他列保持轻量 |
| 商品名 | `text-[12px] font-medium text-gray-800` | 最多两行截断 |
| 商品 ID / 规格 | `text-[11px] text-gray-500` | 商品补充信息弱化 |

间距建议：

| 元素 | Tailwind 建议 | 说明 |
|------|---------------|------|
| 主容器底部 | `pb-10` | 沿用既有页面写法 |
| 页面区块间距 | `space-y-4` 或 `mt-4` | 官方截图区块间距较紧凑 |
| 白色卡片内边距 | `p-4` | 指标卡可用 `p-3` |
| 指标卡间距 | `gap-3` | 5 列卡片保持紧凑 |
| 表格行高 | `py-2.5` | 商品排行行不要过高 |
| 商品缩略图 | `h-12 w-12` | 贴近官方排行表商品图尺寸 |

## 4. 前端设计

### 4.1 文件结构

```
frontend/src/modules/shopee/
├── ShopeePage.tsx                         ← 新增视图路由解析
├── components/
│   ├── Header.tsx                         ← ShopeeView 类型补充
│   └── Sidebar.tsx                        ← ShopeeView 类型补充
└── views/
    ├── MarketingDiscountView.tsx          ← 活动列表“数据”按钮跳转
    └── DiscountDataView.tsx               ← 新增活动数据页
```

### 4.2 ShopeeView 扩展

新增视图类型：

```typescript
type ShopeeView =
  | ...
  | 'marketing-discount-data';
```

路径识别：

```typescript
if (/\/shopee\/marketing\/discount\/data\/?$/.test(path)) {
  return 'marketing-discount-data';
}
```

侧栏隐藏集合加入 `marketing-discount-data`，保持与 `marketing-discount-detail`、创建页一致。

### 4.3 活动列表入口

`MarketingDiscountView` 中操作列新增或复用“数据”按钮。点击后携带 `row.id` 跳转：

```typescript
window.history.pushState(
  null,
  '',
  `/u/${encodeURIComponent(publicId)}/shopee/marketing/discount/data?campaign_id=${row.id}`,
);
window.dispatchEvent(new PopStateEvent('popstate'));
```

按钮展示建议：

| 活动状态 | 操作列 |
|----------|--------|
| 进行中 | 编辑 / 数据 / 详情 |
| 已结束 | 数据 / 详情 / 复制 |
| 即将开始 | 编辑 / 详情 |
| 草稿 | 编辑 / 删除 |

> 若当前列表已有“详情”，数据页入口应与详情页区分：详情页看规则与归因订单，数据页看经营表现与趋势。

### 4.4 `DiscountDataView` 职责

1. 从 URL query 读取 `campaign_id`。
2. 请求 `GET /shopee/runs/{run_id}/marketing/discount/campaigns/{campaign_id}/data` 获取首屏数据。
3. 渲染页面头部、提示横幅、活动基础信息、指标卡、趋势图与商品排行首屏。
4. 切换指标卡时优先使用主接口返回的趋势数据；若选择未加载的维度，调用趋势子接口。
5. 商品排行翻页/排序时调用商品排行子接口。
6. 点击 `Promotion Details >` 跳转到 `marketing-discount-detail`。
7. 点击 `Export Data` 调用导出接口，生成 CSV/XLSX 下载任务。
8. 历史回溯模式下允许查看数据与导出；禁止任何会修改活动状态的操作。

### 4.5 前端状态

| 状态 | 说明 |
|------|------|
| `activeMetric` | 当前选中的指标：`sales_amount / units_sold / orders_count / buyers_count / items_sold` |
| `timeBasis` | 时间口径：`order_time / completed_time` |
| `dateRange` | 默认活动周期；允许后续扩展手动日期筛选 |
| `rankingPage` | 商品排行分页页码 |
| `rankingSort` | 商品排行排序字段，默认按销售额降序 |
| `exporting` | 导出按钮 loading 状态 |

### 4.6 趋势图实现建议

- 优先复用当前前端已有图表依赖；若项目无图表库，可用 SVG/Canvas 轻量实现折线图。
- MVP 中只显示一条主指标线，不做复杂多指标叠加。
- tooltip 展示：日期、指标名称、指标值。
- 空数据时显示空状态：`该活动暂无订单数据`。

## 5. 后端接口设计

### 5.1 数据页主接口

```
GET /shopee/runs/{run_id}/marketing/discount/campaigns/{campaign_id}/data?time_basis=order_time
```

**权限**：同现有折扣页，验证 `run_id` 归属当前用户。

**返回结构**：

```python
class ShopeeDiscountDataResponse(BaseModel):
    campaign_id: int
    campaign_name: str
    campaign_type: str
    campaign_type_label: str
    status: str
    status_label: str
    start_at: str | None
    end_at: str | None
    market: str
    currency: str
    time_basis: str                    # order_time / completed_time
    metric_cards: ShopeeDiscountMetricCards
    trend: ShopeeDiscountTrendSeries
    product_ranking: ShopeeDiscountProductRankingList
    export_enabled: bool


class ShopeeDiscountMetricCards(BaseModel):
    sales_amount: float                # 销售额
    units_sold: int                    # 售出件数
    orders_count: int                  # 订单数
    buyers_count: int                  # 买家数
    items_sold: int                    # 售出商品数，按去重商品数或活动商品成交数口径


class ShopeeDiscountTrendPoint(BaseModel):
    stat_date: str                     # YYYY/MM/DD
    sales_amount: float
    units_sold: int
    orders_count: int
    buyers_count: int
    items_sold: int


class ShopeeDiscountTrendSeries(BaseModel):
    rows: list[ShopeeDiscountTrendPoint]


class ShopeeDiscountProductRankingList(BaseModel):
    rows: list[ShopeeDiscountProductRankingRow]
    pagination: PaginationMeta


class ShopeeDiscountProductRankingRow(BaseModel):
    rank: int
    campaign_item_id: int
    product_id: int | None
    product_name: str
    image_url: str | None
    variation_name: str | None
    original_price: float
    discount_label: str                # 例如 15% OFF / RM 9.90
    discounted_price: float | None
    units_sold: int
    buyers_count: int
    sales_amount: float
```

### 5.2 趋势子接口

```
GET /shopee/runs/{run_id}/marketing/discount/campaigns/{campaign_id}/data/trend?metric=sales_amount&time_basis=order_time
```

用于后续扩展多指标懒加载。MVP 主接口可直接返回所有指标趋势，子接口作为页面刷新与指标切换兜底。

### 5.3 商品排行子接口

```
GET /shopee/runs/{run_id}/marketing/discount/campaigns/{campaign_id}/data/ranking?page=1&page_size=10&sort=sales_amount&order=desc&time_basis=order_time
```

支持排序字段：

| 参数 | 含义 |
|------|------|
| `sales_amount` | 销售额 |
| `units_sold` | 售出件数 |
| `buyers_count` | 买家数 |
| `discounted_price` | 折后价 |

### 5.4 导出接口

```
POST /shopee/runs/{run_id}/marketing/discount/campaigns/{campaign_id}/data/export
```

请求体：

```python
class ShopeeDiscountDataExportRequest(BaseModel):
    time_basis: Literal['order_time', 'completed_time'] = 'order_time'
    export_type: Literal['csv', 'xlsx'] = 'csv'
```

响应：

```python
class ShopeeDiscountDataExportResponse(BaseModel):
    export_id: str
    status: str                       # ready / processing
    download_url: str | None
    expires_at: str | None
```

MVP 可同步生成 CSV 并通过统一 OSS 上传逻辑返回 `download_url`；若数据量较大，再扩展为异步导出任务。

## 6. 数据口径

### 6.1 指标定义

| 指标 | 计算口径 | 数据来源 |
|------|----------|----------|
| 销售额 | 命中该活动订单的 `buyer_payment` 或折扣归因销售额求和 | `shopee_orders` / `shopee_discount_performance_daily` |
| 售出件数 | 命中该活动订单明细数量求和 | `shopee_order_items` 或表现快照 |
| 订单数 | 命中该活动的订单数 | `shopee_orders.marketing_campaign_id` |
| 买家数 | 命中该活动订单的买家去重数 | `shopee_orders.buyer_name/buyer_id` |
| 售出商品数 | 产生销量的活动商品去重数，或商品维度销量求和 | 活动商品 + 订单明细 |

### 6.2 时间口径

| 参数 | 含义 | 使用场景 |
|------|------|----------|
| `order_time` | 按下单时间统计 | 默认口径，对齐官方截图 `Order Time` |
| `completed_time` | 按订单完成时间统计 | 用于复盘已完成订单表现 |

### 6.3 与现有表现快照的关系

- 若 `shopee_discount_performance_daily` 已稳定写入活动维度每日快照，主接口优先读取该表，避免实时聚合大量订单。
- 若某日快照缺失，接口可对该活动订单做实时聚合补齐返回，但不在查询接口内直接写库。
- 后续可由订单模拟器或定时任务在订单生成/完成时回写 `performance_daily`。

## 7. 数据库设计

### 7.1 复用现有表

| 表 | 用途 |
|----|------|
| `shopee_discount_campaigns` | 活动基础信息、活动周期、状态 |
| `shopee_discount_campaign_items` | 活动商品、原价、折扣规则、折后价 |
| `shopee_discount_performance_daily` | 活动每日表现快照，支撑指标卡与趋势图 |
| `shopee_orders` | 订单归因，使用 `marketing_campaign_id` 关联活动 |
| `shopee_order_items` | 商品排行的销量、金额、规格维度聚合 |

### 7.2 可选新增导出任务表

若导出数据同步生成即可完成，MVP 不新增表；若需要异步导出，新增表：`shopee_discount_data_exports`。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | bigint PK | 导出任务 ID |
| `run_id` | bigint index | 对局 ID |
| `user_id` | bigint index | 用户 ID |
| `campaign_id` | bigint index | 折扣活动 ID |
| `export_type` | varchar(16) | csv / xlsx |
| `time_basis` | varchar(32) | order_time / completed_time |
| `status` | varchar(32) | processing / ready / failed |
| `oss_object_key` | varchar(512) nullable | 导出文件 OSS key |
| `download_url` | text nullable | 临时下载地址或可访问 URL |
| `error_message` | text nullable | 失败原因 |
| `expires_at` | datetime nullable | 文件过期时间 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

表注释：`Shopee 单品折扣活动数据页导出任务表，用于记录活动经营数据导出文件的生成状态与 OSS 地址。`

字段注释需在模型与初始化/迁移脚本中同步维护，符合仓库数据库规则。

### 7.3 索引建议

| 表 | 索引 | 用途 |
|----|------|------|
| `shopee_orders` | `(run_id, user_id, marketing_campaign_id, created_at)` | 按活动与下单时间聚合 |
| `shopee_orders` | `(run_id, user_id, marketing_campaign_id, completed_at)` | 按完成时间聚合 |
| `shopee_order_items` | `(order_id, product_id)` | 商品排行聚合 |
| `shopee_discount_performance_daily` | `(run_id, user_id, campaign_id, stat_date)` | 趋势查询 |

## 8. Redis 设计

### 8.1 缓存键

| 键模式 | TTL | 用途 |
|--------|-----|------|
| `{prefix}:cache:shopee:discount:data:{run_id}:{user_id}:{campaign_id}:{time_basis}` | 30s | 数据页首屏缓存 |
| `{prefix}:cache:shopee:discount:data-trend:{run_id}:{user_id}:{campaign_id}:{metric}:{time_basis}` | 30s | 趋势图缓存 |
| `{prefix}:cache:shopee:discount:data-ranking:{run_id}:{user_id}:{campaign_id}:{page}:{page_size}:{sort}:{order}:{time_basis}` | 30s | 商品排行缓存 |
| `{prefix}:rate:shopee:discount:data:{run_id}:{user_id}` | 60s 窗口 | 数据页访问限流 |
| `{prefix}:rate:shopee:discount:data-export:{run_id}:{user_id}` | 60s 窗口 | 导出限流 |

### 8.2 缓存失效

以下动作需要清除该对局用户下折扣数据缓存：

- 折扣活动创建、编辑、停用、删除。
- 订单模拟器生成命中活动的新订单。
- 订单状态推进到完成、取消或回款影响统计口径。
- `shopee_discount_performance_daily` 被回写或重算。

建议按 `run_id:user_id` 前缀批量清理：

```
{prefix}:cache:shopee:discount:data:{run_id}:{user_id}:
{prefix}:cache:shopee:discount:data-trend:{run_id}:{user_id}:
{prefix}:cache:shopee:discount:data-ranking:{run_id}:{user_id}:
```

避免只按 `campaign_id` 后缀删除导致分页、排序、time_basis 缓存漏删。

### 8.3 限流

| 端点 | 每分钟限制 | 说明 |
|------|-----------|------|
| 数据页主接口 | 60 次 | 与详情主接口一致 |
| 趋势/排行子接口 | 120 次 | 翻页和指标切换较频繁 |
| 导出接口 | 10 次 | 防止重复生成导出文件 |

## 9. 历史对局只读模式

- 已结束对局允许进入数据页查看历史数据。
- 数据页所有指标固定使用历史订单与快照，不触发新的订单模拟。
- 导出允许保留，但导出内容必须来自历史只读数据。
- 不展示编辑、停用、复制等写操作。

## 10. 空状态与异常状态

| 场景 | 展示 |
|------|------|
| 活动不存在或不属于当前用户 | 404 / 页面提示“活动不存在或无权访问” |
| 活动无订单数据 | 指标卡为 0，趋势图与排行显示空状态 |
| 趋势数据缺失部分日期 | 缺失日期补 0，保持横轴连续 |
| 商品图片缺失 | 使用现有商品占位图 |
| 导出失败 | Toast 提示失败原因，按钮恢复可点击 |

## 11. 验收标准

| # | 验收项 | 验证方式 |
|---|--------|----------|
| 1 | 活动列表点击“数据”可进入数据页 | 前端手动验证 |
| 2 | 数据页 URL 正确携带 `campaign_id` | 浏览器地址栏检查 |
| 3 | 页面结构与官方截图一致：横幅、指标卡、趋势图、排行表 | 视觉对照截图 |
| 4 | 主容器使用 `mx-auto max-w-[1360px] pb-10`，宽度与创建页/详情页一致 | 前端 DOM 与截图检查 |
| 5 | 字号层级符合文档规范：面包屑/表格 12px、指标数值 18px、商品补充信息 11px | 前端样式检查 |
| 6 | 指标卡与后端聚合值一致 | 对比数据库聚合 SQL |
| 7 | 趋势图按日期连续展示，缺失日期补 0 | 构造缺失日期数据验证 |
| 8 | 切换指标后图表数值更新 | 前端交互验证 |
| 9 | 商品排行按销售额默认降序 | 对比后端返回排序 |
| 10 | 商品排行支持分页 | 翻页验证 |
| 11 | 点击 `Promotion Details >` 可跳转活动详情页 | 路由验证 |
| 12 | 导出按钮可生成 CSV/XLSX 下载链接 | 接口与文件内容验证 |
| 13 | 历史对局可查看数据页且不触发写操作 | 历史局手动验证 |
| 14 | Redis 缓存命中、TTL、失效符合预期 | 查看缓存键与接口日志 |

## 12. 与现有设计的衔接

| 现有设计文档 | 衔接点 |
|-------------|--------|
| 19-Shopee折扣页复刻设计 | 活动列表页新增“数据”入口 |
| 20-Shopee单品折扣创建页设计 | 创建后的活动可进入数据页复盘 |
| 23-单品折扣生效与订单影响设计 | 数据页指标来源于折扣对订单成交价和归因的影响 |
| 24-折扣对下单概率的影响设计 | 数据页用于验证折扣概率模型带来的销量变化 |
| 25-Shopee单品折扣活动详情页设计 | 详情页看规则与归因订单，数据页看指标趋势与商品排行 |

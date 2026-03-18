# 06-店铺运营（Shopee）设计

## 1. 阶段定位
- 阶段编号：`Step 05`
- 阶段名称：`店铺运营（Shopee）`
- 入口前置：
  - Step 02 已完成采购下单
  - Step 03 已完成国际物流与清关
  - Step 04 已完成海外仓入仓（形成可售库存）
- 阶段目标：在限定游戏时间内，通过上架、定价、营销与履约处理，最大化销售额与利润，并维持店铺评分。

## 2. 玩法目标与胜负指标
- 核心经营目标：
  - 提升 `GMV`（销售额）
  - 控制 `利润率`
  - 降低 `取消/退款率`
  - 稳定 `店铺评分`
- 阶段建议 KPI（V1）：
  - 订单量
  - 销售额（GMV）
  - 毛利润
  - 广告花费与投产比（ROAS）
  - 退款率
  - 履约超时率
  - 店铺评分（1~5）

## 3. 页面模块设计（Shopee 运营台）

### 3.1 页面总体布局
- 左侧：运营菜单（仪表盘、商品管理、活动营销、广告投放、订单履约、竞品情报）
- 中间：主操作区（根据菜单切换模块）
- 右侧：经营总览（现金、库存、今日订单、评分、倒计时）
- 顶部：阶段标识、玩家信息、返回工作台、下一阶段入口（满足条件后可进入结算/下一环节）

### 3.2 模块拆分
1. `运营总览 Dashboard`
- 今日核心数据卡（销售额、订单、退款、广告花费）
- 趋势图（近7天/近30天）
- 关键告警（库存不足、评分下滑、超时上升）

2. `商品管理 Listing`
- SKU 列表：库存、售价、毛利、状态（上架/下架）
- 批量上架/下架
- 价格调整（单品或批量）

3. `活动营销 Campaign`
- 活动创建（满减、折扣、限时促销）
- 活动预算设置
- 活动效果追踪（曝光、点击、转化）

4. `广告投放 Ads`
- 广告开关与预算
- 出价档位（低/中/高）
- ROI 指标（消耗、成交、ROAS）

5. `订单履约 Orders`
- 待处理订单、待发货、已完成、退款中
- 自动扣减库存
- 超时风险提示

6. `竞品情报 Competitor`
- 展示竞品前台信息：价格、主图、销量区间、活动状态
- 玩家可对比后调整本店价格/活动策略

## 4. 经营循环（V1）
1. 选择 SKU 上架
2. 设定价格
3. 可选开启活动与广告
4. 系统按“需求 + 竞品 + 价格 + 活动 + 广告 + 时效评分”生成订单
5. 订单履约并扣库存
6. 产生销售、成本、退款与评分变化
7. 玩家根据结果继续调整策略（形成日循环）

## 5. 与前序阶段数据衔接
- 输入数据：
  - Step 04 生成库存批次（InventoryLots）
  - Step 04 生成仓储策略参数（时效分、履约准确率、成本）
  - Step 01 资金剩余
- 输出数据：
  - 销售流水
  - 广告消耗
  - 订单状态明细
  - 店铺评分与阶段积分

## 6. 数据模型建议（后端）

### 6.1 新增核心表（建议）
1. `shop_store_profiles`
- `id`, `run_id`, `channel`(shopee), `store_name`, `rating`, `followers`, `status`, `created_at`

2. `shop_listings`
- `id`, `run_id`, `product_id`, `title`, `price`, `is_active`, `daily_budget`, `created_at`, `updated_at`

3. `shop_campaigns`
- `id`, `run_id`, `campaign_type`, `discount_rate`, `budget`, `start_day`, `end_day`, `status`

4. `shop_ads`
- `id`, `run_id`, `listing_id`, `bid_level`, `daily_budget`, `status`, `spend_total`, `gmv_total`

5. `shop_orders`
- `id`, `run_id`, `listing_id`, `quantity`, `unit_price`, `order_amount`, `status`, `created_at`, `completed_at`

6. `shop_order_events`
- `id`, `order_id`, `event_type`(placed/shipped/completed/refund), `event_time`, `remark`

7. `shop_competitor_snapshots`
- `id`, `run_id`, `category`, `competitor_name`, `price`, `monthly_sales`, `main_image_url`, `snapshot_day`

### 6.2 可复用现有表
- `inventory_lots`：作为可售库存源
- `market_products`：作为商品基础属性与成本参考

## 7. API 设计草案（V1）
- `GET /game/runs/{run_id}/shop/shopee/overview`
- `GET /game/runs/{run_id}/shop/shopee/listings`
- `POST /game/runs/{run_id}/shop/shopee/listings`
- `PATCH /game/runs/{run_id}/shop/shopee/listings/{listing_id}`
- `POST /game/runs/{run_id}/shop/shopee/campaigns`
- `POST /game/runs/{run_id}/shop/shopee/ads`
- `GET /game/runs/{run_id}/shop/shopee/orders`
- `POST /game/runs/{run_id}/shop/shopee/simulate-day`
- `GET /game/runs/{run_id}/shop/shopee/competitors`

## 8. 结算与评分建议（V1）
- 每个“游戏日”更新一次阶段得分：
  - 销售贡献分
  - 利润贡献分
  - 服务质量分（退款率/超时率/评分）
  - 运营效率分（广告投产、库存周转）
- 阶段结束累计进总分，用于班级排行榜/多人对局比较。

## 9. DLC 扩展设计
- 采用渠道插件化：
  - `channel = shopee | tiktok | amazon`
- 复用通用能力：
  - 库存、订单、资金、评分、倒计时
- 渠道差异放在插件层：
  - 流量机制、广告模型、活动规则、费率结构

## 10. V1 边界（先做）
- 先做 Shopee 单渠道
- 先做核心闭环：上架、定价、活动、广告、订单、竞品参考
- 暂不做复杂突发事件（政策/战争/关税波动），后续以事件系统追加







最简流程：
1) 进场准备（进入 Step05 的第一分钟）
前提是你前面 4 步都完成了：有钱、有货、货已清关、已入仓。
进入 Shopee 运营台后，玩家先做这几件事：

1. 看右侧经营总览
确认当前可用资金、可售库存、店铺评分、倒计时。
2. 选要卖的 SKU（上架）
不是所有货都必须上架，先挑“更有把握出单”的商品。
3. 给每个 SKU 定价
价格直接影响转化和利润，是第一关键决策。
4. 选是否开活动/广告
活动偏“拉转化”，广告偏“拉流量”，都会增加成本。

这一段的目标不是马上最优，而是先把“可出单的经营盘”搭起来。

2) 每日经营循环（Step05 主体）
这个阶段的核心是你文档里的日循环。每个游戏日都重复这个闭环：

1. 上架与价格状态生效
你当前设置（上架、价格、活动、广告）进入当天市场。
2. 系统生成订单
系统会综合：需求、竞品价格、你的价格、活动力度、广告投放、履约时效评分 来决定当天订单量。
3. 履约与库存扣减
出单后进入订单履约流程，库存自动减少，开始出现待处理/待发货/完成/退款等状态。
4. 财务与服务结果更新
产生 GMV、毛利润、广告消耗、退款率、超时率、评分变化。
5. 玩家复盘并调参
看数据结果，再改下一天策略：
- 卖得慢：考虑降价或加活动/广告
- 卖得快但不赚钱：提价或收广告
- 退款/超时高：要优化履约与节奏
6. 进入下一天
持续滚动，直到阶段时间结束。
你可以把它理解为：“看数 → 调策略 → 再看数” 的持续博弈。

3) 玩家每天重点看什么（实战优先级）
建议按这个顺序盯盘：

1. 订单量、GMV（有没有卖起来）
2. 毛利润、广告 ROAS（卖得多是否赚钱）
3. 退款率、超时率、店铺评分（服务质量是否失控）
4. 库存水位（避免断货或压货）

也就是：先活下来（有订单）→ 再赚钱（利润）→ 再稳服务（评分）。

4) 阶段收尾（Step05 结束时）
到阶段结束时，系统会按你文档的评分维度汇总：

- 销售贡献（GMV/订单）
- 利润贡献（毛利、投产）
- 服务质量（退款、超时、评分）
- 运营效率（库存与投放效率）

最终进入总分，用于班级/多人对局比较。

一句话总结这个阶段：
Step05 不是“做一次设置就结束”，而是一个持续调参的经营循环，谁能在销量、利润和服务质量之间长期平衡，谁就赢。
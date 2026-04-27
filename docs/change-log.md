# Change Log

最后更新：2026-04-27（优化 Shopee 套餐订单组合图片展示）

## 2026-04-27

### 修复
- 优化 Shopee 我的订单列表中套餐优惠订单的组合图片展示。
  - 涉及文件：`frontend/src/modules/shopee/views/MyOrdersView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增订单商品图片渲染组件，普通订单继续显示单图；套餐优惠多 SKU 订单改为 2x2 组合宫格展示订单明细中的多个 SKU 图片。
  - 影响范围：仅影响我的订单列表商品图片展示，不改变订单数据、金额、履约和营销归因逻辑。
- 修正 Shopee 套餐优惠期间多规格商品的规格选择口径。
  - 涉及文件：`backend/apps/api-gateway/app/services/shopee_order_simulator.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 根因：此前为提高套餐命中，在最终选规格阶段对参加 bundle 的 003/004 增加权重，导致同一商品下未促销的 YZ-C-001 在促销期被挤出，表现为 001 不再自然出单。
  - 修复内容：最终选规格阶段恢复为自然价格/库存/随机扰动评分，不再使用 bundle 权重；只有自然选中套餐 SKU 后才进入套餐组合判断和套餐成交概率计算。
  - 影响范围：套餐优惠不再压制同商品下其他未促销规格的自然销售；套餐组合判断仍只在自然选中套餐 SKU 时触发。
- 修复 Shopee 套餐优惠 `purchase_limit=1` 被误当成活动全局售罄开关的问题。
  - 涉及文件：`backend/apps/api-gateway/app/services/shopee_order_simulator.py`、`docs/设计文档/27-套餐优惠概率计算设计.md`、`docs/设计文档/28-Shopee套餐优惠组合购买改造设计.md`、`docs/当前进度.md`
  - 根因：订单模拟器在加载 ongoing bundle 时按 campaign 累计 bundle 订单数过滤 `purchase_limit`，导致真实活动已有 1 单套餐后，后续管理员加速模拟买到 YZ-C-003/YZ-C-004 也不再加载该套餐活动，只能退回普通单品随机数量。
  - 修复内容：`purchase_limit` 改为买家维度限购：同一买家已购买该套餐次数达到上限后不再命中该套餐，其他买家仍可继续命中；买家决策流水补充 `bundle_purchase_limit_reached` 与 `bundle_purchase_limit_used` 便于排查。
  - 影响范围：仅套餐优惠订单模拟；普通订单和单品折扣随机购买数量逻辑不变。
- 修复 Shopee 套餐优惠下单长期不命中套餐活动的问题。
  - 涉及文件：`backend/apps/api-gateway/app/services/shopee_order_simulator.py`、`docs/设计文档/27-套餐优惠概率计算设计.md`、`docs/当前进度.md`
  - 根因：多变体商品的变体选择只按价格/库存/随机扰动评分，不感知哪些变体参加了套餐优惠；同时套餐加购概率对购买力约束过强，出现“原价能买 2/3 件但优惠套餐不命中”的不合理结果。
  - 修复内容：变体选择对参加 bundle 的变体增加营销加权；套餐加购概率提高基础兴趣、节省吸引和冲动加成，并将购买力约束下限调整为 0.60；买家决策流水补充 `variant_id` 与 `variant_name` 便于排查。
  - 验证结果：真实库 run_id=6 / campaign_id=5 受控模拟已生成 `marketing_campaign_type="bundle"` 订单，订单号 `SIM2026042715942E726828`，数量 3，套餐单价 94。
- 修复 Shopee 套餐优惠订单模拟中阶梯库存判断误用普通下单数量上限的问题。
  - 涉及文件：`backend/apps/api-gateway/app/services/shopee_order_simulator.py`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`docs/当前进度.md`
  - 根因：bundle upgrade 阶梯过滤使用了普通下单 `max_qty`，该值会被限制到最多 3 件并可能被商品 `max_purchase_qty` 压到 1 件，导致套餐阶梯被提前过滤，订单无法归因到套餐活动，套餐数据页订单/销售额为 0。
  - 同步修复：订单列表触发自动模拟后同步失效 Shopee 营销数据页缓存，避免新订单生成后数据页短时间继续读取旧的 0 指标。
  - 影响范围：套餐优惠订单模拟会按真实 `sellable_cap` 判断可支撑阶梯；普通订单随机购买数量仍保持原有 `max_qty` 逻辑，单品折扣概率链路不变。

### 新增
- 实现 Shopee 套餐优惠多 SKU 组合购买订单链路。
  - 涉及文件：`backend/apps/api-gateway/app/models.py`、`backend/apps/api-gateway/app/db.py`、`backend/apps/api-gateway/app/services/shopee_order_simulator.py`、`backend/apps/api-gateway/app/services/shopee_order_cancellation.py`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/views/MyOrdersView.tsx`、`frontend/src/modules/shopee/views/MyOrderDetailView.tsx`、`docs/当前进度.md`
  - 实现内容：`shopee_order_items` 新增 item 级 SKU 与履约字段；买家选择到优惠期内的套餐组合 SKU 后自动归因为套餐优惠，按组合内 SKU 创建多条订单明细，并逐 item 预占库存、发货消耗库存、取消释放库存和补货回填；订单列表/详情响应返回 item 级字段。
  - 前端展示：我的订单列表对多 SKU 套餐显示组合摘要，订单详情逐 SKU 展示套餐组合明细。
  - Redis/cache 影响：继续复用订单列表与营销数据页缓存失效链路，订单模拟、发货、取消后的缓存失效口径不变。
  - 影响范围：仅 `marketing_campaign_type="bundle"` 的套餐订单进入组合 SKU 分支；普通订单和单品折扣订单仍沿用原有随机购买数量与单 item 下单逻辑。
- 新增设计文档 `docs/设计文档/28-Shopee套餐优惠组合购买改造设计.md`，定义 Shopee 套餐优惠从单 SKU 多件加购改为多 SKU 组合购买的改造方案。
  - 涉及文件：`docs/设计文档/28-Shopee套餐优惠组合购买改造设计.md`、`docs/当前进度.md`
  - 方案口径：套餐订单命中后必须包含组合内所有 SKU，不允许只买其中一个；普通订单和单品折扣继续沿用现有随机购买数量逻辑，仅 `marketing_campaign_type="bundle"` 订单进入多 SKU 分支。
  - 影响范围：本次仅新增设计文档和进度台账，尚未改动业务代码；后续实现需补充 `shopee_order_items` item 级 SKU 字段，并改造订单生成、发货、取消、补货和订单展示链路。
- 我的订单列表与详情页补充 Shopee 套餐优惠订单标识。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/views/MyOrdersView.tsx`、`frontend/src/modules/shopee/views/MyOrderDetailView.tsx`、`docs/当前进度.md`
  - 后端订单列表/详情响应新增返回 `marketing_campaign_type`，详情响应同步补齐 `marketing_campaign_id`、`marketing_campaign_name_snapshot` 与折扣比例；前端按 `marketing_campaign_type` 区分显示“单品折扣”或“套餐优惠”。
  - 影响范围：我的订单页中通过套餐优惠成交的订单会显示“套餐优惠：活动名”，不再被统一显示为折扣活动；单品折扣订单继续显示折扣比例。
- 为 Shopee 单品折扣订单模拟补充概率保底机制。
  - 涉及文件：`backend/apps/api-gateway/app/services/shopee_order_simulator.py`、`docs/当前进度.md`
  - 方案口径：命中单品折扣时同时计算无折扣对照概率 `no_discount_order_prob` 和折扣后概率 `discount_order_prob`，最终下单概率不低于无折扣对照，避免有效折扣降低转化；买家决策流水同步记录 `no_discount_order_prob` 与 `discount_order_prob`。
  - 影响范围：单品折扣订单模拟概率保底；套餐优惠仍使用专用 bundle 概率分支，二者互斥不叠加。
- 按 27 号设计文档实现 Shopee 套餐优惠接入订单模拟的概率计算链路。
  - 涉及文件：`backend/apps/api-gateway/app/services/shopee_order_simulator.py`、`docs/当前进度.md`
  - 后端新增 `campaign_type="bundle"` 活动加载、bundle 每件折后价计算、加购阶梯概率、`max(base_order_prob, bundle_order_prob)` 概率保底和单品折扣互斥选择；订单归因支持记录套餐活动，买家决策流水记录 `bundle_applied`、`bundle_qty`、`bundle_attempts`、`base_order_prob` 与 `bundle_order_prob`。
  - 影响范围：订单模拟中套餐优惠将影响下单概率与购买数量；单品折扣原有概率链路保持独立，二者不叠加。
- 新增并修正设计文档 `docs/设计文档/27-套餐优惠概率计算设计.md`，定义 Shopee 套餐优惠接入订单模拟的概率计算方案。
  - 涉及文件：`docs/设计文档/27-套餐优惠概率计算设计.md`、`docs/当前进度.md`
  - 方案口径：三种套餐类型统一折算为每件折后价，再通过节省比例、价格敏感度、冲动系数与购买力约束计算加购概率；bundle 命中后需重算 `price_score`、`bundle_score` 与 `bundle_order_prob`，并以 `max(base_order_prob, bundle_order_prob)` 保底，确保有效优惠不降低下单概率；`purchase_limit` 按买家维度限制套餐购买次数。
  - 影响范围：仅更新设计文档和进度台账，尚未改动订单模拟代码。

### 修复
- 修复 Shopee 单品折扣活动数据页指标卡订单数未按选中游戏年过滤的问题。原订单数使用活动关联订单总数，导致选择折扣活动时间之外的游戏年时仍显示历史订单数；现改为仅统计通过游戏时间年份过滤后的订单数。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`docs/当前进度.md`
  - 影响范围：单品折扣活动数据页关键指标卡订单数；销售额、售出件数、买家数、趋势图和商品排行口径不变，均按选中游戏年过滤。
- 修复 Shopee 单品折扣活动数据页在部分游戏年份没有月度订单数据时，趋势图从 12 个月横坐标退回日维度横坐标的问题。后端按选中游戏年补齐 1-12 月 `monthly_rows`，前端按 `selected_game_year` 固定生成 12 个月横坐标，统计口径保持游戏时间而非真实时间。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/views/DiscountDataView.tsx`、`docs/当前进度.md`
  - 影响范围：单品折扣活动数据页趋势图年份下拉模式；`Check Details` 日维度明细、指标卡和商品排行仍按选中游戏年过滤。

## 2026-04-26

### 修复
- 修复 Shopee 单品折扣活动数据页趋势图在月度模式（坐标轴跨度 > 60 天）下买家数和售出商品数重复计数的问题。原前端月度聚合将每日去重值直接求和，导致同一买家/商品在多天出现时被重复计入。改为后端计算月度去重数据（`monthly_rows`），前端月度模式直接使用。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/views/DiscountDataView.tsx`
  - 影响范围：趋势图月度模式的买家数与售出商品数数值；日度模式与指标卡片不受影响。

## 2026-04-24

### 新增
- Shopee 单品折扣活动数据页关键指标区新增游戏年份区间下拉筛选，数据周期固定显示为单个游戏年（如 `2026-01-01 00:00 - 2027-01-01 00:00`）。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/views/DiscountDataView.tsx`、`docs/当前进度.md`
  - 影响范围：活动数据页首屏指标卡、趋势图与商品排行按所选游戏年份区间聚合，排行缓存 key 已纳入 `game_year`，避免不同年份数据互相复用。
- 调整 Shopee 单品折扣活动数据页趋势图 `Check Details` 触发器样式，改为无边框蓝色文字；未展开显示向下符号，展开后显示向上符号。
  - 涉及文件：`frontend/src/modules/shopee/views/DiscountDataView.tsx`
  - 影响范围：仅调整趋势明细展开按钮视觉，不改变明细数据和展开逻辑。
- 修正 Shopee 单品折扣活动数据页趋势图与明细日期口径，活动时间、趋势折线和 `Check Details` 表格均改为游戏时间，并按游戏日补齐每日数据。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/views/DiscountDataView.tsx`、`docs/当前进度.md`
  - 影响范围：数据页不再按真实订单日期聚合为单天；趋势图与明细表会展示活动覆盖的多个游戏日，缓存 key 已切到 `game-day-v2` 版本避免旧数据残留。
- Shopee 单品折扣活动数据页趋势图新增 `Check Details` 展开明细，可在图表下方查看按日期汇总的 Sales、Units Sold、Orders、Buyers 与 Sales Per Buyer。
  - 涉及文件：`frontend/src/modules/shopee/views/DiscountDataView.tsx`、`docs/当前进度.md`
  - 影响范围：复用现有趋势数据渲染前端明细表，不新增后端接口，不改变导出与商品排行逻辑。
- 调整 Shopee 单品折扣活动数据页布局，删除趋势图上方独立指标按钮栏，并将时间口径选择与导出按钮上移到活动信息卡右侧，`Promotion Details >` 入口移动到活动状态标签右侧。
  - 涉及文件：`frontend/src/modules/shopee/views/DiscountDataView.tsx`、`docs/当前进度.md`
  - 影响范围：仅调整数据页信息层级与操作区位置，指标卡多选、趋势图、导出逻辑和后端接口不变。
- 已按 26 号设计文档实现 Shopee 单品折扣活动数据页首版。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/components/Header.tsx`、`frontend/src/modules/shopee/components/Sidebar.tsx`、`frontend/src/modules/shopee/views/MarketingDiscountView.tsx`、`frontend/src/modules/shopee/views/DiscountDataView.tsx`、`docs/当前进度.md`
  - 后端新增数据页主接口、趋势子接口、商品排行子接口与 CSV 导出接口，并接入数据页缓存、排行/趋势缓存、访问限流、导出限流和折扣缓存统一失效。
  - 前端新增 `DiscountDataView`，活动列表“数据 / 查看数据”可进入 `/u/{public_id}/shopee/marketing/discount/data?campaign_id={id}`；页面按官方数据页结构展示店铺/站点选择器、提示横幅、活动信息、5 个指标卡、轻量 SVG 趋势图、商品排行和导出按钮。
  - 数据库首版不新增表，复用 `shopee_discount_campaigns`、`shopee_discount_campaign_items`、`shopee_orders`、`shopee_order_items`；导出首版同步生成 CSV data URL，后续数据量变大时再扩展异步导出任务表。
  - 影响范围：Shopee 折扣活动从列表页进入经营表现复盘页的链路已具备真实数据驱动能力；进行中活动操作列新增“数据”，已结束活动操作列调整为“数据 / 详情 / 复制”。
- 调整 Shopee 单品折扣活动数据页趋势图交互，对齐官方页面最多同时查看 4 个指标的口径。
  - 涉及文件：`frontend/src/modules/shopee/views/DiscountDataView.tsx`
  - 指标卡改为可多选，默认选中销售额、售出件数、订单、买家；最多同时选中 4 项，至少保留 1 项。
  - 仅选中的指标卡显示顶部颜色条，顶部指标按钮、趋势图折线和数据点统一使用同一颜色，并在图例右侧显示 `Metrics Selected X / 4`。
  - 影响范围：数据页趋势图从单指标切换升级为多指标对比，不影响后端接口结构。
- 新增设计文档 `docs/设计文档/26-Shopee单品折扣活动数据页设计.md`，定义折扣活动列表点击“数据 / 查看数据”后的官方数据页复刻方案。
  - 页面覆盖：顶部面包屑、店铺/站点选择器、官方提示横幅、活动基础信息、关键指标卡、趋势图、商品排行与导出按钮。
  - 前端口径：新增 `DiscountDataView`，路由为 `/u/{public_id}/shopee/marketing/discount/data?campaign_id={id}`，活动列表操作列新增“数据”入口，并与详情页区分职责。
  - 后端接口：规划活动数据主接口、趋势子接口、商品排行子接口与导出接口。
  - 数据库：优先复用 `shopee_discount_campaigns`、`shopee_discount_campaign_items`、`shopee_discount_performance_daily`、`shopee_orders`、`shopee_order_items`，并预留异步导出任务表 `shopee_discount_data_exports`。
  - Redis：规划数据页首屏、趋势、排行缓存，以及访问/导出限流和按 `run_id:user_id` 前缀失效策略。
  - 视觉规范：补充主容器 `mx-auto max-w-[1360px] pb-10`，以及面包屑、标题、指标卡、图表、表格、商品信息的字号与间距规范。
  - 影响范围：仅新增设计文档与进度/变更台账，尚未改动前后端代码或数据库结构。
- 新增并修正设计文档 `docs/设计文档/25-Shopee单品折扣活动详情页设计.md`，定义已结束/所有状态折扣活动"详情"页面。
  - 页面覆盖：活动基础信息、表现总览（4 指标卡）、参与商品 Tab、表现趋势 Tab、归因订单 Tab。
  - 前端口径：详情页沿用 `/u/{public_id}/shopee/...` 路由前缀，活动列表点击"详情"时用 `row.id` 作为 `campaign_id`，并将详情页纳入隐藏左侧菜单栏的视图集合。
  - 后端接口：1 个详情主接口 + 3 个 Tab 分页子接口；主接口只返回三个 Tab 的第 1 页数据，不返回全量。
  - 字段口径：归因订单字段改为对齐现有模型的 `order_no`、`buyer_name`、`buyer_payment`、`type_bucket`，折扣方式改为 `percent/final_price`。
  - 数据库：无需新增表或字段，复用现有 `shopee_discount_campaigns`、`campaign_items`、`performance_daily`、`shopee_orders(marketing_campaign_id)`。
  - Redis：MVP 优先保证接口正确性；如接入缓存，按 `run_id:user_id` 前缀清除详情缓存，避免按 `campaign_id` 后缀失效漏删。
  - 影响范围：后续实现将新增 `DiscountDetailView` 前端视图与 4 个后端接口。
- 已按 25 号设计文档实现 Shopee 单品折扣活动详情页首版。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/views/MarketingDiscountView.tsx`、`frontend/src/modules/shopee/views/DiscountDetailView.tsx`、`frontend/src/modules/shopee/components/Header.tsx`、`frontend/src/modules/shopee/components/Sidebar.tsx`、`docs/当前进度.md`
  - 后端新增详情主接口与参与商品/表现趋势/归因订单 3 个分页子接口，并接入详情缓存、限流与折扣缓存统一失效。
  - 前端新增 `DiscountDetailView`，活动列表“详情”按钮可跳转详情页；详情页按 Shopee 官方详情页截图收口为中文复刻版，移除页面内重复面包屑，基本信息区采用标题 + 状态标签 + 横向三列字段布局并将字号收回到系统常用层级；折扣商品区按官方截图调整搜索框、商品总数、表头顺序与折扣标签样式，库存列改为读取后端详情接口返回值，并保留返回列表页按钮。
  - 单品折扣 Tab 下“促销表现”的默认统计区间改为当前游戏日期所在的周一到周日自然周；手动选择 `date_from/date_to` 时仍优先使用用户筛选范围。
  - 影响范围：Shopee 折扣活动从列表页进入详情页的复盘链路已具备真实数据驱动能力；数据库结构未新增。

### 修复
- 修复 Shopee 待入账收入永远不释放的问题：回填收入时改为使用当前游戏时间 `current_tick` 判断释放条件，并将订单完成后 3 天释放改为按 3 个游戏日换算。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`backend/apps/api-gateway/tests/test_api.py`、`docs/bug/2026-04-23-待入账收入永远不释放.md`
  - 影响范围：已完成订单将在送达后 3 个游戏日释放待入账收入并生成 `income_from_order` 钱包流水，不再永久停留在待入账。

### 优化
- 我的收入页面底部翻页器改为与我的订单一致的页码按钮样式：支持显示所有页码、省略号、首尾页跳转，移除无功能的 pageSize 下拉。
  - 涉及文件：`frontend/src/modules/shopee/views/MyIncomeView.tsx`
  - 影响范围：我的收入（待入账/已入账）底部翻页器交互体验与我的订单统一。

## 2026-04-23

### 修复
- 修复 `_parse_discount_game_datetime` 中游戏年份基准与 `_format_discount_game_datetime` 不一致的问题：将 `datetime(parsed_value.year, 1, 1)` 改为 `datetime(run.created_at.year, 1, 1)`，使解析与格式化使用相同基准年，消除跨年游戏时间（如 2027-11 月）存库后折扣立即显示”已结束”的 bug。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`
  - 影响范围：单品折扣创建页选择跨年游戏时间后，折扣状态将正确显示为进行中/即将开始，不再错误显示已结束。

### 新增
- 订单列表接口新增 `marketing_campaign_id`、`marketing_campaign_name_snapshot`、`discount_percent` 字段，命中折扣的订单会返回折扣活动名称与折扣比例。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`
  - 影响范围：`GET /shopee/runs/{run_id}/orders` 返回结构新增三个折扣相关字段，不影响未命中折扣的订单。
- 订单列表前端在买家实付金额下方新增折扣标注：命中折扣时显示”折扣活动：{活动名}”与”折扣 X% off”两行橙色小字。
  - 涉及文件：`frontend/src/modules/shopee/views/MyOrdersView.tsx`
  - 影响范围：我的订单列表中，折扣价购买的订单可一眼识别折扣活动与折扣比例。

### 更新
- 已补齐 Shopee 单品折扣游戏时间生效链路（接上 2026-04-23 首条记录）：
  - 折扣创建页时间语义改为游戏时间，bootstrap/草稿/创建统一换算存库；
  - 订单模拟器接入 ongoing 折扣，成交价改用折后价，`price_sensitivity` 正式参与 `price_score` 计算；
  - 订单营销归因字段（`marketing_campaign_type/id/name_snapshot`）正确写入；
  - 已通过 3 条后端回归测试验证，并经真实对局手动联调确认折扣生效。

## 2026-04-22 (续)

### 修复
- 修复管理员买家池"推进模拟订单"导致 `latest_tick_time` 超前游戏时钟 1 小时的问题：将 `admin_simulate_orders` 中 `effective_tick_time = latest_tick_time + timedelta(hours=1)` 改为直接使用 `latest_tick_time`，使管理员推进仅凭空额外生成订单而不影响游戏时间与自动 worker 进度。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/game.py`
  - 影响范围：管理员在买家池页面点击"推进模拟订单"后，订单正常生成，但 `ShopeeOrderGenerationLog` 的 `MAX(tick_time)` 不再向前推进，自动 worker 不会因 `base_tick > current_game_tick` 触发 clamp warning 或暂停。

### 修复
- 修正 `_resolve_game_hour_tick_by_run` 中 `current_game_tick` 计算逻辑：改为在真实秒数上直接 clamp（`min(elapsed_seconds, total_game_days × REAL_SECONDS_PER_GAME_DAY)`），避免游戏时间超出对局总时长后被错误截断到终点，导致模拟永久停止。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/game.py`
  - 影响范围：`current_game_tick` 现在正确反映真实时间进度，不再在对局未结束时卡在 `game_end_time`。
- 修复 `_cleanup_game_runs_legacy_columns` 中 UPDATE 无 WHERE 条件导致每次重启后端都将所有对局 `total_game_days` 重置为 365 的问题，改为 `COALESCE` 仅填充空值。
  - 涉及文件：`backend/apps/api-gateway/app/db.py`
  - 影响范围：手动修改过 `total_game_days` 的对局不再被重启覆盖。
- 恢复 `max_ticks_per_request` 从临时调试值 240 改回 10。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`

### 新增
- 新增 `docs/说明文档/时间变量说明.md`，以表格形式说明系统中所有时间相关变量的含义、时间轴归属与常见误区。

## 2026-04-22

### 更新
- 已为 Shopee 订单自动模拟补上未来 `tick_time` 钳制保护：当 `latest_tick_time/base_tick` 晚于当前游戏时刻时，后端会记录 warning 日志并将 `base_tick` 钳制到 `current_game_tick`，避免历史脏数据导致 `missing_steps <= 0` 后永久卡死。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`backend/apps/api-gateway/tests/test_api.py`
  - 影响范围：`/shopee/runs/{run_id}/orders` 自动补跑订单时，即使存在未来 `tick_time` 脏数据，也不会再因基准时间落到未来而持续停摆；后端日志会输出 `[order-auto-sim] clamp future base_tick ...` 便于排查。
- 已修正 Shopee 订单自动模拟按“8 游戏小时”补跑 tick 时误用真实小时的问题：`_auto_simulate_orders_by_game_hour` 现改为按 `REAL_SECONDS_PER_GAME_HOUR * 8` 计算步长，并按同一真实秒数推进 `tick_time`。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`backend/apps/api-gateway/tests/test_api.py`
  - 影响范围：订单列表自动补跑、订单生成频率与状态推进将按“每 8 个游戏小时 = 600 真实秒”执行，不再错误地按 8 个真实小时才推进一次。
- 已修正 Shopee 物流 ETA、运输中到已完成推进、以及运输天数字段误按真实天计算的问题，统一改为按 `REAL_SECONDS_PER_GAME_DAY` 的游戏日秒数换算。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`backend/apps/api-gateway/tests/test_api.py`
  - 影响范围：发货后的 `eta_start_at / eta_end_at`、物流事件推进、以及 `transit_days_expected / elapsed / remaining` 现将按“1 游戏日 = 1800 真实秒”口径一致计算，不再错误地拖成真实天。
- 已为 Shopee 订单自动模拟补充临时调试日志，输出 `latest_tick_time`、`base_tick`、`current_game_tick`、`step_seconds`、`missing_steps` 与 `ticks_to_run`，用于排查订单列表刷新时为何没有新增模拟日志。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`
  - 影响范围：刷新 `/shopee/runs/{run_id}/orders` 时，后端终端将打印 `[order-auto-sim]` 调试信息，便于定位自动模拟是否因时间步长判断未命中而提前返回。
- 已新增 bug 记录文档，沉淀“订单自动模拟被未来 `tick_time` 脏数据卡死”的现象、证据、根因与修复建议，便于后续修复时直接对照处理。
  - 涉及文件：`docs/bug/2026-04-22-订单自动模拟被未来tick卡死问题.md`
  - 影响范围：后续排查 run 级订单自动模拟停滞问题时，可直接参考该文档中的调试日志、SQL 与代码修复建议。

## 2026-04-21

### 新增
- 新建 `docs/change-log.md`，作为项目统一变更台账。

### 约定
- 自本次起，凡是我在仓库内执行的代码修改、文档修改、配置修改，都同步记录到本文件。
- 记录格式默认包含：修改时间、涉及文件、修改内容摘要。
- 若某次修改影响业务规则、接口口径或页面行为，会在摘要中明确写出影响范围。

### 更新
- 已将“每次修改都同步更新 `docs/change-log.md`”写入仓库级 `CLAUDE.md`，作为项目长期协作规则。
  - 涉及文件：`CLAUDE.md`
  - 影响范围：后续所有仓库内代码、文档、配置修改都需同步登记变更台账。
- 已修正管理员运行中对局的延长逻辑：延长现实天数时同步重算 `duration_days`、`manual_end_time`、`total_game_days`，并在前端成功提示中展示新的总游戏日。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/game.py`、`frontend/src/modules/admin/AdminRunManagementPage.tsx`
  - 影响范围：管理员“对局管理”中 running 对局延长 7 天 / 14 天 / 自定义天数后，现实结束时间与游戏总天数将按同一口径同步增长。
- 已修正 running 对局延长时总游戏日被按“累计现实总时长”错误放大的问题，改为按本次延长的现实天数增量追加对应游戏天数。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/game.py`
  - 影响范围：例如延长 7 天时，将在旧总游戏日基础上追加 365 天，不再出现 20127 天这类异常放大结果。
- 已将管理员对局管理列表中的“周期”列名改为“真实总周期”，避免将累计现实总时长误读为基准 7 天周期。
  - 涉及文件：`frontend/src/modules/admin/AdminRunManagementPage.tsx`
  - 影响范围：管理员查看对局列表时，可直接按列名理解这里展示的是当前累计真实周期。
- 已修正管理员对局管理中的真实总周期数据口径：列表/买家池/延长接口统一按 `total_game_days` 反推真实总时长，running 对局延长时按“旧真实时长 + 本次延长天数”重算结束时间与 `duration_days`。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/game.py`
  - 影响范围：原先被错误写成 379/386 天的 running 对局，在管理员列表与后续延长后将回到 7→14→21 这类真实天数累计口径。
- 已定点修复本地 docker 库 `cbec_sim.game_runs` 中 `run_id=6` 的错误时长数据，按确认口径回填为真实总时长 14 天、总游戏日 730 天，结束时间同步修正为创建时间 + 14 天。
  - 涉及位置：本地 MySQL 容器 `cbec-mysql` / 表 `game_runs`
  - 影响范围：管理员对局管理中 `#6` 的真实总周期、总游戏日与结束时间恢复到 1 次延长 7 天后的正确状态。
- 已修正管理员对局管理中其他对局的结束时间口径：当 `manual_end_time` 为空时，不再按脏的 `duration_days` 直接推结束时间，改为按真实总周期口径推导真实世界结束时间。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/game.py`
  - 影响范围：本地库中历史对局即使仍保留旧的 `duration_days=365`，管理员列表里的结束时间也会按真实 7 天/14 天等口径显示，不再误显示到 2027 年。
- 已优化管理员对局管理表格交互：移除中间列表的“时间信息”列与快捷延长 7/14 天按钮，放宽列间距，新增按玩家账号快速筛选，并支持点击整行或首列勾选框样式切换选中对局。
  - 涉及文件：`frontend/src/modules/admin/AdminRunManagementPage.tsx`
  - 影响范围：管理员可更快定位指定账号对局，列表操作区更精简，选中态也更直观。
- 已修正管理员对局管理页的工作台双栏布局：左侧内容区改为 `minmax(0, 1fr)`，右侧统一倒计时中心固定保留 420px 宽度，避免被中间表格横向内容挤压截断。
  - 涉及文件：`frontend/src/modules/game-setup/GameSetupPage.tsx`
  - 影响范围：管理员进入“对局管理”时，右侧时间中心卡片将完整显示，不再被左侧表格压缩。
- 已统一管理员延长对局后的时间口径：后端真实周期优先按 `created_at -> manual_end_time/end_time` 计算，extend 改为按新结束时间重算总游戏日；前端右侧统一倒计时中心也改为按新的真实结束时间继续换算，并优先展示后端返回的 Day。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/game.py`、`backend/apps/api-gateway/tests/test_api.py`、`frontend/src/modules/game-setup/GameSetupPage.tsx`
  - 影响范围：管理员延长 running 对局后，中间表格 Day、右侧当前游戏日、右侧剩余倒计时将围绕同一真实结束时间口径同步更新。
- 已收口管理员对局管理的结束时间权威逻辑：后端 `_resolve_run_end_time` 遇到非法 `manual_end_time <= created_at` 时回退到按有效周期推导结束时间，前端表格与摘要只展示后端统一返回的 `end_time`。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/game.py`、`backend/apps/api-gateway/tests/test_api.py`、`frontend/src/modules/admin/AdminRunManagementPage.tsx`
  - 影响范围：历史脏数据不会再导致管理员对局管理表格中出现“开始时间和结束时间一样”的错误展示。
- 已新增管理员“对局管理”统一时间口径设计文档，详细定义对局列表各列字段含义、真实世界时间与游戏日映射关系、延长操作影响链路，以及后端单一权威逻辑和前后端职责边界。
  - 涉及文件：`docs/设计文档/22-管理员对局管理统一时间口径设计.md`、`docs/当前进度.md`
  - 影响范围：后续继续迭代管理员对局管理页、右侧统一倒计时中心与相关接口时，可统一按该文档作为时间语义基线，减少字段口径分叉。
- 已按 22 号设计文档继续收口管理员对局管理时间来源：后端 `duration_days / total_game_days` 统一优先围绕有效 `end_time` 推导，前端管理员列表剩余时间、续期成功提示与右侧统一时间中心也改为只消费后端权威结束时间，不再混用 `manual_end_time` 作为展示来源。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/game.py`、`frontend/src/modules/admin/AdminRunManagementPage.tsx`、`frontend/src/modules/game-setup/GameSetupPage.tsx`
  - 影响范围：管理员“对局管理”表格、中间操作反馈、右侧统一倒计时中心将围绕同一结束时间口径显示，减少历史脏数据或双字段混用带来的分叉。
- 已补充旧对局脏数据兼容：当历史 run 存在 `duration_days=365`、`base_real_duration_days=7`、`total_game_days=365` 且 `manual_end_time` 为空时，后端会优先按基准真实周期 7 天解析真实结束时间与真实总周期，不再把游戏日误当成真实天数返回给管理员界面。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/game.py`、`backend/apps/api-gateway/tests/test_api.py`
  - 影响范围：这类旧局在管理员“对局管理”中将显示正确的 7 天周期与 `created_at + 7天` 的结束时间，不再出现开始时间和结束时间几乎一样、或周期被误读成 365 天的情况。
- 已直接修复本地 MySQL 容器 `cbec-mysql` 中 `cbec_sim.game_runs` 的历史脏数据：将满足“`duration_days=365`、`base_real_duration_days=7`、`total_game_days=365`、`manual_end_time IS NULL`”条件的旧对局回填为真实周期 7 天，并补齐 `manual_end_time = created_at + 7天`。
  - 涉及位置：本地 MySQL 容器 `cbec-mysql` / 数据库 `cbec_sim` / 表 `game_runs`
  - 影响范围：这批旧局在数据库层也回到正确时间口径，管理员“对局管理”页面与底层表数据保持一致。
- 已统一管理员”买家池总览”中部”当前游戏时刻”与右侧统一倒计时中心的时间轴口径：中部卡片优先按 `selected_run_created_at -> selected_run_end_time` 的真实跨度换算游戏时刻，不再固定按基准 7 天推导。
  - 涉及文件：`frontend/src/modules/admin/AdminBuyerPoolPage.tsx`
  - 影响范围：手动延长过的 running 对局在买家池总览中，中部”当前游戏时刻”将与右侧统一时间中心保持一致，不再提前停在旧周期。
- 修复下单时库存预占逻辑：将 `variant_available_stock` 的来源从 `variant.stock`（listing 层展示值）改为直接查询 `inventory_lots.quantity_available`（lot 层真实可用量），消除两者长期不同步导致订单被错误标记为 backorder 的问题；同时移除下单后的 shortfall 追加兜底逻辑（该逻辑在 lot 层为真实来源后已无必要）；在 `inventory_lot_sync.py` 新增 `get_lot_available_qty` 查询函数。
  - 涉及文件：`backend/apps/api-gateway/app/services/shopee_order_simulator.py`、`backend/apps/api-gateway/app/services/inventory_lot_sync.py`
  - 影响范围：下单时将以仓库实际可用库存为准，不再因 `variant.stock` 与 lot 层偏差导致有货订单被标为缺货；取消订单后库存回退逻辑也因此恢复正确（backorder_qty=0，stock_release=qty）。

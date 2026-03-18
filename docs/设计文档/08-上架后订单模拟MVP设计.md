# 08-上架后订单模拟MVP设计

## 1. 目标
在商品“保存并发布”后，系统能自动生成更真实的模拟订单，不再是纯随机下单。
本期先做 **MVP**：
- 先支持 **10个买家人物**。
- 引入 **时段/周期流量波动**。
- 买家基于自身画像对商品进行“是否需要/是否购买”的判断。
- 订单可落库并进入现有 Shopee 订单列表。

## 2. 设计范围（MVP）
### 2.1 本期包含
- 买家池（10人，固定画像）。
- 时段系数（24小时）与星期系数（7天）。
- 简化购买决策模型（匹配度 + 价格 + 随机扰动）。
- 订单生成（主表 + 明细）与日志记录。

### 2.2 本期不包含
- 复杂促销（满减、优惠券联动）。
- 复购生命周期模型。
- 退款/退货复杂规则。
- 竞品博弈与广告竞价。

## 3. 核心思路
与其“随机生成订单”，改为“随机激活买家 + 买家做决策”：
1. 每个模拟时段先计算活跃买家数量。
2. 从买家池中抽样出活跃买家。
3. 每位买家只看自己偏好的商品候选。
4. 对候选商品打分并判断是否下单。
5. 下单成功则落库订单。

## 4. 买家池方案（先10人）
建议先做 10 个人物，每个画像固定，方便调参和演示。

每个买家字段：
- buyer_code：买家编号（如 B001）
- nickname：昵称
- background：人物背景（一句话）
- preferred_categories：偏好类目（可多选）
- budget_min / budget_max：可接受价格区间
- price_sensitivity：价格敏感度（0~1）
- quality_sensitivity：内容质量敏感度（0~1）
- delivery_sensitivity：发货时效敏感度（0~1）
- impulse_factor：冲动消费系数（0~1）
- active_hours：活跃时段（如 [12,13,20,21,22]）
- weekly_activity：周活跃偏好（工作日/周末）

> 可扩展建议（后续）：
> 先保留“10个人物模板”，后续用模板实例化成 50~200 个买家，既保持解释性又提升样本量。

## 5. 时段与周期波动
定义两个系数：
- hour_factor[0..23]：每小时流量系数（例如 20:00-23:00 较高）
- weekday_factor[1..7]：周内系数（周末略高）

某时段活跃买家数：
`active_count = base_active * hour_factor * weekday_factor * noise(0.9~1.1)`

其中：
- base_active 可先按 2~8（每小时）设置
- 最终 `active_count` 取整数并限制在 [0, buyer_pool_size]

## 6. 买家决策规则（MVP）
单买家对单商品打分：

`score = category_match + price_match + quality_bonus + stock_bonus + random_noise`

建议规则：
- category_match：
  - 偏好类目命中 +0.4
  - 非偏好类目 +0.0
- price_match：
  - 商品价格落在预算区间 +0.3
  - 超出预算按超出比例衰减至 -0.2
- quality_bonus：
  - quality_status = 内容合格 +0.15
  - 内容待完善 +0
- stock_bonus：
  - stock_available > 0 +0.1
  - 否则不可下单
- random_noise：[-0.1, +0.1]

下单阈值：
- `score >= 0.55` 才进入下单概率计算
- 下单概率：`p = min(0.85, max(0.05, score))`
- 通过伯努利采样后生成订单

## 7. 订单生成流程
1. 输入：run_id、当前模拟时间。
2. 读取该 run 下已发布商品（status=live，库存>0）。
3. 计算 active_count 并抽取活跃买家。
4. 每个买家：
   - 过滤候选商品（偏好类目优先，最多取前 N 个）。
   - 打分 + 概率采样。
   - 命中则创建订单（1~2 件随机数量，受 min_purchase_qty 约束）。
5. 写入订单表、订单明细表，扣减库存（若启用）。
6. 写入生成日志（本小时激活人数、成功下单数、失败原因统计）。

## 8. 数据模型（新增）
建议新增2张表：

### 8.1 shopee_sim_buyers（模拟买家池）
- id
- run_id
- user_id
- buyer_code
- nickname
- background
- preferred_categories_json
- budget_min
- budget_max
- price_sensitivity
- quality_sensitivity
- delivery_sensitivity
- impulse_factor
- active_hours_json
- weekly_activity_json
- is_active
- created_at / updated_at

### 8.2 shopee_order_generation_logs（订单生成日志）
- id
- run_id
- user_id
- tick_time（按小时或按批次）
- active_buyer_count
- candidate_product_count
- generated_order_count
- skipped_no_live_products
- skipped_no_stock
- debug_payload_json（可选）
- created_at

> 说明：字段和表都需按项目约定写表注释/字段注释。

## 9. 接口与任务建议
### 9.1 初始化买家池
- `POST /shopee/runs/{run_id}/sim-buyers/init`
- 行为：为该 run 生成10个默认人物（幂等）

### 9.2 手动触发订单生成（调试）
- `POST /shopee/runs/{run_id}/orders/simulate`
- 参数：`tick_time`（可选）
- 返回：本次生成的订单数量与摘要

### 9.3 自动任务（后续）
- 可在游戏tick中每小时调用一次 simulate

## 10. 验收标准（MVP）
- 发布商品后，手动触发 simulate 能生成订单。
- 不同时段触发，订单量有明显差异（晚高峰 > 凌晨）。
- 不同类目/价格的商品，订单命中率有区分。
- 订单可在“我的订单”中看到，字段完整。
- 生成日志可追溯（本次激活人数、生成订单数）。

## 11. 参数初始建议
- 买家数：10
- 每小时基础活跃：4
- 晚高峰 hour_factor：1.6
- 凌晨 hour_factor：0.4
- 周末 weekday_factor：1.2
- 默认下单阈值：0.55

## 12. 迭代路线
- V1（本期）：10人物 + 时段波动 + 基础决策
- V2：模板实例化（10模板扩展到100买家）
- V3：复购、售后、活动与广告联动

## 13. 最终下单概率（P_final）计算规范
为保证模型可解释、可调参、可扩展，MVP 按漏斗拆成 5 个概率项：

`P_final(i,u,t) = clamp(P_exposure(i,t) * P_active(u,t) * P_click(u,i,t) * P_convert(u,i,t) * P_compete(i,t), 0, 0.95)`

- i：商品
- u：买家
- t：时段（建议按小时）

### 13.1 P_exposure（曝光概率，商品侧）
反映商品被平台流量分发并被看到的概率。

`Score_exposure = 0.20*title_score + 0.20*category_score + 0.20*price_band_score + 0.15*stock_score + 0.15*media_score + 0.10*freshness_score`

`P_exposure = clamp(0.05 + 0.60*Score_exposure, 0.01, 0.75)`

子项说明（0~1）：
- title_score：标题质量（长度、关键词覆盖）
- category_score：类目准确度
- price_band_score：价格是否落在类目合理价格带
- stock_score：库存充足度
- media_score：图片/视频完整度
- freshness_score：上新加权（新发布短期加分）

### 13.2 P_active（活跃概率，买家+时段）
反映买家在当前时段是否在逛平台。

`P_active = clamp(base_active_rate * hour_factor[hour] * weekday_factor[weekday] * holiday_factor * persona_activity_multiplier, 0.01, 0.95)`

参数来源：
- base_active_rate：人物基础活跃率
- hour_factor：24 小时时段因子
- weekday_factor：周内因子
- holiday_factor：节假日因子（MVP 可先固定 1）
- persona_activity_multiplier：人物活跃偏好

### 13.3 P_click（点击概率，买家与商品匹配）
反映“看到后是否点进详情”。

`Score_click = 0.35*category_pref_match + 0.25*brand_pref_match + 0.25*price_accept_match + 0.15*visual_attract_score`

`P_click = clamp(0.02 + 0.50*Score_click, 0.01, 0.70)`

子项说明（0~1）：
- category_pref_match：类目偏好匹配
- brand_pref_match：品牌偏好匹配
- price_accept_match：人物价格带接受度
- visual_attract_score：视觉吸引（主图、视频等）

### 13.4 P_convert（转化概率，详情到下单）
反映“点进后是否最终下单”。

`Score_convert = 0.25*shipping_fee_score + 0.20*shipping_time_score + 0.20*stock_confidence_score + 0.15*min_purchase_score + 0.10*sku_usability_score + 0.10*trust_score`

`P_convert = clamp(0.01 + 0.45*Score_convert, 0.005, 0.60)`

子项说明（0~1）：
- shipping_fee_score：运费友好度
- shipping_time_score：时效友好度
- stock_confidence_score：库存稳定性
- min_purchase_score：起购量合理性
- sku_usability_score：SKU 选择可用性
- trust_score：信任信号（MVP 可先用固定基线）

### 13.5 P_compete（竞争修正）
- 单机单人运营阶段：`P_compete = 1`
- 多玩家阶段（同类候选池归一化）：

`attract_i = w1*price_score + w2*quality_score + w3*delivery_score + w4*brand_score`

`P_compete_i = attract_i / Σ(attract_j)`

说明：后续引入多玩家同品类上架后，`P_compete` 用于分流曝光与转化机会。

### 13.6 示例
假设某时段：
- P_exposure = 0.35
- P_active = 0.40
- P_click = 0.25
- P_convert = 0.30
- P_compete = 1（单机）

则：

`P_final = 0.35 * 0.40 * 0.25 * 0.30 * 1 = 0.0105`

即该买家在该时段对该商品下单概率约为 1.05%。

若该时段活跃买家数为 100，则期望订单数约：

`ExpectedOrders = 100 * 0.0105 = 1.05`

### 13.7 实施建议（MVP）
- 先固定权重和 clamp 区间，避免过早过拟合。
- 每次 simulate 记录各概率项均值到 `shopee_order_generation_logs.debug_payload_json`，便于回放与调参。
- 后续多玩家上线时仅替换 `P_compete` 逻辑，其余模块复用。

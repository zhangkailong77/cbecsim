# 17-Shopee商品多模态内容质量评分设计

## 1. 目标
- 为 Shopee 商品建立“可解释、可配置、可降级”的内容质量评分体系。
- 评分覆盖文案、图片质量、图文一致性，输出统一 `quality_status` 与改进建议。
- 支持后端通过 `.env` 全局切换评分提供方（API 服务或本地 Ollama）。
- 评分结果用于：
  - `我的产品` 列表展示内容质量状态与分数；
  - 后续订单模拟中的质量因子（替代当前静态质量文案）。

## 2. 范围与非范围
### 2.1 本次范围
- 新增质量评分配置、评分规则、评分结果落库与查询接口。
- 新增“规则引擎 + 视觉模型 + 文本模型”的融合评分流程。
- 新增异步评分任务（发布后触发、编辑关键字段后重评）。
- 前端展示“分数 + 状态 + 扣分原因 + 优化建议”。

### 2.2 非范围
- 不做自动改写文案/自动修图（仅给建议）。
- 不做跨语言自动翻译评分（本期聚焦中文/混合电商文案）。
- 不做全平台（Lazada/TikTok）复用，仅 Shopee 模块先落地。

## 3. 设计原则
- 可解释优先：评分必须输出分项与原因，禁止黑盒单分。
- 稳定优先：模型不可用时自动降级到规则评分，业务不中断。
- 可追踪优先：保存评分版本、模型、prompt_hash，支持回放与审计。
- 成本可控：异步执行 + 缓存命中 + 内容未变更不重评。

## 4. 评分流程
1. 玩家发布商品或修改关键字段（标题、类目、描述、图片、变体）后触发评分任务。
2. 规则引擎先计算“硬规则分”（本地稳定、低成本）。
3. 若开启模型评分：
   - 视觉模型评估图片质量；
   - 文本模型评估标题/描述质量；
   - 融合模型评估图文一致性（可与文本模型同模型不同 prompt）。
4. 融合器按权重计算总分并映射 `quality_status`。
5. 将评分结果写入数据库，并更新 listing 的摘要字段。
6. 前端查询商品列表/详情时展示评分结果。

## 5. 评分维度与权重（v1）
总分 100 分，默认权重如下（可配置）：
- `rule_score`（规则分）：30%
- `vision_score`（视觉图像分）：35%
- `text_score`（文案分）：20%
- `consistency_score`（图文一致性分）：15%

建议阈值：
- `0 ~ 59`: `内容待完善`
- `60 ~ 84`: `内容合格`
- `85 ~ 100`: `内容优秀`

## 6. 各维度评分规则
### 6.1 规则分（rule_score，0~100）
规则分由硬规则累计，默认基线 100，逐项扣分（最低 0）：
- 图片数量不足（<3）：每缺 1 张扣 8 分（最多扣 24）。
- 主图分辨率不足（短边 < 800）：扣 12 分。
- 标题过短（<20 字）或过长（>120 字）：扣 8 分。
- 未选择有效类目：扣 20 分。
- 无描述或描述 <30 字：扣 10 分。
- 变体缺 SKU/价格/库存任一关键字段：每个缺陷变体扣 3 分（最多扣 18）。
- 价格异常（<=0 或超类目合理区间）：扣 10 分。

### 6.2 视觉图像分（vision_score，0~100）
视觉模型返回结构化评分（每项 0~100，再加权）：
- 清晰度（blur/noise）：25%
- 主体完整度（是否遮挡、裁切）：20%
- 构图与主体突出（居中、可识别）：20%
- 背景与干净度（杂乱程度）：15%
- 违规视觉元素（大水印、联系方式、二维码等）：20%

### 6.3 文案分（text_score，0~100）
文本模型返回结构化评分：
- 标题信息密度（品类/规格/核心卖点）：35%
- 描述完整性（材质、功效、使用方式、注意事项）：35%
- 可读性与电商表达（非堆词、非乱码）：20%
- 合规性（夸张词、违禁承诺）：10%

### 6.4 图文一致性分（consistency_score，0~100）
模型判断标题/描述/类目与图片是否一致：
- 标题与图片主体一致：40%
- 变体信息与图片一致（颜色/型号）：35%
- 类目与图片语义一致：25%

## 7. `.env` 配置设计（后端全局）
```env
# 总开关
QUALITY_SCORER_ENABLED=true
QUALITY_SCORER_VERSION=v1

# 提供方：openai / ollama / none
QUALITY_SCORER_PROVIDER=openai
QUALITY_SCORER_BASE_URL=
QUALITY_SCORER_API_KEY=

# 模型配置
QUALITY_SCORER_TEXT_MODEL=gpt-4.1-mini
QUALITY_SCORER_VISION_MODEL=gpt-4.1-mini
QUALITY_SCORER_VISION_ENABLED=true

# 超时与重试
QUALITY_SCORER_TIMEOUT_MS=6000
QUALITY_SCORER_MAX_RETRIES=1

# 权重（总和建议=1）
QUALITY_WEIGHT_RULE=0.30
QUALITY_WEIGHT_VISION=0.35
QUALITY_WEIGHT_TEXT=0.20
QUALITY_WEIGHT_CONSISTENCY=0.15

# 阈值
QUALITY_THRESHOLD_GOOD=60
QUALITY_THRESHOLD_EXCELLENT=85
```

说明：
- `provider=none` 时只跑规则分。
- `provider=ollama` 时使用本地模型服务，`API_KEY` 可空。
- 若视觉模型不可用且 `VISION_ENABLED=true`，自动降级并记录原因。

## 8. 数据模型设计
### 8.1 新增表：`shopee_listing_quality_scores`
用途：存储每次评分快照，支持追踪与回放。

建议字段：
- `id` bigint PK
- `listing_id` bigint（索引）
- `run_id` bigint（索引）
- `user_id` bigint（索引）
- `score_version` varchar(32)（如 `v1`）
- `provider` varchar(32)
- `text_model` varchar(128)
- `vision_model` varchar(128)
- `prompt_hash` varchar(64)
- `rule_score` int
- `vision_score` int
- `text_score` int
- `consistency_score` int
- `total_score` int
- `quality_status` varchar(32)
- `reasons_json` json（扣分原因）
- `suggestions_json` json（优化建议）
- `raw_result_json` json（模型原始结构化响应）
- `is_latest` tinyint(1)
- `created_at` datetime

### 8.2 现有表扩展：`shopee_listings`
新增冗余字段（便于列表快速查询）：
- `quality_total_score` int
- `quality_status` varchar(32)（已存在则复用）
- `quality_scored_at` datetime
- `quality_score_version` varchar(32)

## 9. 接口设计
### 9.1 触发评分（内部）
- 发布成功后异步投递任务：`score_listing_quality(listing_id)`。
- 编辑关键字段后异步重评。

### 9.2 手动重评（运营/调试）
- `POST /shopee/runs/{run_id}/listings/{listing_id}/quality/recompute`
- 返回：任务已受理 + 当前状态。

### 9.3 查询评分详情
- `GET /shopee/runs/{run_id}/listings/{listing_id}/quality`
- 返回：
  - `total_score`
  - `quality_status`
  - `dimension_scores`
  - `reasons`
  - `suggestions`
  - `score_version/model/provider/scored_at`

### 9.4 列表接口增强
- `GET /shopee/runs/{run_id}/listings`
- 每行返回：
  - `quality_status`
  - `quality_total_score`
  - `quality_scored_at`

## 10. 前端展示建议
- `我的产品` 列：
  - 现状：只显示文案；
  - 目标：显示 `状态 + 分数`（如 `内容合格 72`）。
- 点击“提升”：
  - 打开侧栏/弹窗展示分项、扣分原因、建议；
  - 支持“重新评分”按钮（调试期可见）。

## 11. 异步与性能
- 评分任务采用异步队列，接口不阻塞发布流程。
- 内容哈希（标题/描述/类目/图片URL/变体）不变时跳过重评。
- 结果缓存（Redis）用于详情接口短时加速（例如 TTL 60s）。
- 限流：同 listing 60 秒内最多触发一次重评。

## 12. 降级与容错
- 模型超时/失败：
  - 回退为规则分；
  - `quality_status` 仍可产出；
  - `reasons` 增加 `"模型不可用，已使用规则评分"`。
- 图片下载失败：
  - 视觉分以缺省分（如 50）并记录错误码；
  - 不阻断整体评分完成。

## 13. 安全与合规
- 仅发送必要字段给模型（标题、描述、类目、图片 URL），不发送用户敏感信息。
- 记录模型请求日志时做脱敏（不记录 `API_KEY`、用户隐私字段）。
- 对外部 URL 做下载白名单与大小限制，防 SSRF 与资源滥用。

## 14. 验收标准
### 14.1 功能验收
- 新发布商品 10 秒内可看到评分结果（异步完成）。
- 列表可展示状态与分数，详情可展示维度分与建议。
- 模型不可用时仍可返回规则评分结果。
- 重评接口可生效，结果版本可追踪。

### 14.2 质量验收
- 同一输入重复评分，分数波动控制在可接受范围（例如 ±5 分）。
- 典型低质量样例（少图、短标题、无描述）得分显著低于高质量样例。
- 图文明显不一致样例被 consistency 维度识别并扣分。

## 15. 实施顺序建议
1. 落地数据表与 listing 冗余字段（含注释）。
2. 完成规则引擎 v1（不依赖外部模型）。
3. 接入评分任务与查询接口。
4. 前端列表/详情接入展示。
5. 接入文本+视觉模型并启用融合评分。
6. 灰度发布：先 `provider=none`，再切 `openai/ollama`。

## 16. 风险与后续优化
- 风险：模型成本、稳定性、分数漂移。
- 优化方向：
  - 增加类目特定评分模板（美妆/3C/服饰分开评分标准）；
  - 引入人工复核样本持续校准权重；
  - 加入“评分变化解释”（本次比上次提升/下降原因）。

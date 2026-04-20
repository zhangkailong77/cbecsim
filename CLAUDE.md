# CBEC_SIM Agent Defaults

本文件用于给 Codex 提供本仓库的长期默认约束，减少每次对话重复说明。

## Global UI Rules
- 所有核心业务页面统一使用：`左上角为原点 + 等比例缩放` 适配。
- 保持统一视觉语言：蓝白主色、统一 `logo.png` 风格、统一左侧菜单栏样式。
- 新页面默认延续现有工作台/选品页的布局节奏与间距体系，不做风格漂移。

## Frontend Rules
- 技术栈：React + TypeScript。
- 目录：`frontend/src/modules/<stage-name>/` 按阶段建模块。
- 页面必须可从统一工作台进入，并保留返回工作台入口。
- 有“阶段状态/进度”的页面，优先展示状态摘要，不重复展示同一倒计时信息。
- Shopee 模块凡是需要日期选择器（日期/日期时间）时，必须优先复用 `frontend/src/modules/shopee/components/` 下现有日期组件，禁止在 Shopee 模块内重复实现新的日期选择器。

## Backend Rules
- 技术栈：FastAPI + SQLAlchemy（Python 3.12, conda env: `cbec-py312`）。
- 业务状态优先落库，不使用仅前端本地状态作为最终数据源。
- 新阶段接口按 `game/runs/{run_id}/...` 命名，保持与现有 Step02/03 风格一致。

## Database Schema Rules
- 新建数据表时必须添加表注释（table comment），明确该表业务用途。
- 新增字段时必须添加字段注释（column comment），说明字段含义与单位/枚举语义。
- 若通过迁移或初始化脚本创建/变更表结构，脚本内必须同步维护表注释与字段注释，禁止仅创建裸表结构。
- 历史表新增字段时，补齐字段注释；历史无注释表在结构变更时一并补齐表注释。

## Data Persistence Rules
- 影响经营结果的数据（资金、订单、物流、仓储、阶段状态）必须持久化到数据库。
- 前端本地缓存仅可作为临时 UI 状态，不可作为唯一真实来源。

## Upload & OSS Rules
- 所有上传能力（图片、文件、附件等）统一走 OSS（MinIO / S3 协议），禁止写入本地磁盘作为兜底。
- OSS 配置必须从数据库表 `oss_storage_configs` 读取（使用 `is_active=true` 的配置项）。
- 新增上传功能时，后端必须复用统一 OSS 上传逻辑，前端仅处理选择与预览，不直接决定存储位置。

## Docs Rules
- 每个阶段设计完成后，在 `docs/设计文档/` 新增对应文档（编号递增）。
- 文档至少包含：目标、流程、规则、数据模型、接口、验收标准。
- 新建并维护统一进度台账：`docs/当前进度.md`。
- 每次开发或设计完成一个模块/子功能后，必须立即同步更新 `docs/当前进度.md`（至少更新：完成内容、当前阶段、下一步待办）。

## Run Commands (macOS)
- 一键启动：`./start-dev.sh`
- 前端：`cd frontend && npm run dev`
- 后端：`conda activate cbec-py312 && cd backend/apps/api-gateway && uvicorn app.main:app --host 0.0.0.0 --reload`

## Redis Regression Check
- Redis 订单缓存回归检查命令（本地开发）：
  - `cd backend/apps/api-gateway/scripts && python verify_redis_orders_cache.py --username <username> --password <password> --no-flush`
- 默认要求：
  - 若涉及 `GET /shopee/runs/{run_id}/orders` 缓存逻辑、缓存失效逻辑、simulate 相关缓存行为变更，提交前必须至少执行一次上述回归脚本并确认通过。

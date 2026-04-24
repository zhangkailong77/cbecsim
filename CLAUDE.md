# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.


# CBEC_SIM Agent Defaults

本文件用于给 claude code 提供本仓库的长期默认约束，减少每次对话重复说明。

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
- 自 2026-04-21 起，凡是仓库内发生代码、文档、配置修改，必须同步更新 `docs/change-log.md`，记录修改时间、涉及文件与修改摘要；若影响业务规则、接口口径或页面行为，需写明影响范围。



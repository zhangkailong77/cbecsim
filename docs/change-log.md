# Change Log

最后更新：2026-04-21

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
- 已统一管理员“买家池总览”中部“当前游戏时刻”与右侧统一倒计时中心的时间轴口径：中部卡片优先按 `selected_run_created_at -> selected_run_end_time` 的真实跨度换算游戏时刻，不再固定按基准 7 天推导。
  - 涉及文件：`frontend/src/modules/admin/AdminBuyerPoolPage.tsx`
  - 影响范围：手动延长过的 running 对局在买家池总览中，中部“当前游戏时刻”将与右侧统一时间中心保持一致，不再提前停在旧周期。

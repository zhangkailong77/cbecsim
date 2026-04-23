# Change Log

最后更新：2026-04-22 (current_game_tick 计算修复 + max_ticks_per_request 恢复)

## 2026-04-22 (续)

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

# 16-7天对局结束与Shopee订单封盘设计

## 1. 目标
- 建立统一“对局结束”判定：当对局达到 `duration_days`（示例：7天）后，Shopee 订单域停止一切“订单演化写入”。
- 封盘后保留历史可读性：订单、物流轨迹、财务流水可继续查询。
- 历史回溯入口固定在工作台左侧菜单 `历史经营记录`（`/setup/history`），而非从“工作台总览”进入。
- 在 `/setup/history` 可查看某个历史对局总结，并可跳转各阶段页面（URL 带 `run_id`）进行全链路只读回看。
- 结束后玩家可立即新开一局，且新局数据独立（新 `run_id`，不继承旧局经营数据）。

## 2. 范围与非范围
### 2.1 本次范围
- Shopee 订单域自动演化逻辑封盘：自动模拟、自动取消、自动物流推进、自动回款补记。
- Shopee 订单域人工演化接口封盘：手动 simulate、发货、取消、物流推进等。
- 对局状态引入自然结束语义：`running -> finished`。
- 新建对局前增加到期 run 的“自动收口”兜底，避免玩家被旧 `running` 卡住。
- 工作台历史经营记录页能力补齐：
  - 仅展示 `finished` 对局；
  - 支持查看所选历史对局总结；
  - 支持携带 `run_id` 跳转 Step02~Step05 与工作台阶段页做只读回看。

### 2.2 非范围
- 不改 Step02/03/04 的业务规则与状态机本身。
- 不做历史数据批量修复脚本（另立任务）。
- 不新增复杂全局权限系统（本期以 `run_id + run.status` 闸门实现只读）。

## 3. 用户流程
1. 玩家点击左侧菜单 `历史经营记录`，进入 `/setup/history`。
2. 页面加载“该玩家历史对局列表（仅 `finished`）”，按创建时间倒序展示。
3. 玩家选择一个历史对局后，页面展示该局经营总结（资金、订单、物流、仓储、Shopee 经营结果等摘要）。
4. 玩家点击“查看阶段详情”可跳转各阶段页面，URL 带 `run_id`（如 `/u/{public_id}/intel?run_id=123`）。
5. 进入历史 `run_id` 时，全页面进入只读模式：
   - 经营动作按钮保留；
   - 点击时统一提示“历史对局仅支持回溯查看，不能继续经营操作”。

## 4. 规则
### 4.1 结束判定规则
- `run_end_time = run.created_at + timedelta(days=run.duration_days)`。
- `tick_time >= run_end_time` 判定为结束。
- 边界（`duration_days=7`）：
  - `[created_at, created_at + 7d)` 可演化；
  - `>= created_at + 7d` 封盘（第8天开始封盘）。

### 4.2 历史列表规则
- 历史经营记录页只展示 `status=finished`。
- `abandoned` 不进入历史经营记录列表（本期按你的确认排除）。

### 4.3 只读模式规则（历史 `run_id`）
- 历史 `run_id` 允许所有查询类接口读取（返回 200）。
- 历史 `run_id` 禁止所有经营演化写接口（返回 `400 + RUN_FINISHED`）。
- 前端动作按钮保留不隐藏，点击后弹统一只读提示。
- 查询接口在 `finished` 下不得触发自动写入（不补模拟、不补取消、不补物流推进、不补自动回款写入）。

### 4.4 时间口径规则
- 统一使用后端 UTC 口径判定结束。
- 业务推进以游戏时钟 `tick_time` 为准，不使用前端本地时间。

### 4.5 幂等并发规则
- `running -> finished` 更新必须幂等，重复触发无副作用。
- 并发场景以数据库条件更新保证一致性，避免状态抖动。

## 5. 接口与路由设计
### 5.1 工作台历史页接口（新增）
- `GET /game/runs/history/options`
  - 返回当前玩家历史对局列表，默认仅 `finished`。
  - 返回字段建议：`run_id/status/market/duration_days/day_index/created_at`。
- `GET /game/runs/{run_id}/history/summary`
  - 返回历史对局总结聚合（工作台可视化摘要所需字段）。

### 5.2 阶段页回溯路由（前端）
- 历史入口固定：`/u/{public_id}/setup/history`。
- 阶段回溯跳转：`/u/{public_id}/{stage}?run_id={run_id}`。
- 当 URL 存在 `run_id` 且该 run 为 `finished` 时，页面进入只读回溯模式。

### 5.3 既有查询接口（封盘后可查）
- 订单列表、订单详情、物流详情、财务总览/流水/收入保持可查，返回结构不变。
- 跳过自动演化写入逻辑。

### 5.4 既有演化写接口（封盘后拒绝）
- 封盘后统一拒绝（`400`）：
  - `POST /shopee/runs/{run_id}/orders/simulate`
  - `POST /game/admin/runs/{run_id}/orders/simulate`
  - `POST /shopee/runs/{run_id}/orders/{order_id}/ship`
  - `POST /shopee/runs/{run_id}/orders/{order_id}/cancel`
  - `POST /shopee/runs/{run_id}/orders/{order_id}/logistics/progress`
- 错误语义：
  - `code=RUN_FINISHED`
  - `message=当前对局已结束，无法继续订单演化操作`

## 6. 数据模型
- 不新增表，复用 `game_runs`：
  - `status` 使用 `finished` 作为自然结束状态。
  - `running/abandoned` 保持兼容。
- 参数约束：
  - `POST /game/runs` 的 `duration_days` 下限调整为 `7`，与玩法一致。

## 7. 验收标准
### 7.1 功能验收
- 玩家可从左侧菜单进入 `/setup/history` 查看历史经营记录。
- 历史列表仅显示 `finished` 对局。
- 选择历史对局后可看到该局总结信息。
- 可从总结页跳转到各阶段页面并携带 `run_id` 回溯查看。
- 历史回溯页动作按钮保留，点击后出现只读提示，不执行写入。
- 第8天开始不再新增订单模拟日志，不再发生自动取消/自动物流推进等演化写入。
- 封盘后查询接口返回 `200`，演化写接口返回 `400 + RUN_FINISHED`。
- 旧局结束后可成功创建新 run，且新 run 数据从 0 开始。

### 7.2 回归验收
- 第7天内原有演化行为不受影响。
- auto tick worker 对未到期 run 行为保持一致。
- 并发访问查询接口时，到期后不再引入“读触发写”锁竞争。

## 8. 实施顺序建议
1. 固化结束判定与状态迁移 helper（幂等）。
2. 完成历史列表/历史总结接口（仅 `finished`）。
3. 前端完成 `/setup/history` 页面渲染与历史 run 选择。
4. 前端完成跨阶段 `run_id` 回溯路由与只读模式提示（按钮保留）。
5. 后端全面接入“查询可读、写入拒绝”的 finished 闸门。
6. 完成自动化测试与回归验证。

## 9. 风险与约束
- 后续新增经营写入口必须接入统一 finished 闸门，否则会出现漏网写入。
- 阶段页若存在前端本地态写入副作用，需要在历史回溯模式下统一禁用。
- 若未来要把 `abandoned` 也纳入历史列表，可作为后续可选项单独评审。

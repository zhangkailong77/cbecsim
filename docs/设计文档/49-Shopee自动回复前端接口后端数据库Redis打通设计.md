# 49-Shopee 自动回复前端接口后端数据库 Redis 打通设计

> 创建日期：2026-05-11  
> 状态：V1 配置持久化已实现

## 1. 目标

为 Shopee `客户服务 -> 聊天管理 -> 自动回复` 页面接入前端接口、后端数据库与 Redis 数据闭环，使卖家可以在当前对局中配置店铺默认自动回复与离线自动回复，并为后续聊天消息模拟、买家咨询触发、客服表现统计预留稳定数据口径。

本设计基于当前已手动完成的前端页面，不调整页面布局和视觉样式：

- 页面：`frontend/src/modules/shopee/views/AutoReplySettingsView.tsx`
- 路由：`/shopee/customer-service/chat-management/auto-reply`
- 当前页面元素：顶部提示横幅、默认自动回复卡片、离线自动回复卡片、开关、编辑按钮、离线消息预览。

## 2. 范围与非范围

### 2.1 本期范围（V1）

- 前端接口接入：
  - 自动回复页加载真实配置。
  - 默认自动回复与离线自动回复开关读取后端状态。
  - 点击开关后更新后端配置。
  - 编辑入口后续可打开编辑弹窗或编辑页，本期先定义接口与数据结构。
- 后端接口：
  - 自动回复配置 bootstrap / 查询。
  - 更新默认自动回复开关与内容。
  - 更新离线自动回复开关、内容与工作时间配置。
- 数据库：
  - 新增自动回复配置表，保存影响客服回复行为的数据。
  - 表注释与字段注释必须同步维护。
- Redis：
  - 自动回复配置缓存。
  - 更新接口限流。
  - 更新成功后清理配置缓存与聊天触发缓存。
- 后续聊天模拟预留：
  - 买家发起对话时按规则判断是否触发默认自动回复。
  - 非工作时间买家发起对话时按规则判断是否触发离线自动回复。
  - 记录每个买家的触发频率，避免重复发送。

### 2.2 非范围（V1 不做）

- 不重做用户已手动完成的前端样式和布局。
- 不接入真实 Shopee Chat API。
- 不实现复杂机器人 FAQ、关键词匹配或智能客服。
- 不实现快捷回复配置；快捷回复另行设计。
- 不实现聊天消息完整收发系统；仅为后续聊天模拟定义自动回复配置来源。
- 不实现多语言模板自动翻译。
- 不实现按商品、订单状态、买家标签的细分自动回复规则。

## 3. 当前前端布局观察

`AutoReplySettingsView.tsx` 当前布局：

- 外层延续 Shopee 模块统一布局：`flex-1 overflow-y-auto bg-[#f6f6f6] px-9 py-6`。
- 内容区：`w-[1360px] max-w-full`，无左侧菜单栏。
- 顶部黄色提示横幅：
  - 默认自动回复对每个买家每 24 小时只触发一次。
  - 离线自动回复对每个买家每天只触发一次。
  - 横幅可关闭，属于前端临时 UI 状态，不需要落库。
- 默认自动回复卡片：
  - 标题“默认自动回复”。
  - 说明“开启后，此自动回复将在买家发起对话时发送一次。”
  - 店铺设置行：开关 + 编辑按钮。
- 离线自动回复卡片：
  - 标题“离线自动回复”。
  - 说明“开启后，如果在工作时间外买家发起对话，将发送此自动回复消息。”
  - 店铺设置行：开关 + 编辑按钮。
  - 下方展示离线回复内容预览。

后续接接口时应保留上述结构，只替换当前 `useState` 静态状态为后端数据源与更新行为。

## 4. 业务规则

### 4.1 自动回复类型

| 类型 | 代码 | 触发场景 | 频率限制 |
| --- | --- | --- | --- |
| 默认自动回复 | `default` | 买家发起新对话时触发 | 同一买家每 24 小时最多 1 次 |
| 离线自动回复 | `off_work` | 买家在店铺非工作时间发起对话时触发 | 同一买家每个游戏日最多 1 次 |

### 4.2 默认自动回复规则

- 默认自动回复是店铺级配置，每个 `run_id/user_id` 最多一条配置。
- 开启后，买家发起对话时自动发送配置内容。
- 同一买家 24 小时内只触发一次，避免刷屏。
- 若配置内容为空，不允许开启。
- 默认内容可由后端 bootstrap 返回一条 Shopee 风格默认文案：
  - `您好，欢迎光临本店！请问有什么可以帮您？`
- 触发时间口径使用对局游戏时间，不使用真实世界当前时间。

### 4.3 离线自动回复规则

- 离线自动回复是店铺级配置，每个 `run_id/user_id` 最多一条配置。
- 开启后，仅在当前游戏时间不属于工作时间范围时触发。
- 同一买家每个游戏日只触发一次。
- 若配置内容为空，不允许开启。
- 默认内容沿用当前前端预览文案：
  - `亲爱的买家，您的消息已收到。由于目前是非工作时间，我们暂时无法回复您。我们一上线就会立即回复您。感谢您的理解。`
- 工作时间 V1 可先使用固定配置：`09:00-18:00`，后续编辑页可开放修改。
- 工作时间按店铺本地游戏时间解释。

### 4.4 默认自动回复与离线自动回复优先级

当买家发起对话同时满足默认自动回复和离线自动回复条件时，V1 建议优先发送离线自动回复：

```text
离线自动回复 > 默认自动回复
```

原因：离线自动回复更具体，能够解释当前无法人工响应；默认自动回复作为在线或未命中离线场景的兜底欢迎语。

### 4.5 状态规则

| 状态 | 条件 |
| --- | --- |
| `enabled` | 开关开启且内容非空 |
| `disabled` | 开关关闭 |
| `invalid` | 配置内容为空、超过长度或工作时间配置非法，接口返回时提示前端不可开启 |

### 4.6 游戏时间口径

自动回复所有触发、频控和统计口径均使用当前对局游戏时间：

- 24 小时内触发一次的判断。
- 每个游戏日触发一次的判断。
- 工作时间内/外判断。
- 聊天表现统计中的自动回复计数。

前端仅展示和提交配置，不使用浏览器真实时间判断是否离线。

## 5. 数据模型设计

### 5.1 新增 ORM：`ShopeeAutoReplySetting`

建议新增表：`shopee_auto_reply_settings`。

> 数据库 Schema Rules 要求：新建表必须添加表注释，新增字段必须添加字段注释。

| 字段 | 类型 | 约束 | 注释 |
| --- | --- | --- | --- |
| `id` | Integer | PK | 自动回复配置 ID |
| `run_id` | Integer | FK `game_runs.id`, index, not null | 所属对局 ID |
| `user_id` | Integer | FK `users.id`, index, not null | 所属卖家用户 ID |
| `reply_type` | String(32) | not null | 自动回复类型：default/off_work |
| `enabled` | Boolean | not null, default false | 是否启用该自动回复 |
| `message` | Text | not null | 自动回复消息内容 |
| `work_time_enabled` | Boolean | not null, default false | 是否启用工作时间判断；默认回复可为 false，离线回复为 true |
| `work_start_time` | String(8) | nullable | 工作开始时间，格式 HH:mm，离线回复使用 |
| `work_end_time` | String(8) | nullable | 工作结束时间，格式 HH:mm，离线回复使用 |
| `timezone` | String(64) | not null, default `game_time` | 时间解释口径，V1 固定对局游戏时间 |
| `trigger_interval_minutes` | Integer | not null | 同买家触发间隔分钟数；默认回复 1440 |
| `trigger_once_per_game_day` | Boolean | not null, default false | 是否按游戏日限制每天一次；离线回复为 true |
| `sent_count` | Integer | not null, default 0 | 已触发发送次数 |
| `last_sent_game_at` | DateTime(timezone=True) | nullable | 最近一次触发的游戏时间 |
| `created_at` | DateTime(timezone=True) | not null | 创建时间 |
| `updated_at` | DateTime(timezone=True) | not null | 更新时间 |

建议索引：

```python
Index("ix_shopee_auto_reply_settings_run_user_type", "run_id", "user_id", "reply_type", unique=True)
Index("ix_shopee_auto_reply_settings_run_user_enabled", "run_id", "user_id", "enabled")
```

### 5.2 新增 ORM：`ShopeeAutoReplyTriggerLog`（后续聊天模拟预留）

建议新增表：`shopee_auto_reply_trigger_logs`，用于频控与调试。

| 字段 | 类型 | 约束 | 注释 |
| --- | --- | --- | --- |
| `id` | Integer | PK | 自动回复触发记录 ID |
| `run_id` | Integer | FK `game_runs.id`, index, not null | 所属对局 ID |
| `user_id` | Integer | FK `users.id`, index, not null | 所属卖家用户 ID |
| `setting_id` | Integer | FK `shopee_auto_reply_settings.id`, index, not null | 命中的自动回复配置 ID |
| `reply_type` | String(32) | not null | 自动回复类型：default/off_work |
| `buyer_name` | String(255) | index, not null | 触发自动回复的买家名称 |
| `buyer_message_snapshot` | Text | nullable | 触发时买家消息快照 |
| `reply_message_snapshot` | Text | not null | 发送的自动回复内容快照 |
| `trigger_game_at` | DateTime(timezone=True) | index, not null | 触发游戏时间 |
| `trigger_game_day` | Integer | index, not null | 触发时对局游戏日序号 |
| `dedupe_key` | String(255) | unique, not null | 频控去重键 |
| `created_at` | DateTime(timezone=True) | not null | 创建时间 |

建议索引：

```python
Index("ix_shopee_auto_reply_logs_buyer_type_time", "run_id", "user_id", "buyer_name", "reply_type", "trigger_game_at")
Index("ix_shopee_auto_reply_logs_buyer_type_day", "run_id", "user_id", "buyer_name", "reply_type", "trigger_game_day")
```

V1 如果只先实现配置页，可暂不创建触发表，但设计中保留，便于后续聊天模拟接入。

## 6. 后端接口设计

接口统一挂在现有 Shopee 路由下，沿用鉴权与 `run_id` 权限校验。

### 6.1 查询自动回复配置

```http
GET /shopee/runs/{run_id}/customer-service/auto-replies
```

用途：页面初始化加载默认自动回复与离线自动回复配置。

响应示例：

```json
{
  "default_reply": {
    "id": 1,
    "reply_type": "default",
    "enabled": false,
    "message": "您好，欢迎光临本店！请问有什么可以帮您？",
    "trigger_interval_minutes": 1440,
    "status": "disabled"
  },
  "off_work_reply": {
    "id": 2,
    "reply_type": "off_work",
    "enabled": false,
    "message": "亲爱的买家，您的消息已收到。由于目前是非工作时间，我们暂时无法回复您。我们一上线就会立即回复您。感谢您的理解。",
    "work_time_enabled": true,
    "work_start_time": "09:00",
    "work_end_time": "18:00",
    "trigger_once_per_game_day": true,
    "status": "disabled"
  },
  "rules": {
    "max_message_length": 500,
    "default_reply_interval_minutes": 1440,
    "off_work_once_per_game_day": true
  }
}
```

后端行为：

- 若当前对局尚无配置，自动创建默认配置或返回默认值并在首次更新时落库。
- 建议 V1 查询时即确保两条配置存在，便于前端直接按 ID 更新。
- 返回数据从 Redis 读取；缓存未命中则查库并回填。

### 6.2 更新某类自动回复配置

```http
PUT /shopee/runs/{run_id}/customer-service/auto-replies/{reply_type}
```

`reply_type` 可选：`default`、`off_work`。

请求示例：

```json
{
  "enabled": true,
  "message": "您好，欢迎光临本店！请问有什么可以帮您？",
  "work_start_time": "09:00",
  "work_end_time": "18:00"
}
```

校验规则：

- `reply_type` 必须为 `default` 或 `off_work`。
- `message` 去除首尾空白后不能为空。
- `message` 最多 500 字。
- `enabled=true` 时必须有合法 `message`。
- `off_work` 如提交工作时间，必须为 `HH:mm` 且开始结束时间不能相同。
- 历史对局回溯模式下禁止写操作。

响应示例：

```json
{
  "setting": {
    "id": 2,
    "reply_type": "off_work",
    "enabled": true,
    "message": "亲爱的买家，您的消息已收到。由于目前是非工作时间，我们暂时无法回复您。我们一上线就会立即回复您。感谢您的理解。",
    "work_time_enabled": true,
    "work_start_time": "09:00",
    "work_end_time": "18:00",
    "trigger_once_per_game_day": true,
    "status": "enabled"
  }
}
```

后端行为：

- 在事务中 upsert 对应 `run_id/user_id/reply_type` 配置。
- 更新 `updated_at`。
- 写入后清理 Redis 配置缓存。
- 若后续聊天模拟已接入，还需清理自动回复触发候选缓存。

### 6.3 切换自动回复开关（可选轻量接口）

若前端开关只需要切换状态，可提供轻量 PATCH：

```http
PATCH /shopee/runs/{run_id}/customer-service/auto-replies/{reply_type}/enabled
```

请求：

```json
{
  "enabled": true
}
```

规则：

- 开启前必须校验当前配置内容非空且合法。
- 关闭不清空消息内容。
- 成功后返回完整 setting。

V1 可以不单独实现 PATCH，直接复用 `PUT` 更新完整配置；若前端只传 `enabled`，后端读取当前 message 后校验并更新。

## 7. 前端接入设计

### 7.1 页面数据状态

`AutoReplySettingsView.tsx` 建议新增 props：

```ts
interface AutoReplySettingsViewProps {
  runId: number | null;
  readOnly?: boolean;
}
```

核心状态：

```ts
const [data, setData] = useState<AutoReplySettingsResponse | null>(null);
const [loading, setLoading] = useState(false);
const [error, setError] = useState('');
const [savingType, setSavingType] = useState<'default' | 'off_work' | null>(null);
```

### 7.2 初始化加载

- `runId` 为空时展示空配置或错误提示。
- 有 `runId` 时请求：`GET /shopee/runs/{runId}/customer-service/auto-replies`。
- 加载期间可保留页面骨架，只禁用开关。
- 接口失败时在页面顶部展示错误提示，不改变现有卡片布局。

### 7.3 开关更新

默认自动回复开关：

- 点击开关后调用 `PUT /auto-replies/default` 或 PATCH enabled。
- 请求成功后用响应覆盖本地状态。
- 请求失败则恢复原状态并展示错误。

离线自动回复开关：

- 点击开关后调用 `PUT /auto-replies/off_work` 或 PATCH enabled。
- 保留当前消息与工作时间配置。

### 7.4 编辑入口

当前页面只有编辑图标，V1 可选择两种落地方式：

1. 页面内弹窗编辑消息内容与工作时间。
2. 后续新增独立编辑页。

本设计建议先做弹窗，减少路由数量：

- 默认自动回复编辑：只编辑 message。
- 离线自动回复编辑：编辑 message、work_start_time、work_end_time。
- 保存时复用 `PUT` 接口。

### 7.5 只读模式

历史对局回溯模式下：

- 页面可以加载配置。
- 开关、编辑保存按钮禁用。
- 点击写操作时提示“历史对局仅支持回溯查看，不能修改自动回复配置。”

## 8. Redis 设计

### 8.1 Key 设计

| Key | 类型 | TTL | 用途 |
| --- | --- | --- | --- |
| `shopee:auto_reply:settings:{run_id}:{user_id}` | String JSON | 300s | 自动回复页配置缓存 |
| `shopee:auto_reply:trigger:{run_id}:{user_id}:{buyer}:{reply_type}` | String | 按规则过期 | 买家触发频控缓存，后续聊天模拟使用 |
| `shopee:auto_reply:ratelimit:update:{run_id}:{user_id}` | String/Counter | 60s | 更新接口限流 |

### 8.2 缓存读写

查询配置：

1. 先读 `shopee:auto_reply:settings:{run_id}:{user_id}`。
2. 命中直接返回。
3. 未命中查库，若配置不存在则创建默认配置或组装默认响应。
4. 写 Redis，TTL 300 秒。

更新配置：

1. 校验限流 key。
2. 写数据库。
3. 删除 `shopee:auto_reply:settings:{run_id}:{user_id}`。
4. 如后续聊天模拟接入，删除或更新相关 trigger 候选缓存。

### 8.3 频控缓存预留

默认自动回复：

```text
shopee:auto_reply:trigger:{run_id}:{user_id}:{buyer}:default
TTL = 24 小时对应的游戏时间映射窗口，V1 可先按真实秒 86400 缓存兜底，但最终判断必须以数据库 trigger_game_at + 游戏时间为准。
```

离线自动回复：

```text
shopee:auto_reply:trigger:{run_id}:{user_id}:{buyer}:off_work:{game_day}
TTL = 当前游戏日剩余时长或 24 小时兜底。
```

注意：Redis 只做加速，数据库触发日志才是最终频控依据，避免 Redis 丢失导致重复触发。

## 9. 与聊天模拟和统计的关系

### 9.1 聊天触发预留

后续如果订单模拟或买家行为模拟产生咨询事件：

1. 读取当前 `run_id/user_id` 的自动回复配置。
2. 按当前游戏时间判断是否非工作时间。
3. 按优先级选择 `off_work` 或 `default`。
4. 查询 Redis/数据库触发记录判断频控。
5. 写入聊天消息记录与 `shopee_auto_reply_trigger_logs`。
6. 回写配置 `sent_count`、`last_sent_game_at`。

### 9.2 聊天表现统计预留

聊天管理页后续可展示：

- 自动回复发送次数。
- 自动回复覆盖买家数。
- 默认自动回复发送次数。
- 离线自动回复发送次数。
- 自动回复后买家继续咨询率。

本期仅为统计预留字段，不实现统计页面。

## 10. 初始化与历史数据处理

### 10.1 新对局默认配置

首次进入自动回复页时，后端应确保存在两条配置：

| 类型 | 默认 enabled | 默认 message |
| --- | --- | --- |
| `default` | false | `您好，欢迎光临本店！请问有什么可以帮您？` |
| `off_work` | false | 当前前端预览文案 |

### 10.2 历史库补表

实现时需在 `db.py` 的历史库保障逻辑中：

- 创建 `shopee_auto_reply_settings` 表。
- 创建 `shopee_auto_reply_trigger_logs` 表（如 V1 同步实现预留表）。
- 补齐表注释与字段注释。
- 添加唯一索引与查询索引。

## 11. 验收标准

### 11.1 设计验收

- 文档覆盖目标、范围、业务规则、数据模型、接口、前端接入、Redis、验收标准。
- 明确不改当前前端布局。
- 明确游戏时间口径。
- 明确数据库表与字段注释要求。

### 11.2 前端验收（后续实现）

- 打开 `/shopee/customer-service/chat-management/auto-reply`，页面从后端加载配置。
- 默认自动回复开关状态来自接口。
- 离线自动回复开关与消息预览来自接口。
- 点击开关后状态落库，刷新页面后保持一致。
- 接口失败时展示错误，不破坏原页面布局。
- 历史对局回溯模式禁用写操作。

### 11.3 后端验收（后续实现）

- `GET /shopee/runs/{run_id}/customer-service/auto-replies` 返回两类配置。
- `PUT /shopee/runs/{run_id}/customer-service/auto-replies/default` 可更新默认自动回复。
- `PUT /shopee/runs/{run_id}/customer-service/auto-replies/off_work` 可更新离线自动回复。
- 非法 message、非法工作时间、无权限 run_id 返回明确错误。
- 更新成功后数据库记录正确，Redis 配置缓存失效。

### 11.4 Redis 验收（后续实现）

- 首次查询未命中 Redis 时查库并回填缓存。
- 再次查询命中缓存。
- 更新配置后旧缓存被删除。
- 更新接口有限流保护。

## 12. 后续扩展

- 自动回复编辑弹窗或独立编辑页。
- 工作时间按星期配置。
- 多语言自动回复模板。
- 按关键词或商品分类触发不同自动回复。
- FAQ 助手与自动回复联动。
- 聊天消息真实落库后，将自动回复作为系统消息插入聊天记录。

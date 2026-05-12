# 50-Shopee 快捷回复前端接口后端数据库 Redis 打通设计

> 创建日期：2026-05-11  
> 状态：V1 配置持久化、编辑、删除、移动排序已实现

## 1. 目标

为 Shopee `客户服务 -> 聊天管理 -> 快捷回复` 页面与 `新建快捷回复` 页面接入前端接口、后端数据库与 Redis 数据闭环，使卖家可以在当前对局中维护快捷回复分组、快捷回复消息、提示开关与分组启用状态。

本设计基于当前已手动完成的前端页面，不调整页面布局和视觉样式：

- 快捷回复列表页：`frontend/src/modules/shopee/views/QuickReplySettingsView.tsx`
- 快捷回复创建页：`frontend/src/modules/shopee/views/QuickReplyCreateView.tsx`
- 列表路由：`/shopee/customer-service/chat-management/quick-reply`
- 创建路由：`/shopee/customer-service/chat-management/quick-reply/create`
- 当前列表页元素：自动显示消息提示开关、我的快捷回复卡片、新建快捷回复按钮、默认分组、分组开关、编辑/删除/拖拽图标、快捷回复消息列表。
- 当前创建页元素：分组名称、快捷回复消息列表、标签、添加消息、从模板添加消息弹窗、保存/取消按钮。

## 2. 范围与非范围

### 2.1 本期范围（V1）

- 前端接口接入：
  - 快捷回复列表页加载真实配置与分组列表。
  - 自动显示消息提示开关读取与更新后端状态。
  - 分组启用开关读取与更新后端状态。
  - 新建快捷回复页提交分组名称与消息列表。
  - 创建成功后返回快捷回复列表页并刷新数据。
  - 创建页“从模板添加消息”继续保留现有前端模板交互，本期模板可先由前端静态数据提供。
- 后端接口：
  - 快捷回复配置 bootstrap / 查询。
  - 快捷回复分组列表查询。
  - 创建快捷回复分组与消息。
  - 更新提示开关。
  - 更新分组启用状态。
  - 删除分组或消息、编辑分组/消息、拖拽排序可先定义接口，V1 可按优先级实现创建与开关保存。
- 数据库：
  - 新增快捷回复用户配置表。
  - 新增快捷回复分组表。
  - 新增快捷回复消息表。
  - 表注释与字段注释必须同步维护。
- Redis：
  - 快捷回复列表缓存。
  - 快捷回复配置缓存。
  - 创建/更新接口限流。
  - 写操作成功后清理配置、列表缓存。

### 2.2 非范围（V1 不做）

- 不重做用户已手动完成的前端样式和布局。
- 不接入真实 Shopee Chat API。
- 不实现客服聊天输入框中的实时推荐弹窗，只保存“自动显示消息提示”开关。
- 不实现复杂关键词匹配或智能推荐算法。
- 不实现跨店铺共享快捷回复。
- 不实现系统级模板后台维护；创建页模板本期可继续使用前端静态数据。
- 不实现真实客服消息发送，仅维护快捷回复配置数据。

## 3. 当前前端布局观察

### 3.1 快捷回复列表页

`QuickReplySettingsView.tsx` 当前布局：

- 外层：`flex-1 overflow-y-auto bg-[#f6f6f6] px-9 py-6 custom-scrollbar text-[#333]`。
- 内容区：`mx-auto w-[1360px] max-w-full flex flex-col gap-5`，无左侧菜单栏。
- 顶部卡片：
  - 标题“自动显示消息提示”。
  - 描述“开启后，在输入时会自动检索并弹出相关的快捷回复提示。”
  - 右侧开关。
- 主卡片：
  - 标题“我的快捷回复 (1/25)”。
  - 描述“快捷回复允许您为常用消息创建模板，提高回复效率。”
  - 右上角“新建快捷回复”按钮。
  - 分组 header：展开/收起、分组名称、分组启用开关、编辑、删除、拖拽排序。
  - 展开后展示快捷回复消息列表。

后续接接口时应保留当前结构，只替换静态 `mockShortcuts`、本地开关状态为后端数据源与更新行为。

### 3.2 快捷回复创建页

`QuickReplyCreateView.tsx` 当前布局：

- 外层：`flex-1 overflow-y-auto bg-[#f6f6f6] px-9 py-6 custom-scrollbar text-[#333] relative`。
- 内容区：`mx-auto w-[1360px] max-w-full flex flex-col gap-4`，无左侧菜单栏。
- 主白色表单卡片：
  - 标题“创建个人快捷回复”。
  - 分组名称输入框。
  - 快捷回复消息区域。
  - 支持添加消息、从模板添加消息。
  - 消息字段包含：消息内容、标签。
  - 消息最多 20 条，单条消息内容最多 500 字。
  - 支持拖拽排序。
- 底部操作区：取消、保存。
- 模板弹窗：通用、订单、物流、售后服务四类模板，多选后添加到消息列表。

后续接接口时应保留当前页面交互，仅增加真实保存、错误提示、保存中状态和只读禁用。

## 4. 业务规则

### 4.1 快捷回复层级

| 层级 | 说明 | V1 行为 |
| --- | --- | --- |
| 用户配置 | 当前对局卖家的快捷回复偏好 | 保存自动显示消息提示开关 |
| 分组 | 一组快捷回复消息 | 可启用/停用、展示、创建 |
| 消息 | 具体快捷回复内容 | 包含内容、标签、排序 |

### 4.2 数量限制

| 对象 | 限制 |
| --- | --- |
| 每个 `run_id/user_id` 快捷回复分组 | 最多 25 个 |
| 每个分组消息数 | 最多 20 条 |
| 分组名称长度 | 1-200 字 |
| 消息内容长度 | 1-500 字 |
| 单条消息标签数 | 最多 3 个 |
| 标签长度 | 单个最多 32 字 |

### 4.3 默认数据

首次进入快捷回复列表页时，后端应确保存在：

- 用户配置：`auto_hint_enabled=true`。
- 默认分组：`默认分组`，`enabled=true`。
- 默认分组内可写入当前前端模拟列表中的常用消息，或仅创建空分组。

V1 建议创建默认分组并写入当前页面已有的 13 条示例快捷回复，使列表页从接入初期就能展示与当前静态页面一致的数据。

### 4.4 排序规则

- 分组按 `sort_order ASC, id ASC` 排序。
- 分组内消息按 `sort_order ASC, id ASC` 排序。
- 创建分组时默认追加到最后。
- 创建消息时按前端提交顺序写入 `sort_order`。

### 4.5 状态规则

| 状态 | 条件 |
| --- | --- |
| `enabled` | 分组启用，可在聊天输入中被候选推荐或手动使用 |
| `disabled` | 分组停用，列表仍展示但聊天侧不作为可用快捷回复 |
| `invalid` | 分组名称为空、消息为空、消息超长、标签超限等 |

### 4.6 只读模式

历史对局回溯模式下：

- 列表页可加载快捷回复配置和分组。
- 创建页不允许保存。
- 自动提示开关、分组开关、编辑、删除、拖拽和保存按钮禁用。
- 点击写操作时提示“历史对局仅支持回溯查看，不能修改快捷回复配置。”

## 5. 数据模型设计

### 5.1 新增 ORM：`ShopeeQuickReplyPreference`

建议新增表：`shopee_quick_reply_preferences`。

| 字段 | 类型 | 约束 | 注释 |
| --- | --- | --- | --- |
| `id` | Integer | PK | 快捷回复偏好 ID |
| `run_id` | Integer | FK `game_runs.id`, index, not null | 所属对局 ID |
| `user_id` | Integer | FK `users.id`, index, not null | 所属卖家用户 ID |
| `auto_hint_enabled` | Boolean | not null, default true | 是否开启输入时自动显示快捷回复提示 |
| `created_at` | DateTime(timezone=True) | not null | 创建时间 |
| `updated_at` | DateTime(timezone=True) | not null | 更新时间 |

建议约束与索引：

```python
UniqueConstraint("run_id", "user_id", name="uq_shopee_quick_reply_preferences_run_user")
```

### 5.2 新增 ORM：`ShopeeQuickReplyGroup`

建议新增表：`shopee_quick_reply_groups`。

| 字段 | 类型 | 约束 | 注释 |
| --- | --- | --- | --- |
| `id` | Integer | PK | 快捷回复分组 ID |
| `run_id` | Integer | FK `game_runs.id`, index, not null | 所属对局 ID |
| `user_id` | Integer | FK `users.id`, index, not null | 所属卖家用户 ID |
| `group_name` | String(200) | not null | 快捷回复分组名称 |
| `enabled` | Boolean | not null, default true | 分组是否启用 |
| `sort_order` | Integer | not null, default 0 | 分组排序值 |
| `message_count` | Integer | not null, default 0 | 分组内消息数量冗余计数 |
| `created_at` | DateTime(timezone=True) | not null | 创建时间 |
| `updated_at` | DateTime(timezone=True) | not null | 更新时间 |

建议索引：

```python
Index("ix_shopee_quick_reply_groups_run_user_sort", "run_id", "user_id", "sort_order")
Index("ix_shopee_quick_reply_groups_run_user_enabled", "run_id", "user_id", "enabled")
```

### 5.3 新增 ORM：`ShopeeQuickReplyMessage`

建议新增表：`shopee_quick_reply_messages`。

| 字段 | 类型 | 约束 | 注释 |
| --- | --- | --- | --- |
| `id` | Integer | PK | 快捷回复消息 ID |
| `group_id` | Integer | FK `shopee_quick_reply_groups.id`, index, not null | 所属快捷回复分组 ID |
| `run_id` | Integer | FK `game_runs.id`, index, not null | 所属对局 ID |
| `user_id` | Integer | FK `users.id`, index, not null | 所属卖家用户 ID |
| `message` | Text | not null | 快捷回复消息内容 |
| `tags_json` | Text | nullable | 标签 JSON 数组，最多 3 个 |
| `sort_order` | Integer | not null, default 0 | 消息排序值 |
| `created_at` | DateTime(timezone=True) | not null | 创建时间 |
| `updated_at` | DateTime(timezone=True) | not null | 更新时间 |

建议索引：

```python
Index("ix_shopee_quick_reply_messages_group_sort", "group_id", "sort_order")
Index("ix_shopee_quick_reply_messages_run_user", "run_id", "user_id")
```

## 6. 后端接口设计

接口统一挂在现有 Shopee 路由下，沿用鉴权与 `run_id` 权限校验。

### 6.1 查询快捷回复配置与分组列表

```http
GET /shopee/runs/{run_id}/customer-service/quick-replies
```

用途：快捷回复列表页初始化加载配置、分组与消息。

响应示例：

```json
{
  "preference": {
    "auto_hint_enabled": true
  },
  "limits": {
    "max_groups": 25,
    "max_messages_per_group": 20,
    "max_group_name_length": 200,
    "max_message_length": 500,
    "max_tags_per_message": 3
  },
  "groups": [
    {
      "id": 1,
      "group_name": "默认分组",
      "enabled": true,
      "sort_order": 1,
      "message_count": 13,
      "messages": [
        {
          "id": 1,
          "message": "商品有现货哦",
          "tags": [],
          "sort_order": 1
        }
      ]
    }
  ]
}
```

后端行为：

- 若当前对局尚无配置，自动创建默认 preference 和默认分组。
- 返回数据优先从 Redis 读取；缓存未命中则查库并回填。
- 历史对局允许读取，不允许写入。

### 6.2 更新自动显示消息提示开关

```http
PUT /shopee/runs/{run_id}/customer-service/quick-replies/preference
```

请求：

```json
{
  "auto_hint_enabled": true
}
```

响应：

```json
{
  "preference": {
    "auto_hint_enabled": true
  }
}
```

后端行为：

- 仅 running 对局可写。
- 更新后清理快捷回复配置与列表缓存。
- 接入更新限流。

### 6.3 创建快捷回复分组与消息

```http
POST /shopee/runs/{run_id}/customer-service/quick-reply-groups
```

请求示例：

```json
{
  "group_name": "物流回复",
  "enabled": true,
  "messages": [
    {
      "message": "您的包裹已经发出，您可以随时在订单页面查看最新的物流动态。",
      "tags": ["物流", "已发货"]
    }
  ]
}
```

响应示例：

```json
{
  "group": {
    "id": 2,
    "group_name": "物流回复",
    "enabled": true,
    "sort_order": 2,
    "message_count": 1,
    "messages": [
      {
        "id": 14,
        "message": "您的包裹已经发出，您可以随时在订单页面查看最新的物流动态。",
        "tags": ["物流", "已发货"],
        "sort_order": 1
      }
    ]
  }
}
```

校验规则：

- `group_name` 去除首尾空白后不能为空，最多 200 字。
- 每个 `run_id/user_id` 最多 25 个分组。
- `messages` 至少 1 条，最多 20 条。
- 每条 `message` 去除首尾空白后不能为空，最多 500 字。
- 每条消息最多 3 个标签。
- 单个标签去除首尾空白后最多 32 字，空标签应过滤。
- 历史对局回溯模式下禁止写操作。

后端行为：

- 在事务中创建分组和消息。
- 按前端提交顺序写入消息 `sort_order`。
- 更新 `message_count`。
- 创建成功后清理 Redis 列表/配置缓存。

### 6.4 更新分组启用状态

```http
PATCH /shopee/runs/{run_id}/customer-service/quick-reply-groups/{group_id}/enabled
```

请求：

```json
{
  "enabled": false
}
```

响应：返回完整 group。

后端行为：

- 仅允许操作当前 `run_id/user_id` 下的分组。
- 更新后清理缓存。

### 6.5 编辑/删除/排序接口

V1 已实现分组编辑、删除和上移/下移排序：

| 操作 | 接口 | 用途 |
| --- | --- | --- |
| 更新分组 | `PUT /shopee/runs/{run_id}/customer-service/quick-reply-groups/{group_id}` | 修改分组名称、启用状态和消息列表 |
| 删除分组 | `DELETE /shopee/runs/{run_id}/customer-service/quick-reply-groups/{group_id}` | 删除分组及其消息 |
| 分组排序 | `PATCH /shopee/runs/{run_id}/customer-service/quick-reply-groups/{group_id}/sort` | 上移/下移分组排序 |
| 拖拽排序 | `PUT /shopee/runs/{run_id}/customer-service/quick-reply-groups/reorder` | 保存拖拽后的分组 ID 顺序 |
| 消息排序 | `PUT /shopee/runs/{run_id}/customer-service/quick-reply-groups/{group_id}/messages/reorder` | 保存分组内消息拖拽排序 |

## 7. 前端接入设计

### 7.1 列表页 props

`QuickReplySettingsView.tsx` 建议扩展 props：

```ts
interface QuickReplySettingsViewProps {
  runId: number | null;
  readOnly?: boolean;
  onCreateQuickReply: () => void;
}
```

核心状态：

```ts
const [data, setData] = useState<QuickReplyListResponse | null>(null);
const [loading, setLoading] = useState(false);
const [error, setError] = useState('');
const [savingPreference, setSavingPreference] = useState(false);
const [savingGroupId, setSavingGroupId] = useState<number | null>(null);
const [expandedGroupIds, setExpandedGroupIds] = useState<Set<number>>(new Set());
```

### 7.2 列表页初始化加载

- `runId` 为空时展示空列表或错误提示。
- 有 `runId` 时请求：`GET /shopee/runs/{runId}/customer-service/quick-replies`。
- 加载期间保留当前卡片结构，禁用开关和操作按钮。
- 接口失败时在页面顶部展示错误提示，不改变现有布局。
- `我的快捷回复 (x/25)` 中的 `x` 使用后端 groups 数量。

### 7.3 列表页开关更新

自动显示消息提示：

- 点击顶部开关后调用 `PUT /quick-replies/preference`。
- 成功后更新本地 `preference.auto_hint_enabled`。
- 失败后恢复原状态并展示错误。

分组启用开关：

- 点击分组开关后调用 `PATCH /quick-reply-groups/{group_id}/enabled`。
- 成功后覆盖该分组数据。
- 失败后恢复原状态并展示错误。

### 7.4 创建页 props

`QuickReplyCreateView.tsx` 建议扩展 props：

```ts
interface QuickReplyCreateViewProps {
  runId: number | null;
  readOnly?: boolean;
  onBackToQuickReply: () => void;
}
```

核心状态：

```ts
const [groupName, setGroupName] = useState('');
const [messages, setMessages] = useState<Array<{ id: number; text: string; tags: string }>>([]);
const [saving, setSaving] = useState(false);
const [error, setError] = useState('');
```

### 7.5 创建页保存

- 点击保存时调用：`POST /shopee/runs/{runId}/customer-service/quick-reply-groups`。
- `messages[].tags` 前端可先按换行、逗号或空白拆分为数组；若当前 UI 只支持一个标签文本，也可作为单标签提交。
- 保存成功后调用 `onBackToQuickReply()` 返回列表页。
- 取消按钮调用 `onBackToQuickReply()`。
- 保存失败时展示错误，不清空当前输入。
- `readOnly=true` 时禁用新增、模板添加、删除、拖拽、保存按钮。

### 7.6 ShopeePage 接入

当前渲染分支后续应改为：

```tsx
<QuickReplySettingsView
  runId={run?.id ?? null}
  readOnly={readOnly}
  onCreateQuickReply={() => handleSelectView('customer-service-quick-reply-create')}
/>

<QuickReplyCreateView
  runId={run?.id ?? null}
  readOnly={readOnly}
  onBackToQuickReply={() => handleSelectView('customer-service-quick-reply')}
/>
```

## 8. Redis 设计

### 8.1 Key 设计

| Key | 类型 | TTL | 用途 |
| --- | --- | --- | --- |
| `shopee:quick_reply:list:{run_id}:{user_id}` | String JSON | 300s | 快捷回复配置、分组、消息列表缓存 |
| `shopee:quick_reply:preference:{run_id}:{user_id}` | String JSON | 300s | 快捷回复偏好缓存，可与 list 合并 |
| `shopee:quick_reply:ratelimit:read:{user_id}` | Counter | 60s | 查询接口限流 |
| `shopee:quick_reply:ratelimit:update:{user_id}` | Counter | 60s | 创建/更新/删除接口限流 |

### 8.2 缓存读写

查询列表：

1. 先读 `shopee:quick_reply:list:{run_id}:{user_id}`。
2. 命中直接返回。
3. 未命中查库，若配置不存在则创建默认 preference 和默认分组。
4. 写 Redis，TTL 300 秒。

写操作：

1. 校验更新限流 key。
2. 写数据库。
3. 删除 `shopee:quick_reply:list:{run_id}:{user_id}`。
4. 删除 `shopee:quick_reply:preference:{run_id}:{user_id}`（如单独缓存）。

### 8.3 聊天推荐缓存预留

后续接入聊天输入框快捷回复推荐时，可增加：

```text
shopee:quick_reply:search:{run_id}:{user_id}:{keyword_hash}
```

- TTL 可为 60-300 秒。
- 仅做搜索加速。
- 真实可用性仍以数据库分组 `enabled` 和消息内容为准。

## 9. 初始化与历史数据处理

### 9.1 新对局默认配置

首次进入快捷回复页时，后端应确保：

| 对象 | 默认值 |
| --- | --- |
| preference.auto_hint_enabled | true |
| 默认分组名称 | 默认分组 |
| 默认分组 enabled | true |
| 默认分组消息 | 可沿用当前前端 mockShortcuts |

### 9.2 历史库补表

实现时需在 `db.py` 的历史库保障逻辑中：

- 创建/保障 `shopee_quick_reply_preferences` 表。
- 创建/保障 `shopee_quick_reply_groups` 表。
- 创建/保障 `shopee_quick_reply_messages` 表。
- 添加唯一约束与查询索引。
- 补齐表注释与字段注释。

## 10. 验收标准

### 10.1 设计验收

- 文档覆盖目标、范围、业务规则、数据模型、接口、前端接入、Redis、验收标准。
- 明确不改当前前端布局。
- 明确 V1 只维护快捷回复配置，不实现真实聊天发送或智能推荐。
- 明确数据库表与字段注释要求。

### 10.2 前端验收（后续实现）

- 打开 `/shopee/customer-service/chat-management/quick-reply`，页面从后端加载快捷回复配置和分组列表。
- 自动显示消息提示开关状态来自接口。
- 分组名称、分组启用状态、消息列表来自接口。
- 点击“新建快捷回复”进入 `/shopee/customer-service/chat-management/quick-reply/create`。
- 创建页提交分组名称和消息列表后落库，返回列表页后可看到新分组。
- 接口失败时展示错误，不破坏现有页面布局。
- 历史对局回溯模式禁用写操作。

### 10.3 后端验收（后续实现）

- `GET /shopee/runs/{run_id}/customer-service/quick-replies` 返回 preference、limits、groups、messages。
- `PUT /shopee/runs/{run_id}/customer-service/quick-replies/preference` 可更新自动提示开关。
- `POST /shopee/runs/{run_id}/customer-service/quick-reply-groups` 可创建分组与消息。
- `PATCH /shopee/runs/{run_id}/customer-service/quick-reply-groups/{group_id}/enabled` 可更新分组启用状态。
- 非法分组名称、非法消息、标签超限、分组数量超限、无权限 run_id 返回明确错误。
- 更新成功后数据库记录正确，Redis 旧缓存失效。

### 10.4 Redis 验收（后续实现）

- 首次查询未命中 Redis 时查库并回填缓存。
- 再次查询命中缓存。
- 创建或更新后旧缓存被删除。
- 创建/更新接口有限流保护。

## 11. 后续扩展

- 快捷回复编辑页或弹窗。
- 分组删除、分组排序、消息排序持久化。
- 系统模板后端化。
- 聊天输入框按关键词检索快捷回复。
- 快捷回复使用次数统计。
- 快捷回复对客服响应时间、回复率的统计影响。
- 多语言快捷回复模板。

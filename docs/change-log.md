# Change Log

最后更新：2026-05-12（调整 Shopee 客服买家自然反馈提示词）

## 2026-05-12

### 调整
- 调整 Shopee 客服买家自然反馈提示词。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`backend/apps/api-gateway/app/services/shopee_order_simulator.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：强化售前商品细节追问的买家角色提示，要求买家在适当节点先表达理解、犹豫、认可或补充个人偏好/顾虑，再继续追问，避免连续问卷式短答；默认剧本 seed 与实际 LLM 买家回复提示词同步调整。
  - 影响范围：仅影响 Shopee 客服模型生成买家下一条消息的表达风格和新建默认剧本文案；不改变接口、数据库结构、会话触发规则、评分规则或前端布局。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/api/routes/shopee.py backend/apps/api-gateway/app/services/shopee_order_simulator.py` 通过。

- 新增 Shopee 客服发送后买家输入中动画。
  - 涉及文件：`frontend/src/modules/shopee/components/ChatDetailWindow.tsx`、`frontend/src/modules/shopee/views/CustomerServiceWebView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：Chat 抽屉和客服网页版发送卖家消息后，先将卖家消息本地追加到会话中，并在模型生成买家回复期间显示买家侧三点输入中气泡；接口返回后再用后端会话详情刷新真实消息列表。
  - 影响范围：仅影响客服对话发送期间的前端交互反馈；不改变接口、数据库、页面布局或客服评分规则。
  - 验证结果：已运行前端 TypeScript 诊断与相关文件币种残留检查；未重复执行此前被拒绝的 `npm --prefix frontend run build`。

- 修正 Shopee 客服商品卡片币种展示。
  - 涉及文件：`frontend/src/modules/shopee/components/ChatDetailWindow.tsx`、`frontend/src/modules/shopee/views/CustomerServiceWebView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：将 Chat 抽屉商品卡片、客服网页版中间会话商品卡片和右侧商品面板价格展示从泰铢符号 `฿` 改为马来西亚 `RM`，避免出现 `฿188฿188` 这类错误币种展示。
  - 影响范围：仅影响客服相关商品卡片价格展示；不改变接口数据、订单金额和页面布局。
  - 验证结果：已确认客服相关文件无 `฿` 残留；未重复执行此前被拒绝的 `npm --prefix frontend run build`。

- 修正 Shopee 售前咨询变体图片口径。
  - 涉及文件：`backend/apps/api-gateway/app/services/shopee_order_simulator.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：订单模拟器在买家选中具体变体并触发售前商品细节追问时，会话商品上下文的 `cover_url` 与图片列表优先使用该变体图片，并记录选中变体 ID、名称、选项和变体图，避免买家咨询中展示主商品图而非准备下单变体图。
  - 影响范围：影响订单模拟触发的 `product_detail_inquiry` 会话商品卡片与买家首条咨询上下文；前端样式与接口结构不变。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/services/shopee_order_simulator.py` 通过。

- 调整 Shopee 售前商品细节追问触发口径。
  - 涉及文件：`backend/apps/api-gateway/app/services/shopee_order_simulator.py`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：将 `product_detail_inquiry` 从客服会话列表查询时扫描已上架商品触发，调整为订单模拟器中买家通过下单概率后、正式创建订单前按售前咨询概率分流触发；命中咨询时创建客服会话和买家首条消息，本次不创建订单；客服列表接口改为纯查询，不再承担自动触发副作用。
  - 影响范围：影响 Shopee 订单模拟生成订单前的买家咨询分流，以及 `/shopee/runs/{run_id}/customer-service/conversations` 的触发副作用；前端样式与客服会话接口保持不变。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/services/shopee_order_simulator.py backend/apps/api-gateway/app/api/routes/shopee.py` 通过。

### 新增
- 实现 Shopee 售前商品细节追问客服闭环。
  - 涉及文件：`backend/apps/api-gateway/app/models.py`、`backend/apps/api-gateway/app/db.py`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/components/ChatMessagesDrawer.tsx`、`frontend/src/modules/shopee/components/ChatDetailWindow.tsx`、`frontend/src/modules/shopee/views/CustomerServiceWebView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增客服剧本、会话、消息和模型配置 ORM；补齐历史库索引保障、表注释和字段注释；新增 LM Studio/OpenAI-compatible 客服模型配置接口、会话列表/详情、发送消息和结束评分接口；未配置数据库模型记录时读取 `.env` 中的 `SHOPEE_CUSTOMER_SERVICE_LLM_*` 作为默认客服模型配置；会话列表查询时按对局游戏时间扫描上架商品并按概率、质量分、规格复杂度、描述长度、图片数量、去重、未处理会话上限和每日上限触发 `product_detail_inquiry`；Chat 抽屉和客服网页版共用同一套接口展示、发送、结束和评分。
  - 游戏时间口径：商品咨询触发、消息发送、会话关闭和满意度评分均使用对局游戏时间，不使用真实世界当前时间。
  - 影响范围：影响 `/shopee/runs/{run_id}/customer-service/conversations`、`/messages`、`/resolve`、`/model-settings` 接口，以及 Chat 抽屉和 `/shopee/customer-service/web` 的数据来源与交互；前端保留既有样式和布局，仅替换 mock 数据和事件处理。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/models.py backend/apps/api-gateway/app/db.py backend/apps/api-gateway/app/api/routes/shopee.py` 通过；`npm --prefix frontend run build` 通过。

- 新增 Shopee 售前商品细节追问前后端数据库 Redis 实现设计文档。
  - 涉及文件：`docs/设计文档/52-Shopee售前商品细节追问前后端数据库Redis实现设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：在虚拟客服 MVP 总设计基础上，单独拆出售前商品细节追问实现设计；明确商品上架后按游戏时间延迟、质量分、规格复杂度、描述完整度、概率、去重和未处理会话上限创建客服会话；设计会话列表、详情、发送消息、结束评分接口复用口径；补充 Redis 列表/详情缓存、商品触发锁、LLM 限流和模型配置缓存；定义商品准确性、响应完整度、服务态度、购买引导和平台合规评分重点；补充商品细节追问对话轮次为最少 5 条、推荐 7 条、最多 10 条消息；补充买家/LLM 复用我的产品商品详情、主图/图片 URL、AI 商品质量评分和 AI 主图/内容评分明细的上下文口径。
  - 游戏时间口径：商品上架后的触发延迟、候选有效期、每日上限、消息时间和评分时间均使用对局游戏时间，不使用真实世界当前时间。
  - 影响范围：仅新增后续实现设计与进度记录；本次不修改前端样式布局、后端接口、数据库结构或 Redis 代码。

- 新增 Shopee 虚拟客服对话系统 MVP 设计文档。
  - 涉及文件：`docs/设计文档/51-Shopee虚拟客服对话系统MVP设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：设计基于现有 Shopee Step05 店铺运营的虚拟客服对话系统，明确第一版仅保留商品细节追问、物流停滞催单、签收破损退款三个自动触发案例；Chat 抽屉与客服网页版共用同一套会话和消息数据；自动回复作为辅助；客服 LLM 模型单独配置；会话评分作为买家满意度并可轻微影响店铺表现；补充同一学生未处理会话达到 3 个时暂停新增，商品细节追问可跳过，物流停滞催单和签收破损退款进入待触发候选。
  - 游戏时间口径：商品上架后的触发延迟、物流停滞判断、签收后触发窗口、候选事件过期、会话超时、满意度评分和统计均使用对局游戏时间，不使用真实世界当前时间。
  - 影响范围：仅新增后续实现设计与进度记录；本次不修改前端接口、后端接口、数据库结构或 Redis 代码。

## 2026-05-11

### 修复
- 修正 Shopee 快捷回复拖拽排序接口 422 问题。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：将 `PUT /shopee/runs/{run_id}/customer-service/quick-reply-groups/reorder` 静态路由声明移动到 `PUT /shopee/runs/{run_id}/customer-service/quick-reply-groups/{group_id}` 动态路由之前，避免 FastAPI 将 `reorder` 误解析为整数 `group_id` 导致 422。
  - 影响范围：影响 `/shopee/customer-service/chat-management/quick-reply` 分组拖拽排序后的后端同步保存。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/api/routes/shopee.py` 通过。

### 新增
- 补齐 Shopee 快捷回复分组编辑、删除和移动排序操作。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/components/Header.tsx`、`frontend/src/modules/shopee/views/QuickReplySettingsView.tsx`、`frontend/src/modules/shopee/views/QuickReplyCreateView.tsx`、`docs/设计文档/50-Shopee快捷回复前端接口后端数据库Redis打通设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增快捷回复分组编辑保存、删除分组、上移/下移排序接口和拖拽后批量保存排序接口；列表页将编辑、删除和移动图标接入真实操作，并在拖拽结束后把当前分组 ID 顺序同步到后端；编辑入口跳转到与创建页一致的 1360px 表单布局并回填已设置的分组名称、消息和标签，保存后更新原分组。
  - 影响范围：影响 `/shopee/customer-service/chat-management/quick-reply` 列表页操作区和 `/shopee/customer-service/chat-management/quick-reply/edit?group_id=...` 编辑页；历史对局回溯模式继续禁用写操作。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/api/routes/shopee.py` 通过；`npm --prefix frontend run build` 通过。

- 实现 Shopee 快捷回复配置 V1 前后端数据库 Redis 闭环。
  - 涉及文件：`backend/apps/api-gateway/app/models.py`、`backend/apps/api-gateway/app/db.py`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/views/QuickReplySettingsView.tsx`、`frontend/src/modules/shopee/views/QuickReplyCreateView.tsx`、`docs/设计文档/50-Shopee快捷回复前端接口后端数据库Redis打通设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增快捷回复偏好、分组和消息 ORM，历史库索引保障、表注释和字段注释；新增快捷回复列表查询、提示开关更新、分组创建与分组启用状态更新接口；接入 Redis 列表缓存、读写限流和写入后缓存失效；前端快捷回复列表页加载真实配置，开关状态来自接口并保存到后端，创建页提交分组名称、消息内容和标签。
  - 影响范围：影响 `/shopee/customer-service/chat-management/quick-reply` 与 `/shopee/customer-service/chat-management/quick-reply/create` 的数据来源、开关保存、分组创建和刷新持久化；本次仅实现配置持久化，不实现真实聊天输入框推荐弹窗、客服消息发送、编辑、删除或排序持久化。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/models.py backend/apps/api-gateway/app/db.py backend/apps/api-gateway/app/api/routes/shopee.py` 通过；`npm --prefix frontend run build` 通过。

- 新增 Shopee 快捷回复前端接口后端数据库 Redis 打通设计文档。
  - 涉及文件：`docs/设计文档/50-Shopee快捷回复前端接口后端数据库Redis打通设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：基于当前 `/shopee/customer-service/chat-management/quick-reply` 与 `/shopee/customer-service/chat-management/quick-reply/create` 前端布局，设计快捷回复提示开关、分组、消息、标签、创建页保存、数据库表、后端接口、Redis 列表/配置缓存、读写限流和后续聊天输入框关键词检索缓存预留口径。
  - 影响范围：仅新增后续实现设计与进度记录；本次不修改前端接口、后端接口、数据库结构或 Redis 代码。

- 实现 Shopee 自动回复配置 V1 前后端数据库 Redis 闭环。
  - 涉及文件：`backend/apps/api-gateway/app/models.py`、`backend/apps/api-gateway/app/db.py`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/views/AutoReplySettingsView.tsx`、`docs/设计文档/49-Shopee自动回复前端接口后端数据库Redis打通设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 `shopee_auto_reply_settings` ORM、历史库索引保障、表注释和字段注释；新增自动回复配置查询与按类型更新接口；接入 Redis 配置缓存、读写限流和更新后缓存失效；前端自动回复页加载真实配置，开关状态来自接口，点击开关后保存到后端，离线回复预览来自接口数据。
  - 影响范围：影响 `/shopee/customer-service/chat-management/auto-reply` 自动回复配置页的数据来源、开关保存和刷新持久化；本次仅实现配置持久化，不实现真实客服自动回复触发、买家聊天消息写入或触发日志。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/models.py backend/apps/api-gateway/app/db.py backend/apps/api-gateway/app/api/routes/shopee.py` 通过；`npm --prefix frontend run build` 通过。

- 新增 Shopee 自动回复前端接口后端数据库 Redis 打通设计文档。
  - 涉及文件：`docs/设计文档/49-Shopee自动回复前端接口后端数据库Redis打通设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：基于当前 `/shopee/customer-service/chat-management/auto-reply` 前端布局，设计默认自动回复与离线自动回复的查询、更新、开关、数据库表、Redis 配置缓存、更新限流、后续触发频控和聊天模拟预留口径。
  - 游戏时间口径：自动回复触发、24 小时频控、每游戏日频控、工作时间判断和后续统计均使用对局游戏时间，不使用浏览器或服务器真实当前时间作为业务判断来源。
  - 影响范围：仅新增后续实现设计与进度记录；本次不修改前端接口、后端接口、数据库结构或 Redis 代码。

- 接入 Shopee 快捷回复“新建快捷回复”空白页。
  - 涉及文件：`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/components/Header.tsx`、`frontend/src/modules/shopee/views/QuickReplySettingsView.tsx`、`frontend/src/modules/shopee/views/QuickReplyCreateView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 1360px 空白页面；接入 `/shopee/customer-service/chat-management/quick-reply/create` 前端路由识别、路径构建和页面渲染；快捷回复页“新建快捷回复”按钮跳转到该空白页；该页面不显示左侧菜单栏。
  - 影响范围：仅新增快捷回复新建承载页及按钮跳转，不接入新建快捷回复表单、保存逻辑或后端接口。

- 接入 Shopee 聊天管理“自动回复”和“快捷回复”空白页。
  - 涉及文件：`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/components/Header.tsx`、`frontend/src/modules/shopee/views/ChatManagementView.tsx`、`frontend/src/modules/shopee/views/AutoReplySettingsView.tsx`、`frontend/src/modules/shopee/views/QuickReplySettingsView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增两个 1360px 空白页面；接入 `/shopee/customer-service/chat-management/auto-reply` 与 `/shopee/customer-service/chat-management/quick-reply` 前端路由识别、路径构建和页面渲染；聊天管理页“自动回复 > 开启”和“快捷回复 > 编辑”按钮分别跳转到对应页面；两个页面不显示左侧菜单栏。
  - 影响范围：仅新增聊天管理下两个空白承载页及按钮跳转，不接入自动回复或快捷回复业务数据、表单与后端接口。

- 接入 Shopee 左侧菜单“聊天管理”空白页。
  - 涉及文件：`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/components/Header.tsx`、`frontend/src/modules/shopee/components/Sidebar.tsx`、`frontend/src/modules/shopee/views/ChatManagementView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增聊天管理空白页组件；接入 `/shopee/customer-service/chat-management` 前端路由识别、路径构建和页面渲染分支；左侧菜单“客户服务 > 聊天管理”点击后进入该页并高亮当前菜单；顶部面包屑显示“聊天管理”。
  - 影响范围：仅影响左侧菜单聊天管理入口与新增空白承载页；页面布局沿用营销中心首页外层节奏，暂不接入客服业务数据或后端接口。

- 新增 Shopee 客服 Chat 抽屉“网页版”空白跳转页。
  - 涉及文件：`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/components/ChatMessagesDrawer.tsx`、`frontend/src/modules/shopee/views/CustomerServiceWebView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增客服网页版空白页组件；在 Shopee 页面路由中接入 `/shopee/customer-service/web`；将 Chat 抽屉右上角“网页版”从空链接改为内部页面跳转，点击后关闭抽屉；该路由下隐藏 Shopee 最右侧通知/Chat 竖栏，并将顶部标题调整为保留 Shopee logo、加粗显示“Chat”、隐藏“卖家中心”。
  - 影响范围：仅影响 Chat 抽屉“网页版”入口、新增客服网页版页面展示、该页面右侧竖栏显隐和顶部标题，不改动已手动完成的抽屉布局样式，不新增客服业务接口。

### 修复
- 修正 Shopee 物流运费成本长距离异常放大问题。
  - 涉及文件：`backend/apps/api-gateway/app/services/shopee_fulfillment.py`、`frontend/src/modules/shopee/views/MyIncomeView.tsx`、`docs/设计文档/47-Shopee运费促销创建前后端数据库Redis实现设计.md`、`docs/设计文档/48-Shopee运费促销接入订单模拟影响设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：确认 KL 仓到 Sabah 买家距离约 1623km，旧公式按全量公里数线性计费导致快捷快递展示约 RM231.72；现改为计费距离最多 80km，超过 300km/800km 时按渠道追加远程附加费，并同步待释放收入页前端试算公式与设计文档口径。
  - 影响范围：影响修正后新生成或新结算 Shopee 订单的物流成本、平台运费补贴、净收入和运费促销前后运费展示；已生成订单的历史运费字段不会自动回填。
  - 验证结果：已复核 `快捷快递` 1623.01km 从旧口径约 RM231.72 调整为 RM23.70；`MyIncomeView.tsx` 前端 LSP 错误诊断无新增错误。

- 修正 Shopee 运费促销 `fixed_fee` 层级的订单模拟计算口径。
  - 涉及文件：`backend/apps/api-gateway/app/services/shopee_order_simulator.py`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/views/ShippingFeePromotionCreateView.tsx`、`docs/设计文档/47-Shopee运费促销创建前后端数据库Redis实现设计.md`、`docs/设计文档/48-Shopee运费促销接入订单模拟影响设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：订单模拟中 `fixed_fee_amount` 按“运费减免金额”计算，而不是按“优惠后固定运费”计算；例如原始运费 RM8、配置 RM3 时，本单运费优惠为 RM3、优惠后运费为 RM5。创建页文案从“固定运费”改为“运费减免”，后端层级校验改为高门槛减免金额不能低于低门槛；同时将订单模拟中的 `快捷快递` 映射到标准快递 `standard`，避免只选标准快递的运费促销无法命中新生成订单，并同步设计文档口径。
  - 影响范围：影响修正后新生成 Shopee 订单的运费促销命中金额、活动预算统计和结算明细扣减；已生成且运费促销优惠为 0 的历史订单不会自动回填。

## 2026-05-10

### 新增
- 接入 Shopee 运费促销对订单模拟、订单结算和我的订单展示的影响。
  - 涉及文件：`backend/apps/api-gateway/app/models.py`、`backend/apps/api-gateway/app/db.py`、`backend/apps/api-gateway/app/services/shopee_order_simulator.py`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/views/MyOrdersView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增订单级运费促销命中字段与结算级运费促销优惠字段，历史库补字段、索引和字段注释同步维护；订单模拟按当前游戏 tick 加载可用运费促销，按物流渠道、订单商品小计和原始运费匹配最优活动，支持固定运费、免运费和预算不足部分抵扣；活动统计回写预算、订单数、买家数、销售额和运费优惠金额，预算耗尽后状态转为 `budget_exhausted`；订单列表和结算弹窗展示运费促销优惠。
  - 游戏时间口径：活动加载、命中判断、预算扣减、统计回写和 `buyer_journeys` 调试日志均使用订单模拟 tick 的游戏时间，不使用真实世界当前时间。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/models.py backend/apps/api-gateway/app/db.py backend/apps/api-gateway/app/services/shopee_order_simulator.py backend/apps/api-gateway/app/api/routes/shopee.py` 通过；`MyOrdersView.tsx` 前端 LSP 诊断无错误。
  - 影响范围：影响 Shopee 订单模拟生成订单时的运费促销归因、活动预算与统计、订单结算净收入、我的订单列表展示和结算详情；不改变商品行价格、基础物流成本、平台运费补贴、发货时限或运输时长。

## 2026-05-09

### 新增
- 新增 Shopee 运费促销接入订单模拟影响设计文档。
  - 涉及文件：`docs/设计文档/48-Shopee运费促销接入订单模拟影响设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：设计运费促销接入订单模拟的命中条件、渠道映射、活动选择、固定运费/免运费优惠计算、预算不足处理、订单字段、结算字段、活动统计回写、Redis 失效、前端展示和验收用例。
  - 游戏时间口径：活动命中、预算扣减、统计回写和调试日志均使用订单模拟 tick 的游戏时间，不使用服务器真实当前时间。
  - 验证结果：本次仅新增设计文档和进度记录，未修改前后端业务代码。
  - 影响范围：仅影响后续运费促销接入订单模拟的实现口径；当前订单模拟、订单结算、我的订单页面和运费促销活动行为不变。

### 修复
- 修复 Shopee 运费促销创建页自定义期限结束时间默认值。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/views/ShippingFeePromotionCreateView.tsx`、`docs/设计文档/47-Shopee运费促销创建前后端数据库Redis实现设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：创建页 bootstrap 现在同时返回基于当前对局游戏时间生成的默认开始时间和默认结束时间；前端结束时间读取 `form.end_at`，并保留游戏时间字段兜底，避免自定义期限结束日期选择器为空。
  - 游戏时间口径：自定义期限开始和结束日期选择器均展示后端返回的对局游戏时间，提交后仍由后端按游戏时间解析和判断。
  - 影响范围：影响 `/shopee/marketing/shipping-fee-promotion/create` 自定义期限默认显示；不改变页面布局、样式、物流渠道、预算或层级规则。

### 新增
- 接入 Shopee 运费促销创建与列表前后端数据库 Redis 闭环。
  - 涉及文件：`backend/apps/api-gateway/app/models.py`、`backend/apps/api-gateway/app/db.py`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/views/ShippingFeePromotionView.tsx`、`frontend/src/modules/shopee/views/ShippingFeePromotionCreateView.tsx`、`docs/设计文档/47-Shopee运费促销创建前后端数据库Redis实现设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增运费促销活动主表、适用物流渠道表和门槛层级表 ORM、历史库索引保障、表注释和字段注释；新增创建页 bootstrap、创建提交和列表接口；接入 Redis bootstrap/list 缓存、创建限流和创建成功后的列表/订单模拟活动缓存失效；前端在不调整用户手动样式布局的前提下，将创建页和列表页接入真实接口。
  - 游戏时间口径：创建页默认开始时间、自定义期限提交与解析、活动状态判断和列表活动时间展示均使用对局游戏时间，不使用真实世界当前时间。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/models.py backend/apps/api-gateway/app/db.py backend/apps/api-gateway/app/api/routes/shopee.py` 通过；`ShippingFeePromotionView.tsx`、`ShippingFeePromotionCreateView.tsx`、`ShopeePage.tsx` 前端 LSP 诊断无错误。
  - 影响范围：影响 `/shopee/marketing/shipping-fee-promotion/create` 运费促销创建和 `/shopee/marketing/shipping-fee-promotion` 列表展示；本次不实现编辑、结束、删除、复制和订单模拟真实运费减免生效。

### 变更
- 补充 Shopee 运费促销设计中与现有订单运费、平台补贴和运输时长链路的边界。
  - 涉及文件：`docs/设计文档/47-Shopee运费促销创建前后端数据库Redis实现设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：明确现有“我的订单/发货”链路已通过 `shipping_channel`、`distance_km`、`calc_shipping_cost(...)`、`calc_eta(...)`、`shipping_cost_amount` 和 `shipping_subsidy_amount` 处理原始物流成本、平台补贴和运输时长；运费促销后续只在原始运费基础上计算买家侧减免、卖家促销预算消耗和订单归因，不改变发货时限、配送线路或运输时长。
  - 游戏时间口径：运费促销活动期限、命中、预算扣减和统计回写仍使用对局游戏时间；原有运输时长继续按发货游戏时间与物流距离/渠道计算。
  - 验证结果：本次仅更新设计文档和进度记录，未修改前后端业务代码。
  - 影响范围：影响后续运费促销接入订单模拟和结算设计口径；当前订单运费、运输中展示、平台补贴和运费促销页面行为不变。

### 新增
- 新增 Shopee 运费促销创建前后端数据库 Redis 实现设计文档。
  - 涉及文件：`docs/设计文档/47-Shopee运费促销创建前后端数据库Redis实现设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：在查看用户手动完成的 `ShippingFeePromotionView.tsx` 与 `ShippingFeePromotionCreateView.tsx` 前端布局后，设计运费促销列表、创建页 bootstrap、创建提交、数据库主表/渠道表/层级表、Redis 缓存、创建后缓存失效和后续订单模拟预留口径。
  - 游戏时间口径：活动默认开始时间、自定义期限、状态判断、订单模拟命中和统计回写均使用对局游戏时间，不使用真实世界当前时间。
  - 验证结果：已创建并检查设计文档路径；本次仅新增设计文档和进度记录，未修改前后端业务代码。
  - 影响范围：仅新增运费促销后续实现设计与进度记录；当前运费促销页面、接口、数据库和订单模拟行为不变。

### 优化
- 接入 Shopee 代金券列表底部分页器功能。
  - 涉及文件：`frontend/src/modules/shopee/views/ShopVoucherView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：在不调整分页器样式和布局的前提下，新增页码状态、跳转页状态和接口分页参数；列表请求固定 `page_size=10`，上一页、下一页、页码按钮和 Go 跳转均重新加载对应页数据；切换状态标签和查询时回到第 1 页。
  - 验证结果：`ShopVoucherView.tsx` 前端 LSP 诊断无错误；本次涉及文件 `git diff --check` 通过。
  - 影响范围：影响 `/shopee/marketing/vouchers` 代金券列表数据分页展示；不改变代金券列表表格、卡片、筛选栏或分页器视觉样式。

### 新增
- 接入 Shopee 关注礼代金券对订单模拟的后端影响。
  - 涉及文件：`backend/apps/api-gateway/app/models.py`、`backend/apps/api-gateway/app/db.py`、`backend/apps/api-gateway/app/services/shopee_order_simulator.py`、`frontend/src/modules/shopee/views/MyOrdersView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增模拟买家关注状态表 `shopee_buyer_follow_states` 的 ORM、历史库保障、表注释和字段注释；订单模拟加载当前游戏 tick 下可领取的 `follow_voucher`，按买家画像模拟首次关注并写入关注状态，按 `valid_days_after_claim` 判断个人有效期，纳入统一最优券排序并写入订单级 voucher 归因、活动统计和我的订单代金券标注。
  - 游戏时间口径：关注礼领取窗口、首次关注时间、个人有效期、订单创建时间、归因和统计回写均使用订单模拟 tick 的游戏时间，不使用服务器真实当前时间。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/models.py backend/apps/api-gateway/app/db.py backend/apps/api-gateway/app/services/shopee_order_simulator.py` 通过。
  - 影响范围：影响 Shopee 订单模拟生成订单时关注礼代金券的下单概率、买家实付、订单级代金券归因、关注状态持久化、关注礼活动统计和订单列表展示；不新增真实 Shopee 关注接口或买家个人券实例表。

### 变更
- 补充 Shopee 关注礼代金券接入订单模拟影响设计中的买家关注状态表口径。
  - 涉及文件：`docs/设计文档/46-Shopee关注礼代金券接入订单模拟影响设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：设计后续新增 `shopee_buyer_follow_states`，按 `(run_id, user_id, buyer_name)` 持久化模拟买家是否已关注、首次关注游戏时间、关注来源和来源活动；关注礼领取资格先查关注状态，未关注买家才按概率首次关注并领取，已关注买家不再重复作为新关注者领取关注礼。
  - 游戏时间口径：首次关注时间、领取窗口、个人有效期、下单使用和统计回写均使用订单模拟 tick 的游戏时间。
  - 验证结果：本次仅更新设计文档和进度记录，未修改前后端业务代码。
  - 影响范围：影响后续关注礼接入订单模拟的数据库与资格判定设计；当前实现行为不变。

### 新增
- 新增 Shopee 关注礼代金券接入订单模拟影响设计文档。
  - 涉及文件：`docs/设计文档/46-Shopee关注礼代金券接入订单模拟影响设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：设计 `follow_voucher` 后续接入订单模拟的逻辑口径，覆盖买家关注/领取资格模拟、领取后 `valid_days_after_claim` 个游戏天有效期、下单概率 bonus、订单实付扣减、订单级 voucher 归因、统计回写、Redis 缓存失效和日志字段。
  - 游戏时间口径：领取窗口、个人有效期、下单使用和统计回写均使用订单模拟 tick 的游戏时间，不使用服务器真实当前时间。
  - 验证结果：已创建并检查设计文档路径；本次仅文档设计，未运行前后端构建。
  - 影响范围：仅新增设计文档与进度记录；尚未修改订单模拟、数据库、后端接口或前端页面。

### 新增
- 接入 Shopee 代金券订单页面前后端数据库 Redis 闭环。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/views/VoucherOrdersView.tsx`、`docs/设计文档/45-Shopee代金券订单页面前后端数据库Redis实现设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增代金券订单接口 `GET /shopee/runs/{run_id}/marketing/vouchers/{voucher_type}/{campaign_id}/orders`，返回活动基本信息、订单总数、订单列表和分页；复用 `shopee_orders` 订单级代金券归因字段与 `shopee_order_items` 商品快照，不新增数据库表；新增代金券订单 Redis 缓存并纳入订单缓存失效链路；前端在不改变用户手动布局的前提下将 `VoucherOrdersView` 接入真实接口数据。
  - 游戏时间口径：代金券期限和订单创建时间均由后端按游戏时间格式化后返回，页面不使用真实世界时间展示。
  - 验证结果：`VoucherOrdersView.tsx`、`ShopeePage.tsx` 前端 LSP 诊断无错误；`python -m py_compile backend/apps/api-gateway/app/api/routes/shopee.py` 通过；`git diff --check` 通过。
  - 影响范围：影响 `/shopee/marketing/vouchers` 操作列“订单”入口、代金券订单数据接口和订单缓存失效；页面布局保留现有 1360px 无左侧菜单栏样式。

### 新增
- 接入 Shopee 代金券订单空白页。
  - 涉及文件：`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/components/Header.tsx`、`frontend/src/modules/shopee/views/ShopVoucherView.tsx`、`frontend/src/modules/shopee/views/VoucherOrdersView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 `VoucherOrdersView` 作为 1360px 宽空白内容页；代金券列表操作列“订单”点击后跳转到 `/shopee/marketing/vouchers/orders?voucher_type=...&campaign_id=...`；该页面不显示左侧菜单栏，并在顶部面包屑显示“营销中心 > 代金券 > 代金券订单”。
  - 验证结果：收尾阶段执行前端 LSP 诊断与空白字符校验。
  - 影响范围：影响 `/shopee/marketing/vouchers` 中已结束代金券操作列“订单”入口；仅新增空白承载页，不接入订单数据、后端接口或业务逻辑。

## 2026-05-08

### 新增
- 接入 Shopee 代金券列表只读详情页。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/views/ShopVoucherView.tsx`、`frontend/src/modules/shopee/views/ShopVoucherCreateView.tsx`、`frontend/src/modules/shopee/views/ProductVoucherCreateView.tsx`、`frontend/src/modules/shopee/views/PrivateVoucherCreateView.tsx`、`frontend/src/modules/shopee/views/LiveVoucherCreateView.tsx`、`frontend/src/modules/shopee/views/VideoVoucherCreateView.tsx`、`frontend/src/modules/shopee/views/FollowVoucherCreateView.tsx`、`frontend/src/modules/shopee/views/ShopVoucherDetailView.tsx`、`frontend/src/modules/shopee/views/ProductVoucherDetailView.tsx`、`frontend/src/modules/shopee/views/PrivateVoucherDetailView.tsx`、`frontend/src/modules/shopee/views/LiveVoucherDetailView.tsx`、`frontend/src/modules/shopee/views/VideoVoucherDetailView.tsx`、`frontend/src/modules/shopee/views/FollowVoucherDetailView.tsx`、`frontend/src/modules/shopee/components/Header.tsx`、`frontend/src/modules/shopee/views/ShopeeAdsView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增统一代金券详情接口，按 `voucher_type` 与活动 ID 返回创建时保存的表单字段、状态、统计和指定商品快照；代金券列表“详情”操作接入 `/shopee/marketing/vouchers/detail` 前端路由；新增 6 个券类型专属详情页，每个详情页复用对应创建页布局并灌入详情数据，强制只读且禁用输入、商品选择、提交按钮和日期变更；详情模式不显示“历史对局回溯模式”提示；顶部面包屑按券类型显示“店铺/商品/专属/直播/视频/关注礼代金券详情”。
  - 验证结果：`ShopeePage.tsx`、6 个创建页与 6 个详情页前端 LSP 诊断无错误；`python -m py_compile backend/apps/api-gateway/app/api/routes/shopee.py` 通过；`git diff --check` 通过。
  - 影响范围：影响 `/shopee/marketing/vouchers` 代金券列表操作列“详情”入口和新增详情接口；只读查看创建时填写内容，不接入编辑、删除、停止或复制。

### 优化
- 提高 Shopee 直播/视频代金券内容场景资格命中率。
  - 涉及文件：`backend/apps/api-gateway/app/services/shopee_order_simulator.py`、`docs/设计文档/44-Shopee直播视频代金券接入订单模拟影响设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：在保留内容场景资格模拟口径的前提下，提高 `live_voucher` 与 `video_voucher` 的基础触达概率、画像权重和概率上下限；直播资格概率限制调整为 `clamp(score, 0.096, 0.66)`，视频资格概率限制调整为 `clamp(score, 0.084, 0.576)`，降低手动测试中连续未命中的概率。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/services/shopee_order_simulator.py` 通过；本次涉及文件 `git diff --check` 通过。
  - 影响范围：影响订单模拟中直播/视频代金券进入可用候选池的概率；不改变活动时间、商品范围、门槛、每单最多一张最优券、订单字段归因或统计回写规则。

### 新增
- 接入 Shopee 直播/视频代金券对订单模拟的后端影响。
  - 涉及文件：`backend/apps/api-gateway/app/services/shopee_order_simulator.py`、`frontend/src/modules/shopee/views/MyOrdersView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：订单模拟加载当前游戏 tick 下进行中的 `live_voucher` 与 `video_voucher`，按买家画像和优惠力度模拟直播/视频内容场景触达资格并在单次模拟中缓存结果；直播/视频券支持全部商品/指定商品适用范围、买家限用、总用量、门槛、限时抢购排除，并与店铺/商品/专属券进入统一最优券候选池；订单生成时扣减买家实付、保存订单级 voucher 快照、回写对应活动统计，并在 `buyer_journeys` 顶层保留预览候选、资格、命中和优惠日志。
  - 游戏时间口径：直播/视频券开始/结束判断使用订单模拟传入的 `tick_time` 游戏时间，不使用真实世界当前时间判断活动是否生效；资格判定、用券发生、日志和统计回写均随本次订单模拟 tick。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/services/shopee_order_simulator.py` 通过；`MyOrdersView.tsx` 前端 LSP 诊断无错误；本次涉及文件 `git diff --check` 通过。
  - 影响范围：影响 Shopee 订单模拟生成订单时直播/视频代金券的下单概率、买家实付、订单级代金券归因、直播/视频券活动统计和订单列表展示；不新增买家个人券实例、直播/视频观看记录、领取记录或真实 Shopee 直播/视频接口。


### 新增
- 新增 Shopee 直播/视频代金券接入订单模拟影响设计文档。
  - 涉及文件：`docs/设计文档/44-Shopee直播视频代金券接入订单模拟影响设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：合并设计 `live_voucher` 与 `video_voucher` 接入订单模拟的内容场景口径，明确第一版不做真实直播/视频观看、领券记录或个人券实例，而是按买家画像模拟直播/视频内容触达资格；所有开始/结束、资格判定、用券发生、日志和统计回写均使用订单模拟 tick 的游戏时间；直播/视频券与店铺、商品、专属券进入统一最优券候选池，同额优先级为商品代金券 > 直播代金券 > 视频代金券 > 专属代金券 > 店铺代金券。
  - 验证结果：已创建并检查设计文档路径；本次仅文档设计，未运行前后端构建。
  - 影响范围：仅新增设计文档与进度记录；尚未改动订单模拟、数据库字段、后端接口或前端展示。

### 新增
- 接入 Shopee 专属代金券对订单模拟的后端影响。
  - 涉及文件：`backend/apps/api-gateway/app/services/shopee_order_simulator.py`、`frontend/src/modules/shopee/views/MyOrdersView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：订单模拟加载当前游戏 tick 下进行中的 `private_voucher`，按模拟指定人群方案判断买家专属资格并在单次模拟中缓存结果；专属券支持全部商品/指定商品适用范围、买家限用、总用量、门槛、限时抢购排除，并与店铺/商品券进入统一最优券候选池；订单生成时扣减买家实付、保存订单级 voucher 快照、回写专属券统计，并在 `buyer_journeys` 中记录资格、候选、命中和优惠信息；我的订单买家实付列补充“专属代金券”标注。
  - 游戏时间口径：专属券开始/结束判断使用订单模拟传入的 `tick_time` 游戏时间，不使用真实世界当前时间判断活动是否生效；资格判定、用券发生、日志和统计回写均随本次订单模拟 tick。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/services/shopee_order_simulator.py` 通过；`MyOrdersView.tsx` 前端 LSP 诊断无错误；已用 Grep 检查 `private_voucher`、`private_access_cache`、游戏 tick 传参和订单列表标注接入点；本次涉及文件 `git diff --check` 通过。
  - 影响范围：影响 Shopee 订单模拟生成订单时专属代金券的下单概率、买家实付、订单级代金券归因、专属券活动统计和订单列表展示；不新增买家个人券实例、手动买家名单、买家分组、领取记录或真实 Shopee 领券接口。

### 新增
- 新增 Shopee 专属代金券接入订单模拟影响设计文档。
  - 涉及文件：`docs/设计文档/43-Shopee专属代金券接入订单模拟影响设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：设计 `private_voucher` 接入订单模拟的逻辑口径，明确专属券需先判断买家资格；第一版采用方案 A，不新增个人券实例、不做手动买家名单/买家分组/发券记录，按买家画像、优惠力度模拟被私域触达的指定人群，并在单次模拟 tick 内稳定判定资格；专属券与店铺/商品券进入统一最优券候选池，每单最多使用一张券且存在可用券时必须使用最优券；同额优先级为商品代金券 > 专属代金券 > 店铺代金券。
  - 验证结果：已创建并检查设计文档路径；本次仅文档设计，未运行前后端构建。
  - 影响范围：仅新增设计文档与进度记录；尚未改动订单模拟、数据库字段、后端接口或前端展示。

### 优化
- 在 Shopee 我的订单列表买家实付列展示已使用代金券标注。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/views/MyOrdersView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：订单列表与订单详情响应补充订单级 voucher 字段；前端订单列表 `OrderRow` 增加代金券字段，并在买家实付列按既有营销活动标注样式展示“店铺代金券/商品代金券：名称 -抵扣金额”。
  - 影响范围：影响 `/shopee/orders` 我的订单列表中已用券订单的买家实付列展示，不改变订单模拟、实付计算或代金券统计逻辑。

### 新增
- 接入 Shopee 店铺/商品代金券对订单模拟的后端影响。
  - 涉及文件：`backend/apps/api-gateway/app/models.py`、`backend/apps/api-gateway/app/db.py`、`backend/apps/api-gateway/app/services/shopee_order_simulator.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 `ShopeeOrder` 订单级 voucher 字段与历史库补字段/字段注释逻辑；订单模拟加载当前游戏 tick 下进行中的店铺代金券和商品代金券，按买家限用、用量、门槛和商品范围选择最优可用券；代金券提升价格敏感买家的下单概率，订单生成时每单最多使用一张券且存在可用券时必须使用一张最优可用券；订单实付扣减代金券优惠并保存 voucher 快照，同时回写代金券 `used_count/order_count/sales_amount/buyer_count` 和 buyer_journeys 日志。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/models.py backend/apps/api-gateway/app/db.py backend/apps/api-gateway/app/services/shopee_order_simulator.py` 通过；已用 Grep 检查关键 voucher 字段、补字段函数与订单模拟接入点；自查修正了加价购预览小计变化时 voucher bonus 可能重复叠加的问题；已修复 `buyer_journeys` 中代金券候选携带 `datetime` 导致 `json.dumps(debug_payload)` 报错的问题，并用本地 run_id=6/user_id=3/tick=2026-05-08 10:32:03 验证可生成用券订单。
  - 影响范围：影响 Shopee 订单模拟生成订单时的下单概率、买家实付、订单级代金券归因和店铺/商品代金券统计；限时抢购订单仍不叠加代金券；前端订单展示暂未新增代金券字段展示。

### 新增
- 新增 Shopee 店铺/商品代金券接入订单模拟影响设计文档。
  - 涉及文件：`docs/设计文档/42-Shopee店铺商品代金券接入订单模拟影响设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：设计 `shop_voucher` 与 `product_voucher` 接入订单模拟的逻辑口径，明确活动开始、结束、命中和使用统计均以对局游戏时间 tick 判断；定义订单级优惠、不改商品行单价、每单最多使用一张券且存在可用券时必须使用一张最优可用券、商品券 listing/variant 匹配、买家限用、下单概率 bonus、订单级 voucher 快照字段、统计回写和日志记录方案。
  - 口径修正：代金券提升价格敏感买家的下单意愿；下单概率 bonus 只影响是否下单，一旦订单生成，若存在生效可用券，则必须使用一张最优可用券，不再随机判断是否用券。
  - 验证结果：已创建并检查设计文档路径；本次仅文档设计，未运行前后端构建。
  - 影响范围：仅新增设计文档与进度记录；尚未改动订单模拟、数据库字段、后端接口或前端展示。

## 2026-05-07

### 新增
- 接入 Shopee 关注礼代金券创建前后端数据库 Redis 闭环。
  - 涉及文件：`backend/apps/api-gateway/app/models.py`、`backend/apps/api-gateway/app/db.py`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/views/FollowVoucherCreateView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 `shopee_follow_voucher_campaigns` ORM、表注释、字段注释和历史库补字段逻辑；新增关注礼代金券创建页 bootstrap 与创建提交接口；扩展统一代金券列表兼容 `follow_voucher`；接入 Redis bootstrap/列表缓存失效与创建限流；前端关注礼代金券创建页在保留用户手动布局和右侧预览轮播的前提下接入后端 bootstrap、游戏时间领取期限、表单校验和创建提交。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/models.py backend/apps/api-gateway/app/db.py backend/apps/api-gateway/app/api/routes/shopee.py` 通过；`FollowVoucherCreateView.tsx` 与 `ShopeePage.tsx` 前端 LSP 诊断无错误；`npm run build --prefix frontend` 通过（Vite 仅提示既有 chunk 体积 warning）；本次涉及文件 `git diff --check` 通过。全仓 `git diff --check` 受既有 `ShopeeAdsView.tsx` 尾随空格影响未通过。
  - 影响范围：影响 `/shopee/marketing/vouchers/follow-create` 关注礼代金券创建流程和 `/shopee/marketing/vouchers` 列表展示；本次不接入买家关注发券、买家个人 7 个游戏天有效期滚动计算、订单命中、归因、详情/编辑/删除/停止/复制。

### 新增
- 新增 Shopee 关注礼代金券创建前后端数据库 Redis 实现设计文档。
  - 涉及文件：`docs/设计文档/41-Shopee关注礼代金券创建前后端数据库Redis实现设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：设计 `/shopee/marketing/vouchers/follow-create` 关注礼代金券创建能力，明确前端样式和布局沿用用户现有页面；领取期限必须由后端按对局游戏时间初始化，前端 `DateTimePicker` 展示和提交游戏时间，不展示真实世界时间；有效期限固定为领取后 7 个游戏天；同步设计前端 bootstrap/创建提交接口、后端接口、数据库表 `shopee_follow_voucher_campaigns` 与 Redis 缓存/限流/失效策略。
  - 验证结果：已创建并检查设计文档路径；本次仅文档设计，未运行前后端构建。
  - 影响范围：仅新增设计文档与进度记录；尚未改动关注礼代金券前后端业务代码、数据库或 Redis 实现。

### 新增
- 接入 Shopee 右侧栏 Chat Messages 空白抽屉。
  - 涉及文件：`frontend/src/modules/shopee/components/RightSidebar.tsx`、`frontend/src/modules/shopee/components/ChatMessagesDrawer.tsx`、`frontend/src/modules/shopee/ShopeePage.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 Chat Messages 右侧空白抽屉，样式模仿现有通知抽屉的展开宽度、标题区、刷新/收起图标和空状态；右侧栏 Chat Messages 图标改为可点击按钮，点击后打开对应抽屉并与通知抽屉互斥展开。
  - 验证结果：`RightSidebar.tsx`、`ChatMessagesDrawer.tsx`、`ShopeePage.tsx` 前端 LSP 诊断无错误；收尾阶段执行 `git diff --check`。
  - 影响范围：仅影响 Shopee 页面右侧栏 Chat Messages 图标点击后的前端空白抽屉展示；不接入聊天数据、未读数或后端接口。

### 新增
- 接入 Shopee 视频代金券创建前后端数据库 Redis 闭环。
  - 涉及文件：`backend/apps/api-gateway/app/models.py`、`backend/apps/api-gateway/app/db.py`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/views/VideoVoucherCreateView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 `shopee_video_voucher_campaigns` 与 `shopee_video_voucher_items` ORM、表注释、字段注释和历史库补字段逻辑；新增视频代金券创建页 bootstrap、可选商品、创建提交接口；扩展代金券列表兼容 `video_voucher`；接入 Redis bootstrap/可选商品/列表缓存失效与创建限流；前端视频代金券创建页接入后端 bootstrap、商品选择弹窗、已选商品表格、游戏时间初始化和创建提交，视频代金券内部编号由后端生成，不要求前端输入代金券代码。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/models.py backend/apps/api-gateway/app/db.py backend/apps/api-gateway/app/api/routes/shopee.py` 通过；`VideoVoucherCreateView.tsx` 与 `ShopeePage.tsx` 前端 LSP 诊断无错误；收尾阶段执行 `git diff --check`。
  - 影响范围：影响 `/shopee/marketing/vouchers/video-create` 视频代金券创建流程和 `/shopee/marketing/vouchers` 列表展示；本次不接入 Shopee Video 领券、视频场景下单命中、订单归因、详情/编辑/删除/停止/复制或上传商品列表。

### 新增
- 新增 Shopee 视频代金券创建前后端数据库 Redis 实现设计文档。
  - 涉及文件：`docs/设计文档/40-Shopee视频代金券创建前后端数据库Redis实现设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：设计 `/shopee/marketing/vouchers/video-create` 视频代金券创建能力，明确前端样式和布局沿用用户现有页面；代金券使用期限和提前展示时间必须由后端按对局游戏时间初始化，前端 `DateTimePicker` 展示和提交游戏时间；“添加商品”参考商品代金券、专属代金券和直播代金券的商品选择弹窗、已选商品表格和多变体展开提交逻辑；同步设计前端 bootstrap/可选商品/创建提交接口、后端接口、数据库表 `shopee_video_voucher_campaigns`/`shopee_video_voucher_items` 与 Redis 缓存/限流/失效策略。
  - 影响范围：仅新增设计文档与进度记录；尚未改动视频代金券前后端业务代码、数据库或 Redis 实现。

### 新增
- 接入 Shopee 直播代金券创建前后端数据库 Redis 闭环。
  - 涉及文件：`backend/apps/api-gateway/app/models.py`、`backend/apps/api-gateway/app/db.py`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/views/LiveVoucherCreateView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 `shopee_live_voucher_campaigns` 与 `shopee_live_voucher_items` ORM、表注释、字段注释和历史库补字段逻辑；新增直播代金券创建页 bootstrap、可选商品、创建提交接口；扩展代金券代码检查与列表兼容 `live_voucher`；接入 Redis bootstrap/可选商品/代码检查/列表缓存失效与创建限流；前端直播代金券创建页接入后端 bootstrap、代码校验、商品选择弹窗、已选商品表格、游戏时间初始化和创建提交。
  - 验证结果：`LiveVoucherCreateView.tsx` 与 `ShopeePage.tsx` 前端 LSP 诊断无错误；后端语法与空白字符校验见本次最终验证。
  - 影响范围：影响 `/shopee/marketing/vouchers/live-create` 直播代金券创建流程、`/shopee/marketing/vouchers` 列表展示和代金券代码检查接口；本次不接入直播间领券、直播场景下单命中、订单归因、详情/编辑/删除/停止/复制或上传商品列表。

### 新增
- 新增 Shopee 直播代金券创建前后端数据库 Redis 实现设计文档。
  - 涉及文件：`docs/设计文档/39-Shopee直播代金券创建前后端数据库Redis实现设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：设计 `/shopee/marketing/vouchers/live-create` 直播代金券创建能力，明确前端样式和布局沿用用户现有页面；代金券使用期限和提前展示时间必须由后端按对局游戏时间初始化，前端 `DateTimePicker` 展示和提交游戏时间；“添加商品”参考商品代金券当前按钮、商品选择弹窗、已选商品表格和多变体展开提交逻辑；同步设计前端 bootstrap/可选商品/代码检查/创建提交接口、后端接口、数据库表 `shopee_live_voucher_campaigns`/`shopee_live_voucher_items` 与 Redis 缓存/限流/失效策略。
  - 影响范围：仅新增设计文档与进度记录；尚未改动直播代金券前后端业务代码、数据库或 Redis 实现。

### 新增
- 接入 Shopee 营销中心运费促销空白页与创建空白页。
  - 涉及文件：`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/components/Header.tsx`、`frontend/src/modules/shopee/components/Sidebar.tsx`、`frontend/src/modules/shopee/views/MarketingCentreView.tsx`、`frontend/src/modules/shopee/views/ShippingFeePromotionView.tsx`、`frontend/src/modules/shopee/views/ShippingFeePromotionCreateView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 `/shopee/marketing/shipping-fee-promotion` 前端路由和运费促销空白页；营销中心“运费促销”工具卡可进入该页面；页面按用户手动优化后的运费促销列表布局保留 Create Now 入口；点击 Create Now 可进入 `/shopee/marketing/shipping-fee-promotion/create` 创建空白页，创建页使用 1360px 宽度且不显示左侧菜单栏；顶部面包屑显示“营销中心 > 运费促销 > 创建运费促销”。
  - 验证结果：`ShopeePage.tsx`、`Header.tsx`、`Sidebar.tsx`、`MarketingCentreView.tsx`、`ShippingFeePromotionView.tsx`、`ShippingFeePromotionCreateView.tsx` 前端 LSP 诊断无错误；`git diff --check` 通过。按用户要求未执行 `npm run build`，未执行 init。
  - 影响范围：仅新增 `/shopee/marketing/shipping-fee-promotion` 与 `/shopee/marketing/shipping-fee-promotion/create` 前端占位页和导航入口；不接入后端接口、数据库、Redis 或营销业务逻辑。

### 新增
- 接入 Shopee 专属代金券创建前后端数据库 Redis 闭环。
  - 涉及文件：`backend/apps/api-gateway/app/models.py`、`backend/apps/api-gateway/app/db.py`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/views/PrivateVoucherCreateView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 `shopee_private_voucher_campaigns` 与 `shopee_private_voucher_items` ORM、表注释、字段注释和历史库补字段逻辑；新增专属代金券创建页 bootstrap、可选商品、创建提交接口；扩展代金券代码检查与列表兼容 `private_voucher`；接入 Redis bootstrap/可选商品/代码检查/列表缓存失效与创建限流；前端专属代金券创建页接入后端 bootstrap、代码校验、商品选择弹窗、已选商品表格、游戏时间初始化和创建提交。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/models.py backend/apps/api-gateway/app/db.py backend/apps/api-gateway/app/api/routes/shopee.py` 通过；`PrivateVoucherCreateView.tsx` 与 `ShopeePage.tsx` 前端 LSP 诊断无错误；`git diff --check` 通过。按用户要求未执行 `npm run build`，未执行 init。
  - 影响范围：影响 `/shopee/marketing/vouchers/private-create` 专属代金券创建流程、`/shopee/marketing/vouchers` 列表展示和代金券代码检查接口；本次不接入订单模拟命中专属代金券、买家领取、详情/编辑/删除/停止/复制或上传商品列表。

### 新增
- 新增 Shopee 专属代金券创建前后端数据库 Redis 实现设计文档。
  - 涉及文件：`docs/设计文档/38-Shopee专属代金券创建前后端数据库Redis实现设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：设计 `/shopee/marketing/vouchers/private-create` 专属代金券创建能力，明确前端样式和布局沿用现有页面；代金券使用期限必须由后端按对局游戏时间初始化，前端日期选择器不显示真实世界当前时间；“添加商品”参考商品代金券当前按钮、弹窗、已选商品表格和多变体展开提交逻辑；同步设计前端接口、后端 bootstrap/可选商品/创建接口、统一代码检查、数据库表 `shopee_private_voucher_campaigns`/`shopee_private_voucher_items` 与 Redis 缓存/限流/失效策略。
  - 影响范围：仅新增设计文档与进度记录；尚未改动专属代金券前后端业务代码、数据库或 Redis 实现。

### 修复
- 补充 Shopee 商品代金券明细表 `product_id` 历史库漂移修复。
  - 涉及文件：`backend/apps/api-gateway/app/db.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：核查本地 Docker MySQL `cbec_sim.shopee_product_voucher_items` 实际表结构，确认当前表已存在 `product_id` 字段；同时在 `_ensure_shopee_product_voucher_tables()` 中补充旧库缺少 `product_id` 时的自动增补逻辑，避免其他环境商品代金券明细缺少源商品 ID 字段。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/models.py backend/apps/api-gateway/app/db.py backend/apps/api-gateway/app/api/routes/shopee.py` 通过。
  - 影响范围：仅影响商品代金券明细表历史库结构补齐逻辑；不改变当前已存在字段的 Docker MySQL 表，也不改变前端页面或创建接口入参。

### 优化
- 优化 Shopee 商品代金券创建页适用商品展示。
  - 涉及文件：`frontend/src/modules/shopee/views/ProductVoucherCreateView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：商品代金券添加商品后，适用商品区域不再只在按钮上显示数量，而是展示商品表格；表格包含商品主图、名称、ID/变体数量、原价、库存和删除操作，表头对齐官方 `Products / Original Price / Stock / Action` 结构；保留右侧 `Add Products` 入口用于继续追加商品。
  - 验证结果：`npm run build --prefix frontend` 通过（Vite 仅提示既有 chunk 体积 warning）。
  - 影响范围：仅影响 `/shopee/marketing/vouchers/product-create` 已选适用商品展示与删除交互；不改变商品选择弹窗、后端创建接口或订单模拟逻辑。

### 修复
- 修正 Shopee 商品代金券选中主商品后未提交变体与库存快照字段不兼容的问题。
  - 涉及文件：`backend/apps/api-gateway/app/models.py`、`backend/apps/api-gateway/app/db.py`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/views/ProductVoucherCreateView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：商品代金券可选商品接口返回主商品行时携带全部可售变体 ID；前端确认添加商品后，创建提交会将主商品自动展开为所有可售变体，避免只提交 `variant_id=null` 导致多变体商品创建失败；商品代金券明细库存快照 ORM、初始化补字段和字段注释改回兼容现有数据库的 `stock_snapshot` 字段，避免插入时报 `Field 'stock_snapshot' doesn't have a default value`。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/models.py backend/apps/api-gateway/app/db.py backend/apps/api-gateway/app/api/routes/shopee.py` 通过；`npm run build --prefix frontend` 通过（Vite 仅提示既有 chunk 体积 warning）。
  - 影响范围：影响 `/shopee/marketing/vouchers/product-create` 添加商品与创建提交；不改变店铺代金券、商品代金券列表展示或订单模拟逻辑。

### 修复
- 修正 Shopee 代金券提前展示时间默认值使用真实时间的问题。
  - 涉及文件：`frontend/src/modules/shopee/views/ShopVoucherCreateView.tsx`、`frontend/src/modules/shopee/views/ProductVoucherCreateView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：店铺代金券与商品代金券创建页勾选“提前展示代金券”时，如后端未返回 `display_start_at`，前端不再让日期选择器回落到浏览器真实当前时间，而是基于后端返回的对局游戏开始时间向前 1 小时生成游戏时间默认值；提前展示时间选择器继续以代金券开始游戏时间作为上限。
  - 验证结果：`npm run build --prefix frontend` 通过（Vite 仅提示既有 chunk 体积 warning）。
  - 影响范围：影响 `/shopee/marketing/vouchers/create` 与 `/shopee/marketing/vouchers/product-create` 的提前展示时间默认显示与提交口径；不改变后端解析、活动起止时间或订单模拟逻辑。

### 新增
- 接入 Shopee 商品代金券创建前后端数据库 Redis 闭环。
  - 涉及文件：`backend/apps/api-gateway/app/models.py`、`backend/apps/api-gateway/app/db.py`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/views/ProductVoucherCreateView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：对齐 `shopee_product_voucher_campaigns` 与 `shopee_product_voucher_items` ORM、表字段注释和历史库补字段逻辑；新增商品代金券创建页 bootstrap、可选商品、创建提交接口；扩展代金券代码检查为店铺/商品代金券共享唯一性校验；扩展代金券列表兼容商品代金券；接入 Redis 可选商品缓存、代码检查缓存、列表缓存失效与创建限流；前端商品代金券创建页在保留现有布局前提下接入接口数据、代码校验、表单校验和创建提交。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/models.py backend/apps/api-gateway/app/db.py backend/apps/api-gateway/app/api/routes/shopee.py` 通过；`npm run build --prefix frontend` 通过（Vite 仅提示既有 chunk 体积 warning）。
  - 影响范围：影响 `/shopee/marketing/vouchers/product-create` 商品代金券创建流程、`/shopee/marketing/vouchers` 代金券列表展示和代金券代码检查接口；本次不接入订单模拟命中商品代金券、买家领取、详情/编辑/删除/停止/复制或上传商品列表。

## 2026-05-06

### 新增
- 接入 Shopee 专属及内容代金券创建空白页。
  - 涉及文件：`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/components/Header.tsx`、`frontend/src/modules/shopee/components/Sidebar.tsx`、`frontend/src/modules/shopee/views/ShopVoucherView.tsx`、`frontend/src/modules/shopee/views/PrivateVoucherCreateView.tsx`、`frontend/src/modules/shopee/views/LiveVoucherCreateView.tsx`、`frontend/src/modules/shopee/views/VideoVoucherCreateView.tsx`、`frontend/src/modules/shopee/views/FollowVoucherCreateView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 `/shopee/marketing/vouchers/private-create`、`/shopee/marketing/vouchers/live-create`、`/shopee/marketing/vouchers/video-create`、`/shopee/marketing/vouchers/follow-create` 前端路由；代金券页对应“专属代金券 / 直播代金券 / 视频代金券 / 关注礼代金券”的“创建”按钮可进入各自独立页面；4 个新页面统一复用店铺代金券创建页的布局节奏，保留基础信息、奖励设置、展示与适用商品、底部操作区和右侧预览。
  - 影响范围：仅新增四个代金券创建空白页与导航入口；暂不实现各类型专属表单字段、真实提交、后端接口、数据库或订单模拟影响。

### 新增
- 新增 Shopee 商品代金券创建前后端数据库 Redis 实现设计文档。
  - 涉及文件：`docs/设计文档/37-Shopee商品代金券创建前后端数据库Redis实现设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：设计 `/shopee/marketing/vouchers/product-create` 商品代金券创建能力的前端接口对接、后端 bootstrap/可选商品/代码检查/创建/列表兼容接口、数据库表 `shopee_product_voucher_campaigns` 与 `shopee_product_voucher_items`、Redis bootstrap/可选商品/代码检查/列表缓存与创建限流；明确前端布局不再修改，所有创建页时间显示和提交均使用对局游戏时间，不展示真实世界时间。
  - 影响范围：仅新增设计文档与进度记录；尚未改动商品代金券后端接口、数据库、Redis 或创建提交逻辑。

### 新增
- 接入 Shopee 商品代金券创建空白页与商品选择弹窗。
  - 涉及文件：`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/components/Header.tsx`、`frontend/src/modules/shopee/components/Sidebar.tsx`、`frontend/src/modules/shopee/views/ShopVoucherView.tsx`、`frontend/src/modules/shopee/views/ProductVoucherCreateView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 `/shopee/marketing/vouchers/product-create` 前端路由和商品代金券创建页；代金券页“商品代金券”的“创建”按钮可进入该页；页面对齐当前店铺代金券创建页布局，隐藏左侧菜单栏；“添加商品”按钮复用限时抢购创建页商品选择弹窗界面，包含选择商品/上传商品列表 Tab、分类下拉、搜索、仅显示可参与活动商品、商品表格、空状态和确认/取消，并临时记录已选商品数量。
  - 影响范围：影响 `/shopee/marketing/vouchers/product-create` 前端页面和商品选择弹窗展示；商品数据暂复用现有单品折扣可选商品接口，不新增商品代金券后端接口、数据库、Redis、创建提交或订单模拟影响。

### 新增
- 接入 Shopee 店铺代金券创建前后端数据库 Redis 闭环。
  - 涉及文件：`backend/apps/api-gateway/app/models.py`、`backend/apps/api-gateway/app/db.py`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/views/ShopVoucherCreateView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 `shopee_shop_voucher_campaigns` ORM/表字段注释；实现店铺代金券列表、创建页 bootstrap、代码可用性检查和创建提交接口；接入 Redis bootstrap/代码检查/列表缓存、创建限流和缓存失效；前端创建页改为读取后端游戏时间默认值、受控表单、代码校验和提交落库，并将提前展示具体时间提交到后端；代金券列表和表现面板改为读取真实接口数据。
  - 影响范围：影响 `/shopee/marketing/vouchers` 与 `/shopee/marketing/vouchers/create` 店铺代金券管理和创建流程；代金券使用期限按对局游戏时间展示和提交，不再使用硬编码真实世界时间。订单模拟代金券归因仍待后续接入。

### 优化
- 同步 Shopee 店铺代金券创建设计文档中的奖励设置与新增接口。
  - 涉及文件：`docs/设计文档/36-Shopee店铺代金券创建前后端数据库Redis实现设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：根据当前创建页奖励设置，补充固定金额/百分比折扣、百分比最大折扣金额“设置金额/无限制”、展示设置 `all_pages/specific_channels/code_only` 与特定渠道 `checkout_page`；新增 `GET /shopee/runs/{run_id}/marketing/vouchers/code/check` 代金券代码可用性检查接口设计，并同步请求/响应、校验规则、前端状态和初始化流程。
  - 影响范围：仅影响店铺代金券实现设计文档与进度记录；尚未改动前后端业务代码或数据库结构。

### 新增
- 新增 Shopee 店铺代金券创建前后端数据库 Redis 实现设计文档。
  - 涉及文件：`docs/设计文档/36-Shopee店铺代金券创建前后端数据库Redis实现设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：设计店铺代金券创建能力的前端接口对接、后端 bootstrap/创建/列表接口、数据库表 `shopee_shop_voucher_campaigns`、Redis bootstrap/列表/表现缓存与创建限流，以及后续订单模拟归因接入口径；明确前端样式和布局基本不改，重点完成接口与数据闭环。
  - 影响范围：仅新增设计文档与进度记录；尚未改动前端业务逻辑、后端接口、数据库或 Redis 代码。

### 优化
- 调整 Shopee 店铺代金券创建页日期选择器样式。
  - 涉及文件：`frontend/src/modules/shopee/views/ShopVoucherCreateView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：将 `/shopee/marketing/vouchers/create` 页面的“代金券使用期限”从原生 `datetime-local` 输入改为复用 Shopee 现有 `DateTimePicker`，保持与创建单品折扣页一致的输入框宽度、弹层和“至”分隔样式。
  - 影响范围：仅影响店铺代金券创建页日期选择器前端展示；不改变代金券创建逻辑、数据提交或接口。

### 新增
- 接入 Shopee 店铺代金券创建空白页。
  - 涉及文件：`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/components/Header.tsx`、`frontend/src/modules/shopee/components/Sidebar.tsx`、`frontend/src/modules/shopee/views/ShopVoucherView.tsx`、`frontend/src/modules/shopee/views/ShopVoucherCreateView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 `/shopee/marketing/vouchers/create` 前端路由和店铺代金券创建空白页；代金券页“店铺代金券”的“创建”按钮可进入该页；页面沿用单品折扣创建页布局节奏，隐藏左侧菜单栏，预留基础信息、店铺代金券设置和底部操作区；顶部面包屑显示“营销中心 > 代金券 > 创建店铺代金券”。
  - 验证结果：`ShopeePage.tsx`、`Header.tsx`、`ShopVoucherView.tsx`、`ShopVoucherCreateView.tsx` LSP 诊断无错误。
  - 影响范围：仅新增店铺代金券创建空白页与入口跳转；暂不实现创建表单字段校验、真实提交、接口或订单模拟影响。

## 2026-04-30

### 新增
- 接入 Shopee 营销中心 Shopee 广告空白页。
  - 涉及文件：`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/components/Header.tsx`、`frontend/src/modules/shopee/components/Sidebar.tsx`、`frontend/src/modules/shopee/views/MarketingCentreView.tsx`、`frontend/src/modules/shopee/views/ShopeeAdsView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 `/shopee/marketing/shopee-ads` 前端路由和 Shopee 广告空白页；营销中心“Shopee 广告”工具卡与左侧菜单可进入该页面；页面包含广告表现指标、创建广告按钮、广告列表、状态 Tab、搜索栏和空表格占位；顶部面包屑显示“营销中心 > Shopee 广告”。
  - 验证结果：`ShopeePage.tsx`、`Header.tsx`、`Sidebar.tsx`、`ShopeeAdsView.tsx` LSP 诊断无错误；`npm run build --prefix frontend` 通过（Vite 仅提示既有 chunk 体积 warning）。
  - 影响范围：仅新增 Shopee 广告空白页与导航入口；暂不实现广告创建、列表真实数据、投放模拟或订单归因。

### 优化
- 优化 Shopee 营销中心代金券前端页面布局。
  - 涉及文件：`frontend/src/modules/shopee/views/ShopVoucherView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：记录用户手动优化后的 `/shopee/marketing/vouchers` 页面；页面从空白占位升级为代金券管理页，包含创建代金券入口分组、代金券表现面板、状态 Tab、搜索栏、mock 代金券列表、操作按钮和分页占位。
  - 影响范围：仅影响代金券页面前端展示与文档记录；暂不接入代金券真实创建、列表接口、订单模拟或营销归因。

### 新增
- 接入 Shopee 营销中心代金券空白页。
  - 涉及文件：`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/components/Header.tsx`、`frontend/src/modules/shopee/components/Sidebar.tsx`、`frontend/src/modules/shopee/views/MarketingCentreView.tsx`、`frontend/src/modules/shopee/views/ShopVoucherView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 `/shopee/marketing/vouchers` 前端路由和代金券空白页；营销中心“代金券”工具卡与左侧菜单可进入该页面；页面沿用限时抢购页布局节奏，包含表现面板、活动列表、状态 Tab、时间筛选、创建按钮和空表格占位；顶部面包屑显示“营销中心 > 代金券”。
  - 影响范围：仅新增代金券空白页与导航入口；暂不实现代金券创建、列表真实数据、订单模拟或营销归因。

### 修复
- 修正 Shopee 我的订单限时抢购活动文案。
  - 涉及文件：`frontend/src/modules/shopee/views/MyOrdersView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：我的订单列表中 `flash_sale` 归因订单直接显示“店铺限时抢购活动”，不再拼接“单品折扣：”前缀；同步清理该页面当前未使用的订单摘要图片辅助逻辑。
  - 影响范围：仅影响 `/shopee/orders` 我的订单列表营销活动文案；不改变订单归因、订单模拟、限时抢购统计或活动数据页。

### 修复
- 修正 Shopee 限时抢购数据页商品图与未启用 SKU 活动库存展示。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：限时抢购数据页商品排名接口的商品行图片优先读取 listing 主图，不再使用 SKU 变体快照图作为主商品图；未启用的活动 SKU 变体活动库存返回 `0`。
  - 影响范围：仅影响 `/shopee/marketing/flash-sale/data?campaign_id=...` 商品排名展示；不改变活动创建、详情页、订单模拟、销量统计或下单概率逻辑。

### 新增
- 接入 Shopee 限时抢购浏览点击模拟与数据页真实统计。
  - 涉及文件：`backend/apps/api-gateway/app/models.py`、`backend/apps/api-gateway/app/db.py`、`backend/apps/api-gateway/app/services/shopee_order_simulator.py`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/views/ShopFlashSaleDataView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 `shopee_flash_sale_traffic_events` 限时抢购浏览/点击事件表 ORM、索引、唯一约束与表字段注释；订单模拟器按活跃买家和有效活动商品生成 `view/click` 事件，且仅在浏览成功后判断点击；数据页新增概览、商品排名和导出接口，按事件表统计商品浏览量、商品点击数与 CTR，提醒设置数固定为 `0`；前端数据页接入真实接口展示指标卡和商品排名。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/models.py backend/apps/api-gateway/app/db.py backend/apps/api-gateway/app/services/shopee_order_simulator.py backend/apps/api-gateway/app/api/routes/shopee.py` 通过；`ShopFlashSaleDataView.tsx` 与 `ShopeePage.tsx` 前端 LSP 诊断无错误。
  - 影响范围：影响 Shopee 限时抢购浏览/点击事件生成、数据页概览/商品排名/导出接口和前端数据页展示；不修改现有候选商品评分、`base_order_prob`、`flash_sale_order_prob` 或最终下单概率逻辑。

### 调整
- 调整 Shopee 限时抢购浏览点击模拟设计中的基础浏览概率。
  - 涉及文件：`docs/设计文档/35-Shopee限时抢购浏览点击模拟与下单影响设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：将限时抢购浏览模拟首版 `base_view_prob` 固定为 `0.30`，并将浏览概率上限调整为 `0.75`；补充说明该基础概率是在买家已活跃、活动商品具备展示资格后的条件概率，不代表全买家无条件浏览率。
  - 影响范围：仅调整设计文档与进度记录；尚未改动前端、后端、数据库或 Redis 业务代码。

### 新增
- 新增 Shopee 限时抢购浏览点击模拟与下单影响设计文档。
  - 涉及文件：`docs/设计文档/35-Shopee限时抢购浏览点击模拟与下单影响设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：设计限时抢购 `view/click` 流量事件模拟、事件表字段与索引、数据页浏览量/点击量/CTR 统计口径、浏览点击对候选商品权重与下单概率的间接影响、Redis 缓存失效和验收标准；提醒设置数本期固定为 `0`。
  - 影响范围：仅新增设计文档与进度记录；尚未改动前端、后端、数据库或 Redis 业务代码。

- 新增 Shopee 限时抢购数据页前后端数据库 Redis 打通设计文档。
  - 涉及文件：`docs/设计文档/34-Shopee限时抢购数据页前后端数据库Redis打通设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：设计 `/shopee/marketing/flash-sale/data?campaign_id=...` 数据页从静态占位切换为真实数据的接入方案，覆盖活动基础信息、关键指标、商品排名、订单类型切换、导出接口、明细级订单归因统计、数据库复用/事件表预留、Redis 缓存与失效规则。
  - 影响范围：仅新增设计文档与进度记录；尚未改动前端、后端、数据库或 Redis 业务代码。

### 修复
- 修正 Shopee 限时抢购详情页商品条件类目与主图展示。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/views/ShopFlashSaleDetailView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：后端活动详情按活动商品对应 listing/product 计算真实类目并返回 `category_key/category_label`，旧详情缓存改用 v2 key 避免继续读取 `全部`；前端商品条件规则按详情商品类目请求，只展示当前活动商品对应类别的条件 Tab；限时抢购详情商品图片统一返回主商品图，不再优先使用 SKU 变体图；变体明细按启用优先排序，停用变体置灰并排在底部；详情页顶部面包屑修正为“营销中心 > 我的店铺限时抢购 > 限时抢购详情”。
  - 影响范围：仅影响 `/shopee/marketing/flash-sale/detail?campaign_id=...` 商品条件、商品图片、变体明细和顶部面包屑展示；不改变活动创建、列表、订单模拟或统计口径。

### 新增
- 接入 Shopee 限时抢购数据空白页。
  - 涉及文件：`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/components/Header.tsx`、`frontend/src/modules/shopee/views/ShopFlashSaleView.tsx`、`frontend/src/modules/shopee/views/ShopFlashSaleDataView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 `/shopee/marketing/flash-sale/data?campaign_id=...` 数据页空白布局，活动列表“数据”按钮可携带活动 ID 跳转；页面预留指标卡、趋势图表区域和商品表现表格；顶部面包屑显示“营销中心 > 我的店铺限时抢购 > 限时抢购数据”。
  - 影响范围：仅新增限时抢购数据页前端入口与空白页布局；暂不接入真实数据接口，不改变活动创建、详情、订单模拟或统计口径。

- 接入 Shopee 限时抢购详情页数据展示。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/views/ShopFlashSaleView.tsx`、`frontend/src/modules/shopee/views/ShopFlashSaleDetailView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：`/shopee/marketing/flash-sale/detail?campaign_id=...` 详情页读取活动详情和商品条件规则，展示状态、活动时间段、商品条件、活动商品、变体原价、折后价、折扣、活动库存、库存、订单限购和启停状态；后端活动商品详情响应补充商品状态字段。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/api/routes/shopee.py` 通过；`npm run build --prefix frontend` 通过（Vite 仅提示既有 chunk 体积 warning）。
  - 影响范围：影响限时抢购详情页展示；不改变活动创建、列表筛选、订单模拟和统计口径。

- 接入 Shopee 限时抢购表现当前游戏周统计。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/views/ShopFlashSaleView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 `/shopee/runs/{run_id}/marketing/flash-sale/performance` 接口，按当前游戏日期所在周统计限时抢购销售额、订单、买家数和 CTR；前端表现面板读取真实接口数据，不再展示写死的表现指标和真实世界日期区间。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/api/routes/shopee.py` 通过；`npm run build --prefix frontend` 通过（Vite 仅提示既有 chunk 体积 warning）。
  - 影响范围：影响 `/shopee/marketing/flash-sale` 顶部“我的店铺限时抢购表现”展示；统计区间使用游戏时间当前周，不使用真实世界日期。

### 优化
- 优化 Shopee 限时抢购活动列表前端展示。
  - 涉及文件：`frontend/src/modules/shopee/views/ShopFlashSaleView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：活动列表状态列中 `进行中` 状态改为绿色浅底标签，未开始/即将开始/已结束继续保留灰色样式；删除列表空数据时展示的写死模拟活动和写死分页器，改为真实数据为空时显示“暂无限时抢购活动”。
  - 影响范围：仅影响 `/shopee/marketing/flash-sale` 活动列表前端展示；不改变活动状态判断、筛选、创建或订单模拟逻辑。

### 新增
- 接入 Shopee 限时抢购对订单模拟的概率、成交价、库存和归因影响。
  - 涉及文件：`backend/apps/api-gateway/app/services/shopee_order_simulator.py`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`backend/apps/api-gateway/tests/test_api.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：订单模拟器加载当前游戏 tick 有效的限时抢购活动，命中后使用 `flash_price` 作为主商品成交价，按折扣吸引力与时间段倍率提升下单概率并限制上限；限时抢购与单品折扣、套餐优惠、加价购、满额赠互斥；按创建时设置的活动库存和买家活动 SKU 累计购买件数控制命中；订单生成后更新活动商品 `sold_qty`、活动 `order_count/sales_amount` 和订单/明细营销归因；自动订单补跑窗口覆盖限时抢购时临时切换为 1 游戏小时粒度；订单模拟后同步失效限时抢购缓存。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/services/shopee_order_simulator.py backend/apps/api-gateway/app/api/routes/shopee.py` 通过；`PYTHONPATH=backend/apps/api-gateway pytest backend/apps/api-gateway/tests/test_api.py -q -k "flash_sale_price_probability or one_hour_when_flash_sale_overlaps or use_discount_price"` 通过。
  - 影响范围：影响 Shopee 自动/手动订单模拟、限时抢购活动销量统计、订单营销归因和限时抢购活动缓存刷新；普通无有效限时抢购窗口时仍保持原 8 游戏小时自动补跑粒度。

- 优化 Shopee 限时抢购接入订单模拟概率设计文档。
  - 涉及文件：`docs/设计文档/33-Shopee限时抢购接入订单模拟概率设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：明确限时抢购命中后主商品不再叠加单品折扣、套餐优惠、加价购或满额赠；活动库存以创建活动时设置的 `activity_stock_limit` 为准；补充活动库存防超卖校验；买家限购按活动 SKU 累计购买件数统计，不按订单数统计。
  - 影响范围：仅优化设计文档与进度记录；尚未改动订单模拟业务代码。

- 新增 Shopee 限时抢购接入订单模拟概率设计文档。
  - 涉及文件：`docs/设计文档/33-Shopee限时抢购接入订单模拟概率设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：定义限时抢购接入订单模拟的时间压缩口径、补跑窗口内 1 游戏小时临时粒度、各时间段概率倍率、概率上限、活动匹配、营销互斥优先级、活动库存/限购、订单归因、Redis 缓存失效和验收标准。
  - 影响范围：仅新增设计文档与进度记录；尚未改动订单模拟业务代码。

### 修复
- 修正 Shopee 限时抢购活动列表展示时间口径。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增限时抢购活动展示时间格式化函数，列表、详情、启停响应的 `display_time` 改为基于游戏时间转换后的时分展示；活动状态判断继续沿用 `current_tick` 与 `start_tick/end_tick` 的原逻辑。
  - 影响范围：影响 `/shopee/marketing/flash-sale` 活动列表和限时抢购详情/启停返回的时间文案；不改变活动开始、进行中、结束判断逻辑。

- 调整 Shopee 限时抢购创建提交保留停用变体。
  - 涉及文件：`frontend/src/modules/shopee/views/ShopFlashSaleCreateView.tsx`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：创建页提交时不再过滤停用变体，而是提交全部已选变体并携带 `status=active/disabled`；后端接收并校验启停状态，活动商品落库时写入对应 `status`，时间段名额与重复冲突仍只按启用商品计算。
  - 影响范围：影响 `/shopee/marketing/flash-sale/create` 正式创建提交口径；停用变体会作为活动商品记录保留但不占用启用商品名额。

## 2026-04-29

### 修复
- 完善 Shopee 限时抢购已选商品变体编辑。
  - 涉及文件：`frontend/src/modules/shopee/views/ShopFlashSaleCreateView.tsx`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：添加主商品后按后端返回的 `variations` 展开全部变体到已选商品区域；在保留现有布局样式的前提下，将折后价和活动库存改为受控可编辑输入，折扣标签随折后价自动重算；启用/停用开关写入变体状态，正式创建仅提交启用变体。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/api/routes/shopee.py` 通过；`npm run build --prefix frontend` 通过（Vite 仅提示既有 chunk 体积 warning）。
  - 影响范围：仅影响 `/shopee/marketing/flash-sale/create` 已选商品配置区的变体展示、编辑与提交口径；不改变添加商品弹窗布局、商品条件类目和时间段选择逻辑。

- 修正 Shopee 限时抢购添加商品弹窗价格区间展示。
  - 涉及文件：`frontend/src/modules/shopee/views/ShopFlashSaleCreateView.tsx`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：限时抢购添加商品弹窗价格列改为优先展示后端返回的 `price_range_label`；后端主商品候选行按所有可售变体价格计算 `RM 最低价 - RM 最高价`，同价时显示单个价格。
  - 影响范围：仅影响 `/shopee/marketing/flash-sale/create` 添加商品弹窗价格列展示；不改变活动价格默认值、库存、商品选择和创建提交逻辑。

- 修正 Shopee 限时抢购添加商品弹窗商品 ID 展示。
  - 涉及文件：`frontend/src/modules/shopee/views/ShopFlashSaleCreateView.tsx`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：添加商品弹窗商品名称下方副标题从“单规格商品 / SKU”改为 `ID: {listing_id}`；后端主商品候选行不再回填首个变体 SKU，避免主商品行继续展示变体编码。
  - 影响范围：仅影响 `/shopee/marketing/flash-sale/create` 添加商品弹窗商品副标题展示；不改变候选商品筛选、主图、价格、库存和创建提交逻辑。

- 修正 Shopee 限时抢购添加商品弹窗商品展示口径。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：限时抢购添加商品弹窗候选接口不再按每个变体展开多行，改为每个上架商品只返回一行主商品；商品图片固定使用 `shopee_listings.cover_url` 主图，库存汇总可售变体库存，价格取可售变体最低价。
  - 影响范围：仅影响 `/shopee/marketing/flash-sale/create` 添加商品弹窗候选商品展示；不改变已选商品区域、时间段、商品条件和正式创建接口。

- 修正 Shopee 限时抢购创建页商品条件类目来源。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：`/shopee/marketing/flash-sale/create` 商品条件 Tab 改为按当前对局库存 `inventory_lots` 关联选品表 `market_products.category` 生成；候选商品筛选与商品行类目同步使用选品表类目，避免继续显示限时抢购默认规则类目或 Shopee 叶子类目。
  - 本地数据复核：最新对局 `run_id=5` 库存商品对应选品类目为 `美妆个护`，因此创建页商品条件应展示 `美妆个护`。
  - 影响范围：仅影响限时抢购创建页商品条件类目和添加商品弹窗按类目筛选口径；不改变限时抢购活动时间段、创建提交和订单模拟逻辑。

### 新增
- 调整 Shopee 限时抢购创建页活动时间段日期选择。
  - 涉及文件：`frontend/src/modules/shopee/views/ShopFlashSaleCreateView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：将活动时间段弹窗左侧日历从固定 2026 年 4 月 29/30 日改为按后端返回的游戏内日期当天初始化展示，不使用真实世界系统日期兜底；日期格子可点击选择，选择后重新加载对应日期的限时抢购时间段；选择完成后主按钮展示“年月日 + 时间段”，并保持原有弹窗视觉样式；商品条件类目改为只返回当前对局 live 且有库存/价格的商品命中类目。
  - 影响范围：影响 `/shopee/marketing/flash-sale/create` 活动时间段日期选择、按钮展示与商品条件类目展示；后端限时抢购 slots 将前端日期按游戏日期解析为真实 tick 后判断可选状态和创建活动。

- 调整 Shopee 限时抢购创建页添加商品弹窗。
  - 涉及文件：`frontend/src/modules/shopee/views/ShopFlashSaleCreateView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：将限时抢购创建页“添加商品”从直接加入首个候选商品改为参考 `/shopee/marketing/discount/create?type=discount` 的选择商品弹窗；接入分类下拉、搜索字段、关键字搜索、重置、仅显示可参与商品、多选、全选、加载态、空状态和上传商品列表占位，确认后批量加入已选限时抢购商品。
  - 验证结果：`ShopFlashSaleCreateView.tsx` LSP diagnostics 无报错；`npm run build --prefix frontend` 通过（Vite 仅提示既有 chunk 体积 warning）。
  - 影响范围：仅影响 `/shopee/marketing/flash-sale/create` 添加商品交互；后端接口和已创建活动列表口径不变。

- 打通 Shopee 我的店铺限时抢购前后端数据库 Redis。
  - 涉及文件：`backend/apps/api-gateway/app/models.py`、`backend/apps/api-gateway/app/db.py`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/views/ShopFlashSaleView.tsx`、`frontend/src/modules/shopee/views/ShopFlashSaleCreateView.tsx`、`cbec_sim.sql`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增限时抢购活动/商品、草稿/草稿商品、时间段配置、类目规则配置表模型与注释；初始化默认 4 个时间段和 8 个类目条件；新增 bootstrap、slots、category-rules、eligible-products、drafts、campaigns、detail、toggle 接口；接入 Redis 缓存、缓存失效与限流；列表页和创建页在保留现有样式的前提下接入真实接口数据与正式创建提交。
  - 验证结果：`python -m py_compile backend/apps/api-gateway/app/models.py backend/apps/api-gateway/app/db.py backend/apps/api-gateway/app/api/routes/shopee.py` 通过；`npm run build --prefix frontend` 通过（Vite 仅提示既有 chunk 体积 warning）。
  - 影响范围：`/shopee/marketing/flash-sale` 可读取真实限时抢购活动列表；`/shopee/marketing/flash-sale/create` 可读取游戏时间、时间段、商品条件、候选商品并创建正式活动；历史回溯模式保持只读。

- 新增 Shopee 我的店铺限时抢购前后端数据库 Redis 打通设计文档。
  - 涉及文件：`docs/设计文档/32-Shopee我的店铺限时抢购前后端数据库Redis打通设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：设计 `/shopee/marketing/flash-sale/create` 创建页与 `/shopee/marketing/flash-sale` 列表页的数据链路，覆盖后端接口、数据库表、Redis Key、缓存失效、商品准入、时间段规则、订单模拟预留口径和验收标准。
  - 影响范围：仅新增设计文档与进度记录；尚未改动后端、数据库、Redis 或前端接口接入代码。

- 新增 Shopee 我的店铺限时抢购创建空白页。
  - 涉及文件：`frontend/src/modules/shopee/views/ShopFlashSaleCreateView.tsx`、`frontend/src/modules/shopee/views/ShopFlashSaleView.tsx`、`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/components/Header.tsx`、`frontend/src/modules/shopee/components/Sidebar.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 `/shopee/marketing/flash-sale/create` 前端页面，布局参考创建单品折扣页面，预留基础信息、活动时间、商品配置、保存草稿与确认按钮；限时抢购列表页“创建”按钮已跳转到该页面，面包屑显示“营销中心 / 我的店铺限时抢购 / 创建限时抢购”，并与单品折扣创建页一致隐藏左侧菜单栏。
  - 影响范围：仅新增限时抢购创建空白页面与前端导航入口；暂不改变后端接口、订单模拟、营销活动数据或现有折扣创建流程。

- 新增 Shopee 我的店铺限时抢购空白页。
  - 涉及文件：`frontend/src/modules/shopee/views/ShopFlashSaleView.tsx`、`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/views/MarketingCentreView.tsx`、`frontend/src/modules/shopee/components/Header.tsx`、`frontend/src/modules/shopee/components/Sidebar.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 `/shopee/marketing/flash-sale` 前端页面，布局参考营销中心折扣页，预留创建卡片、状态 Tab、表现指标、搜索区与活动列表空状态；营销中心卡片、侧边栏入口和顶部面包屑均已接入。
  - 影响范围：仅新增我的店铺限时抢购空白页面与导航入口；暂不改变后端接口、订单模拟、营销活动数据或现有折扣页面行为。

### 修复
- 调整 Shopee 我的订单各 Tab 默认按最新订单优先展示。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/views/MyOrdersView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：订单列表接口默认排序从创建时间升序改为降序；待出货 Tab 不再默认追加 `ship_by_date_asc`，避免切换 Tab 时仍按最早发货时间优先。
  - 影响范围：仅影响 Shopee 我的订单页面默认展示顺序；不改变订单状态、订单金额、筛选条件、分页大小或订单生成逻辑。
- 修复 Shopee 加价购/满额赠活动订单页显示无关订单明细的问题。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：活动订单响应在已按活动筛选订单的基础上，进一步将订单明细限制为当前活动的主商品与对应加价购/赠品商品，过滤同订单内无关普通商品、其他加价购活动或其他营销活动明细。
  - 影响范围：仅影响 `/shopee/marketing/add-on/orders?campaign_id=...` 页面展示的订单明细与小计口径；不改变订单模拟、订单落库和活动匹配逻辑。
- 修正 Shopee 我的订单买家实付列加价购/满额赠活动标签。
  - 涉及文件：`frontend/src/modules/shopee/views/MyOrdersView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：我的订单买家实付列营销活动名称前缀按 `marketing_campaign_type` 区分展示，`add_on` 显示“加价购”，`gift` 显示“满额赠”，`bundle` 继续显示“套餐优惠”，默认单品折扣仍显示“单品折扣”。
  - 影响范围：仅影响 Shopee 我的订单列表中营销活动标签文案，不改变订单金额、归因和后端数据。
- 修复 Shopee 加价购订单模拟中加购商品长期不落单的问题。
  - 涉及文件：`backend/apps/api-gateway/app/services/shopee_order_simulator.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：仅在加价购附加商品数量判断中使用专项预算 `30 + purchase_power * 1000`，保留普通订单、套餐优惠、单品折扣与满额赠的全局买家预算口径不变，避免主订单金额占用原预算后加购商品始终无法通过预算校验。
  - 验证结果：本地 Docker MySQL `run_id=6` / 活动“加价购功能测试0429”用正确 `user_id=3` 连续受控模拟后生成 `line_role='add_on'` 订单明细，`marketing_campaign_type='add_on'`、`marketing_campaign_id=3`。
  - 影响范围：仅影响 Shopee 加价购订单模拟中附加加购商品能否落单；不改变活动匹配、加价购吸引力概率、普通订单下单概率、满额赠与套餐优惠逻辑。

## 2026-04-28

### 修复
- 修复 Shopee 套餐优惠活动订单页分页器点击无反应的问题。
  - 涉及文件：`frontend/src/modules/shopee/views/BundleOrdersView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：在保留现有分页器样式与布局的前提下，绑定页码状态、上一页/下一页、页码点击、输入页码确认与 Enter 跳转；订单概览和数据详情按当前页本地切片展示。
  - 影响范围：仅影响 `/shopee/marketing/bundle/orders?campaign_id=...` 页面分页交互，不改变后端接口与数据统计口径。
- 修复 Shopee 套餐优惠活动订单页不同活动显示相同订单的问题。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：套餐优惠订单查询条件收紧为订单头 `marketing_campaign_type=bundle` 且 `marketing_campaign_id` 等于当前活动 ID，或订单明细中存在相同套餐活动归因；避免仅按 `marketing_campaign_type=bundle` 查出同一对局下全部套餐订单。
  - 影响范围：`/shopee/marketing/bundle/orders?campaign_id=...` 会按当前套餐优惠活动隔离订单、指标卡和数据详情；不改变前端样式、布局。
- 修复 Shopee 套餐优惠活动订单页接口 500。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：套餐优惠订单响应构建改为调用现有 `_resolve_discount_campaign_status(campaign, current_tick=current_tick)` 状态解析函数，避免引用不存在的 `_discount_campaign_effective_status` 导致接口报错。
  - 影响范围：修复 `/shopee/runs/{run_id}/marketing/bundle/campaigns/{campaign_id}/orders` 订单页数据接口加载失败；不改变前端样式、布局和统计口径。

### 新增
- 打通 Shopee 套餐优惠活动订单页数据链路。
  - 涉及文件：`frontend/src/modules/shopee/views/BundleOrdersView.tsx`、`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/views/MarketingDiscountView.tsx`、`frontend/src/modules/shopee/components/Header.tsx`、`frontend/src/modules/shopee/components/Sidebar.tsx`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 `BundleOrdersView` 与 `/shopee/marketing/bundle/orders?campaign_id=...` 前端路由；套餐优惠活动列表操作列按官方口径显示“编辑 / 复制 / 详情 / 订单”；订单页保留现有前端样式，改为调用后端活动订单接口加载基础信息、订单概览和数据详情；后端按 `marketing_campaign_type=bundle` 与活动 ID 从 `shopee_orders`、`shopee_order_items` 查询套餐订单，并接入 Redis 订单页缓存和订单缓存失效联动。
  - 影响范围：套餐优惠活动列表进入独立活动订单页并展示真实订单与数据详情；加价购/满额赠订单页和单品折扣数据页保持原有入口。

### 新增
- 打通 Shopee 加价购/满额赠活动订单页数据链路。
  - 涉及文件：`frontend/src/modules/shopee/views/AddOnDealOrdersView.tsx`、`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/views/MarketingDiscountView.tsx`、`frontend/src/modules/shopee/components/Header.tsx`、`frontend/src/modules/shopee/components/Sidebar.tsx`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 `AddOnDealOrdersView` 与 `/shopee/marketing/add-on/orders?campaign_id=...` 前端路由；营销活动列表中 `add_on/gift` 兼容活动的操作列由“数据/查看数据”改为“订单”；订单页保留现有前端样式，改为调用后端活动订单接口加载基础信息与订单明细；后端按加价购正式活动与 item 级营销归因从 `shopee_orders`、`shopee_order_items` 查询订单，并接入 Redis 订单页缓存和订单缓存失效联动。
  - 影响范围：加价购/满额赠活动列表进入独立活动订单页并展示真实订单数据；单品折扣数据页继续使用原 `DiscountDataView`。

### 新增
- 新增 Shopee 营销活动列表操作列官方口径修正设计文档。
  - 涉及文件：`docs/设计文档/31-Shopee营销活动列表操作列官方口径修正设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：根据官方截图整理 Bundle Deal 与 Add-on Deal Tab 的操作列差异：套餐优惠显示“编辑 / 复制 / 详情 / 订单”，加价购/满额赠显示“详情 / 复制 / 订单”；明确这两个 Tab 不展示“数据 / 查看数据”，Add-on Deal 不展示“编辑”，All Tab 按活动真实类型决定操作项。
  - 影响范围：仅新增设计文档与进度台账，尚未改动前端列表操作列代码。

### 修复
- 修正 Shopee 满额赠数据页销售额统计口径。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：满额赠数据页继续通过赠品明细识别命中订单，但指标卡销售额、趋势销售额和商品排行改为统计触发满额赠的主商品成交额；加价购仍按加购商品明细统计。
  - 验证结果：本地库 `campaign_id=8` 复核结果为赠品明细销售额 0、主商品销售额 1880、数据页 analytics 销售额 1880；`python -m py_compile backend/apps/api-gateway/app/api/routes/shopee.py` 通过。
  - 影响范围：仅影响满额赠活动数据页与导出统计口径；单品折扣、套餐优惠和加价购口径不变。

### 新增
- 实现 Shopee 加价购/满额赠详情页与数据页接入。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`frontend/src/modules/shopee/views/DiscountDetailView.tsx`、`frontend/src/modules/shopee/views/DiscountDataView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：折扣详情/数据接口在 `campaign_type=add_on` 时加载正式加价购/满额赠活动，详情页返回主商品与加购/赠品商品，数据页指标、趋势、排行与导出按 item 级加购/赠品归因统计；前端详情页和数据页改为兼容加价购/满额赠的中性促销文案与表头。
  - 影响范围：折扣活动列表中加价购/满额赠的“详情”和“数据/查看数据”入口可进入真实页面；单品折扣与套餐优惠原有详情/数据口径保持不变。
- 实现 Shopee 加价购/满额赠接入订单模拟首版。
  - 涉及文件：`backend/apps/api-gateway/app/services/shopee_order_simulator.py`、`backend/apps/api-gateway/app/models.py`、`backend/apps/api-gateway/app/db.py`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`cbec_sim.sql`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：订单模拟器新增有效加价购/满额赠活动加载、主商品匹配、加价购轻量下单概率加成、下单后加购商品追加、满额赠轻量概率加成与达标赠品追加；`shopee_order_items` 新增明细级营销归因、明细角色、原始单价与成交单价字段，并同步初始化补列、字段注释、索引和 SQL 快照；订单列表/详情响应返回 item 级营销字段。
  - 影响范围：Shopee 自动订单模拟会在有效加价购/满额赠活动下生成加购商品或 0 元赠品明细，并预占对应库存；单品折扣和套餐优惠原有概率链路保持独立，套餐优惠默认不叠加加价购。
- 新增 Shopee 加价购/满额赠接入订单模拟概率设计文档。
  - 涉及文件：`docs/设计文档/30-Shopee加价购满额赠接入订单模拟概率设计.md`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：定义加价购与满额赠接入订单模拟的触发流程、活动加载、概率公式、营销叠加优先级、订单明细归因、库存处理、缓存失效与验收标准。
  - 影响范围：仅新增设计文档与进度台账，尚未改动订单模拟业务代码。
- 优化 Shopee 折扣活动列表中加价购/满额赠展示口径。
  - 涉及文件：`backend/apps/api-gateway/app/api/routes/shopee.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：折扣列表接口对 `campaign_type=add_on` 的活动改为读取加价购正式活动的主商品与加购/赠品商品图片，返回给前端 `products` 多图展示，并保留超过 5 张时的 overflow 计数；活动类型标签改为按正式活动 `promotion_type` 显示，加价购显示“加价购”，满额赠显示“满额赠”。
  - 影响范围：仅影响 `/shopee/marketing/discount` 活动列表中加价购/满额赠活动的商品图片与类型标签展示；单品折扣与套餐优惠列表仍沿用原有折扣活动商品图片来源。
- 调整 Shopee 加价购创建页活动时间为可点击选择的日期时间选择器。
  - 涉及文件：`frontend/src/modules/shopee/views/AddOnDealCreateView.tsx`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：活动时间开始/结束字段复用单品折扣创建页同款 `DateTimePicker`，支持点击弹出日期时间选择面板。
  - 影响范围：仅影响加价购/满额赠创建页活动时间输入方式，其余页面结构、商品选择与提交流程不变。
- 新增 Shopee 加价购后端与数据设计文档，并接入 Phase 1 后端、数据库与 Redis 实现。
  - 涉及文件：`docs/设计文档/29-Shopee加价购后端与数据设计.md`、`backend/apps/api-gateway/app/models.py`、`backend/apps/api-gateway/app/db.py`、`backend/apps/api-gateway/app/api/routes/shopee.py`、`docs/当前进度.md`、`docs/change-log.md`
  - 修改内容：新增 `add_on/gift` 活动主表、主商品表、加购/赠品表、草稿表与字段注释；新增创建页 bootstrap、商品候选、草稿保存/详情、正式创建、活动详情接口；接入 Redis 缓存 key、TTL、失效与限流；正式创建时同步写入折扣活动兼容记录，便于折扣首页 Tab 和列表展示；前端创建页接入 bootstrap、基础字段状态、主商品候选、加购/赠品候选、已选商品状态、保存草稿与确认创建接口；主商品与加购/赠品添加商品入口复用单品折扣创建页同款居中弹窗样式。
  - 影响范围：完成加价购/满额赠后端、数据库、Redis Phase 1 与前端商品选择/提交接口接线；不接入订单模拟和下单概率影响，保持当前加价购前端页面整体视觉风格不漂移。
- 新增 Shopee 加价购创建空白页，并接入折扣页创建入口的 `type=add_on` 路由分支。
  - 涉及文件：`frontend/src/modules/shopee/ShopeePage.tsx`、`frontend/src/modules/shopee/views/AddOnDealCreateView.tsx`、`docs/change-log.md`
  - 修改内容：新增 `AddOnDealCreateView` 空白页面，保留返回折扣页入口与历史回溯只读提示；`ShopeePage` 在 `/shopee/marketing/discount/create?type=add_on` 下渲染该页面。
  - 影响范围：仅影响加价购创建页前端占位展示；不新增后端接口、数据库字段或提交流程。

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

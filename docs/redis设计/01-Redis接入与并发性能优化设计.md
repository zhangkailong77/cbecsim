# 01-Redis接入与并发性能优化设计

## 1. 目标
- 为高成本接口提供短时缓存，优先优化「我的订单」加载耗时。
- 为订单模拟链路提供分布式锁，避免多请求/多实例重复执行。
- 为高风险接口提供限流保护，降低被频繁触发时的数据库压力。
- 保持业务真源在 MySQL，Redis 仅作为加速与保护层。

## 2. 范围
- 本次纳入：
  - 分布式锁（simulate 与 auto tick）。
  - 限流（管理员/玩家模拟接口 + 订单列表接口）。
  - 短 TTL 缓存（订单列表与聚合看板类接口）。
- 本次不纳入：
  - 资金/订单主状态迁移至 Redis。
  - Celery/RQ 任务队列改造。
  - JWT 会话中心化。

## 3. 流程设计
1. 请求进入接口后先执行限流判断。
2. 读接口先查 Redis 缓存，命中则直接返回。
3. 未命中时回源 MySQL，组装结果后写入 Redis（短 TTL）。
4. 写接口或模拟接口执行前先抢分布式锁，拿到锁才继续。
5. 写成功后按 `run_id + user_id` 维度清理相关缓存 key。

## 4. 业务规则
- 一致性规则：
  - 订单、资金、物流等经营结果仅以数据库为准。
  - 缓存允许短暂过期窗口（秒级），通过写后失效保障可接受一致性。
  - 必须满足写后立即可见（Read-After-Write / Read Your Writes）：用户在前端提交修改成功后，下一次读取应看到最新数据。
  - 所有写接口（新增/编辑/取消/发货/推进/模拟）成功后必须执行对应缓存失效（Cache Invalidation），禁止仅依赖 TTL 被动过期。
- 锁规则：
  - 锁 key 建议：`lock:shopee:simulate:{run_id}:{user_id}`。
  - 锁必须带 TTL（建议 30~60 秒），避免异常导致死锁。
- 限流规则：
  - 玩家模拟接口建议初始阈值：`5 次/分钟/用户`。
  - 管理员模拟接口建议初始阈值：`10 次/分钟/用户`。

## 5. 数据模型（Redis Key 设计）
- 锁：
  - `lock:shopee:simulate:{run_id}:{user_id}`
  - `lock:shopee:auto_tick:{run_id}:{user_id}`
- 限流：
  - `ratelimit:shopee:simulate:user:{user_id}`
  - `ratelimit:game:admin:simulate:user:{user_id}`
  - `ratelimit:shopee:orders:list:user:{user_id}`
- 缓存：
  - `cache:shopee:orders:list:{run_id}:{user_id}:{query_hash}`
  - `cache:shopee:orders:counts:{run_id}:{user_id}`
  - `cache:game:buyer_pool:overview:{run_id_or_latest}`

## 6. 接口改造清单
- 必改（锁 + 限流）：
  - `POST /game/admin/runs/{run_id}/orders/simulate`
  - `POST /shopee/runs/{run_id}/orders/simulate`
  - `GET /shopee/runs/{run_id}/orders`
- 建议改（缓存）：
  - `GET /shopee/runs/{run_id}/orders`
  - `GET /game/admin/buyer-pool/overview`
  - `GET /game/runs/{run_id}/warehouse/summary`
  - `GET /game/runs/{run_id}/warehouse/stock-overview`
  - `GET /game/runs/{run_id}/warehouse/backorder-risk`

## 7. 配置设计
- `REDIS_URL`
- `REDIS_PREFIX`
- `REDIS_LOCK_TTL_SEC`
- `REDIS_CACHE_ENABLE`
- `REDIS_RATE_LIMIT_ENABLE`
- `REDIS_CACHE_TTL_ORDERS_LIST_SEC`
- `REDIS_CACHE_TTL_OVERVIEW_SEC`

## 8. 错误处理与降级
- Redis 不可用时：
  - 读接口自动回源 DB。
  - 锁/限流能力降级为日志告警，不阻断核心链路。
- 所有 Redis 操作必须有超时，避免接口阻塞。

## 8.1 缓存一致性策略（写后立即可见）
- 一致性目标：前端写操作返回成功后，同用户同 run 的关键读接口必须立即可见最新结果。
- 执行方式：
  - 写请求事务提交成功后，按 `run_id + user_id` 维度删除相关缓存 key（列表缓存 + 聚合缓存）。
  - 删除失败时记录告警日志，并回退到短 TTL 策略；不得影响主事务返回。
- 适用写接口（首批）：
  - `POST /shopee/runs/{run_id}/orders/simulate`
  - `POST /game/admin/runs/{run_id}/orders/simulate`
  - `POST /shopee/runs/{run_id}/orders/{order_id}/ship`
  - `POST /shopee/runs/{run_id}/orders/{order_id}/cancel`
  - `POST /shopee/runs/{run_id}/orders/{order_id}/logistics/progress`
- 关联失效目标（示例）：
  - `cache:shopee:orders:list:{run_id}:{user_id}:*`
  - `cache:shopee:orders:counts:{run_id}:{user_id}`
  - `cache:shopee:orders:summary:{run_id}:{user_id}`

## 9. 验收标准
1. 「我的订单」接口 P95 延时较当前基线下降明显（建议目标 30%+）。
2. 同一 `run_id + user_id` 并发触发模拟时不再重复执行。
3. 高频触发下限流生效，服务无明显雪崩。
4. Redis 异常时业务主流程可用，且有明确告警日志。

## 10. 分阶段实施
1. P1：接入 Redis 客户端、分布式锁、模拟接口限流。
2. P2：订单列表与聚合接口短 TTL 缓存。
3. P3：压测与阈值调优（TTL、限流窗口、锁过期时间）。

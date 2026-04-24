# 数据库时区从 UTC 迁移至 Asia/Shanghai

## 背景

当前系统所有时间相关逻辑基于 UTC：

- MySQL Docker 容器时区为 UTC
- `created_at` 等字段由 `server_default=func.now()` 写入 UTC 值
- 代码中全部使用 `datetime.utcnow()`

导致日志和前端展示的时间与本地时间（CST, UTC+8）相差 8 小时。

## 迁移目标

将整个时间链路统一为 Asia/Shanghai (UTC+8)，使：
- MySQL `NOW()` 返回本地时间
- `created_at` 等字段存储本地时间
- 代码使用 `datetime.now()` 获取本地时间
- 日志和前端直接展示本地时间

## 迁移步骤

### 第 1 步：修改 MySQL 容器时区

在 docker-compose 中为 MySQL 容器添加环境变量：

```yaml
environment:
  - TZ=Asia/Shanghai
```

或在 MySQL 配置中设置：

```sql
SET GLOBAL time_zone = '+08:00';
```

验证：

```sql
SELECT @@global.time_zone, NOW(), UTC_TIMESTAMP();
-- NOW() 应比 UTC_TIMESTAMP() 多 8 小时
```

### 第 2 步：迁移存量数据（所有 datetime 列 +8 小时）

以下是数据库中全部 datetime 列，迁移时统一 `+ INTERVAL 8 HOUR`。

#### game_runs（游戏对局）
| 列 | 说明 |
|---|---|
| `created_at` | 对局创建时间（游戏时钟起点） |
| `manual_end_time` | 手动设置的结束时间 |

#### shopee_order_generation_logs（订单模拟日志）
| 列 | 说明 |
|---|---|
| `tick_time` | 模拟 tick 时间（核心进度字段） |
| `created_at` | 记录创建时间 |

#### shopee_orders（订单）
| 列 | 说明 |
|---|---|
| `ship_by_date` | 发货截止日期 |
| `ship_by_at` | 发货截止时间 |
| `shipped_at` | 实际发货时间 |
| `delivered_at` | 签收时间 |
| `eta_start_at` | 预计到达开始时间 |
| `eta_end_at` | 预计到达结束时间 |
| `cancelled_at` | 取消时间 |
| `must_restock_before_at` | 补货截止时间 |
| `created_at` | 订单创建时间 |

#### shopee_order_logistics_events（物流事件）
| 列 | 说明 |
|---|---|
| `event_time` | 物流事件时间 |
| `created_at` | 记录创建时间 |

#### shopee_order_settlements（订单结算）
| 列 | 说明 |
|---|---|
| `settled_at` | 结算时间 |
| `created_at` | 记录创建时间 |

#### shopee_discount_campaigns（折扣活动）
| 列 | 说明 |
|---|---|
| `start_at` | 折扣开始时间 |
| `end_at` | 折扣结束时间 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

#### shopee_discount_campaign_items（折扣活动商品）
| 列 | 说明 |
|---|---|
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

#### shopee_discount_drafts（折扣草稿）
| 列 | 说明 |
|---|---|
| `start_at` | 开始时间 |
| `end_at` | 结束时间 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

#### shopee_discount_draft_items（折扣草稿商品）
| 列 | 说明 |
|---|---|
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

#### shopee_discount_performance_daily（折扣每日表现）
| 列 | 说明 |
|---|---|
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

#### shopee_user_discount_preferences（用户折扣偏好）
| 列 | 说明 |
|---|---|
| `date_from` | 日期范围起始 |
| `date_to` | 日期范围结束 |
| `last_viewed_at` | 最后查看时间 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

#### shopee_marketing_events（营销活动）
| 列 | 说明 |
|---|---|
| `start_at` | 活动开始时间 |
| `end_at` | 活动结束时间 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

#### shopee_marketing_announcements（营销公告）
| 列 | 说明 |
|---|---|
| `start_at` | 公告开始时间 |
| `end_at` | 公告结束时间 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

#### shopee_marketing_tools（营销工具）
| 列 | 说明 |
|---|---|
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

#### shopee_user_marketing_preferences（用户营销偏好）
| 列 | 说明 |
|---|---|
| `last_viewed_at` | 最后查看时间 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

#### 其余表（纯记录型）
| 表 | 列 |
|---|---|
| `users` | `created_at` |
| `schools` | `created_at` |
| `game_run_cash_adjustments` | `created_at` |
| `game_runs_total_game_days_audit` | `changed_at` |
| `inventory_lots` | `created_at`, `last_restocked_at` |
| `inventory_stock_movements` | `created_at` |
| `logistics_shipments` | `created_at` |
| `market_products` | `created_at` |
| `oss_storage_configs` | `created_at`, `updated_at` |
| `procurement_orders` | `created_at` |
| `shopee_bank_accounts` | `created_at`, `updated_at` |
| `shopee_category_nodes` | `created_at` |
| `shopee_finance_ledger_entries` | `credited_at`, `created_at` |
| `shopee_listing_draft_images` | `created_at` |
| `shopee_listing_draft_spec_values` | `created_at`, `updated_at` |
| `shopee_listing_drafts` | `created_at`, `updated_at` |
| `shopee_listing_images` | `created_at` |
| `shopee_listing_quality_scores` | `created_at` |
| `shopee_listing_spec_values` | `created_at`, `updated_at` |
| `shopee_listing_variants` | `created_at`, `updated_at` |
| `shopee_listing_wholesale_tiers` | `created_at`, `updated_at` |
| `shopee_listings` | `created_at`, `updated_at`, `schedule_publish_at`, `quality_scored_at` |
| `shopee_spec_template_options` | `created_at` |
| `shopee_spec_templates` | `created_at` |
| `sim_buyer_profiles` | `created_at`, `updated_at` |
| `warehouse_inbound_orders` | `created_at`, `completed_at` |
| `warehouse_landmarks` | `created_at` |
| `warehouse_strategies` | `created_at` |

#### 迁移 SQL 模板

```sql
-- 对每张表的每个 datetime 列执行：
ALTER TABLE cbec_sim.<table_name> UPDATE <column_name> = <column_name> + INTERVAL 8 HOUR WHERE <column_name> IS NOT NULL;
```

> 实际执行时应写一个脚本遍历所有表和列，统一 +8 HOUR，避免遗漏。

### 第 3 步：替换代码中的 `datetime.utcnow()`

#### 业务代码（~20 处）

| 文件 | 位置 | 用途 |
|---|---|---|
| `game.py` | `_resolve_game_hour_tick_by_run` | 游戏时钟 now 参数 |
| `game.py` | `_resolve_run_remaining_seconds` | 对局剩余时间计算 |
| `game.py` | `_calc_run_elapsed_info` | 经过时间信息 |
| `game.py` | `admin_simulate_orders` | 管理员推进订单 |
| `game.py` | `extend_admin_run` | 延长对局 |
| `game.py` | `_mark_run_finished_if_reached` | 判断对局是否结束 |
| `game.py` | `_resolve_game_hour_tick_by_run` (callers) | 多处调用 |
| `shopee.py` | `_auto_simulate_orders_if_needed` | 自动模拟 |
| `shopee.py` | `_resolve_game_tick` | 游戏 tick 解析 |
| `shopee.py` | OSS 上传路径 (x2) | 文件路径日期 |
| `shopee.py` | 限流窗口 | 最近 1 小时窗口 |
| `shopee.py` | 用户侧模拟订单 | 默认 tick_time |
| `shopee.py` | 其他多处 | 获取当前时间 |
| `shopee_order_simulator.py` | `simulate_orders_for_run` | 模拟时间基准 |
| `shopee_fulfillment.py` (x2) | 物流事件 | 事件时间戳 |
| `auto_order_tick_worker.py` | `_run_one_cycle` | worker 循环 |

#### 测试代码（~40 处）

`test_api.py` 中所有 `datetime.utcnow()` 替换为 `datetime.now()`。

### 第 4 步：验证

1. 重启 MySQL 容器，确认 `NOW()` 返回 CST
2. 重启后端，确认日志时间与本地时间一致
3. 创建新对局，确认 `created_at` 是本地时间
4. 触发订单模拟，确认 `tick_time` 是本地时间
5. 检查游戏时钟：`current_game_tick` 应与本地时间一致
6. 跑测试：`pytest backend/apps/api-gateway/tests/`

## 不需要改的

| 项 | 原因 |
|---|---|
| `_align_compare_time` | 只处理 tzinfo 有无对齐，两边都是本地 naive，逻辑不变 |
| `REAL_SECONDS_PER_GAME_HOUR` 等常量 | 与时区无关 |
| 游戏时钟计算公式 | `elapsed = now - created_at`，两边都是本地时间，差值不变 |
| `DateTime(timezone=True)` 声明 | 仍然有效，MySQL 会按新时区存储 |

## 风险

| 风险 | 等级 | 缓解措施 |
|---|---|---|
| 数据迁移遗漏列 | 中 | 用脚本自动遍历 `information_schema.COLUMNS` |
| 迁移期间新数据写入 | 低 | 停服后迁移 |
| 代码遗漏 `utcnow()` | 低 | `grep -r utcnow` 验证零结果 |
| 测试回归 | 低 | 全量跑 pytest |

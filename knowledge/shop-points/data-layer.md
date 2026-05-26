---
name: data-layer-shop-points
description: "shop-points 数据库结构、ShardingSphere 分片策略、MyBatis 模式"
version: "0.2.0"
category: knowledge
tags:
  - shop-points
  - database
  - sharding
  - mybatis
commands: []
---

# shop-points 数据层

## 双数据库

### shop_points（积分库，默认数据源）

**主要表**（按 Mapper 推断）:

| 领域 | 表名（Mapper） |
|------|---------------|
| 积分账户 | `subject_equity_points_account`, `subject_equity_points_ledger`（100 分片）, `subject_equity_points_earn_batch`（100 分片） |
| 积分发放 | `disbursement_plan`, `disbursement_task`, `disbursement_city_exec_info` |
| 佣金 | `commission_detail`, `commission_status`, `commission_event`, `commission_detail_history`（按年分片）, `commission_status_history`（按年分片） |
| 精英佣金 | `elite_commission_detail`, `elite_commission_event`, `elite_points_record` |
| 品牌 | `brand_daily_point_detail`, `brand_commission_points_detail`, `brand_indicator_rank`, `brand_integral_index`, `brand_target_dict`, `brand_code_mapping` |
| 活动 | `act_instance`, `act_instance_resblock`, `act_reward_estimate`, `act_reward_exec_plan`, `act_schedule_task`, `act_template`, `activity_config`, `activity_rel_shop`, `activity_rel_resblock`, `activity_recovery_task` |
| 规则 | `rule_config`, `star_rule` 相关, `biz_coef_rule` 相关, `grade_rule` 相关 |
| 运营门店 | `running_shop`, `running_brand`, `running_brand_city_mdm`, `running_distributor` |
| 星级权益 | `cur_star_right`, `cur_star_right_snapshot`, `daily_shop_star` |
| 黑名单 | `blacklist_rule`, `blacklist_shop` |
| 品质 | `shop_pinzhi_order`, `shop_pinzhi_order_detail`, `shop_pinzhi_kesu_detail`, `shop_pinzhi_punish_detail`, `shop_pinzhi_win_win_detail`, `shop_pinzhi_points_balance`, `shop_pinzhi_event` |
| Lego/推送 | `lego_record_summary`（100 分片）, `lego_record_detail`, `lego_msg_send_log` |
| 其他 | `deal_order`, `contract_info`, `points_dict`, `points_adjust`, `download_record`, `upload_calc_shop`, `upload_record` |

### shop_equity（权益库）

| 领域 | 表名（Mapper） |
|------|---------------|
| 权益策略 | `equity_strategy_info`, `equity_rule`, `equity_shop_switch`, `equity_cycle` |
| 权益结算 | `equity_settlement`, `equity_settlement_detail` |
| 权益账户 | `equity_account` |
| 权益交易 | `equity_trans_log`, `equity_trans_order`, `equity_trans_order_detail` |
| 策略结果 | `equity_strategy_result`, `equity_strategy_result_detail`, `daily_equity_strategy_result`, `daily_equity_strategy_result_detail` |
| 日结算 | `daily_equity_settlement` |
| 执行信息 | `equity_points_exec_info`, `strategy_city_exec_info`, `strategy_shop_exec_info` |

---

## 数据源配置

**连接池**: initial-size=15, min-idle=15, max-active=50

**主从路由**: 写走主库，读走从库

**双数据源切换**: `@DS` 注解

```java
@DS("shop_equity")
public List<EquityAccount> queryEquityAccounts(...) { ... }
```

---

## ShardingSphere 分片规则

### 按 subject_id 分片（100 张）

| 逻辑表 | 分片算法类 | 分片键 | 实际表 |
|--------|-----------|--------|--------|
| `subject_equity_points_ledger` | `SubjectEquityPointsLedgerSplitTableStrategy` | `subject_id` | `_00` .. `_99` |
| `subject_equity_points_earn_batch` | `SubjectEquityPointsEarnBatchSplitTableStrategy` | `subject_id` | `_00` .. `_99` |
| `lego_record_summary` | `LegoRecordSummarySplitTableStrategy` | `subject_id` | `_00` .. `_99` |

算法: 取 `subject_id` 末 2 位字符 → 路由到对应后缀表。

### 按 ctime 按年分片

| 逻辑表 | 分片算法类 | 分片键 | 实际表 |
|--------|-----------|--------|--------|
| `commission_detail_history` | `HistorySplitTableStrategy` | `ctime` | `_2024` .. `_2028` |
| `commission_status_history` | `HistorySplitTableStrategy` | `ctime` | `_2024` .. `_2028` |

算法: 按 `ctime` 年份路由到对应年份后缀表。同时支持范围查询（`RangeShardingAlgorithm`）。

### Hint 分片（编程式路由）

| 逻辑表 | 路由方式 | 说明 |
|--------|----------|------|
| `equity_strategy_result` | Hint | 通过 `StrategyDaily` 程序化路由到 `daily` 数据源 |
| `equity_strategy_result_detail` | Hint | 同上 |
| `equity_settlement` | Hint | 同上 |

---

## MyBatis 模式

### Mapper 继承体系

```java
// 所有 Mapper 继承 BaseMapper，获得通用 CRUD + 动态 SQL 能力
public interface BaseMapper<T> extends
    tk.mybatis.mapper.common.BaseMapper<T>,   // 单表 CRUD
    IdsMapper<T>,                              // 按 ID 列表查询
    ExampleMapper<T>,                          // 条件构造器查询
    InsertListMapper<T> {                      // 批量插入
    @Update("${sql}")
    int executeUpdate(@Param("sql") String sql);  // 动态 SQL 执行
}
```

### XML 分层

| 目录 | 数量 | 用途 |
|------|------|------|
| `mappers/` | 103 | MBG 自动生成的基础 CRUD |
| `manualMappers/` | 51 | 手写自定义 SQL（复杂查询、多表关联、批量操作） |

**新增 Mapper 时**: 同时生成 `mappers/` 基础 XML + 按需在 `manualMappers/` 添加自定义 SQL。

---

## 反模式警告

### 无分片键查询 = 全分片扫描

**严重性**: 性能灾难。

分片表（`_00`..`_99`）的 WHERE 条件缺少 `subject_id` 时，ShardingSphere 遍历全部 100 个分片表。

**规则**: 分片表查询的 WHERE 条件**必须**包含 `subject_id`。

```java
// 正确
SELECT * FROM subject_equity_points_ledger WHERE subject_id = ? AND ...

// 错误 — 触发 100 分片全扫描
SELECT * FROM subject_equity_points_ledger WHERE account_type = ?
```

### 动态 SQL 注入风险

`BaseMapper.executeUpdate(@Param("sql") String sql)` 直接拼接 SQL，禁止将用户输入传入此方法。

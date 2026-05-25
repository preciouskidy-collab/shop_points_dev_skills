---
name: data-layer
description: "需要了解数据库结构、分片策略或表关系时加载"
version: "0.1.0"
category: harness
tags:
  - wiki
  - database
  - schema
  - sharding
  - mybatis
commands: []
---

# 数据层

## shop-points 双数据库

### shop_points（积分库）
- 积分账户表
- 积分明细表
- 发放事件表
- 科目信息表
- 品牌积分表
- 佣金表

### shop_equity（权益库）
- 权益积分账户表
- 权益积分流水表
- 权益策略表
- 权益结算表

---

## ShardingSphere 分表策略

**分片规则**: 按 `subject_id` 分片，每张表 100 个分片。

**分片策略类**:
- `SubjectEquityPointsLedgerSplitTableStrategy` — 权益积分账本分片
- `SubjectEquityPointsEarnBatchSplitTableStrategy` — 权益积分发放批次分片
- `LegoRecordSummarySplitTableStrategy` — Lego 记录汇总分片
- `HistorySplitTableStrategy` — 历史数据分片

**主从路由**:
- 写操作走主库
- 读操作走从库

**双数据源切换**:
- `shop_points` + `shop_equity` 两个数据源
- 通过 `@DS` 注解切换数据源

```java
// 示例：指定使用权益数据源
@DS("shop_equity")
public List<EquityAccount> queryEquityAccounts(...) { ... }
```

---

## 反模式警告

### 无分片键查询 = 全分片扫描

**严重性**: 性能灾难。

当查询缺少 `subject_id` 作为 WHERE 条件时，ShardingSphere 会遍历所有 100 个分片表，导致：
- 查询时间从毫秒级暴涨到秒级甚至分钟级
- 数据库连接池耗尽
- 影响其他正常请求

**规则**: 分片键 `subject_id` 必须存在于 WHERE 条件中。

```java
// 正确：带分片键
SELECT * FROM points_ledger WHERE subject_id = ? AND ...

// 错误：无分片键，触发全分片扫描
SELECT * FROM points_ledger WHERE account_type = ?
```

---

## shop-points-lottery 数据库

### shop_lottery（活动库）
- 活动表
- 奖品表
- 用户奖品表
- 用户机会表
- 任务表

### shop_mall（商城库）
- 商品表
- 订单表
- 物流表
- 退款表
- 账户表
- 账户流水表

**数据源切换**: 使用 `@DS(dataSource = "...")` 注解。

```java
@DS(dataSource = "shop_lottery")
public List<Activity> queryActivities(...) { ... }

@DS(dataSource = "shop_mall")
public List<Product> queryProducts(...) { ... }
```

---

## MyBatis Mapper 模式

### tk.mybatis 通用 Mapper
继承 `Mapper<T>` 获得基础 CRUD 操作：

```java
public interface PointsLedgerMapper extends Mapper<PointsLedger> {
    // 自动获得 selectOne, selectAll, selectByPrimaryKey,
    // insert, updateByPrimaryKey, deleteByPrimaryKey 等
}
```

### 手动 Mapper
位于 `resources/manualMappers/`，用于复杂查询场景：
- 多表关联
- 聚合统计
- 自定义 SQL

### Domain 实体类
每个 Mapper 在 `dao.domain` 包中有对应的 Domain 实体类：

```java
@Table(name = "points_ledger")
@Data  // Lombok
public class PointsLedger {
    @Id
    @Column(name = "id")
    private Long id;

    @Column(name = "subject_id")
    private Long subjectId;
    // ...
}
```

### ORM 规范
- JPA 注解: `@Table`, `@Id`, `@Column`
- Lombok: `@Data` 等注解减少样板代码
- 分片表实体必须包含 `subject_id` 字段

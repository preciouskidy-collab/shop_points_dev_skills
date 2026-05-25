---
name: service-topology
description: "涉及 shop-points 和 shop-points-lottery 之间交互的需求时加载"
version: "0.1.0"
category: harness
tags:
  - wiki
  - integration
  - cross-service
  - dubbo
  - kafka
commands: []
---

# 服务拓扑

## 集成模式

shop-points 和 shop-points-lottery 之间通过两种模式交互：

### Dubbo RPC（同步调用）
Lottery 调用 shop-points-api 的积分查询/消耗/退还接口。

**适用场景**: 需要实时返回结果的积分操作（如扣减积分、查询余额）。

### Kafka Events（异步消息）
shop-points 发送 PointsChangeEvent 给 Lottery。

**适用场景**: 状态变更通知、数据同步（如积分变更后同步 Lottery 本地账户）。

---

## 数据流

### 典型场景：用户在积分商城下单

```
用户下单 → Lottery Controller
  → Lottery ShopOrderBizService
    → Dubbo RPC 调 shop-points（积分查询/扣减）
    → Lottery 本地 DAO（订单/库存操作）
    → Kafka Producer（订单事件）

shop-points Kafka Consumer
  → shop-points Service（积分变更）
  → shop-points DAO（账户更新）
  → Kafka Producer（PointsChangeEvent）

Lottery PointsChangeEvent Consumer
  → Lottery AccountBizService（账户同步）
```

### 调用链路说明

1. **Lottery Controller** 接收用户请求
2. **ShopOrderBizService** 处理订单业务逻辑
3. 通过 **Dubbo RPC** 同步调用 shop-points 进行积分查询和扣减（确认积分充足并锁定）
4. 在 **Lottery 本地数据库** 创建订单、扣减库存
5. 通过 **Kafka** 发送订单事件通知
6. **shop-points** 消费订单事件，完成积分变更
7. **shop-points** 发送 **PointsChangeEvent** 通知变更结果
8. **Lottery** 消费 PointsChangeEvent，同步本地账户状态

---

## 关键风险

### 1. 分布式事务

**现状**: 无 Saga/TCC 方案，依赖幂等性 + 定期对账。

**风险**: 任意一步失败可能导致数据不一致。

**应对策略**:
- 所有写操作必须幂等（基于业务唯一键去重）
- 定期对账任务发现并修复不一致数据
- 关键操作增加状态机，支持重试和回滚

### 2. Kafka 消息顺序

**风险**: Kafka 消息不保证顺序。多条积分变更消息可能乱序到达。

**应对策略**:
- 消费者基于版本号或时间戳判断消息新旧
- 使用乐观锁更新，防止旧消息覆盖新状态

### 3. 分片键不一致

**风险**: shop-points 按 `subject_id` 分片，Lottery 使用自己的分片策略。两个服务的分片键可能不一致，导致关联查询困难。

**应对策略**:
- 消息中必须携带 `subject_id`
- 跨服务查询通过 Dubbo RPC 接口，而非直连数据库

### 4. Dubbo RPC 超时/降级

**风险**: Dubbo RPC 超时或降级可能导致数据不一致。例如：积分已扣减但 Lottery 订单创建失败，或 Lottery 订单已创建但积分扣减超时。

**应对策略**:
- 设置合理的超时时间
- 关键接口实现补偿机制
- Dubbo 调用失败时记录异常日志，便于后续人工或自动修复

---

## 参考文档

`shop-points-lottery/SHOP_POINTS_IMPLEMENTATION_GUIDE.md` — shop-points 集成实施指南。

---
name: message-bus
description: "需要了解 Kafka 消息流或修改消费者时加载"
version: "0.1.0"
category: harness
tags:
  - wiki
  - kafka
  - messaging
  - consumer
  - producer
commands: []
---

# 消息总线

## shop-points Consumers（11 个）

所有 Consumer 位于 `shop-points-service/` 模块中。

| Consumer | 职责 |
|----------|------|
| `CoinConsumer` | 币平台回调消息处理 |
| `PointsChangeEventConsumer` | 积分变更事件消费 |
| `PointsDistributionEventMessageConsumer` | 积分分发事件消费 |
| `PointsDetailMessageConsumer` | 积分明细消息消费 |
| `CommissionEventMessageConsumer` | 佣金事件消费 |
| `EliteCommissionEventMessageConsumer` | 精英佣金事件消费 |
| `BroadcastEventConsumer` | 广播消息消费 |
| `DataSyncMessageConsumer` | 数据同步消费 |
| `MerchantMessageConsumer` | 商户消息消费 |
| `BpmConsumer` | BPM 工作流事件消费 |
| `CoinMessageConsumer` | 币消息消费 |

---

## shop-points Producer

**核心组件**:
- `KafkaMessageProducer` — 消息发送器
- `KafkaPushMessage` — 推送消息工具
- `KafkaMessageAssemble` — 消息构建器

**消息类型**:
- `EquityPointsEventMsg` — 权益积分事件
- `PointsDistributeMsg` — 积分分发消息
- `DealOrderMsg` — 交易订单消息
- 其他业务事件消息

---

## shop-points-lottery MQ

### Consumers（Listener）
路径：`shop-points-lottery-start/listener/`

| Listener | 职责 |
|----------|------|
| `ShopOrderCallbackListener` | 消费 commerce-shop 订单事件 |
| `SupplierEventListener` | 消费供应商事件 |

### Producers
路径：`shop-points-lottery-service/mq/producer/`

发送抽奖结果、商城订单等事件消息。

---

## 跨服务 Kafka 消息流

### shop-points → shop-points-lottery

`shop-points` 发送 `points_change_event_stream` 事件供 `shop-points-lottery` 消费。

**事件内容**:
- 包含 `subject_id`（分片路由必需）
- 积分变更类型、变更金额、变更前后余额
- 关联的业务单号

**流转路径**:
```
shop-points Service
  → KafkaMessageProducer 发送 points_change_event_stream
    → shop-points-lottery Consumer 消费
      → AccountBizService 账户同步
```

---

## 消费者修改规则

### 必须遵守的规则

1. **幂等消费**: 必须处理重复消息。Kafka 至少一次投递（at-least-once），消费者可能收到重复消息。
   ```java
   // 推荐：基于业务唯一键做幂等判断
   if (alreadyProcessed(messageId)) {
       log.warn("重复消息，跳过: {}", messageId);
       return;
   }
   ```

2. **分片键必须存在**: `subject_id` 必须存在于消息体中。缺少分片键将导致无法正确路由到分片表。

3. **层次分离**: Consumer 属于入口层，只调 Service，不直接访问 DAO。
   ```java
   // 正确：Consumer → Service → DAO
   @KafkaListener(topics = "xxx")
   public void onMessage(String message) {
       PointsEvent event = JSON.parseObject(message, PointsEvent.class);
       pointsService.handleEvent(event);  // 委托给 Service
   }

   // 错误：Consumer 直接操作 DAO
   @KafkaListener(topics = "xxx")
   public void onMessage(String message) {
       pointsMapper.insert(...);  // 禁止！
   }
   ```

4. **异常处理**: 消费失败应有明确的重试或死信队列策略，避免消息堆积。

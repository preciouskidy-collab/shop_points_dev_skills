---
name: message-bus-shop-points
description: "shop-points 的 Kafka 消费者、生产者和消息流"
version: "0.1.0"
category: knowledge
tags:
  - shop-points
  - kafka
  - messaging
  - consumer
  - producer
commands: []
---

# shop-points 消息总线

## Consumers（11 个）

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

## Producers

**核心组件**:
- `KafkaMessageProducer` — 消息发送器
- `KafkaPushMessage` — 推送消息工具
- `KafkaMessageAssemble` — 消息构建器

**消息类型**:
- `EquityPointsEventMsg` — 权益积分事件
- `PointsDistributeMsg` — 积分分发消息
- `DealOrderMsg` — 交易订单消息
- 其他业务事件消息

---
name: message-bus-shop-points-lottery
description: "shop-points-lottery 的 Kafka 消费者、生产者和消息流"
version: "0.1.0"
category: knowledge
tags:
  - shop-points-lottery
  - kafka
  - messaging
  - consumer
  - producer
commands: []
---

# shop-points-lottery 消息总线

## Consumers（Listener）

路径：`shop-points-lottery-start/listener/`

| Listener | 职责 |
|----------|------|
| `ShopOrderCallbackListener` | 消费 commerce-shop 订单事件 |
| `SupplierEventListener` | 消费供应商事件 |

---

## Producers

路径：`shop-points-lottery-service/mq/producer/`

发送抽奖结果、商城订单等事件消息。

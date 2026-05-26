---
name: message-bus-shop-points-lottery
description: "shop-points-lottery 的 Kafka 消费者、生产者和消息流"
version: "0.2.0"
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

## Consumers（3 个）

### ShopOrderCallbackListener
**路径**: `shop-points-lottery-start/listener/`
**Topic**: `plat-commerce-eshop-event-queue`（PROD）/ `plat-commerce-eshop-event-queue-commerce-jinbei-test01`（TEST）
**ContainerFactory**: `shopOrderContainerFactory`
**处理逻辑**:
1. 接收 commerce-shop 订单事件
2. 校验 `merchantCode`（默认 `shopPoints`，可配置 `shop.merchant-code`）
3. 委托 `ShopEventContext.processEvent(eventName, content)` 处理:
   - `OrderPayedFlowEvent` → `PaySuccessEventHandler`
   - `OrderPayFailedEvent` → `PayFailedEventHandler`
   - `RefundCompleteEvent` → `RefundSuccessEventHandler`
4. 事件内容经 AES 解密（密钥配置 `shop.secret`）

### SupplierEventListener
**路径**: `shop-points-lottery-start/listener/`
**Topic**: `shop-points-mall-supplier-event`（PROD）/ `shop-points-mall-supplier-event-test`（TEST）
**ContainerFactory**: `supplierEventContainerFactory`
**注解**: `@DS(dataSource = "shop_mall", forceMaster = true)` — 强制主库避免主从延迟
**处理逻辑**: 处理供应商事件（`SupplierEventTypeEnum`）:
- `FULFILLMENT_COMPLETED` — 确认发货
- `REFUND` — 供应商侧退款
- `PRODUCT_OFF_SHELF` — 商品下架 + 微信机器人通知

### RedStarMessageConsumer
**路径**: `shop-points-lottery-service/mq/`
**Topic**: `agent-redstar-reward-ack`（PROD）/ `agent-redstar-reward-ackMsg-test`（TEST）
**ContainerFactory**: `redStarContainerFactory`
**模式**: 批量消费（`List<ConsumerRecord>`），手动 ACK
**处理逻辑**: 消费贝壳币奖励发放结果，按 `COIN_TRADE_PREFIX("lottery_trade_")` 过滤，更新 `SubjectPrize` 状态从 DOING → DONE

---

## Producers（2 个）

### PointsChangeKafkaProducer
**路径**: `shop-points-lottery-service/mq/`
**Topic**: `points_change_event_stream`
**方法**:
| 方法 | 发送事件 |
|------|----------|
| `sendOrderPaySuccessEvent(orderId, subjectId)` | ORDER_PAY_SUCCESS |
| `sendOrderRefundSuccessEvent(refundNo, subjectId)` | ORDER_REFUND_SUCCESS |

**消息格式**: `{ eventId, eventTime, eventType, bizId, subjectId }`

### KafkaMessageProducer
**路径**: `shop-points-lottery-service/mq/producer/`
**模板**: `KebootKafkaTemplate<String, String>`
**方法**:
| 方法 | 说明 |
|------|------|
| `sendMsgAsyn(topic, message)` | 异步发送，带回调 |
| `sendMsg(topic, message)` | 同步发送，1000ms 超时，失败静默 |
| `sendMsgSync(topic, message)` | 同步发送，失败抛 RuntimeException |

---

## Kafka Topic 清单

| 配置键 | 角色 | PROD Topic | TEST Topic |
|--------|------|------------|------------|
| `kafka.config.red-star` | Consumer | `agent-redstar-reward-ack` | `agent-redstar-reward-ackMsg-test` |
| `kafka.config.shop-order` | Consumer | `plat-commerce-eshop-event-queue` | `plat-commerce-eshop-event-queue-commerce-jinbei-test01` |
| `kafka.config.supplier-event` | Producer + Consumer | `shop-points-mall-supplier-event` | `shop-points-mall-supplier-event-test` |
| `kafka.config.points-change` | Producer | `points_change_event_stream` | `points_change_event_stream` |

---

## 消息流

### 商城下单流程

```
用户下单 → Lottery Controller
  → ShopOrderBizService（本地订单创建）
  → commerce-shop（创建商城订单 + 支付）
  → commerce-shop Kafka → ShopOrderCallbackListener
    → PaySuccessEventHandler / PayFailedEventHandler
```

### 供应商发货流程

```
商城发货完成 → Kafka → SupplierEventListener
  → SupplierHandlerFactory.getHandler(supplierCode)
    → BJT / HQ / SP Handler 执行供应商侧操作
  → 更新本地订单状态
```

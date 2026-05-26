---
name: service-topology
description: "涉及 shop-points 和 shop-points-lottery 之间交互的需求时加载"
version: "0.2.0"
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

shop-points 和 shop-points-lottery 之间通过两种模式交互:

### Dubbo RPC（同步调用）

**Lottery → shop-points**: 通过 `ShopPointsRpc`（nacos 注册中心）调用 7 个 Facade:

| Facade | 用途 | 超时 |
|--------|------|------|
| `EquityPointsFacade` | 积分消耗/退还/余额查询/贝壳币发放 | 3000ms |
| `StarRightsFacade` | 星级数据查询 | 1000ms |
| `SubjectFacade` | 科目信息查询 | 1000ms |
| `RunningShopFacade` | 运营门店查询 | 1000ms |
| `ShopPermissionFacade` | 权限校验 | 1000ms |
| `ManagerPermissionFacade` | 管理权限 | 1000ms |
| `PerformanceCityFacade` | 城市转换 | 1000ms |

**适用场景**: 需要实时返回结果的操作（扣减积分、查询余额、权限校验）。

### Kafka Events（异步消息）

| 方向 | Topic | 消息类型 | 说明 |
|------|-------|----------|------|
| Lottery → shop-points | `points_change_event_stream` | ORDER_PAY_SUCCESS, ORDER_REFUND_SUCCESS | 积分变更通知 |
| shop-points → Lottery | `agent-redstar-reward-ack` | 贝壳币发放结果 | 更新奖品状态 |

**适用场景**: 状态变更通知、异步结果确认。

---

## 数据流

### 典型场景: 用户在积分商城下单

```
用户下单 → Lottery OrderController (/api/mall/order)
  → ShopOrderBizService
    ├── ShopProductProxy.getSku() — 验证商品/库存
    ├── ShopOrderProxy.createAndPay() — 创建 commerce 订单并支付
    ├── ProductOrderInfoDAO — 本地创建订单记录
    └── 返回支付信息

支付完成 → commerce-shop Kafka
  → ShopOrderCallbackListener (plat-commerce-eshop-event-queue)
    → ShopEventContext.processEvent()
      → PaySuccessEventHandler
        ├── ShopOrderProxy.getOrderStatus() — 确认支付
        ├── ShopPointsRpc.EquityPointsFacade.queryEquityPointsBalance() — 查余额
        ├── ProductOrderInfoDAO — 更新订单状态为 PAID
        ├── PointsChangeKafkaProducer.sendOrderPaySuccessEvent() — 通知 shop-points
        └── SupplierHandlerFactory.getHandler() — 触发供应商发货
```

### 典型场景: 抽奖消耗积分

```
用户抽奖 → Lottery H5ActivityController (/api/h5/activity)
  → LotteryService.draw()
    ├── ChanceService — 检查/扣减抽奖机会
    ├── ShopPointsRpc.EquityPointsFacade.consumePoints() — 同步扣减积分
    │     ↓ Dubbo RPC → shop-points EquityPointsFacadeImpl
    │       → EquityPointsService.consumePoints()
    │       → SubjectEquityPointsLedgerMapper — 更新积分账本
    ├── PrizeDispenser.distribute() — 发放奖品（策略模式）
    └── 返回抽奖结果
```

### 典型场景: 贝壳币奖品发放

```
Lottery KeCoinDispenser.distribute()
  → 生成 Excel → S3 上传
  → AssignRewardRpc.payBkCoin()
    → Dubbo(reward) → AssignRewardFacade.deliverRewardByFile()
      → 批量发放贝壳币
  → RedStarMessageConsumer 消费结果
    → agent-redstar-reward-ack
    → 更新 SubjectPrize 状态 DOING → DONE
```

---

## 外部服务依赖关系

```
                    ┌─────────────────────────┐
                    │      shop-points         │
                    │  (积分/权益/佣金核心)     │
                    └───────┬────────┬─────────┘
                   Dubbo ▲  │        │ ▲ Kafka
                         │  │        │ │
                    Dubbo│  │Kafka   │ │Dubbo
                         │  │        │ │
                    ┌────┴──┴────────┴─┴───────┐
                    │   shop-points-lottery      │
                    │   (抽奖/活动/积分商城)      │
                    └───────┬────────┬───────────┘
                          Dubbo    HTTP
                            │        │
                    ┌───────┴────────┴───────────┐
                    │   commerce-shop (订单/商品)  │
                    │   EHR/UC (用户/组织)         │
                    │   Reward (贝壳币奖励)        │
                    │   BJT/HQ (供应商)            │
                    │   Coin SDK (贝壳币)          │
                    └─────────────────────────────┘
```

---

## 关键风险

### 1. 分布式事务

**现状**: 无 Saga/TCC 方案，依赖幂等性 + 定期对账。

**风险点**: 积分扣减成功但本地订单创建失败 = 数据不一致。

**应对策略**:
- 所有写操作必须幂等（基于业务唯一键去重）
- `EliteCommissionEventMessageConsumer` 使用 Redis + DB 双重幂等去重
- 定期对账任务发现并修复不一致数据
- 关键操作增加状态机，支持重试和回滚

### 2. 主从延迟

**风险**: Kafka 消费者读从库可能读到旧数据。

**应对**: `SupplierEventListener` 使用 `@DS(dataSource = "shop_mall", forceMaster = true)` 强制主库。

### 3. Dubbo 超时

**配置**: `ShopPointsRpc` retries=0（不重试），EquityPointsFacade 超时 3000ms，其他 1000ms。

**风险**: 积分操作超时但实际已执行 → 幂等性是唯一保障。

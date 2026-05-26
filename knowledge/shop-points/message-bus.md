---
name: message-bus-shop-points
description: "shop-points 的 Kafka 消费者、生产者和消息流"
version: "0.2.0"
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

所有 Consumer 位于 `shop-points-service` 模块 `com.ke.shop.points.service.mq.consumer` 包。

| Consumer | Topic 配置键 | 职责 |
|----------|-------------|------|
| `PointsChangeEventConsumer` | `kafka.config.points-change` | 积分变更事件 — 异步执行积分消耗/退还 |
| `PointsDetailMessageConsumer` | `kafka.config.points-message` | 积分明细消息 — 分发给 `pointsCalcBizService` 处理 |
| `PointsDistributionEventMessageConsumer` | `kafka.config.points-distribution` | 积分分发事件 — 处理品牌和权益积分的分发 |
| `CommissionEventMessageConsumer` | `kafka.config.commission-event` | 佣金事件 — 插入佣金明细记录 |
| `EliteCommissionEventMessageConsumer` | `kafka.config.elite-commission-events` | 精英佣金事件 — 带 Redis + DB 幂等去重 |
| `CoinConsumer` | `kafka.config.coin-pay` | 贝壳币支付回调 — 更新发放计划或权益积分执行状态 |
| `CoinMessageConsumer` | `kafka.config.budget` | 预算管理回调 — 处理品牌/门店/抽奖/活动奖励的贝壳币结果 |
| `BroadcastEventConsumer` | `kafka.config.broadcast-message` | 广播消息 — 通过 BroadcastEventFactory 分发 |
| `DataSyncMessageConsumer` | `kafka.config.data-sync-group` | Hive→Kafka 数据同步 — 同步 15+ 种表（running_shop, running_brand, pinzhi_kesu 等） |
| `MerchantMessageConsumer` | `kafka.config.merchant` | 商户消息 — 处理门店退出/合并时的权益重置 |
| `BpmConsumer` | `kafka.config.bpm` | BPM 工作流事件 — 处理审批通过/驳回/取消 |

---

## Producers（1 个核心类）

**类**: `com.ke.shop.points.service.mq.producer.KafkaMessageProducer`
**模板**: `KebootKafkaTemplate<String, String>`

| 方法 | 说明 |
|------|------|
| `sendMsgAsyn(topic, message)` | 异步发送，带回调 |
| `sendMsg(topic, message)` | 同步发送，1000ms 超时，失败静默吞异常 |
| `sendMsgSync(topic, message)` | 同步发送，1000ms 超时，失败抛 RuntimeException |
| `sendMsgSyncWithKey(topic, key, message)` | 同步发送带 key（保证同一 key 路由到同一分区） |

---

## Kafka Topic 清单

| 配置键 | 角色 | PROD Topic | TEST Topic |
|--------|------|------------|------------|
| `points-change` | Consumer + Producer | `points_change_event_stream` | `points_change_event_stream` |
| `points-distribution` | Consumer + Producer | `points_distribution_event_stream` | `points_distribution_event_stream` |
| `rule-calc-event` | Producer | `lego_rule_calc_trigger_stream` | `lego_rule_calc_trigger_stream` |
| `supplier-event` | Consumer + Producer | `shop-points-mall-supplier-event` | `shop-points-mall-supplier-event-test` |
| `points-message` | Consumer | `points_message` | `points_message_test` |
| `commission-event` | Consumer | `commission-events` | `commission-events` |
| `elite-commission-events` | Consumer | `elite-commission-events` | `elite-commission-events` |
| `data-sync-group` | Consumer | `shop_points_data_sync_stream` | `shop_points_data_sync_stream` |
| `broadcast-message` | Consumer + Producer | `broadcast_message` | `broadcast_message_test` |
| `merchant` | Consumer | `commerce-merchant-renewal-item` | `commerce-merchant-renewal-item-test` |
| `bpm` | Consumer | `bpm-bpm-shop-points` | `bpm-bpm-shop-points` |
| `budget` | Consumer | `budget-manager-distribute-coin-event-prod` | `budget-manager-distribute-coin-event-test` |
| `coin-pay` | Consumer | `platCommerce-coin-AcctPayDetail` | `platCommerce-coin-test-ActPayDetail` |
| `shop_points_im` | Producer | `shop_points_im` | `shop_points_im_test` |

---

## 消息流模式

### 1. 积分消耗/退还（Dubbo → 异步执行）

```
外部 Dubbo 调用（lottery 等）→ EquityPointsFacadeImpl
  ├─ consumePoints() → 创建 EquityPointsExecInfo（状态 COIN_CHANGE_PENDING）
  │   └→ KafkaMessageProducer.sendMsgSyncWithKey(points_change_event_stream)
  ├─ refundPoints() → 创建 EquityPointsExecInfo（状态 REFUND_RECYCLE_PENDING）
  │   └→ KafkaMessageProducer.sendMsgSyncWithKey(points_change_event_stream)
  └→ 返回（不等待异步结果）

PointsChangeEventConsumer ← points_change_event_stream
  ├─ CONSUME_POINTS → PointsConsumeService.processConsumeExecRecord() → Coin 系统 RPC 扣减
  └─ REFUND_POINTS → PointsRefundService.processRefundExecRecord() → Coin 系统 RPC 退还
```

### 2. 算分 → 分发 链路（核心积分计算流水线）

```
多个触发源 → KafkaPushMessage.sendLegoCalcEvent()
  触发源: CommissionMessagePusher, StarLevelRatingBizService, BrandPointsBizService,
          ActRecoveryService, PinZhiOrderCreator, PointsUploadProcessor
  └→ lego_rule_calc_trigger_stream

Lego 算分引擎（外部）→ 计算积分 → 回写结果

PointsDetailMessageConsumer ← points_message
  ├→ 写入 lego_record_detail, lego_record_summary, period_points_summary, cur_star_right
  ├→ 创建 points_distribution_event DB 记录（待分发）
  └→ 可能触发星级刷新

定时任务 PointsDistributeJob → 读取 points_distribution_event
  └→ PointsDistributionBizService.distributePoints()
      └→ points_distribution_event_stream

PointsDistributionEventMessageConsumer ← points_distribution_event_stream
  ├→ BrandPointsBizService.processBrandPointsDistributionEvent()（品牌积分分发）
  └→ EquityPointsBizService.processEquityPointsDistributionEvent()（权益积分分发）
```

### 3. 发放 → 贝壳币打款链路

```
发放定时任务 DisbursementJob → DisbursementProcessor.payServ()
  └→ BudgetRpc.payCoin()（调用预算系统打款）

预算系统 → 异步回调
  └→ budget-manager-distribute-coin-event-prod

CoinMessageConsumer ← budget-manager-distribute-coin-event-prod
  ├→ Brand 路径 → BrandDisbursementProcessor.paySuccess()
  ├→ Shop 路径（默认）→ ShopDisbursementProcessor.paySuccessV2()
  ├→ actRewardCoin 路径 → ActRewardExecPlanService.markSuccessWithCurrentPayPeriod()
  └→ lotteryDelivery 路径 → 成功时发送 SupplierEventDTO(FULFILLMENT_COMPLETED)
      └→ shop-points-mall-supplier-event → [lottery SupplierEventListener 消费]

CoinConsumer ← platCommerce-coin-AcctPayDetail（币系统支付回调）
  ├→ EquityPointsPay 路径 → 更新 equity_points_exec_info 状态
  └→ 默认路径 → DisbursementProcessor.payServSuccess()（更新发放计划状态）
```

### 4. 佣金事件处理

```
佣金系统 → commission-events
  └→ CommissionEventMessageConsumer
      └→ 校验 eventType==SIGN_MATRIX_AGG_SHOP_COMMISMISSION + 时间约束
          └→ batch insert commission_event 表
              └→ 后续由 CommissionMessagePusher → lego_rule_calc_trigger_stream（进入算分链路）

精英佣金系统 → elite-commission-events
  └→ EliteCommissionEventMessageConsumer
      └→ 校验 eventType==SIGN_MATRIX_AGG_CLEARING + bizLine=="2"(新房)
          └→ Redis setIfAbsent 幂等 + DB 二次去重
              └→ batch insert elite_commission_event 表
```

### 5. 广播 → IM 推送

```
多个触发源 → KafkaPushMessage.sendBroadcastEvent()
  触发源: StarLevelRatingBizService, ReportStarUpgradeService, BroadCastJobService
  └→ broadcast_message

BroadcastEventConsumer ← broadcast_message
  └→ BroadcastEventFactory.doExec()
      ├→ 按角色筛选目标用户
      ├→ Redis 频控去重
      └→ KafkaPushMessage.sendImKafka()
          └→ shop_points_im → [IM 消息中心]
```

### 6. 数据同步

```
Hive 数据管道 → shop_points_data_sync_stream
  └→ DataSyncMessageConsumer（按 table_name 路由）

  同步的表:
  ├ running_shop → runningShopService.insertOrUpdate()
  ├ running_brand → runningBrandService.syncBrandInfo()
  ├ running_distributor → runningDistributorService.syncDistributorInfo()
  ├ performance_city_dict → 城市映射同步 + IM 通知
  ├ brand_integral_index → integralService.syncInfo()
  ├ equity_reset_shop → shopBizService.resetShopEquityAccount()
  ├ serv_reset_shop → disbursementProcessor.recycleAccount()
  ├ pinzhi_kesu/punish/win_win → pinzhiDataSyncService.process*Data()
  ├ contract_info → contractInfoMapper.insertOrUpdate()
  └ 其他: new_brand_rating_indicator, monthly_shop_predict_commission,
          reg_score_info, deal_order, cdel_transform_info
```

### 7. 商户退出/合并

```
商户系统 → commerce-merchant-renewal-item
  └→ MerchantMessageConsumer
      └→ 过滤: QUIT + BEFORE_STOP_COOP + STORE + FCH_QUIT/STORE_QUIT/STORE_MERGE
          └→ shopNotifyService.notifyEquityRest()（重置门店权益账户）
```

### 8. BPM 工作流

```
BPM 系统 → bpm-bpm-shop-points
  └→ BpmConsumer
      └→ 查找 ProcessInst + 对应 BpmProcessHandler
          ├→ TERMINATE → handler.cancel()
          ├→ FINISH + NOT_PASS → handler.notPass()
          └→ FINISH + PASS → handler.auditPass()
```

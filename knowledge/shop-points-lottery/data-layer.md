---
name: data-layer-shop-points-lottery
description: "shop-points-lottery 的数据库结构和数据源切换"
version: "0.2.0"
category: knowledge
tags:
  - shop-points-lottery
  - database
  - mybatis
commands: []
---

# shop-points-lottery 数据层

## 双数据库

### shop_lottery（活动库，默认数据源）

| 表名 | 实体类 | 用途 |
|------|--------|------|
| `activity_info` | `ActivityInfo` | 活动（id, projectId, cityCode, title, actType, entryConditions, startDate, endDate, status, onSale, freeChance） |
| `activity_prize` | `ActivityPrize` | 活动奖品配置 |
| `activity_task` | `ActivityTask` | 活动任务 |
| `activity_black_white` | `ActivityBlackWhite` | 黑白名单 |
| `subject_chance` | `SubjectChance` | 用户抽奖机会 |
| `subject_chance_obtain_log` | `SubjectChanceObtainLog` | 机会获取日志 |
| `subject_draw_record` | `SubjectDrawRecord` | 抽奖记录 |
| `subject_prize` | `SubjectPrize` | 用户奖品（id, subjectId, actId, prizeId, prizeType, prizeTitle, prizeValue, status: 0/1/2, displayStatus, extraData, tradeNo） |
| `subject_exchange_code` | `SubjectExchangeCode` | 兑换码（exchangeCode, actId, prizeId, subjectId, bizUniqueId, status, effectDate, expireDate） |
| `subject_exchange_code_consume_log` | `SubjectExchangeCodeConsumeLog` | 兑换码消费日志 |
| `subject_task_reward_record` | `SubjectTaskRewardRecord` | 任务奖励记录 |
| `upload_record` | `UploadRecord` | 上传记录 |

### shop_mall（商城库）

| 表名 | 实体类 | 用途 |
|------|--------|------|
| `product_info` | `ProductInfo` | 商品（id, productName, categoryName, cityCode, supplierProductId, supplierConfig, payConfig, salesCondition, originPrice, salePrice, onShelfTime, offShelfTime, haveInventory, initialStock, status） |
| `product_order_info` | `ProductOrderInfo` | 订单（id, orderId, shopOrderId, productId, ucid, subjectId, quantity, unitPrice, sellAmount, settleAmount, status: INIT=0→RECEIVED=5, paymentTime） |
| `product_order_trace` | `ProductOrderTrace` | 订单轨迹 |
| `product_delivery_info` | `ProductDeliveryInfo` | 物流信息 |
| `product_refund_order_info` | `ProductRefundOrderInfo` | 退款订单 |
| `buy_limit_config` | `BuyLimitConfig` | 限购配置 |

---

## 数据源配置

**动态数据源**: `datasource.use-dynamic: true`, 默认 `shop_lottery`

**数据源切换**: `@DS` 注解

```java
@DS(dataSource = "shop_lottery")
public List<ActivityInfo> queryActivities(...) { ... }

@DS(dataSource = "shop_mall")
public List<ProductInfo> queryProducts(...) { ... }

// 强制主库（用于 Kafka 消费者避免主从延迟）
@DS(dataSource = "shop_mall", forceMaster = true)
```

**主从配置**: 每个数据源都有独立的 master/slave 对。

**无 ShardingSphere**: 不使用分片，仅通过 `@DS` 做数据源切换。

---

## MyBatis 模式

### Mapper 继承体系

```java
public interface BaseMapper<T> extends
    tk.mybatis.mapper.common.BaseMapper<T>,   // 单表 CRUD
    IdsMapper<T>,                              // 按 ID 列表查询
    ExampleMapper<T>,                          // 条件构造器查询
    InsertListMapper<T> {                      // 批量插入
}
```

### XML 分层

| 目录 | 数量 | 用途 |
|------|------|------|
| `mappers/` | 19 | MBG 自动生成的基础 CRUD |
| `manualMappers/` | 5 | 手写自定义 SQL（`ActivityPrizeManualMapper`, `BuyLimitConfigManualMapper`, `ProductOrderTraceManualMapper`, `ProductRefundOrderInfoManualMapper`, `SubjectChanceManualMapper`） |

---

## 关键状态机

### 订单状态（ProductOrderInfo.status）

```
INIT(0) → PAID(1) → SHIPPED(4) → RECEIVED(5)
  ↓
PAY_FAILED(2)
```

### 奖品状态（SubjectPrize.status）

```
0 (待处理) → 1 (处理中) → 2 (完成)
```

### 兑换码状态（ExchangeCodeStatus 枚举）

通过 `SubjectExchangeCode.status` 字段控制兑换码生命周期。

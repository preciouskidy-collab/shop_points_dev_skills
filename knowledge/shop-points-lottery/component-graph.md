---
name: component-graph-shop-points-lottery
description: "shop-points-lottery 的 Maven 模块布局、包结构和依赖链"
version: "0.2.0"
category: knowledge
tags:
  - shop-points-lottery
  - module
  - maven
  - structure
commands: []
---

# shop-points-lottery 组件图谱（5 个模块）

**GAV**: `com.ke.shop.points.lottery:shop-points-lottery:1.0.0-SNAPSHOT`
**Parent**: `com.lianjia.infrastructure:infrastructure-starter-parent:2.1.29`
**Java**: 1.8 | **Spring Cloud**: Greenwich.SR3
**shop-points-api 依赖**: `1.0.20-RELEASE`

---

### shop-points-lottery-api
**定位**: DTO + 常量。独立模块，无内部依赖。

**DTO（67 个）**:
- `api/dto/` — 34 个活动/抽奖相关 DTO（`LotteryRequestDTO`, `LotteryResponseDTO`, `ActivityDetailDTO`, `UserPrizeDTO`, `ClaimTaskRewardRequestDTO` 等）
- `api/dto/mall/` — 33 个商城相关 DTO（`CreateOrderRequest`, `ProductDTO`, `OrderDetailDTO`, `ApplyRefundRequest`, `SupplierConfig` 等）

**枚举（4 个）**: `ProductInstructionEnum`, `ShelfStatusEnum`, `SupplierCodeEnum`, `SupplierProductBizTypeEnum`

**常量**: `Constants` — `COIN_TRADE_PREFIX = "lottery_trade_"`, `STAR_LEVEL_1_TO_10`, `NEW_SHOP_LEVEL = -100`

---

### shop-points-lottery-common
**定位**: 工具类、响应包装器、枚举。

**核心组件**:

| 类别 | 类 | 说明 |
|------|---|------|
| AOP | `RedisLock` + `RedisLockAspect` | 分布式锁注解 + 切面 |
| AOP | `TimedCheck` + `TimedCheckAspect` | 耗时检查 |
| 响应 | `Message<T>`, `Rst`, `RstEnums` | API 响应包装 |
| 异常 | `BusinessException` | 业务异常 |
| 工具 | `Snowflake`, `IdGenerator`, `JsonUtils`, `ExcelUtils`, `DateUtils`, `RedisKeyUtils`, `ProfileUtils`, `ApplicationContextUtil` | 通用工具 |
| S3 | `S3Private`, `S3Public`, `S3Cfg`, `PrivateS3Cfg`, `PublicS3Cfg`, `TestS3Cfg` | 文件上传 |
| 枚举 | `ActTypeEnum`, `ProjectEnum`, `PayGroupEnum`, `TransTypeEnum`, `ExchangeCodeStatus`, `SubjectPrizeStatusEnum` 等 16 个 | 业务枚举 |

---

### shop-points-lottery-dao
**定位**: 数据访问层。

**BaseMapper**: 继承 `tk.mybatis.mapper.common.BaseMapper<T>` + `IdsMapper<T>` + `ExampleMapper<T>` + `InsertListMapper<T>`

**Mapper Interface**: 18 个

| Mapper | 实体 |
|--------|------|
| `ActivityInfoMapper` | `ActivityInfo`（活动信息） |
| `ActivityPrizeMapper` | `ActivityPrize`（活动奖品） |
| `ActivityTaskMapper` | `ActivityTask`（活动任务） |
| `ActivityBlackWhiteMapper` | `ActivityBlackWhite`（黑白名单） |
| `SubjectChanceMapper` | `SubjectChance`（用户机会） |
| `SubjectChanceObtainLogMapper` | `SubjectChanceObtainLog`（机会获取日志） |
| `SubjectDrawRecordMapper` | `SubjectDrawRecord`（抽奖记录） |
| `SubjectPrizeMapper` | `SubjectPrize`（用户奖品，含 status/displayStatus） |
| `SubjectExchangeCodeMapper` | `SubjectExchangeCode`（兑换码） |
| `SubjectExchangeCodeConsumeLogMapper` | `SubjectExchangeCodeConsumeLog`（兑换码消费日志） |
| `SubjectTaskRewardRecordMapper` | `SubjectTaskRewardRecord`（任务奖励记录） |
| `ProductInfoMapper` | `ProductInfo`（商品信息） |
| `ProductOrderInfoMapper` | `ProductOrderInfo`（订单，status: 0-5） |
| `ProductOrderTraceMapper` | `ProductOrderTrace`（订单轨迹） |
| `ProductDeliveryInfoMapper` | `ProductDeliveryInfo`（物流信息） |
| `ProductRefundOrderInfoMapper` | `ProductRefundOrderInfo`（退款订单） |
| `BuyLimitConfigMapper` | `BuyLimitConfig`（限购配置） |
| `UploadRecordMapper` | `UploadRecord`（上传记录） |

**MyBatis XML**: 19 个自动生成 + 5 个手写（`manualMappers/`）

**实体枚举**: `OrderStatusEnum`（INIT=0, PAID=1, PAY_FAILED=2, REFUNDED=3, SHIPPED=4, RECEIVED=5）, `RefundStatusEnum`, `DeliveryStatusEnum`, `SupplierEventTypeEnum`

依赖 `shop-points-lottery-api`。

---

### shop-points-lottery-service
**定位**: 核心业务逻辑。

**子包结构**:

| 子包 | 职责 |
|------|------|
| `service/` (根) | `ActivityService`, `LotteryService`, `ChanceService`, `PrizeService`, `TaskService`, `ExchangeCodeService`, `BlackWhiteListService`, `ProductService`, `SubjectConditionService` |
| `service/account/` | `AccountBizService` — 账户业务 |
| `service/mall/` | `ShopOrderBizService`, `ProductBizService`, `DeliveryBizService`, `RefundInfoService`, `OrderTraceService`, `CoinPackMonthlyLimitService`, `UcSearchService` |
| `service/mall/supplier/` | 供应商处理（工厂模式） |
| `service/mall/schedule/` | `OrderScheduleTask`, `DeliveryScheduleTask`, `ProductScheduleTask`, `RefundScheduleTask` |
| `service/prize/` | 奖品发放（策略模式） |
| `service/prize/schedule/` | `PrizeScheduleTask` |
| `service/shop/` | 商城事件处理（`PaySuccessEventHandler`, `PayFailedEventHandler`, `RefundSuccessEventHandler`） |
| `service/subject/` | 科目条件处理器 |
| `service/upload/` | 上传处理（`BlackAndWhiteUploadProcessor`, `ProductUploadProcessor`） |
| `service/mq/` | `PointsChangeKafkaProducer`, `RedStarMessageConsumer` |
| `service/mq/producer/` | `KafkaMessageProducer` |
| `service/permission/` | `ShopPermissionService` |
| `service/rpc/` | 外部服务调用（详见 rpc-contracts.md） |
| `service/download/` | 下载处理 |
| `service/im/` | 微信机器人 `WeiXinWorkRobotService` |
| `service/cfg/` | `ApolloCfg` |
| `model/dto/` | 内部 DTO（`ShopInfo`, delivery, product, refund, upload） |

### 设计模式

**1. PrizeDispenser 策略模式**（奖品发放）:

| 实现类 | 奖品类型 | 发放方式 |
|--------|----------|----------|
| `KeCoinDispenser` | 贝壳币 | 生成 Excel → S3 → `AssignRewardRpc.payBkCoin()` |
| `CustomCouponDispenser` | 自定义兑换码 | 生成兑换码 → 写 `subject_exchange_code` |
| `VirtualPrizeDispenser` | 虚拟奖品 | 设置 voucher 为 bizUniqueId |

**2. SupplierHandlerFactory 工厂模式**（供应商处理）:

| 实现类 | supplierCode | 调用方式 |
|--------|-------------|----------|
| `SupplierBjtHandler` | BJT | HTTP → BJT OAuth API |
| `SupplierHqHandler` | HQ | HTTP → 花桥 OAuth API |
| `SupplierSpHandler` | SP | Dubbo → `EquityPointsFacade.issueBKCoin()` |
| `DefaultHttpSupplierHandler` | default_http | HTTP 通用 |

**3. ShopEventContext 策略模式**（商城事件）:
- `PaySuccessEventHandler` / `PayFailedEventHandler` / `RefundSuccessEventHandler`

依赖 `shop-points-lottery-dao`, `shop-points-lottery-api` + Dubbo 引用 `shop-points-api`。

---

### shop-points-lottery-start
**定位**: Spring Boot 入口。

**入口类**: `com.ke.shop.points.lottery.Application`（`@EnableApolloConfig` + `@SpringCloudApplication`）

**Controller（14 个）**:

| 子包 | 类 | Base Path |
|------|---|-----------|
| `controller/` | `ActivityController` | `/manage/activity` |
| | `BackController` | `/back` |
| | `BackCoinController` | `/back/coin` |
| | `BackProductController` | `/back/product` |
| | `AccountController` | `/account` |
| | `ExchangeCodeApiController` | `/api/exchange-code` |
| | `H5ActivityController` | `/api/h5/activity` |
| | `WelcomeController` | `/api/v1/hello` |
| `controller/mall/` | `OrderController` | `/api/mall/order` |
| | `ProductController` | `/api/mall/product` |
| | `ShopWebController` | `/api/mall/web` |
| | `InventoryController` | `/api/inventory` |
| `controller/manage/` | `ManageController` | `/manage/product` |
| | `UploadProductController` | `/manage/product/upload` |
| | `CoinPackLimitController` | `/manage/coinPackLimit` |

**Listener（Kafka 消费者）**:

| 类 | Topic（PROD） |
|----|---------------|
| `ShopOrderCallbackListener` | `plat-commerce-eshop-event-queue` |
| `SupplierEventListener` | `shop-points-mall-supplier-event` |

**Filter（3 个）**: `CurrentUserFilter`, `OAuthRouterAuthorizationFilter`（`/api/*`）, `SupportUcidFilter`

**Config（7 个）**: `AsyncConfiguration`, `MvcConfig`（CORS, OAuth filter 注册）, `RedisConfig`, `RestTemplateConfiguration`（含 `oAuthRestTemplate`）, `IdGeneratorConfiguration`, `JsonMessageConvert`

**其他**: `GlobalExceptionHandler`, `ShopPointsCacheManager`

依赖 `shop-points-lottery-service`。

---

## 本地启动

```bash
# 修改 service 代码后必须先 install，否则 spring-boot:run 使用旧 jar
mvn install -pl shop-points-lottery-service -am -DskipTests
mvn spring-boot:run -pl shop-points-lottery-start -Dspring-boot.run.profiles=test
```

本地应用地址: `http://local.ttb.test.ke.com`（不用 localhost）

---

## 依赖图

```
api (standalone)
common (standalone)
dao ← api
service ← dao, api, common (+ Dubbo ref to shop-points-api)
start ← service
```

## Dubbo 注册中心

| 名称 | 协议 | 用途 |
|------|------|------|
| `nacos` | nacos-endpoint | shop-points Facade（7 个接口） |
| `jichu` | zookeeper | EHR 用户/组织 |
| `reward` | zookeeper | 贝壳币奖励发放 |
| `shop` | zookeeper | commerce 商城订单/商品 |

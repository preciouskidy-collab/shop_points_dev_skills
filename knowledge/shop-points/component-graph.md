---
name: component-graph-shop-points
description: "shop-points 的 Maven 模块布局、包结构和依赖链"
version: "0.2.0"
category: knowledge
tags:
  - shop-points
  - module
  - maven
  - structure
commands: []
---

# shop-points 组件图谱（8 个模块）

**GAV**: `com.ke.shop.points:shop-points:1.0.20-RELEASE`
**Parent**: `com.lianjia.infrastructure:infrastructure-starter-parent:2.1.26`
**Java**: 1.8 | **Spring Cloud**: Greenwich.SR3 | **Dubbo**: 2.7.3.9-RELEASE

---

### shop-points-api
**定位**: Dubbo RPC 接口契约 + DTO。被 shop-points-lottery 等外部服务依赖。

**11 个 Facade 接口**:

| 接口 | 关键方法 |
|------|----------|
| `EquityPointsFacade` | `consumePoints(ConsumePointsReq)`, `refundPoints(RefundPointsReq)`, `queryEquityPointsBalance(QueryEquityPointsBalanceReq)`, `issueBKCoin(IssueBKCoinRequest)`, `reissueBKCoin(IssueBKCoinRequest)` |
| `StarRightsFacade` | `fetchShopPoints(shopCode, endDate)`, `initCurStarRights(List<CurStarRightDTO>)`, `initBrandCurStarRights(...)`, `initFjhCurStarRights(...)`, `cleanCurStarRight(cityCode)`, `getSubjectCurrentStarLvAndGradeLv(project, subjectId)` |
| `SubjectFacade` | `findSubject(project, subjectId)` |
| `RuleConfigFacade` | `fetchStarLevelConfig(...)`, `fetchBizCoefConfig(...)`, `fetchGradeRuleConfig(...)`, `applyCalcShopEfficiency(...)`, `applyStarLevelConfig(...)`, `applyBizCoefConfig(...)`, `applyGradeRuleConfig(...)`, `applyCoinStrategyRuleConfig(...)` |
| `RunningShopFacade` | `findRunningShop(shopCode)` |
| `DictFacade` | `fetchCityItem(shopCode)` |
| `EquityStrategyFacade` | `initEquityStrategy(SyncStrategyReq)`, `initEquityStrategies(List)`, `fetchEquityStrategies(cityCode)` |
| `ShopPermissionFacade` | `hasEquityPermission(...)`, `userHasSubjectPermission(...)`, `queryShopCodesByUcId(ucId)`, `hasRole(...)` |
| `ManagerPermissionFacade` | `isAdmin(project, userId)`, `hasThisCityPermission(...)`, `permissionCityList(...)` |
| `PerformanceCityFacade` | `fetchCityCode(performanceCityCode)`, `convert2PerformanceCityCode(...)`, `getCityName(...)`, `cityName2PerformanceCityCode(...)`, `cityName2CityCode(...)`, `cityIsOpen(...)` |
| `ShopBlacklistFacade` | `queryBlackStatus(List<shopCodes>)` |

**DTO/Request/Response**: 45 个类（`ConsumePointsReq`, `RefundPointsReq`, `IssueBKCoinRequest`, `QueryEquityPointsBalanceReq`, `ShopPoints`, `SubjectDTO`, `SubjectLvInfo` 等）

**修改注意**: 此模块是对外契约，变更需保证向后兼容。

---

### shop-points-model
**定位**: 共享领域模型。PO、BO、DTO、枚举。

**462 个 Java 文件**:

| 子包 | 文件数 | 内容 |
|------|--------|------|
| `model/dto/` | 241 | DTO（含 act/, mq/, http/, kafka/ 等子包） |
| `model/enums/` | 130 | 所有枚举（状态、类型、事件枚举） |
| `model/po/` | 55 | 持久化实体对象 |
| `model/extra/` | 28 | 附加数据结构 |
| `model/bo/` | 5 | 业务对象/常量 |
| `model/bpm/` | 2 | BPM 事件模型 |
| `model/user/` | 1 | 用户模型 |

依赖 `shop-points-commons`。

---

### shop-points-commons
**定位**: 工具类库。独立模块，无内部依赖。

**核心工具**: `DateMath`, `PeriodUtils`, `ExcelUtils`, `Snowflake`, `BeanCopyUtils`, `S3Upload`

---

### shop-points-dao
**定位**: MyBatis 数据访问层。

**规模**: Mapper Interface 107 个 + XML 103 个（auto-generated） + 手写 XML 51 个

**BaseMapper**: 继承 `tk.mybatis.mapper.common.BaseMapper<T>` + `IdsMapper<T>` + `ExampleMapper<T>` + `InsertListMapper<T>`，额外提供 `executeUpdate(@Param("sql"))` 动态 SQL 能力

**4 个分片策略类**（`dao.strategy` 包）:

| 类 | 分片键 | 算法 | 分片数 |
|----|--------|------|--------|
| `SubjectEquityPointsLedgerSplitTableStrategy` | `subject_id` | 取末 2 位 → 00-99 | 100 |
| `SubjectEquityPointsEarnBatchSplitTableStrategy` | `subject_id` | 取末 2 位 → 00-99 | 100 |
| `LegoRecordSummarySplitTableStrategy` | `subject_id` | 取末 2 位 → 00-99 | 100 |
| `HistorySplitTableStrategy` | `ctime` | 按年份后缀（_2024.._2028） | 5/年 |

依赖 `shop-points-model`。

---

### shop-points-service
**定位**: 核心业务逻辑。

**33 个子包**（按规模排列）:

| 子包 | 文件数 | 职责 |
|------|--------|------|
| `equity/` | 22 | 权益积分业务 |
| `rule/` | 21 | 规则配置 |
| `biz/` | 21 | 核心业务 |
| `points/` | 20 | 积分计算 |
| `facade/` | 11 | Dubbo Facade 实现 |
| `permission/` | 9 | 权限校验 |
| `brand/` | 9 | 品牌场景 |
| `act/` | 9 | 活动模块 |
| `reach/` | 8 | 推送/触达 |
| `fjh/` | 5 | FJH 星级评定 |
| `commission/` | 4 | 佣金计算 |
| `broadcast/` | 4 | 广播消息 |
| `download/` | 3 | 下载服务 |
| `disbursement/` | 3 | 发放/打款 |
| `settlement/` | 2 | 结算 |
| `mq/` | 12 | Kafka Consumer 11 + Producer 1 |
| 其他 | — | upload, report, diff, dict, im, hint, bpm, dataarchive, blacklist, split, pinzhi, shop, page |

依赖 `shop-points-dao`, `shop-points-api`, `shop-points-rpc`。

---

### shop-points-rpc
**定位**: 外部服务代理（Dubbo + HTTP）。

**26 个代理类**（核心）:

| 代理类 | 外部服务 | 协议 |
|--------|----------|------|
| `EquityRpc` | 权益服务 | Dubbo (nacos) → `EquityBizFacade`, `EquityThresholdBizFacade` |
| `BudgetRpc` / `ShopPayRpc` / `BrandPayRpc` | 预算服务 | Dubbo (commerce) → `BudgetExecutionFacade` |
| `ContractProxy` | 合同服务（璞租） | Dubbo (puzu) + HTTP |
| `OAuthServiceProxy` | EHR/UC 网关 | HTTP RestTemplate |
| `UcSnapshotServiceProxy` | UC 快照服务 | HTTP (带重试) |
| `ThirdBizService` | 多服务门面 | 封装 OAuthServiceProxy |
| `CreditProxy` | 信贷服务 | HTTP |
| `MdmProxy` | 主数据管理 | HTTP |
| `MerchantProxy` / `MerchantDistributorProxy` | 商户内核服务 | Dubbo |
| `IMCenterProxy` | IM 消息中心 | HTTP |
| `JmsProxy` | 门店服务 | HTTP |
| `HdicQueryServiceImpl` | 房源字典 | OpenAPI SDK |
| `BpmConfiguration` | BPM 工作流 | Dubbo (AWS) |
| `BrandMasterSnapshotClient` | 品牌主数据同步 | Feign |
| `NewPermissionClient` | 权限服务 | Feign |
| `QuarkUnicornServiceProxy` | 新房项目服务 | HTTP |
| `TaurusNhserviceServiceProxy` | 新房交易服务 | HTTP |
| `HiveApiProxy` | Hive 数据 | HTTP |
| `SpCalcProxy` | 佣金计算服务 | HTTP |
| `PosterCreator` | 海报生成 | HTTP (HTML→JPG) |

依赖 `shop-points-commons`, `shop-points-model`。

---

### shop-points-start
**定位**: Spring Boot 入口。

**Controller 分层**:

| 子包 | 控制器数 | 前缀 | 用途 |
|------|----------|------|------|
| `api/` | 5 | `/shop-points/api` | 对外 Dubbo API 端点 |
| `web/` | 17 | `/shop-points/web` | H5 前端页面接口 |
| `manage/` | 41 | `/back` + `/shop-points/manage` | 后台管理（含 rule/, act/, upload/, fjh/ 子包） |
| `open/` | 1 | `/shop-points/open` | 开放 API（AppCard） |
| `widget/` | 1 | `/widget` | 嵌入式组件 |
| 根 | 1 | — | WelcomeController |

**manage/ 子包**:
- `manage/rule/` — 星级/系数/成长/钻石/兑换/发放/拆分/活动/黑白名单/品牌/品质规则（20 个控制器）
- `manage/act/` — 活动后台/字典/实例/商圈/预估/模板（6 个控制器）
- `manage/upload/` — 积分/黑白名单/商圈/目标门店/计算门店上传（6 个控制器）
- `manage/fjh/` — FJH 星级/黑白名单/活动/积分管理（4 个控制器）

依赖 `shop-points-service`, `shop-points-schedule`。

---

### shop-points-schedule
**定位**: 定时任务。使用 lianjia-schedule 框架（`AssignmentContext` 参数），非 Spring `@Scheduled`。

**44 个任务类**，主要任务:

| 类 | 方法 |
|----|------|
| `StarRatingSchedule` | `starLevelRatingV2`, `starLevelRating` |
| `DailyCalcShopStarJob` | `dailyCalcShopStar` |
| `CommissionSchedule` | `findAndInsertCommissionDetail`, `pushCommissionDetail`, `confirmRetrospect` |
| `EliteCommissionSchedule` | `pushAgentCityCommissionDetail`, `pushEliteCommissionDetail` |
| `FjhStarLevelRatingSchedule` | `starLevelRating` |
| `DisbursementJob` | `disbursementCheck`, `disbursementJobCreatePlan`, `disbursementJobPayment`, `disbursementJobAdjustPayment` |
| `BrandDisbursementJob` | `disbursementJobCreatePlan`, `disbursementJobPayment`, `disbursementPayCheck` |
| `DataArchiveJob` | `archiveHistoryCommissionDetail`, `archiveHistoryCommissionStatus`, `archiveLegoRecordDetail`, `archiveDailyEquitySettlement` |
| `RunningShopSchedule` | `curStarRightPeriodInit`, `initNewShop`, `runningShopVerify`, `executePushBirth` |
| `BizBroadcastSchedule` | `sendRatingReport`, `sendMilestoneUpgrade`, `starUpgradeReport`, `milestoneExchangeEquityHighs` |
| `WeekPosterJob` | `checkFix`, `toReachDetail`, `toEffectData`, `buildPoster`, `sendPoster` |
| `ActRewardExecPlanJob` | `execute`, `executePointsOnly`, `executeCoinOnly` |
| `SubjectEquityPointsExpireSchedule` | `expirePoints` |
| `EquityPointsDistributionSchedule` | `processDistributionEvents` |
| `SubjectStrategyEquitySchedule` | `executeStrategyAndSettlement`, `executeFjhStrategyAndSettlement` |
| `PointsDistributeJob` | `pushPointsDistributionEvent2Kafka` |

依赖 `shop-points-service`。

---

## 依赖图

```
api (standalone)
commons (standalone)
model ← commons
dao ← model
rpc ← commons, model
service ← dao, api, rpc
schedule ← service
start ← schedule, service
```

## Dubbo 注册中心

| 名称 | 协议 | 地址 |
|------|------|------|
| `jichu` | zookeeper | zk01-03, group jichu3/dubbo |
| `nacos` | nacos-endpoint | namespace public-dubbo |
| `puzu` | zookeeper | zk01-03, group home/dubbo |
| `mlszk` | zookeeper | zk01, group /home3/qianqian/dubbo |

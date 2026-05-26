---
name: rpc-contracts-shop-points
description: "shop-points 提供和消费的 Dubbo RPC 接口"
version: "0.2.0"
category: knowledge
tags:
  - shop-points
  - dubbo
  - rpc
  - interface
commands: []
---

# shop-points RPC 契约

## 提供的 Dubbo 接口（shop-points-api）

路径: `shop-points-api/` | 包: `com.ke.shop.points.api`

### EquityPointsFacade — 积分操作（最核心，被 lottery 高频调用）

| 方法 | 签名 | 说明 |
|------|------|------|
| 消耗积分 | `Long consumePoints(ConsumePointsReq)` | 返回扣减后的余额 |
| 退还积分 | `Long refundPoints(RefundPointsReq)` | 返回退还后的余额 |
| 查询余额 | `BigDecimal queryEquityPointsBalance(QueryEquityPointsBalanceReq)` | 查询权益积分余额 |
| 发放贝壳币 | `String issueBKCoin(IssueBKCoinRequest)` | 发放贝壳币，返回交易号 |
| 补发贝壳币 | `String reissueBKCoin(IssueBKCoinRequest)` | 补发失败的贝壳币 |

### StarRightsFacade — 星级权益

| 方法 | 签名 | 说明 |
|------|------|------|
| 查询门店积分 | `ShopPoints fetchShopPoints(String shopCode, LocalDate endDate)` | — |
| 初始化当期星级 | `void initCurStarRights(List<CurStarRightDTO>)` | — |
| 初始化品牌星级 | `void initBrandCurStarRights(List<BrandCurStarRightDTO>, String dateValue)` | — |
| 初始化 FJH 星级 | `void initFjhCurStarRights(List<FjhCurStarRightDTO>, String dateValue)` | — |
| 清除当期星级 | `void cleanCurStarRight(Integer cityCode)` | — |
| 查询星级等级 | `SubjectLvInfo getSubjectCurrentStarLvAndGradeLv(String project, String subjectId)` | — |

### SubjectFacade — 科目信息

`SubjectDTO findSubject(String project, String subjectId)`

### RuleConfigFacade — 规则配置

| 方法 | 说明 |
|------|------|
| `fetchStarLevelConfig(performanceCityCode, localDateTime)` | 星级规则 |
| `fetchBizCoefConfig(performanceCityCode, localDateTime)` | 系数规则 |
| `fetchGradeRuleConfig(performanceCityCode, localDateTime)` | 等级规则 |
| `applyCalcShopEfficiency(CalcExtraInfo)` | 计算门店效率 |
| `applyStarLevelConfig(CalcStarRuleInfo)` | 应用星级配置 |
| `applyBizCoefConfig(CalcBizCoefRuleInfo)` | 应用系数配置 |
| `applyGradeRuleConfig(CalcGradeDTO)` | 应用等级配置 |
| `applyCoinStrategyRuleConfig(CalcCoinStrategyDTO)` | 应用贝壳币策略 |

### RunningShopFacade — 运营门店
`RunningShopDTO findRunningShop(String shopCode)`

### DictFacade — 字典
`CityItemDTO fetchCityItem(String shopCode)`

### EquityStrategyFacade — 权益策略
`void initEquityStrategy(SyncStrategyReq)` / `void initEquityStrategies(List)` / `CalcCoinStrategyDTO fetchEquityStrategies(Integer cityCode)`

### ShopPermissionFacade — 权限
`hasEquityPermission(...)`, `userHasSubjectPermission(...)`, `queryShopCodesByUcId(ucId)`, `hasRole(...)`

### ManagerPermissionFacade — 管理权限
`isAdmin(project, userId)`, `hasThisCityPermission(...)`, `permissionCityList(...)`

### PerformanceCityFacade — 业绩城市
`fetchCityCode(...)`, `convert2PerformanceCityCode(...)`, `getCityName(...)`, `cityName2CityCode(...)`, `cityIsOpen(...)`

### ShopBlacklistFacade — 黑名单
`List<ShopBlackInfo> queryBlackStatus(List<String> shopCodes)`

---

## 消费的外部 Dubbo/HTTP 服务（shop-points-rpc）

路径: `shop-points-rpc/`

### Dubbo 服务

| 代理类 | 注册中心 | 接口 | 用途 |
|--------|----------|------|------|
| `EquityRpc` | nacos | `EquityBizFacade`, `EquityThresholdBizFacade` | 权益数据交互 |
| `BudgetRpc` | commerce | `BudgetExecutionFacade` | 预算额度查询与扣减（`payCoin`, `balance`, `listUcidsByTaskId`） |
| `ShopPayRpc` | commerce | 封装 `BudgetRpc` | 门店渠道发放 |
| `BrandPayRpc` | commerce | 封装 `BudgetRpc` | 品牌渠道发放 |
| `ContractProxy` | puzu | `PuzuContractFacade` | 合同信息查询 |
| `MerchantProxy` | — | 商户内核 | 门店科目信息查询 |
| `MerchantDistributorProxy` | — | 商户内核 | 经销商查询 |
| `BpmConfiguration` | jichu | BPM AWS | 工作流集成 |

### HTTP 服务

| 代理类 | 目标服务 | 用途 |
|--------|----------|------|
| `OAuthServiceProxy` | EHR/UC 网关 | 公司信息、职位、用户角色、权益账户初始化 |
| `UcSnapshotServiceProxy` | UC 快照 | 组织/用户快照查询（带重试） |
| `ThirdBizService` | 多服务 | 封装 OAuthServiceProxy |
| `CreditProxy` | 信贷 | 签约结果查询 |
| `MdmProxy` | MDM | 公司主数据查询 |
| `IMCenterProxy` | IM | 消息/图片发送 |
| `JmsProxy` | 门店 | 门店信息查询 |
| `QuarkUnicornServiceProxy` | 新房 | 项目数据 |
| `TaurusNhserviceServiceProxy` | 新房 | 交易详情 |
| `HiveApiProxy` | Hive | 城市列表 |
| `SpCalcProxy` | 佣金计算 | 佣金计算服务 |
| `PosterCreator` | 海报 | HTML→JPG 海报生成 |

### Feign 客户端

| 类 | 目标服务 | 用途 |
|----|----------|------|
| `BrandMasterSnapshotClient` | PT Sync | 品牌主数据快照 |
| `NewPermissionClient` | 权限服务 | 权限查询 |

---

## 接口变更规则

### 兼容性原则

**1. 新增参数必须有默认值**（或使用重载方法）
**2. 删除参数必须升级接口版本号**（如 `@DubboService(version = "2.0")`）
**3. 破坏性变更需消费者确认升级计划**:
- 修改返回值类型
- 修改方法签名
- 删除接口方法
- 修改接口语义

### 变更流程
1. 在 `shop-points-api` 中定义变更
2. 通知所有消费方团队（已知消费方: shop-points-lottery）
3. 确认升级时间窗口
4. 灰度发布，逐步升级消费者
5. 确认所有消费者升级完成后清理旧版本

---
name: rpc-contracts-shop-points-lottery
description: "shop-points-lottery 消费的 Dubbo RPC 接口"
version: "0.2.0"
category: knowledge
tags:
  - shop-points-lottery
  - dubbo
  - rpc
  - interface
commands: []
---

# shop-points-lottery RPC 契约

## 消费的 shop-points Dubbo 接口

**代理类**: `ShopPointsRpc`（`service/rpc/`）
**注册中心**: nacos | **重试**: retries=0 | **超时**: 1000ms（EquityPointsFacade 3000ms）

| Facade 接口 | 版本 | 调用方法 |
|-------------|------|----------|
| `EquityPointsFacade` | — | `issueBKCoin(IssueBKCoinRequest)`, `reissueBKCoin(IssueBKCoinRequest)`, `queryEquityPointsBalance(QueryEquityPointsBalanceReq)` |
| `StarRightsFacade` | — | shop-points 星级权益 |
| `SubjectFacade` | — | `findSubject(project, subjectId)` |
| `RunningShopFacade` | — | `findRunningShop(shopCode)` |
| `ShopPermissionFacade` | — | 权限校验 |
| `ManagerPermissionFacade` | — | 管理员权限 |
| `PerformanceCityFacade` | — | 城市转换/查询 |

---

## 消费的 commerce Dubbo 接口

### ShopOrderProxy（商城订单）

**注册中心**: shop | **接口**: `com.ke.commerce.shop.api.v2.order`

| 方法 | 说明 |
|------|------|
| `findShopOrder` | 查询订单 |
| `createAndPay` | 创建并支付 |
| `getOrderStatus` | 获取订单状态 |
| `getOrderInfo` | 获取订单详情 |
| `updateOrder` | 更新订单 |
| `refund` | 退款 |
| `delivery` | 发货 |
| `receive` | 确认收货 |
| `deliveryAndReceive` | 发货并确认收货 |
| `getSkuInventory` | 查询 SKU 库存 |

### ShopProductProxy（商城商品）

**注册中心**: shop | **接口**: `com.ke.commerce.shop.api.v2.product`

| 方法 | 说明 |
|------|------|
| `createProduct` | 创建商品 |
| `updateProduct` | 更新商品 |
| `createSku` | 创建 SKU |
| `updateSku` | 更新 SKU |
| `getSku` | 获取 SKU |
| `searchProduct` | 搜索商品 |
| `syncAdjustInventory` | 同步调整库存 |
| `getSkuInventory` | 查询 SKU 库存 |

---

## 消费的 EHR Dubbo 接口

**代理类**: `UcRpc` | **注册中心**: jichu

| Facade | 方法 | 用途 |
|--------|------|------|
| `EhrUserFacade` | `getEhrUserByUserId(Long)` | 查询用户信息 |
| `EhrUserFacade` | `getEhrUserOfChildOrgPage(...)` | 分页查询子组织用户 |
| `EhrOrgFacade` | `getEhrOrgsByOrgCodes(String[])` | 批量查询组织信息 |

---

## 消费的奖励 Dubbo 接口

**代理类**: `AssignRewardRpc` | **注册中心**: reward

| Facade | 方法 | 用途 |
|--------|------|------|
| `AssignRewardFacade` | `deliverRewardByFile(DeliverByFileReq)` | 通过 Excel 批量发放贝壳币奖励 |

配置来自 `RedStarPayCfg`（accountCode, accountName, createId, activityId, projectId）

---

## HTTP 外部服务调用

### BjtServiceProxy（贝经堂供应商）

**模板**: `oAuthRestTemplate` → OAuth 网关

| 方法 | 路径 | 说明 |
|------|------|------|
| `selectShoppingProductInfo` | GET `/mooc/server/v1/select/shopping/product/info` | 查询商品 |
| `refundProduct` | POST `/mooc/server/v1/shopping/product/refund` | 退款 |
| `exchangeProduct` | POST `/mooc/server/v1/shopping/product/exchange` | 兑换 |

### HQServiceProxy（花桥供应商）

**模板**: `oAuthRestTemplate` → OAuth 网关

| 方法 | 路径 | 说明 |
|------|------|------|
| `exchangeDiscount` | POST `/huaqiao/server/v1/discount/pointsMall/exchange` | 兑换折扣 |
| `refundDiscount` | POST `/huaqiao/server/v1/discount/pointsMall/refund` | 退款折扣 |

### OAuthServiceProxy（UC/EHR 网关）

**模板**: `oAuthRestTemplate`

| 方法 | 说明 |
|------|------|
| `getCompanyInfoWithStoreInfoByUcid(Long)` | 查询门店信息（带 `@Cacheable("rd:shops")`） |
| `positionInfo(Long)` | 职位信息 |
| `getAllNames(Long)` | 组织全名 |
| `getOrgFullName(List<String>)` | 批量组织名（分片 max 50） |

### KeCoinRpc（贝壳币）

**依赖**: `com.ke.commerce:coin-sdk`

| 方法 | 说明 |
|------|------|
| `queryBalance(shopCode, SubAcctType)` | 查询贝壳币余额 |
| `queryAccountCode(shopCode, SubAcctType)` | 查询账户编码 |

---

## 调用关系总览

```
shop-points-lottery-service
  ├── rpc/ShopPointsRpc ──── Dubbo(nacos) ──── shop-points-api (7 Facades)
  ├── rpc/ShopOrderProxyImpl ──── Dubbo(shop) ──── commerce-shop Order API
  ├── rpc/ShopProductProxyImpl ──── Dubbo(shop) ──── commerce-shop Product API
  ├── rpc/UcRpc ──── Dubbo(jichu) ──── EHR User/Org Facades
  ├── rpc/AssignRewardRpc ──── Dubbo(reward) ──── Reward Facade
  ├── rpc/coin/ ──── coin-sdk ──── 贝壳币服务
  ├── BjtServiceProxy ──── HTTP ──── BJT OAuth API
  ├── HQServiceProxy ──── HTTP ──── 花桥 OAuth API
  └── OAuthServiceProxy ──── HTTP ──── UC/EHR 网关
```

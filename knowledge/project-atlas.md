---
name: project-atlas
description: "需要了解 shop-points 和 shop-points-lottery 的整体架构时加载"
version: "0.2.0"
category: harness
tags:
  - wiki
  - system
  - overview
  - architecture
commands: []
---

# 项目全景

## shop-points 定位

门店积分/权益管理核心服务。

**GAV**: `com.ke.shop.points:shop-points:1.0.20-RELEASE`
**技术栈**: Java 8, Spring Boot + Spring Cloud (Greenwich.SR3), Maven 8 模块, Dubbo 2.7.3.9-RELEASE, Kafka, Apollo, ShardingSphere
**Parent**: `infrastructure-starter-parent:2.1.26`

**数据库**: `shop_points`（积分库）+ `shop_equity`（权益库），双库主从，5 张分片表（3 张按 subject_id 100 分片 + 2 张按 ctime 按年分片）

**规模**: 107 Mapper, 462 Model 文件, 65 Controller, 44 定时任务, 11 Kafka Consumer, 11 Dubbo Facade, 26 RPC 代理

核心职责:
- 门店积分账户管理（发放、消耗、退还、查询）
- 权益积分策略计算与结算
- 佣金计算与分发（含精英佣金）
- 品牌场景积分与钻石等级
- 门店星级评定（FJH + 自营）
- 积分发放批次管理（Disbursement）
- 活动奖励预估与执行
- 数据归档与对账

---

## shop-points-lottery 定位

抽奖/活动 + 积分商城/电商。双业务领域。

**GAV**: `com.ke.shop.points.lottery:shop-points-lottery:1.0.0-SNAPSHOT`
**技术栈**: Java 8, Spring Boot + Spring Cloud (Greenwich.SR3), Maven 5 模块
**Parent**: `infrastructure-starter-parent:2.1.29`
**shop-points-api 依赖**: `1.0.20-RELEASE`

**数据库**: `shop_lottery`（活动库）+ `shop_mall`（商城库），双库主从，无分片

**规模**: 18 Mapper, 67 DTO, 14 Controller, 3 Kafka Listener, 3 个策略模式实现

核心职责:
- 活动管理（抽奖、任务、黑白名单）
- 奖品发放（PrizeDispenser 策略模式: 贝壳币/兑换码/虚拟奖品）
- 积分商城（商品、订单、物流、退款）
- 供应商管理（SupplierHandlerFactory: BJT/HQ/SP/Default）
- 订单事件处理（支付成功/失败/退款）
- 账户与权限

---

## shop-points 模块概览

| 模块 | 定位 | 规模 |
|------|------|------|
| `shop-points-api` | Dubbo 接口契约 + 45 DTO | 11 Facade 接口 |
| `shop-points-model` | 领域模型 | 462 文件（241 DTO, 130 枚举, 55 PO） |
| `shop-points-commons` | 工具类库 | Snowflake, ExcelUtils, S3Upload 等 |
| `shop-points-dao` | MyBatis 数据访问 | 107 Mapper + 103 自动 XML + 51 手写 XML |
| `shop-points-service` | 核心业务逻辑 | 33 子包, 11 Consumer, 1 Producer |
| `shop-points-rpc` | 外部服务代理 | 26 代理类（Dubbo + HTTP + Feign） |
| `shop-points-start` | Spring Boot 入口 | 65 Controller (api 5 + web 17 + manage 41 + open 1 + widget 1) |
| `shop-points-schedule` | 定时任务 | 44 任务类（lianjia-schedule 框架） |

---

## shop-points-lottery 模块概览

| 模块 | 定位 | 规模 |
|------|------|------|
| `shop-points-lottery-api` | DTO + 常量 | 67 DTO, 4 枚举 |
| `shop-points-lottery-common` | 工具/枚举/响应包装 | 24 工具类, 16 枚举, RedisLock |
| `shop-points-lottery-dao` | MyBatis 数据访问 | 18 Mapper + 19 自动 XML + 5 手写 XML |
| `shop-points-lottery-service` | 核心业务逻辑 | 9 Service + 7 BizService, 策略/工厂模式 |
| `shop-points-lottery-start` | Spring Boot 入口 | 14 Controller, 3 Listener, 3 Filter |

---

## shop-points 入口点

### HTTP Controller
路径: `shop-points-start/controller/`

| 子包 | 数量 | 用途 |
|------|------|------|
| `api/` | 5 | 对外 API（basic, coef, datasource, equity, fjh） |
| `web/` | 17 | H5 页面（星级, 品牌, 权益, FJH, 报表, 计算器） |
| `manage/` | 41 | 后台管理（rule 20 + act 6 + upload 6 + fjh 4 + 其他 5） |
| `open/` | 1 | 开放 API（AppCard） |
| `widget/` | 1 | 嵌入式组件 |

### Kafka Consumer
路径: `shop-points-service/mq/consumer/` — 11 个 Consumer

### Dubbo Provider
路径: `shop-points-api/` — 11 个 Facade 接口对外暴露

### Scheduled Task
路径: `shop-points-schedule/` — 44 个定时任务（lianjia-schedule 框架，非 Spring @Scheduled）

---

## shop-points-lottery 入口点

### HTTP Controller
路径: `shop-points-lottery-start/controller/`

| 子包 | 数量 | 用途 |
|------|------|------|
| `controller/` (根) | 8 | 活动/兑换码/H5/后台管理 |
| `controller/mall/` | 4 | 积分商城（订单/商品/Web/库存） |
| `controller/manage/` | 3 | 后台管理（商品/上传/限购配置） |

### Kafka Listener
路径: `shop-points-lottery-start/listener/` + `service/mq/` — 3 个 Listener

### Dubbo Consumer
通过 `ShopPointsRpc` 消费 `shop-points-api` 的 7 个 Facade 接口。

---

## 质量状态

- **shop-points**: 测试稀疏，仅 7 个测试文件。父 POM `skipTests=true`。
- **shop-points-lottery**: 测试几乎为零。
- **当前质量保障**: 依赖编译检查（`mvn compile`）+ 手动测试。
- **改进方向**: 补充核心 Service 单元测试，覆盖积分计算、幂等逻辑、分片路由等关键路径。

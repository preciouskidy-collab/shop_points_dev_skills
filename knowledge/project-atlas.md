---
name: project-atlas
description: "需要了解 shop-points 和 shop-points-lottery 的整体架构时加载"
version: "0.1.0"
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

**技术栈**: Java 8, Spring Boot + Spring Cloud (Greenwich.SR3), Maven 8 模块, Dubbo 2.7.3, Kafka, Apollo, ShardingSphere。

**数据库**: 主数据库 `shop_points` + `shop_equity`（双库主从），100 张分片表。

核心职责：
- 门店积分账户管理（发放、消耗、退还、查询）
- 权益积分策略与结算
- 佣金计算与分发
- 品牌场景积分
- 门店星级评定（FJH）
- 积分发放批次管理
- 数据归档

---

## shop-points-lottery 定位

抽奖/活动 + 积分商城/电商。双业务领域。

**技术栈**: Java 8, Spring Boot, Maven 5 模块。

**数据库**: `shop_lottery` + `shop_mall`。

核心职责：
- 活动管理（抽奖、任务、黑白名单）
- 奖品发放（策略模式 PrizeDispenser）
- 积分商城（商品、订单、物流、退款）
- 供应商管理（工厂模式 SupplierHandlerFactory）
- 账户与权限

---

## shop-points 入口点

### HTTP Controller
路径：`shop-points-start/controller/`

| 子包 | 用途 |
|------|------|
| `api/` | 对外 API 接口 |
| `web/` | H5 页面接口 |
| `manage/` | 后台管理接口（30+ 控制器） |
| `widget/` | 组件接口 |
| `open/` | 开放 API |

### Kafka Consumer
路径：`shop-points-service/` 下 11 个 Consumer，涵盖积分变更、佣金事件、广播消息、数据同步等。

### Dubbo Provider
路径：`shop-points-api/` 对外暴露接口（EquityPointsFacade, StarRightsFacade, SubjectFacade 等）。

### Scheduled Task
路径：`shop-points-schedule/`，定时任务包括佣金结算、品牌场景、FJH 星级评定、数据归档。

---

## shop-points-lottery 入口点

### HTTP Controller
路径：`shop-points-lottery-start/controller/`

| 子包 | 用途 |
|------|------|
| `manage/` | 后台管理接口 |
| `mall/` | 积分商城接口 |

### Kafka Listener
路径：`shop-points-lottery-start/listener/`，消费外部事件（订单回调、供应商事件）。

### Dubbo Consumer
调用 `shop-points-api` 的 Dubbo 接口进行积分操作（查询、消耗、退还）。

---

## 质量状态

- **shop-points**: 测试稀疏，仅 7 个测试文件。
- **shop-points-lottery**: 测试几乎为零。
- **父 POM**: `skipTests=true`。
- **当前质量保障**: 依赖编译检查 + 手动测试。
- **改进方向**: 补充核心 Service 单元测试，覆盖积分计算、幂等逻辑、分片路由等关键路径。

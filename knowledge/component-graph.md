---
name: component-graph
description: "需要了解 Maven 模块布局、包结构和依赖链时加载"
version: "0.1.0"
category: harness
tags:
  - wiki
  - module
  - maven
  - structure
commands: []
---

# 组件图谱

## shop-points（8 个模块）

### shop-points-api
**定位**: Dubbo RPC 接口 + DTO。被其他服务依赖。

**关键接口**:
- `EquityPointsFacade` — 积分消耗、退还、余额查询、贝壳币发放
- `StarRightsFacade` — 门店积分查询、星级数据同步
- `SubjectFacade` — 科目信息查询
- `RuleConfigFacade` — 规则配置
- `RunningShopFacade` — 运营门店
- `DictFacade` — 字典查询
- `BrandStatusManagerFacade` — 品牌状态管理

**修改注意**: 此模块是对外契约，变更需保证向后兼容。

---

### shop-points-model
**定位**: 共享领域模型。PO、BO、枚举、DTO。

**规模**: 462 个 Java 文件。

**包含**: 所有业务实体对应的模型类，被 api、dao、service 共同依赖。

---

### shop-points-commons
**定位**: 工具类库。

**核心工具**:
- `DateMath` — 日期计算
- `PeriodUtils` — 周期工具
- `ExcelUtils` — Excel 导入导出
- `Snowflake` — 雪花 ID 生成
- `BeanCopyUtils` — Bean 拷贝
- `S3Upload` — S3 文件上传

---

### shop-points-dao
**定位**: MyBatis 数据访问层。

**规模**: Mapper Interface 108 个 + XML 102 个。

**包含**:
- MyBatis Mapper Interface
- XML 映射文件
- 分片策略配置
- `domain` 实体类

---

### shop-points-service
**定位**: 核心业务逻辑。647 个 Java 文件。

**子包结构（30+ 子包）**:

| 子包 | 职责 |
|------|------|
| `equity` | 权益管理 |
| `points` | 积分核心逻辑 |
| `brand` | 品牌场景 |
| `pinzhi` | 品质相关 |
| `disbursement` | 发放逻辑 |
| `commission` | 佣金计算 |
| `settlement` | 结算 |
| `exchange` | 兑换 |
| `act` | 活动 |
| `biz/strategy` | 策略模式 |
| `biz/role` | 角色管理 |
| `fjh` | FJH 星级评定 |
| `broadcast` | 广播 |
| `split` | 拆分 |
| `hint` | 提示 |
| `download` | 下载 |

**消息层**:
- Kafka Consumer: 11 个（积分变更、佣金事件、广播、数据同步等）
- Kafka Producer: 1 个（KafkaMessageProducer）

---

### shop-points-rpc
**定位**: 外部服务代理。

**代理服务**:
- `UcRpc` — 用户中心
- `EquityRpc` — 权益服务
- `BudgetRpc` — 预算服务
- `ContractProxy` — 合同服务
- `HousedelFacadeRpc` — MLS 房源数据
- `CreditProxy` — 信贷服务
- `MdmProxy` — 主数据管理
- `IMProxy` — IM 消息
- `MerchantProxy` — 商户服务

---

### shop-points-start
**定位**: Spring Boot 入口。

**Controller 分层**:

| 子包 | 用途 | 说明 |
|------|------|------|
| `api/` | 对外 API | 供外部系统调用 |
| `web/` | H5 页面 | 前端页面接口 |
| `manage/` | 后台管理 | 30+ 控制器，运营后台 |
| `widget/` | 组件 | 嵌入式组件接口 |
| `open/` | 开放 API | 第三方接入 |

---

### shop-points-schedule
**定位**: 定时任务。

**任务列表**:
- 佣金定时结算
- 品牌场景定时任务
- FJH 星级评定定时任务
- 数据归档定时任务

---

## shop-points-lottery（5 个模块）

### shop-points-lottery-api
**定位**: DTO + Feign 接口定义。

独立模块，无内部依赖。

---

### shop-points-lottery-common
**定位**: 共享工具、响应包装器、枚举。

独立模块，无内部依赖。

---

### shop-points-lottery-dao
**定位**: 数据访问层。

**包含**: `domain/` 实体类 + MyBatis Mapper Interface + XML。

依赖 `shop-points-lottery-api`。

---

### shop-points-lottery-service
**定位**: 核心业务逻辑。

**子包结构**:

| 子包 | 职责 |
|------|------|
| `activity` | 活动管理 |
| `lottery` | 抽奖核心 |
| `chance` | 用户机会 |
| `prize` | 奖品管理 |
| `task` | 任务系统 |
| `blackwhitelist` | 黑白名单 |
| `exchange` | 兑换 |
| `shop/order` | 订单 |
| `shop/product` | 商品 |
| `shop/delivery` | 物流 |
| `shop/refund` | 退款 |
| `shop/supplier` | 供应商 |
| `shop/account` | 账户 |
| `shop/permission` | 权限 |
| `rpc` | 远程服务调用 |
| `mq` | 消息队列 |

**设计模式**:
- 策略模式: `PrizeDispenser`（奖品发放）
- 工厂模式: `SupplierHandlerFactory`（供应商处理）

依赖 `shop-points-lottery-dao`, `shop-points-lottery-api` + Dubbo 引用 `shop-points-api`。

---

### shop-points-lottery-start
**定位**: Spring Boot 入口。

**包含**:
- Controller (`manage/` + `mall/`)
- Listener (Kafka 消费者)
- 配置类
- 过滤器
- 异常处理器

依赖 `shop-points-lottery-service`。

---

## 依赖图

```
shop-points:
  api ← model ← commons
  dao ← model, commons
  rpc ← api
  service ← dao, api, rpc
  start ← service
  schedule ← service

shop-points-lottery:
  api (standalone)
  common (standalone)
  dao ← api
  service ← dao, api (+ Dubbo ref to shop-points-api)
  start ← service
```

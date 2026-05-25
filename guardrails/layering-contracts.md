---
name: layering-contracts
description: "当修改 Java 代码结构、添加新类或修改 Maven 模块依赖时必须加载的架构分层约束"
version: "0.1.0"
category: harness
tags:
  - rule
  - architecture
  - layering
  - maven
  - java
commands: []
---

# Guardrail: 分层契约

## 适用范围

适用于 `shop-points` 和 `shop-points-lottery` 两个项目的所有 Java 代码结构变更。

## Maven 模块依赖链

### shop-points

```text
shop-points-api        ← model, commons（独立发布，供其他服务依赖）
shop-points-model      ← commons
shop-points-commons    ← （无内部依赖）
shop-points-dao        ← model, commons
shop-points-service    ← dao, api, rpc
shop-points-rpc        ← api（外部服务代理）
shop-points-start      ← service（Controller、应用入口）
shop-points-schedule   ← service（定时任务）
```

依赖方向：`start/schedule → service → dao/rpc → model/commons`，**禁止反向依赖**。

### shop-points-lottery

```text
shop-points-lottery-api      ← （独立 DTO）
shop-points-lottery-common   ← （共享工具）
shop-points-lottery-dao      ← api
shop-points-lottery-service  ← dao, api（+ Dubbo ref to shop-points-api）
shop-points-lottery-start    ← service（Controller、应用入口）
```

## 分层约束

| 层 | 位置 | 允许调用 | 禁止 |
|---|---|---|---|
| **Controller** | `start` 模块 `controller/` | Service | 直接访问 DAO/Mapper、RPC/Proxy、Kafka Producer |
| **Service** | `service` 模块 | DAO、RPC、Kafka Producer、其他 Service | 反向被 RPC 依赖 |
| **DAO/Mapper** | `dao` 模块 | 只含数据访问 | 包含业务逻辑 |
| **RPC/Proxy** | `rpc` 模块 | 只封装外部调用 | 反向 import service |
| **Kafka Consumer** | `service` 模块 | 等同入口层，只调 Service | 直接访问 DAO/Proxy |
| **Scheduled Task** | `schedule` 模块 | Service | 直接访问 DAO |

**强约束**：

- `Controller` 只做参数解析、调用 Service、响应包装。
- `Service` 承载业务编排，可以调用 DAO/RPC/Kafka Producer。
- `Mapper Interface` + `Mapper XML` 必须成对存在且 namespace 一致。
- `RPC Proxy` 只封装外部服务调用，不 import `service/`。

## 跨服务边界

- `shop-points-lottery` 通过 **Dubbo RPC** 调用 `shop-points-api` 的接口。
- `shop-points` 通过 **Kafka Events** 向 `shop-points-lottery` 发送事件。
- **禁止跨服务共享数据库**。每个服务只访问自己的数据库。
- Dubbo 接口变更需要版本化，新增参数必须提供默认值保证向后兼容。

## 机械化检查

```bash
# 检查模块依赖方向
cd /path/to/shop-points && mvn dependency:tree -pl shop-points-service | grep "shop-points-start"
# 应该没有输出（start 不应出现在 service 的依赖树中）

# 检查 Mapper interface 与 XML 匹配
grep -r "namespace" src/main/resources/manualMappers/ | awk -F'"' '{print $2}'
# 逐一确认对应 mapper interface 存在
```

新增分层规则时，优先补到检查脚本中，不要只写自然语言约定。

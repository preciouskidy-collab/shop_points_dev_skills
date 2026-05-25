---
name: rpc-contracts-shop-points-lottery
description: "shop-points-lottery 消费的 Dubbo RPC 接口"
version: "0.1.0"
category: knowledge
tags:
  - shop-points-lottery
  - dubbo
  - rpc
  - interface
commands: []
---

# shop-points-lottery RPC 契约

## 消费的 Dubbo 接口

路径：`shop-points-lottery-service/rpc/`

**子包结构**:
- `coin` — 贝壳币相关 RPC 调用
- `config` — 配置相关 RPC 调用
- `service` — 服务相关 RPC 调用

**调用关系**: Lottery 通过 Dubbo 消费 `shop-points-api` 的接口进行积分操作（查询、消耗、退还）。

```
shop-points-lottery-service
  → rpc/coin, rpc/config, rpc/service
    → Dubbo Reference → shop-points-api (EquityPointsFacade, StarRightsFacade, ...)
```

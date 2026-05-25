---
name: data-layer-shop-points-lottery
description: "shop-points-lottery 的数据库结构和数据源切换"
version: "0.1.0"
category: knowledge
tags:
  - shop-points-lottery
  - database
  - mybatis
commands: []
---

# shop-points-lottery 数据层

## 双数据库

### shop_lottery（活动库）
- 活动表
- 奖品表
- 用户奖品表
- 用户机会表
- 任务表

### shop_mall（商城库）
- 商品表
- 订单表
- 物流表
- 退款表
- 账户表
- 账户流水表

**数据源切换**: 使用 `@DS(dataSource = "...")` 注解。

```java
@DS(dataSource = "shop_lottery")
public List<Activity> queryActivities(...) { ... }

@DS(dataSource = "shop_mall")
public List<Product> queryProducts(...) { ... }
```

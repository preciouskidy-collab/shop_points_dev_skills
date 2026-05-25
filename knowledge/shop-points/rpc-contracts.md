---
name: rpc-contracts-shop-points
description: "shop-points 提供和消费的 Dubbo RPC 接口"
version: "0.1.0"
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

路径：`shop-points-api/`

| 接口 | 职责 | 关键方法 |
|------|------|----------|
| `EquityPointsFacade` | 积分操作 | 消耗积分、退还积分、查询余额、发放贝壳币 |
| `StarRightsFacade` | 星级权益 | 查询门店积分、同步星级数据 |
| `SubjectFacade` | 科目信息 | 科目信息查询 |
| `RuleConfigFacade` | 规则配置 | 规则配置读取 |
| `RunningShopFacade` | 运营门店 | 运营门店数据查询 |
| `DictFacade` | 字典 | 字典数据查询 |
| `BrandStatusManagerFacade` | 品牌状态 | 品牌状态管理 |

**Dubbo 版本**: 2.7.3

**调用方式**: Spring Cloud (Greenwich.SR3) + Dubbo 混合，服务注册通过 Apollo 配置中心管理。

---

## 消费的外部 Dubbo 服务（shop-points-rpc）

路径：`shop-points-rpc/`

| 代理类 | 外部服务 | 用途 |
|--------|----------|------|
| `UcRpc` | 用户中心 | 用户信息查询 |
| `EquityRpc` | 权益服务 | 权益数据交互 |
| `BudgetRpc` | 预算服务 | 预算额度查询与扣减 |
| `ContractProxy` | 合同服务 | 合同信息查询 |
| `HousedelFacadeRpc` | MLS 房源 | 房源数据查询 |
| `CreditProxy` | 信贷服务 | 信贷数据查询 |
| `MdmProxy` | 主数据管理 | 主数据（组织、人员）查询 |
| `IMProxy` | IM 消息 | 消息推送 |
| `MerchantProxy` | 商户服务 | 商户信息查询 |

**调用模式**: 同步 RPC 调用，需注意超时和降级。

---

## 接口变更规则

### 兼容性原则

**1. 新增参数必须有默认值**
```java
// 正确：新参数提供默认值，老消费者不受影响
Result queryBalance(Long subjectId, String accountType /* 新增 */);

// 更好：使用重载方法
Result queryBalance(Long subjectId);
Result queryBalance(Long subjectId, String accountType);
```

**2. 删除参数必须升级接口版本号**
```java
@DubboService(version = "2.0")
public class EquityPointsFacadeV2Impl implements EquityPointsFacadeV2 {
    Result queryBalance(Long subjectId);
}
```

**3. 破坏性变更需要消费者确认升级计划**
- 修改返回值类型
- 修改方法签名
- 删除接口方法
- 修改接口语义

### 变更流程
1. 在 `shop-points-api` 中定义变更
2. 通知所有消费方团队
3. 确认升级时间窗口
4. 灰度发布，逐步升级消费者
5. 确认所有消费者升级完成后清理旧版本

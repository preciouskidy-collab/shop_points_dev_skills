---
name: build-standards
description: "在任何代码变更提交之前必须加载，定义本地验证命令和通过标准"
version: "0.2.0"
category: guardrails
tags:
  - rule
  - testing
  - quality-gates
  - maven
commands: []
---

# Guardrail: 构建标准

## 每次变更必跑

```bash
# shop-points
cd <shop-points-path> && mvn compile -DskipTests

# shop-points-lottery
cd <shop-points-lottery-path> && mvn compile -DskipTests
```

**`mvn compile` 必须通过，无例外。**

## 按变更类型的验证命令

### Java 代码变更

```bash
mvn compile -pl <changed-module>
mvn test -pl <changed-module> -DskipTests=false -Dtest=<TestClass>
```

### Mapper 变更

```bash
# 验证 XML namespace 与 mapper interface 匹配
grep "namespace" <changed-module>/src/main/resources/manualMappers/<ChangedMapper>.xml
# 确认 namespace 值与 Java interface 全限定名一致

# 验证 resultType/resultMap 指向存在的类
grep -E "resultType|resultMap" <changed-module>/src/main/resources/manualMappers/<ChangedMapper>.xml
```

### Dubbo 接口变更（shop-points-api）

```bash
# api 变更后，确认消费者端仍能编译
cd <shop-points-lottery-path> && mvn compile -DskipTests
```

## 通过条件

- `mvn compile` 必须通过（无编译错误）
- MyBatis Mapper XML 的 `namespace` 必须与对应 Mapper Interface 全限定名匹配
- MyBatis Mapper XML 的 `resultType`/`resultMap` 必须指向存在的类
- 新增 Controller 端点至少有一条通过 curl 或测试验证的路径
- 涉及 Dubbo 接口变更时，消费者端仍能编译

## 实际约束

- 父 POM 设置 `<skipTests>true</skipTests>`，**仅对触碰模块显式启用测试**
- 测试命令: `mvn test -pl <changed-module> -DskipTests=false -Dtest=<TestClass>`
- 编译验证无需连接外部服务（DB/Redis/Kafka/Apollo），Apollo 在本地使用默认值

## 回退条件

- 编译失败：先修入口和依赖，不要跳过编译直接改代码
- Mapper XML 验证失败：先检查 namespace 和 resultType，再调整 SQL
- 测试无法运行：在交付说明里明确记录阻塞原因和未覆盖风险
- Dubbo 接口不兼容：先确认消费者版本，再决定是升级版本号还是保持兼容

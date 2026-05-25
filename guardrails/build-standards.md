---
name: build-standards
description: "在任何代码变更提交之前必须加载，定义本地验证命令和通过标准"
version: "0.1.0"
category: harness
tags:
  - rule
  - testing
  - quality-gates
  - maven
commands: []
---

# Guardrail: 构建标准

## 本地最小门禁

按风险从低到高选择：

```bash
# shop-points
cd /path/to/shop-points && mvn compile -DskipTests
mvn test -pl shop-points-service -DskipTests=false -Dtest=<YourTestClass>

# shop-points-lottery
cd /path/to/shop-points-lottery && mvn compile -DskipTests
mvn test -pl shop-points-lottery-service -DskipTests=false -Dtest=<YourTestClass>
```

## 通过条件

- `mvn compile` 必须通过（无编译错误）。
- MyBatis Mapper XML 的 `namespace` 必须与对应 Mapper Interface 的全限定名匹配。
- MyBatis Mapper XML 的 `resultType`/`resultMap` 必须指向存在的类。
- 新增 Controller 端点至少有一条通过 curl 或测试验证的路径。
- 涉及 Dubbo 接口变更时，消费者端仍能编译。

## 实际约束

- 当前项目父 POM 设置了 `<skipTests>true</skipTests>`，**仅对触碰模块显式启用测试**。
- 测试命令格式：`mvn test -pl <changed-module> -DskipTests=false -Dtest=<TestClass>`。
- 不要试图一次性修复所有存量测试债务。

## 回退条件

- 编译失败：先修入口和依赖，不要跳过编译直接改代码。
- Mapper XML 验证失败：先检查 namespace 和 resultType，再调整 SQL。
- 测试无法运行：在交付说明里明确记录阻塞原因和未覆盖风险。
- Dubbo 接口不兼容：先确认消费者版本，再决定是升级版本号还是保持兼容。

## MyBatis Mapper 专项检查

```bash
# 检查 XML namespace 与 mapper interface 匹配
# 1. 提取所有 XML namespace
grep -r "namespace" */src/main/resources/manualMappers/ | awk -F'"' '{print $2}'
# 2. 逐一确认对应 Java interface 存在
find . -path "*/mapper/*.java" -name "*Mapper.java" | xargs grep -l "interface"
```

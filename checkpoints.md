# 本地质量门禁

## Always（每次变更必跑）

```bash
# shop-points
cd /path/to/shop-points && mvn compile -DskipTests

# shop-points-lottery
cd /path/to/shop-points-lottery && mvn compile -DskipTests
```

## Java 代码变更

```bash
mvn compile -pl <changed-module>
mvn test -pl <changed-module> -DskipTests=false -Dtest=<TestClass>
```

## Mapper 变更

```bash
# 验证 XML namespace 与 mapper interface 匹配
grep "namespace" */src/main/resources/manualMappers/<ChangedMapper>.xml
# 确认 namespace 值与 Java interface 全限定名一致
```

## Dubbo 接口变更

```bash
# shop-points-api 变更后，确认消费者端仍能编译
cd /path/to/shop-points-lottery && mvn compile -DskipTests
```

## Notes

- 项目当前默认 `<skipTests>true</skipTests>`，需对触碰模块显式启用测试。
- 编译验证无需连接外部服务（DB/Redis/Kafka/Apollo），Apollo 在本地使用默认值。
- MyBatis Mapper XML 验证目前为手动检查，后续可考虑脚本化。

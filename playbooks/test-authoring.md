---
name: test-authoring
description: "编写或补充 Java 单元测试时触发，定义 JUnit5 + Mockito 测试模式和原则"
version: "0.1.0"
category: harness
tags:
  - skill
  - testing
  - junit
  - mockito
  - unit-test
commands: []
---

# Skill: 测试编写

## 原则

- **改哪里测哪里**：不为不相关的代码加测试。
- **优先 mock 下游**：不依赖真实 DB/Redis/Kafka/Apollo/Dubbo。
- **测业务边界**：不只测 happy path，还要测异常、空值、边界。
- **对历史 bug 增加回归测试**。

## JUnit5 + Mockito 模式

### Service 测试
```java
@ExtendWith(MockitoExtension.class)
class XxxServiceTest {
    @Mock
    private XxxMapper xxxMapper;
    @Mock
    private YyyRpc yyyRpc;
    @InjectMocks
    private XxxServiceImpl xxxService;

    @Test
    void create_success() {
        // given
        when(xxxMapper.insert(any())).thenReturn(1);
        // when
        CreateResult result = xxxService.create(req);
        // then
        assertNotNull(result.getId());
    }

    @Test
    void create_insufficientBalance_throws() {
        // given
        when(xxxMapper.selectById(any())).thenReturn(zeroBalanceAccount);
        // when & then
        assertThrows(BizException.class, () -> xxxService.create(req));
    }
}
```

### 建议模式

| 被测对象 | 推荐方式 |
|----------|----------|
| Service 逻辑 | @ExtendWith(MockitoExtension.class), @Mock DAO/RPC |
| Controller | MockMvc + @WebMvcTest（仅用于接口契约测试） |
| Mapper XML | 仅在必要时使用 @MybatisTest（需要真实数据库） |
| Kafka Consumer | mock Consumer 调用的 Service 方法 |
| 分片策略 | 用特定 subject_id 值验证分片计算结果 |
| 工具方法 | 纯函数测试，覆盖边界值 |

## 实际约束

- 当前项目父 POM 设置 `<skipTests>true</skipTests>`。
- **仅对触碰模块ada显式启用**：`mvn test -pl <module> -DskipTests=false -Dtest=<TestClass>`。
- 不要试图一次性修复所有存量测试债务。

## Web 接口本地测试

需要本地启动应用并调用真实接口验证时：

1. **Install 改动模块**：`mvn install -pl <service-module> -am -DskipTests`
2. **启动应用**：`mvn spring-boot:run -pl <start-module> -Dspring-boot.run.profiles=test`
3. **发送请求**：用 `curl` 调接口，域名用 `local.ttb.test.ke.com`（非 localhost，CAS 认证需要）
4. **Cookie + 参数**：交互式向 RD 获取

> `spring-boot:run` 不直接用 sibling 模块的 `target/classes`，而是从 `~/.m2` 加载 jar。跳过 install 直接 run 会使用旧代码。

## 产出
- `src/test/java/**/*Test.java`
- `tests/backend_test_report.md` 中记录执行命令和结果（Pipeline 阶段 `backend-test-local`）。

## 质量标准
- 测试不能调用生产/预发环境网络。
- 测试名称描述行为，而不是实现细节（如 `create_insufficientBalance_throws` 而非 `test1`）。

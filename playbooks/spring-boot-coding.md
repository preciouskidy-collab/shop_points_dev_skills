---
name: spring-boot-coding
description: "编写或修改 Java/Spring Boot 业务代码时触发，定义编码流程和 Java 特定模式"
version: "0.1.0"
category: harness
tags:
  - skill
  - coding
  - java
  - spring-boot
  - mybatis
commands: []
---

# Skill: Spring Boot 编码

## 适用范围

Java/Spring Boot 业务实现，覆盖 shop-points 和 shop-points-lottery 两个项目。

## 编码流程

1. **先读后改**：先读入口和被调用方，理解现有逻辑，再改代码。
2. **小步修改**：保持分层边界，每次只改一个关注点。
3. **优先复用**：复用现有 Domain、DTO、Service、工具方法。
4. **结构化处理**：下游返回优先使用结构化对象，避免散落魔法字段。
5. **Mapper 同步**：改 Mapper Interface 必须同步更新 Mapper XML（反之亦然）。
6. **修改后即验**：运行最小门禁 `mvn compile`。

## Java/Spring Boot 特定模式

### Controller 模式
```java
@RestController
@RequestMapping("/api/xxx")
@Slf4j
public class XxxController {
    @Autowired
    private XxxService xxxService;

    @PostMapping("/create")
    public Message<CreateResult> create(@RequestBody CreateRequest req) {
        return Message.success(xxxService.create(req));
    }
}
```
- Controller 只做参数接收和响应包装，不含业务逻辑。
- 统一返回 `Message<T>` 包装。

### Service 模式
```java
@Service
@Slf4j
public class XxxServiceImpl implements XxxService {
    @Autowired
    private XxxMapper xxxMapper;

    @Transactional(rollbackFor = Exception.class)
    @Override
    public CreateResult create(CreateRequest req) {
        // 业务逻辑
    }
}
```
- 接口 + 实现分离。
- `@Transactional` 只用于 Service 层写操作。
- 使用 `Assert.isTrue()` / `Assert.notNull()` 代替 if-throw。

### DAO/Mapper 模式
```java
// Mapper Interface
public interface XxxMapper extends Mapper<XxxDO> {
    List<XxxDO> queryByCondition(@Param("req") QueryReq req);
}
```
```xml
<!-- Mapper XML -->
<mapper namespace="com.ke.shop.points.dao.mapper.XxxMapper">
    <select id="queryByCondition" resultType="com.ke.shop.points.dao.domain.XxxDO">
        SELECT * FROM xxx WHERE is_deleted = 0
        <if test="req.name != null">AND name = #{req.name}</if>
    </select>
</mapper>
```
- Mapper Interface 和 XML 的 namespace 必须一致。
- 分库分表查询必须包含 subject_id 条件。

### 日志模式
- 使用 `@Slf4j` 注解。
- 占位符格式：`log.info("创建订单, orderId={}", orderId)`，不用字符串拼接。

### 异常处理
- 业务校验：`Assert.isTrue(condition, "错误信息")`。
- 不用 `e.printStackTrace()`，用 `log.error("描述", e)`。

## 产出
- 代码 diff。
- `coding/coding_report_v*.md`（复杂需求记录修改点和兼容性说明）。

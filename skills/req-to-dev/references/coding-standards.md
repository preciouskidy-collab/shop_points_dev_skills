# 后端编码规范要点

## 命名规范

- 类名：UpperCamelCase（如 OrderService）
- 方法名/变量名：lowerCamelCase（如 getOrderById）
- 常量：UPPER_SNAKE_CASE（如 MAX_RETRY_COUNT）
- 包名：全小写（如 shop.points.dev.skills）
- 数据库字段：snake_case（如 order_id）

## 注解规范

- 日志：@Slf4j（使用 LOGGER，不使用 log）
- 控制器：@RestController + @RequestMapping
- 服务：@Service
- 数据层：@Mapper
- 依赖注入：构造器注入（不使用 @Autowired）

## 代码结构

- Controller 只做参数校验和调用 Service，不包含业务逻辑
- Service 实现业务逻辑，复杂逻辑拆分为私有方法
- Mapper 只做数据访问，不包含业务判断
- DTO 和 Domain 严格分离，不混用

## 异常处理

- 使用统一异常处理器
- 业务异常抛出自定义 RuntimeException
- 不捕获 RuntimeException
- finally 块中不使用 return

## 数据库规范

- 每张表必须包含：id(BIGINT), created_at(DATETIME), updated_at(DATETIME), is_deleted(TINYINT)
- 逻辑删除：0-正常，1-删除
- 禁止使用存储过程
- SQL 不使用 SELECT *
- 字符集：utf8mb4

## 接口规范

- RESTful 风格
- 路径格式：/api/v1/{resource}
- 统一响应结构：{code: int, message: string, data: T}
- 成功：code = 0
- 分页：使用 PageRequest/PageResult
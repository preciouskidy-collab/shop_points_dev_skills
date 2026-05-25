# KeBoot 四模块项目结构规范

## 模块划分

```
{project-name}/
├── pom.xml                          # 父 POM
├── {project}-api/                   # API 模块
│   ├── pom.xml
│   └── src/main/java/.../api/
│       ├── dto/                     # 数据传输对象
│       └── service/                 # Feign 服务接口
├── {project}-dao/                   # DAO 模块
│   ├── pom.xml
│   └── src/main/java/.../dao/
│       ├── domain/                  # 数据库实体
│       └── mapper/                  # MyBatis Mapper
│       └── src/main/resources/
│           └── mappers/             # XML 映射文件
├── {project}-service/               # Service 模块
│   ├── pom.xml
│   └── src/main/java/.../service/   # 业务逻辑
└── {project}-start/                 # 启动模块
    ├── pom.xml
    └── src/main/java/.../
        ├── Application.java         # 启动入口
        ├── configuration/           # 配置类
        └── controller/              # REST Controller
    └── src/main/resources/
        ├── application.yml          # 应用配置
        └── bootstrap.yml            # 启动配置
```

## 模块依赖关系

```
start → service → dao, api
dao → (mybatis-plus provided)
api → (独立发布，无内部依赖)
```

## 关键规范

- **api 模块**是唯一对外发布的模块，其他模块 skip deploy
- **start 模块**是唯一可启动的模块，包含 Application.java
- **service 模块**依赖 api 和 dao，实现业务逻辑
- **dao 模块**依赖 mybatis-plus（provided scope）
- 父 POM 继承 `com.lianjia.infrastructure:infrastructure-starter-parent`
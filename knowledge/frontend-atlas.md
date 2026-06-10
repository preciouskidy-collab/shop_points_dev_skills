---
name: frontend-atlas
description: "门店积分 PC/H5 前端项目全景：技术栈、目录结构、路由与请求封装"
version: "0.1.0"
category: knowledge
tags:
  - frontend
  - react
  - store-integral
  - store-integral-h5
commands: []
---

# 前端项目全景

## 仓库映射

| 本地路径 | Git 仓库 | 大禹模块名 | 说明 |
|----------|----------|-----------|------|
| `/Users/qidi/IdeaProjects/store-integral` | `integral-admin` | `store-integral-cdn` | PC 管理端（多 client 单体仓） |
| `/Users/qidi/IdeaProjects/store-integral-h5` | `store-integral-h5` | `store-integral-h5-cdn` | H5 端（多 client 单体仓） |

默认分支均为 **`master`**。

---

## PC 管理端：`store-integral`

### 技术栈

| 项 | 值 |
|----|-----|
| 框架 | React 16 + TypeScript |
| 构建 | CRA + `@craco/craco` + `craco-less` |
| UI | Ant Design 5 |
| 路由 | `react-router-dom` v6 |
| 状态 | Redux + react-redux |
| 请求 | `client/src/utils/keFetch.js`（基于 `@lianjia/ketch`） |

### 子项目结构

| 目录 | 说明 | 门店积分需求是否涉及 |
|------|------|---------------------|
| `client/` | 门店积分 PC（`client-integral`） | **是，主要改动点** |
| `client-group/` | 集团相关 | 按需 |
| `client-template/` | 模板 | 极少 |

### 关键路径

- 路由入口：`client/src/router/index.tsx`
- 积分路由前缀：`/integral2/...`
- 示例页面：`/integral2/activity-config/city`
- 页面组件：`client/src/container/integralFangjianghu/`
- 本地启动：仓库根目录 `npm start`（进入 `client/` 执行 `BUILD_ENV=development craco start`）
- 构建：根目录 `npm run build` → `build.sh`（大禹构建变量 `BUILD_PROJECTS=client-integral`）

### 测试环境入口

```
https://point-pc.ttb.test.ke.com/integral2/activity-config/city
```

---

## H5 端：`store-integral-h5`

### 技术栈

| 项 | 值 |
|----|-----|
| 框架 | React 18（JSX 为主） |
| 构建 | CRA + craco |
| UI | Ant Design 5 + antd-mobile 5 |
| 路由 | `react-router-dom` v6 |
| 请求 | `client-integral/src/utils/axiosRequestAssistant.js`（axios 封装） |

### 子项目结构

| 目录 | 说明 | 门店积分需求是否涉及 |
|------|------|---------------------|
| `client-integral/` | 门店积分 H5 V2 | **是，主要改动点** |
| `client-grouph5/` | 集团 H5 | 按需 |
| `client-diandongh5/` | 店东 H5 | 按需 |
| `client-template/` | 模板 | 极少 |

### 关键路径

- 路由入口：`client-integral/src/router/index.js`
- 积分路由前缀：`/store-pointsV2/...`
- 首页组件：`client-integral/src/views/HomeV2/`
- 本地启动：`cd client-integral && npm start`
- 构建：`cd client-integral && npm run build`

### 测试环境入口

```
http://integral.ttb.test.ke.com/store-pointsV2/index?shopCode=TJDY0101&shopCodeInnerTest=TJDY0101
```

---

## 前端编码约定

1. **改哪里动哪里**：门店积分需求默认只改 `client/`（PC）或 `client-integral/`（H5）。
2. **API 调用**：PC 用 `keFetch`，H5 用 `axiosRequestAssistant`；不要引入新的 HTTP 库。
3. **路由**：新增页面必须在对应 `router/index` 注册路由。
4. **样式**：PC 用 less + css-modules；H5 注意移动端适配。
5. **提交前**：对应子项目 lint-staged 会通过 ESLint + Prettier。

## 与后端的对应关系

| 端 | 典型后端 | Controller 前缀 |
|----|----------|-------------------|
| H5 页面接口 | shop-points | `/shop-points/web/` |
| PC 管理接口 | shop-points | `/shop-points/manage/` 等 |
| 商城相关 | shop-points-lottery | `/shop-points-lottery/` |

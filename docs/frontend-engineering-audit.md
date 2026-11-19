# 阳光口腔 V1.0 · 2.1 前端工程检查与规范统一

本轮检查当前工作区中的 `miniprogram` 与 `admin-web`。验证在两份临时副本上进行，只复制项目文件、锁文件和构建配置，保留现有依赖目录、本机配置及未提交源码。两端均可复用，继续沿用已批准技术栈。本轮交付为检查报告和后续实施方案。

## 迁移阶段收尾

数据库迁移成果已在 `codex/database-migration` 提交为 `f608c32`，含 Alembic 配置与修订、SQLAlchemy 模型、迁移测试、结构对比和初始化说明，以及运行它们所需的本地配置。首次入库沿用三份验收版冻结文件的原始内容。

| 冻结文件 | 验收时、工作区和迁移提交中的 Git blob 指纹 |
|---|---|
| `sql/database-v1.sql` | `10416bf52794714ccd0f905daf40c2b500c62efd` |
| `sql/database-schema.md` | `8981292ec2346cb258da9413f686371ee94a143b` |
| `sql/database-er.mmd` | `e5999949258e420b0c832a2382faec8a91d8903a` |

2.1 从该提交建立 `codex/frontend-engineering-audit`。原先暂存的 `AGENTS.md` 和交接包仍然保留。两端前期工程文件中仍有未提交内容，本报告的验证结果对应当前工作区快照。下次从干净检出复验时，应先确认将这批前期工程文件随对应功能提交纳入版本管理。 [迁移报告](database-migration-validation.md)

## 工程现状和可复用内容

| 项目 | 当前状态 |
|---|---|
| 微信小程序 | 原生 `App` / `Page`、TypeScript、WXML、WXSS。`project.config.example.json` 启用开发者工具 TypeScript 编译插件；锁定 TypeScript 5.9.3、微信 API 类型 5.3.1、`tdesign-miniprogram` 1.18.0。现有 `app.*`、占位首页和配置模板可复用。TDesign 包已安装验证，当前页面未声明 TDesign 组件。 |
| 管理后台 | 锁定 React 18.3.1、TypeScript 5.9.3、Vite 5.4.21、Ant Design 5.29.3、Vitest 3.2.7。已有 React 挂载入口、Ant Design 样式入口、Vite 配置、占位 Shell 和一条渲染测试，可以在原项目上继续开发。 |
| TypeScript | 两端均启用 `strict`，使用各自的 `tsconfig.json`。小程序类型检查目前覆盖 `app.ts` 与 `pages/**/*.ts`；新增公共模块、配置或组件时同步扩展检查覆盖。后台覆盖 `src` 与 `vite.config.ts`。 |
| 运行环境 | 本次以 Node.js 22.21.1、npm 10.9.4 验证。后续统一用 Node.js 22、npm 10 和各自的 `package-lock.json` 执行 `npm ci`；依赖有意升级时在对应端同时更新清单与锁文件。 |

## 依赖与构建验证

| 检查 | 微信小程序 | 管理后台 |
|---|---|---|
| 锁定安装和依赖树 | `npm ci`、`npm ls --depth=0` 通过 | `npm ci`、`npm ls --depth=0` 通过 |
| 类型检查 | `npm run typecheck` 通过 | `npm run typecheck` 通过 |
| 现有测试和构建 | 路由入口文件、TS 编译配置和 TDesign 组件包静态检查通过。仓库只有 `typecheck` 脚本，微信开发者工具的 npm 构建、模拟器及真机预览本轮未执行 | `npm test` 1 项通过。Vite 生产构建通过，主 JS 500.64 kB，gzip 后 162.04 kB，触发 500 kB 提示 |
| 依赖审计 | 全量及 `--omit=dev` 均为 0 项 | 全量报告 5 项：2 中危、1 高危、2 严重，涉及 Vite、Vitest 及其开发依赖。`--omit=dev` 为 0 项 |

## 依赖和配置问题清单

| 优先级 | 问题 | 建议处理 |
|---|---|---|
| 高 | 后台锁文件包含 Vite、Vitest 开发工具链告警。npm 给出的修复涉及主版本升级 | 在后台框架实施前单独验证 Vite、React 插件、Vitest 与 Node.js 22 的兼容组合，更新锁文件并重跑审计、类型、测试及构建。本轮未改依赖。 |
| 高 | 两端暂无应用级开发、测试、生产配置或显式的模拟环境切换。根目录 `.env` 与 `.env.example` 服务于本地后端和基础设施 | 两端各自拥有类型化的公开配置入口。测试使用明确的模拟数据模式，生产禁止启用模拟适配器。提交无敏感值的配置模板，`.env.*` 本机覆盖继续忽略。 |
| 中 | 小程序安装了 TDesign，尚未生成平台 npm 产物或使用组件 | 2.2 在微信开发者工具执行「构建 npm」，用一个占位组件验证原生 TS 与 TDesign 运行。保存必要的配置模板，生成目录保留为本地文件。 |
| 中 | 后台 Vite 标准启动和生产构建已可用，但没有应用自定义模式配置、路由或 Shell 状态测试 | 2.3 建立基础布局、路由和模拟会话。扩展现有 Vitest 测试，补齐基础 HTML 文档元信息、直链回退及最小构建验收。 |
| 中 | 后台主包已触及构建警告阈值 | 引入后台框架路由时按需拆分页面，比较构建产物后再决定是否需要额外分包配置。 |

## 前端环境配置约定

| 环境 | 微信小程序 | 管理后台 |
|---|---|---|
| 开发 | 以微信 `envVersion=develop` 选择开发配置，使用本地测试 AppID 或游客配置及模拟数据 | Vite `development`，可用 `admin-web/.env.development.local` 覆盖公开配置，框架阶段默认使用模拟适配器 |
| 测试 | 自动化测试注入明确配置。微信 `trial` 对应体验版，使用获准的测试环境 | 使用 Vitest 和明确的 `test` 配置，固定模拟数据，不依赖开发或生产服务 |
| 生产 | `release` 使用批准的 AppID、HTTPS 合法域名和生产公开配置 | Vite `production` 仅注入公开值。API 接入阶段优先使用同源 `/api/v1`，如需异源地址，使用公开环境配置管理 |

小程序的本机 `project.config.json` 和 `project.private.config.json` 已由忽略规则覆盖，仓库保留无凭据示例。Vite `VITE_*`、小程序 AppID 和运行时配置均会暴露给客户端，数据库凭据、微信 AppSecret、COS 密钥等只保存在服务端。前端路由守卫用于界面导航，资源授权按服务端权限契约执行。 [权限矩阵](permissions.md)

## 目标目录与复用方式

按后续子任务增量创建目录。业务页面路径沿用已评审导航。 [三端路由](navigation.md)

```text
miniprogram/
  app.ts / app.json / app.wxss       原生入口、路由注册和全局样式
  pages/                            保留现有入口，按已评审的会员及员工路径扩展
  components/                       原生公共组件和 TDesign 组合
  config/                           公开环境配置与路由常量
  services/                         模拟会话、后续请求适配器
  types/                            微信端共用类型
  project.config.example.json       可提交项目模板
  package.json / package-lock.json / tsconfig.json

admin-web/
  index.html
  src/
    main.tsx / App.tsx               现有启动入口及加载入口
    router/                         路由及导航守卫
    layouts/                        后台布局与导航
    pages/                          逐步按路由加入页面
    components/                     公共交互组件
    config/                         公开环境配置
    services/                       模拟会话、后续请求适配器
    types/                          后台共用类型
  vite.config.ts
  package.json / package-lock.json / tsconfig.json
```

## 建议的 2.2 和 2.3 实施方案

1. **2.2 · 会员与员工小程序框架。** 沿用原生工程，保留当前入口，提供两种身份的路由占位、模拟会话分流、公开配置和基础组件。补齐公共目录的 TS 检查范围。以 `npm ci`、类型检查、微信开发者工具「构建 npm」和模拟器中的两端导航为验收点。
2. **2.3 · 管理后台框架。** 先单独验证并处理 Vite/Vitest 开发依赖告警，再复用 React 和 Ant Design 入口，加入基础布局、路由占位、模拟角色守卫及环境配置。以 `npm audit`、类型检查、Vitest、生产构建、直链回退和基础状态测试为验收点。

本轮未开发业务页面、未接真实 API、未修改数据库、未运行 Alembic。下一步等待 2.1 验收。

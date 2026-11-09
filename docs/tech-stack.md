# 技术选型与架构决策（V1.0）

状态：已采纳。日期：2026-11-09。

## 技术栈
- 微信会员端/员工端：同一个微信原生小程序 + TypeScript
- 小程序 UI：TDesign MiniProgram
- Web 管理后台：React + TypeScript + Vite + Ant Design 5
- 后端：Python + FastAPI + Pydantic 2
- ORM / 迁移：SQLAlchemy 2 + Alembic
- 数据库：PostgreSQL
- 缓存/异步任务：Redis + Celery + Celery Beat
- 文件存储：腾讯云 COS
- API：OpenAPI
- 部署：Docker Compose + Nginx
- 测试：Pytest、Vitest、微信开发者工具
- 开发协作：Claude Code + GitHub + Figma

## 架构
V1.0 采用模块化单体，不拆微服务。微信小程序和 React 管理后台统一调用 FastAPI REST API，前端不得直连数据库。

业务模块：auth、members、staff、assignments、customers、followups、points、products、exchange_orders、admin、audit。

```text
微信小程序（会员/员工） ─┐
                         ├─ HTTPS REST ─ Nginx ─ FastAPI ─ PostgreSQL
React 管理后台 ──────────┘                         ├─ Redis/Celery
                                                  └─ COS
```

## 仓库结构建议
```text
miniprogram/
admin-web/
backend/
  app/{api/v1,core,db,models,schemas,modules,tasks}/
  alembic/
  tests/
deploy/{docker-compose.yml,nginx/}
docs/
```

## 工程约定
- 数据库时间使用 UTC TIMESTAMPTZ，生日使用 DATE。
- 积分、库存、数量使用整数。
- 数据库结构只通过 Alembic migration 修改。
- API 前缀 `/api/v1`，请求/响应使用 Pydantic schema。
- 兑换、积分调整、客户转移、核销、退款必须事务化、幂等并写审计日志。
- 微信登录由后端用临时 code 换取身份，不信任客户端传入的 openid。
- 后台密码使用 Argon2id 哈希；token 有效期短且可撤销。
- 生产密钥只放环境变量/密钥管理服务，不提交 Git。
- V1.0 不接支付，不保存诊断、病历、影像、治疗方案等临床 EMR 数据。

## 部署
建议腾讯云：Nginx、FastAPI、Celery Worker/Beat 部署在云服务器；PostgreSQL、Redis 优先使用托管服务；COS 存储图片。生产数据库不暴露公网。微信公众平台配置 HTTPS 合法域名。开发、测试、生产环境分离。

## Figma → Claude Code
Figma 不是生产代码一键导出器。配置 Figma MCP 后，每次读取一个 Frame/组件；先实现设计 token 和公共组件，再逐页开发；每页用截图与 Figma 对照验收。小程序使用原生组件/TDesign，后台使用 React/Ant Design。不要一次性转码整份 Figma。

Figma：https://www.figma.com/design/vHq5a7gAf59V1lDiR94NdH

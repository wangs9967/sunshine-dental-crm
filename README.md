# Sunshine Dental CRM V1.0
阳光口腔会员运营管理系统。当前是开发交付文档与最小工程骨架，业务功能尚未实现，不可直接用于生产。

## 范围
- 单门店：只服务阳光口腔，不做多门店、门店切换或跨门店权限。
- 会员与员工共用一个微信原生小程序；管理后台为独立 Web。
- 不接入支付；不保存临床病历、诊断、影像或治疗方案。

## 技术栈
微信原生小程序 + TypeScript + TDesign；React + TypeScript + Vite + Ant Design 5；Python + FastAPI + Pydantic 2；PostgreSQL + SQLAlchemy 2 + Alembic；Redis + Celery；COS；Docker Compose + Nginx。

## 先读
[AGENTS.md](AGENTS.md) 和 [V1.0 交接入口](docs/project-handoff/v1.0/README_先看.md) 说明工程规范与业务范围。

- [统一的本地启动与验证说明](docs/local-development.md)
- [第二阶段设计评审报告与交付清单](docs/database-design-gap-report.md)

Figma: https://www.figma.com/design/vHq5a7gAf59V1lDiR94NdH

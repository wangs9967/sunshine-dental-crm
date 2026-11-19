# Sunshine Dental CRM V1.0
阳光口腔会员运营管理系统。当前是开发交付文档与最小工程骨架，业务功能尚未实现，不可直接用于生产。

## 范围
- 单门店：只服务阳光口腔，不做多门店、门店切换或跨门店权限。
- 会员与员工共用一个微信原生小程序；管理后台为独立 Web。
- 不接入支付；不保存临床病历、诊断、影像或治疗方案。

## 技术栈
微信原生小程序 + TypeScript + TDesign；React + TypeScript + Vite + Ant Design 5；Python + FastAPI + Pydantic 2；PostgreSQL + SQLAlchemy 2 + Alembic；Redis + Celery；COS；Docker Compose + Nginx。

## 先读
CLAUDE.md、docs/business-rules.md、docs/open-questions.md、docs/ui-freeze.md、docs/navigation.md、docs/permissions.md、docs/tech-stack.md、docs/database-schema.md、docs/api-spec.md、docs/test-cases.md。

Figma: https://www.figma.com/design/vHq5a7gAf59V1lDiR94NdH

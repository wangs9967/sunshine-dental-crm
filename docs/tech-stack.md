# 技术栈与架构
微信端：原生小程序 + TypeScript + TDesign。后台：React + TypeScript + Vite + Ant Design 5。后端：Python + FastAPI + Pydantic 2。数据层：PostgreSQL + SQLAlchemy 2 + Alembic。异步：Redis + Celery。文件：COS。部署：Docker Compose + Nginx。测试：Pytest、Vitest、微信开发者工具。
采用模块化单体，小程序与后台统一调用 FastAPI，前端不直连数据库。API 前缀 /api/v1。数据库时间 UTC TIMESTAMPTZ，生日 DATE。数据库变更走 Alembic。密钥不提交 Git。
单门店：不创建 stores 表，不使用 store_id，不做门店切换。

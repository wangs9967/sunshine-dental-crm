# 部署说明
本地用 Docker Compose 启动 PostgreSQL/Redis；FastAPI 与 React 本地运行；小程序使用微信开发者工具。生产建议 Nginx + FastAPI + Celery Worker/Beat，托管 PostgreSQL/Redis，COS 存商品图片，配置 HTTPS 与微信合法域名。生产数据库不暴露公网。上线前完成权限、积分、并发兑换、重复核销测试，配置备份恢复、监控、日志脱敏和回滚。真实密钥不得提交 Git。

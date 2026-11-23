# 部署说明
本地用 Docker Compose 启动 PostgreSQL/Redis；FastAPI 与 React 本地运行；小程序使用微信开发者工具。生产建议 Nginx + FastAPI + Celery Worker/Beat，托管 PostgreSQL/Redis，COS 存商品图片，配置 HTTPS 与微信合法域名。生产数据库不暴露公网。上线前完成权限、积分、并发兑换、重复核销测试，配置备份恢复、监控、日志脱敏和回滚。真实密钥不得提交 Git。

## 管理后台认证转发

通过 HTTPS 提供管理后台，并将同源 `/api/v1/` 转发到 FastAPI。由反向代理覆盖来自客户端的转发地址，FastAPI 仅信任指定的代理来源，以便按实际客户端地址执行登录限流。代理访问日志不采集认证请求体和 Authorization 头。

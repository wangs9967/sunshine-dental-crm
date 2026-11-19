# API 规范（FastAPI）
前缀 /api/v1；统一响应包含 success、data/error、request_id；敏感写操作使用 Idempotency-Key。
认证：POST /auth/wechat/login、POST /auth/admin/login、POST /auth/refresh、POST /auth/logout、GET /auth/me。
会员：POST /members/register、GET/PATCH /members/me、GET /members/me/points、GET /members/me/points-records、GET /members/me/exchange-orders。
员工/客户：GET /staff/me、GET /staff/me/qr-code、POST /staff/me/qr-token/rotate、GET /staff/me/customers、GET /customers/{id}、PATCH /customers/{id}/status、POST /customers/{id}/transfer、POST/GET /customers/{id}/followups。
任务：GET /followup-tasks、POST /followup-tasks、POST /followup-tasks/{id}/complete|postpone|ignore。
商城：GET /products、GET /products/{id}、POST/PATCH /admin/products、POST /exchange-orders、GET /exchange-orders/{id}、POST /exchange-orders/{id}/verify、POST /admin/points/adjustments。
单门店 API 不接受 store_id，不提供门店切换。具体角色权限见 permissions.md；未确认业务参数见 open-questions.md。

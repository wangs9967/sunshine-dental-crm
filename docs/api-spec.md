# FastAPI REST API 规范（V1.0）

API 前缀 `/api/v1`。统一 JSON 响应，包含 `success`、`data/error`、`request_id`。状态码：200/201、400、401、403、404、409、422、429、500。敏感写操作使用 `Idempotency-Key` 并写 operation_logs。

## 认证
| Method | Endpoint | 角色 |
|---|---|---|
| POST | /auth/wechat/login | public |
| POST | /auth/admin/login | public |
| POST | /auth/refresh | authenticated |
| POST | /auth/logout | authenticated |
| GET | /auth/me | authenticated |

微信登录只接受临时 code，由后端换取 openid；不信任客户端自报 openid。后台密码 Argon2id 哈希。

## 会员
| Method | Endpoint | 角色 |
|---|---|---|
| POST | /members/register | 已登录未注册用户 |
| GET/PATCH | /members/me | member |
| GET | /members/me/points | member |
| GET | /members/me/points-records | member |
| GET | /members/me/exchange-orders | member |
| GET | /members/me/exchange-orders/{order_id} | member |

注册事务创建会员、客户状态、积分账户；验证员工 scene_token 后建立首次归属；注册奖励只发放一次并写流水。

## 员工/客户
| Method | Endpoint | 角色 |
|---|---|---|
| GET | /staff/me | employee+ |
| GET | /staff/me/qr-code | employee+ |
| POST | /staff/me/qr-token/rotate | employee+/manager/admin |
| GET | /staff/me/customers | employee+ |
| GET | /customers/{customer_id} | employee+ |
| PATCH | /customers/{customer_id}/status | employee+ |
| GET | /customers/{customer_id}/assignments | manager/admin |
| POST | /customers/{customer_id}/transfer | manager/admin |
| GET | /customer-tags | employee+ |
| POST | /customers/{customer_id}/tags | employee+ |
| DELETE | /customers/{customer_id}/tags/{tag_id} | employee+ |

员工仅查本人当前客户，manager 限本门店，admin 全局。手机号默认脱敏。二维码用服务端签发的高熵 opaque scene_token；已有负责人的会员再次扫码不得覆盖负责人。

## 跟进/任务
| Method | Endpoint | 角色 |
|---|---|---|
| POST/GET | /customers/{customer_id}/followups | employee+ |
| GET | /followup-tasks | employee+ |
| POST | /followup-tasks | employee+/manager |
| POST | /followup-tasks/{task_id}/complete | employee+ |
| POST | /followup-tasks/{task_id}/postpone | employee+ |
| POST | /followup-tasks/{task_id}/ignore | employee+/manager |

跟进类型 phone/wechat/home_visit/store_visit/other。effective_contact=true 时更新 last_effective_contact_at。任务状态 pending/completed/postponed/ignored。

## 积分/商城/订单
| Method | Endpoint | 角色 |
|---|---|---|
| GET | /products | member+ |
| GET | /products/{product_id} | member+ |
| POST | /admin/products | admin |
| PATCH | /admin/products/{product_id} | admin |
| POST | /admin/products/{product_id}/publish | admin |
| POST | /admin/products/{product_id}/unpublish | admin |
| POST | /exchange-orders | member |
| GET | /exchange-orders/{order_id} | member/manager/admin（按范围） |
| POST | /exchange-orders/{order_id}/verify | manager/admin/授权员工 |
| POST | /exchange-orders/{order_id}/cancel | admin |
| POST | /exchange-orders/{order_id}/refund | admin |
| POST | /admin/points/adjustments | admin |
| GET | /admin/members/{member_id}/points-records | admin |

兑换事务锁定积分账户和商品，检查商品状态、库存、积分、限购，扣积分、写流水、扣库存、创建订单和核销码。核销只允许 pending→verified。退款的订单、积分返还和流水同事务完成。V1.0 不接支付。

## 管理后台
GET `/admin/dashboard`、`/admin/members`、`/admin/members/{id}`、`/admin/staff`、`/admin/followups`、`/admin/followup-tasks`、`/admin/exchange-orders`、`/admin/assignments`、`/admin/operation-logs`、`/admin/system-configs`；POST `/admin/staff`；PATCH `/admin/staff/{id}`、`/admin/system-configs/{key}`。manager 查询限本门店。

## 上传/定时任务
POST `/uploads/presign` 获取 COS 短时上传授权。Celery Beat 每日执行 generate_recall_tasks、generate_reactivation_tasks、cleanup_expired_qr_tokens。提醒只生成后台名单，员工手动联系。

## 错误码
UNAUTHENTICATED、FORBIDDEN、INVALID_ARGUMENT、NOT_FOUND、CONFLICT、RATE_LIMITED、MEMBER_ALREADY_EXISTS、INVALID_SCENE_TOKEN、EMPLOYEE_DISABLED、CUSTOMER_NOT_ASSIGNED、CROSS_STORE_FORBIDDEN、SAME_OWNER、TARGET_EMPLOYEE_DISABLED、INSUFFICIENT_POINTS、POINTS_NOT_ENOUGH、PRODUCT_OFFLINE、OUT_OF_STOCK、LIMIT_EXCEEDED、ORDER_ALREADY_VERIFIED、INVALID_ORDER_STATUS、DUPLICATE_REQUEST、INTERNAL_ERROR。

## 实现要求
FastAPI 自动生成 OpenAPI；所有 endpoint 使用 Pydantic schema；路由层只处理认证、校验和响应，业务规则放 service 层；SQLAlchemy session 统一管理。Pytest 覆盖重复请求、积分不足、库存不足、并发兑换、重复核销和越权访问。

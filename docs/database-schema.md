# PostgreSQL 数据库设计（V1.0）

数据库：PostgreSQL；ORM：SQLAlchemy 2；迁移：Alembic。主键 UUID；时间 TIMESTAMPTZ（UTC）；生日 DATE；积分/库存/数量 INTEGER；配置 JSONB。手机号应用层加密并使用 HMAC 检索值，日志不得记录明文。V1.0 不保存临床 EMR 数据。

## 表清单

| 表 | 关键字段/用途 |
|---|---|
| accounts | id、wechat_openid UNIQUE、username UNIQUE、password_hash、status、last_login_at |
| stores | id、store_code UNIQUE、name、address、phone_encrypted、status |
| staff_profiles | id、account_id UNIQUE FK、employee_no UNIQUE、name、phone_encrypted、phone_search_hash、store_id FK、role、status |
| members | id、account_id UNIQUE FK、member_no UNIQUE、name、birthday、phone_encrypted、phone_search_hash、status、register_source、source_employee_id FK |
| employee_qr_tokens | id、staff_id FK、token_hash UNIQUE、expires_at、revoked_at |
| customer_assignments | id、member_id FK、staff_id FK、store_id FK、is_current、bind_source、bind_time、end_time、change_reason、operator_id |
| customer_status | id、member_id UNIQUE FK、visit_status、consume_status、deal_status、last_visit_at、last_consume_at、next_recall_at、last_effective_contact_at |
| customer_tags | id、name UNIQUE、description、status |
| member_tag_relations | id、member_id FK、tag_id FK、created_by；member_id+tag_id UNIQUE |
| points_accounts | id、member_id UNIQUE FK、balance CHECK >= 0、total_earned、total_spent |
| points_records | id、member_id FK、change_amount、before_balance、after_balance、type、biz_type、biz_id、idempotency_key UNIQUE、operator_id |
| followup_records | id、member_id FK、staff_id FK、type、followup_at、content、customer_feedback、gift_given、gift_name、next_followup_at、effective_contact |
| followup_tasks | id、member_id FK、staff_id FK、task_type、rule_code、status、scheduled_at、dedupe_key UNIQUE、completed_at、result |
| products | id、name、cover_image_key、images JSONB、description、points_price CHECK > 0、stock CHECK >= 0、limit_per_user、status、sort、version |
| exchange_orders | id、order_no UNIQUE、member_id FK、product_id FK、product_snapshot JSONB、quantity、points_cost、status、idempotency_key UNIQUE、verification_code UNIQUE、verified_by、verified_at、cancelled_at、refunded_at |
| system_configs | id、key UNIQUE、value JSONB、description、updated_by、updated_at |
| operation_logs | id、operator_id、operator_role、action、module、target_id、summary、before_redacted JSONB、after_redacted JSONB、request_id、created_at |

## 关键规则
- `customer_assignments` 建部分唯一索引：`UNIQUE(member_id) WHERE is_current = TRUE`。
- `customer_status.member_id`、`points_accounts.member_id` 唯一。
- `points_records.idempotency_key`、`followup_tasks.dedupe_key` 唯一。
- 积分流水只新增，不更新/删除。
- 会员首次来源员工 `source_employee_id` 永久保留；当前负责人由归属历史单独维护。
- 到店、消费、成交三种状态独立保存。
- 跟进类型：phone/wechat/home_visit/store_visit/other。
- 提醒类型：recall/reactivation/manual；默认沉睡阈值 90/180/365 天。

## 事务规则
兑换时同一事务内检查幂等键，锁定积分账户和商品（SELECT FOR UPDATE），检查上架/库存/积分/限购，扣积分、写流水、扣库存、创建订单和核销码。失败全部回滚。

客户转移时锁定当前归属，关闭旧记录、新增新记录、写审计日志。核销只允许 pending→verified。退款时订单状态、积分返还、流水同事务完成。

## 权限
member 仅本人；employee 仅本人当前负责客户；manager 限本门店；admin 全局。权限必须在服务端 SQL/service 层校验。

# 阳光口腔会员运营管理系统 V1.0 — 数据库最终版

> 目标数据库：Tencent CloudBase 数据库（文档型）。所有敏感写操作通过云函数执行。

## 1. 通用约定

- 主键统一 `_id`；
- 时间统一使用服务端时间；
- 业务编号与幂等键必须由服务端生成/校验；
- 不保存年龄，年龄由 `birthday` 动态计算；
- 不在 V1.0 保存诊断、病历、影像、治疗方案等临床 EMR 数据；
- 涉及会员隐私的日志字段必须脱敏，`operation_logs` 不直接保存完整手机号等敏感快照；
- 重要实体使用 `status`/软停用，不进行随意物理删除。

## 2. `users`

会员主表。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `_id` | string | 是 | 主键 |
| `openid` | string | 是 | 微信用户标识 |
| `member_no` | string | 是 | 会员编号 |
| `name` | string | 是 | 姓名 |
| `birthday` | date | 是 | 出生日期 |
| `phone` | string | 是 | 标准化手机号 |
| `avatar_url` | string | 否 | 头像 |
| `status` | string | 是 | `active/disabled` |
| `register_source` | string | 是 | `employee_qr/direct/admin_import` |
| `source_employee_id` | string | 否 | 首次来源员工，不随归属转移改变 |
| `created_at` | date | 是 | 注册时间 |
| `updated_at` | date | 是 | 更新时间 |

索引：
- `openid` 唯一；
- `member_no` 唯一；
- `phone` 普通索引；
- `source_employee_id + created_at`。

## 3. `employees`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `_id` | string | 是 | 主键 |
| `employee_no` | string | 是 | 员工编号 |
| `name` | string | 是 | 姓名 |
| `phone` | string | 是 | 手机号 |
| `openid` | string | 否 | 绑定微信 |
| `store_id` | string | 是 | 门店 |
| `position` | string | 否 | 职位 |
| `role` | string | 是 | `employee/manager/admin` |
| `status` | string | 是 | `active/disabled/resigned` |
| `qr_scene_token` | string | 否 | 当前二维码场景 token/版本引用 |
| `created_at` | date | 是 | 创建时间 |
| `updated_at` | date | 是 | 更新时间 |

索引：`employee_no` 唯一；`openid` 稀疏唯一；`store_id + status`。

## 4. `stores`

`_id, name, address, phone, status, created_at, updated_at`

索引：`status`。

## 5. `customer_assignments`

客户归属历史表，禁止覆盖历史。

| 字段 | 类型 | 说明 |
|---|---|---|
| `_id` | string | 主键 |
| `user_id` | string | 会员 |
| `employee_id` | string | 当前记录对应员工 |
| `store_id` | string | 门店 |
| `is_current` | boolean | 是否当前负责人 |
| `bind_source` | string | `employee_qr/manual_transfer/import` |
| `bind_time` | date | 生效时间 |
| `end_time` | date | 结束时间 |
| `change_reason` | string | 转移原因 |
| `operator_id` | string | 操作者 |
| `created_at` | date | 创建时间 |

索引：
- `user_id + is_current`；
- `employee_id + is_current`；
- `employee_id + bind_time`。

业务约束：同一 `user_id` 同时只能有一条 `is_current=true`。

## 6. `customer_status`

`_id, user_id, visit_status, consume_status, deal_status, last_visit_at, last_consume_at, next_recall_at, last_effective_contact_at, updated_by, updated_at`

枚举：
- `visit_status`: `not_visited/visited`
- `consume_status`: `not_consumed/consumed`
- `deal_status`: `not_dealt/dealt`

索引：`user_id` 唯一；`next_recall_at`；`last_effective_contact_at`；三类状态组合按实际查询建立复合索引。

## 7. `customer_tags`

`_id, name, description, status, created_at, updated_at`

索引：`name` 唯一（active 范围由业务保证）。

## 8. `customer_tag_relations`

`_id, user_id, tag_id, created_by, created_at`

索引：`user_id + tag_id` 唯一；`tag_id + created_at`。

## 9. `points_accounts`

| 字段 | 类型 | 说明 |
|---|---|---|
| `_id` | string | 主键 |
| `user_id` | string | 会员 |
| `balance` | number | 可用积分 |
| `total_earned` | number | 累计获得 |
| `total_spent` | number | 累计使用 |
| `version` | number | 乐观并发版本（如需要） |
| `updated_at` | date | 更新时间 |

索引：`user_id` 唯一。

## 10. `points_records`

积分不可变流水。任何积分变化必须写流水。

| 字段 | 类型 | 说明 |
|---|---|---|
| `_id` | string | 主键 |
| `user_id` | string | 会员 |
| `change_amount` | number | 正/负变动 |
| `before_balance` | number | 变更前 |
| `after_balance` | number | 变更后 |
| `type` | string | `register_bonus/activity/manual_add/manual_deduct/exchange/refund` |
| `biz_type` | string | 业务类型 |
| `biz_id` | string | 业务单据 ID |
| `idempotency_key` | string | 幂等键 |
| `remark` | string | 备注 |
| `operator_id` | string | 操作者，系统可为空/系统账号 |
| `created_at` | date | 时间 |

索引：
- `user_id + created_at(desc)`；
- `biz_type + biz_id`；
- `idempotency_key` 唯一。

## 11. `followup_records`

`_id, user_id, employee_id, type, followup_at, content, customer_feedback, gift_given, gift_name, next_followup_at, effective_contact, remark, created_at, updated_at`

`type`: `phone/wechat/home_visit/store_visit/other`

索引：`user_id + followup_at(desc)`；`employee_id + followup_at(desc)`；`next_followup_at`。

当 `effective_contact=true` 时，事务/服务端逻辑同步更新 `customer_status.last_effective_contact_at`。

## 12. `followup_tasks`

| 字段 | 类型 | 说明 |
|---|---|---|
| `_id` | string | 主键 |
| `user_id` | string | 会员 |
| `employee_id` | string | 负责人 |
| `task_type` | string | `recall/reactivation/manual` |
| `rule_code` | string | `recall_due/inactive_90d/inactive_180d/inactive_365d/manual` |
| `status` | string | `pending/completed/postponed/ignored` |
| `scheduled_at` | date | 应处理时间 |
| `source_date` | date | 生成任务所依据时间 |
| `dedupe_key` | string | 去重键 |
| `completed_at` | date | 完成时间 |
| `result` | string | 结果 |
| `next_followup_at` | date | 下次跟进 |
| `created_at` | date | 创建时间 |
| `updated_at` | date | 更新时间 |

索引：
- `employee_id + status + scheduled_at`；
- `user_id + status`；
- `dedupe_key` 唯一。

## 13. `products`

`_id, name, cover_image, images, description, points_price, stock, limit_per_user, status, sort, version, created_at, updated_at`

`status`: `draft/online/offline`

索引：`status + sort`；`updated_at`。

库存只允许服务端事务写入。

## 14. `exchange_orders`

| 字段 | 类型 | 说明 |
|---|---|---|
| `_id` | string | 主键 |
| `order_no` | string | 订单号 |
| `user_id` | string | 会员 |
| `product_id` | string | 商品 |
| `product_snapshot` | object | 下单时商品快照 |
| `quantity` | number | 数量 |
| `points_cost` | number | 总积分 |
| `status` | string | `pending/verified/cancelled/refunded` |
| `idempotency_key` | string | 兑换幂等键 |
| `verification_code` | string | 核销码 |
| `verified_by` | string | 核销人 |
| `verified_at` | date | 核销时间 |
| `cancel_reason` | string | 取消原因 |
| `cancelled_at` | date | 取消时间 |
| `refunded_at` | date | 退积分时间 |
| `created_at` | date | 创建时间 |
| `updated_at` | date | 更新时间 |

索引：
- `order_no` 唯一；
- `idempotency_key` 唯一；
- `verification_code` 索引；
- `user_id + created_at(desc)`；
- `status + created_at(desc)`。

## 15. `system_configs`

`_id, key, value, value_type, description, updated_by, updated_at`

初始 key：
- `register_bonus_points = 100`
- `reactivation_90_days = 90`
- `reactivation_180_days = 180`
- `reactivation_365_days = 365`

索引：`key` 唯一。

## 16. `operation_logs`

`_id, operator_id, operator_role, action, module, target_id, summary, before_redacted, after_redacted, request_id, created_at`

不得把完整手机号、openid、敏感个人数据原样写入审计日志。

索引：`operator_id + created_at(desc)`；`module + target_id + created_at(desc)`；`request_id`。

## 17. 权限与安全原则

- 客户端不得直接修改积分、库存、订单状态、归属关系、员工角色；
- 敏感集合默认禁止客户端直接写；
- 管理后台也通过服务端 API/云函数执行业务写操作；
- 每个云函数进行身份、角色、数据范围校验；
- 员工只能访问当前归属为自己的客户，manager 仅限本门店，admin 全局；
- 微信二维码 `scene_token` 必须服务端验证签名/有效期/员工状态。

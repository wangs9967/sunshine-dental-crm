# 阳光口腔 V1.0 数据库字段字典

第二阶段最终评审稿。以下为 PostgreSQL 16 从隔离事务加载 [DDL](database-v1.sql) 后返回的字段、约束与索引。关系图见 [ER](database-er.mmd)，业务语义见[数据库设计](../docs/database-schema.md)。时间点使用 TIMESTAMPTZ，生日使用 DATE。外键使用 ON DELETE RESTRICT。主键与唯一约束的自动索引随约束列出。

## accounts

统一登录身份，后台密码使用 Argon2id 哈希。

| 字段 | PostgreSQL 类型 | 可空 | 默认值 |
|---|---|---|---|
| `id` | `uuid` | 否 | `gen_random_uuid()` |
| `wechat_openid` | `character varying(128)` | 是 | — |
| `wechat_unionid` | `character varying(128)` | 是 | — |
| `username` | `character varying(64)` | 是 | — |
| `password_hash` | `character varying(255)` | 是 | — |
| `status` | `character varying(20)` | 否 | `'active'::character varying` |
| `last_login_at` | `timestamp with time zone` | 是 | — |
| `created_at` | `timestamp with time zone` | 否 | `now()` |
| `updated_at` | `timestamp with time zone` | 否 | `now()` |

| 约束或索引 | 定义 |
|---|---|
| 主键 `accounts_pkey` | `PRIMARY KEY (id)` |
| 唯一约束 `accounts_username_key` | `UNIQUE (username)` |
| 唯一约束 `accounts_wechat_openid_key` | `UNIQUE (wechat_openid)` |
| 索引 `ix_accounts_unionid` | `CREATE INDEX ix_accounts_unionid ON accounts USING btree (wechat_unionid)` |

## staff_profiles

员工档案及角色，每个账号最多一个员工档案。

| 字段 | PostgreSQL 类型 | 可空 | 默认值 |
|---|---|---|---|
| `id` | `uuid` | 否 | `gen_random_uuid()` |
| `account_id` | `uuid` | 否 | — |
| `employee_no` | `character varying(32)` | 是 | — |
| `display_name` | `character varying(80)` | 否 | — |
| `phone_ciphertext` | `bytea` | 是 | — |
| `phone_search_hash` | `bytea` | 是 | — |
| `role` | `character varying(20)` | 否 | — |
| `status` | `character varying(20)` | 否 | `'active'::character varying` |
| `hired_at` | `date` | 是 | — |
| `disabled_at` | `timestamp with time zone` | 是 | — |
| `created_at` | `timestamp with time zone` | 否 | `now()` |
| `updated_at` | `timestamp with time zone` | 否 | `now()` |

| 约束或索引 | 定义 |
|---|---|
| 外键 `staff_profiles_account_id_fkey` | `FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE RESTRICT` |
| 主键 `staff_profiles_pkey` | `PRIMARY KEY (id)` |
| 唯一约束 `staff_profiles_account_id_key` | `UNIQUE (account_id)` |
| 唯一约束 `staff_profiles_employee_no_key` | `UNIQUE (employee_no)` |
| 索引 `ix_staff_role_status` | `CREATE INDEX ix_staff_role_status ON staff_profiles USING btree (role, status)` |

## members

会员身份，手机号加密存储，HMAC 用于精确检索。

| 字段 | PostgreSQL 类型 | 可空 | 默认值 |
|---|---|---|---|
| `id` | `uuid` | 否 | `gen_random_uuid()` |
| `account_id` | `uuid` | 否 | — |
| `member_no` | `character varying(32)` | 否 | — |
| `name` | `character varying(80)` | 否 | — |
| `birthday` | `date` | 否 | — |
| `phone_ciphertext` | `bytea` | 否 | — |
| `phone_search_hash` | `bytea` | 否 | — |
| `register_source` | `character varying(24)` | 否 | — |
| `source_employee_id` | `uuid` | 是 | — |
| `status` | `character varying(20)` | 否 | `'active'::character varying` |
| `registered_at` | `timestamp with time zone` | 否 | `now()` |
| `created_at` | `timestamp with time zone` | 否 | `now()` |
| `updated_at` | `timestamp with time zone` | 否 | `now()` |

| 约束或索引 | 定义 |
|---|---|
| 外键 `members_account_id_fkey` | `FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE RESTRICT` |
| 外键 `members_source_employee_id_fkey` | `FOREIGN KEY (source_employee_id) REFERENCES staff_profiles(id) ON DELETE RESTRICT` |
| 主键 `members_pkey` | `PRIMARY KEY (id)` |
| 唯一约束 `members_account_id_key` | `UNIQUE (account_id)` |
| 唯一约束 `members_member_no_key` | `UNIQUE (member_no)` |
| 索引 `ix_members_phone_hash` | `CREATE INDEX ix_members_phone_hash ON members USING btree (phone_search_hash)` |
| 索引 `ix_members_status_created` | `CREATE INDEX ix_members_status_created ON members USING btree (status, created_at DESC)` |

## employee_qr_tokens

员工二维码，保存令牌摘要和失效时间。

| 字段 | PostgreSQL 类型 | 可空 | 默认值 |
|---|---|---|---|
| `id` | `uuid` | 否 | `gen_random_uuid()` |
| `staff_id` | `uuid` | 否 | — |
| `token_hash` | `bytea` | 否 | — |
| `expires_at` | `timestamp with time zone` | 否 | — |
| `revoked_at` | `timestamp with time zone` | 是 | — |
| `created_at` | `timestamp with time zone` | 否 | `now()` |

| 约束或索引 | 定义 |
|---|---|
| 外键 `employee_qr_tokens_staff_id_fkey` | `FOREIGN KEY (staff_id) REFERENCES staff_profiles(id) ON DELETE RESTRICT` |
| 主键 `employee_qr_tokens_pkey` | `PRIMARY KEY (id)` |
| 唯一约束 `employee_qr_tokens_token_hash_key` | `UNIQUE (token_hash)` |
| 索引 `ix_qr_staff_expiry` | `CREATE INDEX ix_qr_staff_expiry ON employee_qr_tokens USING btree (staff_id, expires_at)` |

## customer_assignments

客户归属历史，每位会员最多一条当前归属。

| 字段 | PostgreSQL 类型 | 可空 | 默认值 |
|---|---|---|---|
| `id` | `uuid` | 否 | `gen_random_uuid()` |
| `member_id` | `uuid` | 否 | — |
| `staff_id` | `uuid` | 否 | — |
| `is_current` | `boolean` | 否 | `true` |
| `bind_source` | `character varying(24)` | 否 | — |
| `started_at` | `timestamp with time zone` | 否 | `now()` |
| `ended_at` | `timestamp with time zone` | 是 | — |
| `change_reason` | `text` | 是 | — |
| `operator_account_id` | `uuid` | 是 | — |
| `created_at` | `timestamp with time zone` | 否 | `now()` |

| 约束或索引 | 定义 |
|---|---|
| 外键 `customer_assignments_member_id_fkey` | `FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE RESTRICT` |
| 外键 `customer_assignments_operator_account_id_fkey` | `FOREIGN KEY (operator_account_id) REFERENCES accounts(id) ON DELETE RESTRICT` |
| 外键 `customer_assignments_staff_id_fkey` | `FOREIGN KEY (staff_id) REFERENCES staff_profiles(id) ON DELETE RESTRICT` |
| 主键 `customer_assignments_pkey` | `PRIMARY KEY (id)` |
| 索引 `ix_assignment_staff_current` | `CREATE INDEX ix_assignment_staff_current ON customer_assignments USING btree (staff_id, is_current)` |
| 索引 `uq_assignment_current_member` | `CREATE UNIQUE INDEX uq_assignment_current_member ON customer_assignments USING btree (member_id) WHERE is_current` |

## customer_status

到店、消费、成交等独立运营状态。

| 字段 | PostgreSQL 类型 | 可空 | 默认值 |
|---|---|---|---|
| `id` | `uuid` | 否 | `gen_random_uuid()` |
| `member_id` | `uuid` | 否 | — |
| `visit_status` | `character varying(20)` | 否 | `'not_visited'::character varying` |
| `consume_status` | `character varying(20)` | 否 | `'not_consumed'::character varying` |
| `deal_status` | `character varying(20)` | 否 | `'not_dealt'::character varying` |
| `last_visit_at` | `timestamp with time zone` | 是 | — |
| `last_consume_at` | `timestamp with time zone` | 是 | — |
| `next_recall_at` | `timestamp with time zone` | 是 | — |
| `last_effective_contact_at` | `timestamp with time zone` | 是 | — |
| `updated_by_account_id` | `uuid` | 是 | — |
| `created_at` | `timestamp with time zone` | 否 | `now()` |
| `updated_at` | `timestamp with time zone` | 否 | `now()` |

| 约束或索引 | 定义 |
|---|---|
| 外键 `customer_status_member_id_fkey` | `FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE RESTRICT` |
| 外键 `customer_status_updated_by_account_id_fkey` | `FOREIGN KEY (updated_by_account_id) REFERENCES accounts(id) ON DELETE RESTRICT` |
| 主键 `customer_status_pkey` | `PRIMARY KEY (id)` |
| 唯一约束 `customer_status_member_id_key` | `UNIQUE (member_id)` |
| 索引 `ix_customer_recall` | `CREATE INDEX ix_customer_recall ON customer_status USING btree (next_recall_at) WHERE (next_recall_at IS NOT NULL)` |

## customer_tags

运营标签。

| 字段 | PostgreSQL 类型 | 可空 | 默认值 |
|---|---|---|---|
| `id` | `uuid` | 否 | `gen_random_uuid()` |
| `name` | `character varying(40)` | 否 | — |
| `description` | `character varying(255)` | 是 | — |
| `status` | `character varying(20)` | 否 | `'active'::character varying` |
| `created_at` | `timestamp with time zone` | 否 | `now()` |
| `updated_at` | `timestamp with time zone` | 否 | `now()` |

| 约束或索引 | 定义 |
|---|---|
| 主键 `customer_tags_pkey` | `PRIMARY KEY (id)` |
| 唯一约束 `customer_tags_name_key` | `UNIQUE (name)` |

## member_tag_relations

会员与标签的多对多关联。

| 字段 | PostgreSQL 类型 | 可空 | 默认值 |
|---|---|---|---|
| `member_id` | `uuid` | 否 | — |
| `tag_id` | `uuid` | 否 | — |
| `created_by_account_id` | `uuid` | 是 | — |
| `created_at` | `timestamp with time zone` | 否 | `now()` |

| 约束或索引 | 定义 |
|---|---|
| 外键 `member_tag_relations_created_by_account_id_fkey` | `FOREIGN KEY (created_by_account_id) REFERENCES accounts(id) ON DELETE RESTRICT` |
| 外键 `member_tag_relations_member_id_fkey` | `FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE RESTRICT` |
| 外键 `member_tag_relations_tag_id_fkey` | `FOREIGN KEY (tag_id) REFERENCES customer_tags(id) ON DELETE RESTRICT` |
| 主键 `member_tag_relations_pkey` | `PRIMARY KEY (member_id, tag_id)` |
| 索引 `ix_member_tag_tag` | `CREATE INDEX ix_member_tag_tag ON member_tag_relations USING btree (tag_id)` |

## points_accounts

积分余额快照，注册时创建。

| 字段 | PostgreSQL 类型 | 可空 | 默认值 |
|---|---|---|---|
| `id` | `uuid` | 否 | `gen_random_uuid()` |
| `member_id` | `uuid` | 否 | — |
| `balance` | `bigint` | 否 | `0` |
| `total_earned` | `bigint` | 否 | `0` |
| `total_spent` | `bigint` | 否 | `0` |
| `created_at` | `timestamp with time zone` | 否 | `now()` |
| `updated_at` | `timestamp with time zone` | 否 | `now()` |

| 约束或索引 | 定义 |
|---|---|
| 检查约束 `points_accounts_balance_check` | `CHECK ((balance >= 0))` |
| 外键 `points_accounts_member_id_fkey` | `FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE RESTRICT` |
| 主键 `points_accounts_pkey` | `PRIMARY KEY (id)` |
| 唯一约束 `points_accounts_member_id_key` | `UNIQUE (member_id)` |

## points_records

不可变积分流水，扣减与订单关联。

| 字段 | PostgreSQL 类型 | 可空 | 默认值 |
|---|---|---|---|
| `id` | `uuid` | 否 | `gen_random_uuid()` |
| `member_id` | `uuid` | 否 | — |
| `delta_points` | `bigint` | 否 | — |
| `balance_before` | `bigint` | 否 | — |
| `balance_after` | `bigint` | 否 | — |
| `record_type` | `character varying(24)` | 否 | — |
| `source_type` | `character varying(32)` | 否 | — |
| `exchange_order_id` | `uuid` | 是 | — |
| `idempotency_key` | `character varying(128)` | 否 | — |
| `request_fingerprint` | `bytea` | 否 | — |
| `reason` | `text` | 是 | — |
| `operator_account_id` | `uuid` | 是 | — |
| `created_at` | `timestamp with time zone` | 否 | `now()` |

| 约束或索引 | 定义 |
|---|---|
| 检查约束 `points_records_balance_after_check` | `CHECK ((balance_after >= 0))` |
| 检查约束 `points_records_balance_before_check` | `CHECK ((balance_before >= 0))` |
| 检查约束 `points_records_check` | `CHECK ((balance_after = (balance_before + delta_points)))` |
| 检查约束 `points_records_delta_points_check` | `CHECK ((delta_points <> 0))` |
| 外键 `fk_points_exchange_order` | `FOREIGN KEY (exchange_order_id) REFERENCES exchange_orders(id) ON DELETE RESTRICT` |
| 外键 `points_records_member_id_fkey` | `FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE RESTRICT` |
| 外键 `points_records_operator_account_id_fkey` | `FOREIGN KEY (operator_account_id) REFERENCES accounts(id) ON DELETE RESTRICT` |
| 主键 `points_records_pkey` | `PRIMARY KEY (id)` |
| 唯一约束 `points_records_exchange_order_id_key` | `UNIQUE (exchange_order_id)` |
| 唯一约束 `points_records_idempotency_key_key` | `UNIQUE (idempotency_key)` |
| 索引 `ix_points_member_created` | `CREATE INDEX ix_points_member_created ON points_records USING btree (member_id, created_at DESC)` |

## followup_records

普通跟进及家访，仅保存运营沟通信息。

| 字段 | PostgreSQL 类型 | 可空 | 默认值 |
|---|---|---|---|
| `id` | `uuid` | 否 | `gen_random_uuid()` |
| `member_id` | `uuid` | 否 | — |
| `staff_id` | `uuid` | 否 | — |
| `contact_type` | `character varying(24)` | 否 | — |
| `followup_at` | `timestamp with time zone` | 否 | `now()` |
| `content` | `text` | 否 | — |
| `customer_feedback` | `text` | 是 | — |
| `effective_contact` | `boolean` | 否 | `false` |
| `gift_given` | `boolean` | 否 | `false` |
| `gift_name` | `character varying(120)` | 是 | — |
| `next_followup_at` | `timestamp with time zone` | 是 | — |
| `created_by_account_id` | `uuid` | 是 | — |
| `created_at` | `timestamp with time zone` | 否 | `now()` |

| 约束或索引 | 定义 |
|---|---|
| 外键 `followup_records_created_by_account_id_fkey` | `FOREIGN KEY (created_by_account_id) REFERENCES accounts(id) ON DELETE RESTRICT` |
| 外键 `followup_records_member_id_fkey` | `FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE RESTRICT` |
| 外键 `followup_records_staff_id_fkey` | `FOREIGN KEY (staff_id) REFERENCES staff_profiles(id) ON DELETE RESTRICT` |
| 主键 `followup_records_pkey` | `PRIMARY KEY (id)` |
| 索引 `ix_followup_member_time` | `CREATE INDEX ix_followup_member_time ON followup_records USING btree (member_id, followup_at DESC)` |

## followup_tasks

后台生成的复查及唤醒任务，由员工手动联系。

| 字段 | PostgreSQL 类型 | 可空 | 默认值 |
|---|---|---|---|
| `id` | `uuid` | 否 | `gen_random_uuid()` |
| `member_id` | `uuid` | 否 | — |
| `assigned_staff_id` | `uuid` | 是 | — |
| `task_type` | `character varying(24)` | 否 | — |
| `status` | `character varying(20)` | 否 | `'pending'::character varying` |
| `title` | `character varying(120)` | 否 | — |
| `scheduled_at` | `timestamp with time zone` | 否 | — |
| `postponed_until` | `timestamp with time zone` | 是 | — |
| `dedupe_key` | `character varying(160)` | 否 | — |
| `result` | `text` | 是 | — |
| `completed_at` | `timestamp with time zone` | 是 | — |
| `created_by_account_id` | `uuid` | 是 | — |
| `created_at` | `timestamp with time zone` | 否 | `now()` |
| `updated_at` | `timestamp with time zone` | 否 | `now()` |

| 约束或索引 | 定义 |
|---|---|
| 外键 `followup_tasks_assigned_staff_id_fkey` | `FOREIGN KEY (assigned_staff_id) REFERENCES staff_profiles(id) ON DELETE RESTRICT` |
| 外键 `followup_tasks_created_by_account_id_fkey` | `FOREIGN KEY (created_by_account_id) REFERENCES accounts(id) ON DELETE RESTRICT` |
| 外键 `followup_tasks_member_id_fkey` | `FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE RESTRICT` |
| 主键 `followup_tasks_pkey` | `PRIMARY KEY (id)` |
| 唯一约束 `followup_tasks_dedupe_key_key` | `UNIQUE (dedupe_key)` |
| 索引 `ix_tasks_staff_status` | `CREATE INDEX ix_tasks_staff_status ON followup_tasks USING btree (assigned_staff_id, status)` |
| 索引 `ix_tasks_status_schedule` | `CREATE INDEX ix_tasks_status_schedule ON followup_tasks USING btree (status, scheduled_at)` |

## products

积分商品和库存快照。

| 字段 | PostgreSQL 类型 | 可空 | 默认值 |
|---|---|---|---|
| `id` | `uuid` | 否 | `gen_random_uuid()` |
| `name` | `character varying(120)` | 否 | — |
| `category` | `character varying(40)` | 是 | — |
| `cover_image_key` | `character varying(500)` | 是 | — |
| `image_keys` | `jsonb` | 否 | `'[]'::jsonb` |
| `description` | `text` | 是 | — |
| `points_price` | `bigint` | 否 | — |
| `stock` | `integer` | 否 | `0` |
| `per_user_monthly_limit` | `integer` | 是 | — |
| `status` | `character varying(20)` | 否 | `'draft'::character varying` |
| `sort_order` | `integer` | 否 | `0` |
| `version` | `integer` | 否 | `1` |
| `created_at` | `timestamp with time zone` | 否 | `now()` |
| `updated_at` | `timestamp with time zone` | 否 | `now()` |

| 约束或索引 | 定义 |
|---|---|
| 检查约束 `products_per_user_monthly_limit_check` | `CHECK ((per_user_monthly_limit > 0))` |
| 检查约束 `products_points_price_check` | `CHECK ((points_price > 0))` |
| 检查约束 `products_stock_check` | `CHECK ((stock >= 0))` |
| 主键 `products_pkey` | `PRIMARY KEY (id)` |
| 索引 `ix_products_status_sort` | `CREATE INDEX ix_products_status_sort ON products USING btree (status, sort_order)` |

## exchange_orders

积分兑换及核销结果，订单创建时间确定自然月。

| 字段 | PostgreSQL 类型 | 可空 | 默认值 |
|---|---|---|---|
| `id` | `uuid` | 否 | `gen_random_uuid()` |
| `order_no` | `character varying(40)` | 否 | — |
| `member_id` | `uuid` | 否 | — |
| `product_id` | `uuid` | 否 | — |
| `product_snapshot` | `jsonb` | 否 | — |
| `quantity` | `integer` | 否 | `1` |
| `points_cost_total` | `bigint` | 否 | — |
| `status` | `character varying(20)` | 否 | `'pending'::character varying` |
| `idempotency_key` | `character varying(128)` | 否 | — |
| `request_fingerprint` | `bytea` | 否 | — |
| `verified_by_account_id` | `uuid` | 是 | — |
| `verified_at` | `timestamp with time zone` | 是 | — |
| `created_at` | `timestamp with time zone` | 否 | — |
| `updated_at` | `timestamp with time zone` | 否 | `now()` |

| 约束或索引 | 定义 |
|---|---|
| 检查约束 `exchange_orders_check` | `CHECK (((((status)::text = 'pending'::text) AND (verified_at IS NULL) AND (verified_by_account_id IS NULL)) OR (((status)::text = 'verified'::text) AND (verified_at IS NOT NULL) AND (verified_by_account_id IS NOT NULL))))` |
| 检查约束 `exchange_orders_points_cost_total_check` | `CHECK ((points_cost_total > 0))` |
| 检查约束 `exchange_orders_quantity_check` | `CHECK ((quantity > 0))` |
| 检查约束 `exchange_orders_status_check` | `CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'verified'::character varying])::text[])))` |
| 外键 `exchange_orders_member_id_fkey` | `FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE RESTRICT` |
| 外键 `exchange_orders_product_id_fkey` | `FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT` |
| 外键 `exchange_orders_verified_by_account_id_fkey` | `FOREIGN KEY (verified_by_account_id) REFERENCES accounts(id) ON DELETE RESTRICT` |
| 主键 `exchange_orders_pkey` | `PRIMARY KEY (id)` |
| 唯一约束 `exchange_orders_member_id_idempotency_key_key` | `UNIQUE (member_id, idempotency_key)` |
| 唯一约束 `exchange_orders_order_no_key` | `UNIQUE (order_no)` |
| 索引 `ix_orders_member_created` | `CREATE INDEX ix_orders_member_created ON exchange_orders USING btree (member_id, created_at DESC)` |
| 索引 `ix_orders_member_product_created` | `CREATE INDEX ix_orders_member_product_created ON exchange_orders USING btree (member_id, product_id, created_at) INCLUDE (quantity, status)` |
| 索引 `ix_orders_status_created` | `CREATE INDEX ix_orders_status_created ON exchange_orders USING btree (status, created_at DESC)` |

## product_stock_records

不可变库存流水，记录初始入库、人工调整和兑换扣减。

| 字段 | PostgreSQL 类型 | 可空 | 默认值 |
|---|---|---|---|
| `id` | `uuid` | 否 | `gen_random_uuid()` |
| `product_id` | `uuid` | 否 | — |
| `exchange_order_id` | `uuid` | 是 | — |
| `operator_account_id` | `uuid` | 是 | — |
| `change_type` | `character varying(24)` | 否 | — |
| `quantity_delta` | `integer` | 否 | — |
| `stock_before` | `integer` | 否 | — |
| `stock_after` | `integer` | 否 | — |
| `idempotency_key` | `character varying(128)` | 否 | — |
| `request_fingerprint` | `bytea` | 否 | — |
| `reason` | `text` | 是 | — |
| `created_at` | `timestamp with time zone` | 否 | `now()` |

| 约束或索引 | 定义 |
|---|---|
| 检查约束 `product_stock_records_check` | `CHECK (((stock_after)::bigint = ((stock_before)::bigint + (quantity_delta)::bigint)))` |
| 检查约束 `product_stock_records_quantity_delta_check` | `CHECK ((quantity_delta <> 0))` |
| 检查约束 `product_stock_records_stock_after_check` | `CHECK ((stock_after >= 0))` |
| 检查约束 `product_stock_records_stock_before_check` | `CHECK ((stock_before >= 0))` |
| 外键 `product_stock_records_exchange_order_id_fkey` | `FOREIGN KEY (exchange_order_id) REFERENCES exchange_orders(id) ON DELETE RESTRICT` |
| 外键 `product_stock_records_operator_account_id_fkey` | `FOREIGN KEY (operator_account_id) REFERENCES accounts(id) ON DELETE RESTRICT` |
| 外键 `product_stock_records_product_id_fkey` | `FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT` |
| 主键 `product_stock_records_pkey` | `PRIMARY KEY (id)` |
| 唯一约束 `product_stock_records_exchange_order_id_key` | `UNIQUE (exchange_order_id)` |
| 唯一约束 `product_stock_records_idempotency_key_key` | `UNIQUE (idempotency_key)` |
| 索引 `ix_stock_product_created` | `CREATE INDEX ix_stock_product_created ON product_stock_records USING btree (product_id, created_at DESC)` |

## redemption_credentials

短时动态凭证，保存摘要和有效期，支持作废和一次性消费。

| 字段 | PostgreSQL 类型 | 可空 | 默认值 |
|---|---|---|---|
| `id` | `uuid` | 否 | `gen_random_uuid()` |
| `exchange_order_id` | `uuid` | 否 | — |
| `token_hash` | `bytea` | 否 | — |
| `issued_at` | `timestamp with time zone` | 否 | — |
| `expires_at` | `timestamp with time zone` | 否 | — |
| `revoked_at` | `timestamp with time zone` | 是 | — |
| `consumed_at` | `timestamp with time zone` | 是 | — |
| `consumed_by_account_id` | `uuid` | 是 | — |

| 约束或索引 | 定义 |
|---|---|
| 检查约束 `redemption_credentials_check` | `CHECK ((expires_at > issued_at))` |
| 检查约束 `redemption_credentials_check1` | `CHECK ((((consumed_at IS NULL) AND (consumed_by_account_id IS NULL)) OR ((consumed_at IS NOT NULL) AND (consumed_by_account_id IS NOT NULL) AND (revoked_at IS NULL) AND (consumed_at >= issued_at) AND (consumed_at < expires_at))))` |
| 外键 `redemption_credentials_consumed_by_account_id_fkey` | `FOREIGN KEY (consumed_by_account_id) REFERENCES accounts(id) ON DELETE RESTRICT` |
| 外键 `redemption_credentials_exchange_order_id_fkey` | `FOREIGN KEY (exchange_order_id) REFERENCES exchange_orders(id) ON DELETE RESTRICT` |
| 主键 `redemption_credentials_pkey` | `PRIMARY KEY (id)` |
| 唯一约束 `redemption_credentials_token_hash_key` | `UNIQUE (token_hash)` |
| 索引 `ix_credentials_order_issued` | `CREATE INDEX ix_credentials_order_issued ON redemption_credentials USING btree (exchange_order_id, issued_at DESC)` |
| 索引 `uq_credentials_consumed_order` | `CREATE UNIQUE INDEX uq_credentials_consumed_order ON redemption_credentials USING btree (exchange_order_id) WHERE (consumed_at IS NOT NULL)` |
| 索引 `uq_credentials_unclosed_order` | `CREATE UNIQUE INDEX uq_credentials_unclosed_order ON redemption_credentials USING btree (exchange_order_id) WHERE ((revoked_at IS NULL) AND (consumed_at IS NULL))` |

## system_configs

单门店资料与可写业务配置，业务时区由部署配置提供。

| 字段 | PostgreSQL 类型 | 可空 | 默认值 |
|---|---|---|---|
| `id` | `uuid` | 否 | `gen_random_uuid()` |
| `key` | `character varying(100)` | 否 | — |
| `value` | `jsonb` | 否 | — |
| `description` | `character varying(255)` | 是 | — |
| `updated_by_account_id` | `uuid` | 是 | — |
| `created_at` | `timestamp with time zone` | 否 | `now()` |
| `updated_at` | `timestamp with time zone` | 否 | `now()` |

| 约束或索引 | 定义 |
|---|---|
| 外键 `system_configs_updated_by_account_id_fkey` | `FOREIGN KEY (updated_by_account_id) REFERENCES accounts(id) ON DELETE RESTRICT` |
| 主键 `system_configs_pkey` | `PRIMARY KEY (id)` |
| 唯一约束 `system_configs_key_key` | `UNIQUE (key)` |

## operation_logs

脱敏审计日志，目标类型与 ID 用于逻辑关联。

| 字段 | PostgreSQL 类型 | 可空 | 默认值 |
|---|---|---|---|
| `id` | `uuid` | 否 | `gen_random_uuid()` |
| `actor_account_id` | `uuid` | 是 | — |
| `actor_role` | `character varying(20)` | 否 | — |
| `action` | `character varying(80)` | 否 | — |
| `module` | `character varying(40)` | 否 | — |
| `target_type` | `character varying(40)` | 是 | — |
| `target_id` | `uuid` | 是 | — |
| `summary` | `text` | 是 | — |
| `before_data` | `jsonb` | 是 | — |
| `after_data` | `jsonb` | 是 | — |
| `request_id` | `character varying(64)` | 是 | — |
| `created_at` | `timestamp with time zone` | 否 | `now()` |

| 约束或索引 | 定义 |
|---|---|
| 外键 `operation_logs_actor_account_id_fkey` | `FOREIGN KEY (actor_account_id) REFERENCES accounts(id) ON DELETE RESTRICT` |
| 主键 `operation_logs_pkey` | `PRIMARY KEY (id)` |
| 索引 `ix_logs_actor_created` | `CREATE INDEX ix_logs_actor_created ON operation_logs USING btree (actor_account_id, created_at DESC)` |
| 索引 `ix_logs_target_created` | `CREATE INDEX ix_logs_target_created ON operation_logs USING btree (target_type, target_id, created_at DESC)` |

## 流水写入权限

points_records_append_only 和 stock_records_append_only 触发器拒绝 UPDATE、DELETE 及 TRUNCATE。迁移角色拥有对象，应用角色仅查询和追加流水。跨表数量、成本、余额和核销一致性由事务服务校验。

## 幂等键与服务校验

订单、积分流水、库存流水的 `idempotency_key` 均为 `VARCHAR(128) NOT NULL`。订单按会员及键唯一，积分与库存流水各自按服务端派生键唯一。`request_fingerprint` 保存服务生成的 32 字节请求摘要，用于区分重放与同键冲突。常规枚举、分类条件及订单和流水的会员或商品匹配由 FastAPI 校验。见 [API 幂等键契约](../docs/api-spec.md#幂等键契约)和[数据库设计](../docs/database-schema.md)。

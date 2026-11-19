-- 阳光口腔 V1.0 PostgreSQL 16 设计评审基线（单门店，18 张表）。
-- 评审通过后以此建立 Alembic 迁移。该文件用于设计评审和隔离验证。
-- 常规枚举、状态流转、摘要格式与分类字段组合由应用服务校验。
CREATE TABLE accounts (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 wechat_openid VARCHAR(128) UNIQUE, wechat_unionid VARCHAR(128),
 username VARCHAR(64) UNIQUE, password_hash VARCHAR(255),
 status VARCHAR(20) NOT NULL DEFAULT 'active',
 last_login_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_accounts_unionid ON accounts(wechat_unionid);

CREATE TABLE staff_profiles (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 account_id UUID NOT NULL UNIQUE REFERENCES accounts(id) ON DELETE RESTRICT,
 employee_no VARCHAR(32) UNIQUE, display_name VARCHAR(80) NOT NULL,
 phone_ciphertext BYTEA, phone_search_hash BYTEA,
 role VARCHAR(20) NOT NULL,
 status VARCHAR(20) NOT NULL DEFAULT 'active',
 hired_at DATE, disabled_at TIMESTAMPTZ,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_staff_role_status ON staff_profiles(role,status);

CREATE TABLE members (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 account_id UUID NOT NULL UNIQUE REFERENCES accounts(id) ON DELETE RESTRICT,
 member_no VARCHAR(32) NOT NULL UNIQUE, name VARCHAR(80) NOT NULL, birthday DATE NOT NULL,
 phone_ciphertext BYTEA NOT NULL, phone_search_hash BYTEA NOT NULL,
 register_source VARCHAR(24) NOT NULL,
 source_employee_id UUID REFERENCES staff_profiles(id) ON DELETE RESTRICT,
 status VARCHAR(20) NOT NULL DEFAULT 'active',
 registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_members_status_created ON members(status,created_at DESC);
CREATE INDEX ix_members_phone_hash ON members(phone_search_hash);

CREATE TABLE employee_qr_tokens (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 staff_id UUID NOT NULL REFERENCES staff_profiles(id) ON DELETE RESTRICT,
 token_hash BYTEA NOT NULL UNIQUE, expires_at TIMESTAMPTZ NOT NULL,
 revoked_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_qr_staff_expiry ON employee_qr_tokens(staff_id,expires_at);

CREATE TABLE customer_assignments (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 member_id UUID NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
 staff_id UUID NOT NULL REFERENCES staff_profiles(id) ON DELETE RESTRICT,
 is_current BOOLEAN NOT NULL DEFAULT TRUE,
 bind_source VARCHAR(24) NOT NULL,
 started_at TIMESTAMPTZ NOT NULL DEFAULT now(), ended_at TIMESTAMPTZ,
 change_reason TEXT, operator_account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_assignment_current_member ON customer_assignments(member_id) WHERE is_current;
CREATE INDEX ix_assignment_staff_current ON customer_assignments(staff_id,is_current);

CREATE TABLE customer_status (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 member_id UUID NOT NULL UNIQUE REFERENCES members(id) ON DELETE RESTRICT,
 visit_status VARCHAR(20) NOT NULL DEFAULT 'not_visited',
 consume_status VARCHAR(20) NOT NULL DEFAULT 'not_consumed',
 deal_status VARCHAR(20) NOT NULL DEFAULT 'not_dealt',
 last_visit_at TIMESTAMPTZ, last_consume_at TIMESTAMPTZ, next_recall_at TIMESTAMPTZ,
 last_effective_contact_at TIMESTAMPTZ,
 updated_by_account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_customer_recall ON customer_status(next_recall_at) WHERE next_recall_at IS NOT NULL;

CREATE TABLE customer_tags (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name VARCHAR(40) NOT NULL UNIQUE,
 description VARCHAR(255), status VARCHAR(20) NOT NULL DEFAULT 'active',
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE member_tag_relations (
 member_id UUID NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
 tag_id UUID NOT NULL REFERENCES customer_tags(id) ON DELETE RESTRICT,
 created_by_account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY(member_id,tag_id)
);
CREATE INDEX ix_member_tag_tag ON member_tag_relations(tag_id);

CREATE TABLE points_accounts (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 member_id UUID NOT NULL UNIQUE REFERENCES members(id) ON DELETE RESTRICT,
 balance BIGINT NOT NULL DEFAULT 0 CHECK(balance >= 0),
 total_earned BIGINT NOT NULL DEFAULT 0,
 total_spent BIGINT NOT NULL DEFAULT 0,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE points_records (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 member_id UUID NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
 delta_points BIGINT NOT NULL CHECK(delta_points <> 0),
 balance_before BIGINT NOT NULL CHECK(balance_before >= 0),
 balance_after BIGINT NOT NULL CHECK(balance_after >= 0),
 record_type VARCHAR(24) NOT NULL,
 source_type VARCHAR(32) NOT NULL, exchange_order_id UUID UNIQUE,
 idempotency_key VARCHAR(128) NOT NULL UNIQUE,
 request_fingerprint BYTEA NOT NULL, reason TEXT,
 operator_account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 CHECK(balance_after = balance_before + delta_points)
);
CREATE INDEX ix_points_member_created ON points_records(member_id,created_at DESC);

CREATE TABLE followup_records (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 member_id UUID NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
 staff_id UUID NOT NULL REFERENCES staff_profiles(id) ON DELETE RESTRICT,
 contact_type VARCHAR(24) NOT NULL,
 followup_at TIMESTAMPTZ NOT NULL DEFAULT now(), content TEXT NOT NULL,
 customer_feedback TEXT, effective_contact BOOLEAN NOT NULL DEFAULT FALSE,
 gift_given BOOLEAN NOT NULL DEFAULT FALSE, gift_name VARCHAR(120),
 next_followup_at TIMESTAMPTZ,
 created_by_account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_followup_member_time ON followup_records(member_id,followup_at DESC);

CREATE TABLE followup_tasks (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 member_id UUID NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
 assigned_staff_id UUID REFERENCES staff_profiles(id) ON DELETE RESTRICT,
 task_type VARCHAR(24) NOT NULL,
 status VARCHAR(20) NOT NULL DEFAULT 'pending',
 title VARCHAR(120) NOT NULL, scheduled_at TIMESTAMPTZ NOT NULL, postponed_until TIMESTAMPTZ,
 dedupe_key VARCHAR(160) NOT NULL UNIQUE, result TEXT, completed_at TIMESTAMPTZ,
 created_by_account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_tasks_status_schedule ON followup_tasks(status,scheduled_at);
CREATE INDEX ix_tasks_staff_status ON followup_tasks(assigned_staff_id,status);

CREATE TABLE products (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name VARCHAR(120) NOT NULL, category VARCHAR(40),
 cover_image_key VARCHAR(500), image_keys JSONB NOT NULL DEFAULT '[]'::jsonb, description TEXT,
 points_price BIGINT NOT NULL CHECK(points_price > 0), stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
 per_user_monthly_limit INTEGER CHECK(per_user_monthly_limit > 0),
 status VARCHAR(20) NOT NULL DEFAULT 'draft',
 sort_order INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 1,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_products_status_sort ON products(status,sort_order);

CREATE TABLE exchange_orders (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), order_no VARCHAR(40) NOT NULL UNIQUE,
 member_id UUID NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
 product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
 product_snapshot JSONB NOT NULL, quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity > 0),
 points_cost_total BIGINT NOT NULL CHECK(points_cost_total > 0),
 status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','verified')),
 idempotency_key VARCHAR(128) NOT NULL,
 request_fingerprint BYTEA NOT NULL,
 verified_by_account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT,
 verified_at TIMESTAMPTZ,
 created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(member_id,idempotency_key),
 CHECK ((status = 'pending' AND verified_at IS NULL AND verified_by_account_id IS NULL)
     OR (status = 'verified' AND verified_at IS NOT NULL AND verified_by_account_id IS NOT NULL))
);
CREATE INDEX ix_orders_member_created ON exchange_orders(member_id,created_at DESC);
CREATE INDEX ix_orders_status_created ON exchange_orders(status,created_at DESC);
-- 等值前缀（会员、商品）与范围列（订单创建时间）匹配月限兑查询。
CREATE INDEX ix_orders_member_product_created
 ON exchange_orders(member_id,product_id,created_at) INCLUDE (quantity,status);

ALTER TABLE points_records ADD CONSTRAINT fk_points_exchange_order
 FOREIGN KEY (exchange_order_id) REFERENCES exchange_orders(id) ON DELETE RESTRICT;

CREATE TABLE product_stock_records (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
 exchange_order_id UUID UNIQUE REFERENCES exchange_orders(id) ON DELETE RESTRICT,
 operator_account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT,
 change_type VARCHAR(24) NOT NULL,
 quantity_delta INTEGER NOT NULL CHECK(quantity_delta <> 0),
 stock_before INTEGER NOT NULL CHECK(stock_before >= 0),
 stock_after INTEGER NOT NULL CHECK(stock_after >= 0),
 idempotency_key VARCHAR(128) NOT NULL UNIQUE,
 request_fingerprint BYTEA NOT NULL,
 reason TEXT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 CHECK (stock_after::BIGINT = stock_before::BIGINT + quantity_delta::BIGINT)
);
CREATE INDEX ix_stock_product_created ON product_stock_records(product_id,created_at DESC);

CREATE TABLE redemption_credentials (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 exchange_order_id UUID NOT NULL REFERENCES exchange_orders(id) ON DELETE RESTRICT,
 token_hash BYTEA NOT NULL UNIQUE,
 issued_at TIMESTAMPTZ NOT NULL,
 expires_at TIMESTAMPTZ NOT NULL,
 revoked_at TIMESTAMPTZ,
 consumed_at TIMESTAMPTZ,
 consumed_by_account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT,
 CHECK (expires_at > issued_at),
 CHECK ((consumed_at IS NULL AND consumed_by_account_id IS NULL)
     OR (consumed_at IS NOT NULL AND consumed_by_account_id IS NOT NULL AND revoked_at IS NULL
         AND consumed_at >= issued_at AND consumed_at < expires_at))
);
CREATE UNIQUE INDEX uq_credentials_unclosed_order ON redemption_credentials(exchange_order_id)
 WHERE revoked_at IS NULL AND consumed_at IS NULL;
CREATE UNIQUE INDEX uq_credentials_consumed_order ON redemption_credentials(exchange_order_id)
 WHERE consumed_at IS NOT NULL;
CREATE INDEX ix_credentials_order_issued ON redemption_credentials(exchange_order_id,issued_at DESC);

CREATE TABLE system_configs (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), key VARCHAR(100) NOT NULL UNIQUE,
 value JSONB NOT NULL, description VARCHAR(255),
 updated_by_account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE operation_logs (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 actor_account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT,
 actor_role VARCHAR(20) NOT NULL,
 action VARCHAR(80) NOT NULL, module VARCHAR(40) NOT NULL,
 target_type VARCHAR(40), target_id UUID, summary TEXT, before_data JSONB, after_data JSONB,
 request_id VARCHAR(64), created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_logs_target_created ON operation_logs(target_type,target_id,created_at DESC);
CREATE INDEX ix_logs_actor_created ON operation_logs(actor_account_id,created_at DESC);

-- 部署时把 SELECT / INSERT 单独授予应用角色，表所有权归迁移角色。
CREATE FUNCTION reject_ledger_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 RAISE EXCEPTION 'Ledger % is append-only', TG_TABLE_NAME USING ERRCODE = '55000';
END;
$$;
CREATE TRIGGER points_records_append_only BEFORE UPDATE OR DELETE OR TRUNCATE ON points_records
 FOR EACH STATEMENT EXECUTE FUNCTION reject_ledger_mutation();
CREATE TRIGGER stock_records_append_only BEFORE UPDATE OR DELETE OR TRUNCATE ON product_stock_records
 FOR EACH STATEMENT EXECUTE FUNCTION reject_ledger_mutation();

"""SQLAlchemy mappings for the accepted V1.0 PostgreSQL schema."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("username", name="accounts_username_key"),
        UniqueConstraint("wechat_openid", name="accounts_wechat_openid_key"),
        Index("ix_accounts_unionid", "wechat_unionid"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    wechat_openid: Mapped[str | None] = mapped_column(String(128))
    wechat_unionid: Mapped[str | None] = mapped_column(String(128))
    username: Mapped[str | None] = mapped_column(String(64))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), server_default=text("'active'::character varying"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class StaffProfile(Base):
    __tablename__ = "staff_profiles"
    __table_args__ = (
        UniqueConstraint("account_id", name="staff_profiles_account_id_key"),
        UniqueConstraint("employee_no", name="staff_profiles_employee_no_key"),
        Index("ix_staff_role_status", "role", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    account_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("accounts.id", name="staff_profiles_account_id_fkey", ondelete="RESTRICT"),
    )
    employee_no: Mapped[str | None] = mapped_column(String(32))
    display_name: Mapped[str] = mapped_column(String(80))
    phone_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    phone_search_hash: Mapped[bytes | None] = mapped_column(LargeBinary)
    role: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), server_default=text("'active'::character varying"))
    hired_at: Mapped[date | None] = mapped_column(Date)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Member(Base):
    __tablename__ = "members"
    __table_args__ = (
        UniqueConstraint("account_id", name="members_account_id_key"),
        UniqueConstraint("member_no", name="members_member_no_key"),
        Index("ix_members_phone_hash", "phone_search_hash"),
        Index("ix_members_status_created", "status", text("created_at DESC")),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    account_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("accounts.id", name="members_account_id_fkey", ondelete="RESTRICT"),
    )
    member_no: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(80))
    birthday: Mapped[date] = mapped_column(Date)
    phone_ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    phone_search_hash: Mapped[bytes] = mapped_column(LargeBinary)
    register_source: Mapped[str] = mapped_column(String(24))
    source_employee_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("staff_profiles.id", name="members_source_employee_id_fkey", ondelete="RESTRICT"),
    )
    status: Mapped[str] = mapped_column(String(20), server_default=text("'active'::character varying"))
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class EmployeeQrToken(Base):
    __tablename__ = "employee_qr_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="employee_qr_tokens_token_hash_key"),
        Index("ix_qr_staff_expiry", "staff_id", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    staff_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("staff_profiles.id", name="employee_qr_tokens_staff_id_fkey", ondelete="RESTRICT"),
    )
    token_hash: Mapped[bytes] = mapped_column(LargeBinary)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class CustomerAssignment(Base):
    __tablename__ = "customer_assignments"
    __table_args__ = (
        Index("ix_assignment_staff_current", "staff_id", "is_current"),
        Index(
            "uq_assignment_current_member",
            "member_id",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    member_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("members.id", name="customer_assignments_member_id_fkey", ondelete="RESTRICT"),
    )
    staff_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("staff_profiles.id", name="customer_assignments_staff_id_fkey", ondelete="RESTRICT"),
    )
    is_current: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    bind_source: Mapped[str] = mapped_column(String(24))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    change_reason: Mapped[str | None] = mapped_column(Text)
    operator_account_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("accounts.id", name="customer_assignments_operator_account_id_fkey", ondelete="RESTRICT"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class CustomerStatus(Base):
    __tablename__ = "customer_status"
    __table_args__ = (
        UniqueConstraint("member_id", name="customer_status_member_id_key"),
        Index(
            "ix_customer_recall",
            "next_recall_at",
            postgresql_where=text("(next_recall_at IS NOT NULL)"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    member_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("members.id", name="customer_status_member_id_fkey", ondelete="RESTRICT"),
    )
    visit_status: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'not_visited'::character varying"),
    )
    consume_status: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'not_consumed'::character varying"),
    )
    deal_status: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'not_dealt'::character varying"),
    )
    last_visit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_consume_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_recall_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_effective_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by_account_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("accounts.id", name="customer_status_updated_by_account_id_fkey", ondelete="RESTRICT"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class CustomerTag(Base):
    __tablename__ = "customer_tags"
    __table_args__ = (
        UniqueConstraint("name", name="customer_tags_name_key"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(String(40))
    description: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), server_default=text("'active'::character varying"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class MemberTagRelation(Base):
    __tablename__ = "member_tag_relations"
    __table_args__ = (
        Index("ix_member_tag_tag", "tag_id"),
    )

    member_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("members.id", name="member_tag_relations_member_id_fkey", ondelete="RESTRICT"),
        primary_key=True,
    )
    tag_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("customer_tags.id", name="member_tag_relations_tag_id_fkey", ondelete="RESTRICT"),
        primary_key=True,
    )
    created_by_account_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("accounts.id", name="member_tag_relations_created_by_account_id_fkey", ondelete="RESTRICT"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class PointsAccount(Base):
    __tablename__ = "points_accounts"
    __table_args__ = (
        CheckConstraint("((balance >= 0))", name="points_accounts_balance_check"),
        UniqueConstraint("member_id", name="points_accounts_member_id_key"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    member_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("members.id", name="points_accounts_member_id_fkey", ondelete="RESTRICT"),
    )
    balance: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    total_earned: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    total_spent: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class PointsRecord(Base):
    __tablename__ = "points_records"
    __table_args__ = (
        CheckConstraint("((balance_after >= 0))", name="points_records_balance_after_check"),
        CheckConstraint("((balance_before >= 0))", name="points_records_balance_before_check"),
        CheckConstraint("((balance_after = (balance_before + delta_points)))", name="points_records_check"),
        CheckConstraint("((delta_points <> 0))", name="points_records_delta_points_check"),
        UniqueConstraint("exchange_order_id", name="points_records_exchange_order_id_key"),
        UniqueConstraint("idempotency_key", name="points_records_idempotency_key_key"),
        Index("ix_points_member_created", "member_id", text("created_at DESC")),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    member_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("members.id", name="points_records_member_id_fkey", ondelete="RESTRICT"),
    )
    delta_points: Mapped[int] = mapped_column(BigInteger)
    balance_before: Mapped[int] = mapped_column(BigInteger)
    balance_after: Mapped[int] = mapped_column(BigInteger)
    record_type: Mapped[str] = mapped_column(String(24))
    source_type: Mapped[str] = mapped_column(String(32))
    exchange_order_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("exchange_orders.id", name="fk_points_exchange_order", ondelete="RESTRICT"),
    )
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_fingerprint: Mapped[bytes] = mapped_column(LargeBinary)
    reason: Mapped[str | None] = mapped_column(Text)
    operator_account_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("accounts.id", name="points_records_operator_account_id_fkey", ondelete="RESTRICT"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class FollowupRecord(Base):
    __tablename__ = "followup_records"
    __table_args__ = (
        Index("ix_followup_member_time", "member_id", text("followup_at DESC")),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    member_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("members.id", name="followup_records_member_id_fkey", ondelete="RESTRICT"),
    )
    staff_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("staff_profiles.id", name="followup_records_staff_id_fkey", ondelete="RESTRICT"),
    )
    contact_type: Mapped[str] = mapped_column(String(24))
    followup_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    content: Mapped[str] = mapped_column(Text)
    customer_feedback: Mapped[str | None] = mapped_column(Text)
    effective_contact: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    gift_given: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    gift_name: Mapped[str | None] = mapped_column(String(120))
    next_followup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_account_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("accounts.id", name="followup_records_created_by_account_id_fkey", ondelete="RESTRICT"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class FollowupTask(Base):
    __tablename__ = "followup_tasks"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="followup_tasks_dedupe_key_key"),
        Index("ix_tasks_staff_status", "assigned_staff_id", "status"),
        Index("ix_tasks_status_schedule", "status", "scheduled_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    member_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("members.id", name="followup_tasks_member_id_fkey", ondelete="RESTRICT"),
    )
    assigned_staff_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("staff_profiles.id", name="followup_tasks_assigned_staff_id_fkey", ondelete="RESTRICT"),
    )
    task_type: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(20), server_default=text("'pending'::character varying"))
    title: Mapped[str] = mapped_column(String(120))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    postponed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dedupe_key: Mapped[str] = mapped_column(String(160))
    result: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_account_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("accounts.id", name="followup_tasks_created_by_account_id_fkey", ondelete="RESTRICT"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("((per_user_monthly_limit > 0))", name="products_per_user_monthly_limit_check"),
        CheckConstraint("((points_price > 0))", name="products_points_price_check"),
        CheckConstraint("((stock >= 0))", name="products_stock_check"),
        Index("ix_products_status_sort", "status", "sort_order"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str | None] = mapped_column(String(40))
    cover_image_key: Mapped[str | None] = mapped_column(String(500))
    image_keys: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    description: Mapped[str | None] = mapped_column(Text)
    points_price: Mapped[int] = mapped_column(BigInteger)
    stock: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    per_user_monthly_limit: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'draft'::character varying"))
    sort_order: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class ExchangeOrder(Base):
    __tablename__ = "exchange_orders"
    __table_args__ = (
        CheckConstraint(
            "(status = 'pending' AND verified_at IS NULL AND verified_by_account_id IS NULL) "
            "OR (status = 'verified' AND verified_at IS NOT NULL AND verified_by_account_id IS NOT NULL)",
            name="exchange_orders_check",
        ),
        CheckConstraint("((points_cost_total > 0))", name="exchange_orders_points_cost_total_check"),
        CheckConstraint("((quantity > 0))", name="exchange_orders_quantity_check"),
        CheckConstraint(
            "status IN ('pending','verified')",
            name="exchange_orders_status_check",
        ),
        UniqueConstraint("member_id", "idempotency_key", name="exchange_orders_member_id_idempotency_key_key"),
        UniqueConstraint("order_no", name="exchange_orders_order_no_key"),
        Index("ix_orders_member_created", "member_id", text("created_at DESC")),
        Index(
            "ix_orders_member_product_created",
            "member_id",
            "product_id",
            "created_at",
            postgresql_include=["quantity", "status"],
        ),
        Index("ix_orders_status_created", "status", text("created_at DESC")),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    order_no: Mapped[str] = mapped_column(String(40))
    member_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("members.id", name="exchange_orders_member_id_fkey", ondelete="RESTRICT"),
    )
    product_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("products.id", name="exchange_orders_product_id_fkey", ondelete="RESTRICT"),
    )
    product_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    quantity: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    points_cost_total: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'pending'::character varying"))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_fingerprint: Mapped[bytes] = mapped_column(LargeBinary)
    verified_by_account_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("accounts.id", name="exchange_orders_verified_by_account_id_fkey", ondelete="RESTRICT"),
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class ProductStockRecord(Base):
    __tablename__ = "product_stock_records"
    __table_args__ = (
        CheckConstraint(
            "stock_after::BIGINT = stock_before::BIGINT + quantity_delta::BIGINT",
            name="product_stock_records_check",
        ),
        CheckConstraint("((quantity_delta <> 0))", name="product_stock_records_quantity_delta_check"),
        CheckConstraint("((stock_after >= 0))", name="product_stock_records_stock_after_check"),
        CheckConstraint("((stock_before >= 0))", name="product_stock_records_stock_before_check"),
        UniqueConstraint("exchange_order_id", name="product_stock_records_exchange_order_id_key"),
        UniqueConstraint("idempotency_key", name="product_stock_records_idempotency_key_key"),
        Index("ix_stock_product_created", "product_id", text("created_at DESC")),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    product_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("products.id", name="product_stock_records_product_id_fkey", ondelete="RESTRICT"),
    )
    exchange_order_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("exchange_orders.id", name="product_stock_records_exchange_order_id_fkey", ondelete="RESTRICT"),
    )
    operator_account_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("accounts.id", name="product_stock_records_operator_account_id_fkey", ondelete="RESTRICT"),
    )
    change_type: Mapped[str] = mapped_column(String(24))
    quantity_delta: Mapped[int] = mapped_column(Integer)
    stock_before: Mapped[int] = mapped_column(Integer)
    stock_after: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_fingerprint: Mapped[bytes] = mapped_column(LargeBinary)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class RedemptionCredential(Base):
    __tablename__ = "redemption_credentials"
    __table_args__ = (
        CheckConstraint("((expires_at > issued_at))", name="redemption_credentials_check"),
        CheckConstraint(
            "((((consumed_at IS NULL) AND (consumed_by_account_id IS NULL)) OR "
            "((consumed_at IS NOT NULL) AND (consumed_by_account_id IS NOT NULL) AND "
            "(revoked_at IS NULL) AND (consumed_at >= issued_at) AND (consumed_at < "
            "expires_at))))",
            name="redemption_credentials_check1",
        ),
        UniqueConstraint("token_hash", name="redemption_credentials_token_hash_key"),
        Index("ix_credentials_order_issued", "exchange_order_id", text("issued_at DESC")),
        Index(
            "uq_credentials_consumed_order",
            "exchange_order_id",
            unique=True,
            postgresql_where=text("(consumed_at IS NOT NULL)"),
        ),
        Index(
            "uq_credentials_unclosed_order",
            "exchange_order_id",
            unique=True,
            postgresql_where=text("((revoked_at IS NULL) AND (consumed_at IS NULL))"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    exchange_order_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("exchange_orders.id", name="redemption_credentials_exchange_order_id_fkey", ondelete="RESTRICT"),
    )
    token_hash: Mapped[bytes] = mapped_column(LargeBinary)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_by_account_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("accounts.id", name="redemption_credentials_consumed_by_account_id_fkey", ondelete="RESTRICT"),
    )


class SystemConfig(Base):
    __tablename__ = "system_configs"
    __table_args__ = (
        UniqueConstraint("key", name="system_configs_key_key"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    key: Mapped[str] = mapped_column(String(100))
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    updated_by_account_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("accounts.id", name="system_configs_updated_by_account_id_fkey", ondelete="RESTRICT"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class OperationLog(Base):
    __tablename__ = "operation_logs"
    __table_args__ = (
        Index("ix_logs_actor_created", "actor_account_id", text("created_at DESC")),
        Index("ix_logs_target_created", "target_type", "target_id", text("created_at DESC")),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    actor_account_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("accounts.id", name="operation_logs_actor_account_id_fkey", ondelete="RESTRICT"),
    )
    actor_role: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(80))
    module: Mapped[str] = mapped_column(String(40))
    target_type: Mapped[str | None] = mapped_column(String(40))
    target_id: Mapped[UUID | None] = mapped_column(Uuid)
    summary: Mapped[str | None] = mapped_column(Text)
    before_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

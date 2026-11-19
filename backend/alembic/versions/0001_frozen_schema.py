"""Install the accepted Sunshine Dental V1.0 schema."""

from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0001_frozen_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This revision owns an immutable snapshot, independent of ORM and design edits.
    ddl = Path(__file__).with_suffix(".sql").read_text(encoding="utf-8")
    if op.get_context().as_sql:
        op.execute(text(ddl.rstrip().removesuffix(";")))
    else:
        op.get_bind().exec_driver_sql(ddl, execution_options={"no_parameters": True})


def downgrade() -> None:
    # Dropping a table also removes its indexes, constraints and triggers.
    # Drop points_records before exchange_orders because of its late-bound FK.
    for table in (
        "operation_logs",
        "system_configs",
        "redemption_credentials",
        "product_stock_records",
        "points_records",
        "exchange_orders",
        "products",
        "followup_tasks",
        "followup_records",
        "points_accounts",
        "member_tag_relations",
        "customer_tags",
        "customer_status",
        "customer_assignments",
        "employee_qr_tokens",
        "members",
        "staff_profiles",
        "accounts",
    ):
        op.drop_table(table)
    op.execute("DROP FUNCTION reject_ledger_mutation()")

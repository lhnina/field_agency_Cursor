"""PR4 MVP gaps: zones, budgets, campaigns, audit, notifications, period lock fields, export ack

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("billing_periods", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("billing_periods", sa.Column("closed_by_user_id", sa.UUID(), nullable=True))
    op.add_column("billing_periods", sa.Column("reopen_reason", sa.String(length=255), nullable=True))
    op.create_foreign_key(
        "fk_billing_periods_closed_by",
        "billing_periods",
        "users",
        ["closed_by_user_id"],
        ["id"],
    )

    op.add_column("payroll_periods", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payroll_periods", sa.Column("closed_by_user_id", sa.UUID(), nullable=True))
    op.add_column("payroll_periods", sa.Column("reopen_reason", sa.String(length=255), nullable=True))
    op.create_foreign_key(
        "fk_payroll_periods_closed_by",
        "payroll_periods",
        "users",
        ["closed_by_user_id"],
        ["id"],
    )

    op.add_column("erp_export_batches", sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("erp_export_batches", sa.Column("ack_reference", sa.String(length=120), nullable=True))
    op.add_column("erp_export_batches", sa.Column("acked_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "zones",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code"),
    )
    op.create_index("ix_zones_organization_id", "zones", ["organization_id"])

    op.create_table(
        "budgets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=True),
        sa.Column("number", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("contract_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("lines", sa.JSON(), nullable=True),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("resulting_contract_id", sa.UUID(), nullable=True),
        sa.Column("resulting_campaign_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["resulting_contract_id"], ["contracts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_budgets_organization_id", "budgets", ["organization_id"])
    op.create_index("ix_budgets_client_id", "budgets", ["client_id"])

    op.create_table(
        "campaigns",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=True),
        sa.Column("contract_id", sa.UUID(), nullable=True),
        sa.Column("budget_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["budget_id"], ["budgets.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_campaigns_organization_id", "campaigns", ["organization_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_organization_id", "audit_logs", ["organization_id"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.String(length=500), nullable=False),
        sa.Column("read", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_organization_id", "notifications", ["organization_id"])
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])

    op.create_table(
        "email_outbox",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("to_address", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("related_kind", sa.String(length=32), nullable=True),
        sa.Column("related_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_outbox_organization_id", "email_outbox", ["organization_id"])


def downgrade() -> None:
    op.drop_table("email_outbox")
    op.drop_table("notifications")
    op.drop_table("audit_logs")
    op.drop_table("campaigns")
    op.drop_table("budgets")
    op.drop_table("zones")
    op.drop_column("erp_export_batches", "acked_at")
    op.drop_column("erp_export_batches", "ack_reference")
    op.drop_column("erp_export_batches", "retry_count")
    op.drop_constraint("fk_payroll_periods_closed_by", "payroll_periods", type_="foreignkey")
    op.drop_column("payroll_periods", "reopen_reason")
    op.drop_column("payroll_periods", "closed_by_user_id")
    op.drop_column("payroll_periods", "closed_at")
    op.drop_constraint("fk_billing_periods_closed_by", "billing_periods", type_="foreignkey")
    op.drop_column("billing_periods", "reopen_reason")
    op.drop_column("billing_periods", "closed_by_user_id")
    op.drop_column("billing_periods", "closed_at")

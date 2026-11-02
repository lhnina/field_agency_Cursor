"""billing, payroll, costs, export batches, time entry validation fields

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("rv_hourly_rate", sa.Numeric(10, 2), nullable=True))
    op.add_column("time_entries", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("time_entries", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("time_entries", sa.Column("auto_approved", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("time_entries", sa.Column("allow_extra_billable", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("time_entries", sa.Column("adjustment_note", sa.String(length=255), nullable=True))
    op.add_column("time_entries", sa.Column("tacit_accepted", sa.Boolean(), server_default="false", nullable=False))

    op.create_table(
        "billing_periods",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("service_area", sa.String(length=32), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "year", "month", "service_area"),
    )
    op.create_index("ix_billing_periods_organization_id", "billing_periods", ["organization_id"])

    op.create_table(
        "billing_drafts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("period_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("contract_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("total_net", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_vat", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_gross", sa.Numeric(12, 2), nullable=False),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("cost_center", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["period_id"], ["billing_periods.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_billing_drafts_organization_id", "billing_drafts", ["organization_id"])
    op.create_index("ix_billing_drafts_period_id", "billing_drafts", ["period_id"])
    op.create_index("ix_billing_drafts_client_id", "billing_drafts", ["client_id"])

    op.create_table(
        "billing_draft_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("draft_id", sa.UUID(), nullable=False),
        sa.Column("contract_line_id", sa.UUID(), nullable=True),
        sa.Column("article_code", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_net", sa.Numeric(12, 2), nullable=False),
        sa.Column("billing_model", sa.String(length=32), nullable=False),
        sa.Column("capped", sa.Boolean(), nullable=False),
        sa.Column("extra_override", sa.Boolean(), nullable=False),
        sa.Column("extra_reason", sa.String(length=255), nullable=True),
        sa.Column("cost_center", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["contract_line_id"], ["contract_lines.id"]),
        sa.ForeignKeyConstraint(["draft_id"], ["billing_drafts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_billing_draft_lines_organization_id", "billing_draft_lines", ["organization_id"])
    op.create_index("ix_billing_draft_lines_draft_id", "billing_draft_lines", ["draft_id"])

    op.create_table(
        "cost_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("contract_id", sa.UUID(), nullable=False),
        sa.Column("contract_line_id", sa.UUID(), nullable=True),
        sa.Column("cost_type", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=True),
        sa.Column("period_month", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"]),
        sa.ForeignKeyConstraint(["contract_line_id"], ["contract_lines.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cost_entries_organization_id", "cost_entries", ["organization_id"])
    op.create_index("ix_cost_entries_contract_id", "cost_entries", ["contract_id"])

    op.create_table(
        "payroll_periods",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "year", "month"),
    )
    op.create_index("ix_payroll_periods_organization_id", "payroll_periods", ["organization_id"])

    op.create_table(
        "payroll_statements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("period_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=True),
        sa.Column("client_name", sa.String(length=200), nullable=False),
        sa.Column("hours", sa.Numeric(12, 2), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("engagement_type", sa.String(length=16), nullable=False),
        sa.Column("hourly_rate", sa.Numeric(10, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["period_id"], ["payroll_periods.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payroll_statements_organization_id", "payroll_statements", ["organization_id"])
    op.create_index("ix_payroll_statements_period_id", "payroll_statements", ["period_id"])
    op.create_index("ix_payroll_statements_employee_id", "payroll_statements", ["employee_id"])

    op.create_table(
        "erp_export_batches",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("batch_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("period_label", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=255), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_erp_export_batches_organization_id", "erp_export_batches", ["organization_id"])


def downgrade() -> None:
    op.drop_table("erp_export_batches")
    op.drop_table("payroll_statements")
    op.drop_table("payroll_periods")
    op.drop_table("cost_entries")
    op.drop_table("billing_draft_lines")
    op.drop_table("billing_drafts")
    op.drop_table("billing_periods")
    op.drop_column("time_entries", "tacit_accepted")
    op.drop_column("time_entries", "adjustment_note")
    op.drop_column("time_entries", "allow_extra_billable")
    op.drop_column("time_entries", "auto_approved")
    op.drop_column("time_entries", "approved_at")
    op.drop_column("time_entries", "submitted_at")
    op.drop_column("employees", "rv_hourly_rate")

"""Align audit_reports and pr_reviews schema with SQLAlchemy models

Revision ID: 002_align_schema
Revises: 001_initial_schema
Create Date: 2026-09-29 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_align_schema'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. Update pr_reviews table
    pr_cols = [c["name"] for c in inspector.get_columns("pr_reviews")]

    if "verdict" not in pr_cols:
        op.add_column(
            "pr_reviews",
            sa.Column("verdict", sa.String(length=32), nullable=True, server_default="COMMENT")
        )
        op.execute("UPDATE pr_reviews SET verdict = 'COMMENT' WHERE verdict IS NULL")

    pr_indexes = [idx["name"] for idx in inspector.get_indexes("pr_reviews")]
    if "ix_pr_reviews_verdict" not in pr_indexes:
        op.create_index("ix_pr_reviews_verdict", "pr_reviews", ["verdict"], unique=False)

    if "risks_count" not in pr_cols:
        op.add_column(
            "pr_reviews",
            sa.Column("risks_count", sa.Integer(), nullable=True, server_default="0")
        )
        op.execute("UPDATE pr_reviews SET risks_count = 0 WHERE risks_count IS NULL")

    # 2. Update audit_reports table
    audit_cols = [c["name"] for c in inspector.get_columns("audit_reports")]

    if "total_opportunities" not in audit_cols:
        op.add_column(
            "audit_reports",
            sa.Column("total_opportunities", sa.Integer(), nullable=True, server_default="0")
        )
        if "opportunities_count" in audit_cols:
            op.execute(
                "UPDATE audit_reports SET total_opportunities = COALESCE(opportunities_count, 0) "
                "WHERE total_opportunities IS NULL OR total_opportunities = 0"
            )
        else:
            op.execute("UPDATE audit_reports SET total_opportunities = 0 WHERE total_opportunities IS NULL")

    if "critical_count" not in audit_cols:
        op.add_column(
            "audit_reports",
            sa.Column("critical_count", sa.Integer(), nullable=True, server_default="0")
        )
        op.execute("UPDATE audit_reports SET critical_count = 0 WHERE critical_count IS NULL")

    if "high_count" not in audit_cols:
        op.add_column(
            "audit_reports",
            sa.Column("high_count", sa.Integer(), nullable=True, server_default="0")
        )
        op.execute("UPDATE audit_reports SET high_count = 0 WHERE high_count IS NULL")

    if "medium_count" not in audit_cols:
        op.add_column(
            "audit_reports",
            sa.Column("medium_count", sa.Integer(), nullable=True, server_default="0")
        )
        op.execute("UPDATE audit_reports SET medium_count = 0 WHERE medium_count IS NULL")

    if "low_count" not in audit_cols:
        op.add_column(
            "audit_reports",
            sa.Column("low_count", sa.Integer(), nullable=True, server_default="0")
        )
        op.execute("UPDATE audit_reports SET low_count = 0 WHERE low_count IS NULL")

    if "summary_narrative" not in audit_cols:
        op.add_column(
            "audit_reports",
            sa.Column("summary_narrative", sa.Text(), nullable=True)
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Revert audit_reports columns
    audit_cols = [c["name"] for c in inspector.get_columns("audit_reports")]
    for col in [
        "summary_narrative",
        "low_count",
        "medium_count",
        "high_count",
        "critical_count",
        "total_opportunities"
    ]:
        if col in audit_cols:
            op.drop_column("audit_reports", col)

    # Revert pr_reviews columns and index
    pr_indexes = [idx["name"] for idx in inspector.get_indexes("pr_reviews")]
    if "ix_pr_reviews_verdict" in pr_indexes:
        op.drop_index("ix_pr_reviews_verdict", table_name="pr_reviews")

    pr_cols = [c["name"] for c in inspector.get_columns("pr_reviews")]
    for col in ["risks_count", "verdict"]:
        if col in pr_cols:
            op.drop_column("pr_reviews", col)

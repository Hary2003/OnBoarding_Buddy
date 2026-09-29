"""Initial baseline schema

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-09-28 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # 1. repositories table
    if "repositories" not in existing_tables:
        op.create_table(
            "repositories",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("session_id", sa.String(length=128), nullable=False),
            sa.Column("repo_name", sa.String(length=255), nullable=False),
            sa.Column("repo_path", sa.Text(), nullable=False),
            sa.Column("total_files", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("total_lines", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("languages", sa.JSON(), nullable=True),
            sa.Column("entry_points", sa.JSON(), nullable=True),
            sa.Column("module_counts", sa.JSON(), nullable=True),
            sa.Column("circular_cycles", sa.JSON(), nullable=True),
            sa.Column("architecture_summary", sa.JSON(), nullable=True),
            sa.Column("files_data", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.PrimaryKeyConstraint("id")
        )
        op.create_index("ix_repositories_session_id", "repositories", ["session_id"], unique=True)
        op.create_index("ix_repositories_repo_name", "repositories", ["repo_name"], unique=False)
        op.create_index("ix_repositories_created_at", "repositories", ["created_at"], unique=False)
        op.create_index("ix_repositories_updated_at", "repositories", ["updated_at"], unique=False)
        op.create_index("ix_repositories_session_updated", "repositories", ["session_id", "updated_at"], unique=False)

    # 2. conversation_turns table
    if "conversation_turns" not in existing_tables:
        op.create_table(
            "conversation_turns",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("session_id", sa.String(length=128), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("attributions", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.PrimaryKeyConstraint("id")
        )
        op.create_index("ix_conversation_turns_session_id", "conversation_turns", ["session_id"], unique=False)
        op.create_index("ix_conversation_turns_role", "conversation_turns", ["role"], unique=False)
        op.create_index("ix_conversation_turns_created_at", "conversation_turns", ["created_at"], unique=False)
        op.create_index("ix_turns_session_created", "conversation_turns", ["session_id", "created_at"], unique=False)

    # 3. pr_reviews table (baseline schema)
    if "pr_reviews" not in existing_tables:
        op.create_table(
            "pr_reviews",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("session_id", sa.String(length=128), nullable=False),
            sa.Column("title", sa.String(length=500), nullable=True),
            sa.Column("risk_level", sa.String(length=32), nullable=True),
            sa.Column("executive_summary", sa.Text(), nullable=True),
            sa.Column("developer_summary", sa.Text(), nullable=True),
            sa.Column("security_findings", sa.JSON(), nullable=True),
            sa.Column("full_analysis", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.PrimaryKeyConstraint("id")
        )
        op.create_index("ix_pr_reviews_session_id", "pr_reviews", ["session_id"], unique=False)
        op.create_index("ix_pr_reviews_created_at", "pr_reviews", ["created_at"], unique=False)
        op.create_index("ix_pr_reviews_risk_level", "pr_reviews", ["risk_level"], unique=False)

    # 4. audit_reports table (baseline schema)
    if "audit_reports" not in existing_tables:
        op.create_table(
            "audit_reports",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("session_id", sa.String(length=128), nullable=False),
            sa.Column("repo_name", sa.String(length=255), nullable=False),
            sa.Column("overall_score", sa.Float(), nullable=True),
            sa.Column("health_grade", sa.String(length=16), nullable=True),
            sa.Column("opportunities_count", sa.Integer(), nullable=True),
            sa.Column("report_data", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.PrimaryKeyConstraint("id")
        )
        op.create_index("ix_audit_reports_session_id", "audit_reports", ["session_id"], unique=False)
        op.create_index("ix_audit_reports_repo_name", "audit_reports", ["repo_name"], unique=False)
        op.create_index("ix_audit_reports_created_at", "audit_reports", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("audit_reports")
    op.drop_table("pr_reviews")
    op.drop_table("conversation_turns")
    op.drop_table("repositories")

"""Historial de cambios de la base de conocimiento.

Revision ID: f016knowledgechanges
Revises: e015contact
"""
import sqlalchemy as sa
from alembic import op

revision = "f016knowledgechanges"
down_revision = "e015contact"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("knowledge_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("business_id", sa.String(50), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("actor_email", sa.String(254), nullable=False),
        sa.Column("before_title", sa.String(120), nullable=True),
        sa.Column("before_body", sa.Text(), nullable=True),
        sa.Column("after_title", sa.String(120), nullable=True),
        sa.Column("after_body", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_knowledge_changes_business_id", "knowledge_changes", ["business_id"])


def downgrade():
    op.drop_index("ix_knowledge_changes_business_id", table_name="knowledge_changes")
    op.drop_table("knowledge_changes")

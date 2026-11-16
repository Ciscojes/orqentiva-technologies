"""Vectores de la base de conocimiento para la búsqueda por significado.

Revision ID: g019knowledgevectors
Revises: f016knowledgechanges
"""
import sqlalchemy as sa
from alembic import op

revision = "g019knowledgevectors"
down_revision = "f016knowledgechanges"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("knowledge_vectors",
        sa.Column("business_id", sa.String(50), sa.ForeignKey("businesses.id"), primary_key=True),
        sa.Column("model", sa.String(200), primary_key=True),
        sa.Column("text_hash", sa.String(64), primary_key=True),
        sa.Column("vector", sa.JSON(), nullable=False))


def downgrade():
    op.drop_table("knowledge_vectors")

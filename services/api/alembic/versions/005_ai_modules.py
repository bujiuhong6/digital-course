"""ai modules

Revision ID: 005_ai_modules
Revises: 004_admin_username
Create Date: 2026-04-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "005_ai_modules"
down_revision: Union[str, None] = "004_admin_username"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), server_default="deepseek", nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("api_key_ciphertext", sa.Text(), nullable=True),
        sa.Column(
            "chapter_model",
            sa.String(length=128),
            server_default="gpt-4o-mini",
            nullable=False,
        ),
        sa.Column(
            "chat_model",
            sa.String(length=128),
            server_default="gpt-4o-mini",
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("llm_config")

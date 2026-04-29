"""prestudy

Revision ID: 006_prestudy
Revises: 005_ai_modules
Create Date: 2026-04-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite


revision: str = "006_prestudy"
down_revision: Union[str, None] = "005_ai_modules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prestudy_chapters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("published_content", sqlite.JSON(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "prestudy_responses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("prestudy_id", sa.Uuid(), nullable=False),
        sa.Column("ratings", sqlite.JSON(), nullable=False),
        sa.Column("feedback_text", sa.Text(), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["prestudy_id"], ["prestudy_chapters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "prestudy_id", name="uq_prestudy_response_student"),
    )
    op.create_index(op.f("ix_prestudy_responses_prestudy_id"), "prestudy_responses", ["prestudy_id"])
    op.create_index(op.f("ix_prestudy_responses_student_id"), "prestudy_responses", ["student_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_prestudy_responses_student_id"), table_name="prestudy_responses")
    op.drop_index(op.f("ix_prestudy_responses_prestudy_id"), table_name="prestudy_responses")
    op.drop_table("prestudy_responses")
    op.drop_table("prestudy_chapters")

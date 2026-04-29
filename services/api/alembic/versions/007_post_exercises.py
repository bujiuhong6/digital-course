"""post exercises

Revision ID: 007_post_exercises
Revises: 006_prestudy
Create Date: 2026-04-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite


revision: str = "007_post_exercises"
down_revision: Union[str, None] = "006_prestudy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "post_exercises",
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
        "post_exercise_submissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("answers", sqlite.JSON(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("ai_feedback", sa.Text(), nullable=True),
        sa.Column("graded_raw", sa.Text(), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["exercise_id"], ["post_exercises.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "exercise_id", name="uq_post_exercise_submission_student"),
    )
    op.create_index(
        op.f("ix_post_exercise_submissions_exercise_id"),
        "post_exercise_submissions",
        ["exercise_id"],
    )
    op.create_index(
        op.f("ix_post_exercise_submissions_student_id"),
        "post_exercise_submissions",
        ["student_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_post_exercise_submissions_student_id"), table_name="post_exercise_submissions")
    op.drop_index(op.f("ix_post_exercise_submissions_exercise_id"), table_name="post_exercise_submissions")
    op.drop_table("post_exercise_submissions")
    op.drop_table("post_exercises")

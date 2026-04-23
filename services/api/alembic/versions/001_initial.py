"""initial schema per design §3–4

Revision ID: 001_initial
Revises:
Create Date: 2026-04-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "chapters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "content_status",
            sa.String(length=32),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column("source_material", sa.Text(), nullable=True),
        sa.Column("ai_generated_draft", sqlite.JSON(), nullable=True),
        sa.Column("ai_generated_raw", sa.Text(), nullable=True),
        sa.Column("generator_prompt_version", sa.String(length=32), nullable=True),
        sa.Column("generator_model", sa.String(length=128), nullable=True),
        sa.Column("published_content", sqlite.JSON(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chapters_slug"), "chapters", ["slug"], unique=True)
    op.create_table(
        "students",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("student_no", sa.String(length=64), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("password_ciphertext", sa.Text(), nullable=False),
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_students_student_no"), "students", ["student_no"], unique=True)
    op.create_table(
        "admin_audit",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_student_id", sa.Uuid(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(["target_student_id"], ["students.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "cell_verifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("cell_id", sa.String(length=128), nullable=False),
        sa.Column("run_ok", sa.Boolean(), nullable=False),
        sa.Column(
            "at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("stdout", sa.Text(), nullable=True),
        sa.Column("error_excerpt", sa.String(length=500), nullable=True),
        sa.Column("elapsed_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "chapter_id", "cell_id", name="uq_cell_verification_scope"),
    )
    op.create_index(
        op.f("ix_cell_verifications_chapter_id"),
        "cell_verifications",
        ["chapter_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cell_verifications_student_id"),
        "cell_verifications",
        ["student_id"],
        unique=False,
    )
    op.create_table(
        "chapter_completions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "chapter_id", name="uq_chapter_completion"),
    )
    op.create_index(
        op.f("ix_chapter_completions_chapter_id"),
        "chapter_completions",
        ["chapter_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chapter_completions_student_id"),
        "chapter_completions",
        ["student_id"],
        unique=False,
    )
    op.create_table(
        "roster_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("student_no", sa.String(length=64), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("student_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_roster_entries_student_no"),
        "roster_entries",
        ["student_no"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_roster_entries_student_no"), table_name="roster_entries")
    op.drop_table("roster_entries")
    op.drop_index(op.f("ix_chapter_completions_student_id"), table_name="chapter_completions")
    op.drop_index(op.f("ix_chapter_completions_chapter_id"), table_name="chapter_completions")
    op.drop_table("chapter_completions")
    op.drop_index(op.f("ix_cell_verifications_student_id"), table_name="cell_verifications")
    op.drop_index(op.f("ix_cell_verifications_chapter_id"), table_name="cell_verifications")
    op.drop_table("cell_verifications")
    op.drop_table("admin_audit")
    op.drop_index(op.f("ix_students_student_no"), table_name="students")
    op.drop_table("students")
    op.drop_index(op.f("ix_chapters_slug"), table_name="chapters")
    op.drop_table("chapters")
    op.drop_table("admin_config")

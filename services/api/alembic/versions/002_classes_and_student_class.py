"""classes table + students.class_id

Revision ID: 002_class
Revises: 001_initial
Create Date: 2026-04-23
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import sqlite

revision: str = "002_class"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "classes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_classes_name"), "classes", ["name"], unique=True)
    with op.batch_alter_table("students") as b:
        b.add_column(
            sa.Column("class_id", sa.Uuid(), nullable=True),
        )
        b.create_index(op.f("ix_students_class_id"), ["class_id"], unique=False)
        b.create_foreign_key(
            "fk_students_class_id_classes",
            "classes",
            ["class_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("students") as b:
        b.drop_constraint("fk_students_class_id_classes", type_="foreignkey")
        b.drop_index(op.f("ix_students_class_id"))
        b.drop_column("class_id")
    op.drop_index(op.f("ix_classes_name"), table_name="classes")
    op.drop_table("classes")

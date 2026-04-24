"""roster_entries.class_id -> classes

Revision ID: 003_roster_class
Revises: 002_class
Create Date: 2026-04-23
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_roster_class"
down_revision: Union[str, None] = "002_class"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("roster_entries") as b:
        b.add_column(sa.Column("class_id", sa.Uuid(), nullable=True))
        b.create_index(op.f("ix_roster_entries_class_id"), ["class_id"], unique=False)
        b.create_foreign_key(
            "fk_roster_entries_class_id_classes",
            "classes",
            ["class_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("roster_entries") as b:
        b.drop_constraint("fk_roster_entries_class_id_classes", type_="foreignkey")
        b.drop_index(op.f("ix_roster_entries_class_id"))
        b.drop_column("class_id")

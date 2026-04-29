"""admin_config.username

Revision ID: 004_admin_username
Revises: 003_roster_class
Create Date: 2026-04-28
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_admin_username"
down_revision: Union[str, None] = "003_roster_class"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("admin_config") as b:
        b.add_column(
            sa.Column(
                "username",
                sa.String(length=128),
                nullable=False,
                server_default="admin",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("admin_config") as b:
        b.drop_column("username")

"""prestudy teaching advice persistence

Revision ID: 008_prestudy_teaching_advice
Revises: 007_post_exercises
Create Date: 2026-04-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "008_prestudy_teaching_advice"
down_revision: Union[str, None] = "007_post_exercises"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "prestudy_chapters",
        sa.Column("teaching_advice_text", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("prestudy_chapters", "teaching_advice_text")

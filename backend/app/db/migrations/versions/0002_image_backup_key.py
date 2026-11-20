"""Store each image's backup location.

Revision ID: 0002_image_backup_key
Revises: 0001_initial
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_image_backup_key"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("images") as batch:
        batch.add_column(sa.Column("backup_key", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("images") as batch:
        batch.drop_column("backup_key")

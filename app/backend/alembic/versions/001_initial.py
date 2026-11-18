from alembic import op
from npsdm_app.db import metadata

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    metadata.create_all(bind=op.get_bind())


def downgrade():
    raise RuntimeError(
        "Destructive downgrade disabled; restore a verified backup explicitly"
    )

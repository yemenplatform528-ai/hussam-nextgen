"""Persist authenticated OIDC provenance for governed mutation approvals."""
from alembic import op
import sqlalchemy as sa

revision = "0040_hus_approval_provenance"
down_revision = "0039_yemen_phase1_runtime_activation"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("ai_actions")}
    if "approval_provenance" not in cols:
        op.add_column("ai_actions", sa.Column("approval_provenance", sa.JSON(), nullable=True))


def downgrade():
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("ai_actions")}
    if "approval_provenance" in cols:
        op.drop_column("ai_actions", "approval_provenance")

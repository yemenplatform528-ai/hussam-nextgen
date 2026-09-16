"""Add provider-neutral OIDC identity bindings."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0002_oidc_identity_binding"
down_revision = "0001_initial_unified_platform"
branch_labels = None
depends_on = None

def upgrade():
    if "oidc_identities" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "oidc_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=255), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("issuer", sa.String(length=500), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("issuer", "subject", name="uq_oidc_identity_issuer_subject"),
    )
    op.create_index("ix_oidc_identities_user_id", "oidc_identities", ["user_id"])

def downgrade():
    op.drop_index("ix_oidc_identities_user_id", table_name="oidc_identities")
    op.drop_table("oidc_identities")

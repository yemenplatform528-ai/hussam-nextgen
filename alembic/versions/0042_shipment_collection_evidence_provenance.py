"""Persist COD collection evidence source and verification level."""

from alembic import op
import sqlalchemy as sa

revision = "0042_shipment_collection_evidence_provenance"
down_revision = "0041_hus_execution_idempotency"
branch_labels = None
depends_on = None

TABLE = "shipment_collections"
SOURCE_CHECK = "ck_shipment_collection_evidence_source"
VERIFICATION_CHECK = "ck_shipment_collection_evidence_verification"


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns(TABLE)}
    checks = {constraint.get("name") for constraint in inspector.get_check_constraints(TABLE)}

    with op.batch_alter_table(TABLE) as batch:
        if "evidence_source" not in columns:
            batch.add_column(
                sa.Column(
                    "evidence_source",
                    sa.String(length=40),
                    nullable=False,
                    server_default=sa.text("'seller_attestation'"),
                )
            )
        if "independently_verified" not in columns:
            batch.add_column(
                sa.Column(
                    "independently_verified",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )
        if SOURCE_CHECK not in checks:
            batch.create_check_constraint(
                SOURCE_CHECK,
                "evidence_source = 'seller_attestation'",
            )
        if VERIFICATION_CHECK not in checks:
            batch.create_check_constraint(
                VERIFICATION_CHECK,
                "independently_verified = false",
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns(TABLE)}
    checks = {constraint.get("name") for constraint in inspector.get_check_constraints(TABLE)}

    with op.batch_alter_table(TABLE) as batch:
        if VERIFICATION_CHECK in checks:
            batch.drop_constraint(VERIFICATION_CHECK, type_="check")
        if SOURCE_CHECK in checks:
            batch.drop_constraint(SOURCE_CHECK, type_="check")
        if "independently_verified" in columns:
            batch.drop_column("independently_verified")
        if "evidence_source" in columns:
            batch.drop_column("evidence_source")

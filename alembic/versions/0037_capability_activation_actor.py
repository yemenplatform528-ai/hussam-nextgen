"""align market capability activation actor with User.id."""
from alembic import op
import sqlalchemy as sa

revision = "0037_capability_activation_actor"
down_revision = "0036_mutation_records"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "market_capability_activations" not in inspector.get_table_names():
        return

    columns = {column["name"]: column for column in inspector.get_columns("market_capability_activations")}
    actor = columns.get("activated_by")
    if actor is None or isinstance(actor["type"], sa.String):
        return

    with op.batch_alter_table("market_capability_activations") as batch:
        batch.alter_column(
            "activated_by",
            existing_type=sa.Integer(),
            type_=sa.String(255),
            existing_nullable=True,
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "market_capability_activations" not in inspector.get_table_names():
        return

    columns = {column["name"]: column for column in inspector.get_columns("market_capability_activations")}
    actor = columns.get("activated_by")
    if actor is None or isinstance(actor["type"], sa.Integer):
        return

    table = sa.table(
        "market_capability_activations",
        sa.column("activated_by", sa.String(255)),
    )
    values = bind.execute(sa.select(table.c.activated_by)).scalars().all()
    non_numeric = [value for value in values if value is not None and not str(value).isdigit()]
    if non_numeric:
        raise RuntimeError(
            "cannot downgrade activated_by to Integer while non-numeric user identities exist"
        )

    with op.batch_alter_table("market_capability_activations") as batch:
        batch.alter_column(
            "activated_by",
            existing_type=sa.String(255),
            type_=sa.Integer(),
            existing_nullable=True,
        )

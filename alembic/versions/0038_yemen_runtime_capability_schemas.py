"""define configuration contracts for remaining Yemen runtime capabilities."""
from alembic import op
import sqlalchemy as sa

revision = "0038_yemen_runtime_capability_schemas"
down_revision = "0037_capability_activation_actor"
branch_labels = None
depends_on = None

SCHEMAS = {
    "yem_local_pricing": {
        "type": "object",
        "properties": {
            "enabled": {"type": "boolean"},
            "modes": {"type": "array", "items": {"type": "string"}},
            "branch_overrides": {"type": "boolean"},
        },
        "required": ["enabled"],
        "additionalProperties": False,
    },
    "yem_business_verticals": {
        "type": "object",
        "properties": {
            "enabled": {"type": "boolean"},
            "verticals": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["enabled"],
        "additionalProperties": False,
    },
    "yem_branch_warehouse_network": {
        "type": "object",
        "properties": {
            "enabled": {"type": "boolean"},
            "branch_aware": {"type": "boolean"},
            "warehouse_aware": {"type": "boolean"},
            "service_area_aware": {"type": "boolean"},
        },
        "required": ["enabled"],
        "additionalProperties": False,
    },
    "yem_local_reporting": {
        "type": "object",
        "properties": {
            "enabled": {"type": "boolean"},
            "dimensions": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["enabled"],
        "additionalProperties": False,
    },
}

def upgrade():
    table = sa.table(
        "platform_capabilities",
        sa.column("code", sa.String(120)),
        sa.column("config_schema", sa.JSON),
    )
    bind = op.get_bind()
    for code, schema in SCHEMAS.items():
        bind.execute(
            table.update().where(table.c.code == code).values(config_schema=schema)
        )

def downgrade():
    table = sa.table(
        "platform_capabilities",
        sa.column("code", sa.String(120)),
        sa.column("config_schema", sa.JSON),
    )
    bind = op.get_bind()
    for code in SCHEMAS:
        bind.execute(
            table.update().where(table.c.code == code).values(config_schema={})
        )
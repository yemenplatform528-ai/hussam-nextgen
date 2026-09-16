"""AI-04 product lock marker.

The repository uses a model-driven unified baseline (0001) whose metadata is
loaded by Alembic before historical closure migrations. The AI-04 tables are
therefore created by the canonical baseline; this revision records the
engineering lock and intentionally performs no duplicate DDL.
"""
from alembic import op

revision = "0013_ai_product_lock"
down_revision = "0012_ai_multi_agent_operations"
branch_labels = None
depends_on = None


def upgrade():
    # AI-04 schema is part of the canonical metadata baseline.
    pass


def downgrade():
    # Schema ownership remains with the canonical baseline.
    pass

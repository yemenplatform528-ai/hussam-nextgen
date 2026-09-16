"""Hussam NextGen unified platform baseline.

This is the canonical database baseline. The platform is maintained as one
unified system; historical implementation increments are intentionally not
part of the active repository schema.
"""
from alembic import op
from app.core.persistence import Base
import app.core.models.core  # noqa: F401
import app.core.models.finance  # noqa: F401
import app.core.models.inventory  # noqa: F401
import app.core.models.governance  # noqa: F401
import app.core.models.commerce  # noqa: F401
import app.core.models.procurement  # noqa: F401
import app.core.models.payments  # noqa: F401
import app.core.models.logistics  # noqa: F401
import app.core.models.workflow  # noqa: F401
import app.core.models.documents  # noqa: F401
import app.core.models.retail  # noqa: F401
import app.core.models.ai_hus  # noqa: F401
import app.core.models.ai_intelligence  # noqa: F401
import app.core.models.marketplace  # noqa: F401
import app.core.models.catalog  # noqa: F401
import app.core.models.marketplace_growth  # noqa: F401
import app.core.models.platform_completion  # noqa: F401

revision = "0001_initial_unified_platform"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

def downgrade():
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)

import app.core.models.marketplace_operational  # noqa: F401
import app.core.models.amazon_completion  # noqa: F401

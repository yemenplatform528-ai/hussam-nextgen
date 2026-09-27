"""seed the governed Yemen Phase 1 runtime capability activations.

This migration activates only market configuration capabilities. It does not
activate external payment providers, carriers, credentials, or production
certification. Geography coverage remains data-driven and therefore empty until
an independently reviewed geography artifact is admitted.
"""
from datetime import datetime, timezone
import json

from alembic import op
import sqlalchemy as sa

revision = "0039_yemen_phase1_runtime_activation"
down_revision = "0038_yemen_runtime_capability_schemas"
branch_labels = None
depends_on = None

ACTIVATIONS = {
    "yem_money_presentation": {
        "status": "active",
        "configuration": {
            "enabled": True,
            "default_currency": "YER",
            "automatic_conversion": False,
            "conversion_provenance_required": True,
        },
    },
    "yem_geography_service_areas": {
        "status": "active",
        "configuration": {
            "enabled": True,
            "hierarchy": ["country", "governorate", "district", "locality"],
            "coverage_source_required": True,
            "fail_closed_when_unknown": True,
        },
    },
    "yem_payment_methods": {
        "status": "active",
        "configuration": {
            "enabled": True,
            "cod_enabled": True,
            "cash_at_pickup_enabled": True,
            "manual_transfer_enabled": True,
            "provider_backed_activation_requires_certification": True,
        },
    },
    "yem_delivery_modes": {
        "status": "active",
        "configuration": {
            "enabled": True,
            "modes": ["pickup", "local_delivery", "inter_city_delivery"],
        },
    },
    "yem_connectivity_policy": {
        "status": "active",
        "configuration": {
            "offline_drafts": True,
            "idempotent_mutations": True,
            "explicit_pending_states": True,
        },
    },
    "yem_arabic_documents": {
        "status": "active",
        "configuration": {
            "enabled": True,
            "arabic_first": True,
            "english_supported": True,
        },
    },
    "yem_notification_channels": {
        "status": "active",
        "configuration": {
            "enabled": True,
            "channels": ["in_app"],
            "external_channels_require_provider_configuration": True,
        },
    },
    "yem_local_pricing": {
        "status": "active",
        "configuration": {
            "enabled": True,
            "modes": ["retail", "wholesale"],
            "branch_overrides": True,
        },
    },
    "yem_business_verticals": {
        "status": "active",
        "configuration": {
            "enabled": True,
            "verticals": [
                "retail",
                "wholesale",
                "services",
                "clinic",
                "dental_lab",
                "projects",
                "community",
            ],
        },
    },
    "yem_branch_warehouse_network": {
        "status": "active",
        "configuration": {
            "enabled": True,
            "branch_aware": True,
            "warehouse_aware": True,
            "service_area_aware": True,
        },
    },
    "yem_local_reporting": {
        "status": "active",
        "configuration": {
            "enabled": True,
            "dimensions": ["governorate", "market", "business_context", "channel"],
        },
    },
    "yem_ai_hus_context": {
        "status": "active",
        "configuration": {
            "enabled": True,
            "arabic_terminology": True,
            "local_market_context": True,
            "ai_proposes_not_authorizes": True,
            "hus_uses_domain_contracts": True,
        },
    },
}


def upgrade():
    bind = op.get_bind()
    market = bind.execute(
        sa.text("SELECT id FROM market_contexts WHERE code = :code"),
        {"code": "YEM"},
    ).first()
    if market is None:
        return

    capability_rows = bind.execute(
        sa.text(
            "SELECT id, code FROM platform_capabilities "
            "WHERE code IN :codes"
        ).bindparams(sa.bindparam("codes", expanding=True)),
        {"codes": list(ACTIVATIONS)},
    ).all()
    capability_ids = {row.code: row.id for row in capability_rows}

    now = datetime.now(timezone.utc)
    for code, spec in ACTIVATIONS.items():
        capability_id = capability_ids.get(code)
        if capability_id is None:
            continue
        existing = bind.execute(
            sa.text(
                "SELECT id FROM market_capability_activations "
                "WHERE market_id = :market_id AND capability_id = :capability_id"
            ),
            {"market_id": market.id, "capability_id": capability_id},
        ).first()
        if existing is None:
            bind.execute(
                sa.text(
                    "INSERT INTO market_capability_activations "
                    "(id, market_id, capability_id, status, configuration, "
                    "activated_by, created_at, updated_at) "
                    "VALUES (:id, :market_id, :capability_id, :status, "
                    ":configuration, NULL, :created_at, :updated_at)"
                ),
                {
                    "id": f"YEM-{code}",
                    "market_id": market.id,
                    "capability_id": capability_id,
                    "status": spec["status"],
                    "configuration": json.dumps(spec["configuration"]),
                    "created_at": now,
                    "updated_at": now,
                },
            )


def downgrade():
    bind = op.get_bind()
    market = bind.execute(
        sa.text("SELECT id FROM market_contexts WHERE code = :code"),
        {"code": "YEM"},
    ).first()
    if market is None:
        return

    bind.execute(
        sa.text(
            "DELETE FROM market_capability_activations "
            "WHERE market_id = :market_id AND id LIKE 'YEM-%'"
        ),
        {"market_id": market.id},
    )

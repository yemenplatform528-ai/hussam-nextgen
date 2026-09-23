"""add governed platform capability registry"""
from alembic import op
import sqlalchemy as sa

revision = "0030_platform_capability_registry"
down_revision = "0029_developer_extension_platform"
branch_labels = None
depends_on = None

CAPABILITIES = [
    ("yem_money_presentation","money","Yemen money presentation","Currency, denomination and market-money-unit presentation without creating parallel accounting currencies."),
    ("yem_geography_service_areas","geography","Yemen geography and service areas","Governorate, district, locality and operational service-area configuration."),
    ("yem_payment_methods","payments","Yemen payment method catalog","Cash, COD, transfer and certified provider-backed payment method configuration."),
    ("yem_delivery_modes","logistics","Yemen delivery modes","Pickup, local delivery, inter-city delivery and service-area delivery configuration."),
    ("yem_connectivity_policy","connectivity","Connectivity-aware operation","Offline-safe drafts, retry/idempotency and pending synchronization policy metadata."),
    ("yem_arabic_documents","documents","Arabic document templates","Arabic-first document and transaction template configuration."),
    ("yem_notification_channels","notifications","Yemen notification channels","Configurable SMS, WhatsApp and in-platform notification workflow metadata."),
    ("yem_local_pricing","pricing","Local pricing rules","Market-aware price display and local pricing policy configuration."),
    ("yem_business_verticals","verticals","Yemen business verticals","Configuration for shops, wholesalers, services, clinics, labs, projects and community operations."),
    ("yem_branch_warehouse_network","operations","Branch and warehouse network","Local branch, warehouse and inventory-service-area configuration."),
    ("yem_local_reporting","analytics","Local reporting","Governorate, market and business-context reporting configuration."),
    ("yem_ai_hus_context","ai","Yemen AI/HUS context","Governed Yemen context supplied to AI/HUS without bypassing authoritative engines."),
]

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "platform_capabilities" in insp.get_table_names():
        return
    op.create_table(
        "platform_capabilities",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("code", sa.String(120), nullable=False, unique=True),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("market_scope", sa.JSON(), nullable=False),
        sa.Column("config_schema", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("category", "code", name="uq_platform_capability_category_code"),
        sa.CheckConstraint("status IN ('active','draft','deprecated','suspended')", name="ck_platform_capability_status"),
    )
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    table = sa.table(
        "platform_capabilities",
        sa.column("id", sa.String),
        sa.column("code", sa.String),
        sa.column("category", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("market_scope", sa.JSON),
        sa.column("config_schema", sa.JSON),
        sa.column("status", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(table, [
        {"id": code, "code": code, "category": category, "name": name,
         "description": description, "market_scope": ["YEM"], "config_schema": {},
         "status": "active", "created_at": now, "updated_at": now}
        for code, category, name, description in CAPABILITIES
    ])

def downgrade():
    op.drop_table("platform_capabilities")

from logging.config import fileConfig
from alembic import context
from sqlalchemy import Column, MetaData, String, Table, engine_from_config, inspect, pool, text
import os

from app.core.persistence import Base
import app.core.models.core
import app.core.models.oidc
import app.core.models.finance
import app.core.models.inventory
import app.core.models.governance
import app.core.models.commerce
import app.core.models.procurement
import app.core.models.payments
import app.core.models.logistics
import app.core.models.workflow
import app.core.models.documents
import app.core.models.retail
import app.core.models.ai_hus
import app.core.models.ai_intelligence
import app.core.models.ai_foundation
import app.core.models.marketplace
import app.core.models.catalog
import app.core.models.marketplace_growth
import app.core.models.market

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _prepare_alembic_version_table(connection):
    """Allow descriptive revision ids longer than Alembic's historical 32-char default."""
    inspector = inspect(connection)
    if "alembic_version" not in inspector.get_table_names():
        Table(
            "alembic_version",
            MetaData(),
            Column("version_num", String(255), primary_key=True),
        ).create(connection)
        return

    if connection.dialect.name != "postgresql":
        return

    column = next(
        (c for c in inspector.get_columns("alembic_version") if c["name"] == "version_num"),
        None,
    )
    length = getattr(column.get("type"), "length", None) if column else None
    if length is not None and length < 255:
        connection.execute(
            text(
                "ALTER TABLE alembic_version "
                "ALTER COLUMN version_num TYPE VARCHAR(255)"
            )
        )


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata,
                      literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    if not config.get_main_option("sqlalchemy.url"):
        config.set_main_option("sqlalchemy.url", os.environ.get("DATABASE_URL", ""))
    if not config.get_main_option("sqlalchemy.url"):
        raise RuntimeError("DATABASE_URL or sqlalchemy.url is required for migrations")
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        _prepare_alembic_version_table(connection)
        context.configure(connection=connection, target_metadata=target_metadata,
                          compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

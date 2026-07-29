from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys, os

# Make the app package importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.models import Base  # noqa: E402  — imports all SQLAlchemy models
from app.core.config import settings  # noqa: E402

config = context.config

# Override sqlalchemy.url from our Settings so .env is respected
# Escape '%' → '%%' so configparser doesn't mis-interpret URL-encoded passwords
_safe_url = settings.database_url.replace("%", "%%")
config.set_main_option("sqlalchemy.url", _safe_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata,
        literal_binds=True, dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

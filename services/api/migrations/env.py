from logging.config import fileConfig

from alembic import context
from sqlalchemy import URL, create_engine, pool, text

from app.config import get_settings
from app.models import SCHEMA, Base

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str | URL:
    return config.get_main_option("sqlalchemy.url") or get_settings().database_url


def include_name(name, type_, parent_names):  # type: ignore[no-untyped-def]
    # Only manage BackIt's own schema; `auth` belongs to Better Auth and is never touched.
    if type_ == "schema":
        return name == SCHEMA
    return True


def _configure(**kwargs) -> None:  # type: ignore[no-untyped-def]
    context.configure(
        target_metadata=target_metadata,
        include_schemas=True,
        include_name=include_name,
        version_table_schema=SCHEMA,
        compare_type=True,
        **kwargs,
    )


def run_migrations_offline() -> None:
    _configure(url=_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
        connection.commit()
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

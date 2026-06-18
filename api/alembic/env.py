from __future__ import annotations

from sqlalchemy import engine_from_config, pool

from alembic import context
from app import models
from app.config import SQLALCHEMY_DATABASE_URI, log_config
from app.database import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Set up logging with app.config's log_config
log_config.structlog_logging_config.configure()
log_config.structlog_logging_config.standard_lib_logging_config.configure()

config.set_main_option(
    'sqlalchemy.url', SQLALCHEMY_DATABASE_URI.render_as_string(hide_password=False)
)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def include_object(object, name, type_, reflected, compare_to):
    # When a FK constraint has ON DELETE SET NULL [ ( column_name [, ... ] ) ],
    # reflection doesn't properly recognize that option nor additional options
    # like `deferrable` and `initially`.
    # So we'll skip comparisons where either `object` or `compare_to` have
    # that option to prevent false positives from `alembic check` reporting
    # that there are upgrade operations detected.
    # On the downside, if we make changes to these FK constraints and they
    # keep the ondelete_set_null_columns option, Alembic won't detect that
    # there have been changes. If that happens, you can comment this out before
    # upgrading, or just manually write the migration script. But I expect this
    # to be less common than migrations in general, so this should be more useful
    # than harmful.
    # TODO: there's probably some way to make reflection properly work here,
    # but I can't imagine any solution besides something within the PGDialect
    # class itself (maybe in get_multi_foreign_keys()?).
    if type_ == 'foreign_key_constraint' and (
        'postgresql_ondelete_set_null_columns'
        in list(object.dialect_kwargs) + list(compare_to.dialect_kwargs)
    ):
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option('sqlalchemy.url')
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

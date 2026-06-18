from __future__ import annotations

from advanced_alchemy.extensions.litestar import (
    AlembicSyncConfig,
    SQLAlchemyInitPlugin,
    SQLAlchemySyncConfig,
)
from litestar import Litestar
from litestar.plugins.structlog import StructlogPlugin

from .api.v1 import api_v1_router
from .config import (
    compress_config,
    cors_config,
    csrf_config,
    log_config,
)
from .database import engine, init_db, session_factory
from .openapi import openapi_config
from .problem_details import problem_details_plugin
from .schemas import (
    JSONNull,
    bigint,
    bigint_enc_hook,
    jsonnull_enc_hook,
    remove_incorrect_defaults,
)


def create_app(csrf_protection_enabled: bool = True) -> Litestar:
    # Create the 'db_session' dependency
    sqlalchemy_config = SQLAlchemySyncConfig(
        engine_instance=engine,
        session_maker=session_factory,
        # Can either use alembic directly with `alembic` or with Litestar CLI
        alembic_config=AlembicSyncConfig(script_location='alembic'),
    )

    app = Litestar(
        cors_config=cors_config,
        compression_config=compress_config,
        csrf_config=csrf_config if csrf_protection_enabled else None,
        openapi_config=openapi_config,
        plugins=[
            problem_details_plugin,
            SQLAlchemyInitPlugin(config=sqlalchemy_config),
            # NOTE: Use structlog.stdlib.get_logger() instead of logging.getLogger()
            # in our code. The config means the former will include the filename
            # and function in the log, but the latter does not.
            StructlogPlugin(config=log_config),
        ],
        on_startup=[init_db],
        type_encoders={JSONNull: jsonnull_enc_hook, bigint: bigint_enc_hook},
        route_handlers=[api_v1_router],
    )

    remove_incorrect_defaults(app.openapi_schema)

    return app


app = create_app()

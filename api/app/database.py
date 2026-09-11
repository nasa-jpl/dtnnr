from __future__ import annotations

import structlog
from alembic.config import Config as AlembicConfig
from sqlalchemy import MetaData, create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy_utils import create_database, database_exists

from alembic import command as alembic_command

from .config import ALEMBIC_INI_PATH, SQLALCHEMY_DATABASE_URI

logger = structlog.stdlib.get_logger()

engine = create_engine(
    SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,
    connect_args={'options': '-c timezone=UTC'},
    # echo=True will print logs twice (in SQLAlchemy format and in structlog).
    # Just set the right envvars in production to enable logs.
    # But echo=True can be used in testing to print out logs (structlog logs
    # don't show up in pytest for some reason).
    # echo=True,
)
session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

convention = {
    'ix': 'ix_%(column_0_label)s',
    'uq': 'uq_%(table_name)s_%(column_0_name)s',
    'ck': 'ck_%(table_name)s_%(constraint_name)s',
    'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
    'pk': 'pk_%(table_name)s',
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=convention)


def init_db() -> None:
    logger.info('Running init_db()')
    if not database_exists(SQLALCHEMY_DATABASE_URI):
        logger.info('Database does not exist, creating database.')
        create_database(SQLALCHEMY_DATABASE_URI)

    # import all modules here that might define models so that
    # they will be registered properly on the metadata. Otherwise
    # you will have to import them first before calling init_db()
    from . import models  # noqa: F401

    alembic_cfg = AlembicConfig(ALEMBIC_INI_PATH)
    table_names = set(inspect(engine).get_table_names())

    if 'alembic_version' in table_names:
        alembic_command.upgrade(alembic_cfg, 'head')
        with engine.begin() as conn:
            Base.metadata.create_all(bind=conn)
        return

    legacy_schema = 'underlying_communication_service' in table_names and not any(
        column['name'] == 'underlying_communication_service_abbreviation'
        for column in inspect(engine).get_columns('underlying_communication_service')
    )
    if legacy_schema:
        # Releases before the first Alembic revision created tables directly.
        # Mark that schema as the migration base, then apply all revisions.
        alembic_command.stamp(alembic_cfg, 'base')
        alembic_command.upgrade(alembic_cfg, 'head')
        with engine.begin() as conn:
            Base.metadata.create_all(bind=conn)
        return

    # A new database (or a current unversioned test database) can be created
    # directly from the current metadata and marked as current.
    with engine.begin() as conn:
        Base.metadata.create_all(bind=conn)
    alembic_command.stamp(alembic_cfg, 'head')

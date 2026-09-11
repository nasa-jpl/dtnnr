"""Add underlying communication service abbreviation.

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-09-10

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = 'underlying_communication_service'
ID_COLUMN = 'underlying_communication_service_id'
NAME_COLUMN = 'underlying_communication_service_name'
ABBREVIATION_COLUMN = 'underlying_communication_service_abbreviation'

DEFAULT_SERVICE_NAMES = (
    (1, 'USLP', 'Unified Space Data Link Protocol'),
    (2, 'TM (Data Link)', 'TM Space Data Link Protocol'),
    (
        3,
        'TM (Synchronization and Channel Coding)',
        'TM Synchronization and Channel Coding',
    ),
    (4, 'TC (Data Link)', 'TC Space Data Link Protocol'),
    (
        5,
        'TC (Synchronization and Channel Coding)',
        'TC Synchronization and Channel Coding',
    ),
    (6, 'AOS', 'AOS Space Data Link Protocol'),
    (
        7,
        'Prox-1 (Data Link)',
        'Proximity-1 Space Link Protocol—Data Link Layer',
    ),
    (
        8,
        'Prox-1 (Synchronization and Channel Coding)',
        'Proximity-1 Space Link Protocol—Coding and Synchronization Sublayer',
    ),
    (9, 'Ethernet', 'Ethernet'),
    (10, 'Optical', 'Optical'),
    (11, 'SpaceWire', 'SpaceWire'),
    (12, 'Serial', 'Serial'),
    (13, 'UART', 'Universal Asynchronous Receiver-Transmitter'),
    (14, 'SPP', 'Space Packet Protocol'),
    (15, 'EPP', 'Encapsulation Packet Protocol'),
    (16, 'UDP', 'User Datagram Protocol'),
    (17, 'DCCP', 'Datagram Congestion Control Protocol'),
)


def upgrade() -> None:
    op.drop_index(
        op.f(f'ix_{TABLE_NAME}_{NAME_COLUMN}'),
        table_name=TABLE_NAME,
    )
    op.alter_column(
        TABLE_NAME,
        NAME_COLUMN,
        new_column_name=ABBREVIATION_COLUMN,
        existing_type=sa.Text(),
        existing_nullable=False,
    )
    op.create_index(
        op.f(f'ix_{TABLE_NAME}_{ABBREVIATION_COLUMN}'),
        TABLE_NAME,
        [ABBREVIATION_COLUMN],
        unique=False,
    )
    op.add_column(TABLE_NAME, sa.Column(NAME_COLUMN, sa.Text(), nullable=True))

    service = sa.table(
        TABLE_NAME,
        sa.column(ID_COLUMN, sa.Integer()),
        sa.column(NAME_COLUMN, sa.Text()),
        sa.column(ABBREVIATION_COLUMN, sa.Text()),
    )
    op.execute(
        service.update().values(
            {NAME_COLUMN: service.c.underlying_communication_service_abbreviation}
        )
    )
    for service_id, abbreviation, name in DEFAULT_SERVICE_NAMES:
        op.execute(
            service.update()
            .where(
                service.c.underlying_communication_service_id == service_id,
                service.c.underlying_communication_service_abbreviation == abbreviation,
            )
            .values({NAME_COLUMN: name})
        )

    op.alter_column(
        TABLE_NAME,
        NAME_COLUMN,
        existing_type=sa.Text(),
        nullable=False,
    )
    op.create_index(
        op.f(f'ix_{TABLE_NAME}_{NAME_COLUMN}'),
        TABLE_NAME,
        [NAME_COLUMN],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f(f'ix_{TABLE_NAME}_{NAME_COLUMN}'),
        table_name=TABLE_NAME,
    )
    op.drop_column(TABLE_NAME, NAME_COLUMN)
    op.drop_index(
        op.f(f'ix_{TABLE_NAME}_{ABBREVIATION_COLUMN}'),
        table_name=TABLE_NAME,
    )
    op.alter_column(
        TABLE_NAME,
        ABBREVIATION_COLUMN,
        new_column_name=NAME_COLUMN,
        existing_type=sa.Text(),
        existing_nullable=False,
    )
    op.create_index(
        op.f(f'ix_{TABLE_NAME}_{NAME_COLUMN}'),
        TABLE_NAME,
        [NAME_COLUMN],
        unique=False,
    )

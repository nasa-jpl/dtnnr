from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING

import structlog
from sqlakeyset import select_page
from sqlalchemy import exc, select

from app.models import Destination

if TYPE_CHECKING:
    from ipaddress import IPv4Address, IPv6Address

    from sqlakeyset import Page
    from sqlalchemy import Row, Tuple
    from sqlalchemy.orm import Session

logger = structlog.stdlib.get_logger()


def get(db_session: Session, destination_id: int) -> Destination | None:
    """Get a destination by its id."""
    return db_session.scalar(
        select(Destination).where(Destination.destination_id == destination_id)
    )


def get_by_host_id_and_ip_address(
    db_session: Session, host_id: int, ip_address: str
) -> Destination | None:
    """Get a destination by host_id and ip_address."""
    try:
        return db_session.scalar(
            select(Destination).where(
                Destination.host_id == host_id,
                Destination.ip_address == ipaddress.ip_address(ip_address),
            )
        )
    except exc.DataError as e:
        # Invalid input syntax for type INET
        logger.exception(e._message())
        raise
    except Exception:
        logger.exception('Unexpected error')
        raise


def get_by_host_id_and_registered_name(
    db_session: Session, host_id: int, registered_name: str
) -> Destination | None:
    """Get a destination by host_id and registered_name."""
    try:
        return db_session.scalar(
            select(Destination).where(
                Destination.host_id == host_id,
                Destination.registered_name == registered_name,
            )
        )
    except Exception:
        logger.exception('Unexpected error')
        raise


def list_destinations(
    db_session: Session, host_id: int, max_page_size: int, bookmark: str | None
) -> Page[Row[Tuple[Destination]]]:
    """List destinations associated with a host."""
    q = (
        select(Destination)
        .where(Destination.host_id == host_id)
        .order_by(Destination.destination_id)
    )
    return select_page(db_session, q, per_page=max_page_size, page=bookmark)


def create(
    db_session: Session,
    host_id: int,
    ip_address: str | IPv4Address | IPv6Address = None,
    registered_name: str = None,
) -> Destination:
    """Create a new destination associated with the host identified by
    `host_id`. Either `ip_address` exclusive or `registered_name` need
    to not be None.
    """
    if (ip_address is None) == (registered_name is None):
        logger.exception(
            'Either `ip_address` exclusive or `registered_name` need to be None.'
        )
        raise
    try:
        destination = Destination(
            ip_address=ip_address, registered_name=registered_name, host_id=host_id
        )
        db_session.add(destination)
        db_session.commit()
    except exc.DataError as e:
        # Invalid input syntax for type INET
        logger.exception(e._message())
        raise
    except exc.IntegrityError as e:
        # Duplicate key value violates unique constraint
        logger.exception(e._message())
        raise
    except Exception as e:
        logger.exception('Unexpected error')
        raise
    return destination


def update(
    db_session: Session,
    destination_id: int,
    ip_address: str | IPv4Address | IPv6Address = None,
    registered_name: str = None,
) -> Destination:
    """Updates an existing destination record identified by
    `destination`.
    """
    if (ip_address is None) == (registered_name is None):
        logger.exception(
            'Either `ip_address` exclusive or `registered_name` need to be None.'
        )
        raise
    destination = get(db_session, destination_id)
    destination.ip_address = ip_address
    destination.registered_name = registered_name
    try:
        db_session.commit()
    except exc.IntegrityError as e:
        logger.exception(e._message())
        raise
    except Exception as e:
        logger.exception('Unexpected error')
        raise
    return destination


def delete(db_session: Session, destination_id: int) -> None:
    """Delete a destination from the `destination` table."""
    destination = get(db_session, destination_id)
    if destination is None:
        return None
    db_session.delete(destination)
    db_session.commit()

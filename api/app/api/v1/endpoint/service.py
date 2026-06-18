from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlakeyset import select_page
from sqlalchemy import delete, exc, select, tuple_
from sqlalchemy.dialects.postgresql import insert

from app.models import EndpointIMC, EndpointIPN

from .schemas import EndpointIMCReplaceSchema, EndpointIPNReplaceSchema

if TYPE_CHECKING:
    from sqlakeyset import Page
    from sqlalchemy import Row, Tuple
    from sqlalchemy.orm import Session

logger = structlog.stdlib.get_logger()


def get_ipn(db_session: Session, node_id: int, service_number: int) -> EndpointIPN:
    """Get an endpoint_ipn by `node_id` and `service_number`."""
    return db_session.scalar(
        select(EndpointIPN).where(
            (EndpointIPN.node_id == node_id)
            & (EndpointIPN.service_number == service_number)
        )
    )


def get_imc(db_session: Session, node_id: int, group_number: int) -> EndpointIMC:
    """Get an endpoint_imc by `node_id` and `group_number`."""
    return db_session.scalar(
        select(EndpointIMC).where(
            (EndpointIMC.node_id == node_id)
            & (EndpointIMC.group_number == group_number)
        )
    )


def list_ipn(
    db_session: Session, node_id: int, max_page_size: int, bookmark: str | None
) -> Page[Row[Tuple[EndpointIPN]]]:
    """List endpoint_ipn records associated with a node."""
    q = (
        select(EndpointIPN)
        .where(EndpointIPN.node_id == node_id)
        .order_by(EndpointIPN.service_number)
    )
    return select_page(db_session, q, per_page=max_page_size, page=bookmark)


def list_imc(
    db_session: Session, node_id: int, max_page_size: int, bookmark: str | None
) -> Page[Row[Tuple[EndpointIMC]]]:
    """List endpoint_imc records associated with a node."""
    q = (
        select(EndpointIMC)
        .where(EndpointIMC.node_id == node_id)
        .order_by(EndpointIMC.group_number)
    )
    return select_page(db_session, q, per_page=max_page_size, page=bookmark)


def replace_ipn(
    db_session: Session, node_id: int, endpoints: list[EndpointIPNReplaceSchema]
) -> None:
    try:
        db_session.execute(
            delete(EndpointIPN).where(
                EndpointIPN.node_id == node_id,
                tuple_(
                    EndpointIPN.service_number,
                    EndpointIPN.disposition,
                    EndpointIPN.application,
                ).not_in(
                    [
                        (e.service_number, e.disposition, e.application)
                        for e in endpoints
                    ]
                ),
            )
        )
        if endpoints:
            db_session.execute(
                insert(EndpointIPN).on_conflict_do_nothing(),
                [
                    {
                        'node_id': node_id,
                        'service_number': e.service_number,
                        'disposition': e.disposition,
                        'application': e.application,
                    }
                    for e in endpoints
                ],
            )
        db_session.commit()
    except exc.IntegrityError as e:
        # Think this happens when we repeat service numbers
        logger.exception(e._message())
        raise
    except Exception:
        logger.exception('Unexpected error')
        raise


def replace_imc(
    db_session: Session, node_id, endpoints: list[EndpointIMCReplaceSchema]
) -> None:
    try:
        db_session.execute(
            delete(EndpointIMC).where(
                EndpointIMC.node_id == node_id,
                tuple_(
                    EndpointIMC.group_number,
                    EndpointIMC.disposition,
                    EndpointIMC.application,
                ).not_in(
                    [(e.group_number, e.disposition, e.application) for e in endpoints]
                ),
            )
        )
        if endpoints:
            db_session.execute(
                insert(EndpointIMC).on_conflict_do_nothing(),
                [
                    {
                        'node_id': node_id,
                        'group_number': e.group_number,
                        'disposition': e.disposition,
                        'application': e.application,
                    }
                    for e in endpoints
                ],
            )
        db_session.commit()
    except exc.IntegrityError as e:
        # Think this happens when we repeat group numbers
        logger.exception(e._message())
        raise
    except Exception:
        logger.exception('Unexpected error')
        raise


def create_ipn(
    db_session: Session,
    node_id: int,
    service_number: int,
    disposition: str | None = None,
    application: str | None = None,
) -> EndpointIPN:
    """Create an endpoint_ipn for the node identified by node_id with
    the given service_number, disposition, and application.
    """
    try:
        endpoint = EndpointIPN(node_id=node_id, service_number=service_number)
        # Disposition and application are optional, add them if present
        if disposition in ('q', 'x'):
            # If disposition isn't 'q' or 'x', just use default disposition
            endpoint.disposition = disposition
        if application != None:
            endpoint.application = application
        db_session.add(endpoint)
        db_session.commit()
    except exc.IntegrityError as e:
        # PK on (node_id, service_number)
        # FK on node (node_id)
        # Invalid disposition (Postgres ENUM)
        logger.exception(e._message())
        raise
    except Exception:
        logger.exception('Unexpected error')
        raise
    return endpoint


def create_imc(
    db_session: Session,
    node_id: int,
    group_number: int,
    disposition: str | None = None,
    application: str | None = None,
) -> EndpointIMC:
    """Create an endpoint_imc for the node identified by node_id with
    the given group_number, disposition, and application.
    """
    try:
        endpoint = EndpointIMC(node_id=node_id, group_number=group_number)
        # Disposition and application are optional, add them if present
        if disposition in ('q', 'x'):
            # If disposition isn't 'q' or 'x', just use default disposition
            endpoint.disposition = disposition
        if application != None:
            endpoint.application = application
        db_session.add(endpoint)
        db_session.commit()
    except exc.IntegrityError as e:
        # PK on (node_id, group_number)
        # FK on node (node_id)
        # Invalid disposition (Postgres ENUM)
        logger.exception(e._message())
        raise
    except Exception:
        logger.exception('Unexpected error')
        raise
    return endpoint


def update_ipn(
    db_session: Session,
    node_id: int,
    service_number: int,
    disposition: str,
    application: str | None,
    new_service_number: int | None = None,
) -> EndpointIPN:
    """Update an endpoint_ipn identified by its EID with the given
    disposition and application.
    """
    endpoint = get_ipn(db_session, node_id, service_number)
    endpoint.disposition = disposition
    endpoint.application = application
    if new_service_number != None:
        endpoint.service_number = new_service_number
    try:
        db_session.commit()
    except exc.IntegrityError as e:
        # If the new service number is already used
        logger.exception(e._message())
        raise e
    except Exception as e:
        logger.exception('Unexpected error')
        raise e
    return endpoint


def update_imc(
    db_session: Session,
    node_id: int,
    group_number: int,
    disposition: str,
    application: str | None,
    new_group_number: int | None = None,
) -> EndpointIMC:
    """Update an endpoint_imc identified by its node_id and group_number
    with the given disposition and application.
    """
    endpoint = get_imc(db_session, node_id, group_number)
    endpoint.disposition = disposition
    endpoint.application = application
    if new_group_number != None:
        endpoint.group_number = new_group_number
    try:
        db_session.commit()
    except exc.IntegrityError as e:
        # If the new group number is already used
        logger.exception(e._message())
        raise e
    except Exception as e:
        logger.exception('Unexpected error')
        raise e
    return endpoint


def delete_ipn(db_session: Session, node_id: int, service_number: int) -> None:
    """Delete an endpoint_ipn identified by its EID."""
    endpoint = get_ipn(db_session, node_id, service_number)
    if endpoint is None:
        return None
    db_session.delete(endpoint)
    db_session.commit()


def delete_imc(db_session: Session, node_id: int, group_number: int) -> None:
    """Delete an endpoint_imc identified by its EID."""
    endpoint = get_imc(db_session, node_id, group_number)
    if endpoint is None:
        return None
    db_session.delete(endpoint)
    db_session.commit()

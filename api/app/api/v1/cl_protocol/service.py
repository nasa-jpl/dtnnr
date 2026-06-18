from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlakeyset import select_page
from sqlalchemy import cast, exc, select
from sqlalchemy.types import Text

from app.models import (
    ClProtocol,
    Induct,
    cli_command_with_required_protocol_name,
    known_cl_protocol_name_to_class,
)

if TYPE_CHECKING:
    from sqlakeyset import Page
    from sqlalchemy import Row, Tuple
    from sqlalchemy.orm import Session

logger = structlog.stdlib.get_logger()


def get_cl_protocol_check_value(protocol_name: str) -> int | None:
    """If `protocol_name` must be associated with a particular
    protocol class value, returns that value. Otherwise, returns None.
    """
    return known_cl_protocol_name_to_class.get(protocol_name)


def get(db_session: Session, id: int) -> ClProtocol | None:
    """Get a CL protocol from the `cl_protocol` table by id."""
    return db_session.scalar(select(ClProtocol).where(ClProtocol.cl_protocol_id == id))


def get_by_details(
    db_session: Session, node_id: int, cl_protocol_name: str
) -> ClProtocol | None:
    """Get a CL protocol by its node_id and cl_protocol_name."""
    return db_session.scalar(
        select(ClProtocol).where(
            ClProtocol.node_id == node_id,
            ClProtocol.cl_protocol_name == cl_protocol_name,
        )
    )


known_protocol_name_to_cli_map: dict[str, str] = {
    p_name: cli for cli, p_name in cli_command_with_required_protocol_name
}


def inducts_depend_on_cl_protocol(
    db_session: Session, cl_protocol_id: int
) -> list[str]:
    """Returns a list of induct_ids of inducts that depend on the
    cl_protocol record identified by `cl_protocol_id` such that
    modfiying the cl_protocol will error.
    """
    return db_session.scalars(
        select(cast(Induct.induct_id, Text)).where(
            Induct.cli_command.in_(known_protocol_name_to_cli_map.values())
            & (Induct.cl_protocol_id == cl_protocol_id)
        )
    ).all()


def list_cl_protocols(
    db_session: Session, node_id: int, max_page_size: int, bookmark: str | None
) -> Page[Row[Tuple[ClProtocol]]]:
    """List CL protocols associated with a node."""
    # TODO: might be better to order by name
    q = (
        select(ClProtocol)
        .where(ClProtocol.node_id == node_id)
        .order_by(ClProtocol.cl_protocol_id)
    )
    return select_page(db_session, q, per_page=max_page_size, page=bookmark)


def create(
    db_session: Session,
    node_id: int,
    cl_protocol_name: str,
    cl_protocol_class: int,
) -> ClProtocol:
    """Create a new CL protocol for the node specified by `node_id`"""
    try:
        cl_protocol = ClProtocol(
            node_id=node_id,
            cl_protocol_name=cl_protocol_name,
            cl_protocol_class=cl_protocol_class,
        )
        db_session.add(cl_protocol)
        db_session.commit()
    except exc.IntegrityError as e:
        logger.exception(e._message())
        raise
    except Exception:
        logger.exception('Unexpected error')
        raise
    return cl_protocol


def update(
    db_session: Session,
    cl_protocol_id: int,
    cl_protocol_name: str,
    cl_protocol_class: int,
) -> ClProtocol:
    """Updates an existing CL protocol record identified by
    `cl_protocol_id`.
    """
    cl_protocol = get(db_session, cl_protocol_id)
    cl_protocol.cl_protocol_name = cl_protocol_name
    cl_protocol.cl_protocol_class = cl_protocol_class
    try:
        db_session.commit()
    except exc.IntegrityError as e:
        logger.exception(e._message())
        raise
    except Exception as e:
        logger.exception('Unexpected error')
        raise
    return cl_protocol


def delete(db_session: Session, cl_protocol_id: int) -> None:
    """Delete a CL protocol record from the `cl_protocol` table by its
    ID.
    """
    cl_protocol = get(db_session, cl_protocol_id)
    if not cl_protocol:
        return None
    db_session.delete(cl_protocol)
    db_session.commit()

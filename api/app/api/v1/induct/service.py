from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlakeyset import select_page
from sqlalchemy import cast, exc, literal, select
from sqlalchemy import delete as sa_delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.types import Text

from app.models import Induct, InductIp, Link, Seat, induct_link, induct_seat

from ..cl_protocol.service import get as cl_protocol_get
from ..node.service import get as node_get

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from sqlakeyset import Page
    from sqlalchemy import Row, Tuple
    from sqlalchemy.orm import Session

logger = structlog.stdlib.get_logger()


def get(db_session: Session, id: int) -> Induct | None:
    """Get an induct by its id."""
    return db_session.scalar(select(Induct).where(Induct.induct_id == id))


def links_related_to_induct(db_session: Session, induct_id: int) -> Sequence[str]:
    """Returns a list of link_ids of links that are associated with
    the induct identified by `induct_id`.
    """
    return db_session.scalars(
        select(cast(induct_link.c.link_id, Text))
        .where(induct_link.c.induct_id == induct_id)
        .order_by(induct_link.c.link_id)
    ).all()


def seats_related_to_induct(db_session: Session, induct_id: int) -> Sequence[str]:
    """Returns a list of seat_ids of seats that are associated with
    the induct identified by `induct_id`.
    """
    return db_session.scalars(
        select(cast(induct_seat.c.seat_id, Text))
        .where(induct_seat.c.induct_id == induct_id)
        .order_by(induct_seat.c.seat_id)
    ).all()


def list_inducts(
    db_session: Session, node_id: int, max_page_size: int, bookmark: str | None
) -> Page[Row[Tuple[Induct]]]:
    """List inducts associated with a node."""
    q = select(Induct).where(Induct.node_id == node_id).order_by(Induct.induct_id)
    return select_page(db_session, q, per_page=max_page_size, page=bookmark)


def list_links(
    db_session: Session, induct_id: int, max_page_size: int, bookmark: str | None
) -> Page[Row[Tuple[Link]]]:
    """List links associated with an induct."""
    q = (
        select(Link)
        .where(
            Link.link_id == induct_link.c.link_id, induct_link.c.induct_id == induct_id
        )
        .order_by(Link.link_id)
    )
    return select_page(db_session, q, per_page=max_page_size, page=bookmark)


def list_seats(
    db_session: Session, induct_id: int, max_page_size: int, bookmark: str | None
) -> Page[Row[Tuple[Link]]]:
    """List seats associated with an induct."""
    q = (
        select(Seat)
        .where(
            Seat.seat_id == induct_seat.c.seat_id, induct_seat.c.induct_id == induct_id
        )
        .order_by(Seat.seat_id)
    )
    return select_page(db_session, q, per_page=max_page_size, page=bookmark)


def create(
    db_session: Session,
    node_id: int,
    type: str | None = None,
    cl_protocol_id: int | None = None,
    duct_name: str | None = None,
    cli_command: str | None = None,
    uses_ltp: bool = False,
) -> Induct:
    """Create a record in the induct parent table. `db_session` is
    flushed, not committed.
    """
    try:
        cl_protocol = cl_protocol_get(db_session, cl_protocol_id)
        induct = Induct(
            type=type,
            node_id=node_id,
            host_id=node_get(db_session, node_id).host_id,
            cl_protocol_id=cl_protocol_id,
            cl_protocol_name=(
                None if cl_protocol is None else cl_protocol.cl_protocol_name
            ),
            duct_name=duct_name,
            cli_command=cli_command,
            uses_ltp=uses_ltp,
        )
        db_session.add(induct)
        db_session.flush()
    except exc.IntegrityError as e:
        logger.exception(e._message())
        raise e
    except Exception:
        logger.exception('Unexpected error')
        raise
    return induct


def create_ip(
    db_session: Session,
    induct_id: int,
    destination_id: int | None = None,
    port_number: int | None = None,
) -> Induct:
    """Create a record in the `induct_ip` child table. A parent record
    in `induct` must already exist and be identified by `induct_id`.
    Returns the parent record. `db_session` is flushed, not committed.
    """
    try:
        induct = get(db_session, induct_id)
        induct_ip = InductIp(
            induct_id=induct_id,
            host_id=induct.host_id,
            destination_id=destination_id,
            port_number=port_number,
        )
        db_session.add(induct_ip)
        db_session.flush()
    except exc.IntegrityError as e:
        logger.exception(e._message())
        raise e
    except Exception:
        logger.exception('Unexpected error')
        raise
    return induct


def update(
    db_session: Session,
    induct_id: int,
    node_id: int,
    type: str | None,
    cl_protocol_id: int | None,
    duct_name: str | None,
    cli_command: str | None,
    uses_ltp: bool,
) -> Induct:
    """Update an existing induct record identified by `induct_id`.
    `db_session` is flushed, not committed.
    """
    induct = get(db_session, induct_id)
    node = node_get(db_session, node_id)
    cl_protocol = cl_protocol_get(db_session, cl_protocol_id)
    induct.type = type
    induct.node_id = node_id
    induct.host_id = node.host_id
    induct.cl_protocol_id = cl_protocol_id
    induct.cl_protocol_name = (
        None if cl_protocol is None else cl_protocol.cl_protocol_name
    )
    induct.duct_name = duct_name
    induct.cli_command = cli_command
    induct.uses_ltp = uses_ltp
    try:
        db_session.flush()
    except exc.IntegrityError as e:
        logger.exception(e._message())
        raise e
    except Exception:
        logger.exception('Unexpected error')
        raise
    return induct


def replace_links(db_session: Session, induct_id: int, link_ids: Iterable[int]) -> None:
    """Replace the links associated with the induct identified by
    `induct_id` with the links identified by the IDs in `link_ids`.
    """
    try:
        db_session.execute(
            sa_delete(induct_link).where(
                induct_link.c.induct_id == induct_id,
                induct_link.c.link_id.not_in(link_ids),
            )
        )
        if link_ids:
            select_stmt = (
                select(
                    literal(induct_id).label('induct_id'),
                    Link.link_id,
                    Link.host_id,
                    Link.direction,
                    Induct.uses_ltp,
                )
                .join(Induct, Link.host_id == Induct.host_id)
                .where(
                    Link.link_id.in_(link_ids),
                    Induct.induct_id == induct_id,
                )
            )
            insert_stmt = (
                insert(induct_link)
                .from_select(
                    ['induct_id', 'link_id', 'host_id', 'direction', 'uses_ltp'],
                    select_stmt,
                )
                .on_conflict_do_nothing()
            )
            db_session.execute(insert_stmt)
        db_session.commit()
    except Exception:
        logger.exception('Unexpected error')
        raise


def replace_seats(db_session: Session, induct_id: int, seat_ids: Iterable[int]) -> None:
    """Replace the seats associated with the induct identified by
    `induct_id` with the seats identified by the IDs in `seat_ids`.
    """
    try:
        db_session.execute(
            sa_delete(induct_seat).where(
                induct_seat.c.induct_id == induct_id,
                induct_seat.c.seat_id.not_in(seat_ids),
            )
        )
        if seat_ids:
            select_stmt = (
                select(
                    literal(induct_id).label('induct_id'),
                    Seat.seat_id,
                    Seat.node_id,
                    Induct.uses_ltp,
                )
                .join(Induct, Seat.node_id == Induct.node_id)
                .where(
                    Seat.seat_id.in_(seat_ids),
                    Induct.induct_id == induct_id,
                )
            )
            insert_stmt = (
                insert(induct_seat)
                .from_select(
                    ['induct_id', 'seat_id', 'node_id', 'uses_ltp'],
                    select_stmt,
                )
                .on_conflict_do_nothing()
            )
            db_session.execute(insert_stmt)
        db_session.commit()
    except Exception:
        logger.exception('Unexpected error')
        raise


def delete(db_session: Session, induct_id: int) -> None:
    """Delete an induct from the `induct` table by its ID."""
    induct = get(db_session, induct_id)
    if not induct:
        return None
    db_session.delete(induct)
    db_session.commit()


def delete_ip(db_session: Session, induct_id: int) -> None:
    """Deletes the `induct_ip` child record identified by `induct_id`.
    This only deletes the child record, not the parent record.
    `db_session` is flushed, not committed.
    """
    induct = get(db_session, induct_id)
    if induct.induct_ip is None:
        return None
    db_session.delete(induct.induct_ip)
    db_session.flush()

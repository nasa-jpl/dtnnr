from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlakeyset import select_page
from sqlalchemy import cast, column, exc, except_, literal, select, values
from sqlalchemy import delete as sa_delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.types import Text

from app.models import Link, Seat, SeatIp, seat_link

from ..node.service import get as node_get

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from sqlakeyset import Page
    from sqlalchemy import Row, Tuple
    from sqlalchemy.orm import Session

logger = structlog.stdlib.get_logger()


def get(db_session: Session, id: int) -> Seat | None:
    """Get a seat by its id."""
    return db_session.scalar(select(Seat).where(Seat.seat_id == id))


def exclude_ids_not_under_node(
    db_session: Session, ids: Iterable[int], node_id: int
) -> Sequence[str]:
    """Returns a sorted sequence of values from `ids` that do not
    identify a seat with a seat.node_id equivalent to `node_id`.
    """
    return db_session.scalars(
        except_(
            select(values(column('id', Text), name='t').data([(i,) for i in ids])),
            select(cast(Seat.seat_id, Text)).where(Seat.node_id == node_id),
        ).order_by(column('id'))
    ).all()


def list_seats(
    db_session: Session, node_id: int, max_page_size: int, bookmark: str | None
) -> Page[Row[Tuple[Seat]]]:
    """List seats associated with a node."""
    q = select(Seat).where(Seat.node_id == node_id).order_by(Seat.seat_id)
    return select_page(db_session, q, per_page=max_page_size, page=bookmark)


def list_links(
    db_session: Session, seat_id: int, max_page_size: int, bookmark: str | None
) -> Page[Row[Tuple[Seat]]]:
    """List links associated with a seat."""
    q = (
        select(Link)
        .where(Link.link_id == seat_link.c.link_id, seat_link.c.seat_id == seat_id)
        .order_by(Link.link_id)
    )
    return select_page(db_session, q, per_page=max_page_size, page=bookmark)


def create(
    db_session: Session,
    node_id: int,
    type: str | None = None,
    lsi_command: str | None = None,
) -> Seat:
    """Create a record in the seat parent table. `db_session` is
    flushed, not committed.
    """
    try:
        seat = Seat(
            type=type,
            node_id=node_id,
            host_id=node_get(db_session, node_id).host_id,
            lsi_command=lsi_command,
        )
        db_session.add(seat)
        db_session.flush()
    except exc.IntegrityError as e:
        logger.exception(e._message())
        raise e
    except Exception:
        logger.exception('Unexpected error')
        raise
    return seat


def create_ip(
    db_session: Session,
    seat_id: int,
    destination_id: int | None = None,
    port_number: int | None = None,
) -> Seat:
    """Create a record in the `seat_ip` child table. A parent record
    in `seat` must already exist and be identified by `seat_id`.
    Returns the parent record. `db_session` is flushed, not committed.
    """
    try:
        seat = get(db_session, seat_id)
        seat_ip = SeatIp(
            seat_id=seat_id,
            host_id=seat.host_id,
            destination_id=destination_id,
            port_number=port_number,
        )
        db_session.add(seat_ip)
        db_session.flush()
    except exc.IntegrityError as e:
        logger.exception(e._message())
        raise e
    except Exception:
        logger.exception('Unexpected error')
        raise
    return seat


def update(
    db_session: Session,
    seat_id: int,
    type: str | None,
    lsi_command: str | None,
) -> Seat:
    """Update an existing seat record identified by `seat_id`.
    `db_session` is flushed, not committed.
    """
    seat = get(db_session, seat_id)
    seat.type = type
    seat.lsi_command = lsi_command
    try:
        db_session.flush()
    except exc.IntegrityError as e:
        logger.exception(e._message())
        raise e
    except Exception:
        logger.exception('Unexpected error')
        raise
    return seat


def replace_links(db_session: Session, seat_id: int, link_ids: Iterable[int]) -> None:
    """Replace the links associated with the seat identified by
    `seat_id` with the links identified by the IDs in `link_ids`.
    """
    try:
        db_session.execute(
            sa_delete(seat_link).where(
                seat_link.c.seat_id == seat_id, seat_link.c.link_id.not_in(link_ids)
            )
        )
        if link_ids:
            select_stmt = select(
                literal(seat_id).label('seat_id'),
                Link.link_id,
                Link.host_id,
                Link.direction,
            ).where(
                Link.link_id.in_(link_ids),
            )
            insert_stmt = (
                insert(seat_link)
                .from_select(
                    ['seat_id', 'link_id', 'host_id', 'direction'],
                    select_stmt,
                )
                .on_conflict_do_nothing()
            )
            db_session.execute(insert_stmt)
        db_session.commit()
    except Exception:
        logger.exception('Unexpected error')
        raise


def delete(db_session: Session, seat_id: int) -> None:
    """Delete an seat from the `seat` table by its ID."""
    seat = get(db_session, seat_id)
    if not seat:
        return None
    db_session.delete(seat)
    db_session.commit()


def delete_ip(db_session: Session, seat_id: int) -> None:
    """Deletes the `seat_ip` child record identified by `seat_id`. This
    only deletes the child record, not the parent record. `db_session`
    is flushed, not committed.
    """
    seat = get(db_session, seat_id)
    if seat.seat_ip is None:
        return None
    db_session.delete(seat.seat_ip)
    db_session.commit()

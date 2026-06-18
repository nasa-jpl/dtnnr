from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlakeyset import select_page
from sqlalchemy import cast, column, exc, except_, insert, intersect, select, values
from sqlalchemy import delete as sa_delete
from sqlalchemy.types import Text

from app.models import (
    CommDirectionEnumInternal,
    Link,
    LinkRf,
    induct_link,
    underlying_communication_service_link,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from sqlakeyset import Page
    from sqlalchemy import Row, Tuple
    from sqlalchemy.orm import Session

logger = structlog.stdlib.get_logger()


def get(db_session: Session, link_id: int) -> Link | None:
    """Get a link by its link ID."""
    return db_session.scalar(select(Link).where(Link.link_id == link_id))


def inducts_using_link(db_session: Session, link_id: int) -> list[str]:
    """Returns a list of induct_ids of inducts that are associated with
    the link identified by `link_id`.
    """
    return db_session.scalars(
        select(cast(induct_link.c.induct_id, Text))
        .where(induct_link.c.link_id == link_id)
        .order_by(induct_link.c.induct_id)
    ).all()


def exclude_ids_not_under_host(
    db_session: Session, ids: Iterable[int], host_id: int
) -> Sequence[str]:
    """Returns a sorted sequence of values from `ids` that do not
    identify a link with a link.host_id equivalent to `host_id`.
    """
    return db_session.scalars(
        except_(
            select(values(column('id', Text), name='t').data([(i,) for i in ids])),
            select(cast(Link.link_id, Text)).where(Link.host_id == host_id),
        ).order_by(column('id'))
    ).all()


def keep_simplex_outgoing_ids(db_session: Session, ids: Iterable[int]) -> Sequence[str]:
    """Returns a sorted sequence of values from `ids` that identify a
    link with link.direction = 'Simplex (outgoing)'.
    """
    return db_session.scalars(
        intersect(
            select(values(column('id', Text), name='t').data([(i,) for i in ids])),
            select(cast(Link.link_id, Text)).where(
                Link.direction == CommDirectionEnumInternal.SIMPLEX_OUT
            ),
        ).order_by(column('id'))
    ).all()


def list_links(
    db_session: Session, host_id: int, max_page_size: int, bookmark: str | None
) -> Page[Row[Tuple[Link]]]:
    """List links associated with a host."""
    q = select(Link).where(Link.host_id == host_id).order_by(Link.link_id)
    return select_page(db_session, q, per_page=max_page_size, page=bookmark)


def create(
    db_session: Session,
    host_id: int,
    direction: str | None,
    type: str | None = None,
) -> Link:
    """Create a record in the `link` parent table. `db_session` is
    flushed, not committed.
    """
    try:
        link = Link(type=type, host_id=host_id, direction=direction)
        db_session.add(link)
        db_session.flush()
    except Exception:
        logger.exception('Unexpected error')
        raise
    return link


def create_rf(
    db_session: Session,
    link_id: int,
    band_id: int | None = None,
) -> Link:
    """Create a record in the `link_rf` child table. A parent record in
    `link` must already exist and be identified by `link_id`. Returns
    the parent record. `db_session` is flushed, not committed.
    """
    try:
        link_rf = LinkRf(link_id=link_id, band_id=band_id)
        db_session.add(link_rf)
        db_session.flush()
    except Exception:
        logger.exception('Unexpected error')
        raise
    return link_rf.link


def update(
    db_session: Session,
    link_id: int,
    host_id: int,
    direction: str | None,
    type: str | None = None,
) -> Link:
    """Update the record in the `link` parent table identified
    `link_id`. `db_session` is flushed, not committed.
    """
    link = get(db_session, link_id)
    link.host_id = host_id
    link.direction = direction
    link.type = type
    try:
        db_session.flush()
    except exc.IntegrityError as e:
        # Changing type when a child record still exists, changing host_id when
        # still used by ducts on the old host
        logger.exception(e._message())
        raise e
    except Exception:
        logger.exception('Unexpected error')
        raise
    return link


def update_rf(
    db_session: Session,
    link_id: int,
    band_id: int,
) -> Link:
    """Update the record in the `link_rf` child table identified by
    `link_id`. Returns the parent record. `db_session` is flushed, not
    committed.
    """
    link = get(db_session, link_id)
    link.link_rf.band_id = band_id
    try:
        db_session.flush()
    except Exception:
        logger.exception('Unexpected error')
        raise
    return link


def replace_underlying_communication_services(
    db_session: Session, link_id: int, service_ids: list[int]
) -> None:
    """Replace the underlying communication services associated with
    the link specified by `link_id` with the services identified by the
    IDs in `service_ids`. `db_session` is flushed, not committed.
    """
    try:
        db_session.execute(
            sa_delete(underlying_communication_service_link).where(
                underlying_communication_service_link.c.link_id == link_id
            )
        )
        if service_ids:
            db_session.execute(
                insert(underlying_communication_service_link),
                [
                    {'link_id': link_id, 'underlying_communication_service_id': id}
                    for id in service_ids
                ],
            )
        db_session.flush()
    except Exception:
        logger.exception('Unexpected error')
        raise


def delete(db_session: Session, link_id: int) -> None:
    """Deletes the `link` parent record identified by `link_id`. This
    will delete child link records, associated records with ducts, and
    associated records with underlying communication services.
    """
    link = get(db_session, link_id)
    if link is None:
        return None
    db_session.delete(link)
    db_session.commit()


def delete_rf(db_session: Session, link_id: int) -> None:
    """Deletes the `link_rf` child record identified by `link_id`. This
    only deletes the child record, not the parent record. `db_session`
    is flushed, not committed.
    """
    link = get(db_session, link_id)
    if link is None:
        return None
    db_session.delete(link.link_rf)
    db_session.flush()

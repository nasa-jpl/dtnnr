from __future__ import annotations

from typing import TYPE_CHECKING

from sqlakeyset import select_page
from sqlalchemy import cast, column, except_, select, values
from sqlalchemy.types import Text

from app.models import UnderlyingCommunicationService

if TYPE_CHECKING:
    from sqlakeyset import Page
    from sqlalchemy import Row, Tuple
    from sqlalchemy.orm import Session


def query(
    db_session: Session, max_page_size: int, bookmark: str | None
) -> Page[Row[Tuple[UnderlyingCommunicationService]]]:
    """Query underlying communication services."""
    # TODO: support filtering by name or abbreviation
    q = select(UnderlyingCommunicationService).order_by(
        UnderlyingCommunicationService.underlying_communication_service_abbreviation,
        UnderlyingCommunicationService.underlying_communication_service_id,
    )
    return select_page(db_session, q, per_page=max_page_size, page=bookmark)


def get_nonmatching_ids(db_session: Session, ids: list[int]) -> list[str]:
    """Returns the list of numbers from `ids` which do not match an
    underlying communication service ID. Duplicates are eliminated and
    results are sorted.
    """
    return db_session.scalars(
        except_(
            select(values(column('id', Text), name='t').data([(i,) for i in ids])),
            select(
                cast(
                    UnderlyingCommunicationService.underlying_communication_service_id,
                    Text,
                )
            ),
        ).order_by(column('id'))
    ).all()

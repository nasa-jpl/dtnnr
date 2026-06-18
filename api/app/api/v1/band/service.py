from __future__ import annotations

from typing import TYPE_CHECKING

from sqlakeyset import select_page
from sqlalchemy import select

from app.models import Band

if TYPE_CHECKING:
    from sqlakeyset import Page
    from sqlalchemy import Row, Tuple
    from sqlalchemy.orm import Session


def get(db_session: Session, band_id: int) -> Band | None:
    """Get a band by its ID."""
    return db_session.scalar(select(Band).where(Band.band_id == band_id))


def query(
    db_session: Session, max_page_size: int, bookmark: str | None
) -> Page[Row[Tuple[Band]]]:
    """Query bands."""
    # TODO: support filtering by name
    q = select(Band).order_by(Band.band_name, Band.band_id)
    return select_page(db_session, q, per_page=max_page_size, page=bookmark)

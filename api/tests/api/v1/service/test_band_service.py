from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import Band


def test_get(session: Session, band: Band):
    from app.api.v1.band.service import get

    t_band = get(session, band.band_id)
    assert t_band == band


def test_query(
    session: Session,
    bands: list[Band],
):
    from app.api.v1.band.service import query

    t_bands = []
    page = query(session, 1, None)
    t_bands.extend([_ for (_,) in page])
    while page.paging.has_next:
        page = query(session, 1, page.paging.bookmark_next)
        t_bands.extend([_ for (_,) in page])

    for b in bands:
        assert b in t_bands

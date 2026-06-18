from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import UnderlyingCommunicationService


def test_query(
    session: Session,
    underlying_communication_services: list[UnderlyingCommunicationService],
):
    from app.api.v1.underlying_communication_service.service import query

    t_services = []
    page = query(session, 1, None)
    t_services.extend([_ for (_,) in page])
    while page.paging.has_next:
        page = query(session, 1, page.paging.bookmark_next)
        t_services.extend([_ for (_,) in page])

    for ucs in underlying_communication_services:
        assert ucs in t_services


def test_get_nonmatching_ids(
    session: Session,
    underlying_communication_services: list[UnderlyingCommunicationService],
):
    from app.api.v1.underlying_communication_service.service import get_nonmatching_ids

    t = [
        s.underlying_communication_service_id for s in underlying_communication_services
    ]
    last = t[-1]
    t.extend([last + 1, last + 2, last + 1])
    res = get_nonmatching_ids(session, t)
    assert len(res) == 2
    assert str(last + 1) in res
    assert str(last + 2) in res

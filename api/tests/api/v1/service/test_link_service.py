from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import exc

from app.models import CommDirectionEnumInternal
from tests.util import get_as_jsonb

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import (
        Band,
        Host,
        Induct,
        Link,
        LinkRf,
        Seat,
        UnderlyingCommunicationService,
    )


def test_get(session: Session, link: Link):
    from app.api.v1.link.service import get

    t_link = get(session, link.link_id)
    assert t_link == link


def test_inducts_using_link(session: Session, link_with_inducts: Link):
    from app.api.v1.link.service import inducts_using_link

    link = link_with_inducts
    ids = inducts_using_link(session, link.link_id)
    for i in link.inducts:
        assert str(i.induct_id) in ids


def test_exclude_ids_not_under_host(
    session: Session, host_with_links: Host, links: list[Link]
):
    from app.api.v1.link.service import exclude_ids_not_under_host

    h_links = set([l.link_id for l in host_with_links.links])
    other = set([l.link_id for l in links])
    other.add(0)  # Postgres identity columns start at 1
    ids = exclude_ids_not_under_host(
        session, h_links.union(other), host_with_links.host_id
    )
    ids_int = set([int(i) for i in ids])
    assert ids_int == h_links.union(other).difference(h_links)


def test_keep_simplex_outgoing_ids(
    session: Session, links_simplex_outgoing_etc: list[Link]
):
    from app.api.v1.link.service import keep_simplex_outgoing_ids

    links = links_simplex_outgoing_etc
    only_simplex_outgoing_ids = set(
        [
            str(l.link_id)
            for l in links
            if l.direction == CommDirectionEnumInternal.SIMPLEX_OUT
        ]
    )
    ids = keep_simplex_outgoing_ids(session, [l.link_id for l in links])
    assert set(ids) == only_simplex_outgoing_ids


def test_list_links(session: Session, host_with_links: Host):
    from app.api.v1.link.service import list_links

    host = host_with_links
    links = []
    page = list_links(session, host.host_id, 1, None)
    links.extend([_ for (_,) in page])
    while page.paging.has_next:
        page = list_links(session, host.host_id, 1, page.paging.bookmark_next)
        links.extend([_ for (_,) in page])

    for l in host.links:
        assert l in links


def test_create(session: Session, host: Host):
    from app.api.v1.link.service import create

    t_link = create(session, host.host_id, CommDirectionEnumInternal.N_A.value)
    session.commit()
    assert t_link.host == host
    assert t_link in host.links
    assert t_link.type is None
    assert t_link.direction == CommDirectionEnumInternal.N_A.value
    assert t_link.link_rf is None


def test_create_rf(session: Session, link: Link):
    from app.api.v1.link.service import create_rf

    with pytest.raises(exc.IntegrityError):
        t_link = create_rf(session, link.link_id, None)
    session.rollback()

    host = link.host
    direction = link.direction

    link.type = 'rf'
    session.commit()
    t_link = create_rf(session, link.link_id, None)
    session.commit()
    assert t_link == link
    assert t_link.host == host
    assert t_link in host.links
    assert t_link.type == 'rf'
    assert t_link.direction == direction
    assert t_link.link_rf is not None
    assert t_link.link_rf.band_id is None


def test_update(session: Session, link: Link, host: Host):
    from app.api.v1.link.service import update

    old_host_id = link.host_id
    old_type = link.type
    old_direction = link.direction
    t_link = update(session, link.link_id, host.host_id, link.direction)
    session.commit()
    assert t_link == link
    assert t_link.host_id == host.host_id
    assert t_link.host_id != old_host_id
    assert t_link.type == old_type
    assert t_link.direction == old_direction


def test_update_rf(session: Session, link_rf: LinkRf, band: Band):
    from app.api.v1.link.service import update_rf

    old_host_id = link_rf.link.host_id
    old_band_id = link_rf.band_id
    old_type = link_rf.type
    old_direction = link_rf.link.direction
    t_link: Link = update_rf(session, link_rf.link_id, band.band_id)
    session.commit()
    assert t_link.link_rf == link_rf
    assert t_link.host_id == old_host_id
    assert t_link.type == old_type
    assert t_link.direction == old_direction
    assert t_link.link_rf.band_id == band.band_id
    assert t_link.link_rf.band_id != old_band_id


def test_replace_underlying_communication_services(
    session: Session,
    link_with_underlying_communication_service: Link,
    underlying_communication_services: list[UnderlyingCommunicationService],
):
    from app.api.v1.link.service import replace_underlying_communication_services

    link = link_with_underlying_communication_service
    old_service = link.underlying_communication_services[0]
    for s in underlying_communication_services:
        assert s not in link.underlying_communication_services
    replace_underlying_communication_services(
        session,
        link.link_id,
        [
            s.underlying_communication_service_id
            for s in underlying_communication_services
        ],
    )
    session.commit()
    assert old_service not in link.underlying_communication_services
    for s in underlying_communication_services:
        assert s in link.underlying_communication_services


def test_delete(
    session: Session, link: Link, induct_with_links: Induct, seat_with_links: Seat
):
    from sqlalchemy import select

    from app.api.v1.link.service import delete, get
    from app.models import Induct, Link, Seat
    from tests.util import verify_soft_deletion

    jsonb = get_as_jsonb(session, select(Link).where(Link.link_id == link.link_id))
    delete(session, link.link_id)
    assert get(session, link.link_id) is None
    assert verify_soft_deletion(session, jsonb)

    link_id = induct_with_links.links[0].link_id
    delete(session, link_id)
    assert get(session, link_id) is None
    assert (
        session.scalar(
            select(Induct).where(Induct.induct_id == induct_with_links.induct_id)
        )
        is not None
    )

    link_id = seat_with_links.links[0].link_id
    delete(session, link_id)
    assert get(session, link_id) is None
    assert (
        session.scalar(select(Seat).where(Seat.seat_id == seat_with_links.seat_id))
        is not None
    )


def test_delete_rf(session: Session, link_rf: LinkRf):
    from sqlalchemy import select

    from app.api.v1.link.service import delete_rf, get
    from app.models import LinkRf
    from tests.util import verify_soft_deletion

    link = link_rf.link

    jsonb = get_as_jsonb(session, select(LinkRf).where(LinkRf.link_id == link.link_id))
    delete_rf(session, link.link_id)
    session.commit()
    assert verify_soft_deletion(session, jsonb)
    assert get(session, link.link_id) is not None
    assert get(session, link.link_id).link_rf is None
    assert link in session

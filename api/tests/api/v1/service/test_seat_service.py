from __future__ import annotations

from typing import TYPE_CHECKING

from tests.util import get_as_jsonb

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import Node, Seat, SeatIp


def test_get(session: Session, seat: Seat, seat_ip: SeatIp):
    from app.api.v1.seat.service import get

    assert seat == get(session, seat.seat_id)
    assert seat_ip == get(session, seat_ip.seat_id).seat_ip


def test_exclude_ids_not_under_node(
    session: Session, node_with_seats: Node, seats: list[Seat]
):
    from app.api.v1.seat.service import exclude_ids_not_under_node

    n_seats = set([s.seat_id for s in node_with_seats.seats])
    other = set([s.seat_id for s in seats])
    other.add(0)  # Postgres identity columns start at 1
    ids = exclude_ids_not_under_node(
        session, n_seats.union(other), node_with_seats.node_id
    )
    ids_int = set([int(i) for i in ids])
    assert ids_int == n_seats.union(other).difference(n_seats)


def test_list_seats(session: Session, node_with_seats: Node):
    from app.api.v1.seat.service import list_seats

    node = node_with_seats
    seats = []
    page = list_seats(session, node.node_id, 1, None)
    seats.extend([_ for (_,) in page])
    while page.paging.has_next:
        page = list_seats(session, node.node_id, 1, page.paging.bookmark_next)
        seats.extend([_ for (_,) in page])

    for s in node.seats:
        assert s in seats


def test_list_links(
    session: Session, seat_with_links: Seat, seat_max_and_one_links: Seat
):
    from app.api.v1.seat.service import list_links

    seat = seat_with_links
    links = []
    page = list_links(session, seat.seat_id, 1, None)
    links.extend([_ for (_,) in page])
    while page.paging.has_next:
        page = list_links(session, seat.seat_id, 1, page.paging.bookmark_next)
        links.extend([_ for (_,) in page])

    for l in seat.links:
        assert l in links
    for l in links:
        assert l in seat.links


def test_create(session: Session, node: Node):
    from app.api.v1.seat.service import create

    type_ = None
    lsi_command = 'blah'
    seat = create(session, node.node_id, type_, lsi_command)
    session.commit()
    assert seat.node == node
    assert seat.type == type_
    assert seat.lsi_command == lsi_command


def test_create_ip(session: Session, node: Node):
    from app.api.v1.seat.service import create, create_ip

    seat = create(session, node.node_id, type='ip')
    destination_id = node.host.destinations[0].destination_id
    port_number = 1234
    seat = create_ip(session, seat.seat_id, destination_id, port_number)
    assert seat.seat_ip.destination_id == destination_id
    assert seat.seat_ip.port_number == port_number


def test_replace_links(session: Session, seat_with_link_on_host_with_links: Seat):
    from app.api.v1.seat.service import replace_links

    seat = seat_with_link_on_host_with_links
    host = seat.node.host
    old_links_len = len(seat.links)
    replace_links(session, seat.seat_id, [l.link_id for l in host.links])
    assert old_links_len != len(seat.links)
    assert host.links == seat.links


def test_replace_links_no_change(session: Session, seat_with_links: Seat):
    from app.api.v1.seat.service import replace_links

    seat = seat_with_links
    node = seat.node
    old_modified_at = node.modified_at
    old_links = seat.links
    replace_links(session, seat.seat_id, [l.link_id for l in old_links])
    assert old_links == seat.links
    assert old_modified_at == node.modified_at


def test_update(session: Session, seat_null_type: Seat):
    from app.api.v1.seat.service import update

    seat = seat_null_type
    old_node_id = seat.node_id
    old_host_id = seat.host_id
    old_type = seat.type
    assert old_type is None
    new_type = 'ip'
    new_lsi_command = 'foo'
    t_seat = update(session, seat.seat_id, new_type, new_lsi_command)
    session.commit()
    assert t_seat == seat
    assert t_seat.node_id == old_node_id
    assert t_seat.host_id == old_host_id
    assert t_seat.type == new_type
    assert t_seat.lsi_command == new_lsi_command


def test_delete(session: Session, seat: Seat, seat_ip: SeatIp):
    from sqlalchemy import select

    from app.api.v1.seat.service import delete, get
    from app.models import Seat, SeatIp
    from tests.util import verify_soft_deletion

    primary_key = seat.seat_id
    jsonb = get_as_jsonb(session, select(Seat).where(Seat.seat_id == seat.seat_id))
    delete(session, primary_key)
    assert not get(session, primary_key)
    assert verify_soft_deletion(session, jsonb)

    primary_key = seat_ip.seat_id
    jsonb = get_as_jsonb(
        session, select(SeatIp).where(SeatIp.seat_id == seat_ip.seat_id)
    )
    delete(session, primary_key)
    assert not get(session, primary_key)
    assert verify_soft_deletion(session, jsonb)


def test_delete_ip(session: Session, seat_ip: SeatIp):
    from sqlalchemy import select

    from app.api.v1.seat.service import delete_ip, get
    from app.models import SeatIp
    from tests.util import verify_soft_deletion

    seat = seat_ip.seat

    jsonb = get_as_jsonb(
        session, select(SeatIp).where(SeatIp.seat_id == seat_ip.seat_id)
    )
    delete_ip(session, seat.seat_id)
    session.commit()
    assert verify_soft_deletion(session, jsonb)
    assert get(session, seat.seat_id) is not None
    assert get(session, seat.seat_id).seat_ip is None
    assert seat in session

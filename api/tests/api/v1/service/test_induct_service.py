from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import exc

from tests.util import get_as_jsonb

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import ClProtocol, Induct, InductIp, Node


def test_get(session: Session, induct: Induct, induct_ip: InductIp):
    from app.api.v1.induct.service import get

    assert induct == get(session, induct.induct_id)
    assert induct_ip == get(session, induct_ip.induct_id).induct_ip


def test_links_related_to_induct(session: Session, induct_with_links: Induct):
    from app.api.v1.induct.service import links_related_to_induct

    induct = induct_with_links
    ids = links_related_to_induct(session, induct.induct_id)
    assert ids == [str(i) for i in sorted([l.link_id for l in induct.links])]


def test_seats_related_to_induct(session: Session, induct_with_seats: Induct):
    from app.api.v1.induct.service import seats_related_to_induct

    induct = induct_with_seats
    ids = seats_related_to_induct(session, induct.induct_id)
    assert ids == [str(i) for i in sorted([s.seat_id for s in induct.seats])]


def test_list_inducts(session: Session, node_with_inducts: Node):
    from app.api.v1.induct.service import list_inducts

    node = node_with_inducts
    inducts = []
    page = list_inducts(session, node.node_id, 1, None)
    inducts.extend([_ for (_,) in page])
    while page.paging.has_next:
        page = list_inducts(session, node.node_id, 1, page.paging.bookmark_next)
        inducts.extend([_ for (_,) in page])

    for i in node.inducts:
        assert i in inducts


def test_list_induct_links(
    session: Session, induct_with_links: Induct, induct_max_and_one_links: Induct
):
    from app.api.v1.induct.service import list_links

    # Use two fixtures to test that it doesn't select records from induct_link
    # that don't belong to the induct
    induct = induct_with_links
    links = []
    page = list_links(session, induct.induct_id, 1, None)
    links.extend([_ for (_,) in page])
    while page.paging.has_next:
        page = list_links(session, induct.induct_id, 1, page.paging.bookmark_next)
        links.extend([_ for (_,) in page])

    for l in induct.links:
        assert l in links
    for l in links:
        assert l in induct.links


def test_list_seats(
    session: Session, induct_with_seats: Induct, induct_max_and_one_seats: Induct
):
    from app.api.v1.induct.service import list_seats

    # Use two fixtures to test that it doesn't select records from induct_seat
    # that don't belong to the induct
    induct = induct_with_seats
    seats = []
    page = list_seats(session, induct.induct_id, 1, None)
    seats.extend([_ for (_,) in page])
    while page.paging.has_next:
        page = list_seats(session, induct.induct_id, 1, page.paging.bookmark_next)
        seats.extend([_ for (_,) in page])

    for s in induct.seats:
        assert s in seats
    for s in seats:
        assert s in induct.seats


def test_create(session: Session, cl_protocol: ClProtocol):
    from app.api.v1.induct.service import create

    type_ = None
    duct_name = '34'
    cli_command = 'blah blah'
    uses_ltp = False
    induct = create(
        session,
        cl_protocol.node_id,
        type_,
        cl_protocol.cl_protocol_id,
        duct_name,
        cli_command,
        uses_ltp,
    )
    session.commit()
    assert induct.type == type_
    assert induct.duct_name == duct_name
    assert induct.cli_command == cli_command
    assert induct.uses_ltp == uses_ltp


def test_create_ip(session: Session, node: Node):
    from app.api.v1.induct.service import create, create_ip

    induct = create(session, node.node_id, type='ip')
    destination_id = node.host.destinations[0].destination_id
    port_number = 1234
    induct = create_ip(session, induct.induct_id, destination_id, port_number)
    assert induct.induct_ip.destination_id == destination_id
    assert induct.induct_ip.port_number == port_number


def test_update(session: Session, induct_null_type: Induct, cl_protocol: ClProtocol):
    from app.api.v1.induct.service import update

    induct = induct_null_type
    old_node_id = induct.node_id
    old_type = induct.type
    assert old_type is None
    new_duct_name = 'foo'
    new_cli_command = 'bar'
    new_uses_ltp = False
    t_induct = update(
        session,
        induct.induct_id,
        cl_protocol.node_id,
        induct.type,
        cl_protocol.cl_protocol_id,
        new_duct_name,
        new_cli_command,
        new_uses_ltp,
    )
    session.commit()
    assert t_induct == induct
    assert t_induct.node_id == cl_protocol.node_id
    assert t_induct.node_id != old_node_id
    assert t_induct.type == old_type
    assert t_induct.cl_protocol_id == cl_protocol.cl_protocol_id
    assert t_induct.cl_protocol_name == cl_protocol.cl_protocol_name
    assert t_induct.cl_protocol == cl_protocol
    assert t_induct.duct_name == new_duct_name
    assert t_induct.cli_command == new_cli_command
    assert t_induct.uses_ltp == new_uses_ltp

    t_induct = update(
        session, induct.induct_id, induct.node_id, None, None, None, None, False
    )
    session.commit()
    assert t_induct == induct
    assert t_induct.type is None
    assert t_induct.cl_protocol_id is None
    assert t_induct.cl_protocol_name is None
    assert t_induct.cl_protocol is None
    assert t_induct.duct_name is None
    assert t_induct.cli_command is None
    assert t_induct.uses_ltp is False


def test_replace_links(session: Session, induct_with_link_on_host_with_links: Induct):
    from app.api.v1.induct.service import replace_links

    induct = induct_with_link_on_host_with_links
    host = induct.node.host
    old_links_len = len(induct.links)
    replace_links(session, induct.induct_id, [l.link_id for l in host.links])
    assert old_links_len != len(induct.links)
    assert host.links == induct.links


def test_replace_links_induct_ltp(
    session: Session, induct_ltp_on_host_with_links: Induct
):
    from app.api.v1.induct.service import replace_links

    induct = induct_ltp_on_host_with_links
    host = induct.node.host
    with pytest.raises(exc.IntegrityError):
        replace_links(session, induct.induct_id, [l.link_id for l in host.links])
    session.rollback()


def test_replace_links_no_change(session: Session, induct_with_links: Induct):
    from app.api.v1.induct.service import replace_links

    induct = induct_with_links
    node = induct.node
    old_modified_at = node.modified_at
    old_links = induct.links
    replace_links(session, induct.induct_id, [l.link_id for l in old_links])
    assert old_links == induct.links
    assert old_modified_at == node.modified_at


def test_replace_seats(session: Session, induct_with_seat_on_node_with_seats: Induct):
    from app.api.v1.induct.service import replace_seats

    induct = induct_with_seat_on_node_with_seats
    node = induct.node
    old_seats_len = len(induct.seats)
    replace_seats(session, induct.induct_id, [s.seat_id for s in node.seats])
    assert old_seats_len != len(induct.seats)
    assert node.seats == induct.seats


def test_replace_seats_not_ltp(
    session: Session, induct_not_ltp_on_node_with_seats: Induct
):
    from app.api.v1.induct.service import replace_seats

    induct = induct_not_ltp_on_node_with_seats
    node = induct.node
    with pytest.raises(exc.IntegrityError):
        replace_seats(session, induct.induct_id, [s.seat_id for s in node.seats])
    session.rollback()


def test_replace_seats_no_change(session: Session, induct_with_seats: Induct):
    from app.api.v1.induct.service import replace_seats

    induct = induct_with_seats
    node = induct.node
    old_modified_at = node.modified_at
    old_seats = induct.seats
    replace_seats(session, induct.induct_id, [s.seat_id for s in old_seats])
    assert old_seats == induct.seats
    assert old_modified_at == node.modified_at


def test_delete(session: Session, induct: Induct, induct_ip: InductIp):
    from sqlalchemy import select

    from app.api.v1.induct.service import delete, get
    from app.models import Induct, InductIp
    from tests.util import verify_soft_deletion

    primary_key = induct.induct_id
    jsonb = get_as_jsonb(
        session, select(Induct).where(Induct.induct_id == induct.induct_id)
    )
    delete(session, primary_key)
    assert not get(session, primary_key)
    assert verify_soft_deletion(session, jsonb)

    primary_key = induct_ip.induct_id
    jsonb = get_as_jsonb(
        session, select(InductIp).where(InductIp.induct_id == induct_ip.induct_id)
    )
    delete(session, primary_key)
    assert not get(session, primary_key)
    assert verify_soft_deletion(session, jsonb)


def test_delete_ip(session: Session, induct_ip: InductIp):
    from sqlalchemy import select

    from app.api.v1.induct.service import delete_ip, get
    from app.models import InductIp
    from tests.util import verify_soft_deletion

    induct = induct_ip.induct

    jsonb = get_as_jsonb(
        session, select(InductIp).where(InductIp.induct_id == induct_ip.induct_id)
    )
    delete_ip(session, induct.induct_id)
    session.commit()
    assert verify_soft_deletion(session, jsonb)
    assert get(session, induct.induct_id) is not None
    assert get(session, induct.induct_id).induct_ip is None
    assert induct in session

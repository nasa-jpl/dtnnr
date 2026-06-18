from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import exc

from app.api.v1.node.service import DestinationRefModeEnum
from tests.util import get_as_jsonb

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import Contact, Host, Induct, InductIp, Node, Operator, Seat, SeatIp


def test_get(session: Session, node: Node):
    from app.api.v1.node.service import get

    t_node = get(session, node.node_id)
    assert t_node == node


def test_get_by_FQNN(session: Session, node: Node):
    from app.api.v1.node.service import get_by_FQNN

    t_node = get_by_FQNN(session, node.allocator_id, node.node_number)
    assert t_node == node


def test_query(session: Session, nodes: list[Node]):
    from app.api.v1.node.service import query

    t_nodes = []
    page = query(session, 1, None)
    t_nodes.extend([_ for (_,) in page])
    while page.paging.has_next:
        page = query(session, 1, page.paging.bookmark_next)
        t_nodes.extend([_ for (_,) in page])

    for n in nodes:
        assert n in t_nodes


# def test_get_all_general_info(session, nodes,
#         node_without_endpoints,
#         node_with_induct_ip_and_unrelated_duct_parts,
#         node_with_induct_rf_and_unrelated_duct_parts,
#         node_with_outduct_rf_and_unrelated_duct_parts
#     ):
#     from sqlalchemy import select, func
#     from app.models import Endpoint, Induct, Outduct
#     from app.api.v1.node.service import get_all_general_info

#     # Cut this in half
#     nodes[1].endpoints = nodes[1].endpoints[:3]
#     session.commit()

#     n_list = [
#         node_without_endpoints,
#         node_with_induct_ip_and_unrelated_duct_parts,
#         node_with_induct_rf_and_unrelated_duct_parts,
#         node_with_outduct_rf_and_unrelated_duct_parts
#     ]
#     n_list.extend(nodes)

#     t_general_info = get_all_general_info(session).all()

#     for n in n_list:
#         node_id = n.node_id
#         for gen_info in t_general_info:
#             if gen_info.node_id == node_id:
#                 gen_info = gen_info
#                 break
#         assert n.allocator_id == gen_info.allocator_id
#         assert n.host.hostname == gen_info.hostname
#         assert n.operator.operator_name == gen_info.operator_name
#         assert session.scalar(
#             select(func.count(Endpoint.service_number))
#             .where(Endpoint.node_id == node_id)
#         ) == gen_info.num_endpoints
#         assert session.scalar(
#             select(func.count(Induct.induct_id))
#             .where(Induct.node_id == node_id)
#         ) == gen_info.num_inducts
#         assert session.scalar(
#             select(func.count(Outduct.outduct_id))
#             .where(Outduct.node_id == node_id)
#         ) == gen_info.num_outducts


def test_create(session: Session, host: Host):
    from sqlalchemy import exc

    from app.api.v1.node.service import create

    # 0 is invalid in our business logic, but convenient b/c our factories
    # don't use it
    # Just leave the other information empty
    t_node = create(session, 0, host_id=host.host_id)
    assert t_node.node_number == 0
    assert t_node.allocator_id == 0  # Default Allocator
    assert t_node in host.nodes
    assert t_node.operator is None
    assert t_node.sdr_config_flags == None
    assert t_node.sdr_wm_size is None
    assert t_node.heap_words is None
    assert t_node.wm_size is None
    assert t_node.node_name is None
    assert t_node.comments is None

    with pytest.raises(exc.IntegrityError):
        create(session, 2**32 + 1, host.host_id)
    session.rollback()


def test_nullify_link_ref(
    session: Session,
    inducts_null_type_with_links: tuple[Induct, Induct, Induct],
    seats_not_ip_with_links: list[Seat],
):
    from app.api.v1.node.service import nullify_link_ref

    i1 = inducts_null_type_with_links[0]
    i2 = inducts_null_type_with_links[1]
    s1 = seats_not_ip_with_links[0]
    s2 = seats_not_ip_with_links[1]

    assert i1.links
    assert i2.links
    assert s1.links
    assert s2.links
    nullify_link_ref(session, i1.node_id)
    session.commit()
    assert not i1.links
    assert i2.links
    assert s1.links
    assert s2.links
    nullify_link_ref(session, s1.node_id)
    session.commit()
    assert not i1.links
    assert i2.links
    assert not s1.links
    assert s2.links


def test_nullify_dest_ref(
    session: Session,
    node_with_inducts_seats: Node,
    induct_ip: InductIp,
    seat_ip: SeatIp,
):
    from app.api.v1.node.service import nullify_dest_ref

    node = node_with_inducts_seats
    for i in node.inducts:
        if i.induct_ip and i.induct_ip.destination:
            assert i.induct_ip.destination_id is not None
    for s in node.seats:
        if s.seat_ip and s.seat_ip.destination:
            assert s.seat_ip.destination_id is not None
    assert induct_ip.destination
    assert seat_ip.destination
    nullify_dest_ref(session, node.node_id, node.host_id)
    session.commit()
    for i in node.inducts:
        if i.induct_ip:
            assert i.induct_ip.destination_id is None
    for s in node.seats:
        if s.seat_ip:
            assert s.seat_ip.destination_id is None
    assert induct_ip.destination
    assert seat_ip.destination


def test_associate_dest_ref(
    session: Session, node_with_ip_inducts_seats_links_host_same_ip: tuple[Node, Host]
):
    from app.api.v1.destination.service import get as dest_get
    from app.api.v1.node.service import associate_dest_ref

    node, host = node_with_ip_inducts_seats_links_host_same_ip
    i1 = node.inducts[0].induct_ip
    i1_dest = i1.destination
    i2 = node.inducts[1].induct_ip
    i2_dest = i2.destination
    i3 = node.inducts[2].induct_ip
    assert i3.destination_id is None
    i4 = node.inducts[3].induct_ip
    i4_dest = i4.destination
    s1 = node.seats[0].seat_ip
    s1_dest = s1.destination
    s2 = node.seats[1].seat_ip
    s2_dest = s2.destination
    s3 = node.seats[2].seat_ip
    assert s3.destination_id is None
    s4 = node.seats[3].seat_ip
    s4_dest = s4.destination

    associate_dest_ref(session, node.node_id, host.host_id)
    for i, d in ((i1, i1_dest), (i2, i2_dest), (s1, s1_dest), (s2, s2_dest)):
        assert i.destination_id != d.destination_id
        new_dest = dest_get(session, i.destination_id)
        assert new_dest.ip_address == d.ip_address
        assert new_dest.registered_name == d.registered_name
        assert new_dest.host_id == host.host_id
    assert i3.destination_id is None
    assert i4.destination_id == i4_dest.destination_id
    assert i4.destination.host_id == node.host_id
    assert s3.destination_id is None
    assert s4.destination_id == s4_dest.destination_id
    assert s4.destination.host_id == node.host_id

    # FK violation b/c *_ip.destination_id is on `host`, but `node` is not
    # under that host.
    with pytest.raises(exc.IntegrityError):
        session.commit()
    session.rollback()


def test_copy_dest_ref(
    session: Session, node_with_ip_inducts_seats_links_host_same_ip: tuple[Node, Host]
):
    from sqlalchemy import and_, select

    from app.api.v1.node.service import copy_dest_ref
    from app.models import Destination

    node, host = node_with_ip_inducts_seats_links_host_same_ip
    i1 = node.inducts[0].induct_ip
    i1_dest = i1.destination
    i2 = node.inducts[1].induct_ip
    i2_dest = i2.destination
    i3 = node.inducts[2].induct_ip
    assert i3.destination_id is None
    i4 = node.inducts[3].induct_ip
    i4_dest = i4.destination
    s1 = node.seats[0].seat_ip
    s1_dest = s1.destination
    s2 = node.seats[1].seat_ip
    s2_dest = s2.destination
    s3 = node.seats[2].seat_ip
    assert s3.destination_id is None
    s4 = node.seats[3].seat_ip
    s4_dest = s4.destination

    for d in (i1_dest, i2_dest, s1_dest, s2_dest):
        assert session.scalar(
            select(Destination).where(
                Destination.host_id == host.host_id,
                and_(
                    Destination.ip_address == d.ip_address,
                    Destination.registered_name == d.registered_name,
                ),
            )
        )

    for d in (i4_dest, s4_dest):
        assert not session.scalar(
            select(Destination).where(
                Destination.host_id == host.host_id,
                and_(
                    Destination.ip_address == d.ip_address,
                    Destination.registered_name == d.registered_name,
                ),
            )
        )

    copy_dest_ref(session, node.node_id, host.host_id)

    for d in (i4_dest, s4_dest):
        assert session.scalar(
            select(Destination).where(
                Destination.host_id == host.host_id,
                and_(
                    Destination.ip_address == d.ip_address,
                    Destination.registered_name == d.registered_name,
                ),
            )
        )


def test_update_no_host(session: Session, node_no_host: Node, operator: Operator):
    from app.api.v1.node.service import update

    node = node_no_host
    node_number = operator.allocated_node_numbers[0].lower
    allocator_id = operator.allocator_id
    sdr_config_flags = 1
    wm_size = 2
    sdr_wm_size = 3
    heap_words = 4
    node_name = 'test_update_no_host name'
    comments = 'test_update_no_host comments'
    update(
        session,
        node.node_id,
        node_number,
        allocator_id,
        operator.operator_id,
        None,
        sdr_config_flags,
        wm_size,
        sdr_wm_size,
        heap_words,
        node_name,
        comments,
    )
    assert node.node_number == node_number
    assert node.allocator_id == allocator_id
    assert node.operator_id == operator.operator_id
    assert node.sdr_config_flags == sdr_config_flags
    assert node.wm_size == wm_size
    assert node.sdr_wm_size == sdr_wm_size
    assert node.heap_words == heap_words
    assert node.node_name == node_name
    assert node.comments == comments


def test_update_nullify_dest(
    session: Session, node_with_ip_inducts_seats_links_host_same_ip: tuple[Node, Host]
):
    from app.api.v1.node.service import update

    node, host = node_with_ip_inducts_seats_links_host_same_ip
    old_host = node.host
    i1 = node.inducts[0].induct_ip
    i1_dest = i1.destination
    i2 = node.inducts[1].induct_ip
    i2_dest = i2.destination
    i3 = node.inducts[2].induct_ip
    i4 = node.inducts[3].induct_ip
    i4_dest = i4.destination
    s1 = node.seats[0].seat_ip
    s1_dest = s1.destination
    s2 = node.seats[1].seat_ip
    s2_dest = s2.destination
    s3 = node.seats[2].seat_ip
    s4 = node.seats[3].seat_ip
    s4_dest = s4.destination

    for r in (i1, i2, i4, s1, s2, s4):
        assert r.destination_id is not None
    for r in (i3, s3):
        assert r.destination_id is None

    node_number = host.operator.allocated_node_numbers[0].lower
    allocator_id = host.operator.allocator_id
    operator_id = host.operator_id

    update(
        session,
        node.node_id,
        node_number,
        allocator_id,
        operator_id,
        host.host_id,
        node.sdr_config_flags,
        node.wm_size,
        node.sdr_wm_size,
        node.heap_words,
        node.node_name,
        node.comments,
        DestinationRefModeEnum.NULLIFY,
    )
    assert node.node_number == node_number
    assert node.allocator_id == allocator_id
    assert node.operator_id == operator_id
    assert node.host_id == host.host_id
    for r in (i1, i2, i3, i4, s1, s2, s3, s4):
        assert r.destination_id is None
    for d in (i1_dest, i2_dest, i4_dest, s1_dest, s2_dest, s4_dest):
        assert d in session
        assert d in old_host.destinations


def test_update_associate_dest(
    session: Session, node_with_ip_inducts_seats_links_host_same_ip: tuple[Node, Host]
):
    from app.api.v1.node.service import update

    node, host = node_with_ip_inducts_seats_links_host_same_ip
    i1 = node.inducts[0].induct_ip
    i1_dest = i1.destination
    i2 = node.inducts[1].induct_ip
    i2_dest = i2.destination
    i3 = node.inducts[2].induct_ip
    assert i3.destination_id is None
    i4 = node.inducts[3].induct_ip
    assert i4.destination_id is not None
    s1 = node.seats[0].seat_ip
    s1_dest = s1.destination
    s2 = node.seats[1].seat_ip
    s2_dest = s2.destination
    s3 = node.seats[2].seat_ip
    assert s3.destination_id is None
    s4 = node.seats[3].seat_ip
    assert s4.destination_id is not None

    node_number = host.operator.allocated_node_numbers[0].lower
    allocator_id = host.operator.allocator_id
    operator_id = host.operator_id

    update(
        session,
        node.node_id,
        node_number,
        allocator_id,
        operator_id,
        host.host_id,
        node.sdr_config_flags,
        node.wm_size,
        node.sdr_wm_size,
        node.heap_words,
        node.node_name,
        node.comments,
        DestinationRefModeEnum.ASSOCIATE,
    )
    assert node.node_number == node_number
    assert node.allocator_id == allocator_id
    assert node.operator_id == operator_id
    assert node.host_id == host.host_id
    for i, d in ((i1, i1_dest), (i2, i2_dest), (s1, s1_dest), (s2, s2_dest)):
        assert i.destination_id != d.destination_id
        new_dest = i.destination
        assert new_dest.ip_address == d.ip_address
        assert new_dest.registered_name == d.registered_name
        assert new_dest.host_id == host.host_id
    for r in (i3, i4, s3, s4):
        assert r.destination_id is None


def test_update_copy_dest(
    session: Session, node_with_ip_inducts_seats_links_host_same_ip: tuple[Node, Host]
):
    from app.api.v1.node.service import update

    node, host = node_with_ip_inducts_seats_links_host_same_ip
    i1 = node.inducts[0].induct_ip
    i1_dest = i1.destination
    i2 = node.inducts[1].induct_ip
    i2_dest = i2.destination
    i3 = node.inducts[2].induct_ip
    assert i3.destination_id is None
    i4 = node.inducts[3].induct_ip
    i4_dest = i4.destination
    s1 = node.seats[0].seat_ip
    s1_dest = s1.destination
    s2 = node.seats[1].seat_ip
    s2_dest = s2.destination
    s3 = node.seats[2].seat_ip
    assert s3.destination_id is None
    s4 = node.seats[3].seat_ip
    s4_dest = s4.destination

    node_number = host.operator.allocated_node_numbers[0].lower
    allocator_id = host.operator.allocator_id
    operator_id = host.operator_id

    update(
        session,
        node.node_id,
        node_number,
        allocator_id,
        operator_id,
        host.host_id,
        node.sdr_config_flags,
        node.wm_size,
        node.sdr_wm_size,
        node.heap_words,
        node.node_name,
        node.comments,
        DestinationRefModeEnum.COPY,
    )
    assert node.node_number == node_number
    assert node.allocator_id == allocator_id
    assert node.operator_id == operator_id
    assert node.host_id == host.host_id
    for i, d in (
        (i1, i1_dest),
        (i2, i2_dest),
        (i4, i4_dest),
        (s1, s1_dest),
        (s2, s2_dest),
        (s4, s4_dest),
    ):
        assert i.destination_id != d.destination_id
        new_dest = i.destination
        assert new_dest.ip_address == d.ip_address
        assert new_dest.registered_name == d.registered_name
        assert new_dest.host_id == host.host_id
    for r in (i3, s3):
        assert r.destination_id is None


def check_copy_node_equality(
    node: Node, copied_node: Node, mode: DestinationRefModeEnum
):
    """Utility function for testing node copying.

    Testing for "associate" mode for destinations lacking an equivalent
    destination on the new host is annoying to generalize, so caller
    of this function has to check that.
    """
    assert node.sdr_config_flags == copied_node.sdr_config_flags
    assert node.wm_size == copied_node.wm_size
    assert node.sdr_wm_size == copied_node.sdr_wm_size
    assert node.heap_words == copied_node.heap_words
    assert node.node_name == copied_node.node_name
    assert node.comments == copied_node.comments
    assert node.created_at != copied_node.created_at
    assert node.modified_at != copied_node.modified_at
    for e, e_copy in zip(node.ipn_endpoints, copied_node.ipn_endpoints):
        assert e.service_number == e_copy.service_number
        assert e.application == e_copy.application
        assert e.disposition == e_copy.disposition
    for e, e_copy in zip(node.imc_endpoints, copied_node.imc_endpoints):
        assert e.group_number == e_copy.group_number
        assert e.application == e_copy.application
        assert e.disposition == e_copy.disposition
    for p, p_copy in zip(node.cl_protocols, copied_node.cl_protocols):
        assert p.cl_protocol_name == p_copy.cl_protocol_name
        assert p.cl_protocol_class == p_copy.cl_protocol_class
    for i, i_copy in zip(node.inducts, copied_node.inducts):
        assert i.type == i.type
        assert i.cl_protocol_name == i_copy.cl_protocol_name
        assert i.duct_name == i_copy.duct_name
        assert i.cli_command == i_copy.cli_command
        assert i.uses_ltp == i_copy.uses_ltp
        assert len(i.seats) == len(i_copy.seats)
        if node.host != copied_node.host:
            assert not i_copy.links
        elif node.host and node.host == copied_node.host:
            assert i.links == i_copy.links
        if i.induct_ip:
            assert i_copy.induct_ip
            if i.induct_ip.destination:
                if node.host and not copied_node.host:
                    assert not i_copy.induct_ip.destination
                elif node.host == copied_node.host:
                    assert i.induct_ip.destination == i_copy.induct_ip.destination
                elif node.host and copied_node.host:
                    if mode == DestinationRefModeEnum.NULLIFY:
                        assert not i_copy.induct_ip.destination
                    elif mode == DestinationRefModeEnum.COPY:
                        assert i_copy.induct_ip.destination
                        assert (
                            i.induct_ip.destination.ip_address
                            == i_copy.induct_ip.destination.ip_address
                        )
                        assert (
                            i.induct_ip.destination.registered_name
                            == i_copy.induct_ip.destination.registered_name
                        )
            assert i.induct_ip.port_number == i_copy.induct_ip.port_number
    for s, s_copy in zip(node.seats, copied_node.seats):
        assert s.type == s.type
        assert s.lsi_command == s_copy.lsi_command
        assert len(s.inducts) == len(s_copy.inducts)
        if node.host != copied_node.host:
            assert not s_copy.links
        elif node.host and node.host == copied_node.host:
            assert s.links == s_copy.links
        if s.seat_ip:
            assert s_copy.seat_ip
            if s.seat_ip.destination:
                if node.host and not copied_node.host:
                    assert not s_copy.seat_ip.destination
                elif node.host == copied_node.host:
                    assert s.seat_ip.destination == s_copy.seat_ip.destination
                elif node.host and copied_node.host:
                    if mode == DestinationRefModeEnum.NULLIFY:
                        assert not s_copy.seat_ip.destination
                    elif mode == DestinationRefModeEnum.COPY:
                        assert s_copy.seat_ip.destination
                        assert (
                            s.seat_ip.destination.ip_address
                            == s_copy.seat_ip.destination.ip_address
                        )
                        assert (
                            s.seat_ip.destination.registered_name
                            == s_copy.seat_ip.destination.registered_name
                        )
            assert s.seat_ip.port_number == s_copy.seat_ip.port_number


def test_copy(session: Session, node_full_and_host: tuple[Node, Host]):
    from app.api.v1.node.service import copy

    node, host = node_full_and_host
    node_number = host.operator.allocated_node_numbers[0].lower
    allocator_id = host.operator.allocator_id
    operator_id = host.operator_id
    mode = DestinationRefModeEnum.COPY

    copied_node = copy(
        session,
        node.node_id,
        allocator_id,
        node_number,
        host.host_id,
        operator_id,
        mode,
    )
    assert copied_node.node_number == node_number
    assert copied_node.allocator_id == allocator_id
    assert copied_node.operator_id == operator_id
    assert copied_node.host_id == host.host_id
    check_copy_node_equality(node, copied_node, mode)


def test_copy_associate(session: Session, node_full_and_host: tuple[Node, Host]):
    from app.api.v1.node.service import copy

    node, host = node_full_and_host
    node_number = host.operator.allocated_node_numbers[0].lower
    allocator_id = host.operator.allocator_id
    operator_id = host.operator_id
    induct_dest_no_equivalent = node.inducts[3].induct_ip.destination
    seat_dest_no_equivalent = node.seats[3].seat_ip.destination
    mode = DestinationRefModeEnum.ASSOCIATE

    copied_node = copy(
        session,
        node.node_id,
        allocator_id,
        node_number,
        host.host_id,
        operator_id,
        mode,
    )
    assert copied_node.node_number == node_number
    assert copied_node.allocator_id == allocator_id
    assert copied_node.operator_id == operator_id
    assert copied_node.host_id == host.host_id
    check_copy_node_equality(node, copied_node, mode)
    for i, i_copy in zip(node.inducts, copied_node.inducts):
        if i.induct_ip and i.induct_ip.destination == induct_dest_no_equivalent:
            assert not i_copy.induct_ip.destination
    for s, s_copy in zip(node.seats, copied_node.seats):
        if s.seat_ip and s.seat_ip.destination == seat_dest_no_equivalent:
            assert not s_copy.seat_ip.destination


def test_copy_same_host(session: Session, node_full_and_host: tuple[Node, Host]):
    from app.api.v1.node.service import copy

    node, _ = node_full_and_host
    node_number = node.operator.allocated_node_numbers[0].lower
    while node_number == node.node_number:
        node_number += 1
    mode = DestinationRefModeEnum.COPY

    copied_node = copy(
        session,
        node.node_id,
        node.allocator_id,
        node_number,
        node.host_id,
        node.operator_id,
        mode,
    )
    assert copied_node.node_number == node_number
    assert copied_node.allocator_id == node.allocator_id
    assert copied_node.operator_id == node.operator_id
    assert copied_node.host_id == node.host_id
    check_copy_node_equality(node, copied_node, mode)


def test_copy_null_host(session: Session, node_full_and_host: tuple[Node, Host]):
    from app.api.v1.node.service import copy

    node, _ = node_full_and_host
    node_number = node.operator.allocated_node_numbers[0].lower
    while node_number == node.node_number:
        node_number += 1
    mode = (DestinationRefModeEnum.NULLIFY,)

    copied_node = copy(
        session,
        node.node_id,
        node.allocator_id,
        node_number,
        None,
        node.operator_id,
        mode,
    )
    assert copied_node.node_number == node_number
    assert copied_node.allocator_id == node.allocator_id
    assert copied_node.operator_id == node.operator_id
    assert copied_node.host_id is None
    check_copy_node_equality(node, copied_node, mode)
    for i, i_copy in zip(node.inducts, copied_node.inducts):
        if i.induct_ip:
            assert not i_copy.induct_ip.destination
    for s, s_copy in zip(node.seats, copied_node.seats):
        if s.seat_ip:
            assert not s_copy.seat_ip.destination


def test_delete(session: Session, node: Node):
    from sqlalchemy import select

    from app.api.v1.node.service import delete, get
    from app.models import Node
    from tests.util import verify_soft_deletion

    node_id = node.node_id
    jsonb = get_as_jsonb(session, select(Node).where(Node.node_id == node.node_id))
    delete(session, node_id)
    assert not get(session, node_id)
    assert verify_soft_deletion(session, jsonb)


def test_list_contacts(session: Session, node_with_contacts: Node):
    from app.api.v1.node.service import list_contacts

    node = node_with_contacts
    contacts = []
    page = list_contacts(session, node.node_id, 1, None)
    contacts.extend([_ for (_,) in page])
    while page.paging.has_next:
        page = list_contacts(session, node.node_id, 1, page.paging.bookmark_next)
        contacts.extend([_ for (_,) in page])

    for c in node.contacts:
        assert c in contacts


def test_associate_contact(session: Session, node: Node, contact_with_details: Contact):
    from app.api.v1.node.service import associate_contact

    contact = contact_with_details
    associate_contact(session, node.node_id, contact.contact_id)
    assert contact in node.contacts
    assert node in contact.nodes


def test_dissociate_contact(
    session: Session, node_with_contacts: Node, operator: Operator
):
    from sqlalchemy import select

    from app.api.v1.node.service import dissociate_contact
    from app.models import Contact, node_contact
    from tests.util import verify_soft_deletion

    n = node_with_contacts
    c1 = n.contacts[0]
    c2 = n.contacts[1]
    o = operator
    o.contacts.append(c2)
    session.commit()

    assert len(n.contacts) > 1
    assert c1 in n.contacts
    jsonb = get_as_jsonb(
        session,
        select(node_contact).where(
            node_contact.c.node_id == n.node_id,
            node_contact.c.contact_id == c1.contact_id,
        ),
    )
    dissociate_contact(session, n.node_id, c1.contact_id)
    assert c1 not in n.contacts
    assert n.contacts  # not empty
    assert c1 not in session.scalars(select(Contact)).all()
    assert c2 in session.scalars(select(Contact)).all()
    assert verify_soft_deletion(session, jsonb)

    # But if the contact is still associated with an entity, it still exists
    assert c2 in o.contacts
    jsonb = get_as_jsonb(
        session,
        select(node_contact).where(
            node_contact.c.node_id == n.node_id,
            node_contact.c.contact_id == c2.contact_id,
        ),
    )
    dissociate_contact(session, n.node_id, c2.contact_id)
    assert c2 in o.contacts
    assert c2 in session.scalars(select(Contact)).all()
    assert verify_soft_deletion(session, jsonb)


def test_contact_is_associated(
    session: Session, node: Node, contacts_with_details: list[Contact]
):
    from sqlalchemy import select

    from app.api.v1.node.service import contact_is_associated
    from app.models import node_contact
    from tests.util import verify_soft_deletion

    n1 = node
    c1 = contacts_with_details[0]
    c2 = contacts_with_details[1]
    n1.contacts.append(c1)
    n1.contacts.append(c2)
    session.commit()

    assert contact_is_associated(session, n1.node_id, c1.contact_id)
    assert contact_is_associated(session, n1.node_id, c2.contact_id)
    jsonb = get_as_jsonb(
        session,
        select(node_contact).where(
            node_contact.c.node_id == n1.node_id,
            node_contact.c.contact_id == c1.contact_id,
        ),
    )
    n1.contacts.remove(c1)
    session.commit()
    assert not contact_is_associated(session, n1.node_id, c1.contact_id)
    assert contact_is_associated(session, n1.node_id, c2.contact_id)
    assert verify_soft_deletion(session, jsonb)

    jsonb = get_as_jsonb(
        session,
        select(node_contact).where(
            node_contact.c.node_id == n1.node_id,
            node_contact.c.contact_id == c2.contact_id,
        ),
    )
    n1.contacts.remove(c2)
    session.commit()
    assert not contact_is_associated(session, n1.node_id, c1.contact_id)
    assert not contact_is_associated(session, n1.node_id, c2.contact_id)
    assert verify_soft_deletion(session, jsonb)

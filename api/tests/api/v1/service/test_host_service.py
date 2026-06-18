from __future__ import annotations

from typing import TYPE_CHECKING

from app.api.v1.host.service import get as host_get
from app.api.v1.node.service import get as node_get
from tests.util import get_as_jsonb

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.api.v1.node.schemas import NodeCopyForHostSchema
    from app.models import Allocator, Contact, Host, Link, Node, Operator


def test_get(session: Session, host: Host):
    from app.api.v1.host.service import get

    t_host = get(session, host.host_id)
    assert host == t_host


def test_query(session: Session, hosts: list[Host]):
    from app.api.v1.host.service import query

    t_hosts = []
    page = query(session, 1, None)
    t_hosts.extend([_ for (_,) in page])
    while page.paging.has_next:
        page = query(session, 1, page.paging.bookmark_next)
        t_hosts.extend([_ for (_,) in page])

    for h in hosts:
        assert h in t_hosts


def test_create(session: Session):
    from sqlalchemy import select

    from app.api.v1.host.service import create
    from app.models import Host

    hostname = 'Test Create Service Host'
    # Only required field is hostname
    t_host = create(session, hostname)
    assert t_host.hostname == hostname
    assert not t_host.operator
    assert t_host in session.scalars(select(Host)).all()


def test_update(session: Session, host: Host, node: Node, operator: Operator):
    from app.api.v1.host.service import update
    from app.models import NewlineEnum

    hostname = 'Test Update Service Host'
    host_description = 'test_update() service test'
    scid = 1
    word_size = 64
    newline = NewlineEnum.LF.value
    t_host = update(
        session,
        host.host_id,
        hostname,
        host_description,
        None,
        scid,
        word_size,
        newline,
    )
    assert t_host == host
    assert t_host.hostname == hostname
    assert t_host.host_description == host_description
    assert t_host.sana_scid == scid
    assert t_host.word_size == word_size
    assert t_host.newline == newline

    # Updating host.operator_id to null will remove node's operator
    operator = node.operator
    assert node.operator
    update(
        session,
        node.host_id,
        node.host.hostname,
        host_description,
        None,
        scid,
        word_size,
        newline,
    )
    assert not node.operator

    # Updating host.operator_id to a not null value will not update node's operator
    # if the node does not have an operator
    update(
        session,
        node.host_id,
        node.host.hostname,
        host_description,
        operator.operator_id,
        scid,
        word_size,
        newline,
    )
    assert not node.operator


def check_copied_host_equality(
    db_session: Session,
    host_id: int,
    copied_host_id: int,
    input_nodes: list[NodeCopyForHostSchema],
):
    """Asserts that host children (destinations and links) were copied,
    and new nodes refer to the new host children.

    This function assumes that the ordering for relationships in
    `old_host` and `copied_host` match (e.g., zipping
    `old_host.destinations` and `copied_host.destinations` should pair
    the old destinations with its copy).

    Pass the same `input_nodes` that was passed to `copy()`.
    """

    def _check_link_equality(old_link: Link, copied_link: Link):
        assert old_link.type == copied_link.type
        assert old_link.direction == copied_link.direction
        if old_link.link_rf:
            assert copied_link.link_rf
            assert old_link.link_rf.band == copied_link.link_rf.band

    old_host = host_get(db_session, host_id)
    copied_host = host_get(db_session, copied_host_id)
    assert old_host.hostname == copied_host.hostname
    assert old_host.host_description == copied_host.host_description
    assert old_host.sana_scid == copied_host.sana_scid
    assert old_host.word_size == copied_host.word_size
    assert old_host.newline == copied_host.newline
    for d, d_copy in zip(old_host.destinations, copied_host.destinations):
        assert d.ip_address == d_copy.ip_address
        assert d.registered_name == d_copy.registered_name
    for l, l_copy in zip(old_host.links, copied_host.links):
        _check_link_equality(l, l_copy)

    for input_n, n_copy in zip(input_nodes, copied_host.nodes):
        n = node_get(db_session, input_n.node_id)
        assert n_copy.node_number == input_n.node_number
        if n_copy.operator_id is None:
            assert n_copy.allocator_id == input_n.allocator_id
        assert n_copy.operator_id == input_n.operator_id
        assert n.wm_size == n_copy.wm_size
        assert n.sdr_wm_size == n_copy.sdr_wm_size
        assert n.heap_words == n_copy.heap_words
        assert n.node_name == n_copy.node_name
        assert n.comments == n_copy.comments
        assert n.created_at != n_copy.created_at
        assert n.modified_at != n_copy.modified_at
        assert len(n.ipn_endpoints) == len(n_copy.ipn_endpoints)
        for e, e_copy in zip(n.ipn_endpoints, n_copy.ipn_endpoints):
            assert e.service_number == e_copy.service_number
            assert e.application == e_copy.application
            assert e.disposition == e_copy.disposition
        assert len(n.imc_endpoints) == len(n_copy.imc_endpoints)
        for e, e_copy in zip(n.imc_endpoints, n_copy.imc_endpoints):
            assert e.group_number == e_copy.group_number
            assert e.application == e_copy.application
            assert e.disposition == e_copy.disposition
        assert len(n.cl_protocols) == len(n_copy.cl_protocols)
        for p, p_copy in zip(n.cl_protocols, n_copy.cl_protocols):
            assert p.cl_protocol_name == p_copy.cl_protocol_name
            assert p.cl_protocol_class == p_copy.cl_protocol_class
        assert len(n.inducts) == len(n_copy.inducts)
        for i, i_copy in zip(n.inducts, n_copy.inducts):
            assert i.type == i.type
            assert i.cl_protocol_name == i_copy.cl_protocol_name
            assert i.duct_name == i_copy.duct_name
            assert i.cli_command == i_copy.cli_command
            assert i.uses_ltp == i_copy.uses_ltp
            assert len(i.seats) == len(i_copy.seats)
            for l, l_copy in zip(i.links, i_copy.links):
                _check_link_equality(l, l_copy)
            if i.induct_ip:
                assert i_copy.induct_ip
                if i.induct_ip.destination:
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
        assert len(n.seats) == len(n_copy.seats)
        for s, s_copy in zip(n.seats, n_copy.seats):
            assert s.type == s.type
            assert s.lsi_command == s_copy.lsi_command
            assert len(s.inducts) == len(s_copy.inducts)
            for l, l_copy in zip(s.links, s_copy.links):
                _check_link_equality(l, l_copy)
            if s.seat_ip:
                assert s_copy.seat_ip
                if s.seat_ip.destination:
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


def test_copy(session: Session, host_with_full_nodes: Host, allocator: Allocator):
    from app.api.v1.host.service import copy
    from app.api.v1.node.schemas import NodeCopyForHostSchema

    host = host_with_full_nodes
    in_nodes = [
        NodeCopyForHostSchema(
            node_id=n.node_id,
            node_number=n.node_number + 1,
            allocator_id=allocator.allocator_id,
            operator_id=None,
        )
        for n in host.nodes
    ]
    copied_host = copy(session, host.host_id, None, in_nodes)
    check_copied_host_equality(session, host.host_id, copied_host.host_id, in_nodes)


def test_delete(session: Session, host: Host, node: Node):
    from sqlalchemy import select

    from app.api.v1.host.service import delete, get
    from app.models import Host, Node
    from tests.util import verify_soft_deletion

    host_id = host.host_id
    jsonb = get_as_jsonb(session, select(Host).where(Host.host_id == host_id))
    delete(session, host_id)
    assert not get(session, host_id)
    assert verify_soft_deletion(session, jsonb)

    # Node still exists after deleting host
    host_id = node.host_id
    node_id = node.node_id
    delete(session, host_id)
    assert not get(session, host_id)
    assert session.scalar(select(Node).where(Node.node_id == node_id))


def test_list_contacts(session: Session, host_with_contacts: Host):
    from app.api.v1.host.service import list_contacts

    host = host_with_contacts
    contacts = []
    page = list_contacts(session, host.host_id, 1, None)
    contacts.extend([_ for (_,) in page])
    while page.paging.has_next:
        page = list_contacts(session, host.host_id, 1, page.paging.bookmark_next)
        contacts.extend([_ for (_,) in page])

    for c in host.contacts:
        assert c in contacts


def test_associate_contact(session: Session, host: Host, contact_with_details: Contact):
    from app.api.v1.host.service import associate_contact

    contact = contact_with_details
    associate_contact(session, host.host_id, contact.contact_id)
    assert contact in host.contacts
    assert host in contact.hosts


def test_dissociate_contact(
    session: Session, host_with_contacts: Host, operator: Operator
):
    from sqlalchemy import select

    from app.api.v1.host.service import dissociate_contact
    from app.models import Contact, host_contact
    from tests.util import verify_soft_deletion

    h = host_with_contacts
    c1 = h.contacts[0]
    c2 = h.contacts[1]
    o = operator
    o.contacts.append(c2)
    session.commit()

    assert len(h.contacts) > 1
    assert c1 in h.contacts
    jsonb = get_as_jsonb(
        session,
        select(host_contact).where(
            host_contact.c.host_id == h.host_id,
            host_contact.c.contact_id == c1.contact_id,
        ),
    )
    dissociate_contact(session, h.host_id, c1.contact_id)
    assert c1 not in h.contacts
    assert h.contacts  # not empty
    assert c1 not in session.scalars(select(Contact)).all()
    assert c2 in session.scalars(select(Contact)).all()
    assert verify_soft_deletion(session, jsonb)

    # But if the contact is still associated with an entity, it still exists
    assert c2 in o.contacts
    jsonb = get_as_jsonb(
        session,
        select(host_contact).where(
            host_contact.c.host_id == h.host_id,
            host_contact.c.contact_id == c2.contact_id,
        ),
    )
    dissociate_contact(session, h.host_id, c2.contact_id)
    assert c2 in o.contacts
    assert c2 in session.scalars(select(Contact)).all()
    assert verify_soft_deletion(session, jsonb)


def test_contact_is_associated(
    session: Session, host: Host, contacts_with_details: list[Contact]
):
    from sqlalchemy import select

    from app.api.v1.host.service import contact_is_associated
    from app.models import host_contact
    from tests.util import verify_soft_deletion

    h1 = host
    c1 = contacts_with_details[0]
    c2 = contacts_with_details[1]
    h1.contacts.append(c1)
    h1.contacts.append(c2)
    session.commit()

    assert contact_is_associated(session, h1.host_id, c1.contact_id)
    assert contact_is_associated(session, h1.host_id, c2.contact_id)
    jsonb = get_as_jsonb(
        session,
        select(host_contact).where(
            host_contact.c.host_id == h1.host_id,
            host_contact.c.contact_id == c1.contact_id,
        ),
    )
    h1.contacts.remove(c1)
    session.commit()
    assert not contact_is_associated(session, h1.host_id, c1.contact_id)
    assert contact_is_associated(session, h1.host_id, c2.contact_id)
    assert verify_soft_deletion(session, jsonb)

    jsonb = get_as_jsonb(
        session,
        select(host_contact).where(
            host_contact.c.host_id == h1.host_id,
            host_contact.c.contact_id == c2.contact_id,
        ),
    )
    h1.contacts.remove(c2)
    session.commit()
    assert not contact_is_associated(session, h1.host_id, c1.contact_id)
    assert not contact_is_associated(session, h1.host_id, c2.contact_id)
    assert verify_soft_deletion(session, jsonb)

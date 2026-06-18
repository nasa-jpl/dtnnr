from __future__ import annotations

from typing import TYPE_CHECKING

from tests.util import get_as_jsonb

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import ClProtocol, InductIp, Node


def test_get(session: Session, cl_protocol: ClProtocol):
    from app.api.v1.cl_protocol.service import get

    t_cl_protocol = get(session, cl_protocol.cl_protocol_id)
    assert t_cl_protocol == cl_protocol


def test_get_by_details(session: Session, cl_protocol: ClProtocol):
    from app.api.v1.cl_protocol.service import get_by_details

    t_cl_protocol = get_by_details(
        session,
        cl_protocol.node_id,
        cl_protocol.cl_protocol_name,
    )
    assert t_cl_protocol == cl_protocol


def test_inducts_depend_on_cl_protocol(
    session: Session, induct_ip: InductIp, cl_protocol: ClProtocol
):
    from app.api.v1.cl_protocol.service import inducts_depend_on_cl_protocol

    assert inducts_depend_on_cl_protocol(session, induct_ip.induct.cl_protocol_id)
    assert not inducts_depend_on_cl_protocol(session, cl_protocol.cl_protocol_id)


def test_list_cl_protocols(session: Session, node_with_cl_protocols: Node):
    from app.api.v1.cl_protocol.service import list_cl_protocols

    node = node_with_cl_protocols
    cl_protocols = []
    page = list_cl_protocols(session, node.node_id, 1, None)
    cl_protocols.extend([_ for (_,) in page])
    while page.paging.has_next:
        page = list_cl_protocols(session, node.node_id, 1, page.paging.bookmark_next)
        cl_protocols.extend([_ for (_,) in page])

    for p in node.cl_protocols:
        assert p in cl_protocols


def test_create(session: Session, node: Node):
    from app.api.v1.cl_protocol.service import create

    # `node` fixture shouldn't give us a CL protocol, so we should be
    # safe using any cl_protocol_name
    t_cl_protocol = create(session, node.node_id, 'foo', 8)
    assert t_cl_protocol.node == node
    assert t_cl_protocol in node.cl_protocols
    assert t_cl_protocol.cl_protocol_name == 'foo'
    assert t_cl_protocol.cl_protocol_class == 8


def test_update(session: Session, cl_protocol: ClProtocol):
    from app.api.v1.cl_protocol.service import update

    old_name = cl_protocol.cl_protocol_name
    new_name = 'abcdefghijklm'
    assert old_name != new_name
    old_class = cl_protocol.cl_protocol_class
    if old_class == 10:
        new_class = 2
    else:
        new_class = 10
    assert new_class != old_class
    t_cl_protocol = update(session, cl_protocol.cl_protocol_id, new_name, new_class)
    assert t_cl_protocol == cl_protocol
    assert t_cl_protocol.cl_protocol_name == new_name
    assert t_cl_protocol.cl_protocol_class == new_class


def test_delete(session: Session, cl_protocol: ClProtocol):
    from sqlalchemy import select

    from app.api.v1.cl_protocol.service import delete, get
    from app.models import ClProtocol
    from tests.util import verify_soft_deletion

    primary_key = cl_protocol.cl_protocol_id
    jsonb = get_as_jsonb(
        session,
        select(ClProtocol).where(
            ClProtocol.cl_protocol_id == cl_protocol.cl_protocol_id
        ),
    )
    delete(session, primary_key)
    assert not get(session, primary_key)
    assert verify_soft_deletion(session, jsonb)

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import exc, select

from tests.util import get_as_jsonb

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import EndpointIMC, Node


def test_get_ipn(session: Session, node: Node):
    from app.api.v1.endpoint.service import get_ipn

    endpoint = node.ipn_endpoints[0]
    t_endpoint = get_ipn(session, endpoint.node_id, endpoint.service_number)
    assert endpoint == t_endpoint


def test_get_imc(session: Session, endpoint_imc: EndpointIMC):
    from app.api.v1.endpoint.service import get_imc

    t_endpoint = get_imc(session, endpoint_imc.node_id, endpoint_imc.group_number)
    assert t_endpoint == endpoint_imc


def test_list_ipn(session: Session, node_max_and_one_ipn_endpoints: Node):
    from app.api.v1.endpoint.service import list_ipn

    node = node_max_and_one_ipn_endpoints
    endpoints = []
    page = list_ipn(session, node.node_id, 1, None)
    endpoints.extend([_ for (_,) in page])
    while page.paging.has_next:
        page = list_ipn(session, node.node_id, 1, page.paging.bookmark_next)
        endpoints.extend([_ for (_,) in page])

    for e in node.ipn_endpoints:
        assert e in endpoints


def test_list_imc(session: Session, node_max_and_one_imc_endpoints: Node):
    from app.api.v1.endpoint.service import list_imc

    node = node_max_and_one_imc_endpoints
    endpoints = []
    page = list_imc(session, node.node_id, 1, None)
    endpoints.extend([_ for (_,) in page])
    while page.paging.has_next:
        page = list_imc(session, node.node_id, 1, page.paging.bookmark_next)
        endpoints.extend([_ for (_,) in page])

    for e in node.imc_endpoints:
        assert e in endpoints


def test_replace_ipn(
    session: Session, node: Node, node_max_and_one_ipn_endpoints: Node
):
    from app.api.v1.endpoint.schemas import EndpointIPNReplaceSchema
    from app.api.v1.endpoint.service import replace_ipn

    old_endpoints = node.ipn_endpoints
    new_endpoints = [
        EndpointIPNReplaceSchema(
            service_number=e.service_number,
            application=e.application,
            disposition=e.disposition,
        )
        for e in node_max_and_one_ipn_endpoints.ipn_endpoints
    ]
    replace_ipn(session, node.node_id, new_endpoints)
    assert node.ipn_endpoints != old_endpoints
    assert new_endpoints == [
        EndpointIPNReplaceSchema(
            service_number=e.service_number,
            application=e.application,
            disposition=e.disposition,
        )
        for e in node.ipn_endpoints
    ]


def test_replace_ipn_no_change(session: Session, node: Node):
    from app.api.v1.endpoint.schemas import EndpointIPNReplaceSchema
    from app.api.v1.endpoint.service import replace_ipn

    old_endpoints = node.ipn_endpoints
    new_endpoints = [
        EndpointIPNReplaceSchema(
            service_number=e.service_number,
            application=e.application,
            disposition=e.disposition,
        )
        for e in old_endpoints
    ]
    old_modified_at = node.modified_at
    replace_ipn(session, node.node_id, new_endpoints)
    assert node.ipn_endpoints == old_endpoints
    assert old_modified_at == node.modified_at


def test_replace_imc(
    session: Session, node: Node, node_max_and_one_imc_endpoints: Node
):
    from app.api.v1.endpoint.schemas import EndpointIMCReplaceSchema
    from app.api.v1.endpoint.service import replace_imc

    old_endpoints = node.imc_endpoints
    new_endpoints = [
        EndpointIMCReplaceSchema(
            group_number=e.group_number,
            application=e.application,
            disposition=e.disposition,
        )
        for e in node_max_and_one_imc_endpoints.imc_endpoints
    ]
    replace_imc(session, node.node_id, new_endpoints)
    assert node.imc_endpoints != old_endpoints
    assert new_endpoints == [
        EndpointIMCReplaceSchema(
            group_number=e.group_number,
            application=e.application,
            disposition=e.disposition,
        )
        for e in node.imc_endpoints
    ]


def test_replace_imc_no_change(session: Session, node_with_imc_endpoints: Node):
    from app.api.v1.endpoint.schemas import EndpointIMCReplaceSchema
    from app.api.v1.endpoint.service import replace_imc

    node = node_with_imc_endpoints
    old_endpoints = node.imc_endpoints
    new_endpoints = [
        EndpointIMCReplaceSchema(
            group_number=e.group_number,
            application=e.application,
            disposition=e.disposition,
        )
        for e in old_endpoints
    ]
    old_modified_at = node.modified_at
    replace_imc(session, node.node_id, new_endpoints)
    assert node.imc_endpoints == old_endpoints
    assert old_modified_at == node.modified_at


def test_create_ipn(session: Session, node: Node):
    from app.api.v1.endpoint.service import create_ipn

    # Our factories should never generate service number 1
    t_endpoint = create_ipn(session, node.node_id, 1)
    assert t_endpoint.node_id == node.node_id
    assert t_endpoint.service_number == 1
    assert t_endpoint.disposition == 'x'  # default value
    assert t_endpoint.application == None


def test_create_imc(session: Session, node: Node):
    from app.api.v1.endpoint.service import create_imc

    # Our factories should never generate group number 128
    t_endpoint = create_imc(session, node.node_id, 1)
    assert t_endpoint.node_id == node.node_id
    assert t_endpoint.group_number == 1
    assert t_endpoint.disposition == 'x'  # default value
    assert t_endpoint.application == None


def test_update_ipn(session: Session, node: Node):
    from app.api.v1.endpoint.service import update_ipn

    # Our factory should generate 7 endpoints
    endpoint = node.ipn_endpoints[0]
    disposition = 'x' if endpoint.disposition == 'q' else 'q'
    # Our factory should give the endpoint an application
    application = endpoint.application[::-1]
    t_endpoint = update_ipn(
        session, endpoint.node_id, endpoint.service_number, disposition, application
    )
    assert t_endpoint == endpoint
    assert endpoint.disposition == disposition
    assert endpoint.application == application

    # TODO: Our factories are too hardcoded. EndpointFactory goes
    # from 128 to 2^16 - 1. While NodeFactory generates endpoints
    # with service numbers 3, 65, 99, 127.
    # Given a node from NodeFactory, we can update to 32
    new_service_number = 32
    t_endpoint = update_ipn(
        session,
        endpoint.node_id,
        endpoint.service_number,
        endpoint.disposition,
        endpoint.application,
        new_service_number=new_service_number,
    )
    assert t_endpoint == endpoint
    assert endpoint.service_number == new_service_number

    used_service_number = node.ipn_endpoints[1].service_number
    with pytest.raises(exc.IntegrityError):
        t_endpoint = update_ipn(
            session,
            endpoint.node_id,
            endpoint.service_number,
            endpoint.disposition,
            endpoint.application,
            new_service_number=used_service_number,
        )
    session.rollback()
    assert endpoint.service_number != used_service_number


def test_update_imc(session: Session, endpoint_imc: EndpointIMC):
    from app.api.v1.endpoint.service import update_imc

    endpoint = endpoint_imc
    disposition = 'x' if endpoint.disposition == 'q' else 'q'
    # Our factory should give the endpoint an application
    application = endpoint.application[::-1]
    t_endpoint = update_imc(
        session, endpoint.node_id, endpoint.group_number, disposition, application
    )
    assert t_endpoint == endpoint
    assert endpoint.disposition == disposition
    assert endpoint.application == application

    # EndpointIMCFactory group number is in [128, 2^16 - 1]
    new_group_number = 127
    t_endpoint = update_imc(
        session,
        endpoint.node_id,
        endpoint.group_number,
        endpoint.disposition,
        endpoint.application,
        new_group_number=new_group_number,
    )
    assert t_endpoint == endpoint
    assert endpoint.group_number == new_group_number


def test_delete_ipn(session: Session, node: Node):
    from app.api.v1.endpoint.service import delete_ipn, get_ipn
    from app.models import EndpointIPN
    from tests.util import verify_soft_deletion

    # Our factory should generate 7 endpoints
    service_number = node.ipn_endpoints[0].service_number
    jsonb = get_as_jsonb(
        session,
        select(EndpointIPN).where(
            EndpointIPN.node_id == node.node_id,
            EndpointIPN.service_number == service_number,
        ),
    )
    delete_ipn(session, node.node_id, service_number)
    assert not get_ipn(session, node.node_id, service_number)
    assert verify_soft_deletion(session, jsonb)


def test_delete_imc(session: Session, endpoint_imc: EndpointIMC):
    from app.api.v1.endpoint.service import delete_imc, get_imc
    from app.models import EndpointIMC
    from tests.util import verify_soft_deletion

    node_id = endpoint_imc.node_id
    group_num = endpoint_imc.group_number
    jsonb = get_as_jsonb(
        session,
        select(EndpointIMC).where(
            EndpointIMC.node_id == node_id, EndpointIMC.group_number == group_num
        ),
    )
    delete_imc(session, node_id, group_num)
    assert not get_imc(session, node_id, group_num)
    assert verify_soft_deletion(session, jsonb)

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec
import pytest

from app.api.v1.cl_protocol.schemas import (
    protocol_class_arr_to_int,
    protocol_class_int_to_arr,
    to_cl_protocol_without_node_id_schema,
)
from app.api.v1.destination.schemas import process_destination_value
from app.api.v1.endpoint.schemas import (
    to_endpoint_imc_schema,
    to_endpoint_ipn_schema,
    to_imc_uri,
    to_ipn_uri,
)
from app.api.v1.induct.schemas import DuctNameTagEnum, to_induct_without_node_id_schema
from app.api.v1.induct.views import cli_p_name_dict
from app.api.v1.node.schemas import (
    NodeSchema,
    config_flags_arr_to_int,
    config_flags_int_to_arr,
    to_node_schema,
)
from app.api.v1.node.service import DestinationRefModeEnum
from app.api.v1.node.service import get as node_get
from app.api.v1.seat.schemas import to_seat_without_node_id_schema
from app.config import API_V1_PATH, MAX_PAGE_SIZE
from app.fields import (
    ALLOCATOR_ID_MAX,
    CL_PROTOCOL_ID_MAX,
    DESTINATION_ID_MAX,
    GROUP_NUMBER_MAX,
    HEAP_WORDS_MAX,
    HOST_ID_MAX,
    NODE_ID_MAX,
    NODE_NUMBER_MAX,
    OPERATOR_ID_MAX,
    PORT_NUMBER_MAX,
    SDR_WM_SIZE_MAX,
    SERVICE_NUMBER_MAX,
    WM_SIZE_MAX,
)
from app.models import (
    cli_command_with_required_protocol_name,
    no_duct_name_known_cli_not_ip,
)
from tests.api.v1.service.test_node_service import check_copy_node_equality
from tests.util import (
    check_invalid_page_token_different_url,
    check_invalid_page_token_query,
    check_page_size,
    check_paginated_request_validation,
    check_query_request_validation,
    collect_paginated_data,
)

if TYPE_CHECKING:
    from litestar import Litestar
    from litestar.testing import TestClient
    from sqlalchemy.orm import Session

    from app.models import (
        Allocator,
        ClProtocol,
        Destination,
        Host,
        InductIp,
        Node,
        Operator,
        SeatIp,
    )

node_decoder = msgspec.json.Decoder(type=NodeSchema, strict=False)
path_prefix = f'{API_V1_PATH}/nodes'


def test_get_node(client: TestClient[Litestar], node: Node):
    response = client.get(f'{path_prefix}/{node.node_id}')
    assert response.status_code == 200
    assert node_decoder.decode(response.content) == to_node_schema(node)


def test_get_node_not_found(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/0')
    assert response.status_code == 404
    assert 'ID 0 does not exist' in response.json()['detail']


def test_get_node_validation(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/{NODE_ID_MAX + 1}')
    assert response.status_code == 400
    assert f'<= {NODE_ID_MAX}' in response.json()['extra'][0]['message']


def test_query_nodes(client: TestClient[Litestar], nodes: list[Node]):
    items = collect_paginated_data(client, path_prefix, MAX_PAGE_SIZE)
    for n in nodes:
        assert to_node_schema(n).to_dict() in items


def test_query_nodes_pagination(client: TestClient[Litestar], nodes: list[Node]):
    items = collect_paginated_data(client, path_prefix, 1)
    for n in nodes:
        assert to_node_schema(n).to_dict() in items

    params = {'max_page_size': 1, 'page_token': 'last'}
    response = client.get(path_prefix, params=params)
    assert response.status_code == 200
    assert len(response.json()['items']) == params['max_page_size']
    assert response.json().get('prev_page_token') is not None
    assert response.json().get('next_page_token') is None
    assert items[-1] == response.json()['items'][0]


def test_query_nodes_page_size(
    client: TestClient[Litestar], nodes_max_and_one: list[Node]
):
    check_page_size(client, path_prefix)


def test_query_nodes_invalid_page_token(
    client: TestClient[Litestar], nodes: list[Node]
):
    check_invalid_page_token_query(client, path_prefix)


def test_query_nodes_validation(client: TestClient[Litestar]):
    check_query_request_validation(client, path_prefix)


def test_create_node(client: TestClient[Litestar], host: Host):
    # Node number from under the host's operator; + 1 to avoid dealing with 0
    node_number = host.operator.allocated_node_numbers[0].lower + 1
    sdr_wm_size = 1
    sdr_config_flags = config_flags_int_to_arr(13)
    heap_words = 2
    wm_size = 3
    node_name = 'blah'
    comments = 'test_create_node() view test'
    response = client.post(
        path_prefix,
        json={
            'node_number': node_number,
            'operator_id': host.operator_id,
            'host_id': host.host_id,
            'sdr_wm_size': sdr_wm_size,
            'sdr_config_flags': sdr_config_flags,
            'heap_words': heap_words,
            'wm_size': wm_size,
            'node_name': node_name,
            'comments': comments,
        },
    )
    assert response.status_code == 201
    content = node_decoder.decode(response.content)
    assert response.headers['location'] == f'{path_prefix}/{content.node_id}'
    assert response.headers['content-location'] == f'{path_prefix}/{content.node_id}'
    assert content.allocator.allocator_id == str(host.operator.allocator_id)
    assert content.node_number == node_number
    assert content.operator.operator_id == str(host.operator_id)
    assert content.host.host_id == str(host.host_id)
    assert content.sdr_wm_size == sdr_wm_size
    assert content.sdr_config_flags == sdr_config_flags
    assert config_flags_arr_to_int(content.sdr_config_flags) == 13
    assert content.heap_words == heap_words
    assert content.wm_size == wm_size
    assert content.node_name == node_name
    assert content.comments == comments


def test_create_node_minimum(client: TestClient[Litestar]):
    node_number = 123
    response = client.post(path_prefix, json={'node_number': node_number})
    assert response.status_code == 201
    content = node_decoder.decode(response.content)
    assert content.allocator.allocator_id == '0'
    assert content.node_number == node_number
    assert content.operator is None
    assert content.host is None
    assert content.sdr_wm_size is None
    assert content.sdr_config_flags is None
    assert content.heap_words is None
    assert content.wm_size is None
    assert content.node_name is None
    assert content.comments is None


def test_create_node_explicit_null(client: TestClient[Litestar], allocator: Allocator):
    node_number = 123
    response = client.post(
        path_prefix,
        json={
            'allocator_id': allocator.allocator_id,
            'node_number': node_number,
            'operator_id': None,
            'host_id': None,
            'sdr_wm_size': None,
            'sdr_config_flags': None,
            'heap_words': None,
            'wm_size': None,
            'node_name': None,
            'comments': None,
        },
    )
    assert response.status_code == 201
    content = node_decoder.decode(response.content)
    assert content.allocator.allocator_id == str(allocator.allocator_id)
    assert content.node_number == node_number
    assert content.operator is None
    assert content.host is None
    assert content.sdr_wm_size is None
    assert content.sdr_config_flags is None
    assert content.heap_words is None
    assert content.wm_size is None
    assert content.node_name is None
    assert content.comments is None


def test_create_node_operator_overwrites_allocator(
    client: TestClient[Litestar], operator: Operator
):
    node_number = operator.allocated_node_numbers[0].lower
    response = client.post(
        path_prefix,
        json={
            'allocator_id': operator.allocator_id + 34,
            'node_number': node_number,
            'operator_id': operator.operator_id,
        },
    )
    assert response.status_code == 201
    content = node_decoder.decode(response.content)
    assert content.allocator.allocator_id == str(operator.allocator_id)
    assert content.node_number == node_number
    assert content.operator.operator_id == str(operator.operator_id)


def test_create_node_bigint_serialize(client: TestClient[Litestar]):
    node_number = 620
    unsafe_number = 2**53
    response = client.post(
        path_prefix,
        json={
            'node_number': node_number,
            'sdr_wm_size': unsafe_number,
            'heap_words': str(unsafe_number),
            'wm_size': unsafe_number,
        },
    )
    assert response.status_code == 201
    content = node_decoder.decode(response.content)
    assert content.allocator.allocator_id == '0'
    assert content.node_number == node_number
    assert content.sdr_wm_size == str(unsafe_number)
    assert content.heap_words == str(unsafe_number)
    assert content.wm_size == str(unsafe_number)


def test_create_node_nonexistent_host(client: TestClient[Litestar]):
    response = client.post(path_prefix, json={'node_number': 123, 'host_id': 0})
    assert response.status_code == 404
    assert 'Host ID 0 does not exist' in response.json()['detail']


def test_create_node_nonexistent_operator(client: TestClient[Litestar]):
    response = client.post(path_prefix, json={'node_number': 123, 'operator_id': 0})
    assert response.status_code == 404
    assert 'Operator ID 0 does not exist' in response.json()['detail']


def test_create_node_host_operator_mismatch(
    client: TestClient[Litestar], operator: Operator, host_no_operator: Host, host: Host
):
    response = client.post(
        path_prefix,
        json={
            'node_number': 123,
            'operator_id': operator.operator_id,
            'host_id': host_no_operator.host_id,
        },
    )
    assert response.status_code == 400
    assert (
        'cannot associate with an operator while on a host without an operator'
        in response.json()['detail']
    )

    response = client.post(
        path_prefix,
        json={
            'node_number': 123,
            'operator_id': operator.operator_id,
            'host_id': host.host_id,
        },
    )
    assert response.status_code == 400
    assert (
        f'ID {operator.operator_id} does not match host operator ID {host.operator_id}'
        in response.json()['detail']
    )


def test_create_node_node_number_not_allocated(
    client: TestClient[Litestar], operator: Operator
):
    ann = operator.allocated_node_numbers
    response = client.post(
        path_prefix,
        json={
            'node_number': ann[0].upper,
            'operator_id': operator.operator_id,
        },
    )
    assert response.status_code == 400
    assert (
        f'Node number {ann[0].upper} is not allocated to operator ID'
        f' {operator.operator_id} which has been allocated'
        f' {{[{ann[0].lower}, {ann[0].upper})}}'
    ) in response.json()['detail']


def test_create_node_nonexistent_allocator(
    client: TestClient[Litestar], allocator: Allocator
):
    allocator_id = allocator.allocator_id + 1
    response = client.post(
        path_prefix, json={'node_number': 123, 'allocator_id': allocator_id}
    )
    assert response.status_code == 404
    assert f'Allocator ID {allocator_id} does not exist' in response.json()['detail']


def test_create_node_duplicate_fqnn(client: TestClient[Litestar], node: Node):
    response = client.post(
        path_prefix,
        json={'allocator_id': node.allocator_id, 'node_number': node.node_number},
    )
    assert response.status_code == 400
    assert (
        f'FQNN ({node.allocator_id}, {node.node_number}) is already used by'
        f' node ID {node.node_id}'
    ) in response.json()['detail']


def test_create_node_validate_required_reqbody(client: TestClient[Litestar]):
    for response in [
        # Missing request body
        client.post(path_prefix),
        # Empty request body
        client.post(path_prefix, content=b''),
    ]:
        assert response.status_code == 400
        assert 'Expected non-empty request' in response.json()['extra'][0]['message']


def test_create_node_validate_null_reqbody(client: TestClient[Litestar]):
    # `null` is distinct from a missing / empty request body
    response = client.post(path_prefix, content=b'null')
    assert response.status_code == 400
    assert 'Expected `object`, got `null`' in response.json()['extra'][0]['message']


def test_create_node_validate_reqbody_fields(client: TestClient[Litestar]):
    # Missing fields
    response = client.post(path_prefix, json={})
    assert response.status_code == 400
    assert (
        'missing required field `node_number`' in response.json()['extra'][0]['message']
    )

    # Fields out of range
    for field, max_val in (
        ('node_number', NODE_NUMBER_MAX),
        ('allocator_id', ALLOCATOR_ID_MAX),
        ('operator_id', OPERATOR_ID_MAX),
        ('host_id', HOST_ID_MAX),
        ('sdr_wm_size', SDR_WM_SIZE_MAX),
        ('heap_words', HEAP_WORDS_MAX),
        ('wm_size', WM_SIZE_MAX),
    ):
        for r in (
            client.post(path_prefix, json={field: max_val + 1}),
            client.post(path_prefix, json={field: str(max_val + 1)}),
        ):
            assert r.status_code == 400
            assert field == r.json()['extra'][0]['key']
            assert f'<= {max_val}' in r.json()['extra'][0]['message']

    # Invalid sdr_config_flags enum
    response = client.post(
        path_prefix, json={'node_number': 123, 'sdr_config_flags': ['blah']}
    )
    assert response.status_code == 400
    assert response.json()['extra'] == [
        {
            'message': "Invalid enum value 'blah'",
            'key': 'sdr_config_flags[0]',
            'source': 'body',
        }
    ]

    # Empty sdr_config_flags
    response = client.post(
        path_prefix, json={'node_number': 123, 'sdr_config_flags': []}
    )
    assert response.status_code == 400
    assert response.json()['extra'] == [
        {
            'message': 'Expected `array` of length >= 1',
            'key': 'sdr_config_flags',
            'source': 'body',
        }
    ]

    # Too many config flags
    response = client.post(
        path_prefix,
        json={
            'node_number': 123,
            'sdr_config_flags': ['SDR_IN_DRAM' for _ in range(5)],
        },
    )
    assert response.status_code == 400
    assert response.json()['extra'] == [
        {
            'message': 'Expected `array` of length <= 4',
            'key': 'sdr_config_flags',
            'source': 'body',
        }
    ]


def test_update_node(client: TestClient[Litestar], node: Node, host: Host):
    node_number = host.operator.allocated_node_numbers[0].lower + 1
    sdr_wm_size = 1
    sdr_config_flags = config_flags_int_to_arr(2)
    heap_words = 3
    wm_size = 4
    node_name = 'foo'
    comments = 'bar'
    response = client.patch(
        f'{path_prefix}/{node.node_id}',
        json={
            'node_number': node_number,
            'allocator_id': 0,  # ignored
            'operator_id': host.operator_id,
            'host_id': host.host_id,
            'sdr_wm_size': sdr_wm_size,
            'sdr_config_flags': sdr_config_flags,
            'heap_words': heap_words,
            'wm_size': wm_size,
            'node_name': node_name,
            'comments': comments,
        },
    )
    assert response.status_code == 200
    content = node_decoder.decode(response.content)
    assert content.allocator.allocator_id == str(host.operator.allocator_id)
    assert content.node_number == node_number
    assert content.operator.operator_id == str(host.operator_id)
    assert content.host.host_id == str(host.host_id)
    assert content.sdr_wm_size == sdr_wm_size
    assert content.sdr_config_flags == sdr_config_flags
    assert config_flags_arr_to_int(content.sdr_config_flags) == 2
    assert content.heap_words == heap_words
    assert content.wm_size == wm_size
    assert content.node_name == node_name
    assert content.comments == comments


def test_update_node_no_change(client: TestClient[Litestar], node: Node):
    old = to_node_schema(node)

    for response in [
        # Missing request body
        client.patch(f'{path_prefix}/{node.node_id}'),
        # Empty request body
        client.patch(f'{path_prefix}/{node.node_id}', content=b''),
        # Empty object
        client.patch(f'{path_prefix}/{node.node_id}', json={}),
        # Same values
        client.patch(
            f'{path_prefix}/{node.node_id}',
            json={
                'node_number': node.node_number,
                'allocator_id': node.allocator_id,
                'operator_id': node.operator_id,
                'host_id': node.host_id,
                'sdr_wm_size': node.sdr_wm_size,
                'sdr_config_flags': config_flags_int_to_arr(node.sdr_config_flags),
                'heap_words': node.heap_words,
                'wm_size': node.wm_size,
                'node_name': node.node_name,
                'comments': node.comments,
            },
        ),
    ]:
        assert response.status_code == 200
        assert old == node_decoder.decode(response.content)


def test_update_node_operator_overwrites_allocator(
    client: TestClient[Litestar], node_no_host: Node, operator: Operator
):
    node = node_no_host
    node_number = operator.allocated_node_numbers[0].lower
    response = client.patch(
        f'{path_prefix}/{node.node_id}',
        json={
            'allocator_id': operator.allocator_id + 34,
            'node_number': node_number,
            'operator_id': operator.operator_id,
        },
    )
    assert response.status_code == 200
    content = node_decoder.decode(response.content)
    assert content.allocator.allocator_id == str(operator.allocator_id)
    assert content.node_number == node_number
    assert content.operator.operator_id == str(operator.operator_id)


def test_update_node_bigint_serialize(client: TestClient[Litestar], node: Node):
    unsafe_number = 2**53
    response = client.patch(
        f'{path_prefix}/{node.node_id}',
        json={
            'sdr_wm_size': unsafe_number,
            'heap_words': str(unsafe_number),
            'wm_size': unsafe_number,
        },
    )
    assert response.status_code == 200
    content = node_decoder.decode(response.content)
    assert content.sdr_wm_size == str(unsafe_number)
    assert content.heap_words == str(unsafe_number)
    assert content.wm_size == str(unsafe_number)


def test_update_node_same_host_dest_ref_mode_no_effect(
    client: TestClient[Litestar], node_with_inducts_seats: Node, session: Session
):
    node = node_with_inducts_seats

    def _f():
        for i in node.inducts:
            assert i.links
            assert i.induct_ip.destination
        for s in node.seats:
            assert s.links
            assert s.seat_ip.destination

    _f()
    for m in DestinationRefModeEnum:
        response = client.patch(
            f'{path_prefix}/{node.node_id}',
            json={'host_id': node.host_id},
            params={'destination_ref_mode': m.value},
        )
        assert response.status_code == 200
        session.refresh(node)
        _f()


@pytest.mark.parametrize(
    'mode', [DestinationRefModeEnum.NULLIFY, DestinationRefModeEnum.ASSOCIATE]
)
def test_update_node_host_to_new_host_dest_nullified(
    client: TestClient[Litestar],
    node_with_inducts_seats: Node,
    host: Host,
    session: Session,
    mode: DestinationRefModeEnum,
):
    node = node_with_inducts_seats
    node_number = host.operator.allocated_node_numbers[0].lower
    allocator_id = host.operator.allocator_id
    operator_id = host.operator_id
    for i in node.inducts:
        assert i.links
        assert i.induct_ip.destination
    for s in node.seats:
        assert s.links
        assert s.seat_ip.destination
    response = client.patch(
        f'{path_prefix}/{node.node_id}',
        params={'destination_ref_mode': mode},
        json={
            'node_number': node_number,
            'allocator_id': allocator_id,
            'operator_id': operator_id,
            'host_id': host.host_id,
        },
    )
    assert response.status_code == 200
    session.refresh(node)
    for i in node.inducts:
        assert not i.links
        assert not i.induct_ip.destination
    for s in node.seats:
        assert not s.links
        assert not s.seat_ip.destination


def test_update_node_host_to_null_host_dest_nullified(
    client: TestClient[Litestar], node_with_inducts_seats: Node, session: Session
):
    node = node_with_inducts_seats
    for i in node.inducts:
        assert i.links
        assert i.induct_ip.destination
    for s in node.seats:
        assert s.links
        assert s.seat_ip.destination
    response = client.patch(
        f'{path_prefix}/{node.node_id}',
        params={'destination_ref_mode': DestinationRefModeEnum.NULLIFY},
        json={'host_id': None},
    )
    assert response.status_code == 200
    session.refresh(node)
    for i in node.inducts:
        assert not i.links
        assert not i.induct_ip.destination
    for s in node.seats:
        assert not s.links
        assert not s.seat_ip.destination


def test_update_node_host_to_new_host_associate(
    client: TestClient[Litestar],
    node_with_ip_inducts_seats_links_host_same_ip: tuple[Node, Host],
    session: Session,
):
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

    response = client.patch(
        f'{path_prefix}/{node.node_id}',
        params={'destination_ref_mode': DestinationRefModeEnum.ASSOCIATE},
        json={
            'node_number': node_number,
            'allocator_id': allocator_id,
            'operator_id': operator_id,
            'host_id': host.host_id,
        },
    )
    assert response.status_code == 200
    session.refresh(node)
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


def test_update_node_host_to_new_host_copy(
    client: TestClient[Litestar],
    node_with_ip_inducts_seats_links_host_same_ip: tuple[Node, Host],
    session: Session,
):
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

    response = client.patch(
        f'{path_prefix}/{node.node_id}',
        params={'destination_ref_mode': DestinationRefModeEnum.COPY},
        json={
            'node_number': node_number,
            'allocator_id': allocator_id,
            'operator_id': operator_id,
            'host_id': host.host_id,
        },
    )
    assert response.status_code == 200
    session.refresh(node)
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


@pytest.mark.parametrize(
    'mode',
    [
        DestinationRefModeEnum.NULLIFY,
        DestinationRefModeEnum.ASSOCIATE,
        DestinationRefModeEnum.COPY,
    ],
)
def test_update_node_null_host_to_host(
    client: TestClient[Litestar],
    node_with_ip_induct_seat_no_host: Node,
    host: Host,
    mode: DestinationRefModeEnum,
    session: Session,
):
    node = node_with_ip_induct_seat_no_host
    node_number = host.operator.allocated_node_numbers[0].lower
    allocator_id = host.operator.allocator_id
    operator_id = host.operator_id
    for i in node.inducts:
        assert not i.links
        if i.induct_ip:
            assert not i.induct_ip.destination
    for s in node.seats:
        assert not s.links
        if s.seat_ip:
            assert not s.seat_ip.destination
    response = client.patch(
        f'{path_prefix}/{node.node_id}',
        params={'destination_ref_mode': mode},
        json={
            'node_number': node_number,
            'allocator_id': allocator_id,
            'operator_id': operator_id,
            'host_id': host.host_id,
        },
    )
    assert response.status_code == 200
    session.refresh(node)
    for i in node.inducts:
        assert not i.links
        if i.induct_ip:
            assert not i.induct_ip.destination
    for s in node.seats:
        assert not s.links
        if s.seat_ip:
            assert not s.seat_ip.destination


@pytest.mark.parametrize(
    'mode',
    [
        DestinationRefModeEnum.NULLIFY,
        DestinationRefModeEnum.ASSOCIATE,
        DestinationRefModeEnum.COPY,
    ],
)
def test_update_node_null_host_to_null_host(
    client: TestClient[Litestar],
    node_with_ip_induct_seat_no_host: Node,
    mode: DestinationRefModeEnum,
    session: Session,
):
    node = node_with_ip_induct_seat_no_host
    for i in node.inducts:
        assert not i.links
        if i.induct_ip:
            assert not i.induct_ip.destination
    for s in node.seats:
        assert not s.links
        if s.seat_ip:
            assert not s.seat_ip.destination
    response = client.patch(
        f'{path_prefix}/{node.node_id}',
        params={'destination_ref_mode': mode},
        json={'host_id': None},
    )
    assert response.status_code == 200
    session.refresh(node)
    for i in node.inducts:
        assert not i.links
        if i.induct_ip:
            assert not i.induct_ip.destination
    for s in node.seats:
        assert not s.links
        if s.seat_ip:
            assert not s.seat_ip.destination


def test_update_node_nonexistent_node(client: TestClient[Litestar]):
    response = client.patch(f'{path_prefix}/0')
    assert response.status_code == 404
    assert 'Node ID 0 does not exist' in response.json()['detail']


def test_update_node_nonexistent_host(client: TestClient[Litestar], node: Node):
    response = client.patch(f'{path_prefix}/{node.node_id}', json={'host_id': 0})
    assert response.status_code == 404
    assert 'Host ID 0 does not exist' in response.json()['detail']


def test_update_node_invalid_dest_ref_mode(client: TestClient[Litestar], node: Node):
    for m in (DestinationRefModeEnum.ASSOCIATE, DestinationRefModeEnum.COPY):
        response = client.patch(
            f'{path_prefix}/{node.node_id}',
            params={'destination_ref_mode': m},
            json={'host_id': None},
        )
        assert response.status_code == 400
        assert (
            f"Cannot use '{m}' for `destination_ref_mode` when node is on a"
            ' host but the operation would make the node hostless'
        ) in response.json()['detail']


def test_update_node_nonexistent_operator(client: TestClient[Litestar], node: Node):
    response = client.patch(f'{path_prefix}/{node.node_id}', json={'operator_id': 0})
    assert response.status_code == 404
    assert 'Operator ID 0 does not exist' in response.json()['detail']


def test_update_node_host_operator_mismatch(
    client: TestClient[Litestar],
    node_no_host: Node,
    host_no_operator: Host,
    operator: Operator,
    host: Host,
):
    node = node_no_host
    response = client.patch(
        f'{path_prefix}/{node.node_id}',
        json={'operator_id': operator.operator_id, 'host_id': host_no_operator.host_id},
    )
    assert response.status_code == 400
    assert (
        'cannot associate with an operator while on a host without an operator'
        in response.json()['detail']
    )

    response = client.patch(
        f'{path_prefix}/{node.node_id}',
        json={'operator_id': operator.operator_id, 'host_id': host.host_id},
    )
    assert response.status_code == 400
    assert (
        f'ID {operator.operator_id} does not match host operator ID {host.operator_id}'
        in response.json()['detail']
    )


def test_update_node_node_number_not_allocated(
    client: TestClient[Litestar], node: Node, operator: Operator
):
    ann = operator.allocated_node_numbers
    response = client.patch(
        f'{path_prefix}/{node.node_id}',
        json={
            'node_number': ann[0].upper,
            'operator_id': operator.operator_id,
            'host_id': None,
        },
    )
    assert response.status_code == 400
    assert (
        f'Node number {ann[0].upper} is not allocated to operator ID'
        f' {operator.operator_id} which has been allocated'
        f' {{[{ann[0].lower}, {ann[0].upper})}}'
    ) in response.json()['detail']


def test_update_node_nonexistent_allocator(client: TestClient[Litestar], node: Node):
    allocator_id = node.allocator_id + 1
    response = client.patch(
        f'{path_prefix}/{node.node_id}',
        json={'allocator_id': allocator_id, 'operator_id': None},
    )
    assert response.status_code == 404
    assert f'Allocator ID {allocator_id} does not exist' in response.json()['detail']


def test_update_node_duplicate_fqnn(
    client: TestClient[Litestar], node: Node, node_no_host: Node
):
    response = client.patch(
        f'{path_prefix}/{node_no_host.node_id}',
        json={
            'allocator_id': node.allocator_id,
            'node_number': node.node_number,
            'operator_id': None,
        },
    )
    assert response.status_code == 400
    assert (
        f'FQNN ({node.allocator_id}, {node.node_number}) is already used by'
        f' node ID {node.node_id}'
    ) in response.json()['detail']


def test_update_node_validate_null_reqbody(client: TestClient[Litestar]):
    # `null` is distinct from a missing / empty request body
    response = client.patch(f'{path_prefix}/0', content=b'null')
    assert response.status_code == 400
    assert 'Expected `object`, got `null`' in response.json()['extra'][0]['message']


def test_update_node_validate_reqbody_fields(client: TestClient[Litestar]):
    path = f'{path_prefix}/0'
    # Fields out of range
    for field, max_val in (
        ('node_number', NODE_NUMBER_MAX),
        ('allocator_id', ALLOCATOR_ID_MAX),
        ('operator_id', OPERATOR_ID_MAX),
        ('host_id', HOST_ID_MAX),
        ('sdr_wm_size', SDR_WM_SIZE_MAX),
        ('heap_words', HEAP_WORDS_MAX),
        ('wm_size', WM_SIZE_MAX),
    ):
        for r in (
            client.patch(path, json={field: max_val + 1}),
            client.patch(path, json={field: str(max_val + 1)}),
        ):
            assert r.status_code == 400
            assert field == r.json()['extra'][0]['key']
            assert f'<= {max_val}' in r.json()['extra'][0]['message']

    # Invalid sdr_config_flags enum
    response = client.patch(path, json={'sdr_config_flags': ['blah']})
    assert response.status_code == 400
    assert response.json()['extra'] == [
        {
            'message': "Invalid enum value 'blah'",
            'key': 'sdr_config_flags[0]',
            'source': 'body',
        }
    ]

    # Empty sdr_config_flags
    response = client.patch(path, json={'sdr_config_flags': []})
    assert response.status_code == 400
    assert response.json()['extra'] == [
        {
            'message': 'Expected `array` of length >= 1',
            'key': 'sdr_config_flags',
            'source': 'body',
        }
    ]

    # Too many config flags
    response = client.patch(
        path, json={'sdr_config_flags': ['SDR_IN_DRAM' for _ in range(5)]}
    )
    assert response.status_code == 400
    assert response.json()['extra'] == [
        {
            'message': 'Expected `array` of length <= 4',
            'key': 'sdr_config_flags',
            'source': 'body',
        }
    ]


def test_update_node_validate_parameter(client: TestClient[Litestar]):
    response = client.patch(f'{path_prefix}/{NODE_ID_MAX + 1}')
    assert response.status_code == 400
    assert f'<= {NODE_ID_MAX}' in response.json()['extra'][0]['message']

    response = client.patch(f'{path_prefix}/0', params={'destination_ref_mode': 'blah'})
    assert response.status_code == 400
    assert "Invalid enum value 'blah'" in response.json()['extra'][0]['message']
    assert 'destination_ref_mode' in response.json()['extra'][0]['key']
    assert 'query' in response.json()['extra'][0]['source']


@pytest.mark.parametrize(
    'mode',
    [
        DestinationRefModeEnum.NULLIFY,
        DestinationRefModeEnum.ASSOCIATE,
        DestinationRefModeEnum.COPY,
    ],
)
def test_copy_node_hostless_to_hostless(
    client: TestClient[Litestar],
    node_no_host: Node,
    mode: DestinationRefModeEnum,
    session: Session,
):
    node_number = node_no_host.node_number + 1
    response = client.post(
        f'{path_prefix}/{node_no_host.node_id}/copies',
        params={'destination_ref_mode': mode},
        json={
            'allocator_id': node_no_host.allocator_id,
            'node_number': node_number,
            'operator_id': None,
            'host_id': None,
        },
    )
    assert response.status_code == 201
    content = node_decoder.decode(response.content)
    assert content.node_number == node_number
    assert content.allocator.allocator_id == str(node_no_host.allocator_id)
    assert response.headers['location'] == f'{path_prefix}/{content.node_id}'
    assert response.headers['content-location'] == f'{path_prefix}/{content.node_id}'
    check_copy_node_equality(
        node_no_host, node_get(session, int(content.node_id)), mode
    )


@pytest.mark.parametrize(
    'mode',
    [
        DestinationRefModeEnum.NULLIFY,
        DestinationRefModeEnum.ASSOCIATE,
        DestinationRefModeEnum.COPY,
    ],
)
def test_copy_node_hostless_to_host(
    client: TestClient[Litestar],
    node_no_host: Node,
    host: Host,
    mode: DestinationRefModeEnum,
    session: Session,
):
    node_number = host.operator.allocated_node_numbers[0].lower
    allocator_id = host.operator.allocator_id
    operator_id = host.operator_id
    response = client.post(
        f'{path_prefix}/{node_no_host.node_id}/copies',
        params={'destination_ref_mode': mode},
        json={
            'allocator_id': allocator_id,
            'node_number': node_number,
            'operator_id': operator_id,
            'host_id': host.host_id,
        },
    )
    assert response.status_code == 201
    content = node_decoder.decode(response.content)
    assert content.node_number == node_number
    assert content.allocator.allocator_id == str(allocator_id)
    assert content.operator.operator_id == str(operator_id)
    assert content.host.host_id == str(host.host_id)
    assert response.headers['location'] == f'{path_prefix}/{content.node_id}'
    assert response.headers['content-location'] == f'{path_prefix}/{content.node_id}'
    check_copy_node_equality(
        node_no_host, node_get(session, int(content.node_id)), mode
    )


def test_copy_node_host_to_hostless(
    client: TestClient[Litestar],
    node_full_and_host: tuple[Node, Host],
    session: Session,
):
    node, _ = node_full_and_host
    node_number = node.node_number + 1
    mode = DestinationRefModeEnum.NULLIFY
    response = client.post(
        f'{path_prefix}/{node.node_id}/copies',
        params={'destination_ref_mode': mode},
        json={
            'allocator_id': node.allocator_id,
            'node_number': node_number,
            'operator_id': None,
            'host_id': None,
        },
    )
    assert response.status_code == 201
    content = node_decoder.decode(response.content)
    assert content.node_number == node_number
    assert content.allocator.allocator_id == str(node.allocator_id)
    assert content.operator is None
    assert content.host is None
    assert response.headers['location'] == f'{path_prefix}/{content.node_id}'
    assert response.headers['content-location'] == f'{path_prefix}/{content.node_id}'
    check_copy_node_equality(node, node_get(session, int(content.node_id)), mode)


@pytest.mark.parametrize(
    'mode',
    [
        DestinationRefModeEnum.NULLIFY,
        DestinationRefModeEnum.ASSOCIATE,
        DestinationRefModeEnum.COPY,
    ],
)
def test_copy_node_host_to_same_host(
    client: TestClient[Litestar],
    node_full_and_host: tuple[Node, Host],
    mode: DestinationRefModeEnum,
    session: Session,
):
    node, _ = node_full_and_host
    node_number = node.operator.allocated_node_numbers[0].lower
    while node_number == node.node_number:
        node_number += 1
    response = client.post(
        f'{path_prefix}/{node.node_id}/copies',
        params={'destination_ref_mode': mode},
        json={
            'allocator_id': node.allocator_id,
            'node_number': node_number,
            'operator_id': node.operator_id,
            'host_id': node.host_id,
        },
    )
    assert response.status_code == 201
    content = node_decoder.decode(response.content)
    assert content.node_number == node_number
    assert content.allocator.allocator_id == str(node.allocator_id)
    assert content.operator.operator_id == str(node.operator_id)
    assert content.host.host_id == str(node.host_id)
    assert response.headers['location'] == f'{path_prefix}/{content.node_id}'
    assert response.headers['content-location'] == f'{path_prefix}/{content.node_id}'
    check_copy_node_equality(node, node_get(session, int(content.node_id)), mode)


@pytest.mark.parametrize(
    'mode',
    [
        DestinationRefModeEnum.NULLIFY,
        DestinationRefModeEnum.ASSOCIATE,
        DestinationRefModeEnum.COPY,
    ],
)
def test_copy_node_host_to_host(
    client: TestClient[Litestar],
    node_full_and_host: tuple[Node, Host],
    mode: DestinationRefModeEnum,
    session: Session,
):
    node, host = node_full_and_host
    node_number = host.operator.allocated_node_numbers[0].lower
    allocator_id = host.operator.allocator_id
    operator_id = host.operator_id
    induct_dest_no_equivalent = node.inducts[3].induct_ip.destination
    seat_dest_no_equivalent = node.seats[3].seat_ip.destination
    response = client.post(
        f'{path_prefix}/{node.node_id}/copies',
        params={'destination_ref_mode': mode},
        json={
            'allocator_id': allocator_id,
            'node_number': node_number,
            'operator_id': operator_id,
            'host_id': host.host_id,
        },
    )
    assert response.status_code == 201
    content = node_decoder.decode(response.content)
    assert content.node_number == node_number
    assert content.allocator.allocator_id == str(allocator_id)
    assert content.operator.operator_id == str(operator_id)
    assert content.host.host_id == str(host.host_id)
    assert response.headers['location'] == f'{path_prefix}/{content.node_id}'
    assert response.headers['content-location'] == f'{path_prefix}/{content.node_id}'
    copied_node = node_get(session, int(content.node_id))
    check_copy_node_equality(node, copied_node, mode)
    if mode == DestinationRefModeEnum.ASSOCIATE:
        for i, i_copy in zip(node.inducts, copied_node.inducts):
            if i.induct_ip and i.induct_ip.destination == induct_dest_no_equivalent:
                assert not i_copy.induct_ip.destination
        for s, s_copy in zip(node.seats, copied_node.seats):
            if s.seat_ip and s.seat_ip.destination == seat_dest_no_equivalent:
                assert not s_copy.seat_ip.destination


def test_copy_node_operator_overwrites_allocator(
    client: TestClient[Litestar], node_no_host: Node, operator: Operator
):
    node = node_no_host
    node_number = operator.allocated_node_numbers[0].lower
    response = client.post(
        f'{path_prefix}/{node.node_id}/copies',
        json={
            'allocator_id': operator.allocator_id + 34,
            'node_number': node_number,
            'operator_id': operator.operator_id,
        },
    )
    assert response.status_code == 201
    content = node_decoder.decode(response.content)
    assert content.node_number == node_number
    assert content.allocator.allocator_id == str(operator.allocator_id)
    assert content.operator.operator_id == str(operator.operator_id)
    assert content.host is None


def test_copy_node_nonexistent_node(client: TestClient[Litestar]):
    response = client.post(f'{path_prefix}/0/copies', json={'node_number': 0})
    assert response.status_code == 404
    assert 'Node ID 0 does not exist' in response.json()['detail']


def test_copy_node_nonexistent_host(client: TestClient[Litestar], node: Node):
    response = client.post(
        f'{path_prefix}/{node.node_id}/copies', json={'host_id': 0, 'node_number': 0}
    )
    assert response.status_code == 404
    assert 'Host ID 0 does not exist' in response.json()['detail']


def test_copy_node_invalid_dest_ref_mode(client: TestClient[Litestar], node: Node):
    for m in (DestinationRefModeEnum.ASSOCIATE, DestinationRefModeEnum.COPY):
        response = client.post(
            f'{path_prefix}/{node.node_id}/copies',
            params={'destination_ref_mode': m},
            json={'host_id': None, 'node_number': 0},
        )
        assert response.status_code == 400
        assert (
            f"Cannot use '{m}' for `destination_ref_mode` when the to-be-copied"
            ' node is on a host but the node to be created will be hostless'
        ) in response.json()['detail']


def test_copy_node_nonexistent_operator(client: TestClient[Litestar], node: Node):
    response = client.post(
        f'{path_prefix}/{node.node_id}/copies',
        json={'operator_id': 0, 'node_number': 0},
    )
    assert response.status_code == 404
    assert 'Operator ID 0 does not exist' in response.json()['detail']


def test_copy_node_host_operator_mismatch(
    client: TestClient[Litestar],
    node_no_host: Node,
    host_no_operator: Host,
    operator: Operator,
    host: Host,
):
    node = node_no_host
    response = client.post(
        f'{path_prefix}/{node.node_id}/copies',
        json={
            'operator_id': operator.operator_id,
            'host_id': host_no_operator.host_id,
            'node_number': 0,
        },
    )
    assert response.status_code == 400
    assert (
        'cannot associate with an operator while on a host without an operator'
        in response.json()['detail']
    )

    response = client.post(
        f'{path_prefix}/{node.node_id}/copies',
        json={
            'operator_id': operator.operator_id,
            'host_id': host.host_id,
            'node_number': 0,
        },
    )
    assert response.status_code == 400
    assert (
        f'ID {operator.operator_id} does not match host operator ID {host.operator_id}'
        in response.json()['detail']
    )


def test_copy_node_node_number_not_allocated(
    client: TestClient[Litestar], node: Node, operator: Operator
):
    ann = operator.allocated_node_numbers
    response = client.post(
        f'{path_prefix}/{node.node_id}/copies',
        json={
            'node_number': ann[0].upper,
            'operator_id': operator.operator_id,
            'host_id': None,
        },
    )
    assert response.status_code == 400
    assert (
        f'Node number {ann[0].upper} is not allocated to operator ID'
        f' {operator.operator_id} which has been allocated'
        f' {{[{ann[0].lower}, {ann[0].upper})}}'
    ) in response.json()['detail']


def test_copy_node_nonexistent_allocator(client: TestClient[Litestar], node: Node):
    allocator_id = node.allocator_id + 1
    response = client.post(
        f'{path_prefix}/{node.node_id}/copies',
        json={'allocator_id': allocator_id, 'operator_id': None, 'node_number': 0},
    )
    assert response.status_code == 404
    assert f'Allocator ID {allocator_id} does not exist' in response.json()['detail']


def test_copy_node_duplicate_fqnn(
    client: TestClient[Litestar], node: Node, node_no_host: Node
):
    response = client.post(
        f'{path_prefix}/{node_no_host.node_id}/copies',
        json={
            'allocator_id': node.allocator_id,
            'node_number': node.node_number,
            'operator_id': None,
        },
    )
    assert response.status_code == 400
    assert (
        f'FQNN ({node.allocator_id}, {node.node_number}) is already used by'
        f' node ID {node.node_id}'
    ) in response.json()['detail']


def test_copy_node_validate_required_reqbody(client: TestClient[Litestar]):
    for response in [
        # Missing request body
        client.post(f'{path_prefix}/0/copies'),
        # Empty request body
        client.post(f'{path_prefix}/0/copies', content=b''),
    ]:
        assert response.status_code == 400
        assert 'Expected non-empty request' in response.json()['extra'][0]['message']


def test_copy_node_validate_null_reqbody(client: TestClient[Litestar]):
    # `null` is distinct from a missing / empty request body
    response = client.post(f'{path_prefix}/0/copies', content=b'null')
    assert response.status_code == 400
    assert 'Expected `object`, got `null`' in response.json()['extra'][0]['message']


def test_copy_node_validate_reqbody_fields(client: TestClient[Litestar]):
    path = f'{path_prefix}/0/copies'
    # Fields out of range
    for r in (
        client.post(path, json={'node_number': NODE_NUMBER_MAX + 1}),
        client.post(path, json={'node_number': str(NODE_NUMBER_MAX + 1)}),
    ):
        assert r.status_code == 400
        assert 'node_number' == r.json()['extra'][0]['key']
        assert f'<= {NODE_NUMBER_MAX}' in r.json()['extra'][0]['message']
    for field, max_val in (
        ('allocator_id', ALLOCATOR_ID_MAX),
        ('operator_id', OPERATOR_ID_MAX),
        ('host_id', HOST_ID_MAX),
    ):
        for r in (
            client.post(path, json={field: max_val + 1, 'node_number': 0}),
            client.post(path, json={field: str(max_val + 1), 'node_number': 0}),
        ):
            assert r.status_code == 400
            assert field == r.json()['extra'][0]['key']
            assert f'<= {max_val}' in r.json()['extra'][0]['message']


def test_copy_node_validate_parameter(client: TestClient[Litestar]):
    response = client.post(
        f'{path_prefix}/{NODE_ID_MAX + 1}/copies', json={'node_number': 0}
    )
    assert response.status_code == 400
    assert f'<= {NODE_ID_MAX}' in response.json()['extra'][0]['message']

    response = client.post(
        f'{path_prefix}/0/copies',
        params={'destination_ref_mode': 'blah'},
        json={'node_number': 0},
    )
    assert response.status_code == 400
    assert "Invalid enum value 'blah'" in response.json()['extra'][0]['message']
    assert 'destination_ref_mode' in response.json()['extra'][0]['key']
    assert 'query' in response.json()['extra'][0]['source']


def test_delete_node(client: TestClient[Litestar], node: Node):
    response = client.delete(f'{path_prefix}/{node.node_id}')
    assert response.status_code == 204
    # The record was deleted, so deleting again should error
    response = client.delete(f'{path_prefix}/{node.node_id}')
    assert response.status_code == 404
    assert f'Node ID {node.node_id} does not exist' in response.json()['detail']


def test_delete_node_validation(client: TestClient[Litestar]):
    response = client.delete(f'{path_prefix}/{NODE_ID_MAX + 1}')
    assert response.status_code == 400
    assert f'<= {NODE_ID_MAX}' in response.json()['extra'][0]['message']


def test_list_node_endpoints_ipn(client: TestClient[Litestar], node: Node):
    items = collect_paginated_data(
        client, f'{path_prefix}/{node.node_id}/endpoints/ipn', MAX_PAGE_SIZE
    )
    for e in node.ipn_endpoints:
        assert to_endpoint_ipn_schema(e).to_dict() in items


def test_list_node_endpoints_ipn_unsafe_num(
    client: TestClient[Litestar], node_with_safe_unsafe_ipn_endpoints: Node
):
    node = node_with_safe_unsafe_ipn_endpoints
    items = collect_paginated_data(
        client, f'{path_prefix}/{node.node_id}/endpoints/ipn', MAX_PAGE_SIZE
    )
    for e in node.ipn_endpoints:
        assert to_endpoint_ipn_schema(e).to_dict() in items


def test_list_node_endpoints_ipn_pagination(
    client: TestClient[Litestar], node_max_and_one_ipn_endpoints: Node
):
    node = node_max_and_one_ipn_endpoints
    items = collect_paginated_data(
        client, f'{path_prefix}/{node.node_id}/endpoints/ipn', 1
    )
    for e in node.ipn_endpoints:
        assert to_endpoint_ipn_schema(e).to_dict() in items

    params = {'max_page_size': 1, 'page_token': 'last'}
    response = client.get(f'{path_prefix}/{node.node_id}/endpoints/ipn', params=params)
    assert response.status_code == 200
    assert len(response.json()['items']) == params['max_page_size']
    assert response.json().get('prev_page_token') is not None
    assert response.json().get('next_page_token') is None
    assert items[-1] == response.json()['items'][0]


def test_list_node_endpoints_ipn_page_size(
    client: TestClient[Litestar], node_max_and_one_ipn_endpoints: Node
):
    node = node_max_and_one_ipn_endpoints
    check_page_size(client, f'{path_prefix}/{node.node_id}/endpoints/ipn')


def test_list_node_endpoints_ipn_invalid_page_token(
    client: TestClient[Litestar], node_max_and_one_ipn_endpoints: Node, node: Node
):
    other_node_id = node.node_id
    node = node_max_and_one_ipn_endpoints
    check_invalid_page_token_different_url(
        client,
        f'{path_prefix}/{node.node_id}/endpoints/ipn',
        f'{path_prefix}/{other_node_id}/endpoints/ipn',
    )


def test_list_node_endpoints_ipn_not_found(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/0/endpoints/ipn')
    assert response.status_code == 404
    assert 'ID 0 does not exist' in response.json()['detail']


def test_list_node_endpoints_ipn_validation(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/{NODE_ID_MAX * 2}/endpoints/ipn')
    assert response.status_code == 400
    assert f'<= {NODE_ID_MAX}' in response.json()['extra'][0]['message']

    check_paginated_request_validation(client, f'{path_prefix}/0/endpoints/ipn')


def test_list_node_endpoints_imc(
    client: TestClient[Litestar], node_with_imc_endpoints: Node
):
    node = node_with_imc_endpoints
    items = collect_paginated_data(
        client, f'{path_prefix}/{node.node_id}/endpoints/imc', MAX_PAGE_SIZE
    )
    for e in node.imc_endpoints:
        assert to_endpoint_imc_schema(e).to_dict() in items


def test_list_node_endpoints_imc_unsafe_num(
    client: TestClient[Litestar], node_with_safe_unsafe_imc_endpoints: Node
):
    node = node_with_safe_unsafe_imc_endpoints
    items = collect_paginated_data(
        client, f'{path_prefix}/{node.node_id}/endpoints/imc', MAX_PAGE_SIZE
    )
    for e in node.imc_endpoints:
        assert to_endpoint_imc_schema(e).to_dict() in items


def test_list_node_endpoints_imc_pagination(
    client: TestClient[Litestar], node_max_and_one_imc_endpoints: Node
):
    node = node_max_and_one_imc_endpoints
    items = collect_paginated_data(
        client, f'{path_prefix}/{node.node_id}/endpoints/imc', 1
    )
    for e in node.imc_endpoints:
        assert to_endpoint_imc_schema(e).to_dict() in items

    params = {'max_page_size': 1, 'page_token': 'last'}
    response = client.get(f'{path_prefix}/{node.node_id}/endpoints/imc', params=params)
    assert response.status_code == 200
    assert len(response.json()['items']) == params['max_page_size']
    assert response.json().get('prev_page_token') is not None
    assert response.json().get('next_page_token') is None
    assert items[-1] == response.json()['items'][0]


def test_list_node_endpoints_imc_page_size(
    client: TestClient[Litestar], node_max_and_one_imc_endpoints: Node
):
    node = node_max_and_one_imc_endpoints
    check_page_size(client, f'{path_prefix}/{node.node_id}/endpoints/imc')


def test_list_node_endpoints_imc_invalid_page_token(
    client: TestClient[Litestar], node_max_and_one_imc_endpoints: Node, node: Node
):
    other_node_id = node.node_id
    node = node_max_and_one_imc_endpoints
    check_invalid_page_token_different_url(
        client,
        f'{path_prefix}/{node.node_id}/endpoints/imc',
        f'{path_prefix}/{other_node_id}/endpoints/imc',
    )


def test_list_node_endpoints_imc_not_found(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/0/endpoints/imc')
    assert response.status_code == 404
    assert 'ID 0 does not exist' in response.json()['detail']


def test_list_node_endpoints_imc_validation(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/{NODE_ID_MAX * 2}/endpoints/imc')
    assert response.status_code == 400
    assert f'<= {NODE_ID_MAX}' in response.json()['extra'][0]['message']

    check_paginated_request_validation(client, f'{path_prefix}/0/endpoints/imc')


def test_replace_endpoints_ipn(
    client: TestClient[Litestar], node: Node, session: Session
):
    old_endpoints = node.ipn_endpoints
    response = client.put(
        f'{path_prefix}/{node.node_id}/endpoints/ipn',
        json=[
            {
                'service_number': 3,
                'application': 'foo',
                'disposition': 'q',
            },
            {
                'uri': f'ipn:{node.allocator_id}.{node.node_number}.4',
                'application': 'bar',
                'disposition': 'x',
            },
        ],
    )
    assert response.status_code == 204
    session.refresh(node)
    assert node.ipn_endpoints != old_endpoints
    assert node.ipn_endpoints[0].service_number == 3
    assert node.ipn_endpoints[0].application == 'foo'
    assert node.ipn_endpoints[0].disposition == 'q'
    assert node.ipn_endpoints[1].service_number == 4
    assert node.ipn_endpoints[1].application == 'bar'
    assert node.ipn_endpoints[1].disposition == 'x'


def test_replace_endpoints_ipn_unsafe_num(
    client: TestClient[Litestar], node: Node, session: Session
):
    old_endpoints = node.ipn_endpoints
    response = client.put(
        f'{path_prefix}/{node.node_id}/endpoints/ipn',
        json=[
            {
                'service_number': 2**53,
                'application': 'foo',
                'disposition': 'q',
            },
            {
                'service_number': str(2**53 + 1),
                'application': 'bar',
                'disposition': 'x',
            },
            {
                'uri': f'ipn:{node.allocator_id}.{node.node_number}.{2**53 + 2}',
                'application': 'baz',
                'disposition': 'x',
            },
        ],
    )
    assert response.status_code == 204
    session.refresh(node)
    assert node.ipn_endpoints != old_endpoints
    assert node.ipn_endpoints[0].service_number == 2**53
    assert node.ipn_endpoints[0].application == 'foo'
    assert node.ipn_endpoints[0].disposition == 'q'
    assert node.ipn_endpoints[1].service_number == 2**53 + 1
    assert node.ipn_endpoints[1].application == 'bar'
    assert node.ipn_endpoints[1].disposition == 'x'
    assert node.ipn_endpoints[2].service_number == 2**53 + 2
    assert node.ipn_endpoints[2].application == 'baz'
    assert node.ipn_endpoints[2].disposition == 'x'


def test_replace_endpoints_ipn_empty(
    client: TestClient[Litestar], node: Node, session: Session
):
    assert node.ipn_endpoints
    response = client.put(f'{path_prefix}/{node.node_id}/endpoints/ipn', json=[])
    assert response.status_code == 204
    session.refresh(node)
    assert not node.ipn_endpoints


def test_replace_endpoints_ipn_parse_uri(
    client: TestClient[Litestar],
    node: Node,
    node_default_allocator: Node,
    node_localnode: Node,
    session: Session,
):
    old_endpoints = node.ipn_endpoints
    response = client.put(
        f'{path_prefix}/{node.node_id}/endpoints/ipn',
        json=[
            {
                'uri': f'ipn:{node.allocator_id}.{node.node_number}.1',
                'application': 'foo',
            }
        ],
    )
    assert response.status_code == 204
    session.refresh(node)
    assert node.ipn_endpoints != old_endpoints
    assert node.ipn_endpoints[0].service_number == 1
    assert node.ipn_endpoints[0].application == 'foo'

    # Default allocator doesn't need 0 in front
    n_d_a = node_default_allocator
    old_endpoints = n_d_a.ipn_endpoints
    response = client.put(
        f'{path_prefix}/{n_d_a.node_id}/endpoints/ipn',
        json=[
            {
                'uri': f'ipn:0.{n_d_a.node_number}.1',
                'application': 'foo',
            },
            {
                'uri': f'ipn:{n_d_a.node_number}.2',
                'application': 'bar',
            },
        ],
    )
    assert response.status_code == 204
    session.refresh(n_d_a)
    assert n_d_a.ipn_endpoints != old_endpoints
    assert n_d_a.ipn_endpoints[0].service_number == 1
    assert n_d_a.ipn_endpoints[0].application == 'foo'
    assert n_d_a.ipn_endpoints[1].service_number == 2
    assert n_d_a.ipn_endpoints[1].application == 'bar'

    # LocalNode can use "!" as its FQNN
    n_ln = node_localnode
    old_endpoints = n_ln.ipn_endpoints
    response = client.put(
        f'{path_prefix}/{n_ln.node_id}/endpoints/ipn',
        json=[
            {
                'uri': f'ipn:0.{n_ln.node_number}.1',
                'application': 'foo',
            },
            {
                'uri': f'ipn:{n_ln.node_number}.2',
                'application': 'bar',
            },
            {
                'uri': 'ipn:!.3',
                'application': 'baz',
            },
        ],
    )
    assert response.status_code == 204
    session.refresh(n_ln)
    assert n_ln.ipn_endpoints != old_endpoints
    assert n_ln.ipn_endpoints[0].service_number == 1
    assert n_ln.ipn_endpoints[0].application == 'foo'
    assert n_ln.ipn_endpoints[1].service_number == 2
    assert n_ln.ipn_endpoints[1].application == 'bar'
    assert n_ln.ipn_endpoints[2].service_number == 3
    assert n_ln.ipn_endpoints[2].application == 'baz'


def test_replace_endpoints_ipn_validation(client: TestClient[Litestar]):
    # null uri and service_number
    for response in [
        client.put(f'{path_prefix}/0/endpoints/ipn', json=[{}]),
        client.put(
            f'{path_prefix}/0/endpoints/ipn',
            json=[{'uri': None, 'service_number': None}],
        ),
        client.put(f'{path_prefix}/0/endpoints/ipn', json=[{'uri': None}]),
        client.put(f'{path_prefix}/0/endpoints/ipn', json=[{'service_number': None}]),
    ]:
        assert response.status_code == 400
        assert (
            response.json()['extra'][0]['message']
            == '`uri` and `service_number` cannot both be `null`'
        )
        assert response.json()['extra'][0]['key'] == '[0].uri'
        assert response.json()['extra'][0]['source'] == 'body'

    # Conflicting uri and service_number
    response = client.put(
        f'{path_prefix}/0/endpoints/ipn',
        json=[{'uri': 'ipn:1.2.3', 'service_number': 4}],
    )
    assert response.status_code == 400
    assert (
        response.json()['extra'][0]['message']
        == '`service_number` (4) conflicts with service number of `uri` (ipn:1.2.3)'
    )
    assert response.json()['extra'][0]['key'] == '[0].service_number'
    assert response.json()['extra'][0]['source'] == 'body'

    # Invalid ipn URI
    for uri, response in [
        (
            'dtn://abc',
            client.put(f'{path_prefix}/0/endpoints/ipn', json=[{'uri': 'dtn://abc'}]),
        ),
        (
            'ipn:001.1',
            client.put(f'{path_prefix}/0/endpoints/ipn', json=[{'uri': 'ipn:001.1'}]),
        ),
        (
            'ipn:-1.-1.-1',
            client.put(
                f'{path_prefix}/0/endpoints/ipn', json=[{'uri': 'ipn:-1.-1.-1'}]
            ),
        ),
    ]:
        assert response.status_code == 400
        assert (
            response.json()['extra'][0]['message']
            == f"'{uri}' does not comply with the text syntax of an ipn URI"
        )
        assert response.json()['extra'][0]['key'] == '[0].uri'
        assert response.json()['extra'][0]['source'] == 'body'

    # Exceed maximum values for allocator ID, node number, service number
    for name, uri, max_val, response in [
        (
            'Allocator Identifier',
            f'ipn:{ALLOCATOR_ID_MAX + 1}.0.0',
            ALLOCATOR_ID_MAX,
            client.put(
                f'{path_prefix}/0/endpoints/ipn',
                json=[{'uri': f'ipn:{ALLOCATOR_ID_MAX + 1}.0.0'}],
            ),
        ),
        (
            'Node Number',
            f'ipn:0.{NODE_NUMBER_MAX + 1}.0',
            NODE_NUMBER_MAX,
            client.put(
                f'{path_prefix}/0/endpoints/ipn',
                json=[{'uri': f'ipn:0.{NODE_NUMBER_MAX + 1}.0'}],
            ),
        ),
        (
            'Service Number',
            f'ipn:0.0.{SERVICE_NUMBER_MAX + 1}',
            SERVICE_NUMBER_MAX,
            client.put(
                f'{path_prefix}/0/endpoints/ipn',
                json=[{'uri': f'ipn:0.0.{SERVICE_NUMBER_MAX + 1}'}],
            ),
        ),
    ]:
        assert response.status_code == 400
        assert response.json()['extra'][0]['message'] == (
            f'Expected {name} in `uri` ({uri}) <= {max_val}, but got {max_val + 1}'
        )
        assert response.json()['extra'][0]['key'] == '[0].uri'
        assert response.json()['extra'][0]['source'] == 'body'

    # Conflicting uri and service_number
    for uri, service_number, response in [
        (
            'ipn:1.2.3',
            4,
            client.put(
                f'{path_prefix}/0/endpoints/ipn',
                json=[{'uri': 'ipn:1.2.3', 'service_number': 4}],
            ),
        ),
        (
            'ipn:1.2',
            3,
            client.put(
                f'{path_prefix}/0/endpoints/ipn',
                json=[{'uri': 'ipn:1.2', 'service_number': 3}],
            ),
        ),
        (
            'ipn:!.2',
            3,
            client.put(
                f'{path_prefix}/0/endpoints/ipn',
                json=[{'uri': 'ipn:!.2', 'service_number': 3}],
            ),
        ),
    ]:
        assert response.status_code == 400
        assert response.json()['extra'][0]['message'] == (
            f'`service_number` ({service_number}) conflicts with service number'
            f' of `uri` ({uri})'
        )
        assert response.json()['extra'][0]['key'] == '[0].service_number'
        assert response.json()['extra'][0]['source'] == 'body'

    # Invalid disposition
    response = client.put(
        f'{path_prefix}/0/endpoints/ipn',
        json=[{'service_number': 34, 'disposition': 'discard'}],
    )
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == "Invalid enum value 'discard'"
    # TODO: include check for key == '[0].disposition' if Litestar merges my PR

    # service_number out of range
    response = client.put(
        f'{path_prefix}/0/endpoints/ipn',
        json=[{'service_number': SERVICE_NUMBER_MAX + 1}],
    )
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == (
        f'Expected `int` <= {SERVICE_NUMBER_MAX}'
    )

    # node_id out of range
    response = client.put(f'{path_prefix}/{NODE_ID_MAX + 1}/endpoints/ipn', json=[])
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == f'Expected `int` <= {NODE_ID_MAX}'


def test_replace_endpoints_ipn_repeat_service_numbers(
    client: TestClient[Litestar], node: Node, session: Session
):
    response = client.put(
        f'{path_prefix}/{node.node_id}/endpoints/ipn',
        json=[
            {
                'uri': f'ipn:{node.allocator_id + 1}.{node.node_number}.3',
                'application': 'superseded mismatch',
            },
            {'service_number': 4, 'application': 'superseded'},
            {'service_number': 3, 'application': 'also superseded'},
            {
                'uri': f'ipn:{node.allocator_id}.{node.node_number}.4',
                'application': 'last four',
                'disposition': 'q',
            },
            {
                'service_number': 3,
                'application': 'last three',
                'disposition': 'x',
            },
        ],
    )
    assert response.status_code == 204
    session.refresh(node)
    assert [
        (e.service_number, e.application, e.disposition) for e in node.ipn_endpoints
    ] == [
        (3, 'last three', 'x'),
        (4, 'last four', 'q'),
    ]


def test_replace_endpoints_ipn_not_found(client: TestClient[Litestar], node: Node):
    response = client.put(f'{path_prefix}/{node.node_id + 1}/endpoints/ipn', json=[])
    assert response.status_code == 404
    assert f'Node ID {node.node_id + 1} does not exist' == response.json()['detail']


def test_replace_endpoints_ipn_conflicting_fqnn(
    client: TestClient[Litestar], node: Node
):
    fqnn = f'{node.allocator_id}, {node.node_number}'
    uri = f'ipn:{node.allocator_id + 1}.{node.node_number}.1'
    response = client.put(
        f'{path_prefix}/{node.node_id}/endpoints/ipn',
        json=[
            {'service_number': 1},
            {'service_number': 2},
            {'uri': uri},
        ],
    )
    assert response.status_code == 400
    assert (
        f'Fully Qualified Node Number of {uri} does not match that of node ID'
        f' {node.node_id} ({fqnn})'
    ) == response.json()['detail']
    assert (f'{uri} cannot be associated with the node') == response.json()['extra'][0][
        'message'
    ]
    assert '[2].uri' == response.json()['extra'][0]['key']
    assert 'body' == response.json()['extra'][0]['source']


def test_replace_endpoints_ipn_required_reqbody(client: TestClient[Litestar]):
    for response in [
        # Missing request body
        client.put(f'{path_prefix}/0/endpoints/ipn'),
        # Empty request body
        client.put(f'{path_prefix}/0/endpoints/ipn', content=b''),
    ]:
        assert response.status_code == 400
        assert 'Expected non-empty request' in response.json()['extra'][0]['message']


def test_replace_endpoints_ipn_null_reqbody(client: TestClient[Litestar]):
    # `null` is distinct from a missing / empty request body
    response = client.put(f'{path_prefix}/0/endpoints/ipn', content=b'null')
    assert response.status_code == 400
    assert 'Expected `array`, got `null`' in response.json()['extra'][0]['message']


def test_create_endpoint_ipn(client: TestClient[Litestar], node: Node):
    service_number = 2**16
    application = 'foo'
    disposition = 'q'
    response = client.post(
        f'{path_prefix}/{node.node_id}/endpoints/ipn',
        json={
            'service_number': service_number,
            'application': application,
            'disposition': disposition,
        },
    )
    assert response.status_code == 201
    assert response.json()['service_number'] == service_number
    assert response.json()['application'] == application
    assert response.json()['disposition'] == disposition
    assert (
        response.headers['location']
        == f'{API_V1_PATH}/nodes/{node.node_id}/endpoints/ipn/{service_number}'
    )


def test_create_endpoint_ipn_uri(client: TestClient[Litestar], node: Node):
    service_number = 2**16
    application = 'foo'
    disposition = 'q'
    uri = to_ipn_uri(node.allocator_id, node.node_number, service_number)
    response = client.post(
        f'{path_prefix}/{node.node_id}/endpoints/ipn',
        json={'uri': uri, 'application': application, 'disposition': disposition},
    )
    assert response.status_code == 201
    assert response.json()['service_number'] == service_number
    assert response.json()['application'] == application
    assert response.json()['disposition'] == disposition
    assert (
        response.headers['location']
        == f'{API_V1_PATH}/nodes/{node.node_id}/endpoints/ipn/{service_number}'
    )


def test_create_endpoint_ipn_unsafe_num(client: TestClient[Litestar], node: Node):
    application = 'foo'
    disposition = 'x'
    for i in range(2**53, 2**53 + 3):
        response = client.post(
            f'{path_prefix}/{node.node_id}/endpoints/ipn',
            json={
                'service_number': str(i),
                'application': application,
                'disposition': disposition,
            },
        )
        assert response.status_code == 201
        assert response.json()['service_number'] == str(i)
        assert response.json()['application'] == application
        assert response.json()['disposition'] == disposition
        assert (
            response.headers['location']
            == f'{API_V1_PATH}/nodes/{node.node_id}/endpoints/ipn/{i}'
        )


def test_create_endpoint_ipn_validation(client: TestClient[Litestar]):
    url = f'{path_prefix}/0/endpoints/ipn'
    # null uri and service_number
    for response in [
        client.post(url, json={}),
        client.post(url, json={'uri': None, 'service_number': None}),
        client.post(url, json={'uri': None}),
        client.post(url, json={'service_number': None}),
    ]:
        assert response.status_code == 400
        assert (
            response.json()['extra'][0]['message']
            == '`uri` and `service_number` cannot both be `null`'
        )
        assert response.json()['extra'][0]['key'] == 'uri'
        assert response.json()['extra'][0]['source'] == 'body'

    # Conflicting uri and service_number
    response = client.post(url, json={'uri': 'ipn:1.2.3', 'service_number': 4})
    assert response.status_code == 400
    assert (
        response.json()['extra'][0]['message']
        == '`service_number` (4) conflicts with service number of `uri` (ipn:1.2.3)'
    )
    assert response.json()['extra'][0]['key'] == 'service_number'
    assert response.json()['extra'][0]['source'] == 'body'

    # Invalid ipn URI
    for uri in ('dtn://abc', 'ipn:001.1', 'ipn:-1.-1.-1'):
        response = client.post(url, json={'uri': uri})
        assert response.status_code == 400
        assert (
            response.json()['extra'][0]['message']
            == f"'{uri}' does not comply with the text syntax of an ipn URI"
        )
        assert response.json()['extra'][0]['key'] == 'uri'
        assert response.json()['extra'][0]['source'] == 'body'

    # Exceed maximum values for allocator ID, node number, service number
    for name, uri, max_val in [
        (
            'Allocator Identifier',
            f'ipn:{ALLOCATOR_ID_MAX + 1}.0.0',
            ALLOCATOR_ID_MAX,
        ),
        (
            'Node Number',
            f'ipn:0.{NODE_NUMBER_MAX + 1}.0',
            NODE_NUMBER_MAX,
        ),
        (
            'Service Number',
            f'ipn:0.0.{SERVICE_NUMBER_MAX + 1}',
            SERVICE_NUMBER_MAX,
        ),
    ]:
        response = client.post(url, json={'uri': uri})
        assert response.status_code == 400
        assert response.json()['extra'][0]['message'] == (
            f'Expected {name} in `uri` ({uri}) <= {max_val}, but got {max_val + 1}'
        )
        assert response.json()['extra'][0]['key'] == 'uri'
        assert response.json()['extra'][0]['source'] == 'body'

    # Conflicting uri and service_number
    for uri, service_number in [('ipn:1.2.3', 4), ('ipn:1.2', 3), ('ipn:!.2', 3)]:
        response = client.post(url, json={'uri': uri, 'service_number': service_number})
        assert response.status_code == 400
        assert response.json()['extra'][0]['message'] == (
            f'`service_number` ({service_number}) conflicts with service number'
            f' of `uri` ({uri})'
        )
        assert response.json()['extra'][0]['key'] == 'service_number'
        assert response.json()['extra'][0]['source'] == 'body'

    # Invalid disposition
    response = client.post(
        url,
        json={'service_number': 34, 'disposition': 'discard'},
    )
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == "Invalid enum value 'discard'"
    assert response.json()['extra'][0]['key'] == 'disposition'

    # service_number out of range
    response = client.post(
        url,
        json={'service_number': SERVICE_NUMBER_MAX + 1},
    )
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == (
        f'Expected `int` <= {SERVICE_NUMBER_MAX}'
    )

    # node_id out of range
    response = client.post(f'{path_prefix}/{NODE_ID_MAX + 1}/endpoints/ipn', json={})
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == f'Expected `int` <= {NODE_ID_MAX}'


def test_create_endpoint_ipn_not_found(client: TestClient[Litestar], node: Node):
    response = client.post(
        f'{path_prefix}/{node.node_id + 1}/endpoints/ipn',
        json={'service_number': 2**16},
    )
    assert response.status_code == 404
    assert f'Node ID {node.node_id + 1} does not exist' == response.json()['detail']


def test_create_endpoint_ipn_conflicting_fqnn(client: TestClient[Litestar], node: Node):
    fqnn = f'{node.allocator_id}, {node.node_number}'
    uri = f'ipn:{node.allocator_id + 1}.{node.node_number}.1'
    response = client.post(
        f'{path_prefix}/{node.node_id}/endpoints/ipn', json={'uri': uri}
    )
    assert response.status_code == 400
    assert (
        f'Fully Qualified Node Number of {uri} does not match that of node ID'
        f' {node.node_id} ({fqnn})'
    ) == response.json()['detail']
    assert (f'{uri} cannot be associated with the node') == response.json()['extra'][0][
        'message'
    ]
    assert 'uri' == response.json()['extra'][0]['key']
    assert 'body' == response.json()['extra'][0]['source']


def test_create_endpoint_ipn_conflicting_eid(client: TestClient[Litestar], node: Node):
    service_number = node.ipn_endpoints[0].service_number
    response = client.post(
        f'{path_prefix}/{node.node_id}/endpoints/ipn',
        json={'service_number': service_number},
    )
    assert response.status_code == 400
    assert (
        'An endpoint with the URI'
        f' ipn:{node.allocator_id}.{node.node_number}.{service_number}'
        ' already exists'
    ) == response.json()['detail']


def test_create_endpoints_ipn_required_reqbody(client: TestClient[Litestar]):
    for response in [
        # Missing request body
        client.post(f'{path_prefix}/0/endpoints/ipn'),
        # Empty request body
        client.post(f'{path_prefix}/0/endpoints/ipn', content=b''),
    ]:
        assert response.status_code == 400
        assert 'Expected non-empty request' in response.json()['extra'][0]['message']


def test_create_endpoints_ipn_null_reqbody(client: TestClient[Litestar]):
    # `null` is distinct from a missing / empty request body
    response = client.post(f'{path_prefix}/0/endpoints/ipn', content=b'null')
    assert response.status_code == 400
    assert 'Expected `object`, got `null`' in response.json()['extra'][0]['message']


def test_update_endpoint_ipn(
    client: TestClient[Litestar], node: Node, session: Session
):
    old_service_number = node.ipn_endpoints[0].service_number
    service_number = 2**16
    application = 'foo'
    disposition = 'q'
    response = client.patch(
        f'{path_prefix}/{node.node_id}/endpoints/ipn/{old_service_number}',
        json={
            'service_number': service_number,
            'application': application,
            'disposition': disposition,
        },
    )
    assert response.status_code == 200
    assert response.json()['service_number'] == service_number
    assert response.json()['application'] == application
    assert response.json()['disposition'] == disposition
    assert (
        response.headers['content-location']
        == f'{API_V1_PATH}/nodes/{node.node_id}/endpoints/ipn/{service_number}'
    )
    session.refresh(node)
    for e in node.ipn_endpoints:
        assert e.service_number != old_service_number


def test_update_endpoint_ipn_uri(
    client: TestClient[Litestar], node: Node, session: Session
):
    old_service_number = node.ipn_endpoints[0].service_number
    service_number = 2**16
    application = 'foo'
    disposition = 'q'
    uri = to_ipn_uri(node.allocator_id, node.node_number, service_number)
    response = client.patch(
        f'{path_prefix}/{node.node_id}/endpoints/ipn/{old_service_number}',
        json={
            'uri': uri,
            'application': application,
            'disposition': disposition,
        },
    )
    assert response.status_code == 200
    assert response.json()['service_number'] == service_number
    assert response.json()['application'] == application
    assert response.json()['disposition'] == disposition
    assert (
        response.headers['content-location']
        == f'{API_V1_PATH}/nodes/{node.node_id}/endpoints/ipn/{service_number}'
    )
    session.refresh(node)
    for e in node.ipn_endpoints:
        assert e.service_number != old_service_number


def test_update_endpoint_ipn_unsafe_num(
    client: TestClient[Litestar], node: Node, session: Session
):
    old_service_number = node.ipn_endpoints[0].service_number
    application = 'foo'
    disposition = 'x'
    for i in range(2**53, 2**53 + 3):
        response = client.patch(
            f'{path_prefix}/{node.node_id}/endpoints/ipn/{old_service_number}',
            json={
                'service_number': str(i),
                'application': application,
                'disposition': disposition,
            },
        )
        assert response.status_code == 200
        assert response.json()['service_number'] == str(i)
        assert response.json()['application'] == application
        assert response.json()['disposition'] == disposition
        assert (
            response.headers['content-location']
            == f'{API_V1_PATH}/nodes/{node.node_id}/endpoints/ipn/{i}'
        )
        session.refresh(node)
        for e in node.ipn_endpoints:
            assert e.service_number != old_service_number
        old_service_number = i


def test_update_endpoint_ipn_no_change(
    client: TestClient[Litestar], node: Node, session: Session
):
    endpoint = node.ipn_endpoints[0]
    service_number = endpoint.service_number
    disposition = endpoint.disposition
    application = endpoint.application

    url = f'{path_prefix}/{node.node_id}/endpoints/ipn/{service_number}'
    for response in [
        # Missing request body
        client.patch(url),
        # Empty request body
        client.patch(url, content=b''),
        # Empty object
        client.patch(url, json={}),
        # Same values
        client.patch(
            url,
            json={
                'service_number': service_number,
                'disposition': disposition,
                'application': application,
            },
        ),
        client.patch(
            url,
            json={
                'uri': to_ipn_uri(node.allocator_id, node.node_number, service_number),
                'disposition': disposition,
                'application': application,
            },
        ),
    ]:
        assert response.status_code == 200
        assert response.json()['service_number'] == service_number
        assert response.json()['application'] == application
        assert response.json()['disposition'] == disposition
        assert (
            response.headers['content-location']
            == f'{API_V1_PATH}/nodes/{node.node_id}/endpoints/ipn/{service_number}'
        )
        session.refresh(endpoint)
        assert endpoint.service_number == service_number
        assert endpoint.application == application
        assert endpoint.disposition == disposition


def test_update_endpoint_ipn_validation(client: TestClient[Litestar]):
    url = f'{path_prefix}/0/endpoints/ipn/0'
    # Conflicting uri and service_number
    response = client.patch(url, json={'uri': 'ipn:1.2.3', 'service_number': 4})
    assert response.status_code == 400
    assert (
        response.json()['extra'][0]['message']
        == '`service_number` (4) conflicts with service number of `uri` (ipn:1.2.3)'
    )
    assert response.json()['extra'][0]['key'] == 'service_number'
    assert response.json()['extra'][0]['source'] == 'body'

    # Invalid ipn URI
    for uri in ('dtn://abc', 'ipn:001.1', 'ipn:-1.-1.-1'):
        response = client.patch(url, json={'uri': uri})
        assert response.status_code == 400
        assert (
            response.json()['extra'][0]['message']
            == f"'{uri}' does not comply with the text syntax of an ipn URI"
        )
        assert response.json()['extra'][0]['key'] == 'uri'
        assert response.json()['extra'][0]['source'] == 'body'

    # Exceed maximum values for allocator ID, node number, service number
    for name, uri, max_val in [
        (
            'Allocator Identifier',
            f'ipn:{ALLOCATOR_ID_MAX + 1}.0.0',
            ALLOCATOR_ID_MAX,
        ),
        (
            'Node Number',
            f'ipn:0.{NODE_NUMBER_MAX + 1}.0',
            NODE_NUMBER_MAX,
        ),
        (
            'Service Number',
            f'ipn:0.0.{SERVICE_NUMBER_MAX + 1}',
            SERVICE_NUMBER_MAX,
        ),
    ]:
        response = client.patch(url, json={'uri': uri})
        assert response.json()['extra'][0]['message'] == (
            f'Expected {name} in `uri` ({uri}) <= {max_val}, but got {max_val + 1}'
        )
        assert response.json()['extra'][0]['key'] == 'uri'
        assert response.json()['extra'][0]['source'] == 'body'

    # Conflicting uri and service_number
    for uri, service_number in [('ipn:1.2.3', 4), ('ipn:1.2', 3), ('ipn:!.2', 3)]:
        response = client.patch(
            url, json={'uri': uri, 'service_number': service_number}
        )
        assert response.status_code == 400
        assert response.json()['extra'][0]['message'] == (
            f'`service_number` ({service_number}) conflicts with service number'
            f' of `uri` ({uri})'
        )
        assert response.json()['extra'][0]['key'] == 'service_number'
        assert response.json()['extra'][0]['source'] == 'body'

    # Invalid disposition
    response = client.patch(
        url,
        json={'service_number': 34, 'disposition': 'discard'},
    )
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == "Invalid enum value 'discard'"
    assert response.json()['extra'][0]['key'] == 'disposition'

    # service_number out of range (path and body)
    response = client.patch(
        f'{path_prefix}/0/endpoints/ipn/{SERVICE_NUMBER_MAX + 1}',
    )
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == (
        f'Expected `int` <= {SERVICE_NUMBER_MAX}'
    )
    response = client.patch(
        url,
        json={'service_number': SERVICE_NUMBER_MAX + 1},
    )
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == (
        f'Expected `int` <= {SERVICE_NUMBER_MAX}'
    )

    # node_id out of range
    response = client.patch(f'{path_prefix}/{NODE_ID_MAX + 1}/endpoints/ipn/0')
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == f'Expected `int` <= {NODE_ID_MAX}'


def test_update_endpoint_ipn_not_found(client: TestClient[Litestar], node: Node):
    response = client.patch(
        f'{path_prefix}/{node.node_id + 1}/endpoints/ipn/0',
    )
    assert response.status_code == 404
    assert f'Node ID {node.node_id + 1} does not exist' == response.json()['detail']

    response = client.patch(
        f'{path_prefix}/{node.node_id}/endpoints/ipn/0',
    )
    assert response.status_code == 404
    assert (
        f'EID {to_ipn_uri(node.allocator_id, node.node_number, 0)} does not exist'
        == response.json()['detail']
    )


def test_update_endpoint_ipn_conflicting_fqnn(client: TestClient[Litestar], node: Node):
    service_number = node.ipn_endpoints[0].service_number
    fqnn = f'{node.allocator_id}, {node.node_number}'
    uri = f'ipn:{node.allocator_id + 1}.{node.node_number}.{service_number}'
    response = client.patch(
        f'{path_prefix}/{node.node_id}/endpoints/ipn/{service_number}',
        json={'uri': uri},
    )
    assert response.status_code == 400
    assert (
        f'Fully Qualified Node Number of {uri} does not match that of node ID'
        f' {node.node_id} ({fqnn})'
    ) == response.json()['detail']
    assert (f'{uri} cannot be associated with the node') == response.json()['extra'][0][
        'message'
    ]
    assert 'uri' == response.json()['extra'][0]['key']
    assert 'body' == response.json()['extra'][0]['source']


def test_update_endpoint_ipn_conflicting_eid(client: TestClient[Litestar], node: Node):
    service_number = node.ipn_endpoints[0].service_number
    service_number2 = node.ipn_endpoints[1].service_number
    response = client.patch(
        f'{path_prefix}/{node.node_id}/endpoints/ipn/{service_number}',
        json={'service_number': service_number2},
    )
    assert response.status_code == 400
    assert (
        'An endpoint with the URI'
        f' ipn:{node.allocator_id}.{node.node_number}.{service_number2}'
        ' already exists'
    ) == response.json()['detail']


def test_update_endpoint_ipn_null_reqbody(client: TestClient[Litestar]):
    # `null` is distinct from a missing / empty request body
    response = client.patch(f'{path_prefix}/0/endpoints/ipn/0', content=b'null')
    assert response.status_code == 400
    assert 'Expected `object`, got `null`' in response.json()['extra'][0]['message']


def test_delete_endpoint_ipn(client: TestClient[Litestar], node: Node):
    service_number = node.ipn_endpoints[0].service_number
    response = client.delete(
        f'{path_prefix}/{node.node_id}/endpoints/ipn/{service_number}'
    )
    assert response.status_code == 204
    # The record was deleted, so deleting again should error
    response = client.delete(
        f'{path_prefix}/{node.node_id}/endpoints/ipn/{service_number}'
    )
    assert response.status_code == 404
    assert (
        f'EID {to_ipn_uri(node.allocator_id, node.node_number, service_number)}'
        ' does not exist'
    ) in response.json()['detail']


def test_delete_endpoint_ipn_not_found(client: TestClient[Litestar], node: Node):
    response = client.delete(f'{path_prefix}/0/endpoints/ipn/0')
    assert response.status_code == 404
    assert 'Node ID 0 does not exist' in response.json()['detail']


def test_delete_endpoint_ipn_validation(client: TestClient[Litestar]):
    response = client.delete(f'{path_prefix}/{NODE_ID_MAX + 1}/endpoints/ipn/0')
    assert response.status_code == 400
    assert f'<= {NODE_ID_MAX}' in response.json()['extra'][0]['message']

    response = client.delete(f'{path_prefix}/0/endpoints/ipn/{SERVICE_NUMBER_MAX + 1}')
    assert response.status_code == 400
    assert f'<= {SERVICE_NUMBER_MAX}' in response.json()['extra'][0]['message']


def test_replace_endpoints_imc(
    client: TestClient[Litestar], node_with_imc_endpoints: Node, session: Session
):
    node = node_with_imc_endpoints
    old_endpoints = node.imc_endpoints
    last_group_nbr = old_endpoints[-1].group_number
    response = client.put(
        f'{path_prefix}/{node.node_id}/endpoints/imc',
        json=[
            {
                'group_number': last_group_nbr + 1,
                'application': 'foo',
                'disposition': 'q',
            },
            {
                'uri': f'imc:{last_group_nbr + 2}.0',
                'application': 'bar',
                'disposition': 'x',
            },
        ],
    )
    assert response.status_code == 204
    session.refresh(node)
    assert node.imc_endpoints != old_endpoints
    assert node.imc_endpoints[0].group_number == last_group_nbr + 1
    assert node.imc_endpoints[0].application == 'foo'
    assert node.imc_endpoints[0].disposition == 'q'
    assert node.imc_endpoints[1].group_number == last_group_nbr + 2
    assert node.imc_endpoints[1].application == 'bar'
    assert node.imc_endpoints[1].disposition == 'x'


def test_replace_endpoints_imc_unsafe_num(
    client: TestClient[Litestar], node_with_imc_endpoints: Node, session: Session
):
    node = node_with_imc_endpoints
    old_endpoints = node.imc_endpoints
    response = client.put(
        f'{path_prefix}/{node.node_id}/endpoints/imc',
        json=[
            {
                'group_number': 2**53,
                'application': 'foo',
                'disposition': 'q',
            },
            {
                'group_number': str(2**53 + 1),
                'application': 'bar',
                'disposition': 'x',
            },
            {
                'uri': f'imc:{2**53 + 2}.0',
                'application': 'baz',
                'disposition': 'x',
            },
        ],
    )
    assert response.status_code == 204
    session.refresh(node)
    assert node.imc_endpoints != old_endpoints
    assert node.imc_endpoints[0].group_number == 2**53
    assert node.imc_endpoints[0].application == 'foo'
    assert node.imc_endpoints[0].disposition == 'q'
    assert node.imc_endpoints[1].group_number == 2**53 + 1
    assert node.imc_endpoints[1].application == 'bar'
    assert node.imc_endpoints[1].disposition == 'x'
    assert node.imc_endpoints[2].group_number == 2**53 + 2
    assert node.imc_endpoints[2].application == 'baz'
    assert node.imc_endpoints[2].disposition == 'x'


def test_replace_endpoints_imc_empty(
    client: TestClient[Litestar], node_with_imc_endpoints: Node, session: Session
):
    node = node_with_imc_endpoints
    assert node.imc_endpoints
    response = client.put(f'{path_prefix}/{node.node_id}/endpoints/imc', json=[])
    assert response.status_code == 204
    session.refresh(node)
    assert not node.imc_endpoints


def test_replace_endpoints_imc_validation(client: TestClient[Litestar]):
    # null uri and group_number
    for response in [
        client.put(f'{path_prefix}/0/endpoints/imc', json=[{}]),
        client.put(
            f'{path_prefix}/0/endpoints/imc',
            json=[{'uri': None, 'group_number': None}],
        ),
        client.put(f'{path_prefix}/0/endpoints/imc', json=[{'uri': None}]),
        client.put(f'{path_prefix}/0/endpoints/imc', json=[{'group_number': None}]),
    ]:
        assert response.status_code == 400
        assert (
            response.json()['extra'][0]['message']
            == '`uri` and `group_number` cannot both be `null`'
        )
        assert response.json()['extra'][0]['key'] == '[0].uri'
        assert response.json()['extra'][0]['source'] == 'body'

    # Conflicting uri and group_number
    response = client.put(
        f'{path_prefix}/0/endpoints/imc',
        json=[{'uri': 'imc:3.0', 'group_number': 4}],
    )
    assert response.status_code == 400
    assert (
        response.json()['extra'][0]['message']
        == '`group_number` (4) conflicts with group number of `uri` (imc:3.0)'
    )
    assert response.json()['extra'][0]['key'] == '[0].group_number'
    assert response.json()['extra'][0]['source'] == 'body'

    # Invalid imc URI
    for uri, response in [
        (
            'dtn://abc',
            client.put(f'{path_prefix}/0/endpoints/imc', json=[{'uri': 'dtn://abc'}]),
        ),
        (
            'imc:3.4',
            client.put(f'{path_prefix}/0/endpoints/imc', json=[{'uri': 'imc:3.4'}]),
        ),
        (
            'imc:-1.0',
            client.put(f'{path_prefix}/0/endpoints/imc', json=[{'uri': 'imc:-1.0'}]),
        ),
    ]:
        assert response.status_code == 400
        assert (
            response.json()['extra'][0]['message']
            == f"'{uri}' does not comply with the text syntax of an imc URI"
        )
        assert response.json()['extra'][0]['key'] == '[0].uri'
        assert response.json()['extra'][0]['source'] == 'body'

    # Exceed maximum values for group number in uri
    response = client.put(
        f'{path_prefix}/0/endpoints/imc',
        json=[{'uri': f'imc:{GROUP_NUMBER_MAX + 1}.0'}],
    )
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == (
        f'Expected Group Number in `uri` (imc:{GROUP_NUMBER_MAX + 1}.0) <='
        f' {GROUP_NUMBER_MAX}, but got {GROUP_NUMBER_MAX + 1}'
    )
    assert response.json()['extra'][0]['key'] == '[0].uri'

    # Conflicting uri and group_number
    response = client.put(
        f'{path_prefix}/0/endpoints/imc', json=[{'uri': 'imc:3.0', 'group_number': 4}]
    )
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == (
        '`group_number` (4) conflicts with group number of `uri` (imc:3.0)'
    )
    assert response.json()['extra'][0]['key'] == '[0].group_number'
    assert response.json()['extra'][0]['source'] == 'body'

    # Invalid disposition
    response = client.put(
        f'{path_prefix}/0/endpoints/imc',
        json=[{'group_number': 34, 'disposition': 'discard'}],
    )
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == "Invalid enum value 'discard'"
    # TODO: include check for key == '[0].disposition' if Litestar merges my PR

    # group_number out of range
    response = client.put(
        f'{path_prefix}/0/endpoints/imc',
        json=[{'group_number': GROUP_NUMBER_MAX + 1}],
    )
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == (
        f'Expected `int` <= {GROUP_NUMBER_MAX}'
    )

    # node_id out of range
    response = client.put(f'{path_prefix}/{NODE_ID_MAX + 1}/endpoints/imc', json=[])
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == f'Expected `int` <= {NODE_ID_MAX}'


def test_replace_endpoints_imc_repeat_group_numbers(
    client: TestClient[Litestar], node_with_imc_endpoints: Node, session: Session
):
    node = node_with_imc_endpoints
    response = client.put(
        f'{path_prefix}/{node.node_id}/endpoints/imc',
        json=[
            {'uri': 'imc:3.0', 'application': 'superseded'},
            {'group_number': 4, 'application': 'superseded'},
            {'group_number': 3, 'application': 'also superseded'},
            {'uri': 'imc:4.0', 'application': 'last four', 'disposition': 'q'},
            {'group_number': 3, 'application': 'last three', 'disposition': 'x'},
        ],
    )
    assert response.status_code == 204
    session.refresh(node)
    assert [
        (e.group_number, e.application, e.disposition) for e in node.imc_endpoints
    ] == [
        (3, 'last three', 'x'),
        (4, 'last four', 'q'),
    ]


def test_replace_endpoints_imc_not_found(client: TestClient[Litestar], node: Node):
    response = client.put(f'{path_prefix}/{node.node_id + 1}/endpoints/imc', json=[])
    assert response.status_code == 404
    assert f'Node ID {node.node_id + 1} does not exist' == response.json()['detail']


def test_replace_endpoints_imc_required_reqbody(client: TestClient[Litestar]):
    for response in [
        # Missing request body
        client.put(f'{path_prefix}/0/endpoints/imc'),
        # Empty request body
        client.put(f'{path_prefix}/0/endpoints/imc', content=b''),
    ]:
        assert response.status_code == 400
        assert 'Expected non-empty request' in response.json()['extra'][0]['message']


def test_replace_endpoints_imc_null_reqbody(client: TestClient[Litestar]):
    # `null` is distinct from a missing / empty request body
    response = client.put(f'{path_prefix}/0/endpoints/imc', content=b'null')
    assert response.status_code == 400
    assert 'Expected `array`, got `null`' in response.json()['extra'][0]['message']


def test_create_endpoint_imc(client: TestClient[Litestar], node: Node):
    group_number = 2**16
    application = 'foo'
    disposition = 'q'
    response = client.post(
        f'{path_prefix}/{node.node_id}/endpoints/imc',
        json={
            'group_number': group_number,
            'application': application,
            'disposition': disposition,
        },
    )
    assert response.status_code == 201
    assert response.json()['group_number'] == group_number
    assert response.json()['application'] == application
    assert response.json()['disposition'] == disposition
    assert (
        response.headers['location']
        == f'{API_V1_PATH}/nodes/{node.node_id}/endpoints/imc/{group_number}'
    )


def test_create_endpoint_imc_uri(client: TestClient[Litestar], node: Node):
    group_number = 2**16
    application = 'foo'
    disposition = 'q'
    uri = to_imc_uri(group_number)
    response = client.post(
        f'{path_prefix}/{node.node_id}/endpoints/imc',
        json={'uri': uri, 'application': application, 'disposition': disposition},
    )
    assert response.status_code == 201
    assert response.json()['group_number'] == group_number
    assert response.json()['application'] == application
    assert response.json()['disposition'] == disposition
    assert (
        response.headers['location']
        == f'{API_V1_PATH}/nodes/{node.node_id}/endpoints/imc/{group_number}'
    )


def test_create_endpoint_imc_unsafe_num(client: TestClient[Litestar], node: Node):
    application = 'foo'
    disposition = 'x'
    for i in range(2**53, 2**53 + 3):
        response = client.post(
            f'{path_prefix}/{node.node_id}/endpoints/imc',
            json={
                'group_number': str(i),
                'application': application,
                'disposition': disposition,
            },
        )
        assert response.status_code == 201
        assert response.json()['group_number'] == str(i)
        assert response.json()['application'] == application
        assert response.json()['disposition'] == disposition
        assert (
            response.headers['location']
            == f'{API_V1_PATH}/nodes/{node.node_id}/endpoints/imc/{i}'
        )


def test_create_endpoint_imc_validation(client: TestClient[Litestar]):
    url = f'{path_prefix}/0/endpoints/imc'
    # null uri and group_number
    for response in [
        client.post(url, json={}),
        client.post(url, json={'uri': None, 'group_number': None}),
        client.post(url, json={'uri': None}),
        client.post(url, json={'group_number': None}),
    ]:
        assert response.status_code == 400
        assert (
            response.json()['extra'][0]['message']
            == '`uri` and `group_number` cannot both be `null`'
        )
        assert response.json()['extra'][0]['key'] == 'uri'
        assert response.json()['extra'][0]['source'] == 'body'

    # Conflicting uri and group_number
    response = client.post(url, json={'uri': 'imc:3.0', 'group_number': 4})
    assert response.status_code == 400
    assert (
        response.json()['extra'][0]['message']
        == '`group_number` (4) conflicts with group number of `uri` (imc:3.0)'
    )
    assert response.json()['extra'][0]['key'] == 'group_number'
    assert response.json()['extra'][0]['source'] == 'body'

    # Invalid imc URI
    for uri in ('dtn://abc', 'imc:3.4', 'imc:-1.0'):
        response = client.post(url, json={'uri': uri})
        assert response.status_code == 400
        assert (
            response.json()['extra'][0]['message']
            == f"'{uri}' does not comply with the text syntax of an imc URI"
        )
        assert response.json()['extra'][0]['key'] == 'uri'
        assert response.json()['extra'][0]['source'] == 'body'

    # Exceed maximum values for group number in uri
    response = client.post(url, json={'uri': f'imc:{GROUP_NUMBER_MAX + 1}.0'})
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == (
        f'Expected Group Number in `uri` (imc:{GROUP_NUMBER_MAX + 1}.0) <='
        f' {GROUP_NUMBER_MAX}, but got {GROUP_NUMBER_MAX + 1}'
    )
    assert response.json()['extra'][0]['key'] == 'uri'

    # Conflicting uri and service_number
    response = client.post(url, json={'uri': 'imc:3.0', 'group_number': 4})
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == (
        '`group_number` (4) conflicts with group number of `uri` (imc:3.0)'
    )
    assert response.json()['extra'][0]['key'] == 'group_number'
    assert response.json()['extra'][0]['source'] == 'body'

    # Invalid disposition
    response = client.post(
        url,
        json={'service_number': 34, 'disposition': 'discard'},
    )
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == "Invalid enum value 'discard'"
    assert response.json()['extra'][0]['key'] == 'disposition'

    # group_number out of range
    response = client.post(
        url,
        json={'group_number': GROUP_NUMBER_MAX + 1},
    )
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == (
        f'Expected `int` <= {GROUP_NUMBER_MAX}'
    )

    # node_id out of range
    response = client.post(f'{path_prefix}/{NODE_ID_MAX + 1}/endpoints/imc', json={})
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == f'Expected `int` <= {NODE_ID_MAX}'


def test_create_endpoint_imc_not_found(client: TestClient[Litestar], node: Node):
    response = client.post(
        f'{path_prefix}/{node.node_id + 1}/endpoints/imc',
        json={'group_number': 2**16},
    )
    assert response.status_code == 404
    assert f'Node ID {node.node_id + 1} does not exist' == response.json()['detail']


def test_create_endpoint_imc_conflicting_eid(
    client: TestClient[Litestar], node_with_imc_endpoints: Node
):
    node = node_with_imc_endpoints
    group_number = node.imc_endpoints[0].group_number
    response = client.post(
        f'{path_prefix}/{node.node_id}/endpoints/imc',
        json={'group_number': group_number},
    )
    assert response.status_code == 400
    assert (
        f'Node ID {node.node_id} is already associated with multicast EID'
        f' imc:{group_number}.0'
    ) == response.json()['detail']


def test_create_endpoints_imc_required_reqbody(client: TestClient[Litestar]):
    for response in [
        # Missing request body
        client.post(f'{path_prefix}/0/endpoints/imc'),
        # Empty request body
        client.post(f'{path_prefix}/0/endpoints/imc', content=b''),
    ]:
        assert response.status_code == 400
        assert 'Expected non-empty request' in response.json()['extra'][0]['message']


def test_create_endpoints_imc_null_reqbody(client: TestClient[Litestar]):
    # `null` is distinct from a missing / empty request body
    response = client.post(f'{path_prefix}/0/endpoints/imc', content=b'null')
    assert response.status_code == 400
    assert 'Expected `object`, got `null`' in response.json()['extra'][0]['message']


def test_update_endpoint_imc(
    client: TestClient[Litestar], node_with_imc_endpoints: Node, session: Session
):
    node = node_with_imc_endpoints
    old_group_number = node.imc_endpoints[0].group_number
    group_number = 2**16
    application = 'foo'
    disposition = 'q'
    response = client.patch(
        f'{path_prefix}/{node.node_id}/endpoints/imc/{old_group_number}',
        json={
            'group_number': group_number,
            'application': application,
            'disposition': disposition,
        },
    )
    assert response.status_code == 200
    assert response.json()['group_number'] == group_number
    assert response.json()['application'] == application
    assert response.json()['disposition'] == disposition
    assert (
        response.headers['content-location']
        == f'{API_V1_PATH}/nodes/{node.node_id}/endpoints/imc/{group_number}'
    )
    session.refresh(node)
    for e in node.imc_endpoints:
        assert e.group_number != old_group_number


def test_update_endpoint_imc_uri(
    client: TestClient[Litestar], node_with_imc_endpoints: Node, session: Session
):
    node = node_with_imc_endpoints
    old_group_number = node.imc_endpoints[0].group_number
    group_number = 2**16
    application = 'foo'
    disposition = 'q'
    uri = to_imc_uri(group_number)
    response = client.patch(
        f'{path_prefix}/{node.node_id}/endpoints/imc/{old_group_number}',
        json={
            'uri': uri,
            'application': application,
            'disposition': disposition,
        },
    )
    assert response.status_code == 200
    assert response.json()['group_number'] == group_number
    assert response.json()['application'] == application
    assert response.json()['disposition'] == disposition
    assert (
        response.headers['content-location']
        == f'{API_V1_PATH}/nodes/{node.node_id}/endpoints/imc/{group_number}'
    )
    session.refresh(node)
    for e in node.imc_endpoints:
        assert e.group_number != old_group_number


def test_update_endpoint_imc_unsafe_num(
    client: TestClient[Litestar], node_with_imc_endpoints: Node, session: Session
):
    node = node_with_imc_endpoints
    old_group_number = node.imc_endpoints[0].group_number
    application = 'foo'
    disposition = 'x'
    for i in range(2**53, 2**53 + 3):
        response = client.patch(
            f'{path_prefix}/{node.node_id}/endpoints/imc/{old_group_number}',
            json={
                'group_number': str(i),
                'application': application,
                'disposition': disposition,
            },
        )
        assert response.status_code == 200
        assert response.json()['group_number'] == str(i)
        assert response.json()['application'] == application
        assert response.json()['disposition'] == disposition
        assert (
            response.headers['content-location']
            == f'{API_V1_PATH}/nodes/{node.node_id}/endpoints/imc/{i}'
        )
        session.refresh(node)
        for e in node.imc_endpoints:
            assert e.group_number != old_group_number
        old_group_number = i


def test_update_endpoint_imc_no_change(
    client: TestClient[Litestar], node_with_imc_endpoints: Node, session: Session
):
    node = node_with_imc_endpoints
    endpoint = node.imc_endpoints[0]
    group_number = endpoint.group_number
    disposition = endpoint.disposition
    application = endpoint.application

    url = f'{path_prefix}/{node.node_id}/endpoints/imc/{group_number}'
    for response in [
        # Missing request body
        client.patch(url),
        # Empty request body
        client.patch(url, content=b''),
        # Empty object
        client.patch(url, json={}),
        # Same values
        client.patch(
            url,
            json={
                'group_number': group_number,
                'disposition': disposition,
                'application': application,
            },
        ),
        client.patch(
            url,
            json={
                'uri': to_imc_uri(group_number),
                'disposition': disposition,
                'application': application,
            },
        ),
    ]:
        assert response.status_code == 200
        assert response.json()['group_number'] == group_number
        assert response.json()['application'] == application
        assert response.json()['disposition'] == disposition
        assert (
            response.headers['content-location']
            == f'{API_V1_PATH}/nodes/{node.node_id}/endpoints/imc/{group_number}'
        )
        session.refresh(endpoint)
        assert endpoint.group_number == group_number
        assert endpoint.application == application
        assert endpoint.disposition == disposition


def test_update_endpoint_imc_validation(client: TestClient[Litestar]):
    url = f'{path_prefix}/0/endpoints/imc/1'
    # Conflicting uri and service_number
    response = client.patch(url, json={'uri': 'imc:3.0', 'group_number': 4})
    assert response.status_code == 400
    assert (
        response.json()['extra'][0]['message']
        == '`group_number` (4) conflicts with group number of `uri` (imc:3.0)'
    )
    assert response.json()['extra'][0]['key'] == 'group_number'
    assert response.json()['extra'][0]['source'] == 'body'

    # Invalid imc URI
    for uri in ('dtn://abc', 'imc:3.4', 'imc:-1.0'):
        response = client.patch(url, json={'uri': uri})
        assert response.status_code == 400
        assert (
            response.json()['extra'][0]['message']
            == f"'{uri}' does not comply with the text syntax of an imc URI"
        )
        assert response.json()['extra'][0]['key'] == 'uri'
        assert response.json()['extra'][0]['source'] == 'body'

    # Exceed maximum values for group number in uri
    response = client.patch(url, json={'uri': f'imc:{GROUP_NUMBER_MAX + 1}.0'})
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == (
        f'Expected Group Number in `uri` (imc:{GROUP_NUMBER_MAX + 1}.0) <='
        f' {GROUP_NUMBER_MAX}, but got {GROUP_NUMBER_MAX + 1}'
    )
    assert response.json()['extra'][0]['key'] == 'uri'

    # Conflicting uri and service_number
    response = client.patch(url, json={'uri': 'imc:3.0', 'group_number': 4})
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == (
        '`group_number` (4) conflicts with group number of `uri` (imc:3.0)'
    )
    assert response.json()['extra'][0]['key'] == 'group_number'
    assert response.json()['extra'][0]['source'] == 'body'

    # Invalid disposition
    response = client.patch(
        url,
        json={'service_number': 34, 'disposition': 'discard'},
    )
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == "Invalid enum value 'discard'"
    assert response.json()['extra'][0]['key'] == 'disposition'

    # service_number out of range (path and body)
    response = client.patch(
        f'{path_prefix}/0/endpoints/imc/{GROUP_NUMBER_MAX + 1}',
    )
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == (
        f'Expected `int` <= {GROUP_NUMBER_MAX}'
    )
    response = client.patch(
        url,
        json={'group_number': GROUP_NUMBER_MAX + 1},
    )
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == (
        f'Expected `int` <= {GROUP_NUMBER_MAX}'
    )

    # node_id out of range
    response = client.patch(f'{path_prefix}/{NODE_ID_MAX + 1}/endpoints/imc/0')
    assert response.status_code == 400
    assert response.json()['extra'][0]['message'] == f'Expected `int` <= {NODE_ID_MAX}'


def test_update_endpoint_imc_not_found(client: TestClient[Litestar], node: Node):
    response = client.patch(
        f'{path_prefix}/{node.node_id + 1}/endpoints/imc/1',
    )
    assert response.status_code == 404
    assert f'Node ID {node.node_id + 1} does not exist' == response.json()['detail']

    response = client.patch(
        f'{path_prefix}/{node.node_id}/endpoints/imc/1',
    )
    assert response.status_code == 404
    assert (
        f'Node ID {node.node_id} is not associated with multicast EID {to_imc_uri(1)}'
    ) == response.json()['detail']


def test_update_endpoint_imc_conflicting_eid(
    client: TestClient[Litestar], node_with_imc_endpoints: Node
):
    node = node_with_imc_endpoints
    group_number = node.imc_endpoints[0].group_number
    group_number2 = node.imc_endpoints[1].group_number
    response = client.patch(
        f'{path_prefix}/{node.node_id}/endpoints/imc/{group_number}',
        json={'group_number': group_number2},
    )
    assert response.status_code == 400
    assert (
        f'Node ID {node.node_id} is already associated with multicast EID'
        f' imc:{group_number2}.0'
    ) == response.json()['detail']


def test_update_endpoint_imc_null_reqbody(client: TestClient[Litestar]):
    # `null` is distinct from a missing / empty request body
    response = client.patch(f'{path_prefix}/0/endpoints/imc/1', content=b'null')
    assert response.status_code == 400
    assert 'Expected `object`, got `null`' in response.json()['extra'][0]['message']


def test_delete_endpoint_imc(
    client: TestClient[Litestar], node_with_imc_endpoints: Node
):
    node = node_with_imc_endpoints
    group_number = node.imc_endpoints[0].group_number
    response = client.delete(
        f'{path_prefix}/{node.node_id}/endpoints/imc/{group_number}'
    )
    assert response.status_code == 204
    # The record was deleted, so deleting again should error
    response = client.delete(
        f'{path_prefix}/{node.node_id}/endpoints/imc/{group_number}'
    )
    assert response.status_code == 404
    assert (
        f'Node ID {node.node_id} is not associated with multicast EID'
        f' {to_imc_uri(group_number)}'
    ) in response.json()['detail']


def test_delete_endpoint_imc_not_found(client: TestClient[Litestar]):
    response = client.delete(f'{path_prefix}/0/endpoints/imc/1')
    assert response.status_code == 404
    assert 'Node ID 0 does not exist' in response.json()['detail']


def test_delete_endpoint_imc_validation(client: TestClient[Litestar]):
    response = client.delete(f'{path_prefix}/{NODE_ID_MAX + 1}/endpoints/imc/1')
    assert response.status_code == 400
    assert f'<= {NODE_ID_MAX}' in response.json()['extra'][0]['message']

    response = client.delete(f'{path_prefix}/0/endpoints/imc/{GROUP_NUMBER_MAX + 1}')
    assert response.status_code == 400
    assert f'<= {GROUP_NUMBER_MAX}' in response.json()['extra'][0]['message']


def test_list_node_cl_protocols(
    client: TestClient[Litestar], node_with_cl_protocols: Node
):
    node = node_with_cl_protocols
    items = collect_paginated_data(
        client, f'{path_prefix}/{node.node_id}/cl-protocols', MAX_PAGE_SIZE
    )
    for p in node.cl_protocols:
        assert to_cl_protocol_without_node_id_schema(p).to_dict() in items


def test_list_node_cl_protocols_pagination(
    client: TestClient[Litestar], node_max_and_one_cl_protocols: Node
):
    node = node_max_and_one_cl_protocols
    items = collect_paginated_data(
        client, f'{path_prefix}/{node.node_id}/cl-protocols', 1
    )
    for p in node.cl_protocols:
        assert to_cl_protocol_without_node_id_schema(p).to_dict() in items

    params = {'max_page_size': 1, 'page_token': 'last'}
    response = client.get(f'{path_prefix}/{node.node_id}/cl-protocols', params=params)
    assert response.status_code == 200
    assert len(response.json()['items']) == params['max_page_size']
    assert response.json().get('prev_page_token') is not None
    assert response.json().get('next_page_token') is None
    assert items[-1] == response.json()['items'][0]


def test_list_node_cl_protocols_page_size(
    client: TestClient[Litestar], node_max_and_one_cl_protocols: Node
):
    node = node_max_and_one_cl_protocols
    check_page_size(client, f'{path_prefix}/{node.node_id}/cl-protocols')


def test_list_node_cl_protocols_invalid_page_token(
    client: TestClient[Litestar], node_max_and_one_cl_protocols: Node, node: Node
):
    other_node_id = node.node_id
    node = node_max_and_one_cl_protocols
    check_invalid_page_token_different_url(
        client,
        f'{path_prefix}/{node.node_id}/cl-protocols',
        f'{path_prefix}/{other_node_id}/cl-protocols',
    )


def test_list_node_cl_protocols_not_found(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/0/cl-protocols')
    assert response.status_code == 404
    assert 'ID 0 does not exist' in response.json()['detail']


def test_list_node_cl_protocols_validation(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/{NODE_ID_MAX + 1}/cl-protocols')
    assert response.status_code == 400
    assert f'<= {NODE_ID_MAX}' in response.json()['extra'][0]['message']

    check_paginated_request_validation(client, f'{path_prefix}/0/cl-protocols')


def test_create_cl_protocol(client: TestClient[Litestar], node: Node, session: Session):
    # node fixture does not create any CL protocols, so use whatever
    assert not node.cl_protocols
    new_name = 'foo'
    new_class = ['BP_BEST_EFFORT', 'BP_RELIABLE']
    response = client.post(
        f'{path_prefix}/{node.node_id}/cl-protocols',
        json={'cl_protocol_name': new_name, 'cl_protocol_class': new_class},
    )
    assert response.status_code == 201
    assert response.json()['node_id'] == str(node.node_id)
    assert response.json()['cl_protocol_name'] == new_name
    assert response.json()['cl_protocol_class'] == new_class
    session.refresh(node)
    assert node.cl_protocols
    assert node.cl_protocols[0].cl_protocol_name == new_name
    assert node.cl_protocols[0].cl_protocol_class == protocol_class_arr_to_int(
        new_class
    )
    assert (
        response.headers['location']
        == f'{API_V1_PATH}/cl-protocols/{response.json()["cl_protocol_id"]}'
    )
    assert (
        response.headers['content-location']
        == f'{API_V1_PATH}/cl-protocols/{response.json()["cl_protocol_id"]}'
    )


def test_create_cl_protocol_default_class(client: TestClient[Litestar], node: Node):
    d = {
        8: ['tcp', 'stcp', 'dgr', 'dccp', 'brss', 'brsc'],
        10: ['bssp', 'ltp', 'bibe'],
        2: ['udp'],
    }
    for class_val, name_list in d.items():
        for n in name_list:
            r = client.post(
                f'{path_prefix}/{node.node_id}/cl-protocols',
                json={'cl_protocol_name': n},
            )
            assert r.status_code == 201
            assert r.json()['node_id'] == str(node.node_id)
            assert r.json()['cl_protocol_name'] == n
            assert r.json()['cl_protocol_class'] == protocol_class_int_to_arr(class_val)


def test_create_cl_protocol_duplicate_class(client: TestClient[Litestar], node: Node):
    response = client.post(
        f'{path_prefix}/{node.node_id}/cl-protocols',
        json={
            'cl_protocol_name': 'foo',
            'cl_protocol_class': ['BP_BEST_EFFORT' for _ in range(2)],
        },
    )
    assert response.status_code == 201
    assert response.json()['node_id'] == str(node.node_id)
    assert response.json()['cl_protocol_name'] == 'foo'
    assert response.json()['cl_protocol_class'] == ['BP_BEST_EFFORT']


def test_create_cl_protocol_existing(
    client: TestClient[Litestar], cl_protocol: ClProtocol
):
    node_id = cl_protocol.node_id
    response = client.post(
        f'{path_prefix}/{node_id}/cl-protocols',
        json={
            'cl_protocol_name': cl_protocol.cl_protocol_name,
            'cl_protocol_class': protocol_class_int_to_arr(
                cl_protocol.cl_protocol_class
            ),
        },
    )
    assert response.status_code == 400
    assert response.json()['detail'] == (
        f"A CL protocol with the name '{cl_protocol.cl_protocol_name}' is already"
        f' associated with node ID {node_id}'
    )


def test_create_cl_protocol_well_known_protocol(
    client: TestClient[Litestar], node: Node
):
    response = client.post(
        f'{path_prefix}/{node.node_id}/cl-protocols',
        json={
            'cl_protocol_name': 'ltp',
            'cl_protocol_class': protocol_class_int_to_arr(2),
        },
    )
    assert response.status_code == 400
    assert response.json()['detail'] == (
        "CL protocol name 'ltp' must use protocol class"
        f' {protocol_class_int_to_arr(10)}'
    )


def test_create_cl_protocol_not_found(client: TestClient[Litestar]):
    response = client.post(
        f'{path_prefix}/0/cl-protocols', json={'cl_protocol_name': 'blah'}
    )
    assert response.status_code == 404
    assert response.json()['detail'] == 'Node ID 0 does not exist'


def test_create_cl_protocol_validate_required_reqbody(client: TestClient[Litestar]):
    for response in [
        # Missing request body
        client.post(f'{path_prefix}/0/cl-protocols'),
        # Empty request body
        client.post(f'{path_prefix}/0/cl-protocols', content=b''),
    ]:
        assert response.status_code == 400
        assert 'Expected non-empty request' in response.json()['extra'][0]['message']


def test_create_cl_protocol_validation(client: TestClient[Litestar]):
    url = f'{path_prefix}/0/cl-protocols'
    # Out of range name
    for r in [
        client.post(url, json={'cl_protocol_name': ''}),
        client.post(url, json={'cl_protocol_name': 'A' * 16}),
    ]:
        assert r.status_code == 400
        assert r.json()['extra'][0]['message'] == (
            'Length in bytes must be in the inclusive range [1, 15]'
        )
        assert r.json()['extra'][0]['key'] == 'cl_protocol_name'
        assert r.json()['extra'][0]['source'] == 'body'

    # Invalid enum
    response = client.post(
        url,
        json={'cl_protocol_name': 'foo', 'cl_protocol_class': ['BP_MINIMAL_LATENCY']},
    )
    assert response.status_code == 400
    assert response.json()['extra'] == [
        {
            'message': "Invalid enum value 'BP_MINIMAL_LATENCY'",
            'key': 'cl_protocol_class[0]',
            'source': 'body',
        }
    ]

    # Empty class
    response = client.post(
        url,
        json={'cl_protocol_name': 'foo', 'cl_protocol_class': []},
    )
    assert response.status_code == 400
    assert response.json()['extra'] == [
        {
            'message': 'Expected `array` of length >= 1',
            'key': 'cl_protocol_class',
            'source': 'body',
        }
    ]

    # Too many class
    response = client.post(
        url,
        json={
            'cl_protocol_name': 'foo',
            'cl_protocol_class': ['BP_BEST_EFFORT' for _ in range(3)],
        },
    )
    assert response.status_code == 400
    assert response.json()['extra'] == [
        {
            'message': 'Expected `array` of length <= 2',
            'key': 'cl_protocol_class',
            'source': 'body',
        }
    ]

    # node_id out of range
    response = client.post(
        f'{path_prefix}/{NODE_ID_MAX + 1}/cl-protocols',
        json={'cl_protocol_name': 'foo'},
    )
    assert response.status_code == 400
    assert f'<= {NODE_ID_MAX}' in response.json()['extra'][0]['message']


def test_list_node_inducts(client: TestClient[Litestar], node_with_inducts: Node):
    node = node_with_inducts
    items = collect_paginated_data(
        client, f'{path_prefix}/{node.node_id}/inducts', MAX_PAGE_SIZE
    )
    for i in node.inducts:
        assert to_induct_without_node_id_schema(i).to_dict() in items


def test_list_node_inducts_pagination(
    client: TestClient[Litestar], node_max_and_one_inducts: Node
):
    node = node_max_and_one_inducts
    items = collect_paginated_data(client, f'{path_prefix}/{node.node_id}/inducts', 1)
    for i in node.inducts:
        assert to_induct_without_node_id_schema(i).to_dict() in items

    params = {'max_page_size': 1, 'page_token': 'last'}
    response = client.get(f'{path_prefix}/{node.node_id}/inducts', params=params)
    assert response.status_code == 200
    assert len(response.json()['items']) == params['max_page_size']
    assert response.json().get('prev_page_token') is not None
    assert response.json().get('next_page_token') is None
    assert items[-1] == response.json()['items'][0]


def test_list_node_inducts_page_size(
    client: TestClient[Litestar], node_max_and_one_inducts: Node
):
    node = node_max_and_one_inducts
    check_page_size(client, f'{path_prefix}/{node.node_id}/inducts')


def test_list_node_inducts_invalid_page_token(
    client: TestClient[Litestar], node_max_and_one_inducts: Node, node: Node
):
    other_node_id = node.node_id
    node = node_max_and_one_inducts
    check_invalid_page_token_different_url(
        client,
        f'{path_prefix}/{node.node_id}/inducts',
        f'{path_prefix}/{other_node_id}/inducts',
    )


def test_list_node_inducts_not_found(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/0/inducts')
    assert response.status_code == 404
    assert 'ID 0 does not exist' in response.json()['detail']


def test_list_node_inducts_validation(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/{NODE_ID_MAX + 1}/inducts')
    assert response.status_code == 400
    assert f'<= {NODE_ID_MAX}' in response.json()['extra'][0]['message']

    check_paginated_request_validation(client, f'{path_prefix}/0/inducts')


def test_create_induct(client: TestClient[Litestar], cl_protocol: ClProtocol):
    node = cl_protocol.node
    duct_name = 'foo'
    cli_command = 'bar'
    uses_ltp = True
    response = client.post(
        f'{path_prefix}/{node.node_id}/inducts',
        json={
            'cl_protocol_id': cl_protocol.cl_protocol_id,
            'duct_name': duct_name,
            'cli_command': cli_command,
            'uses_ltp': uses_ltp,
        },
    )
    assert response.status_code == 201
    assert str(node.node_id) == response.json()['node_id']
    assert response.json()['cl_protocol']['cl_protocol_id'] == str(
        cl_protocol.cl_protocol_id
    )
    assert response.json()['duct_name']['value'] == duct_name
    assert response.json()['duct_name']['type'] == DuctNameTagEnum.PLAIN
    assert response.json()['cli_command'] == cli_command
    assert response.json()['uses_ltp'] == uses_ltp
    assert (
        response.headers['location']
        == f'{API_V1_PATH}/inducts/{response.json()["induct_id"]}'
    )
    assert (
        response.headers['content-location']
        == f'{API_V1_PATH}/inducts/{response.json()["induct_id"]}'
    )


def test_create_induct_ip(client: TestClient[Litestar], cl_protocol: ClProtocol):
    node = cl_protocol.node
    host = node.host
    dest = host.destinations[0]
    cli_command = 'bar'
    uses_ltp = True
    port_number = 34
    response = client.post(
        f'{path_prefix}/{node.node_id}/inducts',
        json={
            'cl_protocol_id': cl_protocol.cl_protocol_id,
            'duct_name': {
                'type': DuctNameTagEnum.IP,
                'destination_id': dest.destination_id,
                'port_number': port_number,
            },
            'cli_command': cli_command,
            'uses_ltp': uses_ltp,
        },
    )
    assert response.status_code == 201
    assert str(node.node_id) == response.json()['node_id']
    assert response.json()['cl_protocol']['cl_protocol_id'] == str(
        cl_protocol.cl_protocol_id
    )
    assert (
        response.json()['duct_name']['value']
        == f'{process_destination_value(dest)}:{port_number}'
    )
    assert response.json()['duct_name']['type'] == DuctNameTagEnum.IP
    assert response.json()['duct_name']['destination']['destination_id'] == str(
        dest.destination_id
    )
    assert response.json()['duct_name']['port_number'] == port_number
    assert response.json()['cli_command'] == cli_command
    assert response.json()['uses_ltp'] == uses_ltp
    assert (
        response.headers['location']
        == f'{API_V1_PATH}/inducts/{response.json()["induct_id"]}'
    )
    assert (
        response.headers['content-location']
        == f'{API_V1_PATH}/inducts/{response.json()["induct_id"]}'
    )


def test_create_induct_defaults(client: TestClient[Litestar], node: Node):
    for response in [
        client.post(f'{path_prefix}/{node.node_id}/inducts'),
        client.post(f'{path_prefix}/{node.node_id}/inducts', content=b''),
        client.post(f'{path_prefix}/{node.node_id}/inducts', json={}),
    ]:
        assert response.status_code == 201
        assert str(node.node_id) == response.json()['node_id']
        assert response.json()['cl_protocol'] is None
        assert response.json()['duct_name']['value'] is None
        assert response.json()['duct_name']['type'] == DuctNameTagEnum.PLAIN
        assert response.json()['cli_command'] is None
        assert response.json()['uses_ltp'] == False

    response = client.post(
        f'{path_prefix}/{node.node_id}/inducts', json={'duct_name': {}}
    )
    assert response.status_code == 201
    assert str(node.node_id) == response.json()['node_id']
    assert response.json()['cl_protocol'] is None
    assert response.json()['duct_name']['value'] is None
    assert response.json()['duct_name']['type'] == DuctNameTagEnum.IP
    assert response.json()['duct_name']['destination'] is None
    assert response.json()['duct_name']['port_number'] is None
    assert response.json()['cli_command'] is None
    assert response.json()['uses_ltp'] == False


def test_create_induct_not_found(client: TestClient[Litestar], node: Node):
    response = client.post(f'{path_prefix}/0/inducts')
    assert response.status_code == 404
    assert 'Node ID 0 does not exist' in response.json()['detail']

    response = client.post(
        f'{path_prefix}/{node.node_id}/inducts', json={'cl_protocol_id': 0}
    )
    assert response.status_code == 404
    assert 'CL protocol ID 0 does not exist' in response.json()['detail']

    response = client.post(
        f'{path_prefix}/{node.node_id}/inducts',
        json={'duct_name': {'type': DuctNameTagEnum.IP, 'destination_id': 0}},
    )
    assert response.status_code == 404
    assert 'Destination ID 0 does not exist' in response.json()['detail']


def test_create_induct_no_ownership(
    client: TestClient[Litestar],
    node: Node,
    cl_protocol: ClProtocol,
    destination_ip: Destination,
):
    url = f'{path_prefix}/{node.node_id}/inducts'
    response = client.post(url, json={'cl_protocol_id': cl_protocol.cl_protocol_id})
    assert response.status_code == 400
    assert (
        f'CL protocol ID {cl_protocol.cl_protocol_id} does not belong to node ID'
        f' {node.node_id}'
    ) == response.json()['detail']

    response = client.post(
        url,
        json={
            'duct_name': {
                'type': DuctNameTagEnum.IP,
                'destination_id': destination_ip.destination_id,
            }
        },
    )
    assert response.status_code == 400
    assert (
        f'Destination ID {destination_ip.destination_id} belongs to a different'
        f' host than host ID {node.host_id}'
    ) in response.json()['detail']


def test_create_induct_destination_hostless_node(
    client: TestClient[Litestar], node_no_host: Node, induct_ip: InductIp
):
    node = node_no_host
    response = client.post(
        f'{path_prefix}/{node.node_id}/inducts',
        json={
            'duct_name': {
                'type': DuctNameTagEnum.IP,
                'destination_id': induct_ip.destination_id,
                'port_number': induct_ip.port_number,
            }
        },
    )
    assert response.status_code == 400
    assert (
        'A destination cannot be associated with an induct when the node is not'
        ' on a host.'
    ) == response.json()['detail']


def test_create_induct_wrong_cl_protocol_for_cli(
    client: TestClient[Litestar], cl_protocol_gibberish_name: ClProtocol
):
    node = cl_protocol_gibberish_name.node
    for cli, p_name in cli_command_with_required_protocol_name:
        r = client.post(
            f'{path_prefix}/{node.node_id}/inducts',
            json={
                'cl_protocol_id': cl_protocol_gibberish_name.cl_protocol_id,
                'cli_command': cli,
            },
        )
        assert r.status_code == 400
        assert (
            f"`cli_command` ('{cli}') must be associated with an induct that"
            f" uses a `cl_protocol_name` of '{p_name}'"
        ) == r.json()['detail']


def test_create_induct_wrong_uses_ltp_for_cli(
    client: TestClient[Litestar], cl_protocols_for_known_cli_same_node: list[ClProtocol]
):
    node = cl_protocols_for_known_cli_same_node[0].node
    cl_protocol_name_to_id = {
        p.cl_protocol_name: p.cl_protocol_id
        for p in cl_protocols_for_known_cli_same_node
    }

    for cli, p_name in cli_command_with_required_protocol_name:
        r = client.post(
            f'{path_prefix}/{node.node_id}/inducts',
            json={
                'cl_protocol_id': cl_protocol_name_to_id[p_name],
                'cli_command': cli,
                'uses_ltp': p_name != 'ltp',
            },
        )
        assert r.status_code == 400
        if p_name == 'ltp':
            assert (
                "`uses_ltp` must be true when `cli_command` is 'ltpcli'"
                == r.json()['detail']
            )
        else:
            assert '`uses_ltp` must be false' in r.json()['detail']


def test_create_induct_no_duct_name_known_cli(
    client: TestClient[Litestar], cl_protocols_for_known_cli_same_node: list[ClProtocol]
):
    node = cl_protocols_for_known_cli_same_node[0].node
    cl_protocol_name_to_id = {
        p.cl_protocol_name: p.cl_protocol_id
        for p in cl_protocols_for_known_cli_same_node
    }

    for cli in no_duct_name_known_cli_not_ip:
        p_name = cli_p_name_dict[cli]
        r = client.post(
            f'{path_prefix}/{node.node_id}/inducts',
            json={
                'cl_protocol_id': cl_protocol_name_to_id[p_name],
                'cli_command': cli,
                'duct_name': 'blahblah',
                'uses_ltp': p_name == 'ltp',
            },
        )
        assert r.status_code == 400
        assert (
            '`duct_name` must be null when `cli_command` is in'
            f' {no_duct_name_known_cli_not_ip}'
        ) in r.json()['detail']


def test_create_induct_brsccla_no_ip(
    client: TestClient[Litestar], cl_protocols_for_known_cli_same_node: list[ClProtocol]
):
    node = cl_protocols_for_known_cli_same_node[0].node
    cl_protocol_name_to_id = {
        p.cl_protocol_name: p.cl_protocol_id
        for p in cl_protocols_for_known_cli_same_node
    }
    cli = 'brsccla'
    p_name = cli_p_name_dict[cli]
    r = client.post(
        f'{path_prefix}/{node.node_id}/inducts',
        json={
            'cl_protocol_id': cl_protocol_name_to_id[p_name],
            'cli_command': cli,
            'duct_name': {'type': DuctNameTagEnum.IP},
            'uses_ltp': p_name == 'ltp',
        },
    )
    assert r.status_code == 400
    assert (
        f"`cli_command` ('{cli}') does not use an 'ip:port' format for"
        ' "duct_name", so an "ip" type object cannot be used for'
        ' `duct_name`'
    ) == r.json()['detail']


def test_create_induct_validation(client: TestClient[Litestar]):
    # node_id out of range
    response = client.post(f'{path_prefix}/{NODE_ID_MAX + 1}/inducts')
    assert response.status_code == 400
    assert f'<= {NODE_ID_MAX}' in response.json()['extra'][0]['message']

    # cl_protocol_id out of range
    response = client.post(
        f'{path_prefix}/0/inducts', json={'cl_protocol_id': CL_PROTOCOL_ID_MAX + 1}
    )
    assert response.status_code == 400
    assert f'<= {CL_PROTOCOL_ID_MAX}' in response.json()['extra'][0]['message']

    # destination_id out of range
    response = client.post(
        f'{path_prefix}/0/inducts',
        json={'duct_name': {'destination_id': DESTINATION_ID_MAX + 1}},
    )
    assert response.status_code == 400
    assert f'<= {DESTINATION_ID_MAX}' in response.json()['extra'][0]['message']

    # port_number out of range
    response = client.post(
        f'{path_prefix}/0/inducts',
        json={'duct_name': {'port_number': PORT_NUMBER_MAX + 1}},
    )
    assert response.status_code == 400
    assert f'<= {PORT_NUMBER_MAX}' in response.json()['extra'][0]['message']


def test_list_node_seats(client: TestClient[Litestar], node_with_seats: Node):
    node = node_with_seats
    items = collect_paginated_data(
        client, f'{path_prefix}/{node.node_id}/seats', MAX_PAGE_SIZE
    )
    for s in node.seats:
        assert to_seat_without_node_id_schema(s).to_dict() in items


def test_list_node_seats_pagination(
    client: TestClient[Litestar], node_max_and_one_seats: Node
):
    node = node_max_and_one_seats
    items = collect_paginated_data(client, f'{path_prefix}/{node.node_id}/seats', 1)
    for s in node.seats:
        assert to_seat_without_node_id_schema(s).to_dict() in items

    params = {'max_page_size': 1, 'page_token': 'last'}
    response = client.get(f'{path_prefix}/{node.node_id}/seats', params=params)
    assert response.status_code == 200
    assert len(response.json()['items']) == params['max_page_size']
    assert response.json().get('prev_page_token') is not None
    assert response.json().get('next_page_token') is None
    assert items[-1] == response.json()['items'][0]


def test_list_node_seats_page_size(
    client: TestClient[Litestar], node_max_and_one_seats: Node
):
    node = node_max_and_one_seats
    check_page_size(client, f'{path_prefix}/{node.node_id}/seats')


def test_list_node_seats_invalid_page_token(
    client: TestClient[Litestar], node_max_and_one_seats: Node, node: Node
):
    other_node_id = node.node_id
    node = node_max_and_one_seats
    check_invalid_page_token_different_url(
        client,
        f'{path_prefix}/{node.node_id}/seats',
        f'{path_prefix}/{other_node_id}/seats',
    )


def test_list_node_seats_not_found(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/0/seats')
    assert response.status_code == 404
    assert 'ID 0 does not exist' in response.json()['detail']


def test_list_node_seats_validation(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/{NODE_ID_MAX + 1}/seats')
    assert response.status_code == 400
    assert f'<= {NODE_ID_MAX}' in response.json()['extra'][0]['message']

    check_paginated_request_validation(client, f'{path_prefix}/0/seats')


def test_create_seat(client: TestClient[Litestar], node: Node):
    lsi_command = 'foo'
    response = client.post(
        f'{path_prefix}/{node.node_id}/seats', json={'lsi_command': lsi_command}
    )
    assert response.status_code == 201
    assert str(node.node_id) == response.json()['node_id']
    assert lsi_command == response.json()['lsi_command_full']
    assert lsi_command == response.json()['lsi_command']
    assert response.json()['seat_ip'] is None
    assert (
        response.headers['location']
        == f'{API_V1_PATH}/seats/{response.json()["seat_id"]}'
    )
    assert (
        response.headers['content-location']
        == f'{API_V1_PATH}/seats/{response.json()["seat_id"]}'
    )


def test_create_seat_ip(client: TestClient[Litestar], node: Node):
    host = node.host
    dest = host.destinations[0]
    lsi_command = 'foo'
    port_number = 34
    response = client.post(
        f'{path_prefix}/{node.node_id}/seats',
        json={
            'lsi_command': lsi_command,
            'seat_ip': {
                'destination_id': dest.destination_id,
                'port_number': port_number,
            },
        },
    )
    assert response.status_code == 201
    assert str(node.node_id) == response.json()['node_id']
    assert response.json()['lsi_command_full'] == (
        f'{lsi_command} {process_destination_value(dest)}:{port_number}'
    )
    assert response.json()['lsi_command'] == lsi_command
    assert response.json()['seat_ip']['destination']['destination_id'] == str(
        dest.destination_id
    )
    assert response.json()['seat_ip']['port_number'] == port_number
    assert (
        response.headers['location']
        == f'{API_V1_PATH}/seats/{response.json()["seat_id"]}'
    )
    assert (
        response.headers['content-location']
        == f'{API_V1_PATH}/seats/{response.json()["seat_id"]}'
    )


def test_create_seats_defaults(client: TestClient[Litestar], node: Node):
    for response in [
        client.post(f'{path_prefix}/{node.node_id}/seats'),
        client.post(f'{path_prefix}/{node.node_id}/seats', content=b''),
        client.post(f'{path_prefix}/{node.node_id}/seats', json={}),
    ]:
        assert response.status_code == 201
        assert str(node.node_id) == response.json()['node_id']
        assert response.json()['lsi_command_full'] is None
        assert response.json()['lsi_command'] is None
        assert response.json()['seat_ip'] is None

    response = client.post(f'{path_prefix}/{node.node_id}/seats', json={'seat_ip': {}})
    assert response.status_code == 201
    assert str(node.node_id) == response.json()['node_id']
    assert response.json()['lsi_command_full'] is None
    assert response.json()['lsi_command'] is None
    assert response.json()['seat_ip']['destination'] is None
    assert response.json()['seat_ip']['port_number'] is None


def test_create_seat_not_found(client: TestClient[Litestar], node: Node):
    response = client.post(f'{path_prefix}/0/seats')
    assert response.status_code == 404
    assert 'Node ID 0 does not exist' in response.json()['detail']

    response = client.post(
        f'{path_prefix}/{node.node_id}/seats',
        json={'seat_ip': {'destination_id': 0}},
    )
    assert response.status_code == 404
    assert 'Destination ID 0 does not exist' in response.json()['detail']


def test_create_seat_no_ownership(
    client: TestClient[Litestar],
    node: Node,
    destination_ip: Destination,
):
    response = client.post(
        f'{path_prefix}/{node.node_id}/seats',
        json={'seat_ip': {'destination_id': destination_ip.destination_id}},
    )
    assert response.status_code == 400
    assert (
        f'Destination ID {destination_ip.destination_id} belongs to a different'
        f' host than host ID {node.host_id}'
    ) in response.json()['detail']


def test_create_seat_destination_hostless_node(
    client: TestClient[Litestar], node_no_host: Node, seat_ip: SeatIp
):
    node = node_no_host
    response = client.post(
        f'{path_prefix}/{node.node_id}/seats',
        json={
            'seat_ip': {
                'destination_id': seat_ip.destination_id,
                'port_number': seat_ip.port_number,
            }
        },
    )
    assert response.status_code == 400
    assert (
        'A destination cannot be associated with a seat when the node is not on a host.'
    ) == response.json()['detail']


def test_create_seat_validation(client: TestClient[Litestar]):
    # node_id out of range
    response = client.post(f'{path_prefix}/{NODE_ID_MAX + 1}/seats')
    assert response.status_code == 400
    assert f'<= {NODE_ID_MAX}' in response.json()['extra'][0]['message']

    # destination_id out of range
    response = client.post(
        f'{path_prefix}/0/seats',
        json={'seat_ip': {'destination_id': DESTINATION_ID_MAX + 1}},
    )
    assert response.status_code == 400
    assert f'<= {DESTINATION_ID_MAX}' in response.json()['extra'][0]['message']

    # port_number out of range
    response = client.post(
        f'{path_prefix}/0/seats',
        json={'seat_ip': {'port_number': PORT_NUMBER_MAX + 1}},
    )
    assert response.status_code == 400
    assert f'<= {PORT_NUMBER_MAX}' in response.json()['extra'][0]['message']

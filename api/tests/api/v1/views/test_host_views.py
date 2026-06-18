from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

from app.api.v1.band.schemas import to_schema as to_band_schema
from app.api.v1.destination.schemas import to_destination_without_host_id_schema
from app.api.v1.host.schemas import HostSchema, to_host_schema
from app.api.v1.host.service import get as host_get
from app.api.v1.link.schemas import LinkSchema, to_link_schema
from app.api.v1.node.schemas import NodeCopyForHostSchema
from app.api.v1.underlying_communication_service.schemas import (
    to_underlying_communication_service_schema as to_ucs_schema,
)
from app.config import API_V1_PATH, MAX_PAGE_SIZE
from app.fields import (
    ALLOCATOR_ID_MAX,
    BAND_ID_MAX,
    HOST_ID_MAX,
    NODE_ID_MAX,
    NODE_NUMBER_MAX,
    OPERATOR_ID_MAX,
    SANA_SCID_MAX,
    UNDERLYING_COMMUNICATION_SERVICE_ID_MAX,
)
from app.models import NewlineEnum
from tests.api.v1.service.test_host_service import check_copied_host_equality
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
        Band,
        Destination,
        Host,
        Node,
        Operator,
        UnderlyingCommunicationService,
    )

host_decoder = msgspec.json.Decoder(type=HostSchema, strict=False)
link_decoder = msgspec.json.Decoder(type=LinkSchema, strict=False)
path_prefix = f'{API_V1_PATH}/hosts'


def test_get_host(client: TestClient[Litestar], host: Host):
    response = client.get(f'{path_prefix}/{host.host_id}')
    assert response.status_code == 200
    assert host_decoder.decode(response.content) == to_host_schema(host)


def test_get_host_not_found(client: TestClient[Litestar], host: Host):
    response = client.get(f'{path_prefix}/{host.host_id + 1}')
    assert response.status_code == 404
    assert f'ID {host.host_id + 1} does not exist' in response.json()['detail']


def test_get_host_validation(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/{HOST_ID_MAX * 2}')
    assert response.status_code == 400
    assert f'<= {HOST_ID_MAX}' in response.json()['extra'][0]['message']


def test_query_hosts(client: TestClient[Litestar], hosts: list[Host]):
    items = collect_paginated_data(client, path_prefix, MAX_PAGE_SIZE)
    for h in hosts:
        assert to_host_schema(h).to_dict() in items


def test_query_hosts_pagination(client: TestClient[Litestar], hosts: list[Host]):
    items = collect_paginated_data(client, path_prefix, 1)
    for h in hosts:
        assert to_host_schema(h).to_dict() in items

    params = {'max_page_size': 1, 'page_token': 'last'}
    response = client.get(path_prefix, params=params)
    assert response.status_code == 200
    assert len(response.json()['items']) == params['max_page_size']
    assert response.json().get('prev_page_token') is not None
    assert response.json().get('next_page_token') is None
    assert items[-1] == response.json()['items'][0]


def test_query_hosts_page_size(
    client: TestClient[Litestar], hosts_max_and_one: list[Host]
):
    check_page_size(client, path_prefix)


def test_query_hosts_invalid_page_token(
    client: TestClient[Litestar], hosts: list[Host]
):
    check_invalid_page_token_query(client, path_prefix)


def test_query_hosts_validation(client: TestClient[Litestar]):
    check_query_request_validation(client, path_prefix)


def test_create_host(client: TestClient[Litestar], operator: Operator):
    hostname = 'test_create_host() view test'
    description = 'blah blah blah'
    sana_scid = 123
    word_size = 64
    newline = NewlineEnum.LF.value
    response = client.post(
        path_prefix,
        json={
            'hostname': hostname,
            'host_description': description,
            'operator_id': operator.operator_id,
            'sana_scid': sana_scid,
            'word_size': word_size,
            'newline': newline,
        },
    )
    assert response.status_code == 201
    content = host_decoder.decode(response.content)
    assert response.headers['location'] == f'{API_V1_PATH}/hosts/{content.host_id}'
    assert (
        response.headers['content-location'] == f'{API_V1_PATH}/hosts/{content.host_id}'
    )
    assert content.hostname == hostname
    assert content.host_description == description
    assert content.sana_scid == sana_scid
    assert content.newline == newline
    assert content.operator.operator_id == str(operator.operator_id)
    assert content.operator.operator_name == operator.operator_name


def test_create_host_minimum(client: TestClient[Litestar]):
    hostname = 'test_create_host_minimum()'
    response = client.post(
        path_prefix,
        json={
            'hostname': hostname,
        },
    )
    assert response.status_code == 201
    assert response.status_code == 201
    content = host_decoder.decode(response.content)
    assert response.headers['location'] == f'{API_V1_PATH}/hosts/{content.host_id}'
    assert (
        response.headers['content-location'] == f'{API_V1_PATH}/hosts/{content.host_id}'
    )
    assert content.hostname == hostname
    assert content.host_description is None
    assert content.sana_scid is None
    assert content.newline is None
    assert content.operator is None


def test_create_host_nonexistent_operator(
    client: TestClient[Litestar], operator: Operator
):
    hostname = 'test_create_host_nonexistent_operator()'
    response = client.post(
        path_prefix,
        json={'hostname': hostname, 'operator_id': operator.operator_id + 1},
    )
    assert response.status_code == 404
    assert f'ID {operator.operator_id + 1} does not exist' in response.json()['detail']


def test_create_host_validate_required_reqbody(client: TestClient[Litestar]):
    for response in [
        # Missing request body
        client.post(path_prefix),
        # Empty request body
        client.post(path_prefix, content=b''),
    ]:
        assert response.status_code == 400
        assert 'Expected non-empty request' in response.json()['extra'][0]['message']


def test_create_host_validate_null_reqbody(client: TestClient[Litestar]):
    # `null` is distinct from a missing / empty request body
    response = client.post(path_prefix, content=b'null')
    assert response.status_code == 400
    assert 'Expected `object`, got `null`' in response.json()['extra'][0]['message']


def test_create_host_validate_reqbody_fields(client: TestClient[Litestar]):
    # Missing fields
    response = client.post(path_prefix, json={})
    assert response.status_code == 400
    assert 'missing required field' in response.json()['extra'][0]['message']

    # sana_scid and operator_id out of range
    hostname = 'test_create_host_validate_reqbody_fields()'
    for field, max_val in (
        ('sana_scid', SANA_SCID_MAX),
        ('operator_id', OPERATOR_ID_MAX),
    ):
        for response in (
            client.post(path_prefix, json={'hostname': hostname, field: max_val + 1}),
            client.post(
                path_prefix, json={'hostname': hostname, field: str(max_val + 1)}
            ),
        ):
            assert response.status_code == 400
            assert field == response.json()['extra'][0]['key']
            assert f'<= {max_val}' in response.json()['extra'][0]['message']

    # Invalid word_size
    response = client.post(path_prefix, json={'hostname': hostname, 'word_size': 16})
    assert response.status_code == 400
    assert 'Invalid enum value 16' in response.json()['extra'][0]['message']

    # Invalid newline
    response = client.post(path_prefix, json={'hostname': hostname, 'newline': 'blah'})
    assert response.status_code == 400
    assert "Invalid enum value 'blah'" in response.json()['extra'][0]['message']


def test_update_host(client: TestClient[Litestar], host: Host, operator: Operator):
    hostname = 'test_update_host() view test'
    description = 'abc'
    sana_scid = 123
    word_size = 64
    newline = NewlineEnum.CRLF.value
    response = client.patch(
        f'{path_prefix}/{host.host_id}',
        json={
            'hostname': hostname,
            'host_description': description,
            'operator_id': operator.operator_id,
            'sana_scid': sana_scid,
            'word_size': word_size,
            'newline': newline,
        },
    )
    assert response.status_code == 200
    content = host_decoder.decode(response.content)
    assert content.hostname == hostname
    assert content.host_description == description
    assert content.sana_scid == sana_scid
    assert content.newline == newline
    assert content.operator.operator_id == str(operator.operator_id)
    assert content.operator.operator_name == operator.operator_name


def test_update_host_no_change(client: TestClient[Litestar], host: Host):
    old = to_host_schema(host)

    for response in [
        # Missing request body
        client.patch(f'{path_prefix}/{host.host_id}'),
        # Empty request body
        client.patch(f'{path_prefix}/{host.host_id}', content=b''),
        # Empty object
        client.patch(f'{path_prefix}/{host.host_id}', json={}),
        # Same values
        client.patch(
            f'{path_prefix}/{host.host_id}',
            json={
                'hostname': host.hostname,
                'host_description': host.host_description,
                'operator_id': host.operator_id,
                'sana_scid': host.sana_scid,
                'word_size': host.word_size,
                'newline': host.newline,
            },
        ),
    ]:
        assert response.status_code == 200
        assert old == host_decoder.decode(response.content)


def test_update_host_not_found(
    client: TestClient[Litestar], host: Host, operator: Operator
):
    response = client.patch(f'{path_prefix}/{host.host_id + 1}')
    assert response.status_code == 404
    assert f'ID {host.host_id + 1} does not exist' in response.json()['detail']

    response = client.patch(
        f'{path_prefix}/{host.host_id}', json={'operator_id': operator.operator_id + 1}
    )
    assert response.status_code == 404
    assert f'ID {operator.operator_id + 1} does not exist' in response.json()['detail']


def test_update_host_with_nodes_to_new_operator(
    client: TestClient[Litestar],
    operator: Operator,
    nodes_under_same_host_and_operator_under_same_allocator: tuple[
        Node, Node, Node, Node, Operator
    ],
):
    nodes = nodes_under_same_host_and_operator_under_same_allocator[:-1]
    h = nodes[0].host
    operator_same_allocator = nodes_under_same_host_and_operator_under_same_allocator[
        -1
    ]

    # Update to operator with different allocator
    response = client.patch(
        f'{path_prefix}/{h.host_id}', json={'operator_id': operator.operator_id}
    )
    assert response.status_code == 400
    assert (
        f'node IDs: [{", ".join([str(n.node_id) for n in nodes if n.operator])}]'
    ) in response.json()['detail']

    # Update to operator with same allocator
    response = client.patch(
        f'{path_prefix}/{h.host_id}',
        json={'operator_id': operator_same_allocator.operator_id},
    )
    assert response.status_code == 400
    assert (
        f'Node IDs: [{", ".join([str(n.node_id) for n in nodes if n.operator])}]'
    ) in response.json()['detail']
    assert (
        f'node numbers: [{", ".join([str(n.node_number) for n in nodes if n.operator])}]'
    ) in response.json()['detail']


def test_update_host_validation(client: TestClient[Litestar]):
    # host_id out of range
    response = client.patch(f'{path_prefix}/{HOST_ID_MAX * 2}')
    assert response.status_code == 400
    assert f'<= {HOST_ID_MAX}' in response.json()['extra'][0]['message']

    # sana_scid and operator_id out of range
    for field, max_val in (
        ('sana_scid', SANA_SCID_MAX),
        ('operator_id', OPERATOR_ID_MAX),
    ):
        url = f'{path_prefix}/0'
        for response in (
            client.patch(url, json={field: max_val + 1}),
            client.patch(url, json={field: str(max_val + 1)}),
        ):
            assert response.status_code == 400
            assert field == response.json()['extra'][0]['key']
            assert f'<= {max_val}' in response.json()['extra'][0]['message']

    # Invalid word_size
    response = client.patch(f'{path_prefix}/0', json={'word_size': 16})
    assert response.status_code == 400
    assert 'Invalid enum value 16' in response.json()['extra'][0]['message']

    # Invalid newline
    response = client.patch(f'{path_prefix}/0', json={'newline': 'blah'})
    assert response.status_code == 400
    assert "Invalid enum value 'blah'" in response.json()['extra'][0]['message']


def test_copy_host(
    client: TestClient[Litestar],
    host_with_full_nodes: Host,
    operator: Operator,
    session: Session,
):
    host = host_with_full_nodes
    in_nodes = [
        NodeCopyForHostSchema(
            node_id=n.node_id,
            allocator_id=operator.allocator_id + 34,  # ignored
            node_number=operator.allocated_node_numbers[0].lower + i,
            operator_id=operator.operator_id,
        )
        for n, i in zip(host.nodes, range(len(host.nodes)))
    ]
    response = client.post(
        f'{path_prefix}/{host.host_id}/copies',
        json={
            'operator_id': operator.operator_id,
            'nodes': [n.to_dict() for n in in_nodes],
        },
    )
    assert response.status_code == 201
    content = host_decoder.decode(response.content)
    assert response.headers['location'] == f'{API_V1_PATH}/hosts/{content.host_id}'
    assert (
        response.headers['content-location'] == f'{API_V1_PATH}/hosts/{content.host_id}'
    )
    check_copied_host_equality(session, host.host_id, int(content.host_id), in_nodes)


def test_copy_host_multiple_copies_same_node(
    client: TestClient[Litestar],
    host_with_full_nodes: Host,
    allocator: Allocator,
    session: Session,
):
    host = host_with_full_nodes
    in_nodes = [
        NodeCopyForHostSchema(
            node_id=host.nodes[0].node_id,
            allocator_id=allocator.allocator_id,
            node_number=i,
        )
        for i in range(3)
    ]
    response = client.post(
        f'{path_prefix}/{host.host_id}/copies',
        json={'operator_id': None, 'nodes': [n.to_dict() for n in in_nodes]},
    )
    assert response.status_code == 201
    content = host_decoder.decode(response.content)
    assert response.headers['location'] == f'{API_V1_PATH}/hosts/{content.host_id}'
    assert (
        response.headers['content-location'] == f'{API_V1_PATH}/hosts/{content.host_id}'
    )
    check_copied_host_equality(session, host.host_id, int(content.host_id), in_nodes)
    assert len(host_get(session, int(content.host_id)).nodes) == len(in_nodes)


def test_copy_host_defaults(
    client: TestClient[Litestar], host_with_full_nodes: Host, session: Session
):
    host = host_with_full_nodes
    url = f'{path_prefix}/{host.host_id}/copies'
    for response in [
        # Missing request body
        client.post(url),
        # Empty request body
        client.post(url, content=b''),
        # Empty object
        client.post(url, json={}),
        # Explicit default values
        client.post(url, json={'operator_id': None, 'nodes': []}),
    ]:
        assert response.status_code == 201
        content = host_decoder.decode(response.content)
        assert response.headers['location'] == f'{API_V1_PATH}/hosts/{content.host_id}'
        assert (
            response.headers['content-location']
            == f'{API_V1_PATH}/hosts/{content.host_id}'
        )
        check_copied_host_equality(session, host.host_id, int(content.host_id), [])
        assert not host_get(session, int(content.host_id)).nodes


def test_copy_host_nonexistent_host(client: TestClient[Litestar]):
    response = client.post(f'{path_prefix}/0/copies')
    assert response.status_code == 404
    assert 'Host ID 0 does not exist' in response.json()['detail']


def test_copy_host_nonexistent_operator(client: TestClient[Litestar], host: Host):
    response = client.post(
        f'{path_prefix}/{host.host_id}/copies', json={'operator_id': 0}
    )
    assert response.status_code == 404
    assert 'Operator ID 0 does not exist' in response.json()['detail']


def test_copy_host_break_copy_nodes_rules(
    client: TestClient[Litestar],
    host_with_full_nodes: Host,
    node: Node,
    allocator: Allocator,
):
    host = host_with_full_nodes
    response = client.post(
        f'{path_prefix}/{host.host_id}/copies',
        json={
            'operator_id': host.operator_id,
            'nodes': [
                {'node_id': 0, 'node_number': 0},
                {
                    'node_id': host.nodes[0].node_id,
                    'operator_id': host.operator_id,
                    'node_number': host.operator.allocated_node_numbers[0].upper,
                },
                {
                    'node_id': host.nodes[0].node_id,
                    'node_number': 0,
                    'allocator_id': allocator.allocator_id + 99,
                },
                {
                    'node_id': host.nodes[0].node_id,
                    'node_number': node.node_number,
                    'allocator_id': node.allocator_id,
                },
                {
                    'node_id': host.nodes[0].node_id,
                    'node_number': 34,
                    'allocator_id': allocator.allocator_id,
                },
                {
                    'node_id': host.nodes[0].node_id,
                    'node_number': 34,
                    'allocator_id': allocator.allocator_id,
                },
            ],
        },
    )
    assert response.status_code == 400
    assert 'violate the rules for copying nodes' in response.json()['detail']
    assert (
        f'Node ID 0 does not belong to host ID {host.host_id}'
        == response.json()['extra'][0]['message']
    )
    assert 'nodes[0].node_id' == response.json()['extra'][0]['key']
    assert 'body' == response.json()['extra'][0]['source']
    assert (
        f'Node number {host.operator.allocated_node_numbers[0].upper} is not'
        f' allocated to operator ID {host.operator_id}'
    ) in response.json()['extra'][1]['message']
    assert 'nodes[1].node_number' == response.json()['extra'][1]['key']
    assert 'body' == response.json()['extra'][1]['source']
    assert (
        f'Allocator ID {allocator.allocator_id + 99} does not exist'
        == response.json()['extra'][2]['message']
    )
    assert 'nodes[2].allocator_id' == response.json()['extra'][2]['key']
    assert 'body' == response.json()['extra'][2]['source']
    assert (
        f'FQNN ({node.allocator_id}, {node.node_number}) already exists'
        == response.json()['extra'][3]['message']
    )
    assert 'nodes[3].node_number' == response.json()['extra'][3]['key']
    assert 'body' == response.json()['extra'][3]['source']
    assert (
        f'FQNN ({allocator.allocator_id}, 34) is already specified to be used'
        ' by nodes[4]'
    ) == response.json()['extra'][4]['message']
    assert 'nodes[5].node_number' == response.json()['extra'][4]['key']
    assert 'body' == response.json()['extra'][4]['source']


def test_copy_host_mismatch_operator(
    client: TestClient[Litestar], host_with_full_nodes: Host
):
    host = host_with_full_nodes
    response = client.post(
        f'{path_prefix}/{host.host_id}/copies',
        json={
            'operator_id': host.operator_id,
            'nodes': [
                {
                    'node_id': host.nodes[0].node_id,
                    'operator_id': 0,
                    'node_number': 0,
                },
            ],
        },
    )
    assert response.status_code == 400
    assert (
        f'Operator ID 0 does not match with operator ID {host.operator_id}'
        ' specified for the new host'
    ) in response.json()['extra'][0]['message']
    assert 'nodes[0].operator_id' == response.json()['extra'][0]['key']
    assert 'body' == response.json()['extra'][0]['source']


def test_copy_host_required_node_id_node_number(client: TestClient[Litestar]):
    response = client.post(f'{path_prefix}/0/copies', json={'nodes': [{}]})
    assert response.status_code == 400
    assert (
        'Object missing required field `node_id`'
        == response.json()['extra'][0]['message']
    )
    assert 'nodes[0]' == response.json()['extra'][0]['key']
    assert 'body' == response.json()['extra'][0]['source']

    response = client.post(f'{path_prefix}/0/copies', json={'nodes': [{'node_id': 0}]})
    assert response.status_code == 400
    assert (
        'Object missing required field `node_number`'
        == response.json()['extra'][0]['message']
    )
    assert 'nodes[0]' == response.json()['extra'][0]['key']
    assert 'body' == response.json()['extra'][0]['source']

    response = client.post(
        f'{path_prefix}/0/copies',
        json={'nodes': [{'node_id': None, 'node_number': 0}]},
    )
    assert response.status_code == 400
    assert 'Expected `int`, got `null`' == response.json()['extra'][0]['message']
    assert 'nodes[0].node_id' == response.json()['extra'][0]['key']
    assert 'body' == response.json()['extra'][0]['source']

    response = client.post(
        f'{path_prefix}/0/copies',
        json={'nodes': [{'node_id': 0, 'node_number': None}]},
    )
    assert response.status_code == 400
    assert 'Expected `int`, got `null`' == response.json()['extra'][0]['message']
    assert 'nodes[0].node_number' == response.json()['extra'][0]['key']
    assert 'body' == response.json()['extra'][0]['source']


def test_copy_host_non_null_allocator_id(client: TestClient[Litestar]):
    response = client.post(
        f'{path_prefix}/0/copies',
        json={'nodes': [{'node_id': 0, 'node_number': 0, 'allocator_id': None}]},
    )
    assert response.status_code == 400
    assert 'Expected `int`, got `null`' == response.json()['extra'][0]['message']
    assert 'nodes[0].allocator_id' == response.json()['extra'][0]['key']
    assert 'body' == response.json()['extra'][0]['source']


def test_copy_host_validation(client: TestClient[Litestar]):
    response = client.post(
        f'{path_prefix}/{HOST_ID_MAX + 1}/copies',
        json={'operator_id': OPERATOR_ID_MAX + 1},
    )
    assert response.status_code == 400
    assert f'Expected `int` <= {HOST_ID_MAX}' == response.json()['extra'][0]['message']
    assert 'host_id' == response.json()['extra'][0]['key']
    assert 'path' == response.json()['extra'][0]['source']
    assert (
        f'Expected `int` <= {OPERATOR_ID_MAX}' == response.json()['extra'][1]['message']
    )
    assert 'operator_id' == response.json()['extra'][1]['key']
    assert 'body' == response.json()['extra'][1]['source']

    for field, field_max in (
        ('node_id', NODE_ID_MAX),
        ('node_number', NODE_NUMBER_MAX),
        ('allocator_id', ALLOCATOR_ID_MAX),
        ('operator_id', OPERATOR_ID_MAX),
    ):
        response = client.post(
            f'{path_prefix}/0/copies', json={'nodes': [{field: field_max + 1}]}
        )
        assert response.status_code == 400
        assert (
            f'Expected `int` <= {field_max}' == response.json()['extra'][0]['message']
        )
        assert f'nodes[0].{field}' == response.json()['extra'][0]['key']
        assert 'body' == response.json()['extra'][0]['source']


def test_delete_host(client: TestClient[Litestar], host: Host):
    response = client.delete(f'{path_prefix}/{host.host_id}')
    assert response.status_code == 204
    # The record was deleted, so deleting again should error
    response = client.delete(f'{path_prefix}/{host.host_id}')
    assert response.status_code == 404
    assert f'ID {host.host_id} does not exist' in response.json()['detail']


def test_delete_host_validation(client: TestClient[Litestar]):
    response = client.delete(f'{path_prefix}/{HOST_ID_MAX * 2}')
    assert response.status_code == 400
    assert f'<= {HOST_ID_MAX}' in response.json()['extra'][0]['message']


def test_list_host_links(client: TestClient[Litestar], host_with_links: Host):
    host = host_with_links
    items = collect_paginated_data(
        client, f'{path_prefix}/{host.host_id}/links', MAX_PAGE_SIZE
    )
    for l in host.links:
        assert to_link_schema(l, with_host=False).to_dict() in items


def test_list_host_links_pagination(
    client: TestClient[Litestar], host_max_and_one_links: Host
):
    host = host_max_and_one_links
    items = collect_paginated_data(client, f'{path_prefix}/{host.host_id}/links', 1)
    for l in host.links:
        assert to_link_schema(l, with_host=False).to_dict() in items

    params = {'max_page_size': 1, 'page_token': 'last'}
    response = client.get(f'{path_prefix}/{host.host_id}/links', params=params)
    assert response.status_code == 200
    assert len(response.json()['items']) == params['max_page_size']
    assert response.json().get('prev_page_token') is not None
    assert response.json().get('next_page_token') is None
    assert items[-1] == response.json()['items'][0]


def test_list_host_links_page_size(
    client: TestClient[Litestar], host_max_and_one_links: Host
):
    host = host_max_and_one_links
    check_page_size(client, f'{path_prefix}/{host.host_id}/links')


def test_list_host_links_invalid_page_token(
    client: TestClient[Litestar], host_max_and_one_links: Host, host: Host
):
    other_host_id = host.host_id
    host = host_max_and_one_links
    check_invalid_page_token_different_url(
        client,
        f'{path_prefix}/{host.host_id}/links',
        f'{path_prefix}/{other_host_id}/links',
    )


def test_list_host_links_not_found(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/0/links')
    assert response.status_code == 404
    assert 'ID 0 does not exist' in response.json()['detail']


def test_list_host_links_validation(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/{HOST_ID_MAX * 2}/links')
    assert response.status_code == 400
    assert f'<= {HOST_ID_MAX}' in response.json()['extra'][0]['message']

    check_paginated_request_validation(client, f'{path_prefix}/0/links')


def test_create_link(
    client: TestClient[Litestar],
    host: Host,
    underlying_communication_services: list[UnderlyingCommunicationService],
    band: Band,
):
    response = client.post(
        f'{path_prefix}/{host.host_id}/links',
        json={
            'direction': 'Full-duplex',
            'underlying_communication_service_ids': [
                s.underlying_communication_service_id
                for s in underlying_communication_services
            ],
            'link_rf': {'band_id': band.band_id},
        },
    )
    assert response.status_code == 201
    assert str(host.host_id) == response.json()['host_id']
    assert 'Full-duplex' == response.json()['direction']
    for s in underlying_communication_services:
        assert (
            to_ucs_schema(s).to_dict()
            in response.json()['underlying_communication_services']
        )
    assert to_band_schema(band).to_dict() == response.json()['link_rf']['band']
    assert (
        response.headers['location']
        == f'{API_V1_PATH}/links/{response.json()["link_id"]}'
    )
    assert (
        response.headers['content-location']
        == f'{API_V1_PATH}/links/{response.json()["link_id"]}'
    )

    response = client.post(
        f'{path_prefix}/{host.host_id}/links',
        json={
            'direction': 'Simplex (incoming)',
            'underlying_communication_service_ids': [
                s.underlying_communication_service_id
                for s in underlying_communication_services
            ],
            'link_rf': None,
        },
    )
    assert response.status_code == 201
    assert str(host.host_id) == response.json()['host_id']
    assert 'Simplex (incoming)' == response.json()['direction']
    for s in underlying_communication_services:
        assert (
            to_ucs_schema(s).to_dict()
            in response.json()['underlying_communication_services']
        )
    assert response.json()['link_rf'] is None


def test_create_link_null_band(client: TestClient[Litestar], host: Host):
    response = client.post(
        f'{path_prefix}/{host.host_id}/links',
        json={'link_rf': {'band_id': None}},
    )
    assert response.status_code == 201
    assert str(host.host_id) == response.json()['host_id']
    assert response.json()['link_rf']['band'] is None


def test_create_link_null_direction(client: TestClient[Litestar], host: Host):
    response = client.post(
        f'{path_prefix}/{host.host_id}/links',
        json={'direction': None},
    )
    assert response.status_code == 201
    assert response.json()['direction'] is None


def test_create_link_not_found(
    client: TestClient[Litestar],
    host: Host,
    underlying_communication_services: list[UnderlyingCommunicationService],
    band: Band,
):
    response = client.post(f'{path_prefix}/{host.host_id + 1}/links')
    assert response.status_code == 404
    assert f'Host ID {host.host_id + 1} does not exist' in response.json()['detail']

    nums = [
        underlying_communication_services[-1].underlying_communication_service_id + 1
    ]
    nums.append(nums[-1] + 1)
    nums.append(nums[-1] + 2)
    response = client.post(
        f'{path_prefix}/{host.host_id}/links',
        json={'underlying_communication_service_ids': nums},
    )
    assert response.status_code == 404
    for i in nums:
        assert str(i) in response.json()['extra']

    response = client.post(
        f'{path_prefix}/{host.host_id}/links',
        json={'link_rf': {'band_id': band.band_id + 1}},
    )
    assert response.status_code == 404
    assert f'Band ID {band.band_id + 1} does not exist' in response.json()['detail']


def test_create_link_defaults(client: TestClient[Litestar], host: Host):
    for response in [
        client.post(f'{path_prefix}/{host.host_id}/links'),
        client.post(f'{path_prefix}/{host.host_id}/links', content=b''),
        client.post(f'{path_prefix}/{host.host_id}/links', json={}),
    ]:
        assert response.status_code == 201
        assert response.json()['link_id'] is not None
        assert str(host.host_id) == response.json()['host_id']
        assert response.json()['direction'] is None
        assert response.json()['underlying_communication_services'] == []
        assert response.json()['link_rf'] is None

    response = client.post(f'{path_prefix}/{host.host_id}/links', json={'link_rf': {}})
    assert response.status_code == 201
    assert response.json()['link_id'] is not None
    assert str(host.host_id) == response.json()['host_id']
    assert response.json()['direction'] is None
    assert response.json()['underlying_communication_services'] == []
    assert response.json()['link_rf'] is not None
    assert response.json()['link_rf']['band'] is None


def test_create_link_unique_service_ids(
    client: TestClient[Litestar],
    host: Host,
    underlying_communication_services: list[UnderlyingCommunicationService],
):
    ids = [
        s.underlying_communication_service_id for s in underlying_communication_services
    ]
    ids_original_len = len(ids)
    ids.extend(ids[::-1])
    assert len(ids) != ids_original_len
    response = client.post(
        f'{path_prefix}/{host.host_id}/links',
        json={'underlying_communication_service_ids': ids},
    )
    assert response.status_code == 201
    assert str(host.host_id) == response.json()['host_id']
    assert ids_original_len == len(response.json()['underlying_communication_services'])


def test_create_link_validation(client: TestClient[Litestar]):
    # host_id out of range
    response = client.post(f'{path_prefix}/{HOST_ID_MAX * 2}/links')
    assert response.status_code == 400
    assert f'<= {HOST_ID_MAX}' in response.json()['extra'][0]['message']

    # Invalid direction
    response = client.post(f'{path_prefix}/0/links', json={'direction': 'semiduplex'})
    assert response.status_code == 400
    assert 'Invalid enum value' in response.json()['extra'][0]['message']

    # Underlying comm service ID out of range
    response = client.post(
        f'{path_prefix}/0/links',
        json={'underlying_communication_service_ids': [3, 2, -1, 0]},
    )
    assert response.status_code == 400
    assert '>= 0' in response.json()['extra'][0]['message']
    response = client.post(
        f'{path_prefix}/0/links',
        json={
            'underlying_communication_service_ids': [
                0,
                UNDERLYING_COMMUNICATION_SERVICE_ID_MAX + 1,
                2,
            ]
        },
    )
    assert response.status_code == 400
    assert (
        f'<= {UNDERLYING_COMMUNICATION_SERVICE_ID_MAX}'
        in response.json()['extra'][0]['message']
    )

    # band_id out of range
    response = client.post(
        f'{path_prefix}/0/links', json={'link_rf': {'band_id': BAND_ID_MAX * 2}}
    )
    assert response.status_code == 400
    assert f'<= {BAND_ID_MAX}' in response.json()['extra'][0]['message']


def test_list_host_destinations(
    client: TestClient[Litestar], host_with_destinations: Host
):
    host = host_with_destinations
    items = collect_paginated_data(
        client, f'{path_prefix}/{host.host_id}/destinations', MAX_PAGE_SIZE
    )
    for d in host.destinations:
        assert to_destination_without_host_id_schema(d).to_dict() in items


def test_list_host_destinations_pagination(
    client: TestClient[Litestar], host_max_and_one_destinations: Host
):
    host = host_max_and_one_destinations
    items = collect_paginated_data(
        client, f'{path_prefix}/{host.host_id}/destinations', 1
    )
    for d in host.destinations:
        assert to_destination_without_host_id_schema(d).to_dict() in items

    params = {'max_page_size': 1, 'page_token': 'last'}
    response = client.get(f'{path_prefix}/{host.host_id}/destinations', params=params)
    assert response.status_code == 200
    assert len(response.json()['items']) == params['max_page_size']
    assert response.json().get('prev_page_token') is not None
    assert response.json().get('next_page_token') is None
    assert items[-1] == response.json()['items'][0]


def test_list_host_destinations_page_size(
    client: TestClient[Litestar], host_max_and_one_destinations: Host
):
    host = host_max_and_one_destinations
    check_page_size(client, f'{path_prefix}/{host.host_id}/destinations')


def test_list_host_destinations_invalid_page_token(
    client: TestClient[Litestar], host_max_and_one_destinations: Host, host: Host
):
    other_host_id = host.host_id
    host = host_max_and_one_destinations
    check_invalid_page_token_different_url(
        client,
        f'{path_prefix}/{host.host_id}/destinations',
        f'{path_prefix}/{other_host_id}/destinations',
    )


def test_list_host_destinations_not_found(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/0/destinations')
    assert response.status_code == 404
    assert 'ID 0 does not exist' in response.json()['detail']


def test_list_host_destinations_validation(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/{HOST_ID_MAX * 2}/destinations')
    assert response.status_code == 400
    assert f'<= {HOST_ID_MAX}' in response.json()['extra'][0]['message']

    check_paginated_request_validation(client, f'{path_prefix}/0/destinations')


def test_create_destination(client: TestClient[Litestar], host: Host):
    # DestinationFactory generates public addresses, so use a private one to
    # avoid potential conflicts.
    ip = '192.168.1.1'
    response = client.post(
        f'{path_prefix}/{host.host_id}/destinations?ip=true',
        json={'destination_value': ip},
    )
    assert response.status_code == 201
    assert str(host.host_id) == response.json()['host_id']
    assert ip == response.json()['destination_value']

    # DestinationFactory generates domain names at one subdomain level, use
    # more levels to avoid potential conflicts.
    name = 'sub.example.test'
    response = client.post(
        f'{path_prefix}/{host.host_id}/destinations', json={'destination_value': name}
    )
    assert response.status_code == 201
    assert str(host.host_id) == response.json()['host_id']
    assert name == response.json()['destination_value']


def test_create_destination_existing(
    client: TestClient[Litestar],
    destination_ip: Destination,
    destination_name: Destination,
):
    response = client.post(
        f'{path_prefix}/{destination_ip.host_id}/destinations?ip=true',
        json={'destination_value': str(destination_ip.ip_address)},
    )
    assert response.status_code == 400
    assert (
        f"value '{str(destination_ip.ip_address)}' is already associated with"
        f' host ID {destination_ip.host_id}'
    ) in response.json()['detail']

    response = client.post(
        f'{path_prefix}/{destination_name.host_id}/destinations',
        json={'destination_value': destination_name.registered_name},
    )
    assert response.status_code == 400
    assert (
        f"value '{destination_name.registered_name}' is already associated with"
        f' host ID {destination_name.host_id}'
    ) in response.json()['detail']


def test_create_destination_not_found(client: TestClient[Litestar], host: Host):
    response = client.post(
        f'{path_prefix}/{host.host_id + 1}/destinations',
        json={'destination_value': '192.168.1.2'},
    )
    assert response.status_code == 404
    assert f'Host ID {host.host_id + 1} does not exist' in response.json()['detail']


def test_create_destination_validate_required_reqbody(client: TestClient[Litestar]):
    for response in [
        # Missing request body
        client.post(f'{path_prefix}/0/destinations'),
        # Empty request body
        client.post(f'{path_prefix}/0/destinations', content=b''),
    ]:
        assert response.status_code == 400
        assert 'Expected non-empty request' in response.json()['extra'][0]['message']


def test_create_destination_validate_null_reqbody(client: TestClient[Litestar]):
    # `null` is distinct from a missing / empty request body
    response = client.post(f'{path_prefix}/0/destinations', content=b'null')
    assert response.status_code == 400
    assert 'Expected `object`, got `null`' in response.json()['extra'][0]['message']


def test_create_destination_validation(client: TestClient[Litestar]):
    # host_id out of range
    response = client.post(
        f'{path_prefix}/{HOST_ID_MAX * 2}/destinations',
        json={'destination_value': '192.168.1.3'},
    )
    assert response.status_code == 400
    assert f'<= {HOST_ID_MAX}' in response.json()['extra'][0]['message']

    # Invalid IP address
    response = client.post(
        f'{path_prefix}/0/destinations?ip=true', json={'destination_value': 'abc'}
    )
    assert response.status_code == 400
    assert (
        "'abc' does not appear to be an IPv4 or IPv6 address"
        in response.json()['extra'][0]['message']
    )

    # destination_value required
    response = client.post(f'{path_prefix}/0/destinations', json={})
    assert response.status_code == 400
    assert (
        'Object missing required field `destination_value`'
        in response.json()['extra'][0]['message']
    )

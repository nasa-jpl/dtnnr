from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

from app.api.v1.allocator.schemas import AllocatorSchema, to_schema
from app.config import API_V1_PATH, MAX_PAGE_SIZE
from app.fields import ALLOCATOR_ID_MAX
from tests.util import (
    check_invalid_page_token_query,
    check_page_size,
    check_query_request_validation,
    collect_paginated_data,
)

if TYPE_CHECKING:
    from litestar import Litestar
    from litestar.testing import TestClient
    from sqlalchemy.orm import Session

    from app.models import Allocator, Node

decoder = msgspec.json.Decoder(type=AllocatorSchema, strict=False)


def test_get_allocator(client: TestClient[Litestar], allocator_with_details: Allocator):
    allocator = allocator_with_details
    response = client.get(f'{API_V1_PATH}/allocators/{allocator.allocator_id}')
    assert response.status_code == 200
    assert decoder.decode(response.content) == to_schema(allocator)
    # TODO: adapt these remaining checks
    # # Check if contacts are present
    # assert allocator.contacts == load_data.contacts
    # for c in allocator.contacts:
    #     assert f'"contact_id":{c.contact_id}'.encode() in response.data
    #     assert c.contact_name.encode() in response.data
    # # Check if operators are present
    # assert allocator.operators == load_data.operators
    # for o in allocator.operators:
    #     assert f'"operator_id":{o.operator_id}'.encode() in response.data
    # # Check if nodes are present
    # assert allocator.nodes == load_data.nodes
    # for n in allocator.nodes:
    #     assert f'"node_id":{n.node_id}'.encode() in response.data


def test_get_allocator_not_found(client: TestClient[Litestar], allocator: Allocator):
    # Invalid allocator_id
    response = client.get(f'{API_V1_PATH}/allocators/{allocator.allocator_id + 1}')
    assert response.status_code == 404
    assert (
        f'ID {allocator.allocator_id + 1} does not exist' in response.json()['detail']
    )


def test_get_allocator_validation(client: TestClient[Litestar]):
    # allocator_id too large
    response = client.get(f'{API_V1_PATH}/allocators/{ALLOCATOR_ID_MAX * 2}')
    assert response.status_code == 400
    assert f'<= {ALLOCATOR_ID_MAX}' in response.json()['extra'][0]['message']


def test_query_allocators(client: TestClient[Litestar], allocators: list[Allocator]):
    items = collect_paginated_data(client, f'{API_V1_PATH}/allocators', MAX_PAGE_SIZE)
    for a in allocators:
        assert to_schema(a).to_dict() in items


def test_query_allocators_pagination(
    client: TestClient[Litestar], allocators: list[Allocator]
):
    items = collect_paginated_data(client, f'{API_V1_PATH}/allocators', 1)
    for a in allocators:
        assert to_schema(a).to_dict() in items

    params = {'max_page_size': 1, 'page_token': 'last'}
    response = client.get(f'{API_V1_PATH}/allocators', params=params)
    assert response.status_code == 200
    assert len(response.json()['items']) == params['max_page_size']
    assert response.json().get('prev_page_token') is not None
    assert response.json().get('next_page_token') is None
    assert items[-1] == response.json()['items'][0]


def test_query_allocators_page_size(
    client: TestClient[Litestar], allocators_max_and_one: list[Allocator]
):
    check_page_size(client, f'{API_V1_PATH}/allocators')


def test_query_allocators_invalid_page_token(
    client: TestClient[Litestar], allocators: list[Allocator]
):
    check_invalid_page_token_query(client, f'{API_V1_PATH}/allocators')


# TODO: disable sorting parameters until I can think of an actual use case
# def test_query_allocators_sort(
#     client: TestClient[Litestar], allocators: list[Allocator]
# ):
#     params = [
#         {'max_page_size': MAX_PAGE_SIZE, 'sort': 'allocator_id', 'direction': 'asc'},
#         # test defaults
#         {'max_page_size': MAX_PAGE_SIZE},
#     ]
#     for p in params:
#         response = client.get(f'{API_V1_PATH}/allocators', params=p)
#         assert response.status_code == 200
#         for i in range(1, len(response.json()['items'])):
#             assert (
#                 response.json()['items'][i]['allocator_id']
#                 > response.json()['items'][i - 1]['allocator_id']
#             )

#     params = [
#         {'max_page_size': MAX_PAGE_SIZE, 'sort': 'allocator_id', 'direction': 'desc'},
#         # test defaults
#         {'max_page_size': MAX_PAGE_SIZE, 'direction': 'desc'},
#     ]
#     for p in params:
#         response = client.get(f'{API_V1_PATH}/allocators', params=p)
#         assert response.status_code == 200
#         for i in range(1, len(response.json()['items'])):
#             assert (
#                 response.json()['items'][i]['allocator_id']
#                 < response.json()['items'][i - 1]['allocator_id']
#             )


def test_query_allocators_validation(client: TestClient[Litestar]):
    check_query_request_validation(client, f'{API_V1_PATH}/allocators')


def test_create_allocator(client: TestClient[Litestar]):
    allocator_id = 98765
    allocator_name = 'Test View Create Allocator'
    response = client.post(
        f'{API_V1_PATH}/allocators',
        json={
            'allocator_id': allocator_id,
            'allocator_name': allocator_name,
        },
    )
    assert response.status_code == 201
    content = decoder.decode(response.content)
    response.headers['location'] == f'{API_V1_PATH}/allocators/{allocator_id}'
    response.headers['content-location'] == f'{API_V1_PATH}/allocators/{allocator_id}'
    assert content.allocator_id == str(allocator_id)
    assert content.allocator_name == allocator_name


def test_create_allocator_existing(client: TestClient[Litestar], allocator: Allocator):
    # Already existent allocator
    response = client.post(
        f'{API_V1_PATH}/allocators',
        json={
            'allocator_id': allocator.allocator_id,
            'allocator_name': 'blah',
        },
    )
    assert response.status_code == 400
    assert f'ID {allocator.allocator_id} already exists' in response.json()['detail']


def test_create_allocator_validate_required_reqbody(client: TestClient[Litestar]):
    for response in [
        # Missing request body
        client.post(f'{API_V1_PATH}/allocators'),
        # Empty request body
        client.post(f'{API_V1_PATH}/allocators', content=b''),
    ]:
        assert response.status_code == 400
        assert 'Expected non-empty request' in response.json()['extra'][0]['message']


def test_create_allocator_validate_null_reqbody(client: TestClient[Litestar]):
    # `null` is distinct from a missing / empty request body
    response = client.post(f'{API_V1_PATH}/allocators', content=b'null')
    assert response.status_code == 400
    assert 'Expected `object`, got `null`' in response.json()['extra'][0]['message']


def test_create_allocator_validate_reqbody_fields(client: TestClient[Litestar]):
    # Missing fields
    response = client.post(f'{API_V1_PATH}/allocators', json={})
    assert response.status_code == 400
    assert 'missing required field' in response.json()['extra'][0]['message']

    # Negative allocator_id
    response = client.post(
        f'{API_V1_PATH}/allocators',
        json={
            'allocator_id': -1,
            'allocator_name': 'blah',
        },
    )
    assert response.status_code == 400
    assert '>= 0' in response.json()['extra'][0]['message']

    # Allocator_id > 2^63-1
    response = client.post(
        f'{API_V1_PATH}/allocators',
        json={
            'allocator_id': ALLOCATOR_ID_MAX * 2,
            'allocator_name': 'blah',
        },
    )
    assert response.status_code == 400
    assert f'<= {ALLOCATOR_ID_MAX}' in response.json()['extra'][0]['message']


def test_update_allocator(client: TestClient[Litestar], allocator: Allocator):
    # Only change the name
    old_allocator_id = allocator.allocator_id
    allocator_name = 'Test View Update Allocator'
    assert allocator.allocator_name != allocator_name
    response = client.patch(
        f'{API_V1_PATH}/allocators/{allocator.allocator_id}',
        json={
            'allocator_name': allocator_name,
        },
    )
    assert response.status_code == 200
    content = decoder.decode(response.content)
    response.headers[
        'content-location'
    ] == f'{API_V1_PATH}/allocators/{allocator.allocator_id}'
    assert content.allocator_id == str(old_allocator_id)
    assert content.allocator_name == allocator_name

    # Only change allocator id
    new_allocator_id = old_allocator_id + 99999  # Assuming this id isn't used
    response = client.patch(
        f'{API_V1_PATH}/allocators/{allocator.allocator_id}',
        json={
            'allocator_id': new_allocator_id,
        },
    )
    assert response.status_code == 200
    content = decoder.decode(response.content)
    response.headers[
        'content-location'
    ] == f'{API_V1_PATH}/allocators/{new_allocator_id}'
    # We changed the primary key of the record, so you can't use `allocator` anymore.
    assert content.allocator_id == str(new_allocator_id)
    assert content.allocator_name == allocator_name  # this variable is still unchanged

    # Change both name and allocator id
    new_allocator_id += 1
    allocator_name = 'Test View Update Allocator 2'
    assert content.allocator_name != allocator_name
    response = client.patch(
        f'{API_V1_PATH}/allocators/{content.allocator_id}',
        json={
            'allocator_name': allocator_name,
            'allocator_id': new_allocator_id,
        },
    )
    assert response.status_code == 200
    content = decoder.decode(response.content)
    response.headers[
        'content-location'
    ] == f'{API_V1_PATH}/allocators/{new_allocator_id}'
    assert content.allocator_id == str(new_allocator_id)
    assert content.allocator_name == allocator_name


def test_update_allocator_no_change(client: TestClient[Litestar], allocator: Allocator):
    old_allocator_id = allocator.allocator_id
    old_allocator_name = allocator.allocator_name

    for response in [
        # Missing request body
        client.patch(f'{API_V1_PATH}/allocators/{allocator.allocator_id}'),
        # Empty request body
        client.patch(f'{API_V1_PATH}/allocators/{allocator.allocator_id}', content=b''),
        # Empty object
        client.patch(f'{API_V1_PATH}/allocators/{allocator.allocator_id}', json={}),
        # Same allocator_id and allocator_name
        client.patch(
            f'{API_V1_PATH}/allocators/{allocator.allocator_id}',
            json={
                'allocator_name': old_allocator_name,
                'new_allocator_id': old_allocator_id,
            },
        ),
    ]:
        assert response.status_code == 200
        content = decoder.decode(response.content)
        response.headers[
            'content-location'
        ] == f'{API_V1_PATH}/allocators/{old_allocator_id}'
        assert content.allocator_id == str(old_allocator_id)
        assert content.allocator_name == old_allocator_name


def test_update_allocator_not_found(client: TestClient[Litestar], allocator: Allocator):
    # Updating a non-existent allocator
    response = client.patch(
        f'{API_V1_PATH}/allocators/{allocator.allocator_id + 1}',
        json={
            'allocator_name': 'blah',
            'allocator_id': 123,
        },
    )
    assert response.status_code == 404
    assert (
        f'ID {allocator.allocator_id + 1} does not exist' in response.json()['detail']
    )


def test_update_allocator_existing(
    client: TestClient[Litestar], allocators: list[Allocator], session: Session
):
    # Updating allocator_id to existing allocator
    allocator = allocators[0]
    other = allocators[1]
    response = client.patch(
        f'{API_V1_PATH}/allocators/{allocator.allocator_id}',
        json={
            'allocator_name': other.allocator_name[::-1],
            'allocator_id': other.allocator_id,
        },
    )
    assert response.status_code == 400
    assert f'ID {other.allocator_id} already exists' in response.json()['detail']
    session.refresh(allocator)
    assert allocator.allocator_id != other.allocator_id
    assert allocator.allocator_name != other.allocator_name[::-1]


def test_update_allocator_validation(client: TestClient[Litestar]):
    # allocator_id in path out of range
    response = client.patch(
        f'{API_V1_PATH}/allocators/{ALLOCATOR_ID_MAX * 2}',
        json={
            'allocator_name': 'blah',
            'new_allocator_id': 123,
        },
    )
    assert response.status_code == 400
    assert f'<= {ALLOCATOR_ID_MAX}' in response.json()['extra'][0]['message']

    # new_allocator_id out of range
    response = client.patch(
        f'{API_V1_PATH}/allocators/0',
        json={
            'allocator_name': 'blah',
            'allocator_id': ALLOCATOR_ID_MAX * 2,
        },
    )
    assert response.status_code == 400
    assert f'<= {ALLOCATOR_ID_MAX}' in response.json()['extra'][0]['message']


def test_delete_allocator(client: TestClient[Litestar], allocator: Allocator):
    response = client.delete(f'{API_V1_PATH}/allocators/{allocator.allocator_id}')
    assert response.status_code == 204
    # The record was deleted, so deleting again should error
    response = client.delete(f'{API_V1_PATH}/allocators/{allocator.allocator_id}')
    assert response.status_code == 404
    assert f'ID {allocator.allocator_id} does not exist' in response.json()['detail']


def test_delete_allocator_existing_associations(
    client: TestClient[Litestar], node: Node
):
    # allocator_id still being referenced
    response = client.delete(f'{API_V1_PATH}/allocators/{node.allocator_id}')
    assert response.status_code == 400
    assert b'still associated with operators or nodes' in response.content


def test_delete_allocator_validation(client: TestClient[Litestar]):
    # allocator_id out of range
    response = client.delete(f'{API_V1_PATH}/allocators/{ALLOCATOR_ID_MAX * 2}')
    assert response.status_code == 400
    assert f'<= {ALLOCATOR_ID_MAX}' in response.json()['extra'][0]['message']

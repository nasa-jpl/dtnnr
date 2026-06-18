from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

from app.api.v1.allocator.schemas import (
    to_minimal_schema as to_allocator_minimal_schema,
)
from app.api.v1.operator.schemas import OperatorSchema, to_operator_schema
from app.config import API_V1_PATH, MAX_PAGE_SIZE
from app.fields import ALLOCATOR_ID_MAX, NODE_NUMBER_MAX, OPERATOR_ID_MAX
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

    from app.models import Allocator, Node, Operator

decoder = msgspec.json.Decoder(type=OperatorSchema, strict=False)


def test_get_operator(client: TestClient[Litestar], operator_with_details: Operator):
    operator = operator_with_details
    response = client.get(f'{API_V1_PATH}/operators/{operator.operator_id}')
    assert response.status_code == 200
    assert decoder.decode(response.content) == to_operator_schema(operator)
    # TODO: adapt these remaining checks
    # # Check if contacts are present
    # assert operator.contacts == load_data.contacts
    # for c in operator.contacts:
    #     assert f'"contact_id":{c.contact_id}'.encode() in response.data
    #     assert c.contact_name.encode() in response.data
    # # Check allocator is present
    # assert operator.allocator == load_data.allocator
    # assert f'"allocator_id":"{operator.allocator_id}"'.encode() in response.data
    # assert operator.allocator.allocator_name.encode() in response.data
    # # Check if hosts are present
    # assert operator.hosts == load_data.hosts
    # for h in operator.hosts:
    #     assert f'"host_id":{h.host_id}'.encode() in response.data
    #     assert h.hostname.encode() in response.data
    # # Check if nodes are present
    # assert operator.nodes == load_data.nodes
    # for n in operator.nodes:
    #     assert f'"node_id":{n.node_id}'.encode() in response.data
    #     assert f'"node_number":{n.node_number}'.encode() in response.data


def test_get_operator_not_found(client: TestClient[Litestar], operator: Operator):
    response = client.get(f'{API_V1_PATH}/operators/{operator.operator_id + 1}')
    assert response.status_code == 404
    assert f'ID {operator.operator_id + 1} does not exist' in response.json()['detail']


def test_get_operator_validation(client: TestClient[Litestar]):
    response = client.get(f'{API_V1_PATH}/operators/{OPERATOR_ID_MAX * 2}')
    assert response.status_code == 400
    assert f'<= {OPERATOR_ID_MAX}' in response.json()['extra'][0]['message']


def test_query_operators(client: TestClient[Litestar], operators: list[Operator]):
    items = collect_paginated_data(client, f'{API_V1_PATH}/operators', MAX_PAGE_SIZE)
    for o in operators:
        assert to_operator_schema(o).to_dict() in items


def test_query_operators_pagination(
    client: TestClient[Litestar], operators: list[Operator]
):
    items = collect_paginated_data(client, f'{API_V1_PATH}/operators', 1)
    for o in operators:
        assert to_operator_schema(o).to_dict() in items

    params = {'max_page_size': 1, 'page_token': 'last'}
    response = client.get(f'{API_V1_PATH}/operators', params=params)
    assert response.status_code == 200
    assert len(response.json()['items']) == params['max_page_size']
    assert response.json().get('prev_page_token') is not None
    assert response.json().get('next_page_token') is None
    assert items[-1] == response.json()['items'][0]


def test_query_operators_page_size(
    client: TestClient[Litestar], operators_max_and_one: list[Operator]
):
    check_page_size(client, f'{API_V1_PATH}/operators')


def test_query_operators_invalid_page_token(
    client: TestClient[Litestar], operators: list[Operator]
):
    check_invalid_page_token_query(client, f'{API_V1_PATH}/operators')


def test_query_operators_validation(client: TestClient[Litestar]):
    check_query_request_validation(client, f'{API_V1_PATH}/operators')


def test_create_operator(client: TestClient[Litestar], allocator: Allocator):
    operator_name = 'Test View Create Operator'
    response = client.post(
        f'{API_V1_PATH}/operators',
        json={
            'operator_name': operator_name,
            'allocator_id': allocator.allocator_id,
        },
    )
    assert response.status_code == 201
    content = decoder.decode(response.content)
    assert (
        response.headers['location'] == f'{API_V1_PATH}/operators/{content.operator_id}'
    )
    assert (
        response.headers['content-location']
        == f'{API_V1_PATH}/operators/{content.operator_id}'
    )
    assert content.operator_name == operator_name
    assert content.allocator == to_allocator_minimal_schema(allocator)


def test_create_operator_nonexistent_allocator(
    client: TestClient[Litestar], allocator: Allocator
):
    response = client.post(
        f'{API_V1_PATH}/operators',
        json={'operator_name': 'blah', 'allocator_id': allocator.allocator_id + 1},
    )
    assert response.status_code == 404
    assert (
        f'ID {allocator.allocator_id + 1} does not exist' in response.json()['detail']
    )


def test_create_operator_default_allocator(client: TestClient[Litestar]):
    operator_name = 'Test View Create Operator Default Allocator'
    response = client.post(
        f'{API_V1_PATH}/operators', json={'operator_name': operator_name}
    )
    assert response.status_code == 201
    content = decoder.decode(response.content)
    assert content.operator_name == operator_name
    assert content.allocator.allocator_id == '0'


def test_create_operator_validate_required_reqbody(client: TestClient[Litestar]):
    for response in [
        # Missing request body
        client.post(f'{API_V1_PATH}/operators'),
        # Empty request body
        client.post(f'{API_V1_PATH}/operators', content=b''),
    ]:
        assert response.status_code == 400
        assert 'Expected non-empty request' in response.json()['extra'][0]['message']


def test_create_operator_validate_null_reqbody(client: TestClient[Litestar]):
    # `null` is distinct from a missing / empty request body
    response = client.post(f'{API_V1_PATH}/operators', content=b'null')
    assert response.status_code == 400
    assert 'Expected `object`, got `null`' in response.json()['extra'][0]['message']


def test_create_operator_validate_reqbody_fields(client: TestClient[Litestar]):
    # Missing fields
    response = client.post(f'{API_V1_PATH}/operators', json={})
    assert response.status_code == 400
    assert 'missing required field' in response.json()['extra'][0]['message']

    # Negative allocator_id
    response = client.post(
        f'{API_V1_PATH}/operators',
        json={
            'allocator_id': -1,
            'operator_name': 'blah',
        },
    )
    assert response.status_code == 400
    assert '>= 0' in response.json()['extra'][0]['message']

    # operator_id > 2^63-1
    response = client.post(
        f'{API_V1_PATH}/operators',
        json={
            'allocator_id': ALLOCATOR_ID_MAX * 2,
            'operator_name': 'blah',
        },
    )
    assert response.status_code == 400
    assert f'<= {ALLOCATOR_ID_MAX}' in response.json()['extra'][0]['message']


def test_update_allocated_node_numbers_union(
    client: TestClient[Litestar], operator: Operator
):
    # Union, expand upper bound by doubling it
    old_lower = operator.allocated_node_numbers[0].lower
    old_upper = operator.allocated_node_numbers[0].upper
    response = client.post(
        f'{API_V1_PATH}/operators/{operator.operator_id}/allocated-node-numbers',
        json={
            'lower': old_lower,
            'upper': old_upper + 10,
            'operation': 'union',
            'bounds': '[)',
        },
    )
    assert response.status_code == 200
    content = decoder.decode(response.content)
    assert content.allocated_node_numbers[0].lower == old_lower
    assert content.allocated_node_numbers[0].upper == old_upper + 10


def test_update_allocated_node_numbers_difference(
    client: TestClient[Litestar], operator: Operator
):
    # Difference, remove the 0.5 to 0.75 part of the range
    old_lower = operator.allocated_node_numbers[0].lower
    old_upper = operator.allocated_node_numbers[0].upper
    half = old_lower + (old_upper - old_lower) // 2
    upper_bound_to_remove = half + (old_upper - half) // 2
    response = client.post(
        f'{API_V1_PATH}/operators/{operator.operator_id}/allocated-node-numbers',
        json={
            'lower': half,
            'upper': upper_bound_to_remove,
            'operation': 'difference',
            'bounds': '[)',
        },
    )
    assert response.status_code == 200
    content = decoder.decode(response.content)
    assert content.allocated_node_numbers[0].lower == old_lower
    assert content.allocated_node_numbers[0].upper == half
    assert content.allocated_node_numbers[1].lower == upper_bound_to_remove
    assert content.allocated_node_numbers[1].upper == old_upper


def test_update_allocated_node_numbers_intersection(
    client: TestClient[Litestar], operator: Operator
):
    # Intersection, only keep the 0.75 to 1.00 part of the range
    old_lower = operator.allocated_node_numbers[0].lower
    old_upper = operator.allocated_node_numbers[0].upper
    three_quarters = old_upper - (old_upper - old_lower) // 4
    response = client.post(
        f'{API_V1_PATH}/operators/{operator.operator_id}/allocated-node-numbers',
        json={
            'lower': three_quarters,
            # Omit upper, take advantage of upper bound being infinity
            'operation': 'intersection',
            'bounds': '[)',
        },
    )
    assert response.status_code == 200
    content = decoder.decode(response.content)
    assert content.allocated_node_numbers[0].lower == three_quarters
    assert content.allocated_node_numbers[0].upper == old_upper


def test_update_allocated_node_numbers_not_found(
    client: TestClient[Litestar], operator: Operator
):
    response = client.post(
        f'{API_V1_PATH}/operators/{operator.operator_id + 1}/allocated-node-numbers',
        json={'operation': 'union'},
    )
    assert response.status_code == 404
    assert f'ID {operator.operator_id + 1} does not exist' in response.json()['detail']


def test_update_allocated_node_numbers_overlapping(
    client: TestClient[Litestar], operators_same_allocator: list[Operator]
):
    o1 = operators_same_allocator[0]
    o2 = operators_same_allocator[1]

    response = client.post(
        f'{API_V1_PATH}/operators/{o1.operator_id}/allocated-node-numbers',
        json={
            'operation': 'union',
            'lower': o1.allocated_node_numbers[0].lower,
            'upper': o2.allocated_node_numbers[0].upper,
            'bounds': '[)',
        },
    )
    # Should only conflict with o2
    assert response.status_code == 400
    assert f'node numbers for operator ID {o1.operator_id}' in response.json()['detail']
    assert f'under allocator ID {o1.allocator_id}' in response.json()['detail']
    assert f'(operator_id): [{o2.operator_id}]' in response.json()['detail']

    # Increase o1 to have all node numbers
    response = client.post(
        f'{API_V1_PATH}/operators/{o1.operator_id}/allocated-node-numbers',
        json={
            'operation': '+',
        },
    )
    # Should conflict with all other operators
    assert response.status_code == 400
    assert f'node numbers for operator ID {o1.operator_id}' in response.json()['detail']
    assert f'under allocator ID {o1.allocator_id}' in response.json()['detail']
    l = [o.operator_id for o in o1.allocator.operators]
    l.remove(o1.operator_id)
    assert f'(operator_id): {l}' in response.json()['detail']


def test_update_allocated_node_numbers_intersection_missing_one_number(
    client: TestClient[Litestar], node: Node
):
    response = client.post(
        f'{API_V1_PATH}/operators/{node.operator_id}/allocated-node-numbers',
        json={'lower': 0, 'upper': 0, 'bounds': '()', 'operation': 'intersection'},
    )
    assert response.status_code == 400
    assert (
        f'{{}}, would not contain currently in-use node number: {node.node_number}'
        in response.json()['detail']
    )


def test_update_allocated_node_numbers_intersection_missing_multiple_numbers(
    client: TestClient[Litestar], nodes_under_same_operator: list[Node]
):
    n1 = nodes_under_same_operator[0]
    n2 = nodes_under_same_operator[1]
    response = client.post(
        f'{API_V1_PATH}/operators/{n1.operator_id}/allocated-node-numbers',
        json={'lower': 0, 'upper': 0, 'bounds': '()', 'operation': '*'},
    )
    assert response.status_code == 400
    assert (
        '{}, would not contain currently in-use node numbers:'
        f' {str(sorted([n1.node_number, n2.node_number]))[1:-1]}'
        in response.json()['detail']
    )


def test_update_allocated_node_numbers_difference_missing_one_number(
    client: TestClient[Litestar], node: Node
):
    response = client.post(
        f'{API_V1_PATH}/operators/{node.operator_id}/allocated-node-numbers',
        json={
            # [0, 2^32 - 1] by default
            'operation': 'difference'
        },
    )
    assert response.status_code == 400
    assert (
        f'{{}}, would not contain currently in-use node number: {node.node_number}'
        in response.json()['detail']
    )


def test_update_allocated_node_numbers_difference_missing_multiple_numbers(
    client: TestClient[Litestar], nodes_under_same_operator: list[Node]
):
    n1 = nodes_under_same_operator[0]
    n2 = nodes_under_same_operator[1]
    response = client.post(
        f'{API_V1_PATH}/operators/{n1.operator_id}/allocated-node-numbers',
        json={
            # [0, 2^32 - 1] by default
            'operation': '-'
        },
    )
    assert response.status_code == 400
    assert (
        '{}, would not contain currently in-use node numbers:'
        f' {str(sorted([n1.node_number, n2.node_number]))[1:-1]}'
        in response.json()['detail']
    )


def test_update_allocated_node_numbers_validate_bounds(client: TestClient[Litestar]):
    # lower > upper, invalid bounds
    response = client.post(
        f'{API_V1_PATH}/operators/0/allocated-node-numbers',
        json={
            'lower': 100,
            'upper': 50,
            'operation': 'union',
        },
    )
    assert response.status_code == 400
    assert (
        'Lower bound 100 cannot be greater than upper bound 50'
        in response.json()['extra'][0]['message']
    )

    # lower bounds out of range
    response = client.post(
        f'{API_V1_PATH}/operators/0/allocated-node-numbers',
        json={
            'lower': -1,
            'operation': 'union',
        },
    )
    assert response.status_code == 400
    assert '>= 0' in response.json()['extra'][0]['message']
    assert 'lower' in response.json()['extra'][0]['key']

    response = client.post(
        f'{API_V1_PATH}/operators/0/allocated-node-numbers',
        json={
            'lower': NODE_NUMBER_MAX * 2,
            'operation': 'union',
        },
    )
    assert response.status_code == 400
    assert f'<= {NODE_NUMBER_MAX}' in response.json()['extra'][0]['message']
    assert 'lower' in response.json()['extra'][0]['key']

    # upper bounds out of range
    response = client.post(
        f'{API_V1_PATH}/operators/0/allocated-node-numbers',
        json={
            'upper': -1,
            'operation': 'union',
        },
    )
    assert response.status_code == 400
    assert '>= 0' in response.json()['extra'][0]['message']
    assert 'upper' in response.json()['extra'][0]['key']

    response = client.post(
        f'{API_V1_PATH}/operators/0/allocated-node-numbers',
        json={
            'upper': NODE_NUMBER_MAX * 2,
            'operation': 'union',
        },
    )
    assert response.status_code == 400
    assert f'<= {NODE_NUMBER_MAX}' in response.json()['extra'][0]['message']
    assert 'upper' in response.json()['extra'][0]['key']


def test_update_allocated_node_numbers_validate_required_reqbody(
    client: TestClient[Litestar],
):
    for response in [
        # Missing request body
        client.post(f'{API_V1_PATH}/operators/0/allocated-node-numbers'),
        # Empty request body
        client.post(f'{API_V1_PATH}/operators/0/allocated-node-numbers', content=b''),
    ]:
        assert response.status_code == 400
        assert 'Expected non-empty request' in response.json()['extra'][0]['message']


def test_update_allocated_node_numbers_validate_missing_operation(
    client: TestClient[Litestar],
):
    response = client.post(f'{API_V1_PATH}/operators/0/allocated-node-numbers', json={})
    assert response.status_code == 400
    assert (
        'Object missing required field `operation`'
        in response.json()['extra'][0]['message']
    )


def test_update_allocated_node_numbers_validate_operator_id(
    client: TestClient[Litestar],
):
    response = client.post(
        f'{API_V1_PATH}/operators/{OPERATOR_ID_MAX * 2}/allocated-node-numbers',
        json={'operation': '+'},
    )
    assert response.status_code == 400
    assert f'<= {OPERATOR_ID_MAX}' in response.json()['extra'][0]['message']


def test_update_operator_only_name(
    client: TestClient[Litestar], operator: Operator, session: Session
):
    operator_name = 'Test View Update Operator'
    assert operator.operator_name != operator_name
    response = client.patch(
        f'{API_V1_PATH}/operators/{operator.operator_id}',
        json={'operator_name': operator_name},
    )
    assert response.status_code == 200
    session.refresh(operator)
    content = decoder.decode(response.content)
    assert content == to_operator_schema(operator)


def test_update_operator_only_allocator(
    client: TestClient[Litestar],
    operator: Operator,
    allocator: Allocator,
    session: Session,
):
    response = client.patch(
        f'{API_V1_PATH}/operators/{operator.operator_id}',
        json={'allocator_id': allocator.allocator_id},
    )
    assert response.status_code == 200
    session.refresh(operator)
    content = decoder.decode(response.content)
    assert content == to_operator_schema(operator)


def test_update_operator_name_and_allocator(
    client: TestClient[Litestar],
    operator: Operator,
    allocator: Allocator,
    session: Session,
):
    operator_name = 'Test View Update Operator Name and Allocator'
    response = client.patch(
        f'{API_V1_PATH}/operators/{operator.operator_id}',
        json={'operator_name': operator_name, 'allocator_id': allocator.allocator_id},
    )
    assert response.status_code == 200
    session.refresh(operator)
    content = decoder.decode(response.content)
    assert content == to_operator_schema(operator)


def test_update_operator_no_change(client: TestClient[Litestar], operator: Operator):
    old_operator_name = operator.operator_name
    old_allocator_id = operator.allocator_id

    for response in [
        # Missing request body
        client.patch(f'{API_V1_PATH}/operators/{operator.operator_id}'),
        # Empty request body
        client.patch(f'{API_V1_PATH}/operators/{operator.operator_id}', content=b''),
        # Empty object
        client.patch(f'{API_V1_PATH}/operators/{operator.operator_id}', json={}),
        # Same operator_name and allocator_id
        client.patch(
            f'{API_V1_PATH}/operators/{operator.operator_id}',
            json={
                'operator_name': old_operator_name,
                'allocator_id': old_allocator_id,
            },
        ),
    ]:
        assert response.status_code == 200
        content = decoder.decode(response.content)
        assert content.operator_name == old_operator_name
        assert content.allocator.allocator_id == str(old_allocator_id)


def test_update_operator_not_found(client: TestClient[Litestar], operator: Operator):
    response = client.patch(
        f'{API_V1_PATH}/operators/{operator.operator_id + 1}',
        json={'operator_name': 'blah'},
    )
    assert response.status_code == 404
    assert f'ID {operator.operator_id + 1} does not exist' in response.json()['detail']


def test_update_operator_nonexistent_allocator(
    client: TestClient[Litestar], operator: Operator, allocator: Allocator
):
    response = client.patch(
        f'{API_V1_PATH}/operators/{operator.operator_id}',
        json={'allocator_id': allocator.allocator_id + 1},
    )
    assert response.status_code == 404
    assert (
        f'ID {allocator.allocator_id + 1} does not exist' in response.json()['detail']
    )


def test_update_operator_overlapping_node_numbers(
    client: TestClient[Litestar],
    operators_overlapping_allocated_node_numbers: list[Operator],
):
    o1 = operators_overlapping_allocated_node_numbers[0]
    o2 = operators_overlapping_allocated_node_numbers[1]
    response = client.patch(
        f'{API_V1_PATH}/operators/{o1.operator_id}',
        json={'allocator_id': o2.allocator_id},
    )
    assert response.status_code == 400
    assert f'(operator_id): [{o2.operator_id}]' in response.json()['detail']


def test_update_operator_conflicting_node_numbers(
    client: TestClient[Litestar], nodes_different_policy_same_node_number: list[Node]
):
    # n1 follows Allocator -> Operator -> Node
    n1 = nodes_different_policy_same_node_number[0]
    # n2 follows Allocator -> Node
    n2 = nodes_different_policy_same_node_number[1]
    response = client.patch(
        f'{API_V1_PATH}/operators/{n1.operator_id}',
        json={'allocator_id': n2.allocator_id},
    )
    assert response.status_code == 400
    assert str(n2.node_number) in response.json()['detail']


def test_update_operator_validation(client: TestClient[Litestar], operator: Operator):
    # operator_id out of range
    response = client.patch(f'{API_V1_PATH}/operators/{OPERATOR_ID_MAX * 2}')
    assert response.status_code == 400
    assert f'<= {OPERATOR_ID_MAX}' in response.json()['extra'][0]['message']

    # allocator_id out of range
    response = client.patch(
        f'{API_V1_PATH}/operators/{operator.operator_id}',
        json={'allocator_id': ALLOCATOR_ID_MAX * 2},
    )
    assert response.status_code == 400
    assert f'<= {ALLOCATOR_ID_MAX}' in response.json()['extra'][0]['message']


def test_delete_operator(client: TestClient[Litestar], operator: Operator):
    response = client.delete(f'{API_V1_PATH}/operators/{operator.operator_id}')
    assert response.status_code == 204
    # The record was deleted, so deleting again should error
    response = client.delete(f'{API_V1_PATH}/operators/{operator.operator_id}')
    assert response.status_code == 404
    assert f'ID {operator.operator_id} does not exist' in response.json()['detail']


def test_delete_operator_validation(client: TestClient[Litestar]):
    # operator_id out of range
    response = client.delete(f'{API_V1_PATH}/operators/{OPERATOR_ID_MAX * 2}')
    assert response.status_code == 400
    assert f'<= {OPERATOR_ID_MAX}' in response.json()['extra'][0]['message']

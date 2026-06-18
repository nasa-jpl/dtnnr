from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec
import pytest

from app.api.v1.cl_protocol.schemas import (
    ClProtocolSchema,
    protocol_class_arr_to_int,
    protocol_class_int_to_arr,
)
from app.config import API_V1_PATH
from app.fields import CL_PROTOCOL_ID_MAX
from app.models import known_cl_protocol_name_to_class

if TYPE_CHECKING:
    from litestar import Litestar
    from litestar.testing import TestClient

    from app.models import ClProtocol, InductIp, Node

decoder = msgspec.json.Decoder(type=ClProtocolSchema, strict=False)
path_prefix = f'{API_V1_PATH}/cl-protocols'


def test_get_cl_protocol(client: TestClient[Litestar], cl_protocol: ClProtocol):
    response = client.get(f'{path_prefix}/{cl_protocol.cl_protocol_id}')
    assert response.status_code == 200
    content = decoder.decode(response.content)
    # decode() gives us set[enum] while to_cl_protocol_schema gives list[str],
    # so just check these individually
    assert content.cl_protocol_id == str(cl_protocol.cl_protocol_id)
    assert content.cl_protocol_name == cl_protocol.cl_protocol_name
    assert content.node_id == str(cl_protocol.node_id)
    assert (
        protocol_class_arr_to_int(content.cl_protocol_class)
        == cl_protocol.cl_protocol_class
    )


def test_get_cl_protocol_not_found(
    client: TestClient[Litestar], cl_protocol: ClProtocol
):
    response = client.get(f'{path_prefix}/{cl_protocol.cl_protocol_id + 1}')
    assert response.status_code == 404
    assert (
        f'ID {cl_protocol.cl_protocol_id + 1} does not exist'
        in response.json()['detail']
    )


def test_get_cl_protocol_validation(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/{CL_PROTOCOL_ID_MAX + 1}')
    assert response.status_code == 400
    assert f'<= {CL_PROTOCOL_ID_MAX}' in response.json()['extra'][0]['message']


def test_update_cl_protocol(client: TestClient[Litestar], cl_protocol: ClProtocol):
    new_name = 'foo'
    new_class = ['BP_BEST_EFFORT', 'BP_RELIABLE']
    response = client.patch(
        f'{path_prefix}/{cl_protocol.cl_protocol_id}',
        json={'cl_protocol_name': new_name, 'cl_protocol_class': new_class},
    )
    assert response.status_code == 200
    assert response.json()['cl_protocol_name'] == new_name
    assert response.json()['cl_protocol_class'] == new_class


@pytest.mark.parametrize(
    'protocol_name,class_val',
    [(name, val) for name, val in known_cl_protocol_name_to_class.items()],
)
def test_update_cl_protocol_omit_class_well_known_name(
    client: TestClient[Litestar],
    cl_protocol: ClProtocol,
    protocol_name: str,
    class_val: int,
):
    response = client.patch(
        f'{path_prefix}/{cl_protocol.cl_protocol_id}',
        json={'cl_protocol_name': protocol_name},
    )
    assert response.status_code == 200
    assert response.json()['cl_protocol_name'] == protocol_name
    assert response.json()['cl_protocol_class'] == protocol_class_int_to_arr(class_val)


def test_update_cl_protocol_omit_class_custom_name(
    client: TestClient[Litestar], cl_protocol: ClProtocol
):
    old_class_val = cl_protocol.cl_protocol_class
    response = client.patch(
        f'{path_prefix}/{cl_protocol.cl_protocol_id}', json={'cl_protocol_name': 'foo'}
    )
    assert response.status_code == 200
    assert response.json()['cl_protocol_name'] == 'foo'
    assert response.json()['cl_protocol_class'] == protocol_class_int_to_arr(
        old_class_val
    )


def test_update_cl_protocol_no_change(
    client: TestClient[Litestar],
    cl_protocols_for_known_cli_same_node: list[ClProtocol],
):
    for cl_protocol in cl_protocols_for_known_cli_same_node:
        old_cl_protocol_name = cl_protocol.cl_protocol_name
        old_cl_protocol_class = protocol_class_int_to_arr(cl_protocol.cl_protocol_class)
        for response in [
            # Missing request body
            client.patch(f'{path_prefix}/{cl_protocol.cl_protocol_id}'),
            # Empty request body
            client.patch(f'{path_prefix}/{cl_protocol.cl_protocol_id}', content=b''),
            # Empty object
            client.patch(f'{path_prefix}/{cl_protocol.cl_protocol_id}', json={}),
            # Same values
            client.patch(
                f'{path_prefix}/{cl_protocol.cl_protocol_id}',
                json={
                    'cl_protocol_name': old_cl_protocol_name,
                    'cl_protocol_class': old_cl_protocol_class,
                },
            ),
        ]:
            assert response.status_code == 200
            assert response.json()['cl_protocol_name'] == old_cl_protocol_name
            assert response.json()['cl_protocol_class'] == old_cl_protocol_class


def test_update_cl_protocol_duplicate_class(
    client: TestClient[Litestar], cl_protocol: ClProtocol
):
    response = client.patch(
        f'{path_prefix}/{cl_protocol.cl_protocol_id}',
        json={
            'cl_protocol_name': 'foo',
            'cl_protocol_class': ['BP_BEST_EFFORT' for _ in range(2)],
        },
    )
    assert response.status_code == 200
    assert response.json()['cl_protocol_id'] == str(cl_protocol.cl_protocol_id)
    assert response.json()['cl_protocol_name'] == 'foo'
    assert response.json()['cl_protocol_class'] == ['BP_BEST_EFFORT']


def test_update_cl_protocol_dependent_inducts(
    client: TestClient[Litestar], induct_ip: InductIp
):
    response = client.patch(
        f'{path_prefix}/{induct_ip.induct.cl_protocol_id}',
        json={'cl_protocol_name': 'foo'},
    )
    assert response.status_code == 400
    assert induct_ip.induct.cl_protocol_name in response.json()['detail']
    assert str(induct_ip.induct_id) in response.json()['extra']


def test_update_cl_protocol_existing(
    client: TestClient[Litestar], node_with_cl_protocols: Node
):
    node = node_with_cl_protocols
    p1 = node.cl_protocols[0]
    p2 = node.cl_protocols[1]
    response = client.patch(
        f'{path_prefix}/{p1.cl_protocol_id}',
        json={
            'cl_protocol_name': p2.cl_protocol_name,
            'cl_protocol_class': protocol_class_int_to_arr(p2.cl_protocol_class),
        },
    )
    assert response.status_code == 400
    assert response.json()['detail'] == (
        f"A CL protocol with the name '{p2.cl_protocol_name}' is already"
        f' associated with node ID {node.node_id}'
    )


def test_update_cl_protocol_well_known_protocol(
    client: TestClient[Litestar], cl_protocol: ClProtocol
):
    response = client.patch(
        f'{path_prefix}/{cl_protocol.cl_protocol_id}',
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


def test_update_cl_protocol_not_found(client: TestClient[Litestar]):
    response = client.patch(f'{path_prefix}/0')
    assert response.status_code == 404
    assert 'ID 0 does not exist' in response.json()['detail']


def test_update_cl_protocol_validation(client: TestClient[Litestar]):
    url = f'{path_prefix}/0'
    # Out of range name
    for r in [
        client.patch(url, json={'cl_protocol_name': ''}),
        client.patch(url, json={'cl_protocol_name': 'A' * 16}),
    ]:
        assert r.status_code == 400
        assert r.json()['extra'][0]['message'] == (
            'Length in bytes must be in the inclusive range [1, 15]'
        )
        assert r.json()['extra'][0]['key'] == 'cl_protocol_name'
        assert r.json()['extra'][0]['source'] == 'body'

    # Invalid enum
    response = client.patch(
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
    response = client.patch(
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
    response = client.patch(
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
    response = client.patch(
        f'{path_prefix}/{CL_PROTOCOL_ID_MAX + 1}',
        json={'cl_protocol_name': 'foo'},
    )
    assert response.status_code == 400
    assert f'<= {CL_PROTOCOL_ID_MAX}' in response.json()['extra'][0]['message']


def test_delete_cl_protocol(client: TestClient[Litestar], cl_protocol: ClProtocol):
    response = client.delete(f'{path_prefix}/{cl_protocol.cl_protocol_id}')
    assert response.status_code == 204
    # The record was deleted, so deleting again should error
    response = client.delete(f'{path_prefix}/{cl_protocol.cl_protocol_id}')
    assert response.status_code == 404
    assert (
        f'ID {cl_protocol.cl_protocol_id} does not exist' in response.json()['detail']
    )


def test_delete_cl_protocol_dependent_inducts(client: TestClient, induct_ip: InductIp):
    response = client.delete(f'{path_prefix}/{induct_ip.induct.cl_protocol_id}')
    assert response.status_code == 400
    assert induct_ip.induct.cl_protocol_name in response.json()['detail']
    assert str(induct_ip.induct_id) in response.json()['extra']


def test_delete_cl_protocol_validation(client: TestClient[Litestar]):
    response = client.delete(f'{path_prefix}/{CL_PROTOCOL_ID_MAX + 1}')
    assert response.status_code == 400
    assert f'<= {CL_PROTOCOL_ID_MAX}' in response.json()['extra'][0]['message']

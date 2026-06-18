from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

from app.api.v1.destination.schemas import DestinationSchema, to_destination_schema
from app.config import API_V1_PATH
from app.fields import DESTINATION_ID_MAX

if TYPE_CHECKING:
    from litestar import Litestar
    from litestar.testing import TestClient
    from sqlalchemy.orm import Session

    from app.models import Destination

decoder = msgspec.json.Decoder(type=DestinationSchema, strict=False)
path_prefix = f'{API_V1_PATH}/destinations'


def test_get_destination(
    client: TestClient[Litestar],
    destination_ip: Destination,
    destination_name: Destination,
):
    response = client.get(f'{path_prefix}/{destination_ip.destination_id}')
    assert response.status_code == 200
    assert decoder.decode(response.content) == to_destination_schema(destination_ip)

    response = client.get(f'{path_prefix}/{destination_name.destination_id}')
    assert response.status_code == 200
    assert decoder.decode(response.content) == to_destination_schema(destination_name)


def test_get_destination_not_found(
    client: TestClient[Litestar], destination_ip: Destination
):
    response = client.get(f'{path_prefix}/{destination_ip.destination_id + 1}')
    assert response.status_code == 404
    assert (
        f'ID {destination_ip.destination_id + 1} does not exist'
    ) in response.json()['detail']


def test_get_destination_validation(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/{DESTINATION_ID_MAX * 2}')
    assert response.status_code == 400
    assert f'<= {DESTINATION_ID_MAX}' in response.json()['extra'][0]['message']


def test_update_destination(
    client: TestClient[Litestar],
    destination_ip: Destination,
    destination_name: Destination,
    session: Session,
):
    # IP address to IP address
    # Use private addresses to avoid conflicts with factories
    ip = '192.168.1.4'
    response = client.patch(
        f'{path_prefix}/{destination_ip.destination_id}?ip=true',
        json={'destination_value': ip},
    )
    assert response.status_code == 200
    session.refresh(destination_ip)
    assert decoder.decode(response.content) == to_destination_schema(destination_ip)
    assert str(destination_ip.ip_address) == ip

    # Registered name to registered name
    # Use domain names with more than one subdomain level to avoid conflicts
    # with factories.
    name = 'test.test.test'
    response = client.patch(
        f'{path_prefix}/{destination_name.destination_id}',
        json={'destination_value': name},
    )
    assert response.status_code == 200
    session.refresh(destination_name)
    assert decoder.decode(response.content) == to_destination_schema(destination_name)
    assert destination_name.registered_name == name

    # IP address to registered name
    name = 'ip.addr.to.reg.name'
    response = client.patch(
        f'{path_prefix}/{destination_ip.destination_id}',
        json={'destination_value': name},
    )
    assert response.status_code == 200
    session.refresh(destination_ip)
    assert decoder.decode(response.content) == to_destination_schema(destination_ip)
    assert destination_ip.registered_name == name
    assert destination_ip.ip_address is None

    # Registered name to IP address
    ip = '192.168.1.5'
    response = client.patch(
        f'{path_prefix}/{destination_name.destination_id}?ip=true',
        json={'destination_value': ip},
    )
    assert response.status_code == 200
    session.refresh(destination_name)
    assert decoder.decode(response.content) == to_destination_schema(destination_name)
    assert destination_name.registered_name is None
    assert str(destination_name.ip_address) == ip


def test_update_destination_existing(
    client: TestClient[Litestar], destinations_same_host: list[Destination]
):
    d_ip = destinations_same_host[0]
    d_name = destinations_same_host[1]

    response = client.patch(
        f'{path_prefix}/{d_ip.destination_id}',
        json={'destination_value': d_name.registered_name},
    )
    assert response.status_code == 400
    assert (
        f"value '{d_name.registered_name}' is already associated with host"
        f' ID {d_name.host_id}'
    ) in response.json()['detail']

    response = client.patch(
        f'{path_prefix}/{d_name.destination_id}?ip=true',
        json={'destination_value': str(d_ip.ip_address)},
    )
    assert response.status_code == 400
    assert (
        f"value '{str(d_ip.ip_address)}' is already associated with host"
        f' ID {d_ip.host_id}'
    ) in response.json()['detail']


def test_update_destination_not_found(
    client: TestClient[Litestar], destination_ip: Destination
):
    response = client.patch(
        f'{path_prefix}/{destination_ip.destination_id + 1}',
        json={'destination_value': 'blah.blah.blah'},
    )
    assert response.status_code == 404
    assert (
        f'Destination ID {destination_ip.destination_id + 1} does not exist'
    ) in response.json()['detail']


def test_update_destination_no_change(
    client: TestClient[Litestar], destination_ip: Destination, session: Session
):
    old_dest = to_destination_schema(destination_ip)
    old_dest_value = str(destination_ip.ip_address)

    for response in [
        # Missing request body
        client.patch(f'{path_prefix}/{destination_ip.destination_id}'),
        # Empty request body
        client.patch(f'{path_prefix}/{destination_ip.destination_id}', content=b''),
        # Empty object
        client.patch(f'{path_prefix}/{destination_ip.destination_id}', json={}),
        # Same destination_value
        client.patch(
            f'{path_prefix}/{destination_ip.destination_id}',
            json={'destination_value': old_dest_value},
        ),
    ]:
        assert response.status_code == 200
        session.refresh(destination_ip)
        assert decoder.decode(response.content) == old_dest


def test_update_destination_validation(client: TestClient[Litestar]):
    # destination_id out of range
    response = client.patch(
        f'{path_prefix}/{DESTINATION_ID_MAX * 2}?ip=true',
        json={'destination_value': '192.168.1.6'},
    )
    assert response.status_code == 400
    assert f'<= {DESTINATION_ID_MAX}' in response.json()['extra'][0]['message']

    # Invalid IP address
    response = client.patch(
        f'{path_prefix}/0?ip=true', json={'destination_value': 'abc'}
    )
    assert response.status_code == 400
    assert (
        "'abc' does not appear to be an IPv4 or IPv6 address"
        in response.json()['extra'][0]['message']
    )

    # null destination_value
    response = client.patch(f'{path_prefix}/0', json={'destination_value': None})
    assert response.status_code == 400
    assert 'Expected `str`, got `null`' in response.json()['extra'][0]['message']


def test_delete_destination(client: TestClient[Litestar], destination_ip: Destination):
    response = client.delete(f'{path_prefix}/{destination_ip.destination_id}')
    assert response.status_code == 204
    # The record was deleted, so deleting again should error
    response = client.delete(f'{path_prefix}/{destination_ip.destination_id}')
    assert response.status_code == 404
    assert (
        f'ID {destination_ip.destination_id} does not exist'
        in response.json()['detail']
    )


def test_delete_destination_validation(client: TestClient[Litestar]):
    response = client.delete(f'{path_prefix}/{DESTINATION_ID_MAX * 2}')
    assert response.status_code == 400
    assert f'<= {DESTINATION_ID_MAX}' in response.json()['extra'][0]['message']

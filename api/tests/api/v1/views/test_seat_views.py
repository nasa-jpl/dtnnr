from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

from app.api.v1.induct.schemas import process_destination_value
from app.api.v1.link.schemas import to_link_schema
from app.api.v1.seat.schemas import SeatSchema, to_seat_schema
from app.config import API_V1_PATH, MAX_PAGE_SIZE
from app.fields import DESTINATION_ID_MAX, LINK_ID_MAX, PORT_NUMBER_MAX, SEAT_ID_MAX
from app.models import CommDirectionEnumInternal
from tests.util import (
    check_invalid_page_token_different_url,
    check_page_size,
    check_paginated_request_validation,
    collect_paginated_data,
)

if TYPE_CHECKING:
    from litestar import Litestar
    from litestar.testing import TestClient
    from sqlalchemy.orm import Session

    from app.models import Destination, Link, Seat, SeatIp

decoder = msgspec.json.Decoder(type=SeatSchema, strict=False)
path_prefix = f'{API_V1_PATH}/seats'


def test_get_seat(client: TestClient[Litestar], seat: Seat):
    response = client.get(f'{path_prefix}/{seat.seat_id}')
    assert response.status_code == 200
    assert decoder.decode(response.content) == to_seat_schema(seat)


def test_get_seat_not_found(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/0')
    assert response.status_code == 404
    assert f'ID 0 does not exist' in response.json()['detail']


def test_get_seat_validation(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/{SEAT_ID_MAX + 1}')
    assert response.status_code == 400
    assert f'<= {SEAT_ID_MAX}' in response.json()['extra'][0]['message']


def test_list_seat_links(client: TestClient[Litestar], seat_with_links: Seat):
    seat = seat_with_links
    items = collect_paginated_data(
        client, f'{path_prefix}/{seat.seat_id}/links', MAX_PAGE_SIZE
    )
    for l in seat.links:
        assert to_link_schema(l, with_host=False).to_dict() in items


def test_list_seat_links_pagination(
    client: TestClient[Litestar], seat_max_and_one_links: Seat
):
    seat = seat_max_and_one_links
    items = collect_paginated_data(client, f'{path_prefix}/{seat.seat_id}/links', 1)
    for l in seat.links:
        assert to_link_schema(l, with_host=False).to_dict() in items

    params = {'max_page_size': 1, 'page_token': 'last'}
    response = client.get(f'{path_prefix}/{seat.seat_id}/links', params=params)
    assert response.status_code == 200
    assert len(response.json()['items']) == params['max_page_size']
    assert response.json().get('prev_page_token') is not None
    assert response.json().get('next_page_token') is None
    assert items[-1] == response.json()['items'][0]


def test_list_seat_links_page_size(
    client: TestClient[Litestar], seat_max_and_one_links: Seat
):
    seat = seat_max_and_one_links
    check_page_size(client, f'{path_prefix}/{seat.seat_id}/links')


def test_list_seat_links_invalid_page_token(
    client: TestClient[Litestar], seat_max_and_one_links: Seat, seat: Seat
):
    other_seat_id = seat.seat_id
    seat = seat_max_and_one_links
    check_invalid_page_token_different_url(
        client,
        f'{path_prefix}/{seat.seat_id}/links',
        f'{path_prefix}/{other_seat_id}/links',
    )


def test_list_seat_links_not_found(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/0/links')
    assert response.status_code == 404
    assert 'ID 0 does not exist' in response.json()['detail']


def test_list_seat_links_validation(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/{SEAT_ID_MAX + 1}/links')
    assert response.status_code == 400
    assert f'<= {SEAT_ID_MAX}' in response.json()['extra'][0]['message']

    check_paginated_request_validation(client, f'{path_prefix}/0/links')


def test_replace_seat_links(
    client: TestClient[Litestar],
    seat_with_link_on_host_with_links: Seat,
    session: Session,
):
    seat = seat_with_link_on_host_with_links
    old_links = seat.links
    host = seat.node.host
    response = client.put(
        f'{path_prefix}/{seat.seat_id}/links', json=[l.link_id for l in host.links]
    )
    assert response.status_code == 204
    session.refresh(seat)
    assert seat.links != old_links
    assert seat.links == host.links


def test_replace_seat_links_empty(
    client: TestClient[Litestar],
    seat_with_links: Seat,
    session: Session,
):
    seat = seat_with_links
    response = client.put(f'{path_prefix}/{seat.seat_id}/links', json=[])
    assert response.status_code == 204
    session.refresh(seat)
    assert not seat.links


def test_replace_seat_links_duplicate_ids(
    client: TestClient[Litestar],
    seat_with_link_on_host_with_links: Seat,
    session: Session,
):
    seat = seat_with_link_on_host_with_links
    host = seat.node.host
    link = host.links[0]
    response = client.put(
        f'{path_prefix}/{seat.seat_id}/links',
        json=[link.link_id, str(link.link_id)] * 2,
    )
    assert response.status_code == 204
    session.refresh(seat)
    assert len(seat.links) == 1
    assert seat.links[0] == link


def test_replace_seat_links_not_found(client: TestClient[Litestar]):
    response = client.put(f'{path_prefix}/0/links', json=[])
    assert response.status_code == 404
    assert 'Seat ID 0 does not exist' in response.json()['detail']


def test_replace_seat_links_no_host(
    client: TestClient[Litestar],
    seat_no_host: Seat,
    links_not_simplex_outgoing: list[Link],
):
    seat = seat_no_host
    response = client.put(
        f'{path_prefix}/{seat.seat_id}/links',
        json=[l.link_id for l in links_not_simplex_outgoing],
    )
    assert response.status_code == 400
    assert (
        f'node ID {seat.node_id} is not associated with a host'
        in response.json()['detail']
    )


def test_replace_seat_links_no_host_clear(
    client: TestClient[Litestar], seat_no_host: Seat, session: Session
):
    seat = seat_no_host
    response = client.put(f'{path_prefix}/{seat.seat_id}/links', json=[])
    assert response.status_code == 204
    session.refresh(seat)
    assert not seat.links


def test_replace_seat_links_wrong_host(
    client: TestClient[Litestar],
    seat: Seat,
    links_not_simplex_outgoing: list[Link],
):
    ids = [l.link_id for l in links_not_simplex_outgoing] + [0]
    response = client.put(f'{path_prefix}/{seat.seat_id}/links', json=ids)
    assert response.status_code == 400
    assert f'not associated with host ID {seat.host_id}' in response.json()['detail']
    assert response.json()['extra'] == [str(i) for i in sorted(ids)]


def test_replace_seat_links_wrong_direction(
    client: TestClient[Litestar],
    seat_on_host_with_links_simplex_outgoing_etc: Seat,
):
    seat = seat_on_host_with_links_simplex_outgoing_etc
    links = seat.node.host.links
    ids = [
        l.link_id for l in links if l.direction == CommDirectionEnumInternal.SIMPLEX_OUT
    ]
    response = client.put(f'{path_prefix}/{seat.seat_id}/links', json=ids)
    assert response.status_code == 400
    assert (
        f"direction '{CommDirectionEnumInternal.SIMPLEX_OUT.value}'"
        in response.json()['detail']
    )
    assert response.json()['extra'] == [str(i) for i in sorted(ids)]


def test_replace_seat_links_required_reqbody(client: TestClient[Litestar]):
    for response in [
        # Missing request body
        client.put(f'{path_prefix}/0/links'),
        # Empty request body
        client.put(f'{path_prefix}/0/links', content=b''),
    ]:
        assert response.status_code == 400
        assert 'Expected non-empty request' in response.json()['extra'][0]['message']


def test_replace_seat_links_null_reqbody(client: TestClient[Litestar]):
    # `null` is distinct from a missing / empty request body
    response = client.put(f'{path_prefix}/0/links', content=b'null')
    assert response.status_code == 400
    assert 'Expected `array`, got `null`' in response.json()['extra'][0]['message']


def test_replace_seat_links_validation(client: TestClient[Litestar]):
    # link_id out of range
    response = client.put(f'{path_prefix}/0/links', json=[1, 2, 3, LINK_ID_MAX + 1, 4])
    assert response.status_code == 400
    assert f'Expected `int` <= {LINK_ID_MAX}' == response.json()['extra'][0]['message']
    # TODO: check if it reports the right index after my PR is approved

    # seat_id out of range
    response = client.put(f'{path_prefix}/{SEAT_ID_MAX + 1}/links', json=[])
    assert response.status_code == 400
    assert f'Expected `int` <= {SEAT_ID_MAX}' == response.json()['extra'][0]['message']


def test_replace_seat_plain_to_plain(
    client: TestClient[Litestar], seat_null_type: Seat
):
    seat = seat_null_type
    lsi_command = 'foo'
    response = client.put(
        f'{path_prefix}/{seat.seat_id}',
        json={'lsi_command': lsi_command, 'seat_ip': None},
    )
    assert response.status_code == 200
    assert response.json()['seat_id'] == str(seat.seat_id)
    assert response.json()['lsi_command'] == lsi_command
    assert response.json()['lsi_command_full'] == lsi_command
    assert response.json()['seat_ip'] is None


def test_replace_seat_ip_to_ip(client: TestClient[Litestar], seat_ip: SeatIp):
    seat = seat_ip.seat
    host = seat.node.host
    dest = host.destinations[0]
    lsi_command = 'foo'
    port_number = 34
    response = client.put(
        f'{path_prefix}/{seat.seat_id}',
        json={
            'lsi_command': lsi_command,
            'seat_ip': {
                'destination_id': dest.destination_id,
                'port_number': port_number,
            },
        },
    )
    assert response.status_code == 200
    assert response.json()['seat_id'] == str(seat.seat_id)
    assert response.json()['lsi_command_full'] == (
        f'{lsi_command} {process_destination_value(dest)}:{port_number}'
    )
    assert response.json()['lsi_command'] == lsi_command
    assert response.json()['seat_ip']['destination']['destination_id'] == str(
        dest.destination_id
    )
    assert response.json()['seat_ip']['port_number'] == port_number


def test_replace_seat_plain_to_ip(client: TestClient[Litestar], seat_null_type: Seat):
    seat = seat_null_type
    host = seat.node.host
    dest = host.destinations[0]
    lsi_command = 'foo'
    port_number = 34
    response = client.put(
        f'{path_prefix}/{seat.seat_id}',
        json={
            'lsi_command': lsi_command,
            'seat_ip': {
                'destination_id': dest.destination_id,
                'port_number': port_number,
            },
        },
    )
    assert response.status_code == 200
    assert response.json()['seat_id'] == str(seat.seat_id)
    assert response.json()['lsi_command_full'] == (
        f'{lsi_command} {process_destination_value(dest)}:{port_number}'
    )
    assert response.json()['lsi_command'] == lsi_command
    assert response.json()['seat_ip']['destination']['destination_id'] == str(
        dest.destination_id
    )
    assert response.json()['seat_ip']['port_number'] == port_number


def test_replace_seat_ip_to_plain(client: TestClient[Litestar], seat_ip: SeatIp):
    seat = seat_ip.seat
    lsi_command = 'foo'
    response = client.put(
        f'{path_prefix}/{seat.seat_id}',
        json={
            'lsi_command': lsi_command,
            'seat_ip': None,
        },
    )
    assert response.status_code == 200
    assert response.json()['seat_id'] == str(seat.seat_id)
    assert response.json()['lsi_command_full'] == lsi_command
    assert response.json()['lsi_command'] == lsi_command
    assert response.json()['seat_ip'] is None


def test_replace_seat_defaults(client: TestClient[Litestar], seat: Seat):
    for response in [
        client.put(f'{path_prefix}/{seat.seat_id}'),
        client.put(f'{path_prefix}/{seat.seat_id}', content=b''),
        client.put(f'{path_prefix}/{seat.seat_id}', json={}),
    ]:
        assert response.status_code == 200
        assert response.json()['seat_id'] == str(seat.seat_id)
        assert response.json()['lsi_command_full'] is None
        assert response.json()['lsi_command'] is None
        assert response.json()['seat_ip'] is None

    response = client.put(f'{path_prefix}/{seat.seat_id}', json={'seat_ip': {}})
    assert response.status_code == 200
    assert response.json()['seat_id'] == str(seat.seat_id)
    assert response.json()['lsi_command'] is None
    assert response.json()['lsi_command_full'] is None
    assert response.json()['seat_ip']['destination'] is None
    assert response.json()['seat_ip']['port_number'] is None


def test_replace_seat_not_found(client: TestClient[Litestar], seat: Seat):
    response = client.put(f'{path_prefix}/0')
    assert response.status_code == 404
    assert 'Seat ID 0 does not exist' in response.json()['detail']

    response = client.put(
        f'{path_prefix}/{seat.seat_id}',
        json={'seat_ip': {'destination_id': 0}},
    )
    assert response.status_code == 404
    assert 'Destination ID 0 does not exist' in response.json()['detail']


def test_replace_seat_no_ownership(
    client: TestClient[Litestar],
    seat: Seat,
    destination_ip: Destination,
):
    response = client.put(
        f'{path_prefix}/{seat.seat_id}',
        json={'seat_ip': {'destination_id': destination_ip.destination_id}},
    )
    assert response.status_code == 400
    assert (
        f'Destination ID {destination_ip.destination_id} belongs to a different'
        f' host than host ID {seat.host_id}'
    ) in response.json()['detail']


def test_replace_seat_destination_hostless_node(
    client: TestClient[Litestar], seat_no_host: Seat, destination_ip: Destination
):
    seat = seat_no_host
    response = client.put(
        f'{path_prefix}/{seat.seat_id}',
        json={
            'seat_ip': {
                'destination_id': destination_ip.destination_id,
                'port_number': 34,
            }
        },
    )
    assert response.status_code == 400
    assert (
        'A destination cannot be associated with a seat when the node is not on a host.'
    ) == response.json()['detail']


def test_replace_seat_validation(client: TestClient[Litestar]):
    response = client.put(f'{path_prefix}/{SEAT_ID_MAX + 1}')
    assert response.status_code == 400
    assert f'<= {SEAT_ID_MAX}' in response.json()['extra'][0]['message']

    response = client.put(
        f'{path_prefix}/0',
        json={'seat_ip': {'destination_id': DESTINATION_ID_MAX + 1}},
    )
    assert response.status_code == 400
    assert f'<= {DESTINATION_ID_MAX}' in response.json()['extra'][0]['message']

    response = client.put(
        f'{path_prefix}/0',
        json={'seat_ip': {'port_number': PORT_NUMBER_MAX + 1}},
    )
    assert response.status_code == 400
    assert f'<= {PORT_NUMBER_MAX}' in response.json()['extra'][0]['message']


def test_delete_seat(client: TestClient[Litestar], seat: Seat, seat_ip: SeatIp):
    for s in [seat, seat_ip.seat]:
        response = client.delete(f'{path_prefix}/{s.seat_id}')
        assert response.status_code == 204
        # The record was deleted, so trying to delete again should error
        response = client.delete(f'{path_prefix}/{s.seat_id}')
        assert response.status_code == 404
        assert f'Seat ID {s.seat_id} does not exist' in response.json()['detail']


def test_delete_seat_validation(client: TestClient[Litestar]):
    # seat_id out of range
    response = client.delete(f'{path_prefix}/{SEAT_ID_MAX + 1}')
    assert response.status_code == 400
    assert f'<= {SEAT_ID_MAX}' in response.json()['extra'][0]['message']

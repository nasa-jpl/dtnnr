from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

from app.api.v1.induct.schemas import (
    DuctNameTagEnum,
    InductSchema,
    process_destination_value,
    to_induct_schema,
)
from app.api.v1.induct.views import cli_p_name_dict
from app.api.v1.link.schemas import to_link_schema
from app.api.v1.seat.schemas import to_seat_without_node_id_schema
from app.config import API_V1_PATH, MAX_PAGE_SIZE
from app.fields import (
    CL_PROTOCOL_ID_MAX,
    DESTINATION_ID_MAX,
    INDUCT_ID_MAX,
    LINK_ID_MAX,
    PORT_NUMBER_MAX,
    SEAT_ID_MAX,
)
from app.models import (
    CommDirectionEnumInternal,
    cli_command_with_required_protocol_name,
    no_duct_name_known_cli_not_ip,
)
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

    from app.models import ClProtocol, Destination, Induct, InductIp, Link, Seat

decoder = msgspec.json.Decoder(type=InductSchema, strict=False)
path_prefix = f'{API_V1_PATH}/inducts'


def test_get_induct(client: TestClient[Litestar], induct: Induct):
    response = client.get(f'{path_prefix}/{induct.induct_id}')
    assert response.status_code == 200
    content = decoder.decode(response.content)
    content.cl_protocol.cl_protocol_class = set(
        c.value for c in content.cl_protocol.cl_protocol_class
    )
    x = to_induct_schema(induct)
    x.cl_protocol.cl_protocol_class = set(x.cl_protocol.cl_protocol_class)
    assert content == x


def test_get_induct_not_found(client: TestClient[Litestar], induct: Induct):
    response = client.get(f'{path_prefix}/{induct.induct_id + 1}')
    assert response.status_code == 404
    assert f'ID {induct.induct_id + 1} does not exist' in response.json()['detail']


def test_get_induct_validation(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/{INDUCT_ID_MAX + 1}')
    assert response.status_code == 400
    assert f'<= {INDUCT_ID_MAX}' in response.json()['extra'][0]['message']


def test_list_induct_links(client: TestClient[Litestar], induct_with_links: Induct):
    induct = induct_with_links
    items = collect_paginated_data(
        client, f'{path_prefix}/{induct.induct_id}/links', MAX_PAGE_SIZE
    )
    for l in induct.links:
        assert to_link_schema(l, with_host=False).to_dict() in items


def test_list_induct_links_pagination(
    client: TestClient[Litestar], induct_max_and_one_links: Induct
):
    induct = induct_max_and_one_links
    items = collect_paginated_data(client, f'{path_prefix}/{induct.induct_id}/links', 1)
    for l in induct.links:
        assert to_link_schema(l, with_host=False).to_dict() in items

    params = {'max_page_size': 1, 'page_token': 'last'}
    response = client.get(f'{path_prefix}/{induct.induct_id}/links', params=params)
    assert response.status_code == 200
    assert len(response.json()['items']) == params['max_page_size']
    assert response.json().get('prev_page_token') is not None
    assert response.json().get('next_page_token') is None
    assert items[-1] == response.json()['items'][0]


def test_list_induct_links_page_size(
    client: TestClient[Litestar], induct_max_and_one_links: Induct
):
    induct = induct_max_and_one_links
    check_page_size(client, f'{path_prefix}/{induct.induct_id}/links')


def test_list_induct_links_invalid_page_token(
    client: TestClient[Litestar], induct_max_and_one_links: Induct, induct: Induct
):
    other_induct_id = induct.induct_id
    induct = induct_max_and_one_links
    check_invalid_page_token_different_url(
        client,
        f'{path_prefix}/{induct.induct_id}/links',
        f'{path_prefix}/{other_induct_id}/links',
    )


def test_list_induct_links_not_found(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/0/links')
    assert response.status_code == 404
    assert 'ID 0 does not exist' in response.json()['detail']


def test_list_induct_links_validation(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/{INDUCT_ID_MAX + 1}/links')
    assert response.status_code == 400
    assert f'<= {INDUCT_ID_MAX}' in response.json()['extra'][0]['message']

    check_paginated_request_validation(client, f'{path_prefix}/0/links')


def test_replace_induct_links(
    client: TestClient[Litestar],
    induct_with_link_on_host_with_links: Induct,
    session: Session,
):
    induct = induct_with_link_on_host_with_links
    old_links = induct.links
    host = induct.node.host
    response = client.put(
        f'{path_prefix}/{induct.induct_id}/links', json=[l.link_id for l in host.links]
    )
    assert response.status_code == 204
    session.refresh(induct)
    assert induct.links != old_links
    assert induct.links == host.links


def test_replace_induct_links_empty(
    client: TestClient[Litestar],
    induct_with_links: Induct,
    session: Session,
):
    induct = induct_with_links
    response = client.put(f'{path_prefix}/{induct.induct_id}/links', json=[])
    assert response.status_code == 204
    session.refresh(induct)
    assert not induct.links


def test_replace_induct_links_duplicate_ids(
    client: TestClient[Litestar],
    induct_with_link_on_host_with_links: Induct,
    session: Session,
):
    induct = induct_with_link_on_host_with_links
    host = induct.node.host
    link = host.links[0]
    response = client.put(
        f'{path_prefix}/{induct.induct_id}/links',
        json=[link.link_id, str(link.link_id)] * 2,
    )
    assert response.status_code == 204
    session.refresh(induct)
    assert len(induct.links) == 1
    assert induct.links[0] == link


def test_replace_induct_links_not_found(client: TestClient[Litestar]):
    response = client.put(f'{path_prefix}/0/links', json=[])
    assert response.status_code == 404
    assert 'Induct ID 0 does not exist' in response.json()['detail']


def test_replace_induct_links_no_host(
    client: TestClient[Litestar],
    induct_null_type_no_host: Induct,
    links_not_simplex_outgoing: list[Link],
):
    induct = induct_null_type_no_host
    response = client.put(
        f'{path_prefix}/{induct.induct_id}/links',
        json=[l.link_id for l in links_not_simplex_outgoing],
    )
    assert response.status_code == 400
    assert (
        f'node ID {induct.node_id} is not associated with a host'
        in response.json()['detail']
    )


def test_replace_induct_links_no_host_clear(
    client: TestClient[Litestar], induct_null_type_no_host: Induct, session: Session
):
    induct = induct_null_type_no_host
    response = client.put(f'{path_prefix}/{induct.induct_id}/links', json=[])
    assert response.status_code == 204
    session.refresh(induct)
    assert not induct.links


def test_replace_induct_links_ltp(
    client: TestClient[Litestar],
    induct_ltp_on_host_with_links: Induct,
):
    induct = induct_ltp_on_host_with_links
    host = induct.node.host
    response = client.put(
        f'{path_prefix}/{induct.induct_id}/links', json=[l.link_id for l in host.links]
    )
    assert response.status_code == 400
    assert (
        'LTP inducts cannot directly associate with links' in response.json()['detail']
    )


def test_replace_induct_links_ltp_no_host_clear(
    client: TestClient[Litestar], induct_ltp_no_host: Induct, session: Session
):
    induct = induct_ltp_no_host
    response = client.put(f'{path_prefix}/{induct.induct_id}/links', json=[])
    assert response.status_code == 204
    session.refresh(induct)
    assert not induct.links


def test_replace_induct_links_wrong_host(
    client: TestClient[Litestar],
    induct_null_type: Induct,
    links_not_simplex_outgoing: list[Link],
):
    induct = induct_null_type
    # 0 should be unused by fixtures
    ids = [l.link_id for l in links_not_simplex_outgoing] + [0]
    response = client.put(f'{path_prefix}/{induct.induct_id}/links', json=ids)
    assert response.status_code == 400
    assert f'not associated with host ID {induct.host_id}' in response.json()['detail']
    assert response.json()['extra'] == [str(i) for i in sorted(ids)]


def test_replace_induct_links_wrong_direction(
    client: TestClient[Litestar],
    induct_null_type_on_host_with_links_simplex_outgoing_etc: Induct,
):
    induct = induct_null_type_on_host_with_links_simplex_outgoing_etc
    links = induct.node.host.links
    ids = [
        l.link_id for l in links if l.direction == CommDirectionEnumInternal.SIMPLEX_OUT
    ]
    response = client.put(f'{path_prefix}/{induct.induct_id}/links', json=ids)
    assert response.status_code == 400
    assert (
        f"direction '{CommDirectionEnumInternal.SIMPLEX_OUT.value}'"
        in response.json()['detail']
    )
    assert response.json()['extra'] == [str(i) for i in sorted(ids)]


def test_replace_induct_links_required_reqbody(client: TestClient[Litestar]):
    for response in [
        # Missing request body
        client.put(f'{path_prefix}/0/links'),
        # Empty request body
        client.put(f'{path_prefix}/0/links', content=b''),
    ]:
        assert response.status_code == 400
        assert 'Expected non-empty request' in response.json()['extra'][0]['message']


def test_replace_induct_links_null_reqbody(client: TestClient[Litestar]):
    # `null` is distinct from a missing / empty request body
    response = client.put(f'{path_prefix}/0/links', content=b'null')
    assert response.status_code == 400
    assert 'Expected `array`, got `null`' in response.json()['extra'][0]['message']


def test_replace_induct_links_validation(client: TestClient[Litestar]):
    # link_id out of range
    response = client.put(f'{path_prefix}/0/links', json=[1, 2, 3, LINK_ID_MAX + 1, 4])
    assert response.status_code == 400
    assert f'Expected `int` <= {LINK_ID_MAX}' == response.json()['extra'][0]['message']
    # TODO: check if it reports the right index after my PR is approved

    # induct_id out of range
    response = client.put(f'{path_prefix}/{INDUCT_ID_MAX + 1}/links', json=[])
    assert response.status_code == 400
    assert (
        f'Expected `int` <= {INDUCT_ID_MAX}' == response.json()['extra'][0]['message']
    )


def test_list_induct_seats(client: TestClient[Litestar], induct_with_seats: Induct):
    induct = induct_with_seats
    items = collect_paginated_data(
        client, f'{path_prefix}/{induct.induct_id}/seats', MAX_PAGE_SIZE
    )
    for s in induct.seats:
        assert to_seat_without_node_id_schema(s).to_dict() in items


def test_list_induct_seats_pagination(
    client: TestClient[Litestar], induct_max_and_one_seats: Induct
):
    induct = induct_max_and_one_seats
    items = collect_paginated_data(client, f'{path_prefix}/{induct.induct_id}/seats', 1)
    for s in induct.seats:
        assert to_seat_without_node_id_schema(s).to_dict() in items

    params = {'max_page_size': 1, 'page_token': 'last'}
    response = client.get(f'{path_prefix}/{induct.induct_id}/seats', params=params)
    assert response.status_code == 200
    assert len(response.json()['items']) == params['max_page_size']
    assert response.json().get('prev_page_token') is not None
    assert response.json().get('next_page_token') is None
    assert items[-1] == response.json()['items'][0]


def test_list_induct_seats_page_size(
    client: TestClient[Litestar], induct_max_and_one_seats: Induct
):
    induct = induct_max_and_one_seats
    check_page_size(client, f'{path_prefix}/{induct.induct_id}/seats')


def test_list_induct_seats_invalid_page_token(
    client: TestClient[Litestar], induct_max_and_one_seats: Induct, induct: Induct
):
    other_induct_id = induct.induct_id
    induct = induct_max_and_one_seats
    check_invalid_page_token_different_url(
        client,
        f'{path_prefix}/{induct.induct_id}/seats',
        f'{path_prefix}/{other_induct_id}/seats',
    )


def test_list_induct_seats_not_found(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/0/seats')
    assert response.status_code == 404
    assert 'ID 0 does not exist' in response.json()['detail']


def test_list_induct_seats_validation(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/{INDUCT_ID_MAX + 1}/seats')
    assert response.status_code == 400
    assert f'<= {INDUCT_ID_MAX}' in response.json()['extra'][0]['message']

    check_paginated_request_validation(client, f'{path_prefix}/0/seats')


def test_replace_induct_seats(
    client: TestClient[Litestar],
    induct_with_seat_on_node_with_seats: Induct,
    session: Session,
):
    induct = induct_with_seat_on_node_with_seats
    old_seats = induct.seats
    node = induct.node
    response = client.put(
        f'{path_prefix}/{induct.induct_id}/seats', json=[s.seat_id for s in node.seats]
    )
    assert response.status_code == 204
    session.refresh(induct)
    assert induct.seats != old_seats
    assert induct.seats == node.seats


def test_replace_induct_seats_empty(
    client: TestClient[Litestar],
    induct_with_seats: Induct,
    session: Session,
):
    induct = induct_with_seats
    response = client.put(f'{path_prefix}/{induct.induct_id}/seats', json=[])
    assert response.status_code == 204
    session.refresh(induct)
    assert not induct.seats


def test_replace_induct_seats_duplicate_ids(
    client: TestClient[Litestar],
    induct_with_seat_on_node_with_seats: Induct,
    session: Session,
):
    induct = induct_with_seat_on_node_with_seats
    node = induct.node
    seat = node.seats[0]
    response = client.put(
        f'{path_prefix}/{induct.induct_id}/seats',
        json=[seat.seat_id, str(seat.seat_id)] * 2,
    )
    assert response.status_code == 204
    session.refresh(induct)
    assert len(induct.seats) == 1
    assert induct.seats[0] == seat


def test_replace_induct_seats_not_found(client: TestClient[Litestar]):
    response = client.put(f'{path_prefix}/0/seats', json=[])
    assert response.status_code == 404
    assert 'Induct ID 0 does not exist' in response.json()['detail']


def test_replace_induct_seats_not_ltp(
    client: TestClient[Litestar], induct_not_ltp_on_node_with_seats: Induct
):
    induct = induct_not_ltp_on_node_with_seats
    node = induct.node
    response = client.put(
        f'{path_prefix}/{induct.induct_id}/seats', json=[s.seat_id for s in node.seats]
    )
    assert response.status_code == 400
    assert f'ID {induct.induct_id} does not use LTP' in response.json()['detail']


def test_replace_induct_seats_not_ltp_clear(
    client: TestClient[Litestar],
    induct_not_ltp_on_node_with_seats: Induct,
    session: Session,
):
    induct = induct_not_ltp_on_node_with_seats
    response = client.put(f'{path_prefix}/{induct.induct_id}/seats', json=[])
    assert response.status_code == 204
    session.refresh(induct)
    assert not induct.seats


def test_replace_induct_seats_wrong_node(
    client: TestClient[Litestar], induct_with_seats: Induct, seats: list[Seat]
):
    induct = induct_with_seats
    ids_same_node = [s.seat_id for s in induct.node.seats]
    # 0 should be unused by fixtures
    ids_other = [s.seat_id for s in seats] + [0]
    response = client.put(
        f'{path_prefix}/{induct.induct_id}/seats', json=ids_same_node + ids_other
    )
    assert response.status_code == 400
    assert f'not associated with node ID {induct.node_id}' in response.json()['detail']
    assert response.json()['extra'] == [str(i) for i in sorted(ids_other)]


def test_replace_induct_seats_required_reqbody(client: TestClient[Litestar]):
    for response in [
        # Missing request body
        client.put(f'{path_prefix}/0/seats'),
        # Empty request body
        client.put(f'{path_prefix}/0/seats', content=b''),
    ]:
        assert response.status_code == 400
        assert 'Expected non-empty request' in response.json()['extra'][0]['message']


def test_replace_induct_seats_null_reqbody(client: TestClient[Litestar]):
    # `null` is distinct from a missing / empty request body
    response = client.put(f'{path_prefix}/0/seats', content=b'null')
    assert response.status_code == 400
    assert 'Expected `array`, got `null`' in response.json()['extra'][0]['message']


def test_replace_induct_seats_validation(client: TestClient[Litestar]):
    # seat_id out of range
    response = client.put(f'{path_prefix}/0/seats', json=[1, 2, 3, SEAT_ID_MAX + 1, 4])
    assert response.status_code == 400
    assert f'Expected `int` <= {SEAT_ID_MAX}' == response.json()['extra'][0]['message']
    # TODO: check if it reports the right index after my PR is approved

    # induct_id out of range
    response = client.put(f'{path_prefix}/{INDUCT_ID_MAX + 1}/seats', json=[])
    assert response.status_code == 400
    assert (
        f'Expected `int` <= {INDUCT_ID_MAX}' == response.json()['extra'][0]['message']
    )


def test_replace_induct_plain_to_plain(
    client: TestClient[Litestar], induct_null_type: Induct
):
    induct = induct_null_type
    duct_name = 'foo'
    cli_command = 'bar'
    uses_ltp = True
    response = client.put(
        f'{path_prefix}/{induct.induct_id}',
        json={
            'cl_protocol_id': None,
            'duct_name': duct_name,
            'cli_command': cli_command,
            'uses_ltp': uses_ltp,
        },
    )
    assert response.status_code == 200
    assert response.json()['induct_id'] == str(induct.induct_id)
    assert response.json()['cl_protocol'] is None
    assert response.json()['duct_name']['value'] == duct_name
    assert response.json()['duct_name']['type'] == DuctNameTagEnum.PLAIN
    assert response.json()['cli_command'] == cli_command
    assert response.json()['uses_ltp'] == uses_ltp


def test_replace_induct_ip_to_ip(client: TestClient[Litestar], induct_ip: InductIp):
    induct = induct_ip.induct
    host = induct.node.host
    dest = host.destinations[0]
    cli_command = 'bar'
    uses_ltp = True
    port_number = 34
    response = client.put(
        f'{path_prefix}/{induct.induct_id}',
        json={
            'cl_protocol_id': None,
            'duct_name': {
                'type': DuctNameTagEnum.IP,
                'destination_id': dest.destination_id,
                'port_number': port_number,
            },
            'cli_command': cli_command,
            'uses_ltp': uses_ltp,
        },
    )
    assert response.status_code == 200
    assert response.json()['induct_id'] == str(induct.induct_id)
    assert response.json()['cl_protocol'] is None
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


def test_replace_induct_plain_to_ip(
    client: TestClient[Litestar], induct_null_type: Induct
):
    induct = induct_null_type
    host = induct.node.host
    dest = host.destinations[0]
    cli_command = 'bar'
    uses_ltp = True
    port_number = 34
    response = client.put(
        f'{path_prefix}/{induct.induct_id}',
        json={
            'cl_protocol_id': None,
            'duct_name': {
                'type': DuctNameTagEnum.IP,
                'destination_id': dest.destination_id,
                'port_number': port_number,
            },
            'cli_command': cli_command,
            'uses_ltp': uses_ltp,
        },
    )
    assert response.status_code == 200
    assert response.json()['induct_id'] == str(induct.induct_id)
    assert response.json()['cl_protocol'] is None
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


def test_replace_induct_ip_to_plain(client: TestClient[Litestar], induct_ip: InductIp):
    induct = induct_ip.induct
    duct_name = 'foo'
    cli_command = 'bar'
    uses_ltp = True
    response = client.put(
        f'{path_prefix}/{induct.induct_id}',
        json={
            'cl_protocol_id': None,
            'duct_name': duct_name,
            'cli_command': cli_command,
            'uses_ltp': uses_ltp,
        },
    )
    assert response.status_code == 200
    assert response.json()['induct_id'] == str(induct.induct_id)
    assert response.json()['cl_protocol'] is None
    assert response.json()['duct_name']['value'] == duct_name
    assert response.json()['duct_name']['type'] == DuctNameTagEnum.PLAIN
    assert response.json()['cli_command'] == cli_command
    assert response.json()['uses_ltp'] == uses_ltp


def test_replace_induct_defaults(client: TestClient[Litestar], induct: Induct):
    for response in [
        client.put(f'{path_prefix}/{induct.induct_id}'),
        client.put(f'{path_prefix}/{induct.induct_id}', content=b''),
        client.put(f'{path_prefix}/{induct.induct_id}', json={}),
    ]:
        assert response.status_code == 200
        assert response.json()['induct_id'] == str(induct.induct_id)
        assert response.json()['cl_protocol'] is None
        assert response.json()['duct_name']['value'] is None
        assert response.json()['duct_name']['type'] == DuctNameTagEnum.PLAIN
        assert response.json()['cli_command'] is None
        assert response.json()['uses_ltp'] == False

    response = client.put(f'{path_prefix}/{induct.induct_id}', json={'duct_name': {}})
    assert response.status_code == 200
    assert response.json()['induct_id'] == str(induct.induct_id)
    assert response.json()['cl_protocol'] is None
    assert response.json()['duct_name']['value'] is None
    assert response.json()['duct_name']['type'] == DuctNameTagEnum.IP
    assert response.json()['duct_name']['destination'] is None
    assert response.json()['duct_name']['port_number'] is None
    assert response.json()['cli_command'] is None
    assert response.json()['uses_ltp'] == False


def test_replace_induct_not_found(client: TestClient[Litestar], induct: Induct):
    response = client.put(f'{path_prefix}/0')
    assert response.status_code == 404
    assert 'Induct ID 0 does not exist' in response.json()['detail']

    response = client.put(
        f'{path_prefix}/{induct.induct_id}', json={'cl_protocol_id': 0}
    )
    assert response.status_code == 404
    assert 'CL protocol ID 0 does not exist' in response.json()['detail']

    response = client.put(
        f'{path_prefix}/{induct.induct_id}',
        json={'duct_name': {'type': DuctNameTagEnum.IP, 'destination_id': 0}},
    )
    assert response.status_code == 404
    assert 'Destination ID 0 does not exist' in response.json()['detail']


def test_replace_induct_no_ownership(
    client: TestClient[Litestar],
    induct: Induct,
    cl_protocol: ClProtocol,
    destination_ip: Destination,
):
    url = f'{path_prefix}/{induct.induct_id}'
    response = client.put(url, json={'cl_protocol_id': cl_protocol.cl_protocol_id})
    assert response.status_code == 400
    assert (
        f'CL protocol ID {cl_protocol.cl_protocol_id} does not belong to node ID'
        f' {induct.node_id}'
    ) == response.json()['detail']

    response = client.put(
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
        f' host than host ID {induct.host_id}'
    ) in response.json()['detail']


def test_replace_induct_destination_hostless_node(
    client: TestClient[Litestar],
    induct_null_type_no_host: Induct,
    destination_ip: Destination,
):
    induct = induct_null_type_no_host
    dest = destination_ip
    response = client.put(
        f'{path_prefix}/{induct.induct_id}',
        json={
            'duct_name': {
                'type': DuctNameTagEnum.IP,
                'destination_id': dest.destination_id,
                'port_number': 34,
            }
        },
    )
    assert response.status_code == 400
    assert (
        'A destination cannot be associated with an induct when the node is not'
        ' on a host.'
    ) == response.json()['detail']


def test_replace_induct_wrong_cl_protocol_for_cli(
    client: TestClient[Litestar], induct_null_type: Induct
):
    for cli, p_name in cli_command_with_required_protocol_name:
        r = client.put(
            f'{path_prefix}/{induct_null_type.induct_id}',
            json={
                'cl_protocol_id': induct_null_type.cl_protocol_id,
                'cli_command': cli,
            },
        )
        assert r.status_code == 400
        assert (
            f"`cli_command` ('{cli}') must be associated with an induct that"
            f" uses a `cl_protocol_name` of '{p_name}'"
        ) == r.json()['detail']


def test_replace_induct_wrong_uses_ltp_for_cli(
    client: TestClient[Litestar],
    induct_null_type_with_cl_protocols_for_known_cli: Induct,
):
    induct = induct_null_type_with_cl_protocols_for_known_cli
    node = induct.node
    cl_protocol_name_to_id = {
        p.cl_protocol_name: p.cl_protocol_id for p in node.cl_protocols
    }

    for cli, p_name in cli_command_with_required_protocol_name:
        r = client.put(
            f'{path_prefix}/{induct.induct_id}',
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


def test_replace_induct_no_duct_name_known_cli(
    client: TestClient[Litestar],
    induct_null_type_with_cl_protocols_for_known_cli: Induct,
):
    induct = induct_null_type_with_cl_protocols_for_known_cli
    node = induct.node
    cl_protocol_name_to_id = {
        p.cl_protocol_name: p.cl_protocol_id for p in node.cl_protocols
    }

    for cli in no_duct_name_known_cli_not_ip:
        p_name = cli_p_name_dict[cli]
        r = client.put(
            f'{path_prefix}/{induct.induct_id}',
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


def test_replace_induct_brsccla_no_ip(
    client: TestClient[Litestar],
    induct_null_type_with_cl_protocols_for_known_cli: Induct,
):
    induct = induct_null_type_with_cl_protocols_for_known_cli
    node = induct.node
    cl_protocol_name_to_id = {
        p.cl_protocol_name: p.cl_protocol_id for p in node.cl_protocols
    }
    cli = 'brsccla'
    p_name = cli_p_name_dict[cli]
    r = client.put(
        f'{path_prefix}/{induct.induct_id}',
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


def test_replace_induct_change_uses_ltp(
    client: TestClient[Litestar],
    induct_with_links: Induct,
    induct_with_seats: Induct,
):
    response = client.put(
        f'{path_prefix}/{induct_with_links.induct_id}', json={'uses_ltp': True}
    )
    assert response.status_code == 400
    assert (
        'Cannot change `uses_ltp` from false to true when the induct is'
        ' associated with links. `extra` contains link IDs of links associated'
        ' with the induct'
    ) in response.json()['detail']
    assert [
        str(i) for i in sorted([l.link_id for l in induct_with_links.links])
    ] == response.json()['extra']

    response = client.put(
        f'{path_prefix}/{induct_with_seats.induct_id}', json={'uses_ltp': False}
    )
    assert response.status_code == 400
    assert (
        'Cannot change `uses_ltp` from true to false when the induct is'
        ' associated with seats. `extra` contains seat IDs of seats associated'
        ' with the induct'
    ) in response.json()['detail']
    assert [
        str(i) for i in sorted([s.seat_id for s in induct_with_seats.seats])
    ] == response.json()['extra']


def test_replace_induct_validation(client: TestClient[Litestar]):
    response = client.put(f'{path_prefix}/{INDUCT_ID_MAX + 1}')
    assert response.status_code == 400
    assert f'<= {INDUCT_ID_MAX}' in response.json()['extra'][0]['message']

    response = client.put(
        f'{path_prefix}/0', json={'cl_protocol_id': CL_PROTOCOL_ID_MAX + 1}
    )
    assert response.status_code == 400
    assert f'<= {CL_PROTOCOL_ID_MAX}' in response.json()['extra'][0]['message']

    response = client.put(
        f'{path_prefix}/0',
        json={'duct_name': {'destination_id': DESTINATION_ID_MAX + 1}},
    )
    assert response.status_code == 400
    assert f'<= {DESTINATION_ID_MAX}' in response.json()['extra'][0]['message']

    response = client.put(
        f'{path_prefix}/0',
        json={'duct_name': {'port_number': PORT_NUMBER_MAX + 1}},
    )
    assert response.status_code == 400
    assert f'<= {PORT_NUMBER_MAX}' in response.json()['extra'][0]['message']


def test_delete_induct(
    client: TestClient[Litestar], induct: Induct, induct_ip: InductIp
):
    for d in [induct, induct_ip.induct]:
        response = client.delete(f'{path_prefix}/{d.induct_id}')
        assert response.status_code == 204
        # The record was deleted, so trying to delete again should error
        response = client.delete(f'{path_prefix}/{d.induct_id}')
        assert response.status_code == 404
        assert f'duct ID {d.induct_id} does not exist' in response.json()['detail']


def test_delete_induct_validation(client: TestClient[Litestar]):
    # induct_id out of range
    response = client.delete(f'{path_prefix}/{INDUCT_ID_MAX + 1}')
    assert response.status_code == 400
    assert f'<= {INDUCT_ID_MAX}' in response.json()['extra'][0]['message']

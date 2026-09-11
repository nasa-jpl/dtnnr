from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

from app.api.v1.link.schemas import LinkSchema, render_direction, to_link_schema
from app.config import API_V1_PATH
from app.fields import BAND_ID_MAX, LINK_ID_MAX, UNDERLYING_COMMUNICATION_SERVICE_ID_MAX
from app.models import CommDirectionEnumInternal

if TYPE_CHECKING:
    from litestar import Litestar
    from litestar.testing import TestClient
    from sqlalchemy.orm import Session

    from app.models import (
        Band,
        Link,
        LinkRf,
        UnderlyingCommunicationService,
    )

decoder = msgspec.json.Decoder(type=LinkSchema, strict=False)
path_prefix = f'{API_V1_PATH}/links'


def test_get_link(client: TestClient[Litestar], link: Link):
    response = client.get(f'{path_prefix}/{link.link_id}')
    assert response.status_code == 200
    assert decoder.decode(response.content) == to_link_schema(link)


def test_get_link_includes_service_name_and_abbreviation(
    client: TestClient[Litestar], link_with_underlying_communication_service: Link
):
    link = link_with_underlying_communication_service
    service = link.underlying_communication_services[0]
    response = client.get(f'{path_prefix}/{link.link_id}')

    assert response.status_code == 200
    representation = response.json()['underlying_communication_services'][0]
    assert representation['underlying_communication_service_name'] == (
        service.underlying_communication_service_name
    )
    assert representation['underlying_communication_service_abbreviation'] == (
        service.underlying_communication_service_abbreviation
    )


def test_get_link_null_direction(
    client: TestClient[Litestar], link_null_direction: Link
):
    link = link_null_direction
    response = client.get(f'{path_prefix}/{link.link_id}')
    assert response.status_code == 200
    assert response.json()['direction'] is None


def test_get_link_not_found(client: TestClient[Litestar], link: Link):
    response = client.get(f'{path_prefix}/{link.link_id + 1}')
    assert response.status_code == 404
    assert f'ID {link.link_id + 1} does not exist' in response.json()['detail']


def test_get_link_validation(client: TestClient[Litestar]):
    response = client.get(f'{path_prefix}/{LINK_ID_MAX * 2}')
    assert response.status_code == 400
    assert f'<= {LINK_ID_MAX}' in response.json()['extra'][0]['message']


def test_update_link(
    client: TestClient[Litestar],
    link: Link,
    underlying_communication_services: list[UnderlyingCommunicationService],
    band: Band,
    session: Session,
):
    response = client.patch(
        f'{path_prefix}/{link.link_id}',
        json={
            'direction': 'Full-duplex',
            'underlying_communication_service_ids': [
                s.underlying_communication_service_id
                for s in underlying_communication_services
            ],
            'link_rf': {'band_id': band.band_id},
        },
    )
    assert response.status_code == 200
    session.refresh(link)
    content = decoder.decode(response.content)
    assert content == to_link_schema(link)


def test_update_link_null_link_rf(
    client: TestClient[Litestar], link: Link, link_rf: LinkRf, session: Session
):
    # `link` doesn't have a _rf child
    response = client.patch(f'{path_prefix}/{link.link_id}', json={'link_rf': None})
    assert response.status_code == 200
    session.refresh(link)
    content = decoder.decode(response.content)
    assert content == to_link_schema(link)
    assert link.link_rf is None

    # Test when a link does have a _rf child
    p_link = link_rf.link
    response = client.patch(f'{path_prefix}/{p_link.link_id}', json={'link_rf': None})
    assert response.status_code == 200
    session.commit()
    content = decoder.decode(response.content)
    assert content == to_link_schema(p_link)
    assert p_link.link_rf is None


def test_update_link_null_band(
    client: TestClient[Litestar], link: Link, link_rf: LinkRf, session: Session
):
    # With no current _rf child, a new record is created
    assert link.link_rf is None
    response = client.patch(
        f'{path_prefix}/{link.link_id}', json={'link_rf': {'band_id': None}}
    )
    assert response.status_code == 200
    session.commit()
    content = decoder.decode(response.content)
    assert content == to_link_schema(link)
    assert link.link_rf is not None
    assert link.link_rf.band_id is None

    # Test when a link already has _rf child
    response = client.patch(
        f'{path_prefix}/{link_rf.link_id}', json={'link_rf': {'band_id': None}}
    )
    assert response.status_code == 200
    session.commit()
    content = decoder.decode(response.content)
    assert content == to_link_schema(link_rf.link)
    assert link_rf.band_id is None


def test_update_link_empty_underlying_communication_services(
    client: TestClient[Litestar],
    link_with_underlying_communication_service: Link,
    session: Session,
):
    link = link_with_underlying_communication_service
    assert link.underlying_communication_services
    response = client.patch(
        f'{path_prefix}/{link.link_id}',
        json={'underlying_communication_service_ids': []},
    )
    assert response.status_code == 200
    session.commit()
    content = decoder.decode(response.content)
    assert content == to_link_schema(link)
    assert not link.underlying_communication_services


def test_update_link_unique_service_ids(
    client: TestClient[Litestar],
    link_with_underlying_communication_service: Link,
    underlying_communication_services: list[UnderlyingCommunicationService],
    session: Session,
):
    link = link_with_underlying_communication_service
    old_ucs = link.underlying_communication_services
    ids = [
        s.underlying_communication_service_id for s in underlying_communication_services
    ]
    ids_original_len = len(ids)
    ids.extend(ids[::-1])
    assert len(ids) != ids_original_len
    response = client.patch(
        f'{path_prefix}/{link.link_id}',
        json={'underlying_communication_service_ids': ids},
    )
    assert response.status_code == 200
    assert ids_original_len == len(response.json()['underlying_communication_services'])
    session.commit()
    content = decoder.decode(response.content)
    for s in old_ucs:
        assert s.underlying_communication_service_id not in [
            _s.underlying_communication_service_id
            for _s in content.underlying_communication_services
        ]


def test_update_link_null_direction(
    client: TestClient[Litestar], link_null_direction: Link, session: Session
):
    link = link_null_direction
    for response in [
        client.patch(
            f'{path_prefix}/{link.link_id}',
            json={'direction': None},
        ),
        client.patch(
            f'{path_prefix}/{link.link_id}',
            json={},  # direction is not set
        ),
    ]:
        assert response.status_code == 200
        session.refresh(link)
        assert link.direction == CommDirectionEnumInternal.N_A.value
        assert response.json()['direction'] is None


def test_update_link_no_change(
    client: TestClient[Litestar],
    link: Link,
    link_with_underlying_communication_service: Link,
    link_rf: LinkRf,
    link_null_direction: Link,
):
    for l in [
        link,
        link_with_underlying_communication_service,
        link_rf.link,
        link_null_direction,
    ]:
        old_content = to_link_schema(l)
        for response in [
            # Missing request body
            client.patch(f'{path_prefix}/{l.link_id}'),
            # Empty request body
            client.patch(f'{path_prefix}/{l.link_id}', content=b''),
            # Empty object
            client.patch(f'{path_prefix}/{l.link_id}', json={}),
            # Same properties
            client.patch(
                f'{path_prefix}/{l.link_id}',
                json={
                    'direction': render_direction(l.direction),
                    'underlying_communication_service_ids': [
                        s.underlying_communication_service_id
                        for s in l.underlying_communication_services
                    ],
                    'link_rf': None
                    if l.link_rf is None
                    else {'band_id': l.link_rf.band_id},
                },
            ),
            # Empty object for link_rf
            client.patch(f'{path_prefix}/{l.link_id}', json={'link_rf': {}}),
        ]:
            assert response.status_code == 200
            assert old_content == decoder.decode(response.content)


def test_update_link_not_found(
    client: TestClient[Litestar],
    link: Link,
    underlying_communication_services: list[UnderlyingCommunicationService],
    band: Band,
):
    response = client.patch(f'{path_prefix}/{link.link_id + 1}')
    assert response.status_code == 404
    assert f'Link ID {link.link_id + 1} does not exist' in response.json()['detail']

    nums = [
        underlying_communication_services[-1].underlying_communication_service_id + 1
    ]
    nums.append(nums[-1] + 1)
    nums.append(nums[-1] + 2)
    response = client.patch(
        f'{path_prefix}/{link.link_id}',
        json={'underlying_communication_service_ids': nums},
    )
    assert response.status_code == 404
    for i in nums:
        assert str(i) in response.json()['extra']

    response = client.patch(
        f'{path_prefix}/{link.link_id}',
        json={'link_rf': {'band_id': band.band_id + 1}},
    )
    assert response.status_code == 404
    assert f'Band ID {band.band_id + 1} does not exist' in response.json()['detail']


def test_update_link_inducts_using_link(
    client: TestClient[Litestar], link_with_inducts: Link
):
    link = link_with_inducts
    response = client.patch(
        f'{path_prefix}/{link.link_id}',
        json={'direction': CommDirectionEnumInternal.SIMPLEX_OUT.value},
    )
    assert response.status_code == 400
    assert CommDirectionEnumInternal.SIMPLEX_OUT.value in response.json()['detail']
    for i in link.inducts:
        assert str(i.induct_id) in response.json()['extra']


def test_update_link_validation(client: TestClient[Litestar]):
    # link_id out of range
    response = client.patch(f'{path_prefix}/{LINK_ID_MAX * 2}')
    assert response.status_code == 400
    assert f'<= {LINK_ID_MAX}' in response.json()['extra'][0]['message']

    # Invalid direction
    response = client.patch(f'{path_prefix}/0', json={'direction': 'semiduplex'})
    assert response.status_code == 400
    assert 'Invalid enum value' in response.json()['extra'][0]['message']

    # Underlying comm service ID out of range
    response = client.patch(
        f'{path_prefix}/0',
        json={'underlying_communication_service_ids': [3, 2, -1, 0]},
    )
    assert response.status_code == 400
    assert '>= 0' in response.json()['extra'][0]['message']
    response = client.patch(
        f'{path_prefix}/0',
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
    response = client.patch(
        f'{path_prefix}/0', json={'link_rf': {'band_id': BAND_ID_MAX * 2}}
    )
    assert response.status_code == 400
    assert f'<= {BAND_ID_MAX}' in response.json()['extra'][0]['message']


def test_delete_link(
    client: TestClient[Litestar],
    link: Link,
    link_with_underlying_communication_service: Link,
    link_rf: LinkRf,
):
    for l in [link, link_with_underlying_communication_service, link_rf.link]:
        response = client.delete(f'{path_prefix}/{l.link_id}')
        assert response.status_code == 204
        # The record was deleted, so deleting again should error
        response = client.delete(f'{path_prefix}/{l.link_id}')
        assert response.status_code == 404
        assert f'ID {l.link_id} does not exist' in response.json()['detail']


def test_delete_link_validation(client: TestClient[Litestar]):
    # link_id out of range
    response = client.delete(f'{path_prefix}/{LINK_ID_MAX * 2}')
    assert response.status_code == 400
    assert f'<= {LINK_ID_MAX}' in response.json()['extra'][0]['message']

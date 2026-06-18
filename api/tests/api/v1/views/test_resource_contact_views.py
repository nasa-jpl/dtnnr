from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec
import pytest

from app.api.v1.contact.schemas import ContactSchema, to_contact_schema
from app.config import (
    API_V1_PATH,
    MAX_PAGE_SIZE,
)
from app.fields import (
    ALLOCATOR_ID_MAX,
    CONTACT_ID_MAX,
    HOST_ID_MAX,
    NODE_ID_MAX,
    OPERATOR_ID_MAX,
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
    from pytest import FixtureRequest
    from sqlalchemy.orm import Session

    from app.models import Allocator, Contact, Host, Node, Operator

    type ContactOwner = Allocator | Operator | Host | Node

contact_decoder = msgspec.json.Decoder(type=ContactSchema, strict=False)


@pytest.mark.parametrize(
    'resource_path_name,resource_id,resource_with_details',
    [
        ('allocators', 'allocator_id', 'allocator_with_details'),
        ('operators', 'operator_id', 'operator_with_details'),
        ('hosts', 'host_id', 'host_with_contacts'),
        ('nodes', 'node_id', 'node_with_contacts'),
    ],
)
def test_list_resource_contacts(
    client: TestClient[Litestar],
    resource_path_name: str,
    resource_id: str,
    resource_with_details: str,
    request: FixtureRequest,
):
    resource: ContactOwner = request.getfixturevalue(resource_with_details)
    items = collect_paginated_data(
        client,
        f'{API_V1_PATH}/{resource_path_name}/{getattr(resource, resource_id)}/contacts',
        MAX_PAGE_SIZE,
    )
    for c in resource.contacts:
        assert to_contact_schema(c).to_dict() in items


@pytest.mark.parametrize(
    'resource_path_name,resource_id,resource_max_contacts_and_one',
    [
        ('allocators', 'allocator_id', 'allocator_max_contacts_and_one'),
        ('operators', 'operator_id', 'operator_max_contacts_and_one'),
        ('hosts', 'host_id', 'host_max_contacts_and_one'),
        ('nodes', 'node_id', 'node_max_contacts_and_one'),
    ],
)
def test_list_resource_contacts_pagination(
    client: TestClient[Litestar],
    resource_path_name: str,
    resource_id: str,
    resource_max_contacts_and_one: str,
    request: FixtureRequest,
):
    resource: ContactOwner = request.getfixturevalue(resource_max_contacts_and_one)
    items = collect_paginated_data(
        client,
        f'{API_V1_PATH}/{resource_path_name}/{getattr(resource, resource_id)}/contacts',
        1,
    )
    for c in resource.contacts:
        assert to_contact_schema(c).to_dict() in items

    params = {'max_page_size': 1, 'page_token': 'last'}
    response = client.get(
        f'{API_V1_PATH}/{resource_path_name}/{getattr(resource, resource_id)}/contacts',
        params=params,
    )
    assert response.status_code == 200
    assert len(response.json()['items']) == params['max_page_size']
    assert response.json().get('prev_page_token') is not None
    assert response.json().get('next_page_token') is None
    assert items[-1] == response.json()['items'][0]


@pytest.mark.parametrize(
    'resource_path_name,resource_id,resource_max_contacts_and_one',
    [
        ('allocators', 'allocator_id', 'allocator_max_contacts_and_one'),
        ('operators', 'operator_id', 'operator_max_contacts_and_one'),
        ('hosts', 'host_id', 'host_max_contacts_and_one'),
        ('nodes', 'node_id', 'node_max_contacts_and_one'),
    ],
)
def test_list_resource_contacts_page_size(
    client: TestClient[Litestar],
    resource_path_name: str,
    resource_id: str,
    resource_max_contacts_and_one: str,
    request: FixtureRequest,
):
    resource: ContactOwner = request.getfixturevalue(resource_max_contacts_and_one)
    check_page_size(
        client,
        f'{API_V1_PATH}/{resource_path_name}/{getattr(resource, resource_id)}/contacts',
    )


@pytest.mark.parametrize(
    'resource_path_name,resource_id,resource_max_contacts_and_one,resource',
    [
        ('allocators', 'allocator_id', 'allocator_max_contacts_and_one', 'allocator'),
        ('operators', 'operator_id', 'operator_max_contacts_and_one', 'operator'),
        ('hosts', 'host_id', 'host_max_contacts_and_one', 'host'),
        ('nodes', 'node_id', 'node_max_contacts_and_one', 'node'),
    ],
)
def test_list_resource_contacts_invalid_page_token(
    client: TestClient[Litestar],
    resource_path_name: str,
    resource_id: str,
    resource_max_contacts_and_one: str,
    resource: str,
    request: FixtureRequest,
):
    id_1 = getattr(request.getfixturevalue(resource_max_contacts_and_one), resource_id)
    id_2 = getattr(request.getfixturevalue(resource), resource_id)
    check_invalid_page_token_different_url(
        client,
        f'{API_V1_PATH}/{resource_path_name}/{id_1}/contacts',
        f'{API_V1_PATH}/{resource_path_name}/{id_2}/contacts',
    )


@pytest.mark.parametrize(
    'resource_path_name,resource_id,resource',
    [
        ('allocators', 'allocator_id', 'allocator'),
        ('operators', 'operator_id', 'operator'),
        ('hosts', 'host_id', 'host'),
        ('nodes', 'node_id', 'node'),
    ],
)
def test_list_resource_contacts_not_found(
    client: TestClient[Litestar],
    resource_path_name: str,
    resource_id: str,
    resource: str,
    request: FixtureRequest,
):
    id = getattr(request.getfixturevalue(resource), resource_id) + 1
    response = client.get(f'{API_V1_PATH}/{resource_path_name}/{id}/contacts')
    assert response.status_code == 404
    assert (
        f'{resource.capitalize()} ID {id} does not exist' in response.json()['detail']
    )


@pytest.mark.parametrize(
    'resource_path_name,resource_id_max',
    [
        ('allocators', ALLOCATOR_ID_MAX),
        ('operators', OPERATOR_ID_MAX),
        ('hosts', HOST_ID_MAX),
        ('nodes', NODE_ID_MAX),
    ],
)
def test_list_resource_contacts_validation(
    client: TestClient[Litestar],
    resource_path_name: str,
    resource_id_max: int,
):
    response = client.get(
        f'{API_V1_PATH}/{resource_path_name}/{resource_id_max * 2}/contacts'
    )
    assert response.status_code == 400
    assert f'<= {resource_id_max}' in response.json()['extra'][0]['message']

    check_paginated_request_validation(
        client, f'{API_V1_PATH}/{resource_path_name}/0/contacts'
    )


@pytest.mark.parametrize(
    'resource_path_name,resource_id,resource',
    [
        ('allocators', 'allocator_id', 'allocator'),
        ('operators', 'operator_id', 'operator'),
        ('hosts', 'host_id', 'host'),
        ('nodes', 'node_id', 'node'),
    ],
)
def test_add_contact(
    client: TestClient[Litestar],
    session: Session,
    resource_path_name: str,
    resource_id: str,
    resource: str,
    request: FixtureRequest,
):
    name = f'Test {resource} Create Contact Name 1'
    email = 'testcreate@contact.name'
    r: ContactOwner = request.getfixturevalue(resource)
    response = client.post(
        f'{API_V1_PATH}/{resource_path_name}/{getattr(r, resource_id)}/contacts',
        json={
            'contact_name': name,
            'email': email,
        },
    )
    assert response.status_code == 201
    content = contact_decoder.decode(response.content)
    assert (
        response.headers['location'] == f'{API_V1_PATH}/contacts/{content.contact_id}'
    )
    assert (
        response.headers['content-location']
        == f'{API_V1_PATH}/contacts/{content.contact_id}'
    )
    assert content.contact_name == name
    assert content.email == email
    session.refresh(r)
    assert to_contact_schema(r.contacts[-1]) == content


@pytest.mark.parametrize(
    'resource_path_name,resource_id,resource',
    [
        ('allocators', 'allocator_id', 'allocator'),
        ('operators', 'operator_id', 'operator'),
        ('hosts', 'host_id', 'host'),
        ('nodes', 'node_id', 'node'),
    ],
)
def test_add_contact_unset_email(
    client: TestClient[Litestar],
    session: Session,
    resource_path_name: str,
    resource_id: str,
    resource: str,
    request: FixtureRequest,
):
    name = f'Test {resource} Create Contact Name 2'
    r: ContactOwner = request.getfixturevalue(resource)
    response = client.post(
        f'{API_V1_PATH}/{resource_path_name}/{getattr(r, resource_id)}/contacts',
        json={
            'contact_name': name,
        },
    )
    assert response.status_code == 201
    content = contact_decoder.decode(response.content)
    assert (
        response.headers['location'] == f'{API_V1_PATH}/contacts/{content.contact_id}'
    )
    assert (
        response.headers['content-location']
        == f'{API_V1_PATH}/contacts/{content.contact_id}'
    )
    assert content.contact_name == name
    assert content.email is None
    session.refresh(r)
    assert to_contact_schema(r.contacts[-1]) == content


@pytest.mark.parametrize(
    'resource_path_name,resource_id,resource',
    [
        ('allocators', 'allocator_id', 'allocator'),
        ('operators', 'operator_id', 'operator'),
        ('hosts', 'host_id', 'host'),
        ('nodes', 'node_id', 'node'),
    ],
)
def test_add_contact_set_null_email(
    client: TestClient[Litestar],
    session: Session,
    resource_path_name: str,
    resource_id: str,
    resource: str,
    request: FixtureRequest,
):
    name = f'Test {resource} Create Contact Name 2'
    r: ContactOwner = request.getfixturevalue(resource)
    response = client.post(
        f'{API_V1_PATH}/{resource_path_name}/{getattr(r, resource_id)}/contacts',
        json={
            'contact_name': name,
            'email': None,
        },
    )
    assert response.status_code == 201
    content = contact_decoder.decode(response.content)
    assert (
        response.headers['location'] == f'{API_V1_PATH}/contacts/{content.contact_id}'
    )
    assert (
        response.headers['content-location']
        == f'{API_V1_PATH}/contacts/{content.contact_id}'
    )
    assert content.contact_name == name
    assert content.email is None
    session.refresh(r)
    assert to_contact_schema(r.contacts[-1]) == content


@pytest.mark.parametrize(
    'resource_path_name,resource_id,resource',
    [
        ('allocators', 'allocator_id', 'allocator'),
        ('operators', 'operator_id', 'operator'),
        ('hosts', 'host_id', 'host'),
        ('nodes', 'node_id', 'node'),
    ],
)
def test_add_contact_existing_contact_id(
    client: TestClient[Litestar],
    session: Session,
    contacts: list[Contact],
    resource_path_name: str,
    resource_id: str,
    resource: str,
    request: FixtureRequest,
):
    contact = contacts[0]
    contact2 = contacts[1]
    r: ContactOwner = request.getfixturevalue(resource)

    name = 'foo'
    email = 'bar'
    response = client.post(
        f'{API_V1_PATH}/{resource_path_name}/{getattr(r, resource_id)}/contacts',
        json={
            'existing_contact_id': contact.contact_id,
            'contact_name': name,
            'email': email,
        },
    )
    assert response.status_code == 200
    content = contact_decoder.decode(response.content)
    assert (
        response.headers['content-location']
        == f'{API_V1_PATH}/contacts/{contact.contact_id}'
    )
    # Using existing_contact_id ignores name and email
    assert content.contact_name != name
    assert content.email != email
    session.refresh(r)
    assert contact in r.contacts

    # It's okay to not have contact name if using existing_contact_id
    response = client.post(
        f'{API_V1_PATH}/{resource_path_name}/{getattr(r, resource_id)}/contacts',
        json={
            'existing_contact_id': contact2.contact_id,
        },
    )
    assert response.status_code == 200
    content = contact_decoder.decode(response.content)
    assert (
        response.headers['content-location']
        == f'{API_V1_PATH}/contacts/{contact2.contact_id}'
    )
    session.refresh(r)
    assert contact2 in r.contacts


@pytest.mark.parametrize(
    'resource_path_name,resource_id,resource',
    [
        ('allocators', 'allocator_id', 'allocator'),
        ('operators', 'operator_id', 'operator'),
        ('hosts', 'host_id', 'host'),
        ('nodes', 'node_id', 'node'),
    ],
)
def test_add_contact_non_existent_allocator(
    client: TestClient[Litestar],
    resource_path_name: str,
    resource_id: str,
    resource: str,
    request: FixtureRequest,
):
    id = getattr(request.getfixturevalue(resource), resource_id)
    response = client.post(
        f'{API_V1_PATH}/{resource_path_name}/{id + 1}/contacts',
        json={
            'contact_name': 'foo',
            'email': 'bar',
        },
    )
    assert response.status_code == 404
    assert (
        f'{resource.capitalize()} ID {id + 1} does not exist'
        in response.json()['detail']
    )


@pytest.mark.parametrize(
    'resource_path_name,resource_id,resource',
    [
        ('allocators', 'allocator_id', 'allocator'),
        ('operators', 'operator_id', 'operator'),
        ('hosts', 'host_id', 'host'),
        ('nodes', 'node_id', 'node'),
    ],
)
def test_add_contact_non_existent_contact_id(
    client: TestClient[Litestar],
    contact: Contact,
    resource_path_name: str,
    resource_id: str,
    resource: str,
    request: FixtureRequest,
):
    id = getattr(request.getfixturevalue(resource), resource_id)
    response = client.post(
        f'{API_V1_PATH}/{resource_path_name}/{id}/contacts',
        json={'existing_contact_id': contact.contact_id + 1},
    )
    assert response.status_code == 404
    assert (
        f'Contact ID {contact.contact_id + 1} does not exist'
        in response.json()['detail']
    )


@pytest.mark.parametrize(
    'resource_path_name,resource_id,resource_with_details',
    [
        ('allocators', 'allocator_id', 'allocator_with_details'),
        ('operators', 'operator_id', 'operator_with_details'),
        ('hosts', 'host_id', 'host_with_contacts'),
        ('nodes', 'node_id', 'node_with_contacts'),
    ],
)
def test_add_contact_already_associated(
    client: TestClient[Litestar],
    resource_path_name: str,
    resource_id: str,
    resource_with_details: str,
    request: FixtureRequest,
):
    r: ContactOwner = request.getfixturevalue(resource_with_details)
    r_id = getattr(r, resource_id)
    contact_id = r.contacts[0].contact_id
    response = client.post(
        f'{API_V1_PATH}/{resource_path_name}/{r_id}/contacts',
        json={'existing_contact_id': contact_id},
    )
    assert response.status_code == 400
    assert (
        f'{contact_id} is already associated with {resource_path_name[:-1]} ID {r_id}'
        in response.json()['detail']
    )


@pytest.mark.parametrize(
    'resource_path_name', [('allocators'), ('operators'), ('hosts'), ('nodes')]
)
def test_add_contact_blank_name(client: TestClient[Litestar], resource_path_name: str):
    response = client.post(
        f'{API_V1_PATH}/{resource_path_name}/34/contacts', json={'contact_name': ' '}
    )
    assert response.status_code == 400
    assert (
        '`contact_name` cannot consist solely of whitespace'
        in response.json()['extra'][0]['message']
    )


@pytest.mark.parametrize(
    'resource_path_name', [('allocators'), ('operators'), ('hosts'), ('nodes')]
)
def test_add_contact_required(client: TestClient[Litestar], resource_path_name: str):
    response = client.post(f'{API_V1_PATH}/{resource_path_name}/34/contacts')
    assert response.status_code == 400
    assert 'Expected non-empty request body' in response.json()['extra'][0]['message']

    response = client.post(f'{API_V1_PATH}/{resource_path_name}/34/contacts', json={})
    assert response.status_code == 400
    assert (
        'Object missing required field `contact_name`'
        in response.json()['extra'][0]['message']
    )


@pytest.mark.parametrize(
    'resource_path_name,resource_id,resource_id_max',
    [
        ('allocators', 'allocator_id', ALLOCATOR_ID_MAX),
        ('operators', 'operator_id', OPERATOR_ID_MAX),
        ('hosts', 'host_id', HOST_ID_MAX),
        ('nodes', 'node_id', NODE_ID_MAX),
    ],
)
def test_add_contact_id_validate_id(
    client: TestClient[Litestar],
    resource_path_name: str,
    resource_id: str,
    resource_id_max: int,
):
    response = client.post(
        f'{API_V1_PATH}/{resource_path_name}/{resource_id_max * 2}/contacts',
        json={'existing_contact_id': CONTACT_ID_MAX * 2},
    )
    assert response.status_code == 400
    assert response.json()['extra'] == [
        {
            'message': f'Expected `int` <= {resource_id_max}',
            'key': resource_id,
            'source': 'path',
        },
        {
            'message': f'Expected `int` <= {CONTACT_ID_MAX}',
            'key': 'existing_contact_id',
            'source': 'body',
        },
    ]


@pytest.mark.parametrize(
    'resource_path_name,resource_id,resource_with_details',
    [
        ('allocators', 'allocator_id', 'allocator_with_details'),
        ('operators', 'operator_id', 'operator_with_details'),
        ('hosts', 'host_id', 'host_with_contacts'),
        ('nodes', 'node_id', 'node_with_contacts'),
    ],
)
def test_remove_contact(
    client: TestClient[Litestar],
    resource_path_name: str,
    resource_id: str,
    resource_with_details: str,
    request: FixtureRequest,
):
    r: ContactOwner = request.getfixturevalue(resource_with_details)
    r_id = getattr(r, resource_id)
    c1 = r.contacts[0]
    response = client.delete(
        f'{API_V1_PATH}/{resource_path_name}/{r_id}/contacts/{c1.contact_id}'
    )
    assert response.status_code == 204
    # Was deleted, so trying again should fail
    response = client.delete(
        f'{API_V1_PATH}/{resource_path_name}/{r_id}/contacts/{c1.contact_id}'
    )
    assert response.status_code == 404
    assert f'Contact ID {c1.contact_id} does not exist' in response.json()['detail']


@pytest.mark.parametrize(
    'resource_path_name,resource_id,resource',
    [
        ('allocators', 'allocator_id', 'allocator'),
        ('operators', 'operator_id', 'operator'),
        ('hosts', 'host_id', 'host'),
        ('nodes', 'node_id', 'node'),
    ],
)
def test_remove_contact_non_existent_allocator(
    client: TestClient[Litestar],
    resource_path_name: str,
    resource_id: str,
    resource: str,
    request: FixtureRequest,
):
    r: ContactOwner = request.getfixturevalue(resource)
    r_id = getattr(r, resource_id)
    response = client.delete(
        f'{API_V1_PATH}/{resource_path_name}/{r_id + 1}/contacts/45'
    )
    assert response.status_code == 404
    assert (
        f'{resource.capitalize()} ID {r_id + 1} does not exist'
        in response.json()['detail']
    )


@pytest.mark.parametrize(
    'resource_path_name,resource_id,resource',
    [
        ('allocators', 'allocator_id', 'allocator'),
        ('operators', 'operator_id', 'operator'),
        ('hosts', 'host_id', 'host'),
        ('nodes', 'node_id', 'node'),
    ],
)
def test_remove_contact_not_associated(
    client: TestClient[Litestar],
    session: Session,
    contact_with_details: Contact,
    resource_path_name: str,
    resource_id: str,
    resource: str,
    request: FixtureRequest,
):
    r: ContactOwner = request.getfixturevalue(resource)
    r_id = getattr(r, resource_id)
    c1 = contact_with_details
    r.contacts.append(c1)
    session.commit()

    # c1 which is currently associated with r
    response = client.delete(
        f'{API_V1_PATH}/{resource_path_name}/{r_id}/contacts/{c1.contact_id}'
    )
    assert response.status_code == 204

    # c1 still exists
    response = client.delete(
        f'{API_V1_PATH}/{resource_path_name}/{r_id}/contacts/{c1.contact_id}'
    )
    assert response.status_code == 400
    assert (
        f'ID {c1.contact_id} is not associated with {resource} ID {r_id}'
        in response.json()['detail']
    )


@pytest.mark.parametrize(
    'resource_path_name,resource_id,resource_id_max',
    [
        ('allocators', 'allocator_id', ALLOCATOR_ID_MAX),
        ('operators', 'operator_id', OPERATOR_ID_MAX),
        ('hosts', 'host_id', HOST_ID_MAX),
        ('nodes', 'node_id', NODE_ID_MAX),
    ],
)
def test_remove_contact_id_validate_id(
    client: TestClient[Litestar],
    resource_path_name: str,
    resource_id: str,
    resource_id_max: int,
):
    response = client.delete(
        f'{API_V1_PATH}/{resource_path_name}/{resource_id_max * 2}'
        f'/contacts/{CONTACT_ID_MAX * 2}'
    )
    assert response.status_code == 400
    assert response.json()['extra'] == [
        {
            'message': f'Expected `int` <= {ALLOCATOR_ID_MAX}',
            'key': resource_id,
            'source': 'path',
        },
        {
            'message': f'Expected `int` <= {CONTACT_ID_MAX}',
            'key': 'contact_id',
            'source': 'path',
        },
    ]

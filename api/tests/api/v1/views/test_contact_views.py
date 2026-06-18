from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

from app.api.v1.contact.schemas import (
    ContactSchema,
    to_contact_schema,
    to_phone_number_schema,
)
from app.config import API_V1_PATH, MAX_PAGE_SIZE
from app.fields import CONTACT_ID_MAX
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

    from app.models import Contact

contact_decoder = msgspec.json.Decoder(type=ContactSchema, strict=False)


def test_get_contact(client: TestClient[Litestar], contact: Contact):
    response = client.get(f'{API_V1_PATH}/contacts/{contact.contact_id}')
    assert response.status_code == 200
    assert contact_decoder.decode(response.content) == to_contact_schema(contact)


def test_get_contact_not_found(client: TestClient[Litestar]):
    response = client.get(f'{API_V1_PATH}/contacts/0')
    assert response.status_code == 404
    assert 'ID 0 does not exist' in response.json()['detail']


def test_get_contact_validation(client: TestClient[Litestar]):
    response = client.get(f'{API_V1_PATH}/contacts/{CONTACT_ID_MAX * 2}')
    assert response.status_code == 400
    assert f'<= {CONTACT_ID_MAX}' in response.json()['extra'][0]['message']


def test_query_contacts(client: TestClient[Litestar], contacts: list[Contact]):
    items = collect_paginated_data(client, f'{API_V1_PATH}/contacts', MAX_PAGE_SIZE)
    for c in contacts:
        assert to_contact_schema(c).to_dict() in items


def test_query_contacts_pagination(
    client: TestClient[Litestar], contacts: list[Contact]
):
    url = f'{API_V1_PATH}/contacts'
    items = collect_paginated_data(client, url, 1)
    for c in contacts:
        assert to_contact_schema(c).to_dict() in items

    params = {'max_page_size': 1, 'page_token': 'last'}
    response = client.get(url, params=params)
    assert response.status_code == 200
    assert len(response.json()['items']) == params['max_page_size']
    assert response.json().get('prev_page_token') is not None
    assert response.json().get('next_page_token') is None
    assert items[-1] == response.json()['items'][0]


def test_query_contacts_page_size(
    client: TestClient[Litestar], contacts_max_and_one: list[Contact]
):
    check_page_size(client, f'{API_V1_PATH}/contacts')


def test_query_contacts_invalid_page_token(
    client: TestClient[Litestar], contacts: list[Contact]
):
    check_invalid_page_token_query(client, f'{API_V1_PATH}/contacts')


def test_query_contacts_validation(client: TestClient[Litestar]):
    check_query_request_validation(client, f'{API_V1_PATH}/contacts')


def test_update_contact(
    client: TestClient[Litestar], session: Session, contact: Contact
):
    contact_name = 'Test Contact Name'
    email = 'testemail@email.com'
    assert contact.contact_name != contact_name
    assert contact.email != email
    response = client.patch(
        f'{API_V1_PATH}/contacts/{contact.contact_id}',
        json={
            'contact_name': contact_name,
            'email': email,
        },
    )
    assert response.status_code == 200
    content = contact_decoder.decode(response.content)
    session.refresh(contact)
    assert content == to_contact_schema(contact)
    assert content.contact_name == contact_name
    assert content.email == email


def test_update_contact_null_email(
    client: TestClient[Litestar], session: Session, contact: Contact
):
    response = client.patch(
        f'{API_V1_PATH}/contacts/{contact.contact_id}',
        json={
            'email': None,
        },
    )
    assert response.status_code == 200
    session.refresh(contact)
    assert contact.email is None


def test_update_contact_no_change(
    client: TestClient[Litestar], session: Session, contact: Contact
):
    old_name = contact.contact_name
    old_email = contact.email

    for response in [
        # Missing request body
        client.patch(f'{API_V1_PATH}/contacts/{contact.contact_id}'),
        # Empty request body
        client.patch(f'{API_V1_PATH}/contacts/{contact.contact_id}', content=b''),
        # Empty object
        client.patch(f'{API_V1_PATH}/contacts/{contact.contact_id}', json={}),
        # Passing same name and email causes no changes
        client.patch(
            f'{API_V1_PATH}/contacts/{contact.contact_id}',
            json={'contact_name': old_name, 'email': old_email},
        ),
    ]:
        assert response.status_code == 200
        content = contact_decoder.decode(response.content)
        session.refresh(contact)
        assert content == to_contact_schema(contact)
        assert content.contact_name == old_name
        assert content.email == old_email


def test_update_contact_not_found(client: TestClient[Litestar], contact: Contact):
    response = client.patch(
        f'{API_V1_PATH}/contacts/{contact.contact_id + 999}',
        json={'contact_name': 'foo', 'email': 'bar'},
    )
    assert response.status_code == 404
    assert f'ID {contact.contact_id + 999} does not exist' in response.json()['detail']


def test_update_contact_validation(client: TestClient[Litestar]):
    # contact_id out of range
    response = client.patch(f'{API_V1_PATH}/contacts/{CONTACT_ID_MAX * 2}')
    assert response.status_code == 400
    assert f'<= {CONTACT_ID_MAX}' in response.json()['extra'][0]['message']

    # Blank string for name fails
    response = client.patch(
        f'{API_V1_PATH}/contacts/0',
        json={
            'contact_name': '  ',
        },
    )
    assert response.status_code == 400
    assert (
        '`contact_name` cannot consist solely of whitespace'
        in response.json()['extra'][0]['message']
    )


def test_delete_contact_no_associations(
    client: TestClient[Litestar], contacts: list[Contact], session: Session
):
    from app.api.v1.contact.service import get

    # c1 and c2 are not associated with anything
    c1_id = contacts[0].contact_id
    c2_id = contacts[1].contact_id
    # Delete contact not associated with anything
    response = client.delete(f'{API_V1_PATH}/contacts/{c1_id}')
    assert response.status_code == 204
    # c1 is deleted, but c2 still exists
    assert not get(session, c1_id)
    assert get(session, c2_id)
    # Trying to delete c1 again will fail b/c doesn't exist
    response = client.delete(f'{API_V1_PATH}/contacts/{c1_id}')
    assert response.status_code == 404
    assert f'ID {c1_id} does not exist' in response.json()['detail']


def test_delete_contact_with_associations(
    client: TestClient[Litestar], contact_with_details: Contact, contact: Contact
):
    # `contact` is not associated with anything.
    # `contact_with_details` is associated with entities.
    # Deleting a contact associated with something will remove all
    # non-associated contacts.
    c1_id = contact_with_details.contact_id
    c2_id = contact.contact_id
    response = client.delete(f'{API_V1_PATH}/contacts/{c1_id}')
    assert response.status_code == 204
    # Trying to delete c1_id and c2_id fails b/c don't exist
    response = client.delete(f'{API_V1_PATH}/contacts/{c1_id}')
    assert response.status_code == 404
    assert f'ID {c1_id} does not exist' in response.json()['detail']
    response = client.delete(f'{API_V1_PATH}/contacts/{c2_id}')
    assert response.status_code == 404
    assert f'ID {c2_id} does not exist' in response.json()['detail']


def test_delete_contact_validation(client: TestClient[Litestar]):
    response = client.delete(f'{API_V1_PATH}/contacts/{CONTACT_ID_MAX * 2}')
    assert response.status_code == 400
    assert f'<= {CONTACT_ID_MAX}' in response.json()['extra'][0]['message']


def test_list_contact_phone_numbers(client: TestClient[Litestar], contact: Contact):
    items = collect_paginated_data(
        client,
        f'{API_V1_PATH}/contacts/{contact.contact_id}/phone-numbers',
        MAX_PAGE_SIZE,
    )
    for p_n in contact.phone_numbers:
        assert to_phone_number_schema(p_n).to_dict() in items


def test_list_contact_phone_numbers_pagination(
    client: TestClient[Litestar], contact_max_and_one_phone_numbers: Contact
):
    contact = contact_max_and_one_phone_numbers
    items = collect_paginated_data(
        client, f'{API_V1_PATH}/contacts/{contact.contact_id}/phone-numbers', 1
    )
    for p_n in contact.phone_numbers:
        assert to_phone_number_schema(p_n).to_dict() in items

    params = {'max_page_size': 1, 'page_token': 'last'}
    response = client.get(
        f'{API_V1_PATH}/contacts/{contact.contact_id}/phone-numbers', params=params
    )
    assert response.status_code == 200
    assert len(response.json()['items']) == params['max_page_size']
    assert response.json().get('prev_page_token') is not None
    assert response.json().get('next_page_token') is None
    assert items[-1] == response.json()['items'][0]


def test_list_contact_phone_numbers_page_size(
    client: TestClient[Litestar], contact_max_and_one_phone_numbers: Contact
):
    contact = contact_max_and_one_phone_numbers
    check_page_size(
        client, f'{API_V1_PATH}/contacts/{contact.contact_id}/phone-numbers'
    )


def test_list_contact_phone_numbers_invalid_page_token(
    client: TestClient[Litestar],
    contact_max_and_one_phone_numbers: Contact,
    contact: Contact,
):
    other_contact_id = contact.contact_id
    contact = contact_max_and_one_phone_numbers
    check_invalid_page_token_different_url(
        client,
        f'{API_V1_PATH}/contacts/{contact.contact_id}/phone-numbers',
        f'{API_V1_PATH}/contacts/{other_contact_id}/phone-numbers',
    )


def test_list_contact_phone_numbers_not_found(client: TestClient[Litestar]):
    response = client.get(f'{API_V1_PATH}/contacts/0/phone-numbers')
    assert response.status_code == 404
    assert 'ID 0 does not exist' in response.json()['detail']


def test_list_contact_phone_numbers_validation(client: TestClient[Litestar]):
    response = client.get(f'{API_V1_PATH}/contacts/{CONTACT_ID_MAX * 2}/phone-numbers')
    assert response.status_code == 400
    assert f'<= {CONTACT_ID_MAX}' in response.json()['extra'][0]['message']

    check_paginated_request_validation(
        client, f'{API_V1_PATH}/contacts/0/phone-numbers'
    )


def test_replace_contact_phone_numbers(
    client: TestClient[Litestar], contact: Contact, session: Session
):
    phone_nums: list[dict[str, str | bool]] = [
        {'phone_number': '123'},
        {'phone_number': '456', 'preferred': True},
        {'phone_number': '789', 'preferred': False},
    ]
    url = f'{API_V1_PATH}/contacts/{contact.contact_id}/phone-numbers'
    response = client.put(url, json=phone_nums)
    assert response.status_code == 204
    session.refresh(contact)
    assert len(phone_nums) == len(contact.phone_numbers)
    for i in range(len(phone_nums)):
        assert i == contact.phone_numbers[i].order_pos
        assert (
            phone_nums[i].get('phone_number') == contact.phone_numbers[i].phone_number
        )
        assert (
            phone_nums[i].get('preferred', False) == contact.phone_numbers[i].preferred
        )


def test_replace_contact_phone_numbers_empty(
    client: TestClient[Litestar], contact: Contact, session: Session
):
    assert contact.phone_numbers
    url = f'{API_V1_PATH}/contacts/{contact.contact_id}/phone-numbers'
    response = client.put(url, json=[])
    assert response.status_code == 204
    session.refresh(contact)
    assert not contact.phone_numbers


def test_replace_contact_phone_numbers_not_found(client: TestClient[Litestar]):
    response = client.put(f'{API_V1_PATH}/contacts/0/phone-numbers', json=[])
    assert response.status_code == 404
    assert 'ID 0 does not exist' in response.json()['detail']


def test_replace_contact_phone_numbers_validate_required_reqbody(
    client: TestClient[Litestar],
):
    for response in [
        # Missing request body
        client.put(f'{API_V1_PATH}/contacts/0/phone-numbers'),
        # Empty request body
        client.put(f'{API_V1_PATH}/contacts/0/phone-numbers', content=b''),
    ]:
        assert response.status_code == 400
        assert 'Expected non-empty request' in response.json()['extra'][0]['message']


def test_replace_contact_phone_numbers_validate_null_reqbody(
    client: TestClient[Litestar],
):
    # `null` is distinct from a missing / empty request body
    response = client.put(f'{API_V1_PATH}/contacts/0/phone-numbers', content=b'null')
    assert response.status_code == 400
    assert 'Expected `array`, got `null`' in response.json()['extra'][0]['message']


def test_replace_contact_phone_numbers_validation(client: TestClient[Litestar]):
    response = client.put(
        f'{API_V1_PATH}/contacts/{CONTACT_ID_MAX * 2}/phone-numbers', json=[]
    )
    assert response.status_code == 400
    assert f'<= {CONTACT_ID_MAX}' in response.json()['extra'][0]['message']

    for json in [
        # Empty object
        [{}],
        # Missing phone_number
        [{'preferred': False}],
    ]:
        response = client.put(f'{API_V1_PATH}/contacts/0/phone-numbers', json=json)
        assert response.status_code == 400
        assert 'missing required field' in response.json()['extra'][0]['message']

    # Blank phone_number
    response = client.put(
        f'{API_V1_PATH}/contacts/0/phone-numbers', json=[{'phone_number': ' '}]
    )
    assert response.status_code == 400
    assert (
        '`phone_number` cannot consist solely of whitespace'
        in response.json()['extra'][0]['message']
    )

    # `null` phone_number
    response = client.put(
        f'{API_V1_PATH}/contacts/0/phone-numbers', json=[{'phone_number': None}]
    )
    assert response.status_code == 400
    assert 'Expected `str`, got `null`' in response.json()['extra'][0]['message']

    # Wrong `preferred` type
    response = client.put(
        f'{API_V1_PATH}/contacts/0/phone-numbers',
        json=[{'phone_number': 'a', 'preferred': 2}],
    )
    assert response.status_code == 400
    assert 'Expected `bool`, got `int`' in response.json()['extra'][0]['message']

    response = client.put(
        f'{API_V1_PATH}/contacts/0/phone-numbers',
        json=[{'phone_number': 'a', 'preferred': None}],
    )
    assert response.status_code == 400
    assert 'Expected `bool`, got `null`' in response.json()['extra'][0]['message']

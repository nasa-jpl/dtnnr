from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import exc

from tests.util import get_as_jsonb

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import Contact, ContactPhoneNumber


def test_get(session: Session, contact: Contact):
    from app.api.v1.contact.service import get

    t_contact = get(session, contact.contact_id)
    assert t_contact == contact


def test_query(session: Session, contacts: list[Contact]):
    from app.api.v1.contact.service import query

    t_contacts = []
    page = query(session, 1, None)
    t_contacts.extend([_ for (_,) in page])
    while page.paging.has_next:
        page = query(session, 1, page.paging.bookmark_next)
        t_contacts.extend([_ for (_,) in page])

    for c in contacts:
        assert c in t_contacts


def test_list_phone_numbers(session: Session, contact: Contact):
    from app.api.v1.contact.service import list_phone_numbers

    p_nums = []
    page = list_phone_numbers(session, contact.contact_id, 1, None)
    p_nums.extend([_ for (_,) in page])
    while page.paging.has_next:
        page = list_phone_numbers(
            session, contact.contact_id, 1, page.paging.bookmark_next
        )
        p_nums.extend([_ for (_,) in page])

    for p_n in contact.phone_numbers:
        assert p_n in p_nums


def test_replace_phone_numbers(
    session: Session, contact: Contact, phone_numbers: list[ContactPhoneNumber]
):
    from app.api.v1.contact.schemas import PhoneNumberReplaceSchema
    from app.api.v1.contact.service import replace_phone_numbers

    p_n_replace_schemas: list[PhoneNumberReplaceSchema] = []
    for p_n in phone_numbers:
        p_n_replace_schemas.append(
            PhoneNumberReplaceSchema(
                phone_number=p_n.phone_number,
                preferred=p_n.preferred,
            )
        )
    replace_phone_numbers(session, contact.contact_id, p_n_replace_schemas)
    for p_n, i in zip(p_n_replace_schemas, range(len(p_n_replace_schemas))):
        assert contact.phone_numbers[i].order_pos == i
        assert contact.phone_numbers[i].phone_number == p_n.phone_number
        assert contact.phone_numbers[i].preferred == p_n.preferred


def test_create(session: Session):
    from app.api.v1.contact.service import create

    name = 'Test Contact Service Create'
    email = 'asdfghjkl'  # Currently no validation for email format
    t_contact = create(session, name, email)
    assert t_contact.contact_name == name
    assert t_contact.email == email

    with pytest.raises(exc.IntegrityError):
        # Can't use empty string for name
        create(session, '', email)
    session.rollback()

    with pytest.raises(exc.IntegrityError):
        # Can't use null for name
        create(session, None, email)
    session.rollback()


def test_update(session: Session, contact: Contact):
    from app.api.v1.contact.service import update

    name = 'New Contact Name'
    email = 'newemail@email.com'
    t_contact = update(session, contact.contact_id, name, email)
    assert t_contact.contact_name == name
    assert t_contact.email == email

    with pytest.raises(Exception):
        # Can't use empty string for name
        update(session, contact.contact_id, '', email)
    session.rollback()

    with pytest.raises(Exception):
        # Can't use null for name
        update(session, contact.contact_id, None, email)
    session.rollback()


def test_delete(
    session: Session, contact_with_details: Contact, contacts: list[Contact]
):
    from sqlalchemy import select

    from app.api.v1.contact.service import delete, get
    from app.models import Contact
    from tests.util import verify_soft_deletion

    c0 = contact_with_details
    c0_id = c0.contact_id

    # Deleting a contact not associated with anything will not delete
    # other non-associated contacts
    c1 = contacts[0]
    c1_id = c1.contact_id
    c2 = contacts[1]
    c2_id = c2.contact_id
    assert not c1.allocators
    assert not c1.operators
    assert not c1.hosts
    assert not c1.nodes
    assert not c2.allocators
    assert not c2.operators
    assert not c1.hosts
    assert not c1.nodes
    assert get(session, c0_id)
    assert get(session, c1_id)
    assert get(session, c2_id)
    c1_jsonb = get_as_jsonb(session, select(Contact).where(Contact.contact_id == c1_id))
    delete(session, c1_id)
    assert get(session, c0_id)
    assert not get(session, c1_id)
    assert get(session, c2_id)
    assert verify_soft_deletion(session, c1_jsonb)

    # But deleting a contact that is associated with something will clean up
    # any non-associated contacts.
    # If we uncommented out these assert statements, my understanding is that
    # SQLAlchemy will load the relationships into session, and when we call
    # session.delete(c0), SQLAlchemy will first emit DELETE statements for the
    # association tables. This will give us a warning because SQLAlchemy will
    # still try to emit a DELETE statement afterwards (and it's not deleting
    # anything because of our trigger which cleans up non-associated contacts).
    # assert c0.allocators
    # assert c0.operators
    c0_jsonb = get_as_jsonb(session, select(Contact).where(Contact.contact_id == c0_id))
    c2_jsonb = get_as_jsonb(session, select(Contact).where(Contact.contact_id == c2_id))
    delete(session, c0_id)
    assert not get(session, c0_id)
    assert not get(session, c2_id)
    assert verify_soft_deletion(session, c0_jsonb)
    assert verify_soft_deletion(session, c2_jsonb)

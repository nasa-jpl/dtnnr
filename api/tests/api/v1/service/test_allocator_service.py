from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import exc

from tests.util import get_as_jsonb

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import Allocator, Contact, Node, Operator


def test_get(session: Session, allocator: Allocator):
    from app.api.v1.allocator.service import get

    t_allocator = get(session, allocator.allocator_id)
    assert t_allocator == allocator


def test_query(session: Session, allocators: list[Allocator]):
    from app.api.v1.allocator.service import query

    t_allocators = []
    page = query(session, 1, None, False)
    t_allocators.extend([_ for (_,) in page])
    while page.paging.has_next:
        page = query(session, 1, page.paging.bookmark_next, False)
        t_allocators.extend([_ for (_,) in page])

    for a in allocators:
        assert a in t_allocators


def test_create(session: Session):
    from app.api.v1.allocator.service import create

    allocator_id = 123456
    allocator_name = 'Test Service Create Allocator'
    t_allocator = create(session, allocator_id, allocator_name)
    assert t_allocator.allocator_id == allocator_id
    assert t_allocator.allocator_name == allocator_name


def test_update(session: Session, allocator: Allocator):
    import random

    from app.api.v1.allocator.service import update

    # Only update the name
    old_allocator_id = allocator.allocator_id
    old_allocator_name = allocator.allocator_name  # this shouldn't be a palindrome
    t_allocator = update(session, allocator.allocator_id, old_allocator_name[::-1])
    assert t_allocator.allocator_id == old_allocator_id
    assert t_allocator.allocator_name == old_allocator_name[::-1]

    # Update both name and id
    new_allocator_id = old_allocator_id + 1234567
    new_allocator_name = f'{random.getrandbits(10 * 4):010x}'
    t_allocator = update(
        session, allocator.allocator_id, new_allocator_name, new_allocator_id
    )
    assert t_allocator.allocator_id == new_allocator_id
    assert t_allocator.allocator_name == new_allocator_name


def test_delete(session: Session, allocator: Allocator, node: Node):
    from sqlalchemy import select

    from app.api.v1.allocator.service import delete, get
    from app.models import Allocator, Node, Operator
    from tests.util import verify_soft_deletion

    allocator_id = allocator.allocator_id
    jsonb = get_as_jsonb(
        session, select(Allocator).where(Allocator.allocator_id == allocator_id)
    )
    delete(session, allocator_id)
    assert not get(session, allocator_id)
    assert verify_soft_deletion(session, jsonb)

    # Deleting an allocator should be restricted if there are any nodes
    # or operators beneath it.
    allocator_id = node.allocator_id
    operator_id = node.operator_id
    node_id = node.node_id
    with pytest.raises(exc.IntegrityError):
        delete(session, allocator_id)
    session.rollback()
    assert get(session, allocator_id)
    assert session.scalar(select(Operator).where(Operator.operator_id == operator_id))
    assert session.scalar(select(Node).where(Node.node_id == node_id))


def test_list_contacts(session: Session, allocator_with_details: Allocator):
    from app.api.v1.allocator.service import list_contacts

    allocator = allocator_with_details
    contacts = []
    page = list_contacts(session, allocator.allocator_id, 1, None)
    contacts.extend([_ for (_,) in page])
    while page.paging.has_next:
        page = list_contacts(
            session, allocator.allocator_id, 1, page.paging.bookmark_next
        )
        contacts.extend([_ for (_,) in page])

    for c in allocator.contacts:
        assert c in contacts


def test_associate_contact(
    session: Session, allocator: Allocator, contact_with_details: Contact
):
    from app.api.v1.allocator.service import associate_contact

    contact = contact_with_details
    associate_contact(session, allocator.allocator_id, contact.contact_id)
    assert contact in allocator.contacts
    assert allocator in contact.allocators


def test_dissociate_contact(
    session: Session, allocator_with_details: Allocator, operator: Operator
):
    from sqlalchemy import select

    from app.api.v1.allocator.service import dissociate_contact
    from app.models import Contact, allocator_contact
    from tests.util import verify_soft_deletion

    a = allocator_with_details
    c1 = a.contacts[0]
    c2 = a.contacts[1]
    o = operator
    o.contacts.append(c2)
    session.commit()

    assert len(a.contacts) > 1
    assert c1 in a.contacts
    jsonb = get_as_jsonb(
        session,
        select(allocator_contact).where(
            allocator_contact.c.allocator_id == a.allocator_id,
            allocator_contact.c.contact_id == c1.contact_id,
        ),
    )
    dissociate_contact(session, a.allocator_id, c1.contact_id)
    assert c1 not in a.contacts
    assert a.contacts  # not empty
    assert c1 not in session.scalars(select(Contact)).all()
    assert c2 in session.scalars(select(Contact)).all()
    assert verify_soft_deletion(session, jsonb)

    # But if the contact is still associated with an entity, it still exists
    assert c2 in o.contacts
    jsonb = get_as_jsonb(
        session,
        select(allocator_contact).where(
            allocator_contact.c.allocator_id == a.allocator_id,
            allocator_contact.c.contact_id == c2.contact_id,
        ),
    )
    dissociate_contact(session, a.allocator_id, c2.contact_id)
    assert c2 in o.contacts
    assert c2 in session.scalars(select(Contact)).all()
    assert verify_soft_deletion(session, jsonb)


def test_contact_is_associated(
    session: Session, allocator: Allocator, contacts_with_details: list[Contact]
):
    from sqlalchemy import select

    from app.api.v1.allocator.service import contact_is_associated
    from app.models import allocator_contact
    from tests.util import verify_soft_deletion

    a1 = allocator
    c1 = contacts_with_details[0]
    c2 = contacts_with_details[1]
    a1.contacts.append(c1)
    a1.contacts.append(c2)
    session.commit()

    assert contact_is_associated(session, a1.allocator_id, c1.contact_id)
    assert contact_is_associated(session, a1.allocator_id, c2.contact_id)
    jsonb = get_as_jsonb(
        session,
        select(allocator_contact).where(
            allocator_contact.c.allocator_id == a1.allocator_id,
            allocator_contact.c.contact_id == c1.contact_id,
        ),
    )
    a1.contacts.remove(c1)
    session.commit()
    assert not contact_is_associated(session, a1.allocator_id, c1.contact_id)
    assert contact_is_associated(session, a1.allocator_id, c2.contact_id)
    assert verify_soft_deletion(session, jsonb)

    jsonb = get_as_jsonb(
        session,
        select(allocator_contact).where(
            allocator_contact.c.allocator_id == a1.allocator_id,
            allocator_contact.c.contact_id == c2.contact_id,
        ),
    )
    a1.contacts.remove(c2)
    session.commit()
    assert not contact_is_associated(session, a1.allocator_id, c1.contact_id)
    assert not contact_is_associated(session, a1.allocator_id, c2.contact_id)
    assert verify_soft_deletion(session, jsonb)

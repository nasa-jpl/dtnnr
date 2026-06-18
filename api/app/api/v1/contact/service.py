from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlakeyset import select_page
from sqlalchemy import delete as sa_delete
from sqlalchemy import exc, insert, select

from app.models import Contact, ContactPhoneNumber

from .schemas import PhoneNumberReplaceSchema

if TYPE_CHECKING:
    from sqlakeyset import Page
    from sqlalchemy import Row, Tuple
    from sqlalchemy.orm import Session

logger = structlog.stdlib.get_logger()


def get(db_session: Session, contact_id: int) -> Contact | None:
    """Get a contact by id."""
    return db_session.scalar(select(Contact).where(Contact.contact_id == contact_id))


def query(
    db_session: Session, max_page_size: int, bookmark: str | None
) -> Page[Row[Tuple[Contact]]]:
    """Query contacts."""
    # TODO: support filters
    q = select(Contact).order_by(Contact.contact_name, Contact.contact_id)
    return select_page(db_session, q, per_page=max_page_size, page=bookmark)


def list_phone_numbers(
    db_session: Session, contact_id: int, max_page_size: int, bookmark: str | None
) -> Page[Row[Tuple[ContactPhoneNumber]]]:
    """List phone numbers of a contact."""
    q = (
        select(ContactPhoneNumber)
        .where(ContactPhoneNumber.contact_id == contact_id)
        .order_by(ContactPhoneNumber.order_pos)
    )
    return select_page(db_session, q, per_page=max_page_size, page=bookmark)


def replace_phone_numbers(
    db_session: Session, contact_id: int, phone_numbers: list[PhoneNumberReplaceSchema]
) -> None:
    """Replace phone numbers associated with the contact identified by
    `contact_id`.
    """
    db_session.execute(
        sa_delete(ContactPhoneNumber).where(ContactPhoneNumber.contact_id == contact_id)
    )
    if phone_numbers:
        db_session.execute(
            insert(ContactPhoneNumber),
            [
                {
                    'contact_id': contact_id,
                    'order_pos': i,
                    'phone_number': p_n.phone_number,
                    'preferred': p_n.preferred,
                }
                for p_n, i in zip(phone_numbers, range(len(phone_numbers)))
            ],
        )
    db_session.commit()


def create(db_session: Session, contact_name: str = None, email: str = None) -> Contact:
    """Create a contact in the `contact` table with the given name and email."""
    try:
        contact = Contact(contact_name=contact_name, email=email)
        db_session.add(contact)
        db_session.commit()
    except exc.IntegrityError as e:
        logger.exception(e._message())
        raise e
    except Exception as e:
        logger.exception('Unexpected error')
        raise e
    return contact


def update(
    db_session: Session, contact_id: int, contact_name: str, email: str
) -> Contact | None:
    """Update an existing record identified by `contact_id`."""
    contact = get(db_session, contact_id)
    if not contact:
        return None
    contact.contact_name = contact_name
    contact.email = email
    try:
        db_session.commit()
    except Exception as e:
        logger.exception('Unexpected error')
        raise e
    return contact


def delete(db_session: Session, contact_id: int) -> None:
    """Delete a contact from the `contact` table by its ID."""
    contact = get(db_session, contact_id)
    if not contact:
        return None
    db_session.delete(contact)
    db_session.commit()

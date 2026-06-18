from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlakeyset import select_page
from sqlalchemy import exc, exists, select

from app.models import Allocator, Contact, allocator_contact

from ..contact.service import get as contact_get

if TYPE_CHECKING:
    from sqlakeyset import Page
    from sqlalchemy import Row, Tuple
    from sqlalchemy.orm import Session

logger = structlog.stdlib.get_logger()


def get(db_session: Session, allocator_id: int) -> Allocator | None:
    """Get an allocator by its allocator ID."""
    return db_session.scalar(
        select(Allocator).where(Allocator.allocator_id == allocator_id)
    )


def query(
    db_session: Session, max_page_size: int, bookmark: str | None, reverse: bool = False
) -> Page[Row[Tuple[Allocator]]]:
    """Query allocators."""
    # TODO: support filters
    sort_clause = Allocator.allocator_id.desc() if reverse else Allocator.allocator_id
    q = select(Allocator).order_by(sort_clause)
    return select_page(db_session, q, per_page=max_page_size, page=bookmark)


def create(db_session: Session, allocator_id: int, allocator_name: str) -> Allocator:
    """Create an allocator in the `allocator` table."""
    try:
        allocator = Allocator(
            allocator_id=allocator_id,
            allocator_name=allocator_name,
        )
        db_session.add(allocator)
        db_session.commit()
    except exc.IntegrityError as e:
        # allocator_id / allocator_name is null or duplicate allocator_id
        logger.exception(e._message())
        raise e
    except Exception as e:
        logger.exception('Unexpected error')
        raise e
    return allocator


def update(
    db_session: Session,
    allocator_id: int,
    allocator_name: str,
    new_allocator_id: int | None = None,
) -> Allocator | None:
    """Update an existing allocator record identified by `allocator_id`.

    If new_allocator_id is None (default), we won't update the allocator
    record's allocator_id.
    """
    allocator = get(db_session, allocator_id)
    if not allocator:
        return None
    if new_allocator_id is not None:
        allocator.allocator_id = new_allocator_id
    allocator.allocator_name = allocator_name
    try:
        db_session.commit()
    except exc.IntegrityError as e:
        # allocator_name is null or duplicate allocator_id
        logger.exception(e._message())
        raise e
    except Exception as e:
        logger.exception('Unexpected error')
        raise e
    return allocator


def delete(db_session: Session, allocator_id: int) -> None:
    """Delete an allocator from the `allocator` table by its ID."""
    allocator = get(db_session, allocator_id)
    if not allocator:
        return None
    try:
        db_session.delete(allocator)
        db_session.commit()
    except Exception as e:
        logger.exception('Unexpected error')
        raise e


def list_contacts(
    db_session: Session, allocator_id: int, max_page_size: int, bookmark: str | None
) -> Page[Row[Tuple[Contact]]]:
    q = (
        select(Contact)
        .join(allocator_contact, Contact.contact_id == allocator_contact.c.contact_id)
        .where(allocator_contact.c.allocator_id == allocator_id)
        .order_by(Contact.contact_id)
    )
    return select_page(db_session, q, per_page=max_page_size, page=bookmark)


def associate_contact(
    db_session: Session, allocator_id: int, contact_id: int
) -> Contact:
    """Associates an existing contact with an allocator."""
    allocator = get(db_session, allocator_id)
    contact = contact_get(db_session, contact_id)
    try:
        allocator.contacts.append(contact)
        db_session.commit()
    except exc.IntegrityError as e:
        # Violating unique constraint on allocator_id and contact_id
        logger.exception(e._message())
        raise e
    except Exception:
        logger.exception(
            'Unexpected error', possible_reason='Non-existent allocator/contact'
        )
        raise
    return contact


def dissociate_contact(db_session: Session, allocator_id: int, contact_id: int) -> None:
    """Dissociates an existing contact with an allocator."""
    allocator = get(db_session, allocator_id)
    if not allocator:
        return None
    contact = contact_get(db_session, contact_id)
    if not contact:
        return None
    try:
        allocator.contacts.remove(contact)
        db_session.commit()
    except ValueError:
        logger.exception('Contact is not in allocator.contacts list')
        raise
    except Exception:
        logger.exception(
            'Unexpected error', possible_reason='Non-existent allocator/contact'
        )
        raise


def contact_is_associated(
    db_session: Session, allocator_id: int, contact_id: int
) -> bool:
    """Returns true if the contact identified by contact_id is
    associated with the allocator identified by allocator_id.
    """
    associated_in_db = db_session.scalar(
        select(
            exists().where(
                allocator_contact.c.allocator_id == allocator_id,
                allocator_contact.c.contact_id == contact_id,
            )
        )
    )
    allocator = get(db_session, allocator_id)
    if not allocator:
        return False
    contact = contact_get(db_session, contact_id)
    if not contact:
        return False
    associated_in_orm = contact in allocator.contacts
    if not associated_in_db:
        logger.info('Not associated in database')
        return False
    if not associated_in_orm:
        logger.error(
            'allocator & contact: not associated in ORM',
            note='If the ORM works correctly, this should never be logged',
        )
        return False
    return associated_in_db and associated_in_orm

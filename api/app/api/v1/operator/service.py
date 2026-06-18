from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlakeyset import select_page
from sqlalchemy import BigInteger, bindparam, exc, exists, select, text

from app.models import Contact, Operator, operator_contact

from ..contact.service import get as contact_get

if TYPE_CHECKING:
    from psycopg.types.multirange import Multirange
    from sqlakeyset import Page
    from sqlalchemy import Row, Tuple
    from sqlalchemy.orm import Session

logger = structlog.stdlib.get_logger()


def get(db_session: Session, operator_id: int) -> Operator | None:
    """Get an operator by its operator ID."""
    return db_session.scalar(
        select(Operator).where(Operator.operator_id == operator_id)
    )


def get_by_name(db_session: Session, operator_name: str) -> Operator | None:
    """Get an operator by its name."""
    return db_session.scalar(
        select(Operator).where(Operator.operator_name == operator_name)
    )


def query(
    db_session: Session, max_page_size: int, bookmark: str | None
) -> Page[Row[Tuple[Operator]]]:
    """Query operators."""
    # TODO: support filters
    q = select(Operator).order_by(Operator.operator_id)
    return select_page(db_session, q, per_page=max_page_size, page=bookmark)


def get_allocated_node_numbers(db_session: Session, operator_id: int) -> Multirange:
    """Returns allocated_node_numbers of the operator identified by
    operator_id as a psycopg.types.multirange.Multirange.
    """
    stmt = text(
        'SELECT allocated_node_numbers FROM operator WHERE operator_id = :operator_id;'
    ).bindparams(bindparam('operator_id', value=operator_id))
    try:
        res = db_session.scalar(stmt)
    except Exception as e:
        logger.exception('Unexpected error')
        raise e
    return res


def check_node_number_allocated(
    db_session: Session, operator_id: int, node_number: int
) -> bool:
    """Checks whether the passed `node_number` is within the range of
    `allocated_node_numbers` of the operator identified by
    `operator_id`.
    """
    stmt = text(
        'SELECT :node_number <@ (SELECT allocated_node_numbers FROM operator'
        ' WHERE operator_id = :operator_id)'
    ).bindparams(
        bindparam('node_number', value=node_number, type_=BigInteger),
        bindparam('operator_id', value=operator_id),
    )
    return db_session.scalar(stmt)


def create(db_session: Session, operator_name: str, allocator_id: int = 0) -> Operator:
    """Create an operator in the `operator` table.

    By default, allocated_node_numbers is an empty list (Postgres sees
    this as an empty multirange, i.e., {}).
    """
    try:
        operator = Operator(
            operator_name=operator_name,
            allocator_id=allocator_id,
        )
        db_session.add(operator)
        db_session.commit()
    except exc.IntegrityError as e:
        logger.exception(e._message())
        raise e
    except Exception as e:
        logger.exception('Unexpected error')
        raise e
    return operator


def union_allocated_node_numbers(
    db_session: Session,
    operator_id: int,
    lower: int = None,
    upper: int = None,
    bounds: str = '[)',
) -> Operator:
    """Computes the union on the allocated node numbers of the operator
    identified by `operator_id` with a range of numbers [lower, upper).
    By default, this range is inclusive lower, exclusive upper.

    Returns the updated operator.
    """
    stmt = text(
        'UPDATE operator'
        ' SET allocated_node_numbers = allocated_node_numbers'
        ' + int8multirange(int8range(:lower, :upper, :bounds))'
        ' WHERE operator_id = :operator_id;'
    ).bindparams(
        bindparam('lower', value=lower),
        bindparam('upper', value=upper),
        bindparam('bounds', value=bounds),
        bindparam('operator_id', value=operator_id),
    )
    try:
        db_session.execute(stmt)
        db_session.commit()
    except exc.DataError as e:
        # (psycopg.errors.DataException) range lower bound must be less than or
        # equal to range upper bound
        logger.exception(e._message())
        raise e
    except exc.IntegrityError as e:
        # Exclusion constraint violated when numbers overlap
        logger.exception(e._message())
        raise e
    except Exception as e:
        logger.exception('Unexpected error')
        raise
    return get(db_session, operator_id)


def intersection_allocated_node_numbers(
    db_session: Session,
    operator_id: int,
    lower: int = None,
    upper: int = None,
    bounds: str = '[)',
) -> Operator:
    """Computes the intersection on the allocated node numbers of the
    operator identified by `operator_id` with a range of numbers
    [lower, upper). By default, this range is inclusive lower, exclusive
    upper.

    Returns the updated operator.
    """
    stmt = text(
        'UPDATE operator'
        ' SET allocated_node_numbers = allocated_node_numbers'
        ' * int8multirange(int8range(:lower, :upper, :bounds))'
        ' WHERE operator_id = :operator_id;'
    ).bindparams(
        bindparam('lower', value=lower),
        bindparam('upper', value=upper),
        bindparam('bounds', value=bounds),
        bindparam('operator_id', value=operator_id),
    )
    try:
        db_session.execute(stmt)
        db_session.commit()
    except exc.DataError as e:
        # (psycopg.errors.DataException) range lower bound must be less than or
        # equal to range upper bound
        logger.exception(e._message())
        raise e
    except exc.ProgrammingError as e:
        # Error from violating node number trigger
        logger.exception(e._message())
        raise e
    except Exception as e:
        logger.exception('Unexpected error')
        raise
    # Should not have to worry about exclusion constraint violation b/c
    # intersection cannot increase elements in a set
    return get(db_session, operator_id)


def difference_allocated_node_numbers(
    db_session: Session,
    operator_id: int,
    lower: int = None,
    upper: int = None,
    bounds: str = '[)',
) -> Operator:
    """Computes the difference on the allocated node numbers of the
    operator identified by `operator_id` with a range of numbers
    [lower, upper). By default, this range is inclusive lower, exclusive
    upper.

    Returns the updated operator.
    """
    stmt = text(
        'UPDATE operator'
        ' SET allocated_node_numbers = allocated_node_numbers'
        ' - int8multirange(int8range(:lower, :upper, :bounds))'
        ' WHERE operator_id = :operator_id;'
    ).bindparams(
        bindparam('lower', value=lower),
        bindparam('upper', value=upper),
        bindparam('bounds', value=bounds),
        bindparam('operator_id', value=operator_id),
    )
    try:
        db_session.execute(stmt)
        db_session.commit()
    except exc.DataError as e:
        # (psycopg.errors.DataException) range lower bound must be less than or
        # equal to range upper bound
        logger.exception(e._message())
        raise e
    except exc.ProgrammingError as e:
        # Error from violating node number trigger
        logger.exception(e._message())
        raise e
    except Exception as e:
        logger.exception('Unexpected error')
        raise
    # Should not have to worry about exclusion constraint violation b/c
    # difference cannot increase elements in a set
    return get(db_session, operator_id)


def format_allocated_node_numbers(db_session: Session, operator_id: int):
    """Returns scalar from using SELECT allocated_node_numbers to get
    the psycopg format for multiranges.
    """
    stmt = text(
        'SELECT allocated_node_numbers FROM operator WHERE operator_id = :operator_id;'
    ).bindparams(bindparam('operator_id', value=operator_id))
    try:
        res = db_session.scalar(stmt)
    except Exception as e:
        logger.exception('Unexpected error')
        raise e
    return res


def union_allocated_node_numbers_dry_run(
    db_session: Session,
    operator_id: int,
    lower: int = None,
    upper: int = None,
    bounds: str = '[)',
) -> Multirange:
    """Returns what the operator's allocated_node_numbers would look
    like if a union were performed.
    Does not actually update allocated_node_numbers.

    The executed statement is of the form
    ```
    anymultirange + anymultirange
    ```
    where the first multirange is the operator's allocated_node_numbers
    and the second multirange is specified by this function's arguments.
    """
    stmt = text(
        'SELECT allocated_node_numbers'
        ' + int8multirange(int8range(:lower, :upper, :bounds))'
        ' FROM operator'
        ' WHERE operator_id = :operator_id;'
    ).bindparams(
        bindparam('lower', value=lower),
        bindparam('upper', value=upper),
        bindparam('bounds', value=bounds),
        bindparam('operator_id', value=operator_id),
    )
    try:
        res = db_session.scalar(stmt)
    except Exception as e:
        logger.exception('Unexpected error')
        raise e
    return res


def intersection_allocated_node_numbers_dry_run(
    db_session: Session,
    operator_id: int,
    lower: int = None,
    upper: int = None,
    bounds: str = '[)',
) -> Multirange:
    """Returns what the operator's allocated_node_numbers would look
    like if an intersection were performed.
    Does not actually update allocated_node_numbers.

    The executed statement is of the form
    ```
    anymultirange * anymultirange
    ```
    where the first multirange is the operator's allocated_node_numbers
    and the second multirange is specified by this function's arguments.
    """
    stmt = text(
        'SELECT allocated_node_numbers'
        ' * int8multirange(int8range(:lower, :upper, :bounds))'
        ' FROM operator'
        ' WHERE operator_id = :operator_id;'
    ).bindparams(
        bindparam('lower', value=lower),
        bindparam('upper', value=upper),
        bindparam('bounds', value=bounds),
        bindparam('operator_id', value=operator_id),
    )
    try:
        res = db_session.scalar(stmt)
    except Exception as e:
        logger.exception('Unexpected error')
        raise e
    return res


def difference_allocated_node_numbers_dry_run(
    db_session: Session,
    operator_id: int,
    lower: int = None,
    upper: int = None,
    bounds: str = '[)',
) -> Multirange:
    """Returns what the operator's allocated_node_numbers would look
    like if a difference were performed.
    Does not actually update allocated_node_numbers.

    The executed statement is of the form
    ```
    anymultirange - anymultirange
    ```
    where the first multirange is the operator's allocated_node_numbers
    and the second multirange is specified by this function's arguments.
    """
    stmt = text(
        'SELECT allocated_node_numbers'
        ' - int8multirange(int8range(:lower, :upper, :bounds))'
        ' FROM operator'
        ' WHERE operator_id = :operator_id;'
    ).bindparams(
        bindparam('lower', value=lower),
        bindparam('upper', value=upper),
        bindparam('bounds', value=bounds),
        bindparam('operator_id', value=operator_id),
    )
    try:
        res = db_session.scalar(stmt)
    except Exception as e:
        logger.exception('Unexpected error')
        raise e
    return res


def union_node_numbers_overlapping(
    db_session: Session,
    operator_id: int,
    lower: int = None,
    upper: int = None,
    bounds: str = '[)',
) -> list[int]:
    """Returns a list of operator_id of operators under the same
    allocator as the operator identified by the argument `operator_id`
    whose allocated_node_numbers overlaps with the to-be-updated
    operator's new allocated_node_numbers were a union to be performed.

    Does not actually update allocated_node_numbers.
    """
    operator = get(db_session, operator_id)
    stmt = text(
        'SELECT operator_id'
        ' FROM operator'
        ' WHERE operator_id <> :operator_id AND allocator_id = :allocator_id'
        ' AND allocated_node_numbers'
        ' && (SELECT allocated_node_numbers'
        ' + int8multirange(int8range(:lower, :upper, :bounds))'
        ' FROM operator WHERE operator_id = :operator_id)'
        ' ORDER BY operator_id'
    ).bindparams(
        bindparam('operator_id', value=operator_id),
        bindparam('allocator_id', value=operator.allocator_id),
        bindparam('lower', value=lower),
        bindparam('upper', value=upper),
        bindparam('bounds', value=bounds),
    )
    try:
        res = db_session.scalars(stmt).all()
    except Exception as e:
        logger.exception('Unexpected error')
        raise e
    return res


def intersection_node_numbers_not_covered(
    db_session: Session,
    operator_id: int,
    lower: int = None,
    upper: int = None,
    bounds: str = '[)',
) -> list[int]:
    """Returns the node numbers under the operator that are currently
    used which would not be covered if an intersection were to be
    performed on the operator's allocated_node_numbers.
    Does not actually update allocated_node_numbers.
    """
    stmt = text(
        'SELECT node_number'
        ' FROM node'
        ' WHERE operator_id = :operator_id AND'
        ' NOT(node_number <@ (SELECT allocated_node_numbers'
        ' * int8multirange(int8range(:lower, :upper, :bounds))'
        ' FROM operator WHERE operator_id = :operator_id))'
        ' ORDER BY node_number'
    ).bindparams(
        bindparam('operator_id', value=operator_id),
        bindparam('lower', value=lower),
        bindparam('upper', value=upper),
        bindparam('bounds', value=bounds),
    )
    try:
        res = db_session.scalars(stmt).all()
    except Exception as e:
        logger.exception('Unexpected error')
        raise e
    return res


def difference_node_numbers_not_covered(
    db_session: Session,
    operator_id: int,
    lower: int = None,
    upper: int = None,
    bounds: str = '[)',
) -> list[int]:
    """Returns the node numbers under the operator that are currently
    used which would not be covered if a difference were to be performed
    on the operator's allocated_node_numbers.
    Does not actually update allocated_node_numbers.
    """
    stmt = text(
        'SELECT node_number'
        ' FROM node'
        ' WHERE operator_id = :operator_id AND'
        ' NOT(node_number <@ (SELECT allocated_node_numbers'
        ' - int8multirange(int8range(:lower, :upper, :bounds))'
        ' FROM operator WHERE operator_id = :operator_id))'
        ' ORDER BY node_number'
    ).bindparams(
        bindparam('operator_id', value=operator_id),
        bindparam('lower', value=lower),
        bindparam('upper', value=upper),
        bindparam('bounds', value=bounds),
    )
    try:
        res = db_session.scalars(stmt).all()
    except Exception as e:
        logger.exception('Unexpected error')
        raise e
    return res


def update(
    db_session: Session, operator_id: int, operator_name: str, allocator_id: int
) -> Operator:
    """Updates an existing operator record identified by `operator_id`."""
    operator = get(db_session, operator_id)
    operator.operator_name = operator_name
    operator.allocator_id = allocator_id
    try:
        db_session.commit()
    except exc.IntegrityError as e:
        # Duplicate operator_name, non-existent allocator_id, overlapping
        # allocated_node_numbers, conflicting node_numbers from cascade update
        logger.exception(e._message())
        raise e
    except Exception as e:
        logger.exception('Unexpected error')
        raise e
    return operator


def operators_overlapping_allocated_node_numbers_under_new_allocator(
    db_session: Session, operator_id: int, allocator_id: int
) -> list[int]:
    """Returns a list of operator_id of the operators with
    allocated_node_numbers under the allocator identified by
    allocator_id which would conflict with the allocated_node_numbers of
    the operator identified by the passed operator_id.

    Updating operator.allocator_id could violate the exclusion
    constraint in operator because the to-be-updated operator's
    allocated_node_numbers could overlap with other operator's allocated
    numbers under the new allocator.
    """
    stmt = text(
        'SELECT operator_id'
        ' FROM operator'
        ' WHERE allocator_id = :new_allocator_id'
        ' AND allocated_node_numbers && (SELECT allocated_node_numbers'
        ' FROM operator'
        ' WHERE operator_id = :operator_id)'
        ' ORDER BY operator_id'
    ).bindparams(
        bindparam('new_allocator_id', value=allocator_id),
        bindparam('operator_id', value=operator_id),
    )
    try:
        res = db_session.scalars(stmt).all()
    except Exception as e:
        # It's just a SELECT statement, so don't know how it would error
        logger.exception('Unexpected error')
        raise e
    return res


def conflicting_node_numbers_under_new_allocator(
    db_session: Session, operator_id: int, allocator_id: int
) -> list[int]:
    """Returns a list of node numbers that would conflict due to
    updating the operator's (identified by operator_id) allocator_id to
    the passed allocator_id which causes a cascade and updates the
    allocator_id of the operator's nodes, thereby violating the unique
    constraint for FQNN.
    """
    stmt = text(
        'SELECT node_number'
        ' FROM node'
        ' WHERE allocator_id = :new_allocator_id'
        ' AND node_number IN (SELECT node_number FROM node'
        ' WHERE operator_id = :operator_id)'
        ' ORDER BY node_number'
    ).bindparams(
        bindparam('new_allocator_id', value=allocator_id),
        bindparam('operator_id', value=operator_id),
    )
    try:
        res = db_session.scalars(stmt).all()
    except Exception as e:
        # It's just a SELECT statement, so don't know how it would error
        logger.exception('Unexpected error')
        raise e
    return res


def delete(db_session: Session, operator_id: int) -> None:
    """Delete an operator from the `operator` table identified by
    operator_id.
    """
    operator = get(db_session, operator_id)
    if operator is None:
        return None
    db_session.delete(operator)
    try:
        db_session.commit()
    except Exception as e:
        logger.exception('Unexpected error')
        raise e


def list_contacts(
    db_session: Session, operator_id: int, max_page_size: int, bookmark: str | None
) -> Page[Row[Tuple[Contact]]]:
    q = (
        select(Contact)
        .join(operator_contact, Contact.contact_id == operator_contact.c.contact_id)
        .where(operator_contact.c.operator_id == operator_id)
        .order_by(Contact.contact_id)
    )
    return select_page(db_session, q, per_page=max_page_size, page=bookmark)


def associate_contact(
    db_session: Session, operator_id: int, contact_id: int
) -> Contact:
    """Associates an existing contact with an operator."""
    operator = get(db_session, operator_id)
    contact = contact_get(db_session, contact_id)
    try:
        operator.contacts.append(contact)
        db_session.commit()
    except exc.IntegrityError as e:
        # Violating unique constraint on operator_id and contact_id
        logger.exception(e._message())
        raise e
    except Exception:
        # Non-existent operator/contact
        logger.exception('Unexpected error')
        raise
    return contact


def dissociate_contact(db_session: Session, operator_id: int, contact_id: int) -> None:
    """Dissociates an existing contact with an operator."""
    operator = get(db_session, operator_id)
    contact = contact_get(db_session, contact_id)
    try:
        operator.contacts.remove(contact)
        db_session.commit()
    except ValueError:
        logger.exception('Contact is not in operator.contacts list')
        raise
    except Exception:
        logger.exception(
            'Unexpected error', possible_reason='Non-existent operator/contact'
        )
        raise


def contact_is_associated(
    db_session: Session, operator_id: int, contact_id: int
) -> bool:
    """Returns true if the contact identified by contact_id is
    associated with the operator identified by operator_id.
    """
    associated_in_db = db_session.scalar(
        select(
            exists().where(
                operator_contact.c.operator_id == operator_id,
                operator_contact.c.contact_id == contact_id,
            )
        )
    )
    operator = get(db_session, operator_id)
    if operator is None:
        return False
    contact = contact_get(db_session, contact_id)
    if contact is None:
        return False
    associated_in_orm = contact in operator.contacts
    if not associated_in_db:
        logger.info('Not associated in database')
        return False
    if not associated_in_orm:
        logger.error(
            'operator & contact: not associated in ORM',
            note='If the ORM works correctly, this should never be logged',
        )
        return False
    return associated_in_db and associated_in_orm

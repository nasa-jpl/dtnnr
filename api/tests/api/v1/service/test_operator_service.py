from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import exc, select

from tests.util import get_as_jsonb

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import Allocator, Contact, Node, Operator


def test_get(session: Session, operator: Operator):
    from app.api.v1.operator.service import get

    t_operator = get(session, operator.operator_id)
    assert t_operator == operator


def test_get_by_name(session: Session, operator: Operator):
    from app.api.v1.operator.service import get_by_name

    t_operator = get_by_name(session, operator.operator_name)
    assert t_operator == operator


def test_query(session: Session, operators: list[Operator]):
    from app.api.v1.operator.service import query

    t_operators = []
    page = query(session, 1, None)
    t_operators.extend([_ for (_,) in page])
    while page.paging.has_next:
        page = query(session, 1, page.paging.bookmark_next)
        t_operators.extend([_ for (_,) in page])

    for o in operators:
        assert o in t_operators


def test_check_node_number_allocated(session: Session, node: Node):
    from app.api.v1.operator.service import check_node_number_allocated

    assert check_node_number_allocated(session, node.operator_id, node.node_number)
    assert not check_node_number_allocated(
        session, node.operator_id, node.node_number + 20
    )


def test_create(session: Session, allocator: Allocator):
    from sqlalchemy import select

    from app.api.v1.operator.service import create
    from app.models import Operator

    operator_name = 'Test Create Service Operator'
    t_operator = create(session, operator_name, allocator.allocator_id)
    assert t_operator in (session.scalars(select(Operator)).all())
    assert t_operator.operator_name == operator_name
    assert t_operator.allocator == allocator


def test_union_allocated_node_numbers(session: Session, operator: Operator):
    from app.api.v1.operator.service import (
        check_node_number_allocated,
        union_allocated_node_numbers,
    )

    lower = 9000
    upper = 9050
    union_allocated_node_numbers(session, operator.operator_id, lower, upper)
    for i in range(lower, upper):
        assert check_node_number_allocated(session, operator.operator_id, i)

    # Infinite (unbounded) range
    with pytest.raises(exc.IntegrityError):
        union_allocated_node_numbers(session, operator.operator_id)
    assert not operator.allocated_node_numbers[0].upper_inf
    assert not operator.allocated_node_numbers[0].lower_inf


def test_intersection_allocated_node_numbers(session: Session, operator: Operator):
    from app.api.v1.operator.service import (
        check_node_number_allocated,
        intersection_allocated_node_numbers,
    )

    lower = operator.allocated_node_numbers[0].lower
    upper = operator.allocated_node_numbers[0].upper
    mid = lower + (upper - lower) // 2
    intersection_allocated_node_numbers(session, operator.operator_id, mid, upper)
    for i in range(mid, upper):
        assert check_node_number_allocated(session, operator.operator_id, i)

    # Intersection with infinite range should do nothing
    intersection_allocated_node_numbers(session, operator.operator_id)
    assert operator.allocated_node_numbers[0].lower == mid
    assert operator.allocated_node_numbers[0].upper == upper


def test_difference_allocated_node_numbers(session: Session, operator: Operator):
    from app.api.v1.operator.service import (
        check_node_number_allocated,
        difference_allocated_node_numbers,
    )

    lower = operator.allocated_node_numbers[0].lower
    upper = operator.allocated_node_numbers[0].upper
    mid = lower + (upper - lower) // 2
    difference_allocated_node_numbers(session, operator.operator_id, mid, upper)
    for i in range(mid, upper):
        assert not check_node_number_allocated(session, operator.operator_id, i)

    # Difference with infinite range should remove everything
    difference_allocated_node_numbers(session, operator.operator_id)
    assert not operator.allocated_node_numbers


def test_format_allocated_node_numbers(session: Session, operator: Operator):
    from app.api.v1.operator.service import format_allocated_node_numbers

    lower = operator.allocated_node_numbers[0].lower
    upper = operator.allocated_node_numbers[0].upper
    res = format_allocated_node_numbers(session, operator.operator_id)
    assert 'Range' not in str(res)
    assert f'[{lower}, {upper})' in str(res)


def test_union_allocated_node_numbers_dry_run(session: Session, operator: Operator):
    from app.api.v1.operator.service import union_allocated_node_numbers_dry_run

    lower = operator.allocated_node_numbers[0].lower
    upper = operator.allocated_node_numbers[0].upper

    # Union with [upper, upper * 2)
    res = union_allocated_node_numbers_dry_run(
        session, operator.operator_id, upper, upper * 2
    )
    # `res` is of type <class 'psycopg.types.multirange.Multirange'>
    # An element of `res` is of type <class 'psycopg.types.range.Range'>
    assert res[0].lower == lower
    assert res[0].upper == upper * 2
    assert res[0].lower == operator.allocated_node_numbers[0].lower
    assert res[0].upper != operator.allocated_node_numbers[0].upper
    assert res[0] != operator.allocated_node_numbers[0]


def test_intersection_allocated_node_numbers_dry_run(
    session: Session, operator: Operator
):
    from app.api.v1.operator.service import intersection_allocated_node_numbers_dry_run

    lower = operator.allocated_node_numbers[0].lower
    upper = operator.allocated_node_numbers[0].upper
    mid = lower + (upper - lower) // 2

    # Intersection with [mid, infinity)
    res = intersection_allocated_node_numbers_dry_run(
        session, operator.operator_id, mid
    )
    # `res` is of type <class 'psycopg.types.multirange.Multirange'>
    # An element of `res` is of type <class 'psycopg.types.range.Range'>
    assert res[0].lower == mid
    assert res[0].upper == upper
    assert res[0].lower != operator.allocated_node_numbers[0].lower
    assert res[0].upper == operator.allocated_node_numbers[0].upper
    assert res[0] != operator.allocated_node_numbers[0]


def test_difference_allocated_node_numbers_dry_run(
    session: Session, operator: Operator
):
    from app.api.v1.operator.service import difference_allocated_node_numbers_dry_run

    lower = operator.allocated_node_numbers[0].lower
    upper = operator.allocated_node_numbers[0].upper
    mid = lower + (upper - lower) // 2

    # Difference with [mid, infinity)
    res = difference_allocated_node_numbers_dry_run(session, operator.operator_id, mid)
    # `res` is of type <class 'psycopg.types.multirange.Multirange'>
    # An element of `res` is of type <class 'psycopg.types.range.Range'>
    assert res[0].lower == lower
    assert res[0].upper == mid
    assert res[0].lower == operator.allocated_node_numbers[0].lower
    assert res[0].upper != operator.allocated_node_numbers[0].upper
    assert res[0] != operator.allocated_node_numbers[0]


def test_union_node_numbers_overlapping(
    session: Session, operators_same_allocator: list[Operator]
):
    from psycopg.types.range import Range

    from app.api.v1.operator.service import (
        difference_allocated_node_numbers,
        union_node_numbers_overlapping,
    )

    o1 = operators_same_allocator[0]
    o2 = operators_same_allocator[1]
    lower = o2.allocated_node_numbers[0].lower
    upper = o2.allocated_node_numbers[0].upper
    mid = lower + (upper - lower) // 2
    # Split o2's allocated_node_numbers in half so results have a multirange
    # that isn't contiguous
    difference_allocated_node_numbers(session, o2.operator_id, mid - 1, mid + 1, '[]')
    # Union with (-infinity, infinity)
    res = union_node_numbers_overlapping(session, o1.operator_id)
    for o in operators_same_allocator[1:]:
        assert o.operator_id in res


def test_intersection_node_numbers_not_covered(
    session: Session, nodes_under_same_operator: list[Node]
):
    from app.api.v1.operator.service import (
        check_node_number_allocated,
        difference_node_numbers_not_covered,
    )

    operator = nodes_under_same_operator[0].operator
    n0_node_number = nodes_under_same_operator[0].node_number
    n1_node_number = nodes_under_same_operator[1].node_number
    # Intersection with [n0_node_number, n1_node_number)
    res = difference_node_numbers_not_covered(
        session, operator.operator_id, n0_node_number, n1_node_number
    )
    assert n0_node_number in res
    assert n1_node_number not in res
    # Dry run, so should still be allocated
    assert check_node_number_allocated(session, operator.operator_id, n0_node_number)
    assert check_node_number_allocated(session, operator.operator_id, n1_node_number)


def test_difference_node_numbers_not_covered(
    session: Session, nodes_under_same_operator: list[Node]
):
    from app.api.v1.operator.service import (
        check_node_number_allocated,
        difference_node_numbers_not_covered,
    )

    operator = nodes_under_same_operator[0].operator
    # Difference with (-infinity, infinity)
    res = difference_node_numbers_not_covered(session, operator.operator_id)
    for n in nodes_under_same_operator:
        # All node numbers aren't covered
        assert n.node_number in res
        # Dry run, so should still be allocated
        assert check_node_number_allocated(session, operator.operator_id, n.node_number)


def test_update(session: Session, operator: Operator, allocator: Allocator):
    from app.api.v1.operator.service import update

    old_operator_name = operator.operator_name
    assert operator.allocator != allocator
    update(
        session, operator.operator_id, old_operator_name[::-1], allocator.allocator_id
    )
    assert operator.operator_name != old_operator_name
    assert operator.allocator == allocator


def test_operators_overlapping_allocated_node_numbers_under_new_allocator(
    session: Session, operators_overlapping_allocated_node_numbers: list[Operator]
):
    from app.api.v1.operator.service import (
        operators_overlapping_allocated_node_numbers_under_new_allocator,
    )

    o1 = operators_overlapping_allocated_node_numbers[0]
    o2 = operators_overlapping_allocated_node_numbers[1]
    res = operators_overlapping_allocated_node_numbers_under_new_allocator(
        session, o1.operator_id, o2.allocator_id
    )
    assert o2.operator_id in res


def test_conflicting_node_numbers_under_new_allocator(
    session: Session, nodes_different_policy_same_node_number: list[Node]
):
    from app.api.v1.operator.service import conflicting_node_numbers_under_new_allocator

    # n1 follows Allocator -> Operator -> Node
    n1 = nodes_different_policy_same_node_number[0]
    # n2 follows Allocator -> Node
    n2 = nodes_different_policy_same_node_number[1]
    assert n1.node_number == n2.node_number
    res = conflicting_node_numbers_under_new_allocator(
        session, n1.operator_id, n2.allocator_id
    )
    assert n2.node_number in res


def test_delete(
    session: Session,
    operator: Operator,
    node: Node,
    node_without_operator_on_host_with_operator: Node,
):
    from app.api.v1.operator.service import delete, get
    from app.models import Host, Node, Operator
    from tests.util import verify_soft_deletion

    operator_id = operator.operator_id
    jsonb = get_as_jsonb(
        session, select(Operator).where(Operator.operator_id == operator_id)
    )
    delete(session, operator_id)
    assert not get(session, operator_id)
    assert verify_soft_deletion(session, jsonb)

    # Deleting an operator does not delete its nodes and hosts
    operator_id = node.operator_id
    host_id = node.host_id
    node_id = node.node_id
    jsonb = get_as_jsonb(
        session, select(Operator).where(Operator.operator_id == operator_id)
    )
    delete(session, operator_id)
    assert not get(session, operator_id)
    assert verify_soft_deletion(session, jsonb)
    assert session.scalar(select(Host).where(Host.host_id == host_id))
    assert session.scalar(select(Node).where(Node.host_id == host_id))

    # If an Allocator -> Node policy-following node is on a host with an
    # operator, deleting the operator should simply set host.operator_id to null.
    n2 = node_without_operator_on_host_with_operator
    operator_id = n2.host.operator_id
    host_id = n2.host_id
    node_id = n2.node_id
    jsonb = get_as_jsonb(
        session, select(Operator).where(Operator.operator_id == operator_id)
    )
    delete(session, operator_id)
    assert not get(session, operator_id)
    assert verify_soft_deletion(session, jsonb)
    assert session.scalar(select(Host).where(Host.host_id == host_id))
    assert (
        session.scalar(select(Host).where(Host.host_id == host_id)).operator_id is None
    )
    assert session.scalar(select(Node).where(Node.host_id == host_id))


def test_list_contacts(session: Session, operator_with_details: Operator):
    from app.api.v1.operator.service import list_contacts

    operator = operator_with_details
    contacts = []
    page = list_contacts(session, operator.operator_id, 1, None)
    contacts.extend([_ for (_,) in page])
    while page.paging.has_next:
        page = list_contacts(
            session, operator.operator_id, 1, page.paging.bookmark_next
        )
        contacts.extend([_ for (_,) in page])

    for c in operator.contacts:
        assert c in contacts


def test_associate_contact(
    session: Session, operator: Operator, contact_with_details: Contact
):
    from app.api.v1.operator.service import associate_contact

    contact = contact_with_details
    associate_contact(session, operator.operator_id, contact.contact_id)
    assert contact in operator.contacts
    assert operator in contact.operators


def test_dissociate_contact(
    session: Session, operator_with_details: Operator, allocator: Allocator
):
    from sqlalchemy import select

    from app.api.v1.operator.service import dissociate_contact
    from app.models import Contact, operator_contact
    from tests.util import verify_soft_deletion

    o = operator_with_details
    c1 = o.contacts[0]
    c2 = o.contacts[1]
    a = allocator
    a.contacts.append(c2)
    session.commit()

    assert len(o.contacts) > 1
    assert c1 in o.contacts
    jsonb = get_as_jsonb(
        session,
        select(operator_contact).where(
            operator_contact.c.operator_id == o.operator_id,
            operator_contact.c.contact_id == c1.contact_id,
        ),
    )
    dissociate_contact(session, o.operator_id, c1.contact_id)
    assert c1 not in o.contacts
    assert o.contacts  # not empty
    assert c1 not in session.scalars(select(Contact)).all()
    assert c2 in session.scalars(select(Contact)).all()
    assert verify_soft_deletion(session, jsonb)

    # But if the contact is still associated with an entity, it still exists
    assert c2 in a.contacts
    jsonb = get_as_jsonb(
        session,
        select(operator_contact).where(
            operator_contact.c.operator_id == o.operator_id,
            operator_contact.c.contact_id == c2.contact_id,
        ),
    )
    dissociate_contact(session, o.operator_id, c2.contact_id)
    assert c2 in a.contacts
    assert c2 in session.scalars(select(Contact)).all()
    assert verify_soft_deletion(session, jsonb)


def test_contact_is_associated(
    session: Session, operator: Operator, contacts_with_details: list[Contact]
):
    from sqlalchemy import select

    from app.api.v1.operator.service import contact_is_associated
    from app.models import operator_contact
    from tests.util import verify_soft_deletion

    o1 = operator
    c1 = contacts_with_details[0]
    c2 = contacts_with_details[1]
    o1.contacts.append(c1)
    o1.contacts.append(c2)
    session.commit()

    assert contact_is_associated(session, o1.operator_id, c1.contact_id)
    assert contact_is_associated(session, o1.operator_id, c2.contact_id)
    jsonb = get_as_jsonb(
        session,
        select(operator_contact).where(
            operator_contact.c.operator_id == o1.operator_id,
            operator_contact.c.contact_id == c1.contact_id,
        ),
    )
    o1.contacts.remove(c1)
    session.commit()
    assert not contact_is_associated(session, o1.operator_id, c1.contact_id)
    assert contact_is_associated(session, o1.operator_id, c2.contact_id)
    assert verify_soft_deletion(session, jsonb)

    jsonb = get_as_jsonb(
        session,
        select(operator_contact).where(
            operator_contact.c.operator_id == o1.operator_id,
            operator_contact.c.contact_id == c2.contact_id,
        ),
    )
    o1.contacts.remove(c2)
    session.commit()
    assert not contact_is_associated(session, o1.operator_id, c1.contact_id)
    assert not contact_is_associated(session, o1.operator_id, c2.contact_id)
    assert verify_soft_deletion(session, jsonb)

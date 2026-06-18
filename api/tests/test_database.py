from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import (
        Allocator,
        Contact,
        Host,
        Induct,
        InductIp,
        Node,
        Seat,
        SeatIp,
    )


def test_allocator_policy_allocator(session: Session, nodes: list[Node]):
    """Concerning updating and deleting from the `allocator` table."""
    from sqlalchemy import exc, select

    from app.models import Allocator, Node, Operator

    n1 = nodes[0]
    n2 = nodes[1]

    # Variable to make sure we don't reuse an allocator_id
    unique_allocator_id = max([n.allocator_id for n in nodes]) + 1

    # Allocator -> Operator -> Node
    # Updating allocator.allocator_id will update operator.allocator_id and
    # node.allocator_id. No other field should be updated.
    old_allocator_id = n1.allocator.allocator_id
    old_allocated_node_numbers = n1.operator.allocated_node_numbers
    old_node_number = n1.node_number
    assert n1.operator.allocator_id == old_allocator_id
    assert n1.operator.allocated_node_numbers == old_allocated_node_numbers
    assert n1.allocator_id == old_allocator_id
    assert n1.node_number == old_node_number
    # Update allocator.allocator_id
    n1.allocator.allocator_id = unique_allocator_id
    unique_allocator_id += 1
    session.commit()
    assert n1.allocator.allocator_id != old_allocator_id
    assert n1.operator.allocator_id != old_allocator_id
    assert n1.operator.allocated_node_numbers == old_allocated_node_numbers
    assert n1.allocator_id != old_allocator_id
    assert n1.node_number == old_node_number

    # Allocator -> Node
    # If the node doesn't have an operator, there's still the same effect from
    # updating allocator.allocator_id.
    # First, set n2.operator_id to null
    n2.operator_id = None
    session.commit()
    assert not n2.operator_id
    assert not n2.operator
    # Then update n2.allocator.allocator_id
    old_allocator_id = n2.allocator.allocator_id
    old_node_number = n2.node_number
    for o in n2.allocator.operators:
        assert o.allocator_id == old_allocator_id
    assert n2.allocator_id == old_allocator_id
    assert n2.node_number == old_node_number
    # Update allocator.allocator_id
    n2.allocator.allocator_id = unique_allocator_id
    unique_allocator_id += 1
    session.commit()
    assert n2.allocator.allocator_id != old_allocator_id
    for o in n2.allocator.operators:
        assert o.allocator_id != old_allocator_id
    assert n2.allocator_id != old_allocator_id
    assert n2.node_number == old_node_number

    # Cannot update allocator.allocator_id to null b/c primary keys are not null.
    with pytest.raises(exc.IntegrityError):
        n1.allocator.allocator_id = None
        session.commit()
    session.rollback()

    # Cannot update allocator.allocator_id to an existing allocator_id
    # b/c primary keys need to be unique.
    a1 = Allocator()
    a1.allocator_id = unique_allocator_id
    unique_allocator_id += 1
    a1.allocator_name = 'Program A'
    session.add(a1)
    session.commit()
    with pytest.raises(exc.IntegrityError):
        n1.allocator.allocator_id = a1.allocator_id
        session.commit()
    session.rollback()

    # Deleting an allocator will delete associated operators and nodes
    # Deleting an allocator is restricted since there are still associated
    # operators and nodes
    n1_allocator = n1.allocator
    n1_operator = n1.operator
    with pytest.raises(exc.IntegrityError):
        session.delete(n1.allocator)
        session.commit()
    session.rollback()
    assert n1_allocator in session.scalars(select(Allocator)).all()
    assert n1_operator in session.scalars(select(Operator)).all()
    assert n1 in session.scalars(select(Node)).all()


def test_allocator_policy_operator(session: Session, nodes: list[Node]):
    """Concerning updating and deleting from the `operator` table."""
    from sqlalchemy import bindparam, exc, select, text
    from sqlalchemy.dialects.postgresql import Range

    from app.models import Host, Node, Operator

    n1 = nodes[0]
    n2 = nodes[1]
    n3 = nodes[2]

    # Allocator -> Operator -> Node
    # Updating operator.allocator_id will update node.allocator_id. No other
    # field should be updated.
    old_allocator_id = n1.allocator.allocator_id
    old_allocated_node_numbers = n1.operator.allocated_node_numbers
    old_node_number = n1.node_number
    assert n1.operator.allocator_id == old_allocator_id
    assert n1.operator.allocated_node_numbers == old_allocated_node_numbers
    assert n1.allocator_id == old_allocator_id
    assert n1.node_number == old_node_number
    # Update operator.allocator_id
    n1.operator.allocator_id = n2.allocator_id
    session.commit()
    assert n1.allocator.allocator_id != old_allocator_id
    assert n1.operator.allocator_id != old_allocator_id
    assert n1.operator.allocated_node_numbers == old_allocated_node_numbers
    assert n1.allocator_id != old_allocator_id
    assert n1.node_number == old_node_number

    # FK violation if the new allocator_id does not exist
    with pytest.raises(exc.IntegrityError):
        n1.operator.allocator_id = max([n.allocator_id for n in nodes]) + 1
        session.commit()
    session.rollback()

    # Reset n1.operator.allocator_id
    n1.operator.allocator_id = old_allocator_id
    session.commit()

    # Error if the allocated_node_numbers already given out by the new allocator
    # overlaps with the current allocated_node_numbers of the operator that we
    # want to update.
    # Increase the range of allocated_node_numbers of another operator.
    t = Range(n1.node_number, n1.node_number, bounds='[]')
    n2.operator.allocated_node_numbers = n2.operator.allocated_node_numbers + [t]
    session.commit()
    # Cannot update n1.operator.allocator_id to null
    with pytest.raises(exc.IntegrityError):
        n1.operator.allocator_id = None
        session.commit()
    session.rollback()
    # Update n1.operator.allocator_id to new allocator. This violates the
    # exclusion constraint.
    with pytest.raises(exc.IntegrityError):
        n1.operator.allocator_id = n2.allocator_id
        session.commit()
    session.rollback()

    # If there already exists a node which has the node_number of one of the
    # operator's nodes and has the allocator_id of the new allocator_id we
    # want to give the operator, there will be a unique violation.
    # First, reset n2.operator.allocated_node_numbers.
    stmt = text(
        'UPDATE operator'
        ' SET allocated_node_numbers = allocated_node_numbers'
        " -int8multirange(int8range(:lower, :upper, '[]'))"
        ' WHERE operator_id = :operator_id;'
    ).bindparams(
        bindparam('lower', value=t.lower),  # , type_=BigInteger),
        bindparam('upper', value=t.upper),  # , type_=BigInteger),
        bindparam('operator_id', value=n2.operator_id),  # , type_=Integer)
    )
    session.execute(stmt)
    session.commit()
    # Create a node following the Allocator -> Node policy with the same
    # allocator as n2 and node_number as n1.
    node_no_operator = Node()
    node_no_operator.node_number = n1.node_number
    node_no_operator.allocator_id = n2.allocator_id
    node_no_operator.host_id = n2.host_id
    session.add(node_no_operator)
    session.commit()
    # Updating n1.operator.allocator_id will cascade and try to update
    # n1.allocator_id. But there already exists a record with n1's node_number
    # and the new allocator_id, so unique violation.
    with pytest.raises(exc.IntegrityError):
        n1.operator.allocator_id = n2.allocator_id
        session.commit()
    session.rollback()

    # node.node_number has a check constraint to be within [0, 2^32 - 1],
    # operator.allocated_node_numbers has a similar restriction.
    with pytest.raises(exc.IntegrityError):
        n3.operator.allocated_node_numbers = n3.operator.allocated_node_numbers + [
            Range(None, None)
        ]
        session.commit()
    session.rollback()
    assert not n3.operator.allocated_node_numbers[0].upper_inf
    assert not n3.operator.allocated_node_numbers[0].lower_inf

    # Updating allocated_node_numbers to overlap with another operator with the
    # same allocator_id violates the exclusion cosntraint.
    # Create another operator under n2.allocator_id
    operator_with_n2_allocator = Operator()
    operator_with_n2_allocator.allocator_id = n2.allocator_id
    operator_with_n2_allocator.operator_name = 'Mission A'
    # Use half of n2's first range for the new operator
    lower = n2.operator.allocated_node_numbers[0].lower
    upper = n2.operator.allocated_node_numbers[0].upper
    t = Range(lower, lower + (upper - lower) // 2, bounds='[]')
    operator_with_n2_allocator.allocated_node_numbers = [t]
    with pytest.raises(exc.IntegrityError):
        session.add(operator_with_n2_allocator)
        session.commit()
    session.rollback()

    # Shrinking allocated_node_numbers to remove a node_number that is
    # currently used by a node will violate the constraint trigger
    stmt = text(
        'UPDATE operator'
        ' SET allocated_node_numbers = allocated_node_numbers'
        "-int8multirange(int8range(:lower, :upper, '[]'))"
        ' WHERE operator_id = :operator_id;'
    ).bindparams(
        bindparam('lower', value=n3.node_number),  # , type_=BigInteger),
        bindparam('upper', value=n3.node_number),  # , type_=BigInteger),
        bindparam('operator_id', value=n3.operator_id),  # , type_=Integer)
    )
    with pytest.raises(exc.ProgrammingError):
        session.execute(stmt)
        session.commit()
    session.rollback()

    # Deleting an operator sets operator_id to null in associated hosts and nodes
    n2_operator = n2.operator
    n2_host = n2.host
    assert node_no_operator.host == n2.host
    assert not node_no_operator.operator
    session.delete(n2.operator)
    session.commit()
    assert n2_operator not in session.scalars(select(Operator)).all()
    assert n2_host in session.scalars(select(Host)).all()
    assert not n2_host.operator_id
    assert n2 in session.scalars(select(Node)).all()
    assert not n2.operator_id
    assert node_no_operator in session.scalars(select(Node)).all()


def test_allocator_policy_host(session: Session, nodes: list[Node]):
    """Concerning updating and deleting from the `host` table."""
    from sqlalchemy import bindparam, exc, select, text
    from sqlalchemy.dialects.postgresql import Range

    from app.models import Host, Node, Operator

    n1 = nodes[0]  # Allocator -> Operator -> Node
    n2 = nodes[1]  # Update to use Allocator -> Node policy but on n1.host
    n2.operator_id = None
    n2.host_id = n1.host_id
    session.commit()
    n3 = nodes[2]  # Allocator -> Operator -> Node
    n4 = nodes[3]  # Update both node and host to use Allocator -> Node policy
    n4.host.operator_id = None
    session.commit()
    # Setting host.operator_id to null cascades to associated nodes
    assert not n4.operator_id
    assert not n4.host.operator_id

    # Initially, this operator does not have any allocated node numbers
    operator_same_allocator_n1 = Operator()
    operator_same_allocator_n1.allocator_id = n1.allocator_id
    operator_same_allocator_n1.operator_name = 'Mission S'
    session.add(operator_same_allocator_n1)
    session.commit()

    # Consider updating host.operator_id when the new operator's allocator_id
    # matches the current host.operator's allocator_id.
    # Updating the host's operator_id cascades to n1. But n1.node_number is
    # not within the new operator's allocated node numbers, so this will
    # error.
    with pytest.raises(exc.ProgrammingError):
        n1.host.operator_id = operator_same_allocator_n1.operator_id
        session.commit()
    session.rollback()
    # You cannot just allocate the desired node number for this new operator
    # because it is already allocated to the previous allocator. So this
    # violates the exclusion constraint.
    t = Range(n1.node_number, n1.node_number, bounds='[]')
    with pytest.raises(exc.IntegrityError):
        operator_same_allocator_n1.allocated_node_numbers = (
            operator_same_allocator_n1.allocated_node_numbers + [t]
        )
        session.commit()
    session.rollback()
    # To update the host to this new operator, first set the n1.operator_id
    # to null. We need to make n1 follow the Allocator -> Node policy like n2.
    n1_operator = n1.operator  # So we can still refer to this operator
    n1.operator_id = None
    session.commit()
    # Then, remove n1.node_number from the current operator's range, and give
    # it to the new operator
    stmt = text(
        'UPDATE operator'
        ' SET allocated_node_numbers = allocated_node_numbers'
        "-int8multirange(int8range(:lower, :upper, '[]'))"
        ' WHERE operator_id = :operator_id;'
    ).bindparams(
        bindparam('lower', value=n1.node_number),  # , type_=BigInteger),
        bindparam('upper', value=n1.node_number),  # , type_=BigInteger),
        bindparam('operator_id', value=n1_operator.operator_id),  # , type_=Integer)
    )
    session.execute(stmt)
    session.commit()
    operator_same_allocator_n1.allocated_node_numbers = (
        operator_same_allocator_n1.allocated_node_numbers + [t]
    )
    session.commit()
    # Then update host.operator_id
    n1.host.operator_id = operator_same_allocator_n1.operator_id
    session.commit()
    # Neither n1 or n2 had an operator, so changing host.operator_id didn't
    # change their operator_id
    assert not n1.operator_id
    assert not n2.operator_id
    # Finish by updating n1.operator_id to the new operator
    n1.operator_id = operator_same_allocator_n1.operator_id
    session.commit()
    assert n1.operator == n1.host.operator
    assert n1.operator == operator_same_allocator_n1

    # Consider updating host.operator_id when the new operator's allocator_id
    # does not match the current host.operator's allocator_id.
    # Updating host.operator_id will cascade to n3.operator_id. This results in
    # a FK violation because (allocator_id, operator_id) is not present in
    # the `operator` table.
    with pytest.raises(exc.IntegrityError):
        n3.host.operator_id = operator_same_allocator_n1.operator_id
        session.commit()
    session.rollback()
    # We could update the operator to use the new operator's allocator, and this
    # just becomes the case of n1 and n2 that we considered above.
    # Or we can make n3.operator_id null (use the Allocator -> Node policy), then
    # the update on host.operator_id does not cascade.
    n3.operator_id = None
    session.commit()
    n3.host.operator_id = operator_same_allocator_n1.operator_id
    session.commit()
    assert n3.host.operator == operator_same_allocator_n1
    assert not n3.operator_id
    assert not n3.operator
    assert n3.allocator_id != operator_same_allocator_n1.allocator_id
    # If we want n3.operator_id to match the new operator, we need to update the
    # allocator_id to match, and then update node_number to be within the new
    # operator's allocated node numbers (or increase the operator's allocated
    # node numbers to include n3's node_number).
    # FK violation because (allocator_id, operator_id) not in operator table
    with pytest.raises(exc.IntegrityError):
        n3.operator_id = operator_same_allocator_n1.operator_id
        session.commit()
    session.rollback()
    n3.allocator_id = operator_same_allocator_n1.allocator_id
    session.commit()
    # Violates constraint trigger b/c n3.node_number is not within the operator's
    # allocated numbers
    with pytest.raises(exc.ProgrammingError):
        n3.operator_id = operator_same_allocator_n1.operator_id
        session.commit()
    session.rollback()
    # Won't bother with the rest b/c it's the same as in the n1 and n2 case

    # Consider an Allocator -> Node on a host without an operator.
    # Giving the host an operator will not update associated nodes.
    n4.host.operator_id = operator_same_allocator_n1.operator_id
    session.commit()
    assert n4.host.operator == operator_same_allocator_n1
    assert not n4.operator
    assert not n4.operator_id

    # Deleting a host should delete all nodes that use that host, regardless of
    # the Allocator policy.
    # Deleting a host should set host_id to null in associated nodes
    n1_and_n2_host = n1.host
    session.delete(n1.host)
    session.commit()
    assert n1_and_n2_host not in session.scalars(select(Host)).all()
    assert n1 in session.scalars(select(Node)).all()
    assert not n1.host_id
    assert n2 in session.scalars(select(Node)).all()
    assert not n2.host_id
    n3_host = n3
    session.delete(n3.host)
    session.commit()
    assert n3_host not in session.scalars(select(Host)).all()
    assert n3 in session.scalars(select(Node)).all()
    assert not n3.host_id
    n4_host = n4
    session.delete(n4.host)
    session.commit()
    assert n4_host not in session.scalars(select(Host)).all()
    assert n4 in session.scalars(select(Node)).all()


def test_allocator_policy_node(session: Session, nodes: list[Node]):
    """Concerning updating from the `node` table."""
    from sqlalchemy import exc, select
    from sqlalchemy.dialects.postgresql import Range

    from app.models import Allocator, Host, Node, Operator

    n1 = nodes[0]  # Allocator -> Operator -> Node
    n2 = nodes[1]  # Update to use Allocator -> Node policy but on n1.host
    n2.operator_id = None
    n2.host_id = n1.host_id
    session.commit()
    n3 = nodes[2]  # Allocator -> Operator -> Node
    n4 = nodes[3]  # Update both node and host to use Allocator -> Node policy
    n4.host.operator_id = None
    session.commit()
    # Setting host.operator_id to null cascades to associated nodes
    assert not n4.operator_id
    assert not n4.host.operator_id

    # Variable to make sure we don't reuse an allocator_id
    unique_allocator_id = max([n.allocator_id for n in nodes]) + 1

    # Create a new allocator
    a1 = Allocator()
    a1.allocator_id = unique_allocator_id
    unique_allocator_id += 1
    a1.allocator_name = 'Program AA'
    session.add(a1)
    session.commit()

    # Initially, this operator does not have any allocated node numbers
    operator_same_allocator_n1 = Operator()
    operator_same_allocator_n1.allocator_id = n1.allocator_id
    operator_same_allocator_n1.operator_name = 'Mission S'
    session.add(operator_same_allocator_n1)
    session.commit()

    # On a node using Allocator -> Operator -> Node policy, updating
    # node.allocator_id to a new ID is always restricted b/c it doesn't match
    # with node.operator.allocator_id.
    with pytest.raises(exc.IntegrityError):
        n1.allocator_id = a1.allocator_id
        session.commit()
    session.rollback()

    # Updating node.allocator_id using Allocator -> Node policy on a host with
    # an operator is fine
    assert n2.allocator_id != a1.allocator_id
    n2.allocator_id = a1.allocator_id
    session.commit()
    assert n2.allocator_id == a1.allocator_id

    # Updating node.allocator_id using Allocator -> Node policy on a host without
    # an operator is fine
    assert n4.allocator_id != a1.allocator_id
    n4.allocator_id = a1.allocator_id
    session.commit()
    assert n4.allocator_id == a1.allocator_id

    # Updating node.operator_id using Allocator -> Operator -> Node policy is
    # not allowed because it doesn't match with node.host.operator_id
    with pytest.raises(exc.IntegrityError):
        n1.operator_id = operator_same_allocator_n1.operator_id
        session.commit()
    session.rollback()

    # For a node using Allocator -> Node on a host with an operator, updating
    # node.operator_id != node.host.operator_id is not allowed.
    # At the moment, n2.allocator_id != n1.allocator_id, so this fails before
    # the mismatch with the host's operator occurs (because the new operator
    # is not under n2's allocator).
    with pytest.raises(exc.IntegrityError):
        n2.operator_id = operator_same_allocator_n1.operator_id
        session.commit()
    session.rollback()
    # Now update n2.allocator_id == n1.allocator_id, then the host mismatch
    # error occurs.
    n2.allocator_id = operator_same_allocator_n1.allocator_id
    session.commit()
    with pytest.raises(exc.IntegrityError):
        n2.operator_id = operator_same_allocator_n1.operator_id
        session.commit()
    session.rollback()

    # To update node.operator_id when policy is Allocator -> Operator -> Node,
    # the node's operator needs to match the host's operator, the node's
    # allocator needs to match the operator's allocator, and the node's
    # node number needs to be allocated to the operator.
    # Realistically, we probably want to change a node's host's operator and want
    # the host's nodes to also be under the new operator. I already covered this
    # in test_allocator_policy_host.

    # A more `node` specific test would be in the case of Allocator -> Node on
    # a host without an operator.
    # Create a new operator which is not under the node's allocator and which
    # doesn't have the node's node number allocated to it.
    o1 = Operator()
    o1.operator_name = 'Mission AAA'
    session.add(o1)
    session.commit()
    # This fails because the allocators do not match
    with pytest.raises(exc.IntegrityError):
        n4.operator_id = o1.operator_id
        session.commit()
    session.rollback()
    # Update operator.allocator_id to match
    o1.allocator_id = n4.allocator_id
    session.commit()
    # This still fails because the node's host does not have the same operator
    with pytest.raises(exc.IntegrityError):
        n4.operator_id = o1.operator_id
        session.commit()
    session.rollback()
    # Update host.operator_id to match
    n4.host.operator_id = o1.operator_id
    session.commit()
    # This still fails because the operator doesn't have the node's node number
    # allocated to it
    with pytest.raises(exc.ProgrammingError):
        n4.operator_id = o1.operator_id
        session.commit()
    session.rollback()
    # Allocate the node's node number to the operator
    o1.allocated_node_numbers = o1.allocated_node_numbers + [
        Range(n4.node_number, n4.node_number, bounds='[]')
    ]
    session.commit()
    # We can now update the node's operator_id
    n4.operator_id = o1.operator_id
    session.commit()
    assert n4.operator == o1

    # n3 follows the Allocator -> Operator -> Node policy.
    assert n3.operator
    assert n3.host.operator
    # Create another host under the same operator as n3.
    host_under_n3_operator = Host()
    host_under_n3_operator.operator_id = n3.operator_id
    host_under_n3_operator.hostname = 'Computer A'
    session.add(host_under_n3_operator)
    session.commit()
    # Updating n3 to this new host is allowed
    assert n3.host != host_under_n3_operator
    n3.host_id = host_under_n3_operator.host_id
    session.commit()
    assert n3.host == host_under_n3_operator
    # Updating n3 to a host under a different operator violates the FK constraint
    # because the operators do not match
    with pytest.raises(exc.IntegrityError):
        n3.host_id = n1.host_id
        session.commit()
    session.rollback()
    # Reset n4 and its host to be under no operator
    n4.host.operator_id = None
    session.commit()
    assert not n4.host.operator_id
    assert not n4.operator_id
    # Updating n3 to a host under no operator also violates the FK constraint
    # because the operators do not match
    with pytest.raises(exc.IntegrityError):
        n3.host_id = n4.host_id
        session.commit()
    session.rollback()

    # n2 follows Allocator -> Node, on a host with an operator
    assert not n2.operator
    assert n2.host.operator
    assert n1.host == n2.host
    # Create another host under the same operator as n1
    host_under_n1_operator = Host()
    host_under_n1_operator.operator_id = n1.operator_id
    host_under_n1_operator.hostname = 'Computer B'
    session.add(host_under_n1_operator)
    session.commit()
    # Can update to a host under the same operator
    n2.host_id = host_under_n1_operator.host_id
    session.commit()
    assert n2.host == host_under_n1_operator
    # n2.operator should never change from updating node.host
    assert not n2.operator
    # Can update to a host under a different operator
    assert n2.host.operator != n3.operator
    n2.host_id = n3.host_id
    session.commit()
    assert n2.host == n3.host
    assert not n2.operator
    # Can update to host under no operator
    assert not n4.host.operator
    assert n2.host.operator
    n2.host_id = n4.host_id
    session.commit()
    assert n2.host == n4.host
    assert not n2.operator

    # n4 follows Allocator -> Node, on a host without an operator
    assert not n4.operator
    assert not n4.host.operator
    # Like for n2, we're not restricted from changing hosts because n4's node
    # number is not given to it by an operator. So we can freely change hosts.
    # Update n4 to a host under an operator
    old_host_id = n4.host_id
    n4.host_id = n1.host_id
    session.commit()
    assert not n4.operator
    assert n4.host.operator
    # Reset n4 to its previous host
    n4.host_id = old_host_id
    session.commit()
    # Create a new host under no operator
    h1 = Host()
    h1.hostname = 'Computer C'
    session.add(h1)
    session.commit()
    # Update n4 to a host under no operator
    n4.host_id = h1.host_id
    session.commit()
    assert n4.host_id != old_host_id
    assert not n4.operator
    assert not n4.host.operator

    # Deleting a node should not delete any hosts, operators, or allocators
    n1_allocator = n1.allocator
    n1_operator = n1.operator
    n1_host = n1.host
    n1_node_number = n1.node_number
    session.delete(n1)
    session.commit()
    assert n1_allocator in session.scalars(select(Allocator)).all()
    assert n1_operator in session.scalars(select(Operator)).all()
    assert n1_host in session.scalars(select(Host)).all()
    assert n1 not in session.scalars(select(Node)).all()
    # n1's FQNN can now be used by another node
    n2.node_number = n1_node_number
    session.commit()
    assert n2.node_number == n1_node_number


def test_allocator_hierarchy(session: Session):
    from sqlalchemy import bindparam, exc, select, text
    from sqlalchemy.dialects.postgresql import Range

    from app.models import Allocator, Host, Node, Operator

    a1 = Allocator()
    a1.allocator_id = 1
    a1.allocator_name = 'Program A'
    session.add(a1)
    session.commit()
    o1 = Operator()
    o1.operator_name = 'Mission 1'
    o1.allocator_id = a1.allocator_id
    session.add(o1)
    session.commit()
    print(a1)
    print(o1)

    # Adding ranges
    print(o1.allocated_node_numbers + [Range(1, 3, bounds='[]')])
    # print([Range(1, 3, bounds='[]')])
    o1.allocated_node_numbers = o1.allocated_node_numbers + [Range(1, 3, bounds='[]')]
    o1.allocated_node_numbers = o1.allocated_node_numbers + [Range(5, 7, bounds='[]')]
    session.commit()
    print(o1)

    o1.allocated_node_numbers = (
        o1.allocated_node_numbers
        + [Range(4, 4, bounds='[]')]
        + [Range(12, 14, bounds='[]')]
    )
    session.commit()
    print(o1)

    # Check if our exclusion constraint prevents overlapping node numbers
    o2 = Operator()
    o2.operator_name = 'Mission 2'
    o2.allocator_id = a1.allocator_id
    session.add(o2)
    session.commit()
    print(o2)
    assert not o2.allocated_node_numbers  # empty
    print('-------------------')
    # o1 currently has [1, 7] union [12, 14]
    with pytest.raises(exc.IntegrityError):
        o2.allocated_node_numbers = o2.allocated_node_numbers + [
            Range(3, 5, bounds='[]')
        ]
        session.commit()
    session.rollback()
    assert not o2.allocated_node_numbers
    print(o1)
    print(o2)

    # Node with operator needs to be in range
    h1 = Host()
    h1.hostname = 'Host A'
    h1.operator_id = o1.operator_id
    session.add(h1)
    session.commit()

    n1 = Node()
    n1.node_number = 2
    n1.allocator_id = a1.allocator_id
    n1.operator_id = o1.operator_id
    n1.host_id = h1.host_id
    session.add(n1)
    session.commit()

    print(n1)
    print(n1.allocator)
    print(n1.operator)
    print(n1.host)
    assert n1.allocator == a1
    assert n1.operator == o1
    assert n1.host == h1

    # Inserting node with operator, out of range node number
    with pytest.raises(exc.ProgrammingError):
        n2 = Node()
        n2.node_number = 9
        n2.allocator_id = a1.allocator_id
        n2.operator_id = o1.operator_id
        n2.host_id = h1.host_id
        session.add(n2)
        session.commit()
    session.rollback()

    # Updating into out of range node number
    with pytest.raises(exc.ProgrammingError):
        n1.node_number = 9
        session.commit()
    session.rollback()

    # Update node.operator_id to null
    assert n1 in a1.nodes
    assert n1 in o1.nodes
    assert n1 in h1.nodes
    n1.operator_id = None
    session.commit()
    assert n1 in a1.nodes
    assert n1 not in o1.nodes
    assert n1 in h1.nodes

    # Node without operator, on host with operator
    n2 = Node()
    # Not under an operator, so we can use any unused node number
    # o1 is currently [1, 7] union [12, 14]
    # Using a number within o1's interval
    n2.node_number = 12
    n2.allocator_id = a1.allocator_id
    n2.host_id = h1.host_id
    session.add(n2)
    session.commit()
    print(n2)
    assert n2.allocator == a1
    assert not n2.operator
    assert n2.host == h1
    assert n2 in a1.nodes
    assert n2 not in o1.nodes
    assert n2 in h1.nodes
    # Using a number outside of o1's interval
    n2.node_number = 9
    session.commit()
    print(n2)
    assert n2.allocator == a1
    assert not n2.operator
    assert n2.host == h1
    assert n2 in a1.nodes
    assert n2 not in o1.nodes
    assert n2 in h1.nodes

    # Cannot violate unique constraint for FQNN
    with pytest.raises(exc.IntegrityError):
        n2.node_number = 2
        session.commit()
    session.rollback()

    # Update allocator.allocator_id
    a1.allocator_id = 15
    session.commit()
    assert o1.allocator_id == 15
    assert o2.allocator_id == 15
    assert n1.allocator_id == 15
    assert n2.allocator_id == 15

    # Node without operator on host without operator
    h2 = Host()
    h2.hostname = 'Host B'
    session.add(h2)
    session.commit()
    n3 = Node()
    n3.node_number = 8
    n3.allocator_id = a1.allocator_id
    n3.host_id = h2.host_id
    session.add(n3)
    session.commit()
    assert not h2.operator
    assert not n3.operator
    assert n3 in a1.nodes
    assert n3 not in o1.nodes
    assert n3 in h2.nodes

    # Add operator to an existing host
    h2.operator_id = o1.operator_id
    session.commit()
    assert h2.operator == o1
    assert n3 not in o1.nodes

    # Cannot change node's operator to a different operator of its host
    with pytest.raises(exc.IntegrityError):
        n3.operator_id = o2.operator_id
        session.commit()
    session.rollback()

    # If node has an operator, shouldn't be able to update its host to a host
    # on a different operator.
    h3 = Host()
    h3.hostname = 'Host C'
    h3.operator_id = o2.operator_id
    session.add(h3)
    session.commit()
    assert n3.host.operator != h3.operator
    with pytest.raises(exc.IntegrityError):
        n3.operator_id = h3.operator_id
        session.commit()
    session.rollback()

    # If a node has an operator, shouldn't be able to update its host to a host
    # without an operator.
    # Put n1 back under o1
    assert not n1.operator
    assert not n1.operator_id
    n1.operator_id = o1.operator_id
    session.commit()
    assert n1.operator
    # Then try to update n1.host_id to a host without an operator
    h4 = Host()
    h4.hostname = 'Host D'
    session.add(h4)
    session.commit()
    assert not h4.operator
    assert not h4.operator_id
    with pytest.raises(exc.IntegrityError):
        n1.host_id = h4.host_id
        session.commit()
    session.rollback()

    # If node has an operator, will updating operator's allocator_id affect node?
    a2 = Allocator()
    a2.allocator_id = 2
    a2.allocator_name = 'Program B'
    session.add(a2)
    session.commit()
    assert o1.allocator_id == a1.allocator_id
    assert n1.allocator_id == a1.allocator_id
    o1.allocator_id = a2.allocator_id
    session.commit()
    assert o1.allocator_id == a2.allocator_id
    assert n1.allocator_id == a2.allocator_id

    # Put o1 back under a1
    o1.allocator_id = a1.allocator_id
    session.commit()
    assert o1.allocator_id == a1.allocator_id
    assert n1.allocator_id == a1.allocator_id

    # If node doesn't have an operator and node's host doesn't have an operator,
    # should be able to update the node to any host regardless of whether the
    # new host has an operator or not.
    n4 = Node()
    n4.host_id = h4.host_id
    n4.node_number = 3
    session.add(n4)
    session.commit()
    assert n4.allocator_id == 0
    assert not n4.operator_id
    assert not n4.host.operator_id
    # Try updating n4's host to h3 which does have an operator
    n4.host_id = h3.host_id
    session.commit()
    assert n4.host_id == h3.host_id
    # Update n4's host back to h4 which doesn't have an operator
    n4.host_id = h4.host_id
    session.commit()
    assert n4.host_id == h4.host_id

    # Node without operator, on a host with an operator, with different
    # allocator_id than host's operator, then try to update
    # node's operator
    print(n1)
    print(n2)
    assert n1.host == h1
    assert n2.host == h1
    assert n1.operator_id
    assert not n2.operator_id
    # n1 = Node(node_id=1, node_number=2, allocator_id=15, operator_id=1, host_id=1)
    # n2 = Node(node_id=3, node_number=9, allocator_id=15, operator_id=None, host_id=1)
    # First, update n2.allocator_id to default allocator
    n2.allocator_id = 0
    session.commit()
    assert n2.allocator_id != h1.operator.allocator_id
    # Try updating n2.operator_id
    with pytest.raises(exc.IntegrityError):
        # Can't do this because there is no record in Operator with allocator_id = 0
        # and operator_id = 1
        n2.operator_id = h1.operator_id
        session.commit()
    session.rollback()
    # ORM tries to update both node.allocator_id and node.operator_id. This only errors
    # because node_number = 9 is not within the operator's allocated_node_numbers
    with pytest.raises(exc.ProgrammingError):
        n2.operator = h1.operator
        session.commit()
    session.rollback()

    # Updating h1.operator_id from o1 to o2 will also try to update nodes
    # under h1 which have an operator_id to o2.operator_id.
    # n1 is currently under operator_id = 1, so updating h1.operator_id will
    # cascade and try to update n1.operator_id. That will fire the trigger on
    # updating 'node', and the condition is violated because o2 doesn't have
    # any allocated_node_numbers but n1.node_number = 2.
    with pytest.raises(exc.ProgrammingError):
        h1.operator_id = o2.operator_id
        session.commit()
    session.rollback()

    # Try updating host.operator_id to NULL while the host has nodes that use
    # the old operator_id.
    assert h1.operator_id
    h1.operator_id = None
    session.commit()
    # Nodes should have their operator_id set to NULL as well
    assert not h1.operator_id
    for n in h1.nodes:
        assert not n.operator_id
    # Updating h1.operator_id should not make these nodes' operator_id become not null
    h1.operator_id = o2.operator_id
    session.commit()
    for n in h1.nodes:
        assert not n.operator_id
    # Set h1.operator_id back to null
    h1.operator_id = None
    session.commit()

    # Update node.operator through ORM
    # Exception because it violates node number trigger
    # n3 = Node(node_id=4, node_number=8, allocator_id=15, operator_id=None, host_id=2)
    # o1 = Operator(operator_id=1, allocator_id=15, allocated_node_numbers={[1,8),[12,15)]})
    with pytest.raises(exc.ProgrammingError):
        n3.operator = o1
        session.commit()
    session.rollback()
    n3.node_number = 3
    n3.operator = o1
    session.commit()
    assert n3 in o1.nodes
    assert n3.node_number == 3
    assert n3.operator == o1

    # Update node.host through ORM
    print(h1.nodes)
    assert not h1.operator
    with pytest.raises(exc.IntegrityError):
        # This will try to set n3.host_id to 1, but this violates a FK constraint
        # b/c there's no record of host_id = 1 and operator_id = 1 in 'host'
        n3.host = h1
        session.commit()
    session.rollback()
    # First need to update h1's operator to match
    for n in h1.nodes:
        assert not n.operator
    assert not h1.operator
    h1.operator = n3.operator
    session.commit()
    # Only h1.operator updates, not any of h1's nodes
    assert h1.operator == n3.operator
    for n in h1.nodes:
        assert not n.operator
    # Now we can update n3.host
    n3.host = h1
    session.commit()
    assert n3 not in h2.nodes
    assert n3 in h1.nodes
    print(h1.nodes)

    # Update node.allocator through ORM
    a3 = Allocator()
    a3.allocator_id = 3
    a3.allocator_name = 'Program C'
    session.add(a3)
    session.commit()
    n2.allocator = a3
    session.commit()
    assert n2 in a3.nodes

    print('###########')
    print(o1.nodes)
    print(o1.allocated_node_numbers)
    # Currently, o1 has 1 node, with node_number = 3 and
    # allocated_node_numbers = [1, 7] union [12, 14].
    # Set difference of [3, 3] in allocated_node_numbers
    t = Range(3, 3, bounds='[]')
    print(t.lower)
    print(t.upper)
    print(t.bounds)
    # Implement this on API level. We always use bounds='[]', so check if
    # t.lower == t.upper, if so then we use raw SQL
    # Actually, might as well just use this code for any range
    with pytest.raises(exc.ProgrammingError):
        # text() treats its input as trusted SQL text, make sure we validate input
        stmt = text(
            'UPDATE operator'
            ' SET allocated_node_numbers = allocated_node_numbers'
            "-int8multirange(int8range(:lower, :upper, '[]'))"
            ' WHERE operator_id = :operator_id;'
        ).bindparams(
            # Don't need type_ argument, SQLAlchemy knows to make it BIGINT if it's too large
            # Having type_ also means, if someone puts a string in value, we get a exc.DataError
            # rather than exc.ProgrammingError.
            # Should probably check for that outside of here anyway.
            bindparam('lower', value=t.lower),  # , type_=BigInteger),
            bindparam('upper', value=t.upper),  # , type_=BigInteger),
            bindparam('operator_id', value=o1.operator_id),  # , type_=Integer)
        )
        session.execute(stmt)
        session.commit()
    session.rollback()
    # Alternatively, we can do this for any range that doesn't contain only 1 element.
    # (Trying to do this on SQLAlchemy 2.0.20 with a range with only 1 element raises
    # ValueError: Subtracting a strictly inner range is not implemented, so we'd make
    # this conditional on t.lower != t.upper)
    # If we have performance issues with the code above, should measure to see if this
    # is any better.
    # t = Range(3, 3, bounds='[]')
    # Without list comprehension:
    # x = []
    # for r in o1.allocated_node_numbers:
    #     if r.overlaps(t):
    #         x.append(r.difference(t))
    #     else:
    #         x.append(r)
    # o1.allocated_node_numbers = x
    # With list comprehension:
    # o1.allocated_node_numbers = [r.difference(t) if r.overlaps(t) else r for r in o1.allocated_node_numbers]
    # session.commit()

    # Should be okay to remove unused allocated node numbers
    t = Range(5, 20, bounds='[]')
    stmt = text(
        'UPDATE operator'
        ' SET allocated_node_numbers = allocated_node_numbers'
        "-int8multirange(int8range(:lower, :upper, '[]'))"
        ' WHERE operator_id = :operator_id;'
    ).bindparams(
        bindparam('lower', value=t.lower),  # , type_=BigInteger),
        bindparam('upper', value=t.upper),  # , type_=BigInteger),
        bindparam('operator_id', value=o1.operator_id),  # , type_=Integer)
    )
    session.execute(stmt)
    session.commit()
    print('HERE-----------------------')
    print(o1)
    # o1.allocated_node_numbers should just be {[1, 4]} now
    assert not o1.allocated_node_numbers[0].contains(t)

    # Adding node numbers should be fine
    o1.allocated_node_numbers = o1.allocated_node_numbers + [Range(5, 7, bounds='[]')]
    session.commit()
    # o1.allocated_node_numbers should be {[1, 7]} now
    assert o1.allocated_node_numbers[0] == Range(1, 7, bounds='[]')

    # Setting o1.allocated_node_numbers to None violates not null constraint
    with pytest.raises(exc.IntegrityError):
        o1.allocated_node_numbers = None
        session.commit()
    session.rollback()

    # To remove allocations, set allocated_node_numbers to an empty list
    # But we can't do this at the moment because a node is still using one of
    # the operator's allocated numbers
    with pytest.raises(exc.ProgrammingError):
        o1.allocated_node_numbers = []
        session.commit()
    session.rollback()

    # Set the operator's node's operator_id to null
    for n in o1.nodes:
        n.operator_id = None
    session.commit()

    o1.allocated_node_numbers = []
    session.commit()

    # And we can add node numbers again
    o1.allocated_node_numbers = o1.allocated_node_numbers + [Range(1, 5, bounds='[]')]
    session.commit()
    # o1.allocated_node_numbers should be {[1, 5]} now
    assert o1.allocated_node_numbers[0] == Range(1, 5, bounds='[]')

    # Cannot make range infinite
    with pytest.raises(exc.IntegrityError):
        o1.allocated_node_numbers = o1.allocated_node_numbers + [Range(None, None)]
        session.commit()
    session.rollback()
    assert not o1.allocated_node_numbers[0].upper_inf
    assert not o1.allocated_node_numbers[0].lower_inf

    # Allocate full range
    o1.allocated_node_numbers = o1.allocated_node_numbers + [Range(0, 2**32 - 1)]
    session.commit()

    # Now it shouldn't be possible to allocate any numbers to another operator
    with pytest.raises(exc.IntegrityError):
        o2.allocated_node_numbers = o2.allocated_node_numbers + [
            Range(200, 300, bounds='[]')
        ]
        session.commit()
    session.rollback()

    # print(f'a1.nodes = {a1.nodes}')
    # print(f'o1.nodes = {o1.nodes}')
    # print(f'h1.nodes = {h1.nodes}')

    # Deleting allocator is restricted if there are operators and nodes
    # still associated with the allocator
    print(session.scalars(select(Allocator)).all())
    print(session.scalars(select(Operator)).all())
    print(session.scalars(select(Host)).all())
    print(session.scalars(select(Node)).all())
    with pytest.raises(exc.IntegrityError):
        session.delete(a1)
        session.commit()
    session.rollback()
    assert a3 in session.scalars(select(Allocator)).all()
    assert a1 in session.scalars(select(Allocator)).all()
    assert o1 in session.scalars(select(Operator)).all()
    assert o2 in session.scalars(select(Operator)).all()
    assert h1 in session.scalars(select(Host)).all()
    assert h2 in session.scalars(select(Host)).all()
    assert n1 in session.scalars(select(Node)).all()
    assert n2 in session.scalars(select(Node)).all()
    assert n3 in session.scalars(select(Node)).all()
    print(session.scalars(select(Allocator)).all())
    print(session.scalars(select(Operator)).all())
    print(session.scalars(select(Host)).all())
    print(session.scalars(select(Node)).all())


def test_contact_orphans(session: Session, contact: Contact):
    from sqlalchemy import select

    from app.models import (
        Allocator,
        Contact,
        Operator,
        allocator_contact,
        operator_contact,
    )

    # Test if triggers on allocator and operator to delete orphan contact
    # records work correctly.
    a1 = Allocator()
    a1.allocator_id = 34
    a1.allocator_name = 'a1'
    o1 = Operator()
    o1.operator_name = 'o1'
    a1.contacts.append(contact)
    o1.contacts.append(contact)
    session.add_all([a1, o1])
    session.commit()

    # A contact, allocator, and operator are initially all present
    assert contact in session.scalars(select(Contact)).all()
    assert a1 in session.scalars(select(Allocator)).all()
    assert o1 in session.scalars(select(Operator)).all()
    assert a1 in contact.allocators
    assert o1 in contact.operators
    assert a1.allocator_id in session.execute(select(allocator_contact)).first()
    assert o1.operator_id in session.execute(select(operator_contact)).first()

    session.delete(a1)
    session.commit()
    # After deleting the allocator, the contact should still exist, and the
    # record from the allocator_contact association table is deleted
    assert contact in session.scalars(select(Contact)).all()
    assert a1 not in session.scalars(select(Allocator)).all()
    assert o1 in session.scalars(select(Operator)).all()
    assert a1 not in contact.allocators
    assert o1 in contact.operators
    assert not session.execute(select(allocator_contact)).first()
    assert o1.operator_id in session.execute(select(operator_contact)).first()

    session.delete(o1)
    session.commit()
    # After deleting the operator, the contact is no longer in use and should
    # be deleted.
    assert contact not in session.scalars(select(Contact)).all()
    assert o1 not in session.scalars(select(Operator)).all()
    assert not session.execute(select(operator_contact)).first()


def test_contact_allocator_dissociation(
    session: Session, contact: Contact, allocators: list[Allocator]
):
    from sqlalchemy import select

    from app.models import Allocator, Contact

    a1 = allocators[0]
    a2 = allocators[1]
    # Bidirectional, can append either at allocator or contact side
    a1.contacts.append(contact)
    contact.allocators.append(a2)
    session.commit()

    a1.contacts.remove(contact)
    session.commit()
    # contact still exists because its used by a2
    assert contact in session.scalars(select(Contact)).all()
    assert a1 in session.scalars(select(Allocator)).all()
    assert a2 in session.scalars(select(Allocator)).all()

    # Removing from association table fails because it's not there
    with pytest.raises(ValueError):
        a1.contacts.remove(contact)
        session.commit()
    session.rollback()

    a2.contacts.remove(contact)
    session.commit()
    assert contact not in session.scalars(select(Contact)).all()
    assert a1 in session.scalars(select(Allocator)).all()
    assert a2 in session.scalars(select(Allocator)).all()


def test_induct(session: Session, host: Host, nodes: list[Node]):
    from sqlalchemy import exc, select

    from app.models import ClProtocol, CommDirectionEnumInternal, Host, Induct, Link

    n1 = nodes[0]
    n2 = nodes[1]

    # Make the CL protocol and link usable by the node
    cl_p1 = ClProtocol(node_id=n1.node_id, cl_protocol_name='foo', cl_protocol_class=10)
    cl_p2 = ClProtocol(node_id=n2.node_id, cl_protocol_name='bar', cl_protocol_class=8)
    cl_p3 = ClProtocol(node_id=n1.node_id, cl_protocol_name='baz', cl_protocol_class=2)
    link = Link(host_id=n1.host_id, direction=CommDirectionEnumInternal.FULL_DUPLEX)
    session.add_all([cl_p1, cl_p2, cl_p3, link])

    induct = Induct(type=None, node_id=n1.node_id, host_id=n1.host_id)
    host.operator = n1.operator

    # Create an induct without CL protocol or induct link
    session.add(induct)
    session.commit()
    assert not induct.cl_protocol_id
    assert not induct.links

    # Induct with CL protocol, w/o induct link
    induct.cl_protocol = cl_p1
    session.commit()
    assert induct.cl_protocol_id == cl_p1.cl_protocol_id
    assert not induct.links

    # Induct with both CL protocol and induct link
    induct.cl_protocol = cl_p1
    induct.links.append(link)
    session.commit()

    # Cannot insert with link from different host
    with pytest.raises(exc.IntegrityError):
        induct2 = Induct(
            type=None,
            node_id=n2.node_id,
            host_id=n2.host_id,
            cl_protocol_id=cl_p2.cl_protocol_id,
        )
        induct2.links.append(link)
        session.add(induct2)
        session.commit()
    session.rollback()
    assert induct2 not in session.scalars(select(Induct)).all()

    # Changing induct's node directly violates FK constraint
    with pytest.raises(exc.IntegrityError):
        induct.node_id = -1
        session.commit()
    session.rollback()
    assert induct.node_id != -1

    # You also can't update the node through protocols, if you want to
    # change an induct / protocol node, create a new record in the
    # induct / protocol tables and copy old stuff over.
    with pytest.raises(exc.IntegrityError):
        cl_p1.node_id = -1
        session.commit()
    session.rollback()
    assert cl_p1.node_id != -1

    # Inconsistency from trying to change induct's CL protocol to protocol
    # on different node.
    with pytest.raises(exc.IntegrityError):
        induct.cl_protocol = cl_p2
        session.commit()
    session.rollback()
    assert induct.cl_protocol != cl_p2

    # But this is doable with a protocol on the same node
    induct.cl_protocol = cl_p3
    session.commit()
    assert induct.cl_protocol != cl_p1
    assert induct.cl_protocol == cl_p3

    # We cannot switch a node's host to another host when an induct still
    # references a child on the old host.
    with pytest.raises(exc.IntegrityError):
        n1.host = host
        session.commit()
    session.rollback()
    assert n1.host != host
    # Cannot change host of link when still used by induct
    with pytest.raises(exc.IntegrityError):
        link.host = host
        session.commit()
    session.rollback()
    assert link.host != host
    # Cannot change host_id of induct
    with pytest.raises(exc.IntegrityError):
        induct.host_id = host.host_id
        session.commit()
    session.rollback()
    assert induct.host_id != host.host_id

    # To switch a node's host, we must delete the induct first
    # (Or disassociate the induct from the host)
    session.delete(induct)
    session.commit()
    assert induct not in session.scalars(select(Induct)).all()
    # Deleting the induct doesn't delete the link or CL protocol
    assert link in session.scalars(select(Link)).all()
    assert cl_p3 in session.scalars(select(ClProtocol)).all()
    new_host = Host()
    new_host.hostname = 'AAAAAAAAAAAAAA'
    new_host.operator = n1.operator
    n1.host = new_host
    session.commit()
    assert n1.host_id == new_host.host_id
    assert not n1.inducts
    assert cl_p1.node == n1

    # Deleting the link does not delete the induct
    link = Link(host_id=n1.host_id, direction=CommDirectionEnumInternal.FULL_DUPLEX)
    induct = Induct(
        type=None,
        node_id=n1.node_id,
        host_id=n1.host_id,
        cl_protocol=cl_p1,
        links=[link],
    )
    session.add_all([link, induct])
    session.commit()
    session.delete(link)
    session.commit()
    assert not induct.links
    assert induct.host_id == n1.host_id

    # Deleting CL protocol sets id to NULL, but induct still exists
    session.delete(cl_p1)
    session.commit()
    assert not induct.cl_protocol
    assert induct
    assert induct.host_id == n1.host_id

    # Deleting node should delete induct
    session.delete(n1)
    session.commit()
    assert induct not in session.scalars(select(Induct)).all()


def test_induct_ip(session: Session, node: Node, host: Host):
    from sqlalchemy import exc, select

    from app.models import Induct, InductIp

    induct = Induct(type='ip', node=node, host_id=node.host_id)

    host.operator = node.operator

    session.add(induct)
    session.commit()

    # Can create an induct_ip
    induct_ip = InductIp(induct_id=induct.induct_id, host_id=induct.host_id)
    session.add(induct_ip)
    session.commit()

    # Trying to change induct_ip's host violates FK constraint
    with pytest.raises(exc.IntegrityError):
        induct_ip.host_id = host.host_id
        session.commit()
    session.rollback()
    assert induct_ip.host_id != host.host_id

    # Cannot use IP address of different host on induct_ip
    with pytest.raises(exc.IntegrityError):
        induct_ip.destination = host.destinations[0]
        session.commit()
    session.rollback()
    assert not induct_ip.destination

    # IP address of host
    ip = node.host.destinations[0]
    induct_ip.destination = ip
    session.commit()
    assert induct_ip.destination_id == node.host.destinations[0].destination_id

    # Deleting IP address should set induct_ip.destination to NULL but not
    # change induct_ip.host_id
    session.delete(ip)
    session.commit()
    session.refresh(induct_ip)
    assert not induct_ip.destination_id
    assert induct_ip.host_id

    # Deleting induct_ip does not delete from parent table `induct`
    assert session.scalars(
        select(Induct).where(Induct.induct_id == induct_ip.induct_id)
    ).one()
    session.delete(induct_ip)
    session.commit()
    assert session.scalars(
        select(Induct).where(Induct.induct_id == induct.induct_id)
    ).one()


def test_seat(session: Session, host: Host, nodes: list[Node]):
    from sqlalchemy import exc, select

    from app.models import CommDirectionEnumInternal, Host, Link, Seat

    n1 = nodes[0]
    n2 = nodes[1]

    # Make a link usable by the node
    link = Link(host_id=n1.host_id, direction=CommDirectionEnumInternal.FULL_DUPLEX)
    session.add(link)

    seat = Seat(type=None, node_id=n1.node_id, host_id=n1.host_id)
    host.operator = n1.operator
    session.add(seat)
    session.commit()
    assert not seat.links

    # Seat with link
    seat.links.append(link)
    session.commit()
    assert link in seat.links

    # Cannot insert with link from different host
    with pytest.raises(exc.IntegrityError):
        seat2 = Seat(
            type=None,
            node_id=n2.node_id,
            host_id=n2.host_id,
            links=[link],
        )
        session.add(seat2)
        session.commit()
    session.rollback()
    assert seat2 not in session.scalars(select(Seat)).all()

    # Changing seat's node directly violates FK constraint
    with pytest.raises(exc.IntegrityError):
        seat.node_id = -1
        session.commit()
    session.rollback()
    assert seat.node_id != -1

    # We cannot switch a node's host to another host when a seat still
    # references a child on the old host.
    with pytest.raises(exc.IntegrityError):
        n1.host = host
        session.commit()
    session.rollback()
    assert n1.host != host
    # Cannot change host of link when still used by seat
    with pytest.raises(exc.IntegrityError):
        link.host = host
        session.commit()
    session.rollback()
    assert link.host != host
    # Cannot change host_id of seat
    with pytest.raises(exc.IntegrityError):
        seat.host_id = host.host_id
        session.commit()
    session.rollback()
    assert seat.host_id != host.host_id

    # To switch a node's host, we must delete the seat first
    # (Or disassociate the seat from the host)
    session.delete(seat)
    session.commit()
    assert seat not in session.scalars(select(Seat)).all()
    # Deleting the induct doesn't delete the link
    assert link in session.scalars(select(Link)).all()
    new_host = Host()
    new_host.hostname = 'AAAAAAAAAAAAAA'
    new_host.operator = n1.operator
    n1.host = new_host
    session.commit()
    assert n1.host_id == new_host.host_id
    assert not n1.seats

    # Deleting the link does not delete the seat
    link = Link(host_id=n1.host_id, direction=CommDirectionEnumInternal.FULL_DUPLEX)
    seat = Seat(type=None, node_id=n1.node_id, host_id=n1.host_id, links=[link])
    session.add_all([link, seat])
    session.commit()
    session.delete(link)
    session.commit()
    assert not seat.links
    assert seat.host_id == n1.host_id

    # Deleting node should delete seat
    session.delete(n1)
    session.commit()
    assert seat not in session.scalars(select(Seat)).all()


def test_seat_ip(session: Session, node: Node, host: Host):
    from sqlalchemy import exc, select

    from app.models import Seat, SeatIp

    seat = Seat(type='ip', node=node, host_id=node.host_id)

    host.operator = node.operator

    session.add(seat)
    session.commit()

    # Can create an seat_ip
    seat_ip = SeatIp(seat_id=seat.seat_id, host_id=seat.host_id)
    session.add(seat_ip)
    session.commit()

    # Trying to change seat_ip's host violates FK constraint
    with pytest.raises(exc.IntegrityError):
        seat_ip.host_id = host.host_id
        session.commit()
    session.rollback()
    assert seat_ip.host_id != host.host_id

    # Cannot use IP address of different host on seat_ip
    with pytest.raises(exc.IntegrityError):
        seat_ip.destination = host.destinations[0]
        session.commit()
    session.rollback()
    assert not seat_ip.destination

    # IP address of host
    ip = node.host.destinations[0]
    seat_ip.destination = ip
    session.commit()
    assert seat_ip.destination_id == node.host.destinations[0].destination_id

    # Deleting IP address should set seat_ip.destination to NULL but not
    # change seat_ip.host_id
    session.delete(ip)
    session.commit()
    session.refresh(seat_ip)
    assert not seat_ip.destination_id
    assert seat_ip.host_id

    # Deleting seat_ip does not delete from parent table `seat`
    assert session.scalars(select(Seat).where(Seat.seat_id == seat_ip.seat_id)).one()
    session.delete(seat_ip)
    session.commit()
    assert session.scalars(select(Seat).where(Seat.seat_id == seat.seat_id)).one()


def test_induct_seat_delete_node(session: Session, node_with_inducts_seats: Node):
    from sqlalchemy import select

    from app.models import ClProtocol, Induct, Link, Node, Seat

    node = node_with_inducts_seats
    for i in node.inducts:
        assert i.node
        assert i.cl_protocol
        assert i.links
    for s in node.seats:
        assert s.node
        assert s.links

    host = node.host
    session.delete(node)
    session.commit()
    assert not session.scalars(select(Node)).all()
    assert not session.scalars(select(ClProtocol)).all()
    assert not session.scalars(select(Induct)).all()
    assert not session.scalars(select(Seat)).all()
    # The node has been deleted, but the link is still there because host
    # is not deleted yet.
    assert session.scalars(select(Link)).all()
    session.delete(host)
    session.commit()
    # Now the link should be gone
    assert not session.scalars(select(Link)).all()


def test_induct_delete_cascades_to_types(session: Session, induct_ip: InductIp):
    from sqlalchemy import select

    from app.models import Induct, InductIp

    # Test that deleting the parent induct will delete the types
    induct_ip_parent = induct_ip.induct
    assert induct_ip in session.scalars(select(InductIp)).all()

    session.delete(induct_ip_parent)
    session.commit()
    assert not session.scalars(select(Induct)).all()
    assert not session.scalars(select(InductIp)).all()


def test_seat_delete_cascades_to_types(session: Session, seat_ip: SeatIp):
    from sqlalchemy import select

    from app.models import Seat, SeatIp

    seat_ip_parent = seat_ip.seat
    assert seat_ip in session.scalars(select(SeatIp)).all()

    session.delete(seat_ip_parent)
    session.commit()
    assert not session.scalars(select(Seat)).all()
    assert not session.scalars(select(SeatIp)).all()


def test_reassign_induct_nodes_host(
    session: Session, inducts_null_type_with_links: list[Induct], node: Node, host: Host
):
    from sqlalchemy import exc

    from app.models import InductIp

    destination = host.destinations[0]

    # The induct's node's operator doesn't match the host's operator. We could
    # try making them the same, but then we would have to worry about induct's
    # node number not being in the operator's allocated_node_numbers, so let's
    # just make the node not have an operator.
    # Do not update with `induct.node.operator = None` because that also tries
    # to set node.allocator_id to null.
    inducts_null_type_with_links[0].node.operator_id = None
    inducts_null_type_with_links[1].node.operator_id = None
    inducts_null_type_with_links[2].node.operator_id = None
    session.commit()

    induct = inducts_null_type_with_links[0]
    # Trying to reassign when an induct is still attached
    with pytest.raises(exc.IntegrityError):
        induct.node.host = node.host
        session.commit()
    session.rollback()

    # We can reassign the node's host once the induct is no longer
    # associated with links on the host.
    induct.links = []
    session.commit()
    induct.node.host = node.host
    session.commit()
    assert induct.node.host == node.host
    assert induct.host_id == node.host_id

    # Reassigning with an induct_ip
    induct_ip = InductIp()
    inducts_null_type_with_links[1].type = 'ip'
    induct_ip.induct = inducts_null_type_with_links[1]
    induct_ip.host_id = inducts_null_type_with_links[1].host_id
    session.add(induct_ip)
    # Need to commit first or else induct_ip.host_id will be NULL
    session.commit()
    # Reassign the factory generated destination's host
    destination.host_id = induct_ip.host_id
    session.commit()
    # Give the induct_ip an address
    induct_ip.destination_id = destination.destination_id
    session.commit()
    # Reassigning node's host should fail
    with pytest.raises(exc.IntegrityError):
        induct_ip.induct.node.host = node.host
        session.commit()
    session.rollback()
    # Only changing induct_link is not enough
    induct_ip.induct.links = []
    session.commit()
    with pytest.raises(exc.IntegrityError):
        induct_ip.induct.node.host = node.host
        session.commit()
    session.rollback()
    # Set induct_ip.destination_id to NULL
    induct_ip.destination_id = None
    session.commit()
    # We can now reassign
    induct_ip.induct.node.host = node.host
    session.commit()
    assert induct.host_id == node.host_id
    assert induct_ip.host_id == node.host_id


def test_reassign_seat_nodes_host(
    session: Session, seats_not_ip_with_links: list[Seat], node: Node, host: Host
):
    from sqlalchemy import exc

    from app.models import SeatIp

    destination = host.destinations[0]

    # The seat's node's operator doesn't match the host's operator. We could
    # try making them the same, but then we would have to worry about induct's
    # node number not being in the operator's allocated_node_numbers, so let's
    # just make the node not have an operator.
    # Do not update with `seat.node.operator = None` because that also tries
    # to set node.allocator_id to null.
    seats_not_ip_with_links[0].node.operator_id = None
    seats_not_ip_with_links[1].node.operator_id = None
    seats_not_ip_with_links[2].node.operator_id = None
    session.commit()

    seat = seats_not_ip_with_links[0]
    # Trying to reassign when an seat is still attached
    with pytest.raises(exc.IntegrityError):
        seat.node.host = node.host
        session.commit()
    session.rollback()

    # We can reassign the node's host once the seat is no longer
    # associated with links on the host.
    seat.links = []
    session.commit()
    seat.node.host = node.host
    session.commit()
    assert seat.node.host == node.host
    assert seat.host_id == node.host_id

    # Reassigning with an seat_ip
    seat_ip = SeatIp()
    seats_not_ip_with_links[1].type = 'ip'
    seat_ip.seat = seats_not_ip_with_links[1]
    seat_ip.host_id = seats_not_ip_with_links[1].host_id
    session.add(seat_ip)
    # Need to commit first or else seat_ip.host_id will be NULL
    session.commit()
    # Reassign the factory generated destination's host
    destination.host_id = seat_ip.host_id
    session.commit()
    # Give the seat_ip an address
    seat_ip.destination_id = destination.destination_id
    session.commit()
    # Reassigning node's host should fail
    with pytest.raises(exc.IntegrityError):
        seat_ip.seat.node.host = node.host
        session.commit()
    session.rollback()
    # Only changing seat_link is not enough
    seat_ip.seat.links = []
    session.commit()
    with pytest.raises(exc.IntegrityError):
        seat_ip.seat.node.host = node.host
        session.commit()
    session.rollback()
    # Set seat_ip.destination_id to NULL
    seat_ip.destination_id = None
    session.commit()
    # We can now reassign
    seat_ip.seat.node.host = node.host
    session.commit()
    assert seat.host_id == node.host_id
    assert seat_ip.host_id == node.host_id


def test_hostless_duct_seat_relationships_load(session: Session, node: Node):
    from app.models import Induct, InductIp, Seat, SeatIp

    node.host = None
    session.commit()

    induct = Induct(type='ip', node=node)
    session.add(induct)
    session.commit()
    assert induct in node.inducts
    assert induct.node == node

    induct_ip = InductIp(induct_id=induct.induct_id)
    session.add(induct_ip)
    session.commit()
    assert induct.induct_ip == induct_ip
    assert induct_ip.induct == induct

    seat = Seat(type='ip', node=node)
    session.add(seat)
    session.commit()
    assert seat in node.seats
    assert seat.node == node

    seat_ip = SeatIp(seat_id=seat.seat_id)
    session.add(seat_ip)
    session.commit()
    assert seat.seat_ip == seat_ip
    assert seat_ip.seat == seat


def test_duct_types_same_parent_not_allowed(session: Session, node: Node):
    from sqlalchemy import exc

    from app.models import Induct, InductIp

    induct = Induct()
    induct.type = 'ip'
    induct.node = node
    induct.host_id = node.host_id
    session.add(induct)
    session.commit()

    induct_ip = InductIp()
    induct_ip.induct_id = induct.induct_id
    induct_ip.host_id = node.host_id
    session.add(induct_ip)
    session.commit()

    # There's a warning because induct_ip2 uses the same PK as the
    # existing induct_ip
    # IntegrityError because it violates unique constraint on
    # induct_ip.induct_id
    with pytest.warns(exc.SAWarning):
        with pytest.raises(exc.IntegrityError):
            induct_ip2 = InductIp()
            induct_ip2.induct_id = induct.induct_id
            induct_ip2.host_id = node.host_id
            session.add(induct_ip2)
            session.commit()
    session.rollback()


def test_seat_types_same_parent_not_allowed(session: Session, node: Node):
    from sqlalchemy import exc

    from app.models import Seat, SeatIp

    seat = Seat(type='ip', node=node, host_id=node.host_id)
    session.add(seat)
    session.commit()

    seat_ip = SeatIp(seat_id=seat.seat_id, host_id=node.host_id)
    session.add(seat_ip)
    session.commit()

    # There's a warning because seat_ip2 uses the same PK as the
    # existing seat_ip
    # IntegrityError because it violates unique constraint on
    # seat_ip.seat_id
    with pytest.warns(exc.SAWarning):
        with pytest.raises(exc.IntegrityError):
            seat_ip2 = SeatIp(seat_id=seat.seat_id, host_id=node.host_id)
            session.add(seat_ip2)
            session.commit()
    session.rollback()


def test_delete_host_nullifies_references(
    session: Session, node_with_inducts_seats: Node
):
    # Note: normally, if a node has children which reference host children,
    # updating node.host_id to null is restricted.
    # But deleting the host a node is on should not be restrited since the
    # host children should be deleted which nullifies their references in
    # the node children, which makes it okay to set node.host_id to null.
    from sqlalchemy import select

    from app.models import Host, Induct, InductIp, Node

    node = node_with_inducts_seats
    assert node.host_id
    for i in node.inducts:
        assert i.links
        assert i.host_id
        if i.induct_ip:
            assert i.induct_ip.host_id
            assert i.induct_ip.destination_id

    # session.execute(text('SET CONSTRAINTS ALL DEFERRED'))
    session.delete(node.host)
    session.commit()
    assert node.host not in session.scalars(select(Host)).all()

    assert node in session.scalars(select(Node)).all()
    assert not node.host_id
    for i in node.inducts:
        assert i in session.scalars(select(Induct)).all()
        assert not i.links
        assert not i.host_id
        if i.induct_ip:
            assert i.induct_ip in session.scalars(select(InductIp)).all()
            assert not i.induct_ip.host_id
            assert not i.induct_ip.destination_id


def test_node_modified_at_trigger(
    session: Session, node_on_host_with_destination_and_link: Node
):
    from sqlalchemy import bindparam, text

    from app.models import (
        ClProtocol,
        Contact,
        EndpointIPN,
        Induct,
        InductIp,
        Seat,
        SeatIp,
    )

    node = node_on_host_with_destination_and_link

    # Can't reassign node.comments to itself since unit of work will not
    # emit redundant UPDATE statements
    old_modified_at = node.modified_at
    session.execute(
        text(
            'UPDATE node SET comments = :comments WHERE node_id = :node_id'
        ).bindparams(
            bindparam('comments', node.comments), bindparam('node_id', node.node_id)
        )
    )
    session.refresh(node)
    assert old_modified_at == node.modified_at

    # Row is different
    node.comments = 'test'
    session.commit()
    session.refresh(node)
    assert old_modified_at != node.modified_at

    # Insert endpoint
    old_modified_at = node.modified_at
    endpoint = EndpointIPN(node_id=node.node_id, service_number=9999)
    session.add(endpoint)
    session.commit()
    session.refresh(node)
    assert old_modified_at != node.modified_at

    # Update endpoint
    # Redundant update doesn't change modified_at
    old_modified_at = node.modified_at
    session.execute(
        text(
            'UPDATE endpoint_ipn SET application = :application'
            ' WHERE node_id = :node_id AND service_number = :service_number'
        ).bindparams(
            bindparam('application', endpoint.application),
            bindparam('node_id', endpoint.node_id),
            bindparam('service_number', endpoint.service_number),
        )
    )
    session.refresh(node)
    assert old_modified_at == node.modified_at

    # Update with different values
    endpoint.application = 'test'
    session.commit()
    session.refresh(node)
    assert old_modified_at != node.modified_at

    # Delete endpoint
    old_modified_at = node.modified_at
    session.delete(endpoint)
    session.commit()
    assert old_modified_at != node.modified_at

    # Insert cl_protocol
    old_modified_at = node.modified_at
    cl_protocol = ClProtocol(
        node_id=node.node_id, cl_protocol_name='foo', cl_protocol_class=10
    )
    session.add(cl_protocol)
    session.commit()
    session.refresh(node)
    assert old_modified_at != node.modified_at

    # Update cl_protocol
    # Redundant update doesn't change modified_at
    old_modified_at = node.modified_at
    session.execute(
        text(
            'UPDATE cl_protocol SET node_id = :node_id'
            ' WHERE cl_protocol_id = :cl_protocol_id'
        ).bindparams(
            bindparam('node_id', cl_protocol.node_id),
            bindparam('cl_protocol_id', cl_protocol.cl_protocol_id),
        )
    )
    session.refresh(node)
    assert old_modified_at == node.modified_at

    # Update with different values
    cl_protocol.cl_protocol_name = 'blah'
    session.commit()
    session.refresh(node)
    assert old_modified_at != node.modified_at

    # Delete cl_protocol
    old_modified_at = node.modified_at
    session.delete(cl_protocol)
    session.commit()
    assert old_modified_at != node.modified_at

    # Insert induct
    old_modified_at = node.modified_at
    induct = Induct(type='ip', node_id=node.node_id, host_id=node.host_id)
    session.add(induct)
    session.commit()
    session.refresh(node)
    assert old_modified_at != node.modified_at

    # Update induct
    # Redundant update doesn't change modified_at
    old_modified_at = node.modified_at
    session.execute(
        text(
            'UPDATE induct SET node_id = :node_id WHERE induct_id = :induct_id'
        ).bindparams(
            bindparam('node_id', induct.node_id),
            bindparam('induct_id', induct.induct_id),
        )
    )
    session.refresh(node)
    assert old_modified_at == node.modified_at

    # Update with different values
    induct.cli_command = 'foo'
    session.commit()
    session.refresh(node)
    assert old_modified_at != node.modified_at

    # Insert / remove links
    old_modified_at = node.modified_at
    induct.links.append(node.host.links[0])
    session.commit()
    session.refresh(node)
    assert old_modified_at != node.modified_at

    old_modified_at = node.modified_at
    induct.links = []
    session.commit()
    session.refresh(node)
    assert old_modified_at != node.modified_at

    # Insert induct_ip
    old_modified_at = node.modified_at
    induct_ip = InductIp(induct_id=induct.induct_id, host_id=node.host_id)
    session.add(induct_ip)
    session.commit()
    session.refresh(node)
    assert old_modified_at != node.modified_at

    # Update induct_ip
    # Redundant update doesn't change modified_at
    old_modified_at = node.modified_at
    session.execute(
        text(
            'UPDATE induct_ip SET induct_id = :induct_id WHERE induct_id = :induct_id'
        ).bindparams(bindparam('induct_id', induct_ip.induct_id))
    )
    session.refresh(node)
    assert old_modified_at == node.modified_at

    # Update with different values
    induct_ip.port_number = 1
    session.commit()
    session.refresh(node)
    assert old_modified_at != node.modified_at

    # Delete induct_ip
    old_modified_at = node.modified_at
    session.delete(induct_ip)
    session.commit()
    assert old_modified_at != node.modified_at

    # Delete induct
    session.delete(induct)
    session.commit()
    assert old_modified_at != node.modified_at

    # Insert seat
    old_modified_at = node.modified_at
    seat = Seat(type='ip', node_id=node.node_id, host_id=node.host_id)
    session.add(seat)
    session.commit()
    session.refresh(node)
    assert old_modified_at != node.modified_at

    # Update seat
    # Redundant update doesn't change modified_at
    old_modified_at = node.modified_at
    session.execute(
        text('UPDATE seat SET node_id = :node_id WHERE seat_id = :seat_id').bindparams(
            bindparam('node_id', seat.node_id),
            bindparam('seat_id', seat.seat_id),
        )
    )
    session.refresh(node)
    assert old_modified_at == node.modified_at

    # Update with different values
    seat.lsi_command = 'bar'
    session.commit()
    session.refresh(node)
    assert old_modified_at != node.modified_at

    # Insert / remove links
    old_modified_at = node.modified_at
    seat.links.append(node.host.links[0])
    session.commit()
    session.refresh(node)
    assert old_modified_at != node.modified_at

    old_modified_at = node.modified_at
    seat.links = []
    session.commit()
    session.refresh(node)
    assert old_modified_at != node.modified_at

    # Insert seat_ip
    old_modified_at = node.modified_at
    seat_ip = SeatIp(seat_id=seat.seat_id, host_id=node.host_id)
    session.add(seat_ip)
    session.commit()
    session.refresh(node)
    assert old_modified_at != node.modified_at

    # Update seat_ip
    # Redundant update doesn't change modified_at
    old_modified_at = node.modified_at
    session.execute(
        text(
            'UPDATE seat_ip SET seat_id = :seat_id WHERE seat_id = :seat_id'
        ).bindparams(bindparam('seat_id', seat_ip.seat_id))
    )
    session.refresh(node)
    assert old_modified_at == node.modified_at

    # Update with different values
    seat_ip.port_number = 34
    session.commit()
    session.refresh(node)
    assert old_modified_at != node.modified_at

    # Delete seat_ip
    old_modified_at = node.modified_at
    session.delete(seat_ip)
    session.commit()
    assert old_modified_at != node.modified_at

    # Delete seat
    session.delete(seat)
    session.commit()
    assert old_modified_at != node.modified_at

    # Associate contact with node
    old_modified_at = node.modified_at
    contact = Contact(contact_name='contact to test modified_at trigger')
    session.add(contact)
    session.commit()
    contact.nodes.append(node)
    session.commit()
    session.refresh(node)
    assert old_modified_at != node.modified_at

    # Dissociate contact with node
    old_modified_at = node.modified_at
    contact.nodes.remove(node)
    session.commit()
    session.refresh(node)
    assert old_modified_at != node.modified_at


def test_host_id_constraint(session: Session, allocator: Allocator):
    from sqlalchemy import exc

    from app.models import (
        CommDirectionEnumInternal,
        Destination,
        Host,
        Induct,
        InductIp,
        Link,
        Node,
        Seat,
        SeatIp,
    )

    host = Host(hostname='host for test_host_id_constraint')
    session.add(host)
    session.commit()
    link = Link(host_id=host.host_id, direction=CommDirectionEnumInternal.FULL_DUPLEX)
    ip_address = Destination(host_id=host.host_id, ip_address='1.1.1.1')
    session.add_all([link, ip_address])
    session.commit()

    node = Node(allocator_id=allocator.allocator_id, node_number=0)
    session.add(node)
    session.commit()

    # Insert, non-null host reference when host_id is null

    with pytest.raises(exc.IntegrityError):
        induct: Induct = Induct(node_id=node.node_id, type='ip')
        session.add(induct)
        session.commit()
        induct.links.append(link)
        session.commit()
    session.rollback()

    with pytest.raises(exc.IntegrityError):
        seat: Seat = Seat(node_id=node.node_id, type='ip')
        session.add(seat)
        session.commit()
        seat.links.append(link)
        session.commit()
    session.rollback()

    induct_ip_parent = Induct(node_id=node.node_id, type='ip')
    seat_ip_parent = Seat(node_id=node.node_id, type='ip')
    session.add_all([induct_ip_parent, seat_ip_parent])
    session.commit()

    with pytest.raises(exc.IntegrityError):
        session.add(
            InductIp(
                induct_id=induct_ip_parent.induct_id,
                destination_id=ip_address.destination_id,
            )
        )
        session.commit()
    session.rollback()

    with pytest.raises(exc.IntegrityError):
        session.add(
            SeatIp(
                seat_id=seat_ip_parent.seat_id, destination_id=ip_address.destination_id
            )
        )
        session.commit()
    session.rollback()

    node.host_id = host.host_id
    session.commit()

    # Insert, duct host_id doesn't match parent

    with pytest.raises(exc.ProgrammingError) as excinfo:
        session.add(Induct(node_id=node.node_id, type='ip', host_id=None))
        session.commit()
    session.rollback()
    assert (
        f'new induct.host_id (<NULL>) does not match with parent ({node.host_id})'
    ) in excinfo.value.orig.diag.message_primary

    with pytest.raises(exc.ProgrammingError) as excinfo:
        session.add(Seat(node_id=node.node_id, type='ip', host_id=None))
        session.commit()
    session.rollback()
    assert (
        f'new seat.host_id (<NULL>) does not match with parent ({node.host_id})'
    ) in excinfo.value.orig.diag.message_primary

    with pytest.raises(exc.ProgrammingError) as excinfo:
        session.add(InductIp(induct_id=induct_ip_parent.induct_id, host_id=None))
        session.commit()
    session.rollback()
    assert (
        f'new induct_ip.host_id (<NULL>) does not match with parent ({node.host_id})'
    ) in excinfo.value.orig.diag.message_primary

    with pytest.raises(exc.ProgrammingError) as excinfo:
        session.add(SeatIp(seat_id=seat_ip_parent.seat_id, host_id=None))
        session.commit()
    session.rollback()
    assert (
        f'new seat_ip.host_id (<NULL>) does not match with parent ({node.host_id})'
    ) in excinfo.value.orig.diag.message_primary

    node.host_id = None
    session.commit()

    # Update, non-null host reference when host_id is null

    with pytest.raises(exc.IntegrityError):
        induct_ip_parent.links.append(link)
        session.commit()
    session.rollback()

    with pytest.raises(exc.IntegrityError):
        seat_ip_parent.links.append(link)
        session.commit()
    session.rollback()

    induct_ip = InductIp(induct_id=induct_ip_parent.induct_id)
    seat_ip = SeatIp(seat_id=seat_ip_parent.seat_id)
    session.add_all([induct_ip, seat_ip])
    session.commit()

    with pytest.raises(exc.IntegrityError):
        induct_ip.destination_id = ip_address.destination_id
        session.commit()
    session.rollback()

    with pytest.raises(exc.IntegrityError):
        seat_ip.destination_id = ip_address.destination_id
        session.commit()
    session.rollback()

    node.host_id = host.host_id
    session.commit()

    # Update, duct host_id doesn't match parent

    for resource in [
        induct_ip_parent,
        seat_ip_parent,
        induct_ip,
        seat_ip,
    ]:
        with pytest.raises(exc.ProgrammingError) as excinfo:
            resource.host_id = None
            session.commit()
        session.rollback()
        assert (
            f'new {resource.__tablename__}.host_id (<NULL>) does not match with'
            f' parent ({node.host_id})'
        ) in excinfo.value.orig.diag.message_primary

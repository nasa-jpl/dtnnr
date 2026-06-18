from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

import structlog
from sqlakeyset import select_page
from sqlalchemy import (
    bindparam,
    exc,
    exists,
    or_,
    select,
    text,
)
from sqlalchemy import delete as sa_delete
from sqlalchemy import update as sa_update
from sqlalchemy.orm import aliased
from sqlalchemy.types import BigInteger, Text

from app.models import (
    Contact,
    Destination,
    Induct,
    InductIp,
    Node,
    Seat,
    SeatIp,
    induct_link,
    node_contact,
    seat_link,
)

from ..contact.service import get as contact_get

if TYPE_CHECKING:
    from sqlakeyset import Page
    from sqlalchemy import Row, Tuple
    from sqlalchemy.orm import Session

logger = structlog.stdlib.get_logger()


class DestinationRefModeEnum(StrEnum):
    NULLIFY = 'nullify'
    ASSOCIATE = 'associate'
    COPY = 'copy'


def get(db_session: Session, node_id: int) -> Node | None:
    """Get a node by node ID."""
    return db_session.scalar(select(Node).where(Node.node_id == node_id))


def get_by_FQNN(
    db_session: Session, allocator_id: int, node_number: int
) -> Node | None:
    """Get a node by its fully-qualified node number (allocator_id,
    node_number)."""
    return db_session.scalar(
        select(Node).where(
            (Node.allocator_id == allocator_id) & (Node.node_number == node_number)
        )
    )


def query(
    db_session: Session, max_page_size: int, bookmark: str | None
) -> Page[Row[Tuple[Node]]]:
    """Query nodes."""
    q = select(Node).order_by(Node.allocator_id, Node.node_number)
    return select_page(db_session, q, per_page=max_page_size, page=bookmark)


# TODO: not sure if should keep this
# def get_all_general_info(db_session: scoped_session):
#     """Return all records from the `node_general_info` view."""
#     return db_session.scalars(select(NodeGeneralInfo)
#         .order_by(NodeGeneralInfo.allocator_id, NodeGeneralInfo.node_number)
#     )


def create(
    db_session: Session,
    node_number: int,
    allocator_id: int = 0,
    operator_id: int | None = None,
    host_id: int | None = None,
    sdr_config_flags: int | None = None,
    wm_size: int | None = None,
    sdr_wm_size: int | None = None,
    heap_words: int | None = None,
    node_name: str | None = None,
    comments: str | None = None,
) -> Node:
    """Creates a node in the `node` table."""
    try:
        node = Node(
            node_number=node_number,
            allocator_id=allocator_id,
            operator_id=operator_id,
            host_id=host_id,
            sdr_config_flags=sdr_config_flags,
            wm_size=wm_size,
            sdr_wm_size=sdr_wm_size,
            heap_words=heap_words,
            node_name=node_name,
            comments=comments,
        )
        db_session.add(node)
        db_session.commit()
    except exc.IntegrityError as e:
        # FQNN already exists, node number out of range,
        # non-existent allocator / operator / host
        logger.exception(e._message())
        raise
    except Exception:
        logger.exception('Unexpected error')
        raise
    return node


def nullify_link_ref(db_session: Session, node_id: int) -> None:
    """Deletes associations between link and inducts / seats for the
    inducts and seats of the node identified by `node_id`.

    `db_session` is flushed.
    """
    db_session.execute(
        sa_delete(induct_link)
        .where(induct_link.c.induct_id == Induct.induct_id)
        .where(Induct.node_id == node_id)
    )
    db_session.execute(
        sa_delete(seat_link)
        .where(seat_link.c.seat_id == Seat.seat_id)
        .where(Seat.node_id == node_id)
    )
    db_session.flush()


def nullify_dest_ref(db_session: Session, node_id: int, host_id: int) -> None:
    """Set induct_ip.destination_id and seat_ip.destination_id to null
    for the inducts and seats of the node identified by `node_id` which
    use a destination with `host_id`.

    `db_session` is flushed.
    """
    db_session.execute(
        sa_update(InductIp)
        .where(
            InductIp.induct_id == Induct.induct_id,
            Induct.node_id == node_id,
            InductIp.destination_id == Destination.destination_id,
            Destination.host_id == host_id,
        )
        .values(destination_id=None)
    )
    db_session.execute(
        sa_update(SeatIp)
        .where(
            SeatIp.seat_id == Seat.seat_id,
            Seat.node_id == node_id,
            SeatIp.destination_id == Destination.destination_id,
            Destination.host_id == host_id,
        )
        .values(destination_id=None)
    )
    db_session.flush()


def associate_dest_ref(db_session: Session, node_id: int, new_host_id: int) -> None:
    """Updates induct_ip and seat_ip under the node identified by
    `node_id` to have an equivalent destination under the host
    identified by `new_host_id`.

    Foreign keys referencing destination are deferred. `db_session` is
    flushed.
    """
    d1 = aliased(Destination)
    d2 = aliased(Destination)
    db_session.execute(
        text('SET CONSTRAINTS fk_induct_ip_host_id_destination DEFERRED')
    )
    induct_stmt = (
        sa_update(InductIp)
        .where(
            InductIp.induct_id == Induct.induct_id,
            Induct.node_id == node_id,
            d1.host_id == InductIp.host_id,
            d1.destination_id == InductIp.destination_id,
            or_(
                d1.ip_address == d2.ip_address, d1.registered_name == d2.registered_name
            ),
            d2.host_id == new_host_id,
        )
        .values(destination_id=d2.destination_id)
    )
    db_session.execute(induct_stmt)
    db_session.execute(text('SET CONSTRAINTS fk_seat_ip_host_id_destination DEFERRED'))
    seat_stmt = (
        sa_update(SeatIp)
        .where(
            SeatIp.seat_id == Seat.seat_id,
            Seat.node_id == node_id,
            d1.host_id == SeatIp.host_id,
            d1.destination_id == SeatIp.destination_id,
            or_(
                d1.ip_address == d2.ip_address, d1.registered_name == d2.registered_name
            ),
            d2.host_id == new_host_id,
        )
        .values(destination_id=d2.destination_id)
    )
    db_session.execute(seat_stmt)
    db_session.flush()


def copy_dest_ref(db_session: Session, node_id: int, new_host_id: int) -> None:
    """Copy destinations referenced by seats and inducts associated with
    the node identified by `node_id` to the host identified by
    `new_host_id`. If an equivalent destination already exists, then new
    records are not inserted.

    `db_session` is flushed.
    """
    induct_stmt = text(
        'INSERT INTO destination (ip_address, registered_name, host_id)'
        ' SELECT ip_address, registered_name, :new_host_id'
        ' FROM induct_ip'
        ' JOIN induct ON induct_ip.induct_id = induct.induct_id'
        ' JOIN destination ON induct_ip.destination_id = destination.destination_id'
        ' WHERE induct.node_id = :node_id'
        ' ON CONFLICT DO NOTHING'
    ).bindparams(
        bindparam('new_host_id', value=new_host_id), bindparam('node_id', value=node_id)
    )
    db_session.execute(induct_stmt)
    seat_stmt = text(
        'INSERT INTO destination (ip_address, registered_name, host_id)'
        ' SELECT ip_address, registered_name, :new_host_id'
        ' FROM seat_ip'
        ' JOIN seat ON seat_ip.seat_id = seat.seat_id'
        ' JOIN destination ON seat_ip.destination_id = destination.destination_id'
        ' WHERE seat.node_id = :node_id'
        ' ON CONFLICT DO NOTHING'
    ).bindparams(
        bindparam('new_host_id', value=new_host_id), bindparam('node_id', value=node_id)
    )
    db_session.execute(seat_stmt)
    db_session.flush()


def update(
    db_session: Session,
    node_id: int,
    node_number: int,
    allocator_id: int,
    operator_id: int | None,
    host_id: int | None,
    sdr_config_flags: int | None,
    wm_size: int | None,
    sdr_wm_size: int | None,
    heap_words: int | None,
    node_name: str | None,
    comments: str | None,
    destination_ref_mode: DestinationRefModeEnum = DestinationRefModeEnum.NULLIFY,
) -> Node:
    """Updates a node in the `node` table.

    `destination_ref_mode` only has an effect if `host_id` differs from
    the node's current host_id, otherwise it is ignored. There are three
    possible effects:

    * nullify: destination_id of induct_ip and seat_ip records are set
      to null.

    * associate: destination_id of induct_ip and seat_ip records are set
      to an equivalent destination under the host identified by
      `host_id`. If a destination_id does not have an equivalent
      destination on the other host, then the column is set to null.

    * copy: destination of induct_ip and seat_ip records are copied
      to the host identified by `host_id` if an equivalent destination
      does not exist on the host, and destination_id of those induct_ip
      and seat_ip records are updated to reference equivalent
      destinations on the other host.

    For all three effects, any records in induct_link and seat_link that
    are associated with the node are dropped. "associate" and "copy" are
    only allowed when `host_id` is not None.
    """
    node = get(db_session, node_id)
    if node.host_id is not None and node.host_id != host_id:
        nullify_link_ref(db_session, node_id)
        if destination_ref_mode == DestinationRefModeEnum.NULLIFY:
            nullify_dest_ref(db_session, node_id, node.host_id)
        elif destination_ref_mode == DestinationRefModeEnum.ASSOCIATE:
            assert host_id is not None
            associate_dest_ref(db_session, node_id, host_id)
            nullify_dest_ref(db_session, node_id, node.host_id)
        elif destination_ref_mode == DestinationRefModeEnum.COPY:
            assert host_id is not None
            copy_dest_ref(db_session, node_id, host_id)
            associate_dest_ref(db_session, node_id, host_id)
    node.node_number = node_number
    node.allocator_id = allocator_id
    node.operator_id = operator_id
    node.host_id = host_id
    node.sdr_config_flags = sdr_config_flags
    node.wm_size = wm_size
    node.sdr_wm_size = sdr_wm_size
    node.heap_words = heap_words
    node.node_name = node_name
    node.comments = comments

    try:
        db_session.commit()
    except exc.IntegrityError as e:
        # FQNN already exists, node number out of range,
        # non-existent allocator / operator / host
        logger.exception(e._message())
        raise
    except Exception:
        logger.exception('Unexpected error')
        raise
    return node


def copy(
    db_session: Session,
    node_id_to_copy: int,
    allocator_id: int,
    node_number: int,
    host_id: int | None,
    operator_id: int | None,
    destination_ref_mode: DestinationRefModeEnum = DestinationRefModeEnum.NULLIFY,
) -> Node:
    """Copies the node identified by `node_id_to_copy`.

    `destination_ref_mode` only has an effect if `host_id` differs from
    the node's current host_id, otherwise it is ignored. There are three
    possible effects:

    * nullify: destination_id of copied induct_ip and seat_ip records
      are set to null.

    * associate: destination_id of copied induct_ip and seat_ip records
      are set to an equivalent destination under the host identified by
      `host_id`. If a destination_id does not have an equivalent
      destination on the other host, then the column is set to null.

    * copy: destination of induct_ip and seat_ip records are copied to
      the host identified by `host_id` if an equivalent destination does
      not exist on the host, and destination_id of copied induct_ip and
      seat_ip records are set to reference equivalent destinations on
      the new host.

    Moreover:
    * node.created_at, node.modified_at, and contacts are not copied
    * induct_link and seat_link records are not copied if the new node
      is not on the same host
    """
    node = get(db_session, node_id_to_copy)

    if destination_ref_mode == DestinationRefModeEnum.NULLIFY:
        ip_ins = """induct_ip_ins AS (
  INSERT INTO induct_ip (induct_id, host_id, destination_id, port_number)
  SELECT new_induct_id, induct_sel.host_id, NULL, port_number
  FROM induct_sel JOIN induct_ip
  ON induct_sel.induct_id = induct_ip.induct_id
), seat_ip_ins AS (
  INSERT INTO seat_ip (seat_id, host_id, destination_id, port_number)
  SELECT new_seat_id, seat_sel.host_id, NULL, port_number
  FROM seat_sel JOIN seat_ip
  ON seat_sel.seat_id = seat_ip.seat_id
)"""
    elif (
        destination_ref_mode == DestinationRefModeEnum.COPY
        and node.host_id != host_id
        and host_id is not None
    ):
        # https://www.postgresql.org/docs/17/queries-with.html#QUERIES-WITH-MODIFYING
        # The order in which updates from data-modifying statements in WITH
        # happen is unpredictable. induct_ip_ins can't see what happens
        # in destination_induct_ins without RETURNING.
        ip_ins = """destination_induct_ins AS (
  INSERT INTO destination (ip_address, registered_name, host_id)
  SELECT ip_address, registered_name, induct_sel.host_id
  FROM induct_ip
  JOIN induct_sel ON induct_ip.induct_id = induct_sel.induct_id
  JOIN destination ON induct_ip.destination_id = destination.destination_id
  ON CONFLICT DO NOTHING
  RETURNING *
), induct_ip_ins AS (
  INSERT INTO induct_ip (induct_id, host_id, destination_id, port_number)
  SELECT new_induct_id, induct_sel.host_id,
    COALESCE(d2.destination_id, d3.destination_id), port_number
  FROM induct_sel
  JOIN induct_ip ON induct_sel.induct_id = induct_ip.induct_id
  LEFT JOIN destination d1 ON d1.host_id = induct_ip.host_id
    AND d1.destination_id = induct_ip.destination_id
  LEFT JOIN destination d2 ON d2.host_id = induct_sel.host_id
    AND d1.ip_address IS NOT DISTINCT FROM d2.ip_address
    AND d1.registered_name IS NOT DISTINCT FROM d2.registered_name
  LEFT JOIN destination_induct_ins d3
    ON d1.ip_address IS NOT DISTINCT FROM d3.ip_address
    AND d1.registered_name IS NOT DISTINCT FROM d3.registered_name
), destination_seat_ins AS (
  INSERT INTO destination (ip_address, registered_name, host_id)
  SELECT ip_address, registered_name, seat_sel.host_id
  FROM seat_ip
  JOIN seat_sel ON seat_ip.seat_id = seat_sel.seat_id
  JOIN destination ON seat_ip.destination_id = destination.destination_id
  ON CONFLICT DO NOTHING
  RETURNING *
), seat_ip_ins AS (
  INSERT INTO seat_ip (seat_id, host_id, destination_id, port_number)
  SELECT new_seat_id, seat_sel.host_id,
    COALESCE(d2.destination_id, d3.destination_id), port_number
  FROM seat_sel
  JOIN seat_ip ON seat_sel.seat_id = seat_ip.seat_id
  LEFT JOIN destination d1 ON d1.host_id = seat_ip.host_id
    AND d1.destination_id = seat_ip.destination_id
  LEFT JOIN destination d2 ON d2.host_id = seat_sel.host_id
    AND d1.ip_address IS NOT DISTINCT FROM d2.ip_address
    AND d1.registered_name IS NOT DISTINCT FROM d2.registered_name
  LEFT JOIN destination_seat_ins d3
    ON d1.ip_address IS NOT DISTINCT FROM d3.ip_address
    AND d1.registered_name IS NOT DISTINCT FROM d3.registered_name
)"""
    else:
        ip_ins = """induct_ip_ins AS (
  INSERT INTO induct_ip (induct_id, host_id, destination_id, port_number)
  SELECT new_induct_id, induct_sel.host_id, d2.destination_id, port_number
  FROM induct_sel
  JOIN induct_ip ON induct_sel.induct_id = induct_ip.induct_id
  LEFT JOIN destination d1 ON d1.host_id = induct_ip.host_id
    AND d1.destination_id = induct_ip.destination_id
  LEFT JOIN destination d2 ON d2.host_id = induct_sel.host_id
    AND d1.ip_address IS NOT DISTINCT FROM d2.ip_address
    AND d1.registered_name IS NOT DISTINCT FROM d2.registered_name
), seat_ip_ins AS (
  INSERT INTO seat_ip (seat_id, host_id, destination_id, port_number)
  SELECT new_seat_id, seat_sel.host_id, d2.destination_id, port_number
  FROM seat_sel
  JOIN seat_ip ON seat_sel.seat_id = seat_ip.seat_id
  LEFT JOIN destination d1 ON d1.host_id = seat_ip.host_id
    AND d1.destination_id = seat_ip.destination_id
  LEFT JOIN destination d2 ON d2.host_id = seat_sel.host_id
    AND d1.ip_address IS NOT DISTINCT FROM d2.ip_address
    AND d1.registered_name IS NOT DISTINCT FROM d2.registered_name
)"""

    if node.host_id is not None and node.host_id == host_id:
        link_ins = """induct_link_ins AS (
  INSERT INTO induct_link (induct_id, link_id, host_id, direction, uses_ltp)
  SELECT new_induct_id, link_id, induct_sel.host_id, induct_link.direction,
    induct_sel.uses_ltp
  FROM induct_sel
  JOIN induct_link ON induct_sel.induct_id = induct_link.induct_id
), seat_link_ins AS (
  INSERT INTO seat_link (seat_id, link_id, host_id, direction)
  SELECT new_seat_id, link_id, seat_sel.host_id, seat_link.direction
  FROM seat_sel
  JOIN seat_link ON seat_sel.seat_id = seat_link.seat_id
)
"""
    else:
        link_ins = ''

    # SELECT before INSERT advice: https://dba.stackexchange.com/a/292315

    # fmt: off
    stmt = text(
f"""WITH node_ins AS (
  INSERT INTO node (node_number, allocator_id, operator_id, host_id,
    sdr_config_flags, wm_size, sdr_wm_size, heap_words, node_name, comments)
  SELECT :node_number, :allocator_id, :operator_id, :host_id, sdr_config_flags,
    wm_size, sdr_wm_size, heap_words, node_name, comments
  FROM node
  WHERE node_id = :node_id_to_copy
  RETURNING node_id, host_id
), endpoint_ipn_ins AS (
  INSERT INTO endpoint_ipn (node_id, service_number, disposition, application)
  SELECT (SELECT node_id FROM node_ins), service_number, disposition, application
  FROM endpoint_ipn
  WHERE endpoint_ipn.node_id = :node_id_to_copy
  ORDER BY service_number
), endpoint_imc_ins AS (
  INSERT INTO endpoint_imc (node_id, group_number, disposition, application)
  SELECT (SELECT node_id FROM node_ins), group_number, disposition, application
  FROM endpoint_imc
  WHERE endpoint_imc.node_id = :node_id_to_copy
), cl_protocol_sel AS (
  SELECT node_ins.node_id, cl_protocol_id, cl_protocol_name, cl_protocol_class,
    nextval(pg_get_serial_sequence('cl_protocol', 'cl_protocol_id')) AS new_cl_protocol_id
  FROM node_ins
  JOIN cl_protocol ON cl_protocol.node_id = :node_id_to_copy
  ORDER BY cl_protocol_id
), cl_protocol_ins AS (
  INSERT INTO cl_protocol (cl_protocol_id, node_id, cl_protocol_name, cl_protocol_class)
  OVERRIDING SYSTEM VALUE
  SELECT new_cl_protocol_id, node_id, cl_protocol_name, cl_protocol_class
  FROM cl_protocol_sel
), induct_sel AS (
  SELECT induct_id, node_ins.node_id, type, node_ins.host_id,
    cl_protocol_sel.new_cl_protocol_id, cl_protocol_sel.cl_protocol_name,
    duct_name, cli_command, uses_ltp,
    nextval(pg_get_serial_sequence('induct', 'induct_id')) AS new_induct_id
  FROM node_ins
  JOIN induct ON induct.node_id = :node_id_to_copy
  LEFT JOIN cl_protocol_sel ON induct.cl_protocol_id = cl_protocol_sel.cl_protocol_id
  ORDER BY induct_id
), induct_ins AS (
  INSERT INTO induct (induct_id, type, node_id, host_id, cl_protocol_id,
    cl_protocol_name, duct_name, cli_command, uses_ltp)
  OVERRIDING SYSTEM VALUE
  SELECT new_induct_id, type, node_id, host_id, new_cl_protocol_id, cl_protocol_name,
    duct_name, cli_command, uses_ltp
  FROM induct_sel
), seat_sel AS (
  SELECT seat_id, type, node_ins.node_id, node_ins.host_id, lsi_command,
    nextval(pg_get_serial_sequence('seat', 'seat_id')) AS new_seat_id
  FROM node_ins
  JOIN seat ON seat.node_id = :node_id_to_copy
  ORDER BY seat_id
), seat_ins AS (
  INSERT INTO seat (seat_id, type, node_id, host_id, lsi_command)
  OVERRIDING SYSTEM VALUE
  SELECT new_seat_id, type, node_id, host_id, lsi_command
  FROM seat_sel
), induct_seat_ins AS (
  INSERT INTO induct_seat (induct_id, seat_id, node_id, uses_ltp)
  SELECT new_induct_id, new_seat_id, induct_sel.node_id, induct_sel.uses_ltp
  FROM induct_sel
  JOIN induct_seat ON induct_sel.induct_id = induct_seat.induct_id
  JOIN seat_sel ON seat_sel.seat_id = induct_seat.seat_id
), {ip_ins}{f', {link_ins}' if link_ins else ''}
SELECT node_id FROM node_ins
"""
    ).bindparams(
        bindparam('allocator_id', value=allocator_id, type_=BigInteger),
        bindparam('node_number', value=node_number, type_=BigInteger),
        bindparam('host_id', value=host_id, type_=BigInteger),
        bindparam('operator_id', value=operator_id, type_=BigInteger),
        bindparam('node_id_to_copy', value=node_id_to_copy, type_=BigInteger),
    )
    # fmt: on

    try:
        node_id = db_session.scalar(stmt)
        db_session.commit()
        node = get(db_session, node_id)
    except exc.SQLAlchemyError as e:
        logger.exception(e._message())
        raise
    except Exception:
        logger.exception('Unexpected error')
        raise
    return node


def delete(db_session: Session, node_id: int) -> None:
    """Delete a node from the `node` table identified by node_id."""
    node = get(db_session, node_id)
    if not node:
        return None
    try:
        db_session.delete(node)
    except Exception:
        logger.exception('Unexpected error')
        raise
    db_session.commit()


def list_contacts(
    db_session: Session, node_id: int, max_page_size: int, bookmark: str | None
) -> Page[Row[Tuple[Contact]]]:
    q = (
        select(Contact)
        .join(node_contact, Contact.contact_id == node_contact.c.contact_id)
        .where(node_contact.c.node_id == node_id)
        .order_by(Contact.contact_id)
    )
    return select_page(db_session, q, per_page=max_page_size, page=bookmark)


def associate_contact(
    db_session: Session, node_id: int, contact_id: int
) -> Contact | None:
    """Associates an existing contact with an node."""
    node = get(db_session, node_id)
    contact = contact_get(db_session, contact_id)
    try:
        node.contacts.append(contact)
        db_session.commit()
    except exc.IntegrityError as e:
        # Violating unique constraint on node_id and contact_id
        logger.exception(e._message())
        raise e
    except Exception:
        logger.exception(
            'Unexpected error', possible_reason='Non-existent node/contact'
        )
        raise
    return contact


def dissociate_contact(db_session: Session, node_id: int, contact_id: int) -> None:
    """Dissociates an existing contact with an node."""
    node = get(db_session, node_id)
    contact = contact_get(db_session, contact_id)
    try:
        node.contacts.remove(contact)
        db_session.commit()
    except ValueError:
        # Contact is not in node.contacts list
        logger.exception('Contact is not in host.contacts list')
        raise
    except Exception:
        logger.exception(
            'Unexpected error', possible_reason='Non-existent node/contact'
        )
        raise


def contact_is_associated(db_session: Session, node_id: int, contact_id: int) -> bool:
    """Returns true if the contact identified by contact_id is
    associated with the node identified by node_id.
    """
    associated_in_db = db_session.scalar(
        select(
            exists().where(
                node_contact.c.node_id == node_id,
                node_contact.c.contact_id == contact_id,
            )
        )
    )
    node = get(db_session, node_id)
    if node is None:
        return False
    contact = contact_get(db_session, contact_id)
    if contact is None:
        return False
    associated_in_orm = contact in node.contacts
    if not associated_in_db:
        logger.info('Not associated in database')
        return False
    if not associated_in_orm:
        logger.error(
            'node & contact: not associated in ORM',
            note='If the ORM works correctly, this should never be logged',
        )
        return False
    return associated_in_db and associated_in_orm

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlakeyset import select_page
from sqlalchemy import bindparam, exc, exists, select, text
from sqlalchemy.types import ARRAY, BigInteger

from app.models import Contact, Host, host_contact

from ..contact.service import get as contact_get
from ..node.schemas import NodeCopyForHostSchema

if TYPE_CHECKING:
    from sqlakeyset import Page
    from sqlalchemy import Row, Tuple
    from sqlalchemy.orm import Session

logger = structlog.stdlib.get_logger()


def get(db_session: Session, host_id: int) -> Host | None:
    """Get a host by its ID."""
    return db_session.scalar(select(Host).where(Host.host_id == host_id))


def query(
    db_session: Session, max_page_size: int, bookmark: str | None
) -> Page[Row[Tuple[Host]]]:
    """Query hosts."""
    q = select(Host).order_by(Host.host_id)
    return select_page(db_session, q, per_page=max_page_size, page=bookmark)


def create(
    db_session: Session,
    hostname: str,
    host_description: str | None = None,
    operator_id: int | None = None,
    sana_scid: int | None = None,
    word_size: int | None = None,
    newline: str | None = None,
) -> Host:
    """Create a host in the `host` table.

    By default, a host is not under an operator (operator_id is null).
    """
    try:
        host = Host(
            hostname=hostname,
            host_description=host_description,
            operator_id=operator_id,
            sana_scid=sana_scid,
            word_size=word_size,
            newline=newline,
        )
        db_session.add(host)
        db_session.commit()
    except exc.IntegrityError as e:
        # Using non-existent operator
        logger.exception(e._message())
        raise e
    except Exception as e:
        logger.exception('Unexpected error')
        raise e
    return host


def update(
    db_session: Session,
    host_id: int,
    hostname: str,
    host_description: str | None,
    operator_id: int | None,
    sana_scid: int | None,
    word_size: int | None,
    newline: str | None,
) -> Host:
    """Updates a host identified by `host_id`."""
    host = get(db_session, host_id)
    host.hostname = hostname
    host.host_description = host_description
    host.operator_id = operator_id
    host.sana_scid = sana_scid
    host.word_size = word_size
    host.newline = newline
    try:
        db_session.commit()
    except exc.IntegrityError as e:
        # Using non-existent operator
        logger.exception(e._message())
        raise e
    except Exception as e:
        logger.exception('Unexpected error')
        raise e
    return host


def copy(
    db_session: Session,
    host_id_to_copy: int,
    operator_id: int | None = None,
    input_nodes: list[NodeCopyForHostSchema] = [],
) -> Host:
    """Creates a copy of the host identified by `host_id`. The copy will
    be put under an operator if `operator_id` is not None.

    `input_nodes` specifies which nodes should be copied from the
    original host to the copy. If `NodeCopyForHostSchema.node_id`
    identifies a node that does not belong to the host, a copy of that
    node will not be made. Note that you can make multiple copies of one
    node through `input_nodes`.

    It is the caller's responsibility to make sure FQNNs are not
    repeated, that FQNNs are not already used, that allocator_id and
    operator_id exist, and that node numbers allocated to the given
    operator are used in `input_nodes`.
    """
    host: Host = get(db_session, host_id_to_copy)

    db_session.execute(text('SET CONSTRAINTS ALL DEFERRED'))

    stmt = text(
f"""WITH host_ins AS (
  INSERT INTO host (hostname, host_description, operator_id, sana_scid,
    word_size, newline)
  SELECT hostname, host_description, :operator_id, sana_scid, word_size, newline
  FROM host
  WHERE host_id = :host_id_to_copy
  RETURNING host_id
), destination_sel AS (
  SELECT (SELECT host_id FROM host_ins), destination_id, ip_address, registered_name,
    nextval(pg_get_serial_sequence('destination', 'destination_id'))
    AS new_destination_id
  FROM destination
  WHERE destination.host_id = :host_id_to_copy
  ORDER BY destination_id
), destination_ins AS (
  INSERT INTO destination (destination_id, ip_address, registered_name, host_id)
  OVERRIDING SYSTEM VALUE
  SELECT new_destination_id, ip_address, registered_name, host_id
  FROM destination_sel
), link_sel AS (
  SELECT (SELECT host_id FROM host_ins), link_id, type, direction,
    nextval(pg_get_serial_sequence('link', 'link_id')) AS new_link_id
  FROM link
  WHERE link.host_id = :host_id_to_copy
  ORDER BY link_id
), link_ins AS (
  INSERT INTO link (link_id, type, host_id, direction)
  OVERRIDING SYSTEM VALUE
  SELECT new_link_id, type, host_id, direction
  FROM link_sel
), ucs_link_ins AS (
  INSERT INTO underlying_communication_service_link
    (underlying_communication_service_id, link_id)
  SELECT ucsl.underlying_communication_service_id, new_link_id
  FROM link_sel
  JOIN underlying_communication_service_link ucsl
  ON link_sel.link_id = ucsl.link_id
), link_rf_ins AS (
  INSERT INTO link_rf (link_id, band_id)
  SELECT new_link_id, band_id
  FROM link_sel
  JOIN link_rf ON link_sel.link_id = link_rf.link_id
), node_sel AS (
  SELECT *, (SELECT host_id FROM host_ins) AS new_host_id,
    nextval(pg_get_serial_sequence('node', 'node_id')) AS new_node_id
  FROM UNNEST(
    :old_node_ids, :new_node_numbers, :new_allocator_ids, :new_operator_ids
  ) AS t (old_node_id, new_node_number, new_allocator_id, new_operator_id)
  JOIN node ON t.old_node_id = node.node_id
  WHERE host_id = :host_id_to_copy
  ORDER BY node.node_id
), node_ins AS (
  INSERT INTO node (node_id, node_number, allocator_id, operator_id, host_id,
    sdr_config_flags, wm_size, sdr_wm_size, heap_words, node_name, comments)
  OVERRIDING SYSTEM VALUE
  SELECT new_node_id, new_node_number, new_allocator_id, new_operator_id,
    new_host_id, sdr_config_flags, wm_size, sdr_wm_size, heap_words,
    node_name, comments
  FROM node_sel
  RETURNING node_id
), endpoint_ipn_ins AS (
  INSERT INTO endpoint_ipn (node_id, service_number, disposition, application)
  SELECT new_node_id, service_number, disposition, application
  FROM endpoint_ipn
  JOIN node_sel ON endpoint_ipn.node_id = node_sel.node_id
  ORDER BY node_sel.node_id, service_number
), endpoint_imc_ins AS (
  INSERT INTO endpoint_imc (node_id, group_number, disposition, application)
  SELECT new_node_id, group_number, disposition, application
  FROM endpoint_imc
  JOIN node_sel ON endpoint_imc.node_id = node_sel.node_id
  ORDER BY node_sel.node_id, group_number
), cl_protocol_sel AS (
  SELECT node_sel.node_id, node_sel.new_node_id, cl_protocol_id,
    cl_protocol_name, cl_protocol_class,
    nextval(pg_get_serial_sequence('cl_protocol', 'cl_protocol_id'))
    AS new_cl_protocol_id
  FROM node_sel
  JOIN cl_protocol ON cl_protocol.node_id = node_sel.node_id
  ORDER BY node_sel.node_id, cl_protocol_id
), cl_protocol_ins AS (
  INSERT INTO cl_protocol (cl_protocol_id, node_id, cl_protocol_name, cl_protocol_class)
  OVERRIDING SYSTEM VALUE
  SELECT new_cl_protocol_id, new_node_id, cl_protocol_name, cl_protocol_class
  FROM cl_protocol_sel
), induct_sel AS (
  SELECT induct_id, node_sel.node_id, node_sel.new_node_id, type, node_sel.new_host_id,
    cl_protocol_sel.new_cl_protocol_id, cl_protocol_sel.cl_protocol_name,
    duct_name, cli_command, uses_ltp,
    nextval(pg_get_serial_sequence('induct', 'induct_id')) AS new_induct_id
  FROM node_sel
  JOIN induct ON induct.node_id = node_sel.node_id
  LEFT JOIN cl_protocol_sel ON induct.cl_protocol_id = cl_protocol_sel.cl_protocol_id
    AND node_sel.new_node_id = cl_protocol_sel.new_node_id
  ORDER BY node_sel.node_id, induct_id
), induct_ins AS (
  INSERT INTO induct (induct_id, type, node_id, host_id, cl_protocol_id,
    cl_protocol_name, duct_name, cli_command, uses_ltp)
  OVERRIDING SYSTEM VALUE
  SELECT new_induct_id, type, new_node_id, new_host_id, new_cl_protocol_id,
    cl_protocol_name, duct_name, cli_command, uses_ltp
  FROM induct_sel
), seat_sel AS (
  SELECT seat_id, type, node_sel.node_id, node_sel.new_node_id, node_sel.new_host_id,
    lsi_command, nextval(pg_get_serial_sequence('seat', 'seat_id')) AS new_seat_id
  FROM node_sel
  JOIN seat ON seat.node_id = node_sel.node_id
  ORDER BY node_sel.node_id, seat_id
), seat_ins AS (
  INSERT INTO seat (seat_id, type, node_id, host_id, lsi_command)
  OVERRIDING SYSTEM VALUE
  SELECT new_seat_id, type, new_node_id, new_host_id, lsi_command
  FROM seat_sel
), induct_seat_ins AS (
  INSERT INTO induct_seat (induct_id, seat_id, node_id, uses_ltp)
  SELECT new_induct_id, new_seat_id, induct_sel.new_node_id, induct_sel.uses_ltp
  FROM induct_sel
  JOIN induct_seat ON induct_sel.induct_id = induct_seat.induct_id
  JOIN seat_sel ON seat_sel.seat_id = induct_seat.seat_id
    AND induct_sel.new_node_id = seat_sel.new_node_id
), induct_ip_ins AS (
  INSERT INTO induct_ip (induct_id, host_id, destination_id, port_number)
  SELECT new_induct_id, induct_sel.new_host_id,
    destination_sel.new_destination_id, port_number
  FROM induct_sel
  JOIN induct_ip ON induct_sel.induct_id = induct_ip.induct_id
  LEFT JOIN destination_sel
    ON induct_ip.destination_id = destination_sel.destination_id
), seat_ip_ins AS (
  INSERT INTO seat_ip (seat_id, host_id, destination_id, port_number)
  SELECT new_seat_id, seat_sel.new_host_id,
    destination_sel.new_destination_id, port_number
  FROM seat_sel
  JOIN seat_ip ON seat_sel.seat_id = seat_ip.seat_id
  LEFT JOIN destination_sel
    ON seat_ip.destination_id = destination_sel.destination_id
), induct_link_ins AS (
  INSERT INTO induct_link (induct_id, link_id, host_id, direction, uses_ltp)
  SELECT new_induct_id, new_link_id, induct_sel.new_host_id, link_sel.direction,
    induct_sel.uses_ltp
  FROM induct_sel
  JOIN induct_link ON induct_sel.induct_id = induct_link.induct_id
  JOIN link_sel ON induct_link.link_id = link_sel.link_id
), seat_link_ins AS (
  INSERT INTO seat_link (seat_id, link_id, host_id, direction)
  SELECT new_seat_id, new_link_id, seat_sel.new_host_id, link_sel.direction
  FROM seat_sel
  JOIN seat_link ON seat_sel.seat_id = seat_link.seat_id
  JOIN link_sel ON seat_link.link_id = link_sel.link_id
)
SELECT host_id FROM host_ins
"""
    ).bindparams(
        bindparam('host_id_to_copy', value=host_id_to_copy, type_=BigInteger),
        bindparam('operator_id', value=operator_id, type_=BigInteger),
        bindparam(
            'old_node_ids',
            value=[n.node_id for n in input_nodes],
            type_=ARRAY(BigInteger),
        ),
        bindparam(
            'new_node_numbers',
            value=[n.node_number for n in input_nodes],
            type_=ARRAY(BigInteger),
        ),
        # allocator_id must match that of corresponding operator's
        bindparam(
            'new_allocator_ids',
            value=[n.allocator_id for n in input_nodes],
            type_=ARRAY(BigInteger),
        ),
        bindparam(
            'new_operator_ids',
            value=[n.operator_id for n in input_nodes],
            type_=ARRAY(BigInteger),
        ),
    )  # fmt: skip

    try:
        host_id = db_session.scalar(stmt)
        db_session.commit()
        host = get(db_session, host_id)
    except exc.SQLAlchemyError as e:
        logger.exception(e._message())
        raise
    except Exception:
        logger.exception('Unexpected error')
        raise
    return host


def delete(db_session: Session, host_id: int) -> None:
    """Delete a host from the `host` table identified by host_id."""
    host = get(db_session, host_id)
    if host is None:
        return None
    # If this ever breaks, first thing to try is SET CONSTRAINTS ALL DEFERRED
    try:
        db_session.delete(host)
    except Exception:
        logger.exception('Unexpected error')
        raise
    db_session.commit()


def list_contacts(
    db_session: Session, operator_id: int, max_page_size: int, bookmark: str | None
) -> Page[Row[Tuple[Contact]]]:
    q = (
        select(Contact)
        .join(host_contact, Contact.contact_id == host_contact.c.contact_id)
        .where(host_contact.c.host_id == operator_id)
        .order_by(Contact.contact_id)
    )
    return select_page(db_session, q, per_page=max_page_size, page=bookmark)


def associate_contact(db_session: Session, host_id: int, contact_id: int) -> Contact:
    """Associates an existing contact with an host."""
    host = get(db_session, host_id)
    contact = contact_get(db_session, contact_id)
    try:
        host.contacts.append(contact)
        db_session.commit()
    except exc.IntegrityError as e:
        # Violating unique constraint on host_id and contact_id
        logger.exception(e._message())
        raise e
    except Exception:
        logger.exception(
            'Unexpected error', possible_reason='Non-existent host/contact'
        )
        raise
    return contact


def dissociate_contact(db_session: Session, host_id: int, contact_id: int) -> None:
    """Dissociates an existing contact with an host."""
    host = get(db_session, host_id)
    contact = contact_get(db_session, contact_id)
    try:
        host.contacts.remove(contact)
        db_session.commit()
    except ValueError:
        logger.exception('Contact is not in host.contacts list')
        raise
    except Exception:
        logger.exception(
            'Unexpected error', possible_reason='Non-existent host/contact'
        )
        raise


def contact_is_associated(db_session: Session, host_id: int, contact_id: int) -> bool:
    """Returns true if the contact identified by contact_id is
    associated with the host identified by host_id.
    """
    associated_in_db = db_session.scalar(
        select(
            exists().where(
                host_contact.c.host_id == host_id,
                host_contact.c.contact_id == contact_id,
            )
        )
    )
    host = get(db_session, host_id)
    if host is None:
        return False
    contact = contact_get(db_session, contact_id)
    if contact is None:
        return False
    associated_in_orm = contact in host.contacts
    if not associated_in_db:
        logger.info('Not associated in database')
        return False
    if not associated_in_orm:
        logger.error(
            'host & contact: not associated in ORM',
            note='If the ORM works correctly, this should never be logged',
        )
        return False
    return associated_in_db and associated_in_orm

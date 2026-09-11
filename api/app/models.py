from __future__ import annotations

import enum
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address

import structlog
from sqlalchemy import (
    DDL,
    CheckConstraint,
    Column,
    ForeignKeyConstraint,
    Identity,
    Index,
    Table,
    UniqueConstraint,
    event,
    func,
    insert,
    inspect,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import (
    INET,
    INT8MULTIRANGE,
    JSONB,
    TIMESTAMP,
    ExcludeConstraint,
    Range,
)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ExecutableDDLElement, ForeignKey
from sqlalchemy.sql import table
from sqlalchemy.types import (
    BigInteger,
    Boolean,
    Enum,
    Integer,
    SmallInteger,
    Text,
)

from .database import Base

logger = structlog.stdlib.get_logger()

# Postgres 15 allows foreign key ON DELETE SET actions to affect only
# specified columns. SQLAlchemy's postgresql dialect doesn't have an
# official implementation for this yet, so we'll make it ourselves.
# Register a new postgresql dialect specific keyword for ForeignKeyConstraint.
ForeignKeyConstraint.argument_for('postgresql', 'ondelete_set_null_columns', None)


# Provide a custom compiler that uses the new argument
@compiles(ForeignKeyConstraint, 'postgresql')
def compile_foreign_key_constraint(constraint, compiler, **kw):
    stmt = compiler.visit_foreign_key_constraint(constraint, **kw)
    ondelete_set_null_columns = constraint.dialect_options['postgresql'][
        'ondelete_set_null_columns'
    ]

    if constraint.ondelete == 'SET NULL' and ondelete_set_null_columns:
        child_cols = ', '.join(
            [compiler.preparer.quote(c) for c in ondelete_set_null_columns]
        )
        stmt = stmt.replace('ON DELETE SET NULL', f'ON DELETE SET NULL ({child_cols})')
    return stmt


class ContactPhoneNumber(Base):
    """A table to store phone numbers associated with a contact.

    Besides blank strings, phone numbers can be any string. There is no
    restriction on duplicate phone numbers.
    """

    __tablename__ = 'contact_phone_number'

    contact_id: Mapped[int] = mapped_column(
        ForeignKey('contact.contact_id', ondelete='CASCADE'), primary_key=True
    )
    # Integer should suffice; I don't expect a point of contact to have over
    # 2 billion phone numbers. The application could even allow up to 4 billion
    # if you start counting at -2^31 instead of 0.
    order_pos: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone_number: Mapped[str] = mapped_column(
        Text, CheckConstraint('length(trim(from phone_number)) > 0', name='not_blank')
    )
    preferred: Mapped[bool] = mapped_column(Boolean, server_default=text('FALSE'))

    contact: Mapped['Contact'] = relationship(back_populates='phone_numbers')

    def __repr__(self) -> str:
        return (
            f'ContactPhoneNumber(contact_id={self.contact_id!r},'
            f' order_pos={self.order_pos!r},'
            f' phone_number={self.phone_number!r},'
            f' preferred={self.preferred!r})'
        )


allocator_contact = Table(
    'allocator_contact',
    Base.metadata,
    Column(
        'contact_id',
        ForeignKey('contact.contact_id', ondelete='CASCADE'),
        primary_key=True,
    ),
    Column(
        'allocator_id',
        ForeignKey('allocator.allocator_id', onupdate='CASCADE', ondelete='CASCADE'),
        primary_key=True,
        index=True,
    ),
)


operator_contact = Table(
    'operator_contact',
    Base.metadata,
    Column(
        'contact_id',
        ForeignKey('contact.contact_id', ondelete='CASCADE'),
        primary_key=True,
    ),
    Column(
        'operator_id',
        ForeignKey('operator.operator_id', ondelete='CASCADE'),
        primary_key=True,
        index=True,
    ),
)


host_contact = Table(
    'host_contact',
    Base.metadata,
    Column(
        'contact_id',
        ForeignKey('contact.contact_id', ondelete='CASCADE'),
        primary_key=True,
    ),
    Column(
        'host_id',
        ForeignKey('host.host_id', ondelete='CASCADE'),
        primary_key=True,
        index=True,
    ),
)


node_contact = Table(
    'node_contact',
    Base.metadata,
    Column(
        'contact_id',
        ForeignKey('contact.contact_id', ondelete='CASCADE'),
        primary_key=True,
    ),
    Column(
        'node_id',
        ForeignKey('node.node_id', ondelete='CASCADE'),
        primary_key=True,
        index=True,
    ),
)


class Contact(Base):
    """A contact consists a name and email. A contact can be used by
    operators, allocators, hosts, and nodes at the same time. Each
    entity can also have multiple contacts.

    Records in this table have nothing to do with contacts from contact
    plans.

    Records in this table also need not match the 'Point of Contact'
    column of the 'ipn' Scheme URI Allocator Identifiers registry
    defined in RFC 9758, though when records are used to associate with
    allocators, they should probably be relevant to that 'Point of
    Contact' column to avoid confusing people.
    """

    __tablename__ = 'contact'

    contact_id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    # No need to split this into first_name and last_name, just let the user
    # choose to display whatever they want as their contact information.
    # Check constraint b/c doesn't make sense to have empty string as name.
    contact_name: Mapped[str] = mapped_column(
        Text,
        CheckConstraint('length(trim(from contact_name)) > 0', name='not_blank'),
        index=True,
    )
    email: Mapped[str | None] = mapped_column(Text, index=True)

    # If passive_deletes=False (default), when trying to delete a contact,
    # SQLAlchemy will try to load any allocators/operators/etc., and delete from
    # the association table first before deleting the contact itself. But a
    # trigger fires after deleting from the association tables which will delete
    # any contacts that aren't associated with anything.
    # So if a contact was connected to one operator, then trying to delete the
    # contact would first delete from operator_contact. The trigger fires which
    # deletes the contact because it's not associated with anything. Then
    # SQLAlchemy tries to delete the contact; but this is redundant because the
    # trigger already deleted the contact. SQLAlchemy then gives us a warning
    # that we're emitting a DELETE but not actually deleting something.
    # Instead, if we use passive_deletes='all' (or True also worked in testing),
    # then only the DELETE statement for the contact gets sent. The database
    # will handle the association table because of the FK ON DELETE CASCADE.
    # Note that if .allocators/.operators/etc. are in session, then trying to
    # delete the contact will emit a DELETE from the association table
    # regardless of what we set passive_deletes to.
    allocators: Mapped[list['Allocator']] = relationship(
        secondary=allocator_contact,
        back_populates='contacts',
        passive_deletes='all',
        order_by='Allocator.allocator_id',
    )
    operators: Mapped[list['Operator']] = relationship(
        secondary=operator_contact,
        back_populates='contacts',
        passive_deletes='all',
        order_by='Operator.operator_id',
    )
    hosts: Mapped[list['Host']] = relationship(
        secondary=host_contact,
        back_populates='contacts',
        passive_deletes='all',
        order_by='Host.host_id',
    )
    nodes: Mapped[list['Node']] = relationship(
        secondary=node_contact,
        back_populates='contacts',
        passive_deletes='all',
        order_by='Node.node_id',
    )

    # Phone numbers belong to a contact. Delete the number if it
    # gets dissociated with the contact
    phone_numbers: Mapped[list[ContactPhoneNumber]] = relationship(
        back_populates='contact',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='ContactPhoneNumber.order_pos',
    )

    def __repr__(self) -> str:
        return (
            f'Contact(contact_id={self.contact_id!r},'
            f' contact_name={self.contact_name!r},'
            f' email={self.email!r})'
        )


class Allocator(Base):
    """Records in this table represent allocators as defined in
    RFC 9758. This table is not the same as the "Allocator Identifiers
    registry" as defined in Section 9.1, but this table does use the IDs
    from that registry as primary keys.

    In general, we have a policy of
    Allocator -> Operator -> Node
    where an allocator (e.g. "Mars Program") which has access to the
    full range of node numbers [0, 2^32 - 1] assigns node numbers to
    an operator (e.g. "Mission 1").
    N.b., RFC 9758 does not talk about our "operator" concept; an
    allocator "assigns Node Numbers according to its own policies"
    (Section 3.2). This policy is expected to be used by most nodes in
    our database, but the database allows for node records without
    an operator.
    See the docstring for the 'node' table for more information.
    """

    __tablename__ = 'allocator'

    # RFC 9758 does not invalidate Allocator Identifiers >= 2^32,
    # simply reserves them, so we need `bigint` (Postgres' `integer` only
    # goes up to 2^31 - 1)
    allocator_id: Mapped[int] = mapped_column(
        BigInteger,
        CheckConstraint('allocator_id >= 0', name='nonnegative'),
        primary_key=True,
        autoincrement=False,
    )
    # Allocator's "name" attribute as mentioned in RFC 9758.
    # The RFC doesn't say whether or not a name is required, but I assume
    # that it is. Probably shouldn't have a unique index on this column,
    # I imagine you could have "Org A" with range 6-8, and all Allocators
    # in that range have the same name of "Org A".
    allocator_name: Mapped[str] = mapped_column(Text, index=True)

    # Operators must exist under an allocator. Database prevents deleting
    # allocator if operators still use it. Use passive_deletes='all' so
    # SQLAlchemy doesn't try to set operator.allocator_id to null.
    operators: Mapped[list['Operator']] = relationship(
        back_populates='allocator',
        passive_deletes='all',
        order_by='Operator.operator_id',
    )
    # Nodes must exist under an allocator. Database prevents deleting allocator
    # if nodes still use it. Use passive_deletes='all' so SQLAlchemy doesn't try
    # to set node.allocator_id to null.
    nodes: Mapped[list['Node']] = relationship(
        back_populates='allocator',
        passive_deletes='all',
        order_by='Node.allocator_id, Node.node_number',
    )
    # Contacts can exist without an allocator if still used by another
    # entity.
    # Not really sure what 'all' does here, see comments for the Operator
    # class below.
    contacts: Mapped[list[Contact]] = relationship(
        secondary=allocator_contact,
        back_populates='allocators',
        passive_deletes='all',
        order_by=Contact.contact_id,
    )

    def __repr__(self) -> str:
        return (
            f'Allocator(allocator_id={self.allocator_id!r},'
            f' allocator_name={self.allocator_name!r})'
        )


@event.listens_for(Allocator.__table__, 'after_create')
def insert_after_create_allocator(target, connection, **kw):
    logger.info('Inserting Default Allocator to `allocator`')
    connection.execute(
        insert(Allocator),
        [
            {'allocator_id': 0, 'allocator_name': 'Default Allocator'},
        ],
    )


class Operator(Base):
    """An operator has control over a set of nodes and their hosts.
    An operator has a range of node numbers allocated to it by its
    allocator.

    See the docstring for the 'allocator' table for more information
    about the allocator policy expected to be used in this database.

    Operators with the same allocator cannot have overlapping allocated
    node numbers. Nodes that are underneath an operator must have their
    node number be within their operator's allocated node numbers.
    """

    __tablename__ = 'operator'

    operator_id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    operator_name: Mapped[str] = mapped_column(Text, index=True)
    # By default, we assume an operator is under the default allocator.
    # We want to be able to update allocator.allocator_id (not a surrogate key)
    allocator_id: Mapped[int] = mapped_column(
        ForeignKey('allocator.allocator_id', onupdate='CASCADE', ondelete='NO ACTION'),
        server_default=text('0'),
    )
    # psycopg documentation https://www.psycopg.org/psycopg3/docs/basic/pgtypes.html#multirange-adaptation
    # "PostgreSQL will perform normalisation on Multirange objects used as
    #  query parameters, so, when they are fetched back, they will be found
    #  ordered, with overlapping ranges merged, etc."
    # N.b., this is NOT NULL. To express an operator without any allocated
    # node numbers, use an empty list.
    allocated_node_numbers: Mapped[list[Range[int]]] = mapped_column(
        INT8MULTIRANGE,
        CheckConstraint(
            "isempty(allocated_node_numbers - '{[0,4294967295]}'::int8multirange)",
            name='allocated_node_numbers_limit',
        ),
        server_default=text("'{}'::int8multirange"),
    )

    # Operators must be under an allocator
    allocator: Mapped[Allocator] = relationship(back_populates='operators')
    # Contacts can exist without an operator if still used by another entity.
    # 'all' means no "nulling out" of the child foreign keys when an operator
    # is deleted.
    # N.b., "nulling out" still occurs if the Contact is de-associated with
    # its operator, but our association table has both columns as a composite
    # primary key, so this is supposed to cause an error. But I didn't have an
    # error from de-associating in testing.
    contacts: Mapped[list[Contact]] = relationship(
        secondary=operator_contact,
        back_populates='operators',
        passive_deletes='all',
        order_by=Contact.contact_id,
    )
    # Hosts and nodes can exist independently from an operator. Use 'all' for
    # passive_deletes to prevent SQLAlchemy from emitting set null statements
    # (the database handles that itself) when an operator is deleted.
    hosts: Mapped[list['Host']] = relationship(
        back_populates='operator', passive_deletes='all', order_by='Host.host_id'
    )
    nodes: Mapped[list['Node']] = relationship(
        back_populates='operator',
        passive_deletes='all',
        overlaps='nodes',
        order_by='Node.allocator_id, Node.node_number',
    )

    __table_args__ = (
        # Exclusion constraint prevents operators with the same allocator from
        # having overlapping allocated node numbers.
        ExcludeConstraint(('allocator_id', '='), ('allocated_node_numbers', '&&')),
        # Redundant unique constraint for FK constraint in 'node'
        UniqueConstraint('allocator_id', 'operator_id'),
    )

    def __repr__(self) -> str:
        return (
            f'Operator(operator_id={self.operator_id!r},'
            f' operator_name={self.operator_name!r},'
            f' allocator_id={self.allocator_id!r},'
            f' allocated_node_numbers={self.allocated_node_numbers!r})'
        )


# Think we need this for that exclusion constraint to work correctly
event.listen(
    Operator.__table__,
    'before_create',
    DDL('CREATE EXTENSION IF NOT EXISTS btree_gist;'),
)


class NewlineEnum(str, enum.Enum):
    """Set of mandatory break (non-tailorable) control characters or
    sequences of control characters in Unicode.
    """

    # Based on Unicode 16.0.0 Standard Annex #14
    # https://www.unicode.org/reports/tr14/tr14-53.html
    # Rules LB4 and LB5 are what we care about.
    # Sort by Unicode value
    LF = 'U+000A LINE FEED (LF)'
    VT = 'U+000B LINE TABULATION (VT)'
    FF = 'U+000C FORM FEED (FF)'
    CR = 'U+000D CARRIAGE RETURN (CR)'
    CRLF = 'U+000D + U+000A (CRLF)'
    NEL = 'U+0085 NEXT LINE (NEL)'
    LS = 'U+2028 LINE SEPARATOR'
    PS = 'U+2029 PARAGRAPH SEPARATOR'


class Host(Base):
    """A host is hardware that runs ION (i.e., a computer that hosts
    ION nodes).

    Hosts do not have to be under an operator.
    Since node.operator_id is also optional, you could have a host tied
    to an operator with nodes under a different allocator than the
    operator's allocator as long as that node does not have an operator.
    """

    __tablename__ = 'host'

    host_id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    # See hostname(7). Be liberal in what names we accept since what's allowed
    # varies by system.
    hostname: Mapped[str] = mapped_column(Text, index=True)
    # ION Config Tool has a description for hosts
    host_description: Mapped[str | None] = mapped_column(Text, index=True)
    # Hosts do not need to be under an operator.
    operator_id: Mapped[int | None] = mapped_column(
        ForeignKey('operator.operator_id', ondelete='SET NULL')
    )
    # Range of SCID varies depending on version. We don't care about that, so
    # leave it as integer to be flexible.
    sana_scid: Mapped[int | None] = mapped_column(Integer)
    # Assume nonvariable binary architecture. Even if there was an architecture
    # that ran ION which isnt this architecture, smallint's range should be enough
    # to capture the word size.
    # LTP Config Tool intends users to input either 32 ot 64 for bit word size.
    # Description for heapWords in ionconfig(5) also suggests it should be
    # calculated based on whether a system is 32-bit or 64-bit. ION itself doesn't
    # try to build or run regression tests on 32 bit systems, so there may be a
    # point where this column is redundant and it's value is always 64.
    word_size: Mapped[int | None] = mapped_column(
        SmallInteger,
        CheckConstraint('word_size = 32 OR word_size = 64', name='word_size'),
    )
    # Because we're using UTF-8, might want to have all the Unicode terminators
    # in this Enum https://en.wikipedia.org/wiki/Newline#Unicode
    newline: Mapped[str | None] = mapped_column(
        Enum(
            NewlineEnum,
            name='newline_type',
            values_callable=lambda x: [e.value for e in x],
        )
    )

    operator: Mapped[Operator] = relationship(back_populates='hosts')
    # Destinations have a many-to-one relationship with a host, if the host is
    # gone or a destination get de-associated from host, delete the destination.
    destinations: Mapped[list['Destination']] = relationship(
        back_populates='host',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='Destination.destination_id',
    )
    # Nodes do not have to exist on a host. Use passive_deletes='all' so that
    # SQLAlchemy doesn't set the referencing column to null (the database handles
    # that with ON DELETE SET NULL) when the host is deleted.
    nodes: Mapped[list['Node']] = relationship(
        foreign_keys='Node.host_id',
        back_populates='host',
        passive_deletes='all',
        order_by='Node.allocator_id, Node.node_number',
    )
    # Links have to be related to a host, if they de-associate, delete them
    links: Mapped[list['Link']] = relationship(
        back_populates='host',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='Link.link_id',
    )
    # Contacts can exist without any host if still used by another entity.
    # Not really sure what 'all' does here, see comments for the Operator
    # class below.
    contacts: Mapped[list[Contact]] = relationship(
        secondary=host_contact,
        back_populates='hosts',
        passive_deletes='all',
        order_by=Contact.contact_id,
    )

    __table_args__ = (
        # Redundant unique constraint for FK constraint in 'node'
        UniqueConstraint('operator_id', 'host_id'),
    )

    def __repr__(self) -> str:
        return (
            f'Host(host_id={self.host_id!r},'
            f' hostname={self.hostname!r},'
            f' host_description={self.host_description!r},'
            f' operator_id={self.operator_id!r},'
            f' sana_scid={self.sana_scid!r},'
            f' word_size={self.word_size!r},'
            f' newline={self.newline!r})'
        )


class Destination(Base):
    """Table for destinations associated with a host. These are used
    locally at a host for inducts and spans that use IP addresses.

    `registered_name` refers to a name that is looked up with respect
    to a host to derive an IP address (e.g., locally defined in a file
    or remotely at a service name registry).

    When inserting a value to the `ip_address` column, use the
    ipaddress.ip_interface() function from the Python standard library.
    (Actually, I think you can insert a string and psycopg will convert
    it to an ipaddress object for you?)
    """

    __tablename__ = 'destination'

    destination_id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    # https://www.psycopg.org/psycopg3/docs/basic/adapt.html#network-data-types-adaptation
    # psycopg converts between Postgres' INET type with Python's IPv4Address and
    # IPv6Address when the INET value indicates a single address.
    ip_address: Mapped[IPv4Address | IPv6Address | None] = mapped_column(
        INET,
        CheckConstraint(
            '(family(ip_address) = 4 AND masklen(ip_address) = 32)'
            ' OR (family(ip_address) = 6 AND masklen(ip_address) = 128)',
            name='subnet_mask_limit',
        ),
    )
    # When locally defined in a file, the restrictions on the name depends on
    # the OS. This column only matters locally, so we should be flexible in what
    # we accept.
    registered_name: Mapped[str | None] = mapped_column(Text)
    # Destinations have to exist on a host, delete if the host is gone.
    # Omit ON UPDATE option because host.host_id shouldn't be updated.
    host_id: Mapped[int] = mapped_column(ForeignKey('host.host_id', ondelete='CASCADE'))

    host: Mapped[Host] = relationship(back_populates='destinations')
    # Multiple inducts can use the same destination (but with different
    # port numbers). Inducts still exist even if they're not using a
    # destination. Use passive_deletes='all' so when a destination gets
    # deleted, it doesn't try to set induct_ip.host_id to NULL
    inducts: Mapped[list['InductIp']] = relationship(
        back_populates='destination',
        passive_deletes='all',
        order_by='InductIp.induct_id',
    )
    # SeatIp uses the same logic as InductIp
    seats: Mapped[list['SeatIp']] = relationship(
        back_populates='destination',
        passive_deletes='all',
        order_by='SeatIp.seat_id',
    )

    __table_args__ = (
        CheckConstraint(
            '(ip_address IS NULL) <> (registered_name IS NULL)',
            name='ip_address_xor_reg_name',
        ),
        # Prevent duplicate ip_address values on the same host
        UniqueConstraint('ip_address', 'host_id'),
        # Prevent duplicate registered_name values on the same host
        UniqueConstraint('registered_name', 'host_id'),
        # Redundant unique constraint for FK constraint in `induct`
        UniqueConstraint('host_id', 'destination_id'),
    )

    def __eq__(self, other):
        return (
            isinstance(other, Destination)
            and other.ip_address == self.ip_address
            and other.registered_name == self.registered_name
            and other.host_id == self.host_id
        )

    def __repr__(self) -> str:
        return (
            f'Destination(destination_id={self.destination_id!r},'
            f' ip_address={self.ip_address!r},'
            f' registered_name={self.registered_name!r},'
            f' host_id={self.host_id!r})'
        )


underlying_communication_service_link = Table(
    'underlying_communication_service_link',
    Base.metadata,
    Column(
        'underlying_communication_service_id',
        # Don't delete underlying_communication_service records if they're still
        # used by a link
        ForeignKey(
            'underlying_communication_service.underlying_communication_service_id',
            ondelete='NO ACTION',
        ),
        primary_key=True,
    ),
    Column(
        'link_id',
        ForeignKey('link.link_id', ondelete='CASCADE'),
        primary_key=True,
        index=True,
    ),
)


class UnderlyingCommunicationService(Base):
    """Lookup table for underlying communication services. The point is
    to store some information about the plumbing that is below a
    convegence layer.

    See docstring of `Link` class for more information.
    """

    __tablename__ = 'underlying_communication_service'

    underlying_communication_service_id: Mapped[int] = mapped_column(
        Integer, Identity(always=True), primary_key=True
    )
    underlying_communication_service_name: Mapped[str] = mapped_column(Text, index=True)
    underlying_communication_service_abbreviation: Mapped[str] = mapped_column(
        Text, index=True
    )

    # Database doesn't allow underlying communication service records to be
    # deleted if they're still used by a link record.
    # See M:N relationship comment in Link for why we use passive_deletes=True
    links: Mapped[list['Link']] = relationship(
        secondary=underlying_communication_service_link,
        back_populates='underlying_communication_services',
        passive_deletes=True,
        order_by='Link.link_id',
    )

    def __repr__(self) -> str:
        return (
            'UnderlyingCommunicationService(underlying_communication_service_id='
            f'{self.underlying_communication_service_id!r},'
            ' underlying_communication_service_name='
            f'{self.underlying_communication_service_name!r},'
            ' underlying_communication_service_abbreviation='
            f'{self.underlying_communication_service_abbreviation!r})'
        )


default_underlying_communication_services = [
    {
        'underlying_communication_service_name': 'Unified Space Data Link Protocol',
        'underlying_communication_service_abbreviation': 'USLP',
    },
    {
        'underlying_communication_service_name': 'TM Space Data Link Protocol',
        'underlying_communication_service_abbreviation': 'TM (Data Link)',
    },
    {
        'underlying_communication_service_name': 'TM Synchronization and Channel Coding',
        'underlying_communication_service_abbreviation': (
            'TM (Synchronization and Channel Coding)'
        ),
    },
    {
        'underlying_communication_service_name': 'TC Space Data Link Protocol',
        'underlying_communication_service_abbreviation': 'TC (Data Link)',
    },
    {
        'underlying_communication_service_name': 'TC Synchronization and Channel Coding',
        'underlying_communication_service_abbreviation': (
            'TC (Synchronization and Channel Coding)'
        ),
    },
    {
        'underlying_communication_service_name': 'AOS Space Data Link Protocol',
        'underlying_communication_service_abbreviation': 'AOS',
    },
    {
        'underlying_communication_service_name': (
            'Proximity-1 Space Link Protocol—Data Link Layer'
        ),
        'underlying_communication_service_abbreviation': 'Prox-1 (Data Link)',
    },
    {
        'underlying_communication_service_name': (
            'Proximity-1 Space Link Protocol—Coding and Synchronization Sublayer'
        ),
        'underlying_communication_service_abbreviation': (
            'Prox-1 (Synchronization and Channel Coding)'
        ),
    },
    {
        'underlying_communication_service_name': 'Ethernet',
        'underlying_communication_service_abbreviation': 'Ethernet',
    },
    {
        'underlying_communication_service_name': 'Optical',
        'underlying_communication_service_abbreviation': 'Optical',
    },
    {
        'underlying_communication_service_name': 'SpaceWire',
        'underlying_communication_service_abbreviation': 'SpaceWire',
    },
    {
        'underlying_communication_service_name': 'Serial',
        'underlying_communication_service_abbreviation': 'Serial',
    },
    {
        'underlying_communication_service_name': (
            'Universal Asynchronous Receiver-Transmitter'
        ),
        'underlying_communication_service_abbreviation': 'UART',
    },
    {
        'underlying_communication_service_name': 'Space Packet Protocol',
        'underlying_communication_service_abbreviation': 'SPP',
    },
    {
        'underlying_communication_service_name': 'Encapsulation Packet Protocol',
        'underlying_communication_service_abbreviation': 'EPP',
    },
    {
        'underlying_communication_service_name': 'User Datagram Protocol',
        'underlying_communication_service_abbreviation': 'UDP',
    },
    {
        'underlying_communication_service_name': (
            'Datagram Congestion Control Protocol'
        ),
        'underlying_communication_service_abbreviation': 'DCCP',
    },
]


@event.listens_for(UnderlyingCommunicationService.__table__, 'after_create')
def insert_after_create_underlying_communication_service(target, connection, **kw):
    logger.info('Inserting lookup values to `underlying_communication_service`')
    connection.execute(
        insert(UnderlyingCommunicationService),
        default_underlying_communication_services,
    )


class CommDirectionEnum(str, enum.Enum):
    FULL_DUPLEX = 'Full-duplex'
    HALF_DUPLEX = 'Half-duplex'
    SIMPLEX_IN = 'Simplex (incoming)'
    SIMPLEX_OUT = 'Simplex (outgoing)'


class CommDirectionEnumInternal(str, enum.Enum):
    FULL_DUPLEX = 'Full-duplex'
    HALF_DUPLEX = 'Half-duplex'
    SIMPLEX_IN = 'Simplex (incoming)'
    SIMPLEX_OUT = 'Simplex (outgoing)'
    # Nullable `direction` means FK ON UPDATE can't update when a referencing
    # `direction` is null. Rather than handling this with trigger, we use a
    # string to stand in for null so we can make link.direction and
    # induct_link.direction NOT NULL.
    N_A = 'N/A'


induct_link = Table(
    'induct_link',
    Base.metadata,
    Column('induct_id', primary_key=True),
    Column('link_id', primary_key=True),
    Column('host_id', primary_key=True),
    Column(
        'direction',
        CheckConstraint(
            f"direction <> '{CommDirectionEnumInternal.SIMPLEX_OUT.value}'",
            name='no_simplex_outgoing',
        ),
        nullable=False,
    ),
    Column(
        'uses_ltp',
        CheckConstraint('uses_ltp IS FALSE', name='no_uses_ltp'),
        primary_key=True,
        server_default=text('FALSE'),
    ),
    ForeignKeyConstraint(
        ['induct_id', 'host_id', 'uses_ltp'],
        ['induct.induct_id', 'induct.host_id', 'induct.uses_ltp'],
        # An `induct` cannot have a different host_id if there is still an
        # association with a link on the old host. If uses_ltp updates, then
        # it will be changing from false to true which we don't allow anyway.
        # Assume induct.induct_id does not change.
        onupdate='NO ACTION',
        # Deleting an induct should delete this record
        ondelete='CASCADE',
        # We liberally use DEFERRABLE INITIALLY IMMEDIATE in FK constraints
        # even where we don't need to set constraints to deferred since there
        # is likely no performance penalty.
        # See https://www.postgresql.org/message-id/11998.1347809835%40sss.pgh.pa.us
        deferrable=True,
        initially='IMMEDIATE',
    ),
    Index(
        'ix_induct_link_induct_id_host_id_uses_ltp', 'induct_id', 'host_id', 'uses_ltp'
    ),
    ForeignKeyConstraint(
        ['link_id', 'host_id', 'direction'],
        ['link.link_id', 'link.host_id', 'link.direction'],
        # A `link` cannot have a different host_id if there is still an
        # association with an induct on the old host. If link.host_id changes,
        # trying to update induct_link.host_id will violate the FK constraint
        # to induct. CASCADE is used to keep `direction` updated. If it updates
        # to simplex (outgoing), then the check constraint on direction fails.
        onupdate='CASCADE',
        # Deleting a link should delete this record
        ondelete='CASCADE',
        deferrable=True,
        initially='IMMEDIATE',
    ),
    Index(
        'ix_induct_link_link_id_host_id_direction', 'link_id', 'host_id', 'direction'
    ),
)

seat_link = Table(
    'seat_link',
    Base.metadata,
    Column('seat_id', primary_key=True),
    Column('link_id', primary_key=True),
    Column('host_id', primary_key=True),
    Column(
        'direction',
        CheckConstraint(
            f"direction <> '{CommDirectionEnumInternal.SIMPLEX_OUT.value}'",
            name='no_simplex_outgoing',
        ),
        nullable=False,
    ),
    ForeignKeyConstraint(
        ['seat_id', 'host_id'],
        ['seat.seat_id', 'seat.host_id'],
        # A `seat` cannot have a different host_id if there is still an
        # association with a link on the old host. (We assume ON UPDATE only
        # refers to seat.host_id changing and not seat.seat_id.)
        onupdate='NO ACTION',
        # Deleting a seat should delete this record
        ondelete='CASCADE',
        deferrable=True,
        initially='IMMEDIATE',
    ),
    # The query we use to check for FKs with missing indexes does not say
    # that this FK is missing an index, but we'll just add one anyway.
    Index('ix_seat_link_seat_id_induct_id', 'seat_id', 'host_id'),
    ForeignKeyConstraint(
        ['link_id', 'host_id', 'direction'],
        ['link.link_id', 'link.host_id', 'link.direction'],
        # A `link` cannot have a different host_id if there is still an
        # association with a seat on the old host. If link.host_id changes,
        # trying to update seat_link.host_id will violate the FK constraint
        # to seat. CASCADE is used to keep `direction` updated. If it updates
        # to simplex (outgoing), then the check constraint on direction fails.
        onupdate='CASCADE',
        # Deleting a link should delete this record
        ondelete='CASCADE',
        deferrable=True,
        initially='IMMEDIATE',
    ),
    Index('ix_seat_link_link_id_host_id_direction', 'link_id', 'host_id', 'direction'),
)


class Link(Base):
    """Link records have information about what a convergence layer is
    running over.

    This table and its related tables have structures that don't map
    cleanly to the protocol layers described in CCSDS 130.0-G-4 nor the
    OSI model. "Links" for ION don't go beyond the convergence layer,
    but users want to know what a CL protocol is running over. While
    synchronization and coding information is too decoupled from ION
    operation, knowing that LTP is running over an X-band radio or that
    STCP is running over Ethernet is helpful for database users. It's
    this sort of information that these link-related tables capture.

    A link record is owned by a host and can be referenced by *duct
    records owned by node records under said host.

    This is a parent table for table-per-type inheritance, currently
    with one subtype for RF.
    A record in `link_rf` must reference a record here. Deleting a
    record in `link` will delete its matching child record because
    of the FK constraint.
    There could also be a record here that isn't used in `link_rf`.
    """

    __tablename__ = 'link'

    link_id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    # type shouldn't be exposed to application, only used by database to
    # prevent one link_id from being used by multiple link types
    type: Mapped[str | None] = mapped_column(Text)
    # A record here belongs to a host, if the host is deleted, the record here
    # should also be deleted.
    # Omit ON UPDATE option because host.host_id shouldn't be updated
    host_id: Mapped[int] = mapped_column(
        ForeignKey('host.host_id', ondelete='CASCADE'), index=True
    )
    direction: Mapped[str] = mapped_column(
        Enum(
            CommDirectionEnumInternal,
            name='direction_type',
            values_callable=lambda x: [e.value for e in x],
        )
    )

    host: Mapped[Host] = relationship(back_populates='links')
    # These are one-to-one relationships, delete them if they dissociate.
    # Use passive_deletes=True since the database handles deletions with
    # ON DELETE CASCADE.
    link_rf: Mapped['LinkRf'] = relationship(
        back_populates='link',
        cascade='all, delete-orphan',
        passive_deletes=True,
        # foreign_keys=[link_id],
        primaryjoin='Link.link_id == LinkRf.link_id',
    )
    # link_optical: Mapped['LinkOptical'] = relationship(
    #     back_populates='link', cascade='all, delete-orphan',
    #     passive_deletes=True
    # )
    # Many-to-many relationship with inducts, seats, and underlying
    # communication services.
    # N.b., passive_deletes='all' only means something when there is no
    # delete / delete-orphan cascade enabled. We don't have a cascade here
    # because we don't want to delete `link` records when an `induct` is
    # deleted (nor vice versa). Without 'all', SQLAlchemy will null out
    # child FKs, but since we're using an association table, the child
    # `induct` table (from the `link` table's view) doesn't have any FK
    # to null out. So I don't think it matters if we use 'all' or True.
    inducts: Mapped[list['Induct']] = relationship(
        secondary=induct_link,
        back_populates='links',
        passive_deletes=True,
        foreign_keys=[link_id, host_id, direction],
        primaryjoin=(
            'and_(Link.link_id == foreign(induct_link.c.link_id),'
            ' Link.host_id == foreign(induct_link.c.host_id),'
            ' Link.direction == foreign(induct_link.c.direction))'
        ),
        secondaryjoin=(
            'and_(Induct.induct_id == foreign(induct_link.c.induct_id),'
            ' Induct.host_id == foreign(induct_link.c.host_id),'
            ' Induct.uses_ltp == foreign(induct_link.c.uses_ltp))'
        ),
        order_by='Induct.induct_id',
    )
    seats: Mapped[list['Seat']] = relationship(
        secondary=seat_link,
        back_populates='links',
        passive_deletes=True,
        foreign_keys=[link_id, host_id, direction],
        primaryjoin=(
            'and_(Link.link_id == foreign(seat_link.c.link_id),'
            ' Link.host_id == foreign(seat_link.c.host_id),'
            ' Link.direction == foreign(seat_link.c.direction))'
        ),
        secondaryjoin=(
            'and_(Seat.seat_id == foreign(seat_link.c.seat_id),'
            ' Seat.host_id == foreign(seat_link.c.host_id))'
        ),
        order_by='Seat.seat_id',
    )
    underlying_communication_services: Mapped[list[UnderlyingCommunicationService]] = (
        relationship(
            secondary=underlying_communication_service_link,
            back_populates='links',
            passive_deletes=True,
            order_by=(
                UnderlyingCommunicationService.underlying_communication_service_abbreviation,
                UnderlyingCommunicationService.underlying_communication_service_id,
            ),
        )
    )

    __table_args__ = (
        # Only one type of link per link_id
        UniqueConstraint('type', 'link_id'),
        # Redundant unique constraint for FK constraint in induct_link
        UniqueConstraint('host_id', 'link_id', 'direction'),
    )

    def __repr__(self) -> str:
        return (
            f'Link(link_id={self.link_id!r},'
            f' type={self.type!r},'
            f' host_id={self.host_id!r},'
            f' direction={self.direction!r})'
        )


class Band(Base):
    """Lookup table for bands"""

    __tablename__ = 'band'

    band_id: Mapped[int] = mapped_column(
        Integer, Identity(always=True), primary_key=True
    )
    band_name: Mapped[str] = mapped_column(Text, index=True)

    # Database doesn't allow band records to be deleted if they're still
    # used by a link_rf record.
    # Use passive_deletes='all' so that SQLAlchemy doesn't try to set
    # link_rf.band_id to null when deleting a band record.
    links: Mapped[list['LinkRf']] = relationship(
        back_populates='band', passive_deletes='all', order_by='LinkRf.link_id'
    )

    def __repr__(self) -> str:
        return f'Band(band_id={self.band_id!r}, band_name={self.band_name!r})'


default_bands = [
    {'band_name': 'UHF'},
    {'band_name': 'S'},
    {'band_name': 'X'},
    {'band_name': 'Ka'},
]


@event.listens_for(Band.__table__, 'after_create')
def insert_after_create_band(target, connection, **kw):
    logger.info('Inserting lookup values to `band`')
    connection.execute(
        insert(Band),
        default_bands,
    )


class LinkRf(Base):
    """Table for keeping track of band used by a link.

    There is no trigger that deletes the parent `link` record if a
    record is deleted here. You should delete from the `link` table if
    you want to remove a link from the database.
    """

    __tablename__ = 'link_rf'

    # One-to-one relationship with an existing Link record
    link_id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(
        CheckConstraint("type = 'rf'", name='rf_type'), server_default='rf'
    )
    band_id: Mapped[int | None] = mapped_column(
        ForeignKey('band.band_id', ondelete='NO ACTION'), index=True
    )

    link: Mapped[Link] = relationship(back_populates='link_rf', single_parent=True)
    band: Mapped[Band] = relationship(back_populates='links')

    __table_args__ = (
        ForeignKeyConstraint(
            ['type', 'link_id'],
            ['link.type', 'link.link_id'],
            # link_rf.type should never be updated. If parent link.type is
            # updating, then the link_rf record should be deleted.
            onupdate='RESTRICT',
            ondelete='CASCADE',
        ),
        Index('ix_link_rf_type_link_id', type, link_id),
    )

    def __repr__(self) -> str:
        return (
            f'LinkRf(link_id={self.link_id!r},'
            f' type={self.type!r},'
            f' band_id={self.band_id!r})'
        )


# We don't have a good idea of what information is needed for an optical
# link yet, so this table's presence in the database would just be
# confusing. Leaving this commented out in case it will be helpful in
# the future.
# class LinkOptical(Base):
#     __tablename__ = 'link_optical'

#     # One-to-one relationship with an existing Link record
#     link_id: Mapped[int] = mapped_column(
#         ForeignKey('link.link_id', onupdate='CASCADE', ondelete='CASCADE'),
#         primary_key=True
#     )
#     type: Mapped[str] = mapped_column(
#         CheckConstraint("type = 'optical'", name='optical_type'),
#         server_default='optical'
#     )
#     # https://en.wikipedia.org/wiki/Fiber-optic_communication#Transmission_windows
#     # Looks like wavelength tends to be in thousands of nm. So assume
#     # wavelength is stored as nm
#     wavelength: Mapped[int | None] = mapped_column(Integer)

#     link: Mapped[Link] = relationship(back_populates='link_optical')

#     __table_args__ = (
#         ForeignKeyConstraint(
#             ['type', 'link_id'],
#             ['link.type', 'link.link_id'],
#             onupdate='RESTRICT',
#             ondelete='CASCADE'
#         ),
#         Index('ix_link_optical_type_link_id', type, link_id),
#     )

#     def __repr__(self) -> str:
#         return (
#             f'LinkOptical(link_id={self.link_id!r},'
#             f' type={self.type!r},'
#             f' wavelength={self.wavelength!r})'
#         )


class Node(Base):
    """A node is software; just an instance of ION running. A node can
    exist on only one host, and multiple nodes can exist on a host.

    Per Section 3.3.1 of RFC 9758, a particular node is uniquely
    identified by its Fully Qualified Node Number (FQNN), that is,
    (allocator_id, node_number). So node records here need to have
    an allocator.

    Nodes do not have to exist on a host, but they're a lot less
    meaningful without one since inducts and seats need references to
    host children to use destinations (IP addresses) and links.

    Nodes do not need to exist under an operator (not all nodes follow
    the Allocator -> Operator -> Node policy).
    If a node has an operator, and it is on a host, then it must have
    the same operator as its host. The node must have the same
    allocator_id as its operator, and node.node_number must be within
    the operator's allocated_node_numbers.
    A node with an operator but without a host is also allowed (the only
    difference is the restriction that operator_id matches with a host
    doesn't apply since there is no host).

    In summary, this schema allows for 3 use cases:
    1. Most common use case:
       (Allocator -> Operator -> Node)
       There's an operator connected to an allocator. The operator owns
       a host and the nodes on that host. The host's operator_id matches
       this operator. The nodes have an allocator_id and operator_id
       that matches this operator, and a host_id which matches the host.
       The node number of the node must be in the range of the
       operator's allocated node numbers.
    2. An operator with a non-zero allocator with nodes from other
       allocators (should be uncommon):
       (Mix of "Allocator -> Operator -> Node" and "Allocator -> Node")
       There's an operator connected to an allocator. The operator owns
       a host, and you attach a node record like the one mentioned in
       the "most common use case" to this host. But you also attach a
       node record with allocator_id = 0 and operator_id = NULL. (You
       can attach a node record to a host with any allocator_id as long
       as node.operator_id is null.) Because this node record's
       operator_id is NULL, its node number does not need to be in the
       range of the operator's node numbers. In that sense, we can say
       the node is *not* under an operator. But you could also say the
       node *is* under an operator in the sense that the host is under
       an operator.
    3. No operator (should be rare):
       (Allocator -> Node)
       The host.operator_id = NULL and nodes on that host also have
       node.operator_id = NULL. Nodes still need to have an
       allocator_id.
       Similar to the 2nd case, you could have every node on this host
       be from different allocators. But you can't add a node with an
       operator to a host without an operator.

    N.b., this schema limits a host to be under only one operator. It's
    not possible to add nodes from different operators to a host. (The
    only nodes that are not under the host's operator that you can add,
    are nodes that don't have an operator.)
    """

    __tablename__ = 'node'

    # Surrogate key stands in place for the FQNN (allocator_id, node_number)
    node_id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    # Per Section 3.3 of RFC 9758, node numbers must be in the inclusive
    # range [0, 2^32 - 1].
    node_number: Mapped[int] = mapped_column(
        BigInteger,
        CheckConstraint(
            'node_number >= 0 AND node_number <= 4294967295', name='node_number_limit'
        ),
    )
    # Nodes must have an allocator (by default, the default allocator)
    # We want to be able to update allocator.allocator_id (not a surrogate key)
    allocator_id: Mapped[int] = mapped_column(
        ForeignKey('allocator.allocator_id', onupdate='CASCADE', ondelete='NO ACTION'),
        server_default=text('0'),
        index=True,
    )
    # Nodes do not need to be under an operator, so nullable
    operator_id: Mapped[int | None] = mapped_column(BigInteger)
    # Nodes don't have to exist on a host. We need this foreign key because the
    # default behavior of FK constraints is `MATCH SIMPLE`, so in the composite
    # FK below, if we have a case where operator_id = NULL, then the constraint
    # will not require the row to match the referenced table (host).
    host_id: Mapped[int | None] = mapped_column(
        ForeignKey('host.host_id', ondelete='SET NULL')
    )
    # These ionconfig(5) parameters should be nullable. Conceive "null" as
    # meaning "use the default value that my version of ionadmin(1) uses".
    # The default values may change between ION versions, so don't set a default
    # value in the database or in the API.
    # Using integer since sdr_load_profile() (see sdr(3)) takes configFlags as
    # an int.
    # SDR_IN_DRAM (1)
    # SDR_IN_FILE (2)
    # SDR_REVERSIBLE (4)
    # SDR_BOUNDED (8)
    # configFlags == 0 fails ionstart, so forbid it.
    sdr_config_flags: Mapped[int | None] = mapped_column(
        Integer,
        CheckConstraint(
            'sdr_config_flags > 0 AND sdr_config_flags <= 15',
            name='config_flags_combinations',
        ),
    )
    # wmSize, sdrWmSize, and heapWords are defined with size_t in
    # ici/include/ion.h. size_t's max value is system dependent (SIZE_MAX in
    # <stdint.h>), but Postgres' max value for bigint should be enough for
    # any real node.
    # This is the size of the block of dynamic memory that will be used for this
    # ION node's working memory.
    # wmSize == 0 will always fail ionstart, so might as well forbid it.
    wm_size: Mapped[int | None] = mapped_column(
        BigInteger, CheckConstraint('wm_size > 0', name='positive_wm_size')
    )
    # Size of the block of dynamic memory that will be reserved as private
    # working memory for the SDR system.
    # sdrWmSize <= 0 is forced to 1_000_000 by ionadmin.
    sdr_wm_size: Mapped[int | None] = mapped_column(
        BigInteger, CheckConstraint('sdr_wm_size > 0', name='positive_sdr_wm_size')
    )
    # Number of words (of 32 bits each on a 32-bit machine, 64 bits each on a
    # 64-bit machine) of nominally non-volatile storage to use for ION's SDR
    # database.
    # heapWords == 0 also fails ionstart, so forbid it.
    heap_words: Mapped[int | None] = mapped_column(
        BigInteger, CheckConstraint('heap_words > 0', name='positive_heap_words')
    )
    # To be used by ION Config Tool to name files (e.g., if a node's name is
    # "node1" then ION Config Tool generates node1.bprc, node1.ionrc, etc.).
    node_name: Mapped[str | None] = mapped_column(Text, index=True)
    # Just a place to note anything, especially for weird exceptions
    comments: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    # modified_at keeps track of changes to node children, not just the node
    modified_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    # Think we need to configure this b/c two ways of joining
    host: Mapped[Host] = relationship(foreign_keys=[host_id])
    allocator: Mapped[Allocator] = relationship(
        back_populates='nodes', overlaps='nodes'
    )
    operator: Mapped[Operator] = relationship(
        back_populates='nodes', overlaps='allocator,nodes'
    )
    # The following all hold records that belong to a single node. Delete them
    # if the node is gone / they become de-associated from their node.
    ipn_endpoints: Mapped[list['EndpointIPN']] = relationship(
        back_populates='node',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='EndpointIPN.service_number',
    )
    imc_endpoints: Mapped[list['EndpointIMC']] = relationship(
        back_populates='node',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='EndpointIMC.group_number',
    )
    cl_protocols: Mapped[list['ClProtocol']] = relationship(
        back_populates='node',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='ClProtocol.cl_protocol_id',
    )
    inducts: Mapped[list['Induct']] = relationship(
        back_populates='node',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='Induct.induct_id',
        # Ideally, we'd want Induct.node_id and Induct.host_id to be based
        # on Node.host_id, but we don't want to use host_id when SELECTing
        # for Node.inducts.
        # But it doesn't seem like we can have the former without the latter.
        # Our current code also doesn't set Induct.host_id to the same value
        # as Node.host_id when we assign Induct.node (only sets node_id).
        primaryjoin='and_(Node.node_id == foreign(Induct.node_id),'
        ' Node.host_id.is_not_distinct_from(foreign(Induct.host_id)))',
    )
    seats: Mapped[list['Seat']] = relationship(
        back_populates='node',
        cascade='all, delete-orphan',
        passive_deletes=True,
        order_by='Seat.seat_id',
        primaryjoin='and_(Node.node_id == foreign(Seat.node_id),'
        ' Node.host_id.is_not_distinct_from(foreign(Seat.host_id)))',
    )
    # Contacts can exist without a node if still used by another entity.
    # Not really sure what 'all' does here, see comments for the Operator
    # class below.
    contacts: Mapped[list[Contact]] = relationship(
        secondary=node_contact,
        back_populates='nodes',
        passive_deletes='all',
        order_by=Contact.contact_id,
    )

    __table_args__ = (
        # A node is uniquely identified by its FQNN
        UniqueConstraint(
            'node_number', 'allocator_id', name='uq_fully_qualified_node_number'
        ),
        # If operator_id isn't null, this ensures node.allocator_id matches
        # operator.allocator_id
        ForeignKeyConstraint(
            ['allocator_id', 'operator_id'],
            ['operator.allocator_id', 'operator.operator_id'],
            # If operator.allocator_id updates, we should update allocator_id
            # here as well
            onupdate='CASCADE',
            # Deleting an operator should only set node.operator_id to null
            ondelete='SET NULL',
            postgresql_ondelete_set_null_columns=['operator_id'],
        ),
        Index('ix_node_allocator_id_operator_id', allocator_id, operator_id),
        # If operator_id and host_id aren't null, this ensures node.operator_id
        # matches host.operator_id.
        # Since operator_id is optional, this constraint shouldn't force a node
        # record with a host (where the host has an operator) to have a
        # node.operator_id field. And without the operator_id field, we can use
        # any allocator for a node record even though the node is on a host
        # with an operator that has a different allocator.
        ForeignKeyConstraint(
            ['operator_id', 'host_id'],
            ['host.operator_id', 'host.host_id'],
            # If host.operator_id updates, we should update operator_id here too.
            # If the FQNN doesn't work with the new operator, it should be caught
            # by the constraint trigger below.
            onupdate='CASCADE',
            # Nodes can exist without a host, so set node.host_id to null when
            # the host is deleted. node.operator_id doesn't have to match with
            # anything when node.host_id is null, so I think it's okay to only
            # set node.host_id to null.
            ondelete='SET NULL',
            postgresql_ondelete_set_null_columns=['host_id'],
        ),
        Index('ix_node_operator_id_host_id', operator_id, host_id),
        # Redundant unique constraint for FK constraint in duct tables
        UniqueConstraint('host_id', 'node_id'),
    )

    def __repr__(self) -> str:
        return (
            f'Node(node_id={self.node_id!r},'
            f' node_number={self.node_number!r},'
            f' allocator_id={self.allocator_id!r},'
            f' operator_id={self.operator_id!r},'
            f' host_id={self.host_id!r},'
            f' sdr_config_flags={self.sdr_config_flags!r},'
            f' wm_size={self.wm_size!r},'
            f' sdr_wm_size={self.sdr_wm_size!r},'
            f' heap_words={self.heap_words!r},'
            f' node_name={self.node_name!r},'
            f' comments={self.comments!r},'
            f' created_at={self.created_at!r},'
            f' modified_at={self.modified_at!r})'
        )


# TODO: I think this is vulnerable to race conditions

node_func = DDL(
    'CREATE OR REPLACE FUNCTION check_node_number_in_range()'
    ' RETURNS TRIGGER AS $$'
    ' BEGIN'
    " IF (TG_TABLE_NAME = 'node') THEN"
        ' IF NEW.operator_id IS NOT NULL AND'
        ' NOT(NEW.node_number <@ (SELECT allocated_node_numbers FROM operator'
        ' WHERE operator_id = NEW.operator_id))'
        ' THEN'
            " RAISE EXCEPTION 'invalid node number: %%', NEW.node_number"
                " USING DETAIL = format('The node is associated with an operator, so"
                    " its node number must be contained by the operator''s"
                    " allocated_node_numbers: %%s.',"
                    ' (SELECT allocated_node_numbers FROM operator'
                    ' WHERE operator_id = NEW.operator_id));'
        ' END IF;'
    " ELSIF (TG_TABLE_NAME = 'operator') THEN"
        ' IF (SELECT COUNT(*) FROM node WHERE operator_id = NEW.operator_id'
        ' AND node_number <@ NEW.allocated_node_numbers)'
        ' <> (SELECT COUNT(*) FROM node WHERE operator_id = NEW.operator_id)'
        ' THEN'
            " RAISE EXCEPTION 'invalid allocated node numbers: %%',"
                ' NEW.allocated_node_numbers'
                " USING DETAIL = 'The operator''s new allocated_node_numbers conflicts"
                    ' with at least one node under the operator whose node_number is'
                    " not contained by the new range.',"
                " HINT = 'Update conflicting nodes'' operator_id to NULL, then update"
                    " the operator, before setting the nodes'' operator_id back to"
                    " normal. Or delete the conflicting nodes if they should be"
                    " removed.';"
        ' END IF;'
    ' END IF;'
    ' RETURN NULL;'
    ' END; $$ LANGUAGE plpgsql;'
)  # fmt: skip


def node_number_trigger(table: str) -> str:
    # TODO: Could rewrite this to a FOR EACH STATEMENT trigger, but I didn't see
    # significant performance problems with this relative to the other (previously)
    # FOR EACH ROW triggers.
    return (
        f'CREATE CONSTRAINT TRIGGER TG_{table}_node_number_constraint AFTER INSERT OR'
        f' UPDATE ON {table}'
        ' FOR EACH ROW EXECUTE FUNCTION check_node_number_in_range();'
    )


event.listen(Node.__table__, 'after_create', node_func)
event.listen(Node.__table__, 'after_create', DDL(node_number_trigger('node')))
event.listen(Node.__table__, 'after_create', DDL(node_number_trigger('operator')))


contact_func = DDL(
    'CREATE OR REPLACE FUNCTION delete_orphan_contacts()'
    ' RETURNS TRIGGER AS $$'
    ' BEGIN'
    # If the DELETE operation didn't delete anything, then don't
    # clean up orphan contacts.
    ' IF EXISTS (SELECT FROM old_table) THEN'
        ' DELETE FROM contact WHERE NOT EXISTS'
        ' ((SELECT FROM allocator_contact WHERE'
        ' contact.contact_id = allocator_contact.contact_id)'
        ' UNION'
        ' (SELECT FROM operator_contact WHERE'
        ' contact.contact_id = operator_contact.contact_id)'
        ' UNION'
        ' (SELECT FROM host_contact WHERE'
        ' contact.contact_id = host_contact.contact_id)'
        ' UNION'
        ' (SELECT FROM node_contact WHERE'
        ' contact.contact_id = node_contact.contact_id));'
    ' END IF;'
    ' RETURN NULL;'
    ' END; $$ LANGUAGE plpgsql;'
)  # fmt: skip


def orphan_contacts_trigger(table: str) -> str:
    return (
        f'CREATE OR REPLACE TRIGGER TG_{table}_after_delete'
        f' AFTER DELETE ON {table}'
        ' REFERENCING OLD TABLE AS old_table'
        ' FOR EACH STATEMENT EXECUTE FUNCTION delete_orphan_contacts();'
    )


event.listen(Allocator.__table__, 'after_create', contact_func)
# Notice that Contact.__table__ isn't in this list. We only delete contact
# orphans when deleting from allocator, operator, host, node, or their association
# tables. We're allowed to insert contact records that aren't associated with
# anything, then update / delete these records from `contact`, and the other
# non-associated contacts are still there.
for t in [
    Allocator.__table__,
    Operator.__table__,
    Host.__table__,
    Node.__table__,
    allocator_contact,
    operator_contact,
    host_contact,
    node_contact,
]:
    event.listen(t, 'after_create', DDL(orphan_contacts_trigger(t.name)))


class DispositionEnum(str, enum.Enum):
    DISCARD = 'x'
    QUEUE = 'q'


class EndpointIPN(Base):
    """Represents an ION endpoint (like in bpadmin) using the "ipn"
    scheme. An endpoint is uniquely identified by its node (FQNN) and
    service number.
    """

    __tablename__ = 'endpoint_ipn'

    # Composite primary key (node_id, service_number)
    # Endpoints belong to a node, must be deleted when the node is deleted too
    node_id: Mapped[int] = mapped_column(
        ForeignKey('node.node_id', ondelete='CASCADE'), primary_key=True
    )
    # RFC 9758 does not invalidate Service Numbers >= 2^32, simply reserves them,
    # so we need `bigint` (Postgres' `integer` only goes up to 2^31 - 1).
    service_number: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    disposition: Mapped[str] = mapped_column(
        Enum(
            DispositionEnum,
            name='disposition_type',
            values_callable=lambda x: [e.value for e in x],
        ),
        server_default='x',
    )
    application: Mapped[str | None] = mapped_column(Text)

    node: Mapped[Node] = relationship(back_populates='ipn_endpoints')

    def __repr__(self) -> str:
        return (
            f'EndpointIPN(node_id={self.node_id!r},'
            f' service_number={self.service_number!r},'
            f' disposition={self.disposition!r},'
            f' application={self.application!r})'
        )


class EndpointIMC(Base):
    """Represents a multicast endpoint using the "imc" scheme.
    An endpoint is uniquely identified by its group number and service
    number.

    An `endpoint_imc` record states that a node belongs to a multicast
    group.
    """

    __tablename__ = 'endpoint_imc'

    # Composite primary key (node_id, group_number)
    # `endpoint_imc` records are children of a `node` record since they
    # should be removed when the parent is removed, but the concept of
    # the group exists independently from the node.
    node_id: Mapped[int] = mapped_column(
        ForeignKey('node.node_id', ondelete='CASCADE'), primary_key=True
    )
    # The imc scheme hasn't been standardized yet, but it's likely to
    # be similar to
    # https://datatracker.ietf.org/doc/html/draft-burleigh-dtnrg-imc-00#section-2.1
    # which requires that the group number be in [1, 2^64 - 1].
    # We'll use bigint (only up to 2^63 - 1) for now. It's still a draft so it's
    # not clear if 2^64 - 1 will be the final limit since IMC hasn't been
    # standardized. Trying to enforce constraints >= 2^63 is also really annoying
    # with msgspec.
    group_number: Mapped[int] = mapped_column(
        # Numeric(precision=20, scale=0, asdecimal=False),
        # CheckConstraint(
        #     'group_number >= 1 AND group_number <= 18446744073709551615',
        #     name='group_number_limit',
        # ),
        BigInteger,
        primary_key=True,
    )
    disposition: Mapped[str] = mapped_column(
        Enum(
            DispositionEnum,
            name='disposition_type',
            values_callable=lambda x: [e.value for e in x],
        ),
        server_default='x',
    )
    application: Mapped[str | None] = mapped_column(Text)

    node: Mapped[Node] = relationship(back_populates='imc_endpoints')

    def __repr__(self) -> str:
        return (
            f'EndpointIMC(node_id={self.node_id!r},'
            f' group_number={self.group_number!r},'
            f' disposition={self.disposition!r},'
            f' application={self.application!r})'
        )


known_cl_protocol_name_to_class = {
    'bibe': 10,
    'brsc': 8,
    'brss': 8,
    'bssp': 10,
    'dccp': 8,
    'dgr': 8,
    'epp': 2,
    'file': 2,
    'ltp': 10,
    'spp': 2,
    'stcp': 8,
    'tcp': 8,
    'udp': 2,
}


class ClProtocol(Base):
    """This table describes the CL protocols available on a node.

    A record in this relation maps onto bprc(5)'s protocol commands.

    `cl_protocol` records are referenced by `induct` records.
    """

    __tablename__ = 'cl_protocol'

    cl_protocol_id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    # A record here belongs to a node
    node_id: Mapped[int] = mapped_column(ForeignKey('node.node_id', ondelete='CASCADE'))
    # bprc protocol names are case sensitive, so 'LTP' <> 'ltp'
    cl_protocol_name: Mapped[str] = mapped_column(
        Text,
        # bpv7/library/bpP.h, name field of ClProtocol is limited to 15 char.
        # C only requires char to be at least 8 bits; POSIX requires char to be
        # exactly 8 bits.
        # Postgres length('josé') → 4 but octet_length('josé') → 5 (if server
        # encoding is UTF8). I suppose it's possible that ION is compiled on a
        # system where char is more than 8 bits, but this should be very rare,
        # and using length() here would allow invalid names for the majority
        # of users.
        CheckConstraint(
            # Do not trim when checking for length. bpadmin lets you add a protocol
            # consisting only of whitespace if you use '' or {}.
            'length(cl_protocol_name) > 0 AND octet_length(cl_protocol_name) <= 15',
            name='cl_protocol_name_len',
        ),
        index=True,
    )
    # bpv7/library/bpP.h, protocolClass field of ClProtocol is int. The logic for
    # adding protocols in bprc is in bpv7/library/libbpP.c's addProtocol(). The
    # only possible protocol classs values are effectively 2, 8 and 10 (this
    # contradicts bprc(5) as of ION 4.1.3s). During 4.1.4 development, a tentative
    # plan came up to make the default class 2 (BP_BEST_EFFORT).
    cl_protocol_class: Mapped[int] = mapped_column(
        Integer,
        CheckConstraint('cl_protocol_class in (2, 8, 10)', name='cl_protocol_class'),
        server_default=text('2'),
    )

    node: Mapped[Node] = relationship(back_populates='cl_protocols')
    # Ducts can exist without a CL protocol
    inducts: Mapped[list['Induct']] = relationship(
        back_populates='cl_protocol',
        passive_deletes='all',
        overlaps='inducts',
        order_by='Induct.induct_id',
        primaryjoin='ClProtocol.cl_protocol_id == Induct.cl_protocol_id',
    )

    __table_args__ = (
        # Redundant unique constraints for FK constraints in duct tables
        UniqueConstraint('node_id', 'cl_protocol_id', 'cl_protocol_name'),
        UniqueConstraint('cl_protocol_name', 'cl_protocol_id'),
        # Don't let a node use a CL protocol more than once
        UniqueConstraint(
            'cl_protocol_name',
            'node_id',
            name='uq_cl_protocol_cl_protocol_name_node_id',
        ),
        # bpv7/library/libbpP.c addProtocol() forces these protocols to always
        # have a particular protocol class. You can type a command like
        # `a protocol ltp 8`, and bpadmin will always use 10.
        # As of ION 4.1.3s, addProtocol() does  not prevent you from giving an
        # inaccurate class to a well known protocol (e.g., class 2 for TCP).
        # During 4.1.4 development, a tentative plan came up to enforce these
        # constraints for well known protocols and to also restrict 'tcp', 'stcp',
        # 'dgr', 'dccp', 'brss', and 'brsc' to class 8 (BP_RELIABLE).
        CheckConstraint(
            ' AND '.join(
                [
                    f"(cl_protocol_name <> '{n}' OR cl_protocol_class = {c})"
                    for n, c in known_cl_protocol_name_to_class.items()
                ]
            ),
            name='well_known_protocol_and_class',
        ),
    )

    def __repr__(self) -> str:
        return (
            f'ClProtocol(cl_protocol_id={self.cl_protocol_id!r},'
            f' node_id={self.node_id!r},'
            f' cl_protocol_name={self.cl_protocol_name!r},'
            f' cl_protocol_class={self.cl_protocol_class!r})'
        )


cli_command_with_required_protocol_name = (
    ('brsccla', 'brsc'),
    ('brsscla', 'brss'),
    ('bsspcli', 'bssp'),
    ('dccpcli', 'dccp'),
    ('dgrcli', 'dgr'),
    # ('eppcli', 'epp'),
    # ('filecli', 'file'),
    ('ltpcli', 'ltp'),
    # ('sppcli', 'spp'),
    ('stcpcli', 'stcp'),
    ('tcpcli', 'tcp'),
    ('udpcli', 'udp'),
)
no_uses_ltp_known_cli = (
    'brsccla',
    'brsscla',
    'bsspcli',
    'dccpcli',
    'dgrcli',
    # 'eppcli',
    # 'filecli',
    # 'sppcli',
    'stcpcli',
    'tcpcli',
    'udpcli',
)
no_duct_name_known_cli_not_ip = ('bsspcli', 'ltpcli')
# brsccla uses the remote IP address, so:
# * The user needs to be able to set duct_name
# * induct_ip is inappropriate since that uses local adddresses
no_induct_ip_known_cli = ('brsccla', 'bsspcli', 'ltpcli')


induct_seat = Table(
    'induct_seat',
    Base.metadata,
    Column('induct_id', primary_key=True),
    Column('seat_id', primary_key=True),
    Column('node_id', primary_key=True),
    Column(
        'uses_ltp',
        CheckConstraint('uses_ltp IS TRUE', name='yes_uses_ltp'),
        primary_key=True,
        server_default=text('TRUE'),
    ),
    ForeignKeyConstraint(
        ['induct_id', 'node_id', 'uses_ltp'],
        ['induct.induct_id', 'induct.node_id', 'induct.uses_ltp'],
        # Cannot change uses_ltp from true to false or induct.node_id when the
        # induct is still associated with seats. Assume induct.induct_id does
        # not change.
        onupdate='NO ACTION',
        ondelete='CASCADE',
        deferrable=True,
        initially='IMMEDIATE',
    ),
    Index(
        'ix_induct_seat_induct_id_node_id_uses_ltp', 'induct_id', 'node_id', 'uses_ltp'
    ),
    ForeignKeyConstraint(
        ['seat_id', 'node_id'],
        ['seat.seat_id', 'seat.node_id'],
        # Cannot change seat.node_id when seat is still associated with inducts.
        # Assume seat.seat_id does not change.
        onupdate='NO ACTION',
        ondelete='CASCADE',
        deferrable=True,
        initially='IMMEDIATE',
    ),
    Index('ix_induct_seat_seat_id_node_id', 'seat_id', 'node_id'),
)


class Induct(Base):
    """Records from this table have general information about the
    inducts on a node.

    This is a parent table for table-per-type inheritance where the
    typed versions are designed for specific `duct_name` fields. N.b.
    `duct_name` will be passed as the last argument to `cli_command`
    when inducts are started with the `s` command from bprc(5).
    `duct_name` must be null when an induct type is used. If the typed
    table does not have enough information for a `duct_name`, then do
    not use a typed table.

    A CLI is considered "known" if it's a CLI that comes with ION. For
    most of these CLIs, we can derive the duct name either from the
    typed table or from the node's details, so storing a `duct_name` is
    a burden. In these cases, `duct_name` should be kept null. Note that
    `induct_ip` can only reference a destination if a node is on a host,
    so `duct_name` is not required to be null to let hostless nodes have
    meaningful inducts using an ip[:port] based CLI.

    There is a M:N association with `link` records to show what the CL
    protocol used by an induct is actually running over.

    `uses_ltp` is true if the induct can be associated with a seat. For
    the known CLIs, this is true iff `cli_command` is 'ltpcli'. An LTP
    induct cannot directly associate with links. It can only indirectly
    associate with links through seats.
    """

    __tablename__ = 'induct'

    induct_id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    type: Mapped[str | None] = mapped_column(Text)
    # Induct must belong to a node
    node_id: Mapped[int] = mapped_column(
        ForeignKey('node.node_id', ondelete='CASCADE'), index=True
    )
    # Proxy to ensure induct_link associates an induct with a link on the
    # node's host.
    host_id: Mapped[int | None] = mapped_column(BigInteger)
    # Induct doesn't need a CL protocol to exist
    cl_protocol_id: Mapped[int | None] = mapped_column(BigInteger)
    cl_protocol_name: Mapped[str | None] = mapped_column(Text)
    # Keep duct_name null if cli_command is a CLI that comes with ION. For these
    # CLIs, the database has enough information to derive the duct_name, and we
    # avoid having to keep duct_name in sync with other columns.
    duct_name: Mapped[str | None] = mapped_column(Text)
    # cli_command needs to be explicitly set so that we can tell whether one of
    # ION's CLIs is being used.
    cli_command: Mapped[str | None] = mapped_column(Text)
    # We do not know for a custom CLI / protocol whether the induct uses ltp(3).
    # Using ltp(3) means that CLI interacts with the LTP engine which is what
    # we'll consider as an induct that can be associated with an LTP seat.
    # Keep this false by default since the only CLI that comes with ION where
    # this should be true is ltpcli.
    uses_ltp: Mapped[bool] = mapped_column(Boolean, server_default=text('FALSE'))

    # These are one-to-one relationships, delete them if they dissociate.
    # Use passive_deletes=True since the database handles deletions with
    # ON DELETE CASCADE.
    induct_ip: Mapped['InductIp'] = relationship(
        back_populates='induct',
        cascade='all, delete-orphan',
        passive_deletes=True,
        # Include host_id so associating InductIp with an induct sets both
        # induct_id and host_id.
        primaryjoin='and_(Induct.induct_id == foreign(InductIp.induct_id),'
        ' Induct.host_id.is_not_distinct_from(foreign(InductIp.host_id)))',
    )
    # Include host_id in foreign_keys so assigning Induct.node will assign
    # both node_id and host_id.
    node: Mapped[Node] = relationship(
        back_populates='inducts',
        overlaps='inducts',
        foreign_keys=[node_id, host_id],
        # Induct.host_id should be written based on only Induct.node.
        # Default behavior of relationship() equates value on both sides,
        # but we need to use IS NOT DISTINCT FROM because host_id can be
        # null.
        primaryjoin='and_(Node.node_id == foreign(Induct.node_id),'
        ' Node.host_id.is_not_distinct_from(foreign(Induct.host_id)))',
    )
    cl_protocol: Mapped[ClProtocol] = relationship(
        back_populates='inducts',
        overlaps='inducts,node',
        foreign_keys=[cl_protocol_id, cl_protocol_name],
    )
    # See relationship comment in Link for why we use passive_deletes=True
    links: Mapped[list[Link]] = relationship(
        secondary=induct_link,
        back_populates='inducts',
        passive_deletes=True,
        foreign_keys=[induct_id, host_id, uses_ltp],
        primaryjoin=(
            'and_(Induct.induct_id == foreign(induct_link.c.induct_id),'
            ' Induct.host_id == foreign(induct_link.c.host_id),'
            ' Induct.uses_ltp == foreign(induct_link.c.uses_ltp))'
        ),
        secondaryjoin=(
            'and_(Link.link_id == foreign(induct_link.c.link_id),'
            ' Link.host_id == foreign(induct_link.c.host_id),'
            ' Link.direction == foreign(induct_link.c.direction))'
        ),
        order_by=Link.link_id,
    )
    seats: Mapped[list['Seat']] = relationship(
        secondary=induct_seat,
        back_populates='inducts',
        passive_deletes=True,
        foreign_keys=[induct_id, node_id, uses_ltp],
        primaryjoin=(
            'and_(Induct.induct_id == foreign(induct_seat.c.induct_id),'
            ' Induct.node_id == foreign(induct_seat.c.node_id),'
            ' Induct.uses_ltp == foreign(induct_seat.c.uses_ltp))'
        ),
        secondaryjoin=(
            'and_(Seat.seat_id == foreign(induct_seat.c.seat_id),'
            ' Seat.node_id == foreign(induct_seat.c.node_id))'
        ),
        order_by='Seat.seat_id',
    )

    # A unique constraint on protocol_name and duct_name is really tricky.
    # While bpadmin does not create multiple inducts in response to
    # `a induct udp 0.0.0.0:4556 udpcli` being used multiple times, you can
    # get effectively create three inducts using udpcli with the same
    # ip[:port] like:
    # ```
    # a induct udp 0.0.0.0:4556 udpcli
    # a induct udp '0.0.0.0:4556 ' udpcli
    # a induct udp '0.0.0.0:4556  ' udpcli
    # ````
    # Even if ION did prevent stuff like this, it doesn't stop custom CLIs from
    # using UDP but with a different protocol_name in bpadmin. Ideally, you don't
    # want multiple applications using the same ip[:port], but I don't know how
    # to handle this with custom CL protocols. Someone could also have a duct_name
    # that repeats what an induct_ip says, and there can be a seat_ip which uses
    # the same IP address and port.

    __table_args__ = (
        ForeignKeyConstraint(
            ['host_id', 'node_id'],
            ['node.host_id', 'node.node_id'],
            # When node's host updates, we should update induct.host_id too
            onupdate='CASCADE',
            # Induct must belong to a node, delete if node is deleted
            ondelete='CASCADE',
        ),
        Index('ix_induct_host_id_node_id', host_id, node_id),
        ForeignKeyConstraint(
            ['node_id', 'cl_protocol_id', 'cl_protocol_name'],
            [
                'cl_protocol.node_id',
                'cl_protocol.cl_protocol_id',
                'cl_protocol.cl_protocol_name',
            ],
            # A cl_protocol cannot have a new node_id if it's still used by an
            # induct. (We assume ON UPDATE only refers to cl_protocol_name
            # changing and not cl_protocol.node_id or cl_protocol.cl_protocol_id.)
            onupdate='CASCADE',
            # Deleting a cl_protocol should only set induct.cl_protocol_id and
            # induct.cl_protocol_name to NULL and not touch induct.node_id.
            ondelete='SET NULL',
            postgresql_ondelete_set_null_columns=['cl_protocol_id', 'cl_protocol_name'],
            deferrable=True,
            initially='IMMEDIATE',
        ),
        Index(
            'ix_induct_node_id_cl_protocol_id_cl_protocol_name',
            node_id,
            cl_protocol_id,
            cl_protocol_name,
        ),
        # Separate constraint to prevent setting induct.cl_protocol_name to a
        # non-null value without referencing a cl_protocol record.
        ForeignKeyConstraint(
            ['cl_protocol_name', 'cl_protocol_id'],
            ['cl_protocol.cl_protocol_name', 'cl_protocol.cl_protocol_id'],
            # Match the other FK's behavior for ON UPDATE and ON DELETE
            onupdate='CASCADE',
            ondelete='SET NULL',
            postgresql_ondelete_set_null_columns=['cl_protocol_id', 'cl_protocol_name'],
            # Both of these are either null or not null
            match='FULL',
            deferrable=True,
            initially='IMMEDIATE',
        ),
        Index(
            'ix_induct_cl_protocol_name_cl_protocol_id',
            cl_protocol_name,
            cl_protocol_id,
        ),
        # The CLIs that come with ION are hardcoded to look for an induct with
        # an exact protocol name. The only protocol we can't handle here is
        # BIBE. BIBE does not have a CLI, but ION code for BIBE does look for
        # an induct with duct name '*' under protocol 'bibe'. But you can still
        # imagine a custom CLI which uses the same duct name and protocol, so
        # we can't really restrict anything for BIBE.
        CheckConstraint(
            ' AND '.join(
                [
                    f"(cli_command <> '{cli}' OR "
                    f" cl_protocol_name IS NOT DISTINCT FROM '{name}')"
                    for cli, name in cli_command_with_required_protocol_name
                ]
            ),
            name='cli_command_with_required_protocol_name',
        ),
        # The "uses_ltp" column is what enables a seat to associate with an induct.
        # "bssp" technically also has seats, but ION's implementation of BSSP as
        # of 4.1.3s needs to be reworked, so don't bother supporting BSSP for now.
        CheckConstraint(
            "cli_command <> 'ltpcli' OR uses_ltp IS TRUE", name='uses_ltp_when_ltpcli'
        ),
        # We know that it's a mistake to associate an induct, using another CLI that
        # comes with ION that isn't ltpcli, with LTP seats. But we cannot stop
        # something apparently wrong like a 'tcp' induct with a custom CLI from
        # setting uses_ltp to true, because we don't know enough about the custom
        # CLI to tell whether it uses ltp(3).
        CheckConstraint(
            f'cli_command NOT IN {no_uses_ltp_known_cli} OR uses_ltp IS FALSE',
            name='no_uses_ltp_known_cli',
        ),
        # Prevent setting duct_name when a known CLI which doesn't use IP addreses
        # is used. We need to allow duct_name for CLIs that use "ip[:port]" since
        # the node can exist without a host which makes it impossible to have a
        # meaningful induct_ip. Requiring induct_ip in that case will lead users
        # to try to work around our constraint, e.g., by setting cli_command to
        # "tcpcli " which will let them set duct_name. It's better to present
        # induct_ip as a specialized form of duct_name which is only available
        # when the node is on a host.
        CheckConstraint(
            f'cli_command NOT IN {no_duct_name_known_cli_not_ip} OR duct_name IS NULL',
            name='no_duct_name_known_cli_not_ip',
        ),
        # Prevent induct_ip when the CLI is known to *not* use a duct name with
        # an IP address and port number.
        CheckConstraint(
            f"cli_command NOT IN {no_induct_ip_known_cli} OR type <> 'ip'",
            name='no_induct_ip_known_cli',
        ),
        # Prevent setting duct_name when type is set
        CheckConstraint(
            'type IS NULL OR duct_name IS NULL',
            name='no_duct_name_when_type_is_not_null',
        ),
        # Redundant unique constraint for FK constraint in `induct_link`
        UniqueConstraint('uses_ltp', 'induct_id', 'host_id'),
        # Redundant unique constraint for induct type tables
        UniqueConstraint('type', 'induct_id'),
        # Redundant unique constraint for FK in `seat`
        UniqueConstraint('induct_id', 'uses_ltp', 'node_id'),
        UniqueConstraint('host_id', 'induct_id'),
    )

    def __repr__(self) -> str:
        return (
            f'Induct(induct_id={self.induct_id!r},'
            f' type={self.type!r},'
            f' node_id={self.node_id!r},'
            f' host_id={self.host_id!r},'
            f' cl_protocol_id={self.cl_protocol_id!r},'
            f' cl_protocol_name={self.cl_protocol_name!r},'
            f' duct_name={self.duct_name!r},'
            f' cli_command={self.cli_command!r},'
            f' uses_ltp={self.uses_ltp!r})'
        )


class InductIp(Base):
    """Records from this table represent inducts whose duct name can be
    constructed from a local destination and a port number.

    If `destination_id` is not null, then the referenced destination
    is the hostname part of a duct_name of inducts in bprc(5).

    Since `destination.registered_name` is resolved locally at the host
    identified by `destination.host_id`, there is no guarantee that
    nodes on different hosts which would like to talk to this induct can
    use a destination value in their outduct names.
    """

    __tablename__ = 'induct_ip'

    # One-to-one relationship with an existing Induct record
    induct_id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(
        CheckConstraint("type = 'ip'", name='ip_type'), server_default='ip'
    )
    # Ensures destination is from the node's host
    host_id: Mapped[int | None] = mapped_column(BigInteger)
    destination_id: Mapped[int | None] = mapped_column(BigInteger)
    port_number: Mapped[int | None] = mapped_column(
        Integer,
        CheckConstraint(
            'port_number >= 0 AND port_number <= 65535', name='port_number'
        ),
    )
    # Unique constraint on (destination_id, port_number) is tricky. See comment
    # in Induct about why a unique constraint on protocol_name and duct_name is
    # hard. Constraints on destination are also tricky because destinations can
    # resolve to the same value (e.g., "127.0.0.1:4556" and "localhost:4556").

    induct: Mapped[Induct] = relationship(
        back_populates='induct_ip',
        primaryjoin=(
            'and_(foreign(InductIp.type) == Induct.type,'
            ' foreign(InductIp.induct_id) == Induct.induct_id)'
        ),
        single_parent=True,
    )
    destination: Mapped[Destination] = relationship(
        back_populates='inducts', foreign_keys=[destination_id]
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ['type', 'induct_id'],
            ['induct.type', 'induct.induct_id'],
            # induct_ip.type should never be updated. If parent induct.type is
            # updating, then the induct_ip record should be deleted.
            onupdate='RESTRICT',
            ondelete='CASCADE',
            deferrable=True,
            initially='IMMEDIATE',
        ),
        Index('ix_induct_ip_type_induct_id', type, induct_id),
        # Separate FK constraint to handle host_id since it's nullable
        ForeignKeyConstraint(
            ['host_id', 'induct_id'],
            ['induct.host_id', 'induct.induct_id'],
            # Follow the parent induct's behavior when host_id changes
            onupdate='CASCADE',
            ondelete='CASCADE',
            deferrable=True,
            initially='IMMEDIATE',
        ),
        Index('ix_induct_ip_host_id_induct_id', host_id, induct_id),
        ForeignKeyConstraint(
            ['host_id', 'destination_id'],
            ['destination.host_id', 'destination.destination_id'],
            # A destination cannot have a new host_id if it's still used
            # by an induct. (We assume ON UPDATE only refers to desination.host_id
            # changing and not destination.destination_id.)
            onupdate='NO ACTION',
            # When the destination is deleted, the induct should still exist.
            # Deleting a destination should only set induct.destination_id to
            # NULL and not touch induct.host_id.
            ondelete='SET NULL',
            postgresql_ondelete_set_null_columns=['destination_id'],
            deferrable=True,
            initially='IMMEDIATE',
        ),
        Index('ix_induct_ip_host_id_destination_id', host_id, destination_id),
        CheckConstraint(
            'host_id IS NOT NULL OR destination_id IS NULL',
            name='null_destination_when_null_host',
        ),
    )

    def __repr__(self) -> str:
        return (
            f'InductIp(induct_id={self.induct_id!r},'
            f' type={self.type!r},'
            f' host_id={self.host_id!r},'
            f' destination_id={self.destination_id!r},'
            f' port_number={self.port_number!r})'
        )


link_service_protocol_seat = Table(
    'link_service_protocol_seat',
    Base.metadata,
    Column(
        'link_service_protocol_id',
        # Don't delete link_service_protocol records if they're still used by a link
        ForeignKey(
            'link_service_protocol.link_service_protocol_id', ondelete='NO ACTION'
        ),
        primary_key=True,
    ),
    Column(
        'seat_id',
        ForeignKey('seat.seat_id', ondelete='CASCADE'),
        primary_key=True,
        index=True,
    ),
)


# TODO: probably going to delete link_service_protocol and the association
# table. First, the name is bad, "link_protocol" is more apt. Second, I think
# it's conceptually flawed. When we describe what LTP is over, we're describing
# the underlying communication services of the link. But that's a property of
# a link and we already have relations to describe that. This table repeats that
# information. (Consider LTP blocks in Encapsulation Packets.) But without a
# host, you can't store protocol related information for the seat. For ltprc, this
# is irrelevant since it just cares about lsi_command. But this seems lacking
# for the UI. But can you really choose a LSI program if you don't know what the
# link is?
class LinkServiceProtocol(Base):
    """Lookup table for link service protocols (LSI command protocols).
    `seat` records can have a M:N relationship with
    `link_service_protocol` to describe the protocols that the seat's
    LSI program uses.
    """

    __tablename__ = 'link_service_protocol'

    link_service_protocol_id: Mapped[int] = mapped_column(
        Integer, Identity(always=True), primary_key=True
    )
    link_service_protocol_name: Mapped[str] = mapped_column(Text, index=True)

    seats: Mapped[list['Seat']] = relationship(
        secondary='link_service_protocol_seat',
        back_populates='link_service_protocols',
        passive_deletes=True,
        order_by='Seat.seat_id',
    )

    def __repr__(self) -> str:
        return (
            f'LinkServiceProtocol('
            f'link_service_protocol_id={self.link_service_protocol_id!r},'
            f' link_service_protocol_name={self.link_service_protocol_name!r})'
        )


default_link_service_protocols = [
    {'link_service_protocol_name': 'UDP'},
    {'link_service_protocol_name': 'DCCP'},
]


# @event.listens_for(LinkServiceProtocol.__table__, 'after_create')
# def insert_after_create_link_service_protocol(target, connection, **kw):
#     logger.info('Inserting lookup values to `link_service_protocol`')
#     connection.execute(
#         insert(LinkServiceProtocol),
#         default_link_service_protocols,
#     )


# `seat` could be generalized further to support bssp seats, but since bssp
# needs to be reworked, we can ignore its interface for now.
class Seat(Base):
    """Records from this table are used to construct `a seat` commands
    for ltpadmin(1).

    A record can produce a LSI_command which is a program that extracts
    LTP segments from a lower layer PDU and passes the segments to ION's
    LTP engine. A CLI that uses the ltp(3) API can then extract bundles
    from those segments. This creates a M:N relationship between seats
    and LTP inducts.

    This is a parent table for table-per-type inheritance where the
    typed versions store the argument(s) for LSI programs with a known
    format. If a LSI program uses arguments that cannot be completely
    represented by a typed record, then the entire command to invoke
    the program should be stored in `lsi_command`. If a seat record
    is typed, then the LSI command reported to the application is
    `lsi_command` + (arguments derived from typed record).

    There is a M:N relationship with `link` records to show what the
    link service protocol is really running over.
    """

    __tablename__ = 'seat'

    seat_id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    # type is only used by database for table-per-type inheritance
    type: Mapped[str | None] = mapped_column(Text)
    # Seats belong to a node
    node_id: Mapped[int] = mapped_column(
        ForeignKey('node.node_id', ondelete='CASCADE'), index=True
    )
    # Proxy to ensure induct_link associates a seat with a link on the
    # node's host.
    host_id: Mapped[int | None] = mapped_column(BigInteger)
    lsi_command: Mapped[str | None] = mapped_column(Text)

    # One-to-one relationship with typed tables, delete them if they dissociate.
    # Use passive_deletes=True since the database handles deletions with
    # ON DELETE CASCADE.
    seat_ip: Mapped['SeatIp'] = relationship(
        back_populates='seat',
        cascade='all, delete-orphan',
        passive_deletes=True,
        primaryjoin='Seat.seat_id == SeatIp.seat_id',
    )
    node: Mapped[Node] = relationship(
        back_populates='seats',
        overlaps='seats',
        foreign_keys=[node_id, host_id],
        primaryjoin='and_(Node.node_id == foreign(Seat.node_id),'
        ' Node.host_id.is_not_distinct_from(foreign(Seat.host_id)))',
    )
    link_service_protocols: Mapped[list[LinkServiceProtocol]] = relationship(
        secondary=link_service_protocol_seat,
        back_populates='seats',
        passive_deletes=True,
        order_by=LinkServiceProtocol.link_service_protocol_name,
    )
    # See relationship comment in Link for why we use passive_deletes=True
    links: Mapped[list[Link]] = relationship(
        secondary=seat_link,
        back_populates='seats',
        passive_deletes=True,
        foreign_keys=[seat_id, host_id],
        primaryjoin=(
            'and_(Seat.seat_id == foreign(seat_link.c.seat_id),'
            ' Seat.host_id == foreign(seat_link.c.host_id))'
        ),
        secondaryjoin=(
            'and_(Link.link_id == foreign(seat_link.c.link_id),'
            ' Link.host_id == foreign(seat_link.c.host_id),'
            ' Link.direction == foreign(seat_link.c.direction))'
        ),
        order_by=Link.link_id,
    )
    inducts: Mapped[list[Induct]] = relationship(
        secondary=induct_seat,
        back_populates='seats',
        passive_deletes=True,
        foreign_keys=[seat_id, node_id],
        primaryjoin=(
            'and_(Seat.seat_id == foreign(induct_seat.c.seat_id),'
            ' Seat.node_id == foreign(induct_seat.c.node_id))'
        ),
        secondaryjoin=(
            'and_(Induct.induct_id == foreign(induct_seat.c.induct_id),'
            ' Induct.node_id == foreign(induct_seat.c.node_id),'
            ' Induct.uses_ltp == foreign(induct_seat.c.uses_ltp))'
        ),
        order_by=Induct.induct_id,
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ['host_id', 'node_id'],
            ['node.host_id', 'node.node_id'],
            # When node's host updates, we should update seat.host_id too
            onupdate='CASCADE',
            # Seat must belong to a node, delete if node is deleted
            ondelete='CASCADE',
        ),
        Index('ix_seat_host_id_node_id', host_id, node_id),
        # Redundant unique constraint for induct_seat
        UniqueConstraint('seat_id', 'node_id'),
        # Redundant unique constraint for seat_link
        UniqueConstraint('host_id', 'seat_id'),
        # Redundant unique constraints for FK seat types
        UniqueConstraint('type', 'seat_id'),
    )

    def __repr__(self) -> str:
        return (
            f'Seat(seat_id={self.seat_id!r},'
            f' type={self.type!r},'
            f' node_id={self.node_id!r},'
            f' host_id={self.host_id!r},'
            f' lsi_command={self.lsi_command!r})'
        )


class SeatIp(Base):
    """Records from this table represent seats whose LSI command
    consists of concatenating seat.lsi_commmand with an ip[:port]
    argument constructed from a local destination and port number.

    Since `destination.registered_name` is resolved locally at the host
    identified by `destination.host_id`, there is no guarantee that
    nodes on different hosts which would like to talk to this seat can
    use a destination value in their LSO command.

    `seat_ip` can only reference a destination if the node is on a host.
    If you want to store a LSI comamnd on a hostless nodes, do not use
    this record. Just store the entire command in seat.lsi_command.
    """

    __tablename__ = 'seat_ip'

    seat_id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(
        CheckConstraint("type = 'ip'", name='ip_type'), server_default='ip'
    )
    # Ensures destination is from the node's host
    host_id: Mapped[int | None] = mapped_column(BigInteger)
    destination_id: Mapped[int | None] = mapped_column(BigInteger)
    port_number: Mapped[int | None] = mapped_column(
        Integer,
        CheckConstraint(
            'port_number >= 0 AND port_number <= 65535', name='port_number'
        ),
    )

    seat: Mapped[Seat] = relationship(
        back_populates='seat_ip',
        primaryjoin=(
            'and_(foreign(SeatIp.type) == Seat.type,'
            ' foreign(SeatIp.seat_id) == Seat.seat_id)'
        ),
        single_parent=True,
    )
    destination: Mapped[Destination] = relationship(
        back_populates='seats', foreign_keys=[destination_id]
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ['type', 'seat_id'],
            ['seat.type', 'seat.seat_id'],
            # seat_ip.type should never be updated. If parent seat.type is
            # updating, then the seat_ip record should be deleted.
            # Assume that seat.node_id is never updated.
            onupdate='RESTRICT',
            ondelete='CASCADE',
            deferrable=True,
            initially='IMMEDIATE',
        ),
        Index('ix_seat_ip_type_seat_id', type, seat_id),
        ForeignKeyConstraint(
            ['host_id', 'seat_id'],
            ['seat.host_id', 'seat.seat_id'],
            onupdate='CASCADE',
            ondelete='CASCADE',
            deferrable=True,
            initially='IMMEDIATE',
        ),
        Index('ix_seat_ip_host_id_seat_id', host_id, seat_id),
        ForeignKeyConstraint(
            ['host_id', 'destination_id'],
            ['destination.host_id', 'destination.destination_id'],
            # A destination cannot have a new host_id if it's still used
            # by an seat. (We assume ON UPDATE only refers to desination.host_id
            # changing and not destination.destination_id.)
            onupdate='NO ACTION',
            # When the destination is deleted, the seat should still exist.
            # Deleting a destination should only set seat.destination_id to
            # NULL and not touch seat.host_id.
            ondelete='SET NULL',
            postgresql_ondelete_set_null_columns=['destination_id'],
            deferrable=True,
            initially='IMMEDIATE',
        ),
        Index('ix_seat_ip_host_id_destination_id', host_id, destination_id),
        CheckConstraint(
            'host_id IS NOT NULL OR destination_id IS NULL',
            name='null_destination_when_null_host',
        ),
    )

    def __repr__(self) -> str:
        return (
            f'SeatIp(seat_id={self.seat_id!r},'
            f' type={self.type!r},'
            f' host_id={self.host_id!r},'
            f' destination_id={self.destination_id!r},'
            f' port_number={self.port_number!r})'
        )


# TODO: I think these functions are all vulnerable to race conditions

# fmt: off

# Suppose node.host_id is null and we have inducts related to the node. If
# we updated node.host_id to a not-null value, ON UPDATE CASCADE will
# not update the induct.host_id as well because of how null works.
# There wouldn't be a problem if induct.host_id is NOT NULL, but since
# nodes need to be able to exist independently from hosts, induct.host_id
# must be nullable.
# The same logic applies to seat.
# This trigger compensates for ON UPDATE CASCADE not updating the
# children if their host_id is null.
event.listen(Base.metadata, 'after_create', DDL(
    'CREATE OR REPLACE FUNCTION node_update_host_id_cascade()'
    ' RETURNS TRIGGER AS'
    ' $func$'
    ' BEGIN'
    ' IF EXISTS (SELECT FROM old_table o JOIN new_table n'
        ' ON o.node_id = n.node_id'
        ' WHERE o.host_id IS NULL'
        ' AND o.host_id IS DISTINCT FROM n.host_id)'
    ' THEN'
        ' UPDATE induct SET host_id = n.host_id'
        ' FROM old_table o JOIN new_table n ON o.node_id = n.node_id'
        ' WHERE induct.node_id = n.node_id'
        ' AND o.host_id IS NULL AND o.host_id IS DISTINCT FROM n.host_id;'
        ' UPDATE seat SET host_id = n.host_id'
        ' FROM old_table o JOIN new_table n ON o.node_id = n.node_id'
        ' WHERE seat.node_id = n.node_id'
        ' AND o.host_id IS NULL AND o.host_id IS DISTINCT FROM n.host_id;'
    ' END IF;'
    ' RETURN NULL;'
    ' END;'
    ' $func$ LANGUAGE plpgsql;'

    'CREATE OR REPLACE TRIGGER TG_node_after_update_host_id'
    ' AFTER UPDATE ON node'
    ' REFERENCING OLD TABLE AS old_table NEW TABLE AS new_table'
    ' FOR EACH STATEMENT EXECUTE FUNCTION node_update_host_id_cascade();'

    # TODO: need to check if this information is still true.
    #
    # If you remove the CHECK constraint on induct and are relying
    # on the commented out code in the check_host_id_not_distinct_func() to
    # prevent ducts from having host references when their host_id is null,
    # then change these IF statements from using EXISTS to (SELECT count(*) > 0).
    # In other places where we use EXISTS, the function is either faster then
    # or has the same performance as count(*) > 0. When they both end up having
    # bad performance, a VACUUM is enough to fix them.
    # The test case is inserting 20k induct_ips, then creating a destination,
    # then updating the induct_ips to have that destination. The performance
    # issues only happen when the operation would fail by raising an exception
    # in check_host_id_not_distinct_func() since the inducts can't have an
    # destination without a host. If you remember to update the node to have the
    # right host before setting destination_id for the induct_ips, the function
    # performs the same for EXISTS and count(*) > 0.
    # Moreover, the operation hangs on the EXISTS; usually these functions
    # which use EXISTS hang on UPDATE when they're slow. And unlike the other
    # functions, using VACUUM doesn't seem to do anything.

    'CREATE OR REPLACE FUNCTION induct_update_host_id_cascade()'
    ' RETURNS TRIGGER AS'
    ' $func$'
    ' BEGIN'
    ' IF EXISTS (SELECT FROM old_table o JOIN new_table n'
        ' ON o.induct_id = n.induct_id'
        ' WHERE o.host_id IS NULL'
        ' AND o.host_id IS DISTINCT FROM n.host_id)'
    ' THEN'
        ' UPDATE induct_ip SET host_id = n.host_id'
        ' FROM old_table o JOIN new_table n ON o.induct_id = n.induct_id'
        ' WHERE induct_ip.induct_id = n.induct_id'
        ' AND o.host_id IS NULL AND o.host_id IS DISTINCT FROM n.host_id;'
    ' END IF;'
    ' RETURN NULL;'
    ' END;'
    ' $func$ LANGUAGE plpgsql;'

    'CREATE OR REPLACE TRIGGER TG_induct_after_update_host_id'
    ' AFTER UPDATE ON induct'
    ' REFERENCING OLD TABLE AS old_table NEW TABLE AS new_table'
    ' FOR EACH STATEMENT EXECUTE FUNCTION induct_update_host_id_cascade();'

    'CREATE OR REPLACE FUNCTION seat_update_host_id_cascade()'
    ' RETURNS TRIGGER AS'
    ' $func$'
    ' BEGIN'
    ' IF EXISTS (SELECT FROM old_table o JOIN new_table n'
        ' ON o.seat_id = n.seat_id'
        ' WHERE o.host_id IS NULL'
        ' AND o.host_id IS DISTINCT FROM n.host_id)'
    ' THEN'
        ' UPDATE seat_ip SET host_id = n.host_id'
        ' FROM old_table o JOIN new_table n ON o.seat_id = n.seat_id'
        ' WHERE seat_ip.seat_id = n.seat_id'
        ' AND o.host_id IS NULL AND o.host_id IS DISTINCT FROM n.host_id;'
    ' END IF;'
    ' RETURN NULL;'
    ' END;'
    ' $func$ LANGUAGE plpgsql;'

    'CREATE OR REPLACE TRIGGER TG_seat_after_update_host_id'
    ' AFTER UPDATE ON seat'
    ' REFERENCING OLD TABLE AS old_table NEW TABLE AS new_table'
    ' FOR EACH STATEMENT EXECUTE FUNCTION seat_update_host_id_cascade();'
))


# Following a `delete from host`, the FKs and triggers whose order of execution
# can lead to errors are fired after the triggers on `host` are fired.
# Instead of relying on the order of execution to update host references in the
# correct order, we just update here with a trigger defined on `host`.
event.listen(Base.metadata, 'after_create', DDL(
    'CREATE OR REPLACE FUNCTION host_delete_nullify_host_references()'
    ' RETURNS TRIGGER AS'
    ' $func$'
    ' BEGIN'
    ' IF EXISTS (SELECT FROM node WHERE node.host_id = OLD.host_id) THEN'
        ' UPDATE induct_ip SET destination_id = NULL'
        ' WHERE induct_ip.host_id = OLD.host_id;'
        ' UPDATE seat_ip SET destination_id = NULL'
        ' WHERE seat_ip.host_id = OLD.host_id;'
    ' END IF;'
    ' RETURN OLD;'
    ' END;'
    ' $func$ LANGUAGE plpgsql;'

    'CREATE OR REPLACE TRIGGER TG_host_before_delete_nullify_host_references'
    ' BEFORE DELETE ON host'
    ' FOR EACH ROW EXECUTE FUNCTION host_delete_nullify_host_references();'

    # # This has better performance when performing bulk deletions, but it also
    # # requires the trigger that checks that a node child host_id matches with
    # # its parent host_id to raise WARNING instead of EXCEPTION.
    # 'CREATE OR REPLACE FUNCTION host_delete_force_triggers()'
    # ' RETURNS TRIGGER AS'
    # ' $func$'
    # ' BEGIN'
    # # We need to update host_id to null, since the node FK to host already
    # # set node.host_id to null, so we'd violate the FK to node since duct's
    # # host_id is not null.
    # ' UPDATE induct_ip SET host_id = NULL, destination_id = NULL'
    #     ' FROM old_table o WHERE induct.host_id = o.host_id;'
    # ' UPDATE seat_ip SET host_id = NULL, destination_id = NULL'
    #     ' FROM old_table o WHERE seat_ip.host_id = o.host_id;'
    # ' RETURN NULL;'
    # ' END;'
    # ' $func$ LANGUAGE plpgsql;'

    # 'CREATE OR REPLACE TRIGGER tg_host_after_delete_force_triggers'
    # ' AFTER DELETE ON host'
    # ' REFERENCING OLD TABLE AS old_table'
    # ' FOR EACH STATEMENT EXECUTE FUNCTION host_delete_force_triggers();'
))


# This trigger prevents induct and seat_ip records from having a reference to
# a host child when their own host_id is null, and prevents ducts from having
# a host_id that doesn't match their node.
# (The first part can be handled by check constraints, so code to handle that
# part has been commented out, but the second part prevents node.host_id from
# being not null while induct.host_id is null.)
# Note: We used to have problems with new_table having outdated state since
# we were relying on FK referential actions to update columns which meant
# that by the time this trigger ran, new_table would be behind the table's
# current state. In that case, instead of selecting new_table.host_id,
# perform a join with the table and select the current host_id.
# After adding the `BEFORE DELETE ON host` trigger which updates everything to
# what it should be, we haven't encountered this problem again (test this by
# declaring a test_new_host_id variable, select the current host_id into it,
# and raise an exception if new_host_id IS DISTINCT FROM test_new_host_id).
def check_host_id_not_distinct_func(
    table_name: str,
    pk_column: str,
    parent_table_name: str,
    parent_pk_column: str,
    part_table_name: str = None,
    part_column_name: str = None,
) -> str:
    # This Python function works because the tables only have one part_column.
    # If their schemas were more complex, then just write out the functions
    # individually.
    return (
        f'CREATE OR REPLACE FUNCTION check_host_id_not_distinct_for_{table_name}()'
        ' RETURNS TRIGGER AS'
        ' $func$'
        ' DECLARE'
            # f' new_{part_column_name} {part_table_name}.{part_column_name}%%TYPE;'
            ' new_host_id host.host_id%%TYPE;'
            ' parent_host_id host.host_id%%TYPE;'
            f' pk_value {table_name}.{pk_column}%%TYPE;'
        ' BEGIN'
        ' IF NOT EXISTS (SELECT FROM new_table) THEN'
            ' RETURN NULL;'
        ' END IF;'
        # Check constraints are faster than triggers, and since this refers
        # to columns from the same table, this restriction can be handled
        # with a check constraint.
        # I leave the code here in case we want to switch to using a trigger.
        # There's more flexibility with a trigger (e.g., use WARNING instead
        # of EXCEPTION to allow the operation to go through when we know it
        # will be correct at the end).
        # f"{
        #     f' new_{part_column_name} := (SELECT {table_name}.{part_column_name} FROM new_table n'
        #         f' JOIN {table_name} ON n.{pk_column} = {table_name}.{pk_column}'
        #         f' WHERE {table_name}.host_id IS NULL AND {table_name}.{part_column_name} IS NOT NULL'
        #         ' LIMIT 1);'
        #     f' IF new_{part_column_name} IS NOT NULL THEN'
        #         f" RAISE EXCEPTION '{table_name} cannot have non-null {part_column_name} (%%)"
        #             f" with null host_id', new_{part_column_name};"
        #     ' END IF;'
        #     if part_column_name else
        #     ''
        # }"
        f" EXECUTE 'SELECT n.host_id, {parent_table_name}.host_id, n.{pk_column}"
            f' FROM new_table n'
            f' JOIN {parent_table_name}'
            f' ON n.{parent_pk_column} = {parent_table_name}.{parent_pk_column}'
            f" WHERE n.host_id IS DISTINCT FROM {parent_table_name}.host_id'"
            ' INTO new_host_id, parent_host_id, pk_value;'
        ' IF new_host_id IS DISTINCT FROM parent_host_id THEN'
            # EXCEPTION -> WARNING if needed
            # host_id in the ducts is never used by the application, it's
            # just used by the database to make the FKs work. When only
            # interacting with the database through the application, it
            # shouldn't be possible to set a duct host_id to null when the
            # parent host_id is not null. If raising an EXCEPTION only gives
            # us problems when dealing with FK referential actions and
            # triggers, we should consider making this a WARNING.
            # If you do change to warning, consider changing the
            # *_update_host_id_cascade() functions to be unconditional to
            # always perform updates to improve consistency in nodes and
            # node children. But again, I'm not sure if that's worth it
            # if it isn't normally possible to get duct host_id to be
            # inconsistent with their parent anyway.
            f" RAISE EXCEPTION '{table_name}.{pk_column} = %%, new"
            f" {table_name}.host_id (%%) does not match with parent (%%)',"
            ' pk_value, new_host_id, parent_host_id;'
        ' END IF;'
        ' RETURN NULL;'
        ' END;'
        ' $func$ LANGUAGE plpgsql;'
    )

# fmt: on
event.listen(
    Base.metadata,
    'after_create',
    DDL(
        ''.join(
            [
                # induct table does not have any columns referencing a host child, so
                # there's nothing to pass for part_table_name and part_column_name.
                check_host_id_not_distinct_func(
                    'induct', 'induct_id', 'node', 'node_id'
                ),
                check_host_id_not_distinct_func(
                    'induct_ip',
                    'induct_id',
                    'induct',
                    'induct_id',
                    'destination',
                    'destination_id',
                ),
                check_host_id_not_distinct_func('seat', 'seat_id', 'node', 'node_id'),
                check_host_id_not_distinct_func(
                    'seat_ip',
                    'seat_id',
                    'seat',
                    'seat_id',
                    'destination',
                    'destination_id',
                ),
            ]
        )
    ),
)
# fmt: off

for t in [Induct.__table__, InductIp.__table__, Seat.__table__, SeatIp.__table__]:
    event.listen(Base.metadata, 'after_create', DDL(
        f'CREATE OR REPLACE TRIGGER TG_{t.name}_after_insert_host_id_constraint'
        f' AFTER INSERT ON {t.name}'
        ' REFERENCING NEW TABLE AS new_table'
        ' FOR EACH STATEMENT'
        f' EXECUTE FUNCTION check_host_id_not_distinct_for_{t.name}();'

        f'CREATE OR REPLACE TRIGGER TG_{t.name}_after_update_host_id_constraint'
        f' AFTER UPDATE ON {t.name}'
        ' REFERENCING NEW TABLE AS new_table'
        ' FOR EACH STATEMENT'
        f' EXECUTE FUNCTION check_host_id_not_distinct_for_{t.name}();'
    ))

event.listen(Base.metadata, 'after_create', DDL(
    'CREATE OR REPLACE FUNCTION update_node_modified_at_after_insert()'
    ' RETURNS TRIGGER AS'
    ' $func$'
    ' BEGIN'
    ' IF EXISTS (SELECT FROM new_table) THEN'
        ' UPDATE node SET modified_at = now()'
        ' WHERE node.node_id IN (SELECT n.node_id FROM new_table n);'
    ' END IF;'
    ' RETURN NULL;'
    ' END;'
    ' $func$ LANGUAGE plpgsql;'

    'CREATE OR REPLACE FUNCTION update_node_modified_at_for_node_after_update()'
    ' RETURNS TRIGGER AS'
    ' $func$'
    ' BEGIN'
    # temp_diffs should only exist on recursive calls since it's dropped at the
    # end of this function. If we didn't return early on recursive calls, we'd
    # error since the 'temp_diffs' name is already used. Using 'IF NOT EXISTS'
    # does not help since the 'temp_diffs' table is already populated, so the
    # IF EXISTS condition passes and we'd have infinite recursion.
    # https://dba.stackexchange.com/a/86098
    " IF (SELECT to_regclass('temp_diffs') IS NOT NULL) THEN"
        ' RETURN NULL;'
    ' END IF;'
    # The idea is to put the results of the EXCEPT operation in a table so we
    # only need to perform it once. If there aren't any differences, we don't
    # want to perform the UPDATE. If there are differences, we need to only
    # update the modified_at for the nodes that have changed. Without storing
    # the results in a table, you'd need to perform the EXCEPT once for the IF
    # condition, and once in the subquery used for the WHERE clause of the
    # UPDATE.
    # I don't think ON COMMIT DROP will do anything since we explicitly call
    # DROP TABLE after the IF statement, but it's not breaking anything as far
    # as I'm aware, so I'll just leave it there.
    ' CREATE TEMP TABLE temp_diffs ON COMMIT DROP AS'
        ' SELECT n.node_id, n.node_number, n.allocator_id, n.operator_id, n.host_id,'
        ' n.sdr_config_flags, n.wm_size, n.sdr_wm_size, n.heap_words, n.node_name,'
        ' n.comments FROM new_table n'
        ' EXCEPT'
        ' SELECT o.node_id, o.node_number, o.allocator_id, o.operator_id, o.host_id,'
        ' o.sdr_config_flags, o.wm_size, o.sdr_wm_size, o.heap_words, o.node_name,'
        ' o.comments FROM old_table o ;'
    ' IF EXISTS (SELECT FROM temp_diffs) THEN'
        ' UPDATE node SET modified_at = now()'
        ' WHERE node.node_id IN (SELECT node_id FROM temp_diffs);'
    ' END IF;'
    ' DROP TABLE temp_diffs;'
    ' RETURN NULL;'
    ' END;'
    ' $func$ LANGUAGE plpgsql;'

    'CREATE OR REPLACE FUNCTION update_node_modified_at_after_delete()'
    ' RETURNS TRIGGER AS'
    ' $func$'
    ' BEGIN'
    ' IF EXISTS (SELECT FROM old_table) THEN'
        ' UPDATE node SET modified_at = now()'
        ' WHERE node.node_id IN (SELECT o.node_id FROM old_table o);'
    ' END IF;'
    ' RETURN NULL;'
    ' END;'
    ' $func$ LANGUAGE plpgsql;'

    # Don't need one for AFTER INSERT since default modified_at is now()
    'CREATE OR REPLACE TRIGGER TG_node_after_update_check_modified_at'
    ' AFTER UPDATE ON node'
    ' REFERENCING OLD TABLE AS old_table NEW TABLE AS new_table'
    ' FOR EACH STATEMENT EXECUTE FUNCTION update_node_modified_at_for_node_after_update();'
))


def update_node_modified_at_after_update_func(
    table_name: str, pk_table_name: str = None, second_pk_name: str = None
) -> str:
    """Returns a PL/pgSQL function that updates node.modified_at after
    updates to `table_name`. `table_name` must have a `node_id` column.

    By default, assumes the `table_name` table has a surrogate key
    '{table_name}_id'.

    If `pk_table_name` is not None, then the key used is
    '{pk_table_name}_id'.

    Composite keys with 2 columns are handled by setting `pk_table_name`
    to one column and `second_pk_name` to the other column.
    """
    if pk_table_name is None:
        pk_table_name = table_name
    return (
        'CREATE OR REPLACE FUNCTION'
        f' update_node_modified_at_for_{table_name}_after_update()'
        ' RETURNS TRIGGER AS'
        ' $func$'
        ' BEGIN'
        ' IF EXISTS (SELECT FROM new_table n JOIN old_table o'
            f' ON n.{pk_table_name}_id = o.{pk_table_name}_id'
            f"{
                f' AND n.{second_pk_name} = o.{second_pk_name}'
                if second_pk_name else
                ''
            }"
            ' WHERE ROW(n.*) IS DISTINCT FROM ROW(o.*))'
        ' THEN'
            ' UPDATE node SET modified_at = now()'
                ' WHERE node.node_id IN'
                ' (SELECT n.node_id FROM new_table n JOIN old_table o'
                f' ON n.{pk_table_name}_id = o.{pk_table_name}_id'
                f"{
                    f' AND n.{second_pk_name} = o.{second_pk_name}'
                    if second_pk_name else
                    ''
                }"
                ' WHERE ROW(n.*) IS DISTINCT FROM ROW(o.*));'
        ' END IF;'
        ' RETURN NULL;'
        ' END;'
        ' $func$ LANGUAGE plpgsql;'
    )

# fmt: on
event.listen(
    Base.metadata,
    'after_create',
    DDL(
        update_node_modified_at_after_update_func(
            'endpoint_ipn', pk_table_name='node', second_pk_name='service_number'
        )
        + update_node_modified_at_after_update_func(
            'endpoint_imc', pk_table_name='node', second_pk_name='group_number'
        )
    ),
)

for t in [ClProtocol.__table__, Induct.__table__, Seat.__table__]:
    event.listen(
        Base.metadata,
        'after_create',
        DDL(update_node_modified_at_after_update_func(t.name)),
    )

# fmt: off

for t in [
    EndpointIPN.__table__,
    EndpointIMC.__table__,
    ClProtocol.__table__,
    Induct.__table__,
    Seat.__table__,
    node_contact,
]:
    ddl_str = (
        f'CREATE OR REPLACE TRIGGER TG_{t.name}_after_insert_check_modified_at'
        f' AFTER INSERT ON {t.name}'
        ' REFERENCING NEW TABLE AS new_table'
        ' FOR EACH STATEMENT EXECUTE FUNCTION update_node_modified_at_after_insert();'

        f'CREATE OR REPLACE TRIGGER TG_{t.name}_after_delete_check_modified_at'
        f' AFTER DELETE ON {t.name}'
        ' REFERENCING OLD TABLE AS old_table'
        ' FOR EACH STATEMENT EXECUTE FUNCTION update_node_modified_at_after_delete();'
    )
    # node_contact doesn't need one for AFTER UPDATE since it's just two _id fields
    if t != node_contact:
        ddl_str = ddl_str + (
            f'CREATE OR REPLACE TRIGGER TG_{t.name}_after_update_check_modified_at'
            f' AFTER UPDATE ON {t.name}'
            ' REFERENCING OLD TABLE AS old_table NEW TABLE AS new_table'
            ' FOR EACH STATEMENT EXECUTE FUNCTION'
            f' update_node_modified_at_for_{t.name}_after_update();'
        )
    event.listen(Base.metadata, 'after_create', DDL(ddl_str))


def update_node_modified_at_for_table_with_parent_func(
    table_name: str, parent_table_name: str
) -> str:
    """Returns PL/pgSQL functions that updates node.modified_at for
    insertions / updates / deletions to `table_name` where `table_name`
    does not have a `node_id` column, but `table_name` is related to
    `parent_table_name` which does have `node_id`.

    Assumes that the surrogate key in `parent_table_name` is also in
    `table_name`.
    """
    return (
        'CREATE OR REPLACE FUNCTION'
        f' update_node_modified_at_for_{table_name}_after_insert()'
        ' RETURNS TRIGGER AS'
        ' $func$'
        ' BEGIN'
        ' IF EXISTS (SELECT FROM new_table) THEN'
            ' UPDATE node SET modified_at = now()'
                f' FROM {table_name} JOIN {parent_table_name}'
                f' ON {table_name}.{parent_table_name}_id'
                    f' = {parent_table_name}.{parent_table_name}_id'
                f' WHERE {parent_table_name}.node_id = node.node_id'
                f' AND {parent_table_name}.{parent_table_name}_id IN'
                f' (SELECT n.{parent_table_name}_id FROM new_table n);'
        ' END IF;'
        ' RETURN NULL;'
        ' END;'
        ' $func$ LANGUAGE plpgsql;'

        # This update trigger should rarely fire. The application won't
        # allow modifying the association between a link and duct or between
        # a link and seat but this is still possible with psql.
        'CREATE OR REPLACE FUNCTION'
        f' update_node_modified_at_for_{table_name}_after_update()'
        ' RETURNS TRIGGER AS'
        ' $func$'
        ' BEGIN'
        ' IF EXISTS (SELECT FROM new_table n JOIN old_table o'
            f' ON n.{parent_table_name}_id = o.{parent_table_name}_id'
            ' WHERE ROW(n.*) IS DISTINCT FROM ROW(o.*))'
        ' THEN'
            ' UPDATE node SET modified_at = now()'
                f' FROM {table_name} JOIN {parent_table_name}'
                f' ON {table_name}.{parent_table_name}_id'
                    f' = {parent_table_name}.{parent_table_name}_id'
                f' WHERE {parent_table_name}.node_id = node.node_id'
                f' AND {parent_table_name}.{parent_table_name}_id IN'
                f' (SELECT n.{parent_table_name}_id FROM new_table n'
                ' JOIN old_table o'
                f' ON n.{parent_table_name}_id = o.{parent_table_name}_id'
                ' WHERE ROW(n.*) IS DISTINCT FROM ROW(o.*));'
        ' END IF;'
        ' RETURN NULL;'
        ' END;'
        ' $func$ LANGUAGE plpgsql;'

        'CREATE OR REPLACE FUNCTION'
        f' update_node_modified_at_for_{table_name}_after_delete()'
        ' RETURNS TRIGGER AS'
        ' $func$'
        ' BEGIN'
        ' IF EXISTS (SELECT FROM old_table) THEN'
            ' UPDATE node SET modified_at = now()'
            f' WHERE node.node_id in (SELECT {parent_table_name}.node_id'
                f' FROM old_table JOIN {parent_table_name}'
                f' ON old_table.{parent_table_name}_id'
                    f' = {parent_table_name}.{parent_table_name}_id);'
        ' END IF;'
        ' RETURN NULL;'
        ' END;'
        ' $func$ LANGUAGE plpgsql;'
    )


# TODO: if you keep the M:N between seats and link_service_protocol, then
# you need to update node.modified_at() when that changes too.
for t, parent_table_name in (
    (induct_link, 'induct'),
    (InductIp.__table__, 'induct'),
    (induct_seat, 'induct'),  # Think this can be 'induct' or 'seat'
    (seat_link, 'seat'),
    (SeatIp.__table__, 'seat')
):
    event.listen(t, 'after_create', DDL(
        update_node_modified_at_for_table_with_parent_func(t.name, parent_table_name)
        + f'CREATE OR REPLACE TRIGGER TG_{t.name}_after_insert_check_modified_at'
        f' AFTER INSERT ON {t.name}'
        ' REFERENCING NEW TABLE AS new_table'
        ' FOR EACH STATEMENT EXECUTE FUNCTION'
        f' update_node_modified_at_for_{t.name}_after_insert();'
        f'CREATE OR REPLACE TRIGGER TG_{t.name}_after_update_check_modified_at'
        f' AFTER UPDATE ON {t.name}'
        ' REFERENCING OLD TABLE AS old_table NEW TABLE AS new_table'
        ' FOR EACH STATEMENT EXECUTE FUNCTION'
        f' update_node_modified_at_for_{t.name}_after_update();'
        f'CREATE OR REPLACE TRIGGER TG_{t.name}_after_delete_check_modified_at'
        f' AFTER DELETE ON {t.name}'
        ' REFERENCING OLD TABLE AS old_table'
        ' FOR EACH STATEMENT EXECUTE FUNCTION'
        f' update_node_modified_at_for_{t.name}_after_delete();'
    ))

# fmt: on


# https://github.com/sqlalchemy/sqlalchemy/wiki/Views
class CreateView(ExecutableDDLElement):
    def __init__(self, name, selectable):
        self.name = name
        self.selectable = selectable


class DropView(ExecutableDDLElement):
    def __init__(self, name):
        self.name = name


@compiles(CreateView)
def _create_view(element, compiler, **kw):
    return 'CREATE VIEW %s AS %s' % (
        element.name,
        compiler.sql_compiler.process(element.selectable, literal_binds=True),
    )


@compiles(DropView)
def _drop_view(element, compiler, **kw):
    return 'DROP VIEW %s' % (element.name)


def view_exists(ddl, target, connection, **kw):
    return ddl.name in inspect(connection).get_view_names()


def view_doesnt_exist(ddl, target, connection, **kw):
    return not view_exists(ddl, target, connection, **kw)


def view(name, metadata, selectable):
    t = table(
        name,
        *(
            Column(c.name, c.type, primary_key=c.primary_key)
            for c in selectable.selected_columns
        ),
    )
    t.primary_key.update(c for c in t.c if c.primary_key)

    event.listen(
        metadata,
        'after_create',
        CreateView(name, selectable).execute_if(callable_=view_doesnt_exist),
    )
    event.listen(
        metadata, 'before_drop', DropView(name).execute_if(callable_=view_exists)
    )
    return t


class NodeGeneralInfo(Base):
    """View to show general information about nodes.
    Has 10 columns:
    (
        node_id,
        allocator_id, node_number,
        operator_id, operator_name,
        host_id, hostname,
        num_endpoints, num_inducts, num_seats
    )
    (allocator_id, node_number) makes up the Fully Qualified Node Number
    node_id is just there to help the frontend uniquely identify each
    record, should not be displayed.
    operator_id and host_id also shouldn't be displayed and should be
    used to link to the pages for the operator and host, respectively.
    """

    # TODO: either change label to `num_ipn_endpoints` or perform UNION
    # to include imc endpoints
    e_subq = (
        select(EndpointIPN.node_id, func.count().label('num_endpoints'))
        .group_by(EndpointIPN.node_id)
        .subquery()
    )

    i_subq = (
        select(Induct.node_id, func.count().label('num_inducts'))
        .group_by(Induct.node_id)
        .subquery()
    )

    s_subq = (
        select(Seat.node_id, func.count().label('num_seats'))
        .group_by(Seat.node_id)
        .subquery()
    )

    stmt = (
        select(
            Node.node_id,
            Node.allocator_id,
            Node.node_number,
            Node.operator_id,
            Operator.operator_name,
            Node.host_id,
            Host.hostname,
            func.coalesce(e_subq.c.num_endpoints, 0).label('num_endpoints'),
            func.coalesce(i_subq.c.num_inducts, 0).label('num_inducts'),
            func.coalesce(s_subq.c.num_seats, 0).label('num_seats'),
        )
        .select_from(Node)
        .join(Operator, Node.operator_id == Operator.operator_id, isouter=True)
        .join(Host, Node.host_id == Host.host_id, isouter=True)
        .join(e_subq, Node.node_id == e_subq.c.node_id, isouter=True)
        .join(i_subq, Node.node_id == i_subq.c.node_id, isouter=True)
        .join(s_subq, Node.node_id == s_subq.c.node_id, isouter=True)
    )

    __table__ = view('node_general_info', Base.metadata, stmt)

    def __repr__(self):
        return (
            f'NodeGeneralInfo(node_id={self.node_id!r},'
            f' allocator_id={self.allocator_id!r},'
            f' node_number={self.node_number!r},'
            f' operator_id={self.operator_id!r},'
            f' operator_name={self.operator_name!r},'
            f' host_id={self.host_id!r}, '
            f' hostname={self.hostname!r},'
            f' num_endpoints={self.num_endpoints!r},'
            f' num_inducts={self.num_inducts!r},'
            f' num_seats={self.num_seats!r})'
        )


class DeletedRecord(Base):
    """Table to store deleted records.

    Design is modified from https://brandur.org/soft-deletion
    """

    __tablename__ = 'deleted_record'

    # Should be bigint if deletions are frequent
    deleted_record_id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    # https://justatheory.com/2012/04/postgres-use-timestamptz/
    # Generally should use timestampz. Only use timestamp when partitioning
    deleted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    table_name: Mapped[str] = mapped_column(Text)
    # Psycopg uses Python's standard libary json.load to de-serialize which
    # can be different Python types
    data = mapped_column(JSONB, nullable=False)

    def __repr__(self) -> str:
        return (
            f'DeletedRecord(deleted_record_id={self.deleted_record_id!r},'
            f' deleted_at={self.deleted_at!r},'
            f' table_name={self.table_name!r},'
            f' data={self.data!r})'
        )


for table_name, table_obj in Base.metadata.tables.items():
    event.listen(
        table_obj,
        'after_create',
        DDL(
            'CREATE OR REPLACE FUNCTION soft_delete()'
            ' RETURNS TRIGGER AS'
            ' $func$'
            ' BEGIN'
            ' IF EXISTS (SELECT FROM old_table) THEN'
                ' INSERT INTO deleted_record (table_name, data)'
                ' SELECT TG_TABLE_NAME, to_jsonb(o.*) FROM old_table o;'
            ' END IF;'
            ' RETURN NULL;'
            ' END;'
            ' $func$ LANGUAGE plpgsql;'
        ),
    )  # fmt: skip
    if table_obj not in [DeletedRecord.__table__]:
        event.listen(
            table_obj,
            'after_create',
            DDL(
                f'CREATE OR REPLACE TRIGGER TG_{table_name}_soft_delete'
                f' AFTER DELETE ON public.{table_name}'
                ' REFERENCING OLD TABLE AS old_table'
                ' FOR EACH STATEMENT EXECUTE FUNCTION soft_delete();'
            ),
        )

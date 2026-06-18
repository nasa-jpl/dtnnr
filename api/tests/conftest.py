from __future__ import annotations

import os
from typing import TYPE_CHECKING

import factory
import pytest
from litestar.testing import TestClient
from sqlalchemy import bindparam, delete, select, text
from sqlalchemy_utils import create_database, database_exists, drop_database

os.environ['DATABASE_NAME'] = 'dtnnr_test'
# Application logs are just sent to stdout, so setting --log-cli-level won't
# do anything. We generally don't need to see the application logs, so we
# set it to error.
os.environ['LOG_LEVEL'] = '40'  # error

# Make these smaller to be more manageable
os.environ['DEFAULT_PAGE_SIZE'] = '5'
os.environ['MAX_PAGE_SIZE'] = '10'

from app.config import MAX_PAGE_SIZE, SQLALCHEMY_DATABASE_URI, log_config

# engine is from application. There's no point in creating multpile engines
# when we set them up with the same arguments anyway.
from app.database import Base, engine
from app.models import (
    Allocator,
    Band,
    Contact,
    Destination,
    Host,
    Node,
    Operator,
    UnderlyingCommunicationService,
    cli_command_with_required_protocol_name,
    known_cl_protocol_name_to_class,
)

# scoped_session is from test layer, not application
from .database import scoped_session_for_testing
from .factories import (
    BAND_ID_DEFAULT_MAX,
    BAND_ID_DEFAULT_MIN,
    UNDERLYING_COMMUNICATION_SERVICE_ID_DEFAULT_MAX,
    UNDERLYING_COMMUNICATION_SERVICE_ID_DEFAULT_MIN,
    AllocatorFactory,
    BandFactory,
    ClProtocolFactory,
    CommDirectionEnumInternal,
    ContactFactory,
    DestinationFactory,
    EndpointIMCFactory,
    EndpointIPNFactory,
    HostFactory,
    InductFactory,
    InductIpFactory,
    LinkFactory,
    LinkRfFactory,
    NodeFactory,
    OperatorFactory,
    PhoneNumberFactory,
    SeatFactory,
    SeatIpFactory,
    UnderlyingCommunicationServiceFactory,
    fake,
    generate_cl_protocol_name,
)

if TYPE_CHECKING:
    from collections.abc import Generator, Iterator

    from litestar import Litestar
    from sqlalchemy.orm import Session

    from app.models import (
        ClProtocol,
        ContactPhoneNumber,
        EndpointIMC,
        Induct,
        InductIp,
        Link,
        LinkRf,
        Seat,
        SeatIp,
    )

log_config.structlog_logging_config.configure()
log_config.structlog_logging_config.standard_lib_logging_config.configure()


@pytest.fixture(scope='session')
def app() -> Litestar:
    from app.asgi import create_app

    return create_app(csrf_protection_enabled=False)


@pytest.fixture(scope='session')
def client(app: Litestar) -> Iterator[TestClient[Litestar]]:
    with TestClient(app=app) as client:
        yield client


@pytest.fixture(scope='session')
def db():
    if database_exists(SQLALCHEMY_DATABASE_URI):
        drop_database(SQLALCHEMY_DATABASE_URI)
    create_database(SQLALCHEMY_DATABASE_URI)

    Base.metadata.create_all(engine)
    scoped_session_for_testing.configure(bind=engine)
    yield

    drop_database(SQLALCHEMY_DATABASE_URI)


def print_tables(session: Session):
    print(session.scalars(select(Contact)).all())
    print(session.scalars(select(Allocator).where(Allocator.allocator_id > 0)).all())
    print(session.scalars(select(Operator)).all())
    print(session.scalars(select(Host)).all())
    print(session.scalars(select(Destination)).all())
    print(session.scalars(select(Node)).all())
    print(
        session.scalars(
            select(UnderlyingCommunicationService).where(
                (
                    UnderlyingCommunicationService.underlying_communication_service_id
                    < UNDERLYING_COMMUNICATION_SERVICE_ID_DEFAULT_MIN
                )
                | (
                    UnderlyingCommunicationService.underlying_communication_service_id
                    > UNDERLYING_COMMUNICATION_SERVICE_ID_DEFAULT_MAX
                )
            )
        ).all()
    )
    print(
        session.scalars(
            select(Band).where(
                (Band.band_id < BAND_ID_DEFAULT_MIN)
                | (Band.band_id > BAND_ID_DEFAULT_MAX)
            )
        ).all()
    )


def cleanup(session: Session):
    # session.execute(text('SET CONSTRAINTS ALL DEFERRED'))
    print('*** BEFORE')
    print_tables(session)
    session.execute(delete(Contact.__table__))
    session.execute(delete(Operator.__table__))
    session.execute(delete(Host.__table__))
    session.execute(delete(Node.__table__))
    # Need to delete allocators after nodes and operators since deletion
    # is restricted if an allocator is still used by operators or nodes
    session.execute(delete(Allocator.__table__).where(Allocator.allocator_id > 0))
    session.execute(
        delete(UnderlyingCommunicationService.__table__).where(
            (
                UnderlyingCommunicationService.underlying_communication_service_id
                < UNDERLYING_COMMUNICATION_SERVICE_ID_DEFAULT_MIN
            )
            | (
                UnderlyingCommunicationService.underlying_communication_service_id
                > UNDERLYING_COMMUNICATION_SERVICE_ID_DEFAULT_MAX
            )
        )
    )
    session.execute(
        delete(Band.__table__).where(
            (Band.band_id < BAND_ID_DEFAULT_MIN) | (Band.band_id > BAND_ID_DEFAULT_MAX)
        )
    )
    session.commit()
    print('*** AFTER')
    print_tables(session)
    fake.unique.clear()


# SQLAlchemy docs have a pattern for using sessions in tests
# https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites
# For each test function, start with BEGIN and perform insertions, updates,
# etc. inside a SAVEPOINT. Calling .commit() will RELEASE the savepoint
# while .rollback() will ROLLBACK TO the savepoint.
#
# To use this pattern with tests that make reqeusts to the web application,
# the session used by the application should be the same as the session that
# this fixture creates. You can either 1) create a scoped_session/sessionmaker
# in the testing layer and inject it into the application, or 2) import the
# scoped_session/sessionmaker used by the application and use it in the testing
# layer.
#
# In either case, you can't remove the session after the web request since we
# still want to access the objects in the session to do assertions. And the
# idea of having multiple requests use the same session goes against the point
# of linking the scope of a session with that of a web request.
#
# Instead of following the approach in the SQLAlchemy docs, the session used by
# the web application comes from a sessionmaker while the session used in tests
# come from a scoped_sesion using a separate sessionmaker.
# The application creates and removes a session for each web request, and the
# tests can still refer to objects and access their attributes after a request.
# Due to scoped_session using thread-local scope, the session used by factories
# and fixtures will be teh same Session since tests are run on one thread.
#
# We don't need to manually call .rollback() if the application session runs
# into an exception.
# We don't use nested transactions, so .commit() and .rollback() don't use
# the SAVEPOINT related statements. Since changes were committed to the database,
# we have to delete records at the end of each test instead of ROLLBACK.
#
# ROLLBACK in the one scoped_session doesn't really give you a fresh state as
# if *nothing* happened since Postgres sequence state changes are not undone
# by rolling back a transaction.
# https://www.postgresql.org/docs/current/functions-sequence.html
#
# On the SQLAlchemy mailing list, they talked about how you shouldn't have
# two sessions in play.
# https://groups.google.com/g/sqlalchemy/c/0MEL9xt5LFY/m/0Mc3nDl4BQAJ
# But I don't see what's the problem since the session used by the application
# is created and closed within a web request.
#
# As an aside, SAVEPOINT can have a lot of performance issues, but I
# think our application and tests are too small scale for these problems
# to be relevant:
# https://about.gitlab.com/blog/2021/09/29/why-we-spent-the-last-month-eliminating-postgresql-subtransactions/
# https://www.cybertec-postgresql.com/en/subtransactions-and-performance-in-postgresql/
# https://postgres.ai/blog/20210831-postgresql-subtransactions-considered-harmful


@pytest.fixture(scope='function', autouse=True)
def session(db) -> Generator[Session, None]:
    session = scoped_session_for_testing()
    yield session
    # .rollback() in case of PendingRollbackError
    session.rollback()
    cleanup(session)
    session.rollback()
    scoped_session_for_testing.remove()


@pytest.fixture
def phone_numbers(session: Session) -> list[ContactPhoneNumber]:
    return [PhoneNumberFactory(), PhoneNumberFactory()]


@pytest.fixture
def contact(session: Session) -> Contact:
    return ContactFactory()


@pytest.fixture
def contact_max_and_one_phone_numbers(session: Session) -> Contact:
    """Contact with guaranteed multiple phone numbers."""
    contact: Contact = ContactFactory.create(phone_numbers=[])
    for i in range(MAX_PAGE_SIZE + 1):
        PhoneNumberFactory(contact=contact, order_pos=i)
    return contact


@pytest.fixture
def contact_with_details(session: Session) -> Contact:
    """Contact with an allocator, operator, host, and node."""
    res = ContactFactory(
        allocators=(AllocatorFactory(),),
        operators=(OperatorFactory(),),
        hosts=(HostFactory(),),
        nodes=(NodeFactory(),),
    )
    # Need to .commit() or association table won't get populated
    session.commit()
    return res


@pytest.fixture
def contacts(session: Session) -> list[Contact]:
    return [ContactFactory(), ContactFactory()]


@pytest.fixture
def contacts_max_and_one(session: Session) -> list[Contact]:
    """List of contacts at the maximum amount per page plus one."""
    res = []
    for _ in range(MAX_PAGE_SIZE + 1):
        res.append(ContactFactory())
    return res


@pytest.fixture
def contacts_with_details(session: Session) -> list[Contact]:
    return [
        ContactFactory(
            allocators=(AllocatorFactory(),),
            operators=(OperatorFactory(),),
            hosts=(HostFactory(),),
            nodes=(NodeFactory(),),
        ),
        ContactFactory(
            allocators=(AllocatorFactory(),),
            operators=(OperatorFactory(),),
            hosts=(HostFactory(),),
            nodes=(NodeFactory(),),
        ),
        ContactFactory(
            allocators=(AllocatorFactory(),),
            operators=(OperatorFactory(),),
            hosts=(HostFactory(),),
            nodes=(NodeFactory(),),
        ),
    ]


@pytest.fixture
def allocator(session: Session) -> Allocator:
    return AllocatorFactory()


@pytest.fixture
def allocator_default(session: Session) -> Allocator:
    # Assume that the Default Allocator is never deleted
    return session.scalar(select(Allocator).where(Allocator.allocator_id == 0))


@pytest.fixture
def allocator_with_details(session: Session, node: Node) -> Allocator:
    """Allocator from a node, with 2 new contacts."""
    allocator = node.allocator
    c1 = ContactFactory()
    c2 = ContactFactory()
    session.add_all([c1, c2])
    session.commit()
    allocator.contacts.extend([c1, c2])
    session.commit()
    return allocator


@pytest.fixture
def allocator_max_contacts_and_one(session: Session) -> Allocator:
    allocator: Allocator = AllocatorFactory.create()
    contacts = []
    for _ in range(MAX_PAGE_SIZE + 1):
        contacts.append(ContactFactory())
    allocator.contacts.extend(contacts)
    session.commit()
    return allocator


@pytest.fixture
def allocators(session: Session) -> list[Allocator]:
    return [AllocatorFactory(), AllocatorFactory()]


@pytest.fixture
def allocators_max_and_one(session: Session) -> list[Allocator]:
    """List of allocators at the maximum amount per page plus one."""
    res = []
    for _ in range(MAX_PAGE_SIZE + 1):
        res.append(AllocatorFactory())
    return res


@pytest.fixture
def operator(session: Session) -> Operator:
    return OperatorFactory()


@pytest.fixture
def operator_with_details(session: Session, node: Node) -> Operator:
    """Operator from a node, with 2 new contacts."""
    operator = node.operator
    c1 = ContactFactory()
    c2 = ContactFactory()
    session.add_all([c1, c2])
    session.commit()
    operator.contacts.extend([c1, c2])
    session.commit()
    return operator


@pytest.fixture
def operator_max_contacts_and_one(session: Session) -> Operator:
    operator: Operator = OperatorFactory.create()
    contacts = []
    for _ in range(MAX_PAGE_SIZE + 1):
        contacts.append(ContactFactory())
    operator.contacts.extend(contacts)
    session.commit()
    return operator


@pytest.fixture
def operators(session: Session) -> list[Operator]:
    return [OperatorFactory(), OperatorFactory()]


@pytest.fixture
def operators_same_allocator(session: Session, operator: Operator) -> list[Operator]:
    """List of operators under the same allocator."""
    return [
        operator,
        OperatorFactory(allocator=operator.allocator),
        OperatorFactory(allocator=operator.allocator),
        OperatorFactory(allocator=operator.allocator),
    ]


@pytest.fixture
def operators_overlapping_allocated_node_numbers(session: Session) -> list[Operator]:
    """List of two operators under different allocators. The
    allocated_node_numbers of the first operator overlaps with the
    second's.
    """
    o1 = OperatorFactory()
    o2 = OperatorFactory()
    o1_lower = o1.allocated_node_numbers[0].lower
    o2_upper = o2.allocated_node_numbers[0].upper
    # fmt: off
    stmt = text(
        'UPDATE operator'
        ' SET allocated_node_numbers = allocated_node_numbers'
            '+int8multirange(int8range(:lower, :upper, :bounds))'
        ' WHERE operator_id = :operator_id;'
    ).bindparams(
        bindparam('lower', value=o1_lower),
        bindparam('upper', value=o2_upper),
        bindparam('bounds', value='[)'),
        bindparam('operator_id', value=o1.operator_id),
    )
    # fmt: on
    session.execute(stmt)
    session.commit()
    return [o1, o2]


@pytest.fixture
def operators_max_and_one(session: Session) -> list[Operator]:
    """List of operators at the maximum amount per page plus one."""
    res = []
    for _ in range(MAX_PAGE_SIZE + 1):
        res.append(OperatorFactory())
    return res


@pytest.fixture
def host(session: Session) -> Host:
    """A host under an operator (which is under a new allocator) and a
    destination."""
    return HostFactory()


@pytest.fixture
def host_no_operator(session: Session) -> Host:
    """A host not under an operator with a destination."""
    return HostFactory(operator=None)


@pytest.fixture
def host_with_links(session: Session) -> Host:
    """A host with two links."""
    host: Host = HostFactory.create()
    l1 = LinkFactory()
    l2 = LinkFactory()
    host.links.extend([l1, l2])
    session.commit()
    return host


@pytest.fixture
def host_max_and_one_links(session: Session) -> Host:
    host: Host = HostFactory.create()
    for _ in range(MAX_PAGE_SIZE + 1):
        LinkFactory(host=host)
    return host


@pytest.fixture
def host_with_destinations(session: Session) -> Host:
    """A host with two destinations."""
    host: Host = HostFactory.create(destinations=[])
    # Faker unique guarantees these will be different
    DestinationFactory(host=host)
    DestinationFactory(host=host)
    return host


@pytest.fixture
def host_max_and_one_destinations(session: Session) -> Host:
    host: Host = HostFactory.create(destinations=[])
    for _ in range(MAX_PAGE_SIZE + 1):
        DestinationFactory(host=host)
    return host


@pytest.fixture
def host_with_full_nodes(session: Session) -> Host:
    """Host with destinations and links. There are two nodes on the host
    with IPN and IMC endpoints, CL protocols, inducts, and seats. There
    are IP inducts and seats that reference destinations and are
    associated with links on the host.
    """
    host: Host = HostFactory.create()
    l1 = LinkFactory(direction=CommDirectionEnumInternal.FULL_DUPLEX, host=host)
    l2 = LinkFactory(direction=CommDirectionEnumInternal.HALF_DUPLEX, host=host)
    d1 = DestinationFactory.create(post__ip=True, host=host)
    d2 = DestinationFactory.create(post__name=True, host=host)
    d3 = DestinationFactory.create(post__ip=True, host=host)
    session.commit()

    for _ in range(2):
        node: Node = NodeFactory.create(host=host)
        EndpointIMCFactory(node=node)
        EndpointIMCFactory(node=node)
        ltp_cl: ClProtocol = ClProtocolFactory.create(
            node=node,
            cl_protocol_name='ltp',
        )
        tcp_cl: ClProtocol = ClProtocolFactory.create(
            node=node,
            cl_protocol_name='tcp',
        )
        i1: Induct = InductFactory.create(
            node=node, type='ip', cl_protocol=tcp_cl, induct_ip=True
        )
        i1.links.extend([l1, l2])
        i2: Induct = InductFactory.create(
            node=node, type='ip', cl_protocol=tcp_cl, induct_ip=True
        )
        i2.links.extend([l1, l2])
        i3: Induct = InductFactory.create(
            node=node, type='ip', cl_protocol=tcp_cl, induct_ip=True
        )
        i3.links.extend([l1, l2])
        i4: Induct = InductFactory.create(
            node=node, type='ip', cl_protocol=tcp_cl, induct_ip=True
        )
        i4.links.extend([l1, l2])
        InductIpFactory.create(induct=i1, destination=d1)
        InductIpFactory.create(induct=i2, destination=d2)
        InductIpFactory.create(
            induct=i3, host_id=i3.host_id, destination_id=None, destination=None
        )
        InductIpFactory.create(induct=i4, destination=d3)
        i5: Induct = InductFactory.create(
            node=node, type=None, cl_protocol=ltp_cl, induct_ip=False
        )
        s1: Seat = SeatFactory.create(node=node, type='ip', seat_ip=True)
        s1.links.extend([l1, l2])
        s1.inducts.append(i5)
        s2: Seat = SeatFactory.create(node=node, type='ip', seat_ip=True)
        s2.links.extend([l1, l2])
        s2.inducts.append(i5)
        s3: Seat = SeatFactory.create(node=node, type='ip', seat_ip=True)
        s3.links.extend([l1, l2])
        s3.inducts.append(i5)
        s4: Seat = SeatFactory.create(node=node, type='ip', seat_ip=True)
        s4.links.extend([l1, l2])
        s4.inducts.append(i5)
        SeatIpFactory.create(seat=s1, destination=d1)
        SeatIpFactory.create(seat=s2, destination=d2)
        SeatIpFactory.create(
            seat=s3,
            host_id=s3.host_id,
            destination_id=None,
            destination=None,
        )
        SeatIpFactory.create(seat=s4, destination=d3)
    session.commit()

    return host


@pytest.fixture
def host_with_contacts(session: Session) -> Host:
    """Host with 2 new contacts."""
    host = HostFactory()
    c1 = ContactFactory()
    c2 = ContactFactory()
    session.add_all([c1, c2])
    session.commit()
    host.contacts.extend([c1, c2])
    session.commit()
    return host


@pytest.fixture
def host_max_contacts_and_one(session: Session) -> Host:
    host: Host = HostFactory.create()
    contacts = []
    for _ in range(MAX_PAGE_SIZE + 1):
        contacts.append(ContactFactory())
    host.contacts.extend(contacts)
    session.commit()
    return host


@pytest.fixture
def hosts(session: Session) -> list[Host]:
    return [HostFactory(), HostFactory()]


@pytest.fixture
def hosts_max_and_one(session: Session) -> list[Host]:
    """List of hosts at the maximum amount per page plus one."""
    res = []
    for _ in range(MAX_PAGE_SIZE + 1):
        res.append(HostFactory())
    return res


@pytest.fixture
def destination_ip(session: Session) -> Destination:
    """A destination with an IP address."""
    return DestinationFactory(post__ip=True)


@pytest.fixture
def destination_name(session: Session) -> Destination:
    """A destination with a registered name."""
    return DestinationFactory(post__name=True)


@pytest.fixture
def destinations_same_host(session: Session) -> list[Destination]:
    """Two destinations (IP and name) on the same host."""
    host = HostFactory()
    return [
        DestinationFactory(host=host, post__ip=True),
        DestinationFactory(host=host, post__name=True),
    ]


@pytest.fixture
def underlying_communication_services(
    session: Session,
) -> list[UnderlyingCommunicationService]:
    return [
        UnderlyingCommunicationServiceFactory(),
        UnderlyingCommunicationServiceFactory(),
    ]


@pytest.fixture
def underlying_communication_services_max_and_one(
    session: Session,
) -> list[UnderlyingCommunicationService]:
    res = []
    for _ in range(MAX_PAGE_SIZE + 1):
        res.append(UnderlyingCommunicationServiceFactory())
    return res


@pytest.fixture
def link(session: Session) -> Link:
    """Parent link with no child."""
    return LinkFactory()


@pytest.fixture
def link_null_direction(session: Session) -> Link:
    """Link with 'N/A' direction"""
    return LinkFactory(direction=CommDirectionEnumInternal.N_A.value)


@pytest.fixture
def link_with_underlying_communication_service(session: Session) -> Link:
    """Link under a host with a single underlying communication service."""
    link: Link = LinkFactory.create()
    service = UnderlyingCommunicationServiceFactory()
    link.underlying_communication_services.append(service)
    session.commit()
    return link


@pytest.fixture
def link_with_inducts(session: Session) -> Link:
    """Full duplex link associated with three inducts."""
    link: Link = LinkFactory.create(
        direction=CommDirectionEnumInternal.FULL_DUPLEX.value
    )
    node: Node = NodeFactory.create(host=link.host)
    for _ in range(3):
        induct: Induct = InductFactory.create(
            node=node,
            cl_protocol=factory.SubFactory(
                ClProtocolFactory,
                cl_protocol_name=factory.LazyAttribute(
                    lambda _: generate_cl_protocol_name(no_ltp=True)
                ),
                node=node,
            ),
        )
        induct.links.append(link)
    session.commit()
    return link


@pytest.fixture
def links(session: Session) -> list[Link]:
    return [LinkFactory(), LinkFactory()]


@pytest.fixture
def links_simplex_outgoing_etc(session: Session) -> list[Link]:
    """List of 7 links with at least two simplex (outgoing) links."""
    links = []
    links.append(LinkFactory(direction=CommDirectionEnumInternal.SIMPLEX_OUT))
    for _ in range(5):
        links.append(LinkFactory())
    links.append(LinkFactory(direction=CommDirectionEnumInternal.SIMPLEX_OUT))
    session.commit()
    return links


@pytest.fixture
def links_not_simplex_outgoing(session: Session) -> list[Link]:
    """List of links on different hosts. None of the links are simplex
    (outgoint).
    """
    links = []
    for d in CommDirectionEnumInternal:
        if d == CommDirectionEnumInternal.SIMPLEX_OUT:
            continue
        links.append(LinkFactory(direction=d))
    session.commit()
    return links


@pytest.fixture
def band(session: Session) -> Band:
    """A new lookup value in the `band` table."""
    return BandFactory()


@pytest.fixture
def bands(session: Session) -> list[Band]:
    return [BandFactory(), BandFactory()]


@pytest.fixture
def bands_max_and_one(session: Session) -> list[Band]:
    res = []
    for _ in range(MAX_PAGE_SIZE + 1):
        res.append(BandFactory())
    return res


@pytest.fixture
def link_rf(session: Session) -> LinkRf:
    """Child `link_rf` with a band under a parent link."""
    return LinkRfFactory()


@pytest.fixture
def node(session: Session) -> Node:
    """A node with with a host, under the host's operator, and 7
    ipn endpoints."""
    return NodeFactory()


@pytest.fixture
def node_default_allocator(session: Session, allocator_default: Allocator) -> Node:
    """A node with allocator_id == 0 and node_number == 2^32 - 2."""
    return NodeFactory(
        allocator=allocator_default, operator=None, node_number=2**32 - 2
    )


@pytest.fixture
def node_localnode(session: Session, allocator_default: Allocator) -> Node:
    """A node with allocator_id == 0 and node_number == 2^32 - 1."""
    return NodeFactory(
        allocator=allocator_default, operator=None, node_number=2**32 - 1
    )


@pytest.fixture
def node_no_host(session: Session) -> Node:
    """A node without a host. The node has IPN and IMC endpoints, CL
    protocols, inducts, and seats.
    """
    node: Node = NodeFactory.create(host=None, operator=OperatorFactory.create())
    induct: Induct = InductFactory.create(
        node=node,
        cl_protocol=factory.SubFactory(
            ClProtocolFactory,
            cl_protocol_name='ltp',
            node=factory.SelfAttribute('..node'),
        ),
    )
    prefix = 'protocol'
    for _ in range(2):
        EndpointIPNFactory(node=node)
        EndpointIMCFactory(node=node)
        cl_protocol: ClProtocol = ClProtocolFactory.create(
            node=node,
            cl_protocol_name=fake.unique.pystr(
                max_chars=15 - len(prefix), prefix=prefix
            ),
        )
        InductFactory.create(
            node=node, cl_protocol=cl_protocol, induct_ip=False, type='ip'
        )
        seat: Seat = SeatFactory.create(node=node, seat_ip=False)
        seat.inducts.append(induct)
    session.commit()
    return node


@pytest.fixture
def node_with_safe_unsafe_ipn_endpoints(session: Session) -> Node:
    """A node with two IPN endpoints with service numbers 2^53 - 1 and
    2^53.
    """
    node: Node = NodeFactory.create()
    EndpointIPNFactory(node=node, service_number=2**53 - 1)
    EndpointIPNFactory(node=node, service_number=2**53)
    session.commit()
    return node


@pytest.fixture
def node_max_and_one_ipn_endpoints(session: Session) -> Node:
    node: Node = NodeFactory.create()
    for _ in range(MAX_PAGE_SIZE + 1):
        EndpointIPNFactory(node=node)
    session.commit()
    return node


@pytest.fixture
def node_with_imc_endpoints(session: Session) -> Node:
    """A node with two imc endpoints."""
    node: Node = NodeFactory.create()
    EndpointIMCFactory(node=node)
    EndpointIMCFactory(node=node)
    session.commit()
    return node


@pytest.fixture
def node_with_safe_unsafe_imc_endpoints(session: Session) -> Node:
    """A node with two IMC endpoints with group numbers 2^53 - 1 and
    2^53.
    """
    node: Node = NodeFactory.create()
    EndpointIMCFactory(node=node, group_number=2**53 - 1)
    EndpointIMCFactory(node=node, group_number=2**53)
    session.commit()
    return node


@pytest.fixture
def node_max_and_one_imc_endpoints(session: Session) -> Node:
    node: Node = NodeFactory.create()
    for _ in range(MAX_PAGE_SIZE + 1):
        EndpointIMCFactory(node=node)
    session.commit()
    return node


@pytest.fixture
def node_with_cl_protocols(session: Session) -> Node:
    node: Node = NodeFactory.create()
    ClProtocolFactory(cl_protocol_name='ltp', node=node)
    ClProtocolFactory(cl_protocol_name='udp', node=node)
    session.commit()
    return node


@pytest.fixture
def node_max_and_one_cl_protocols(session: Session) -> Node:
    node: Node = NodeFactory.create()
    for i in range(MAX_PAGE_SIZE + 1):
        ClProtocolFactory(cl_protocol_name=f'{i}', node=node)
    session.commit()
    return node


@pytest.fixture
def node_with_inducts(session: Session) -> Node:
    node: Node = NodeFactory.create()
    InductFactory(node=node)
    InductFactory(node=node)
    session.commit()
    return node


@pytest.fixture
def node_max_and_one_inducts(session: Session) -> Node:
    node: Node = NodeFactory.create()
    for _ in range(MAX_PAGE_SIZE + 1):
        InductFactory(node=node)
    session.commit()
    return node


@pytest.fixture
def node_with_seats(session: Session) -> Node:
    node: Node = NodeFactory.create()
    SeatFactory(node=node)
    SeatFactory(node=node)
    session.commit()
    return node


@pytest.fixture
def node_max_and_one_seats(session: Session) -> Node:
    node: Node = NodeFactory.create()
    for _ in range(MAX_PAGE_SIZE + 1):
        SeatFactory(node=node)
    session.commit()
    return node


@pytest.fixture
def node_without_operator_on_host_with_operator(session: Session) -> Node:
    """A node following the Allocator -> Node policy, but on a host
    underneath an operator.
    """
    n = NodeFactory()
    n.operator_id = None
    session.commit()
    return n


@pytest.fixture
def node_with_inducts_seats(session: Session) -> Node:
    """Node with seat_ip's and induct_ip's that are associated with a
    destination and a link on a host.
    """
    node: Node = NodeFactory.create()
    link: Link = LinkFactory.create(
        host=node.host, direction=CommDirectionEnumInternal.FULL_DUPLEX
    )
    for _ in range(2):
        cl_protocol: ClProtocol = ClProtocolFactory.create(
            node=node, cl_protocol_name=generate_cl_protocol_name(only_ip=True)
        )
        induct: Induct = InductFactory.create(
            node=node, cl_protocol=cl_protocol, induct_ip=True
        )
        InductIpFactory.create(induct=induct)
        seat_ip: SeatIp = SeatIpFactory.create(seat=SeatFactory(node=node))
        induct.links.append(link)
        seat_ip.seat.links.append(link)
    session.commit()
    return node


@pytest.fixture
def node_on_host_with_destination_and_link(session: Session) -> Node:
    """Node on a host with a destination and link."""
    host: Host = HostFactory.create()
    LinkFactory.create(host=host, direction=CommDirectionEnumInternal.FULL_DUPLEX)
    DestinationFactory.create(host=host)
    node: Node = NodeFactory.create(host=host)
    return node


@pytest.fixture
def node_with_ip_induct_seat_no_host(session: Session) -> Node:
    """Hostless node with an induct_ip and seat_ip."""
    node: Node = NodeFactory.create(host=None, operator=OperatorFactory.create())
    induct: Induct = InductFactory.create(
        node=node, type='ip', cl_protocol=None, induct_ip=True
    )
    InductIpFactory.create(induct=induct, destination=None)
    seat: Seat = SeatFactory.create(node=node, type='ip', seat_ip=True)
    SeatIpFactory.create(seat=seat, destination=None)
    session.commit()
    return node


@pytest.fixture
def node_with_ip_inducts_seats_links_host_same_ip(
    session: Session,
) -> tuple[Node, Host]:
    """2-tuple (node, host), where `node` has induct_ip's and seat_ip's
    (four each) with the following conditions:

    * Referencing a destination with ip_address with an equivalent
      record under `host`
    * Referencing a destination with registered_name with an equivalent
      record under `host`
    * Not referencing a destination
    * Referencing a destination with ip_address without an equivalent
      record under `host`

    The destinations used by the inducts are separate from the
    destinations used by the seats.

    The inducts and seats are associated with a link.
    """
    node: Node = NodeFactory.create()
    l1 = LinkFactory(direction=CommDirectionEnumInternal.FULL_DUPLEX, host=node.host)
    d1 = DestinationFactory.create(post__ip=True, host=node.host)
    d2 = DestinationFactory.create(post__name=True, host=node.host)
    d3 = DestinationFactory.create(post__ip=True, host=node.host)
    i1: Induct = InductFactory.create(
        node=node, type='ip', cl_protocol=None, induct_ip=True
    )
    i1.links.append(l1)
    i2: Induct = InductFactory.create(
        node=node, type='ip', cl_protocol=None, induct_ip=True
    )
    i2.links.append(l1)
    i3: Induct = InductFactory.create(
        node=node, type='ip', cl_protocol=None, induct_ip=True
    )
    i3.links.append(l1)
    i4: Induct = InductFactory.create(
        node=node, type='ip', cl_protocol=None, induct_ip=True
    )
    i4.links.append(l1)
    InductIpFactory.create(induct=i1, destination=d1)
    InductIpFactory.create(induct=i2, destination=d2)
    InductIpFactory.create(
        induct=i3, host_id=i3.host_id, destination_id=None, destination=None
    )
    InductIpFactory.create(induct=i4, destination=d3)
    d4 = DestinationFactory.create(post__ip=True, host=node.host)
    d5 = DestinationFactory.create(post__name=True, host=node.host)
    d6 = DestinationFactory.create(post__ip=True, host=node.host)
    s1: Seat = SeatFactory.create(node=node, type='ip', seat_ip=True)
    s1.links.append(l1)
    s2: Seat = SeatFactory.create(node=node, type='ip', seat_ip=True)
    s2.links.append(l1)
    s3: Seat = SeatFactory.create(node=node, type='ip', seat_ip=True)
    s3.links.append(l1)
    s4: Seat = SeatFactory.create(node=node, type='ip', seat_ip=True)
    s4.links.append(l1)
    SeatIpFactory.create(seat=s1, destination=d4)
    SeatIpFactory.create(seat=s2, destination=d5)
    SeatIpFactory.create(
        seat=s3,
        host_id=s3.host_id,
        destination_id=None,
        destination=None,
    )
    SeatIpFactory.create(seat=s4, destination=d6)

    host: Host = HostFactory.create()
    for d in (d1, d2, d4, d5):
        DestinationFactory.create(
            ip_address=d.ip_address, registered_name=d.registered_name, host=host
        )
    session.commit()
    return (node, host)


@pytest.fixture
def node_full_and_host(session: Session) -> tuple[Node, Host]:
    """2-tuple (node, host). `node` has IPN endpoints, IMC endpoints,
    CL protocols, and induct_ip's and seat_ip's (four each) with the
    following conditions:

    * Referencing a destination with ip_address with an equivalent
      record under `host`
    * Referencing a destination with registered_name with an equivalent
      record under `host`
    * Not referencing a destination
    * Referencing a destination with ip_address without an equivalent
      record under `host`

    The destinations used by the inducts are separate from the
    destinations used by the seats.

    The `seat` records also reference a LTP induct.

    The inducts (except for the LTP induct) and seats are associated
    with a link.
    """
    node: Node = NodeFactory.create()
    EndpointIMCFactory(node=node)
    EndpointIMCFactory(node=node)
    l1 = LinkFactory(direction=CommDirectionEnumInternal.FULL_DUPLEX, host=node.host)
    d1 = DestinationFactory.create(post__ip=True, host=node.host)
    d2 = DestinationFactory.create(post__name=True, host=node.host)
    d3 = DestinationFactory.create(post__ip=True, host=node.host)
    ltp_cl: ClProtocol = ClProtocolFactory.create(
        node=node,
        cl_protocol_name='ltp',
    )
    tcp_cl: ClProtocol = ClProtocolFactory.create(
        node=node,
        cl_protocol_name='tcp',
    )
    i1: Induct = InductFactory.create(
        node=node, type='ip', cl_protocol=tcp_cl, induct_ip=True
    )
    i1.links.append(l1)
    i2: Induct = InductFactory.create(
        node=node, type='ip', cl_protocol=tcp_cl, induct_ip=True
    )
    i2.links.append(l1)
    i3: Induct = InductFactory.create(
        node=node, type='ip', cl_protocol=tcp_cl, induct_ip=True
    )
    i3.links.append(l1)
    i4: Induct = InductFactory.create(
        node=node, type='ip', cl_protocol=tcp_cl, induct_ip=True
    )
    i4.links.append(l1)
    InductIpFactory.create(induct=i1, destination=d1)
    InductIpFactory.create(induct=i2, destination=d2)
    InductIpFactory.create(
        induct=i3, host_id=i3.host_id, destination_id=None, destination=None
    )
    InductIpFactory.create(induct=i4, destination=d3)
    i5: Induct = InductFactory.create(
        node=node, type=None, cl_protocol=ltp_cl, induct_ip=False
    )
    d4 = DestinationFactory.create(post__ip=True, host=node.host)
    d5 = DestinationFactory.create(post__name=True, host=node.host)
    d6 = DestinationFactory.create(post__ip=True, host=node.host)
    s1: Seat = SeatFactory.create(node=node, type='ip', seat_ip=True)
    s1.links.append(l1)
    s1.inducts.append(i5)
    s2: Seat = SeatFactory.create(node=node, type='ip', seat_ip=True)
    s2.links.append(l1)
    s2.inducts.append(i5)
    s3: Seat = SeatFactory.create(node=node, type='ip', seat_ip=True)
    s3.links.append(l1)
    s3.inducts.append(i5)
    s4: Seat = SeatFactory.create(node=node, type='ip', seat_ip=True)
    s4.links.append(l1)
    s4.inducts.append(i5)
    SeatIpFactory.create(seat=s1, destination=d4)
    SeatIpFactory.create(seat=s2, destination=d5)
    SeatIpFactory.create(
        seat=s3,
        host_id=s3.host_id,
        destination_id=None,
        destination=None,
    )
    SeatIpFactory.create(seat=s4, destination=d6)

    host: Host = HostFactory.create()
    for d in (d1, d2, d4, d5):
        DestinationFactory.create(
            ip_address=d.ip_address, registered_name=d.registered_name, host=host
        )
    session.commit()
    return (node, host)


@pytest.fixture
def node_with_contacts(session: Session) -> Node:
    """Node with 2 new contacts."""
    node = NodeFactory()
    c1 = ContactFactory()
    c2 = ContactFactory()
    session.add_all([c1, c2])
    session.commit()
    node.contacts.extend([c1, c2])
    session.commit()
    return node


@pytest.fixture
def node_max_contacts_and_one(session: Session) -> Node:
    node: Node = NodeFactory.create()
    contacts = []
    for _ in range(MAX_PAGE_SIZE + 1):
        contacts.append(ContactFactory())
    node.contacts.extend(contacts)
    session.commit()
    return node


@pytest.fixture
def nodes(session: Session) -> list[Node]:
    return [NodeFactory(), NodeFactory(), NodeFactory(), NodeFactory()]


@pytest.fixture
def nodes_max_and_one(session: Session) -> list[Node]:
    """List of nodes at the maximum amount per page plus one."""
    res = []
    for _ in range(MAX_PAGE_SIZE + 1):
        res.append(NodeFactory())
    return res


@pytest.fixture
def nodes_under_same_operator(session: Session, operator: Operator) -> list[Node]:
    """Nodes following Allocator -> Operator -> Node under same
    operator.
    """
    lower = operator.allocated_node_numbers[0].lower
    upper = operator.allocated_node_numbers[0].upper
    mid = lower + (upper - lower) // 2
    return [
        NodeFactory(
            operator=operator, host=HostFactory(operator=operator), node_number=lower
        ),
        NodeFactory(
            operator=operator, host=HostFactory(operator=operator), node_number=mid
        ),
    ]


@pytest.fixture
def nodes_under_same_host_and_operator_under_same_allocator(
    session: Session, host: Host
) -> tuple[Node, Node, Node, Node, Operator]:
    """Two nodes following Allocator -> Operator -> Node, and two nodes
    following Allocator -> Node, under the same host. And another
    operator under the same allocator.
    """
    lower = host.operator.allocated_node_numbers[0].lower
    upper = host.operator.allocated_node_numbers[0].upper
    mid = lower + (upper - lower) // 2
    n3: Node = NodeFactory.create(host=host, node_number=upper - 1)
    n3.operator_id = None
    n4: Node = NodeFactory.create(host=host, node_number=upper - 2)
    n4.operator_id = None
    session.commit()
    return (
        NodeFactory(host=host, node_number=lower),
        NodeFactory(host=host, node_number=mid),
        n3,
        n4,
        OperatorFactory(allocator=host.operator.allocator),
    )


@pytest.fixture
def nodes_different_policy_same_node_number(session: Session, node: Node) -> list[Node]:
    """List of nodes. The first node follows Allocator -> Operator ->
    Node, and the second follows Allocator -> Node. These nodes are
    under different allocators, and they have the same node_number.
    """
    n2 = NodeFactory()
    n2.operator_id = None
    session.commit()
    n2.node_number = node.node_number
    session.commit()
    return [node, n2]


@pytest.fixture
def endpoint_imc(session: Session) -> EndpointIMC:
    return EndpointIMCFactory()


@pytest.fixture
def cl_protocol(session: Session) -> ClProtocol:
    """A record in the `cl_protocol` table connected to a node."""
    return ClProtocolFactory()


@pytest.fixture
def cl_protocol_gibberish_name(session: Session) -> ClProtocol:
    """A `cl_protocol` record with a gibberish cl_protocol_name."""
    prefix = 'protocol'
    return ClProtocolFactory(
        cl_protocol_name=fake.unique.pystr(max_chars=15 - len(prefix), prefix=prefix)
    )


@pytest.fixture
def cl_protocols_for_known_cli_same_node(session: Session) -> list[ClProtocol]:
    """A list of cl_protocol records under the same node. The records
    have cl_protocol_name values that are needed by a well known CLI.
    """
    node: Node = NodeFactory.create()
    res = []
    for _, p_name in cli_command_with_required_protocol_name:
        res.append(
            ClProtocolFactory.create(
                node=node,
                cl_protocol_name=p_name,
                cl_protocol_class=known_cl_protocol_name_to_class[p_name],
            )
        )
    session.commit()
    return res


@pytest.fixture
def induct(session: Session) -> Induct:
    """An induct with a node and CL protocol.

    The induct is not guaranteed to have a `cli_command` that depends on
    the CL protocol since the CL protocol could be 'bibe'.
    """
    return InductFactory()


@pytest.fixture
def induct_null_type(session: Session) -> Induct:
    """A non-typed induct record in the parent table."""
    node: Node = NodeFactory.create()
    prefix = 'protocol'
    cl_protocol: ClProtocol = ClProtocolFactory.create(
        node=node,
        cl_protocol_name=fake.unique.pystr(max_chars=15 - len(prefix), prefix=prefix),
    )
    induct: Induct = InductFactory.create(
        node=node, cl_protocol=cl_protocol, induct_ip=False
    )
    return induct


@pytest.fixture
def induct_null_type_no_host(session: Session) -> Induct:
    """A non-typed induct on a hostless node."""
    node: Node = NodeFactory.create(host=None, operator=OperatorFactory.create())
    prefix = 'protocol'
    cl_protocol: ClProtocol = ClProtocolFactory.create(
        node=node,
        cl_protocol_name=fake.unique.pystr(max_chars=15 - len(prefix), prefix=prefix),
    )
    induct: Induct = InductFactory.create(
        node=node, cl_protocol=cl_protocol, induct_ip=False
    )
    return induct


@pytest.fixture
def induct_ltp_no_host(session: Session) -> Induct:
    """LTP induct on a hostless node."""
    node: Node = NodeFactory.create(host=None, operator=OperatorFactory.create())
    induct: Induct = InductFactory.create(
        node=node,
        cl_protocol=factory.SubFactory(
            ClProtocolFactory,
            cl_protocol_name='ltp',
            node=factory.SelfAttribute('..node'),
        ),
    )
    return induct


@pytest.fixture
def induct_ltp_on_host_with_links(session: Session) -> Induct:
    """An induct using ltpcli. The induct has no links, but is on a host
    with four links. None of the links are simplex (outgoing).
    """
    host: Host = HostFactory.create()
    l1 = LinkFactory(direction=CommDirectionEnumInternal.FULL_DUPLEX)
    l2 = LinkFactory(direction=CommDirectionEnumInternal.HALF_DUPLEX)
    l3 = LinkFactory(direction=CommDirectionEnumInternal.N_A)
    l4 = LinkFactory(direction=CommDirectionEnumInternal.SIMPLEX_IN)
    host.links.extend([l1, l2, l3, l4])
    session.flush()
    induct: Induct = InductFactory.create(
        node=NodeFactory(host=host),
        cl_protocol=factory.SubFactory(
            ClProtocolFactory,
            cl_protocol_name='ltp',
            node=factory.SelfAttribute('..node'),
        ),
    )
    return induct


@pytest.fixture
def induct_null_type_with_cl_protocols_for_known_cli(session: Session) -> Induct:
    """An induct without any CL protocol or CLI on a node with
    cl_protocols with cl_protocol_name values that are needed by a well
    known CLI.
    """
    node: Node = NodeFactory.create()
    res = []
    for _, p_name in cli_command_with_required_protocol_name:
        res.append(
            ClProtocolFactory.create(
                node=node,
                cl_protocol_name=p_name,
                cl_protocol_class=known_cl_protocol_name_to_class[p_name],
            )
        )
    session.commit()
    return InductFactory(node=node, cl_protocol=None)


@pytest.fixture
def induct_with_link_on_host_with_links(session: Session) -> Induct:
    """An induct with a single link that is on a host with four links.
    None of the links are simplex (outgoing).
    """
    host: Host = HostFactory.create()
    l1 = LinkFactory(direction=CommDirectionEnumInternal.FULL_DUPLEX)
    l2 = LinkFactory(direction=CommDirectionEnumInternal.HALF_DUPLEX)
    l3 = LinkFactory(direction=CommDirectionEnumInternal.N_A)
    l4 = LinkFactory(direction=CommDirectionEnumInternal.SIMPLEX_IN)
    host.links.extend([l1, l2, l3, l4])
    session.flush()
    induct: Induct = InductFactory.create(
        node=NodeFactory(host=host),
        cl_protocol=factory.SubFactory(
            ClProtocolFactory,
            cl_protocol_name=factory.LazyAttribute(
                lambda _: generate_cl_protocol_name(no_ltp=True)
            ),
            node=factory.SelfAttribute('..node'),
        ),
    )
    induct.links.append(l1)
    session.commit()
    return induct


@pytest.fixture
def induct_with_links(session: Session) -> Induct:
    """An induct with two links."""
    host: Host = HostFactory.create()
    links = []
    for _ in range(2):
        links.append(
            LinkFactory(
                direction=fake.random_element(
                    [
                        CommDirectionEnumInternal.FULL_DUPLEX,
                        CommDirectionEnumInternal.HALF_DUPLEX,
                        CommDirectionEnumInternal.N_A,
                        CommDirectionEnumInternal.SIMPLEX_IN,
                    ]
                ),
                host=host,
            )
        )
    session.flush()
    induct: Induct = InductFactory.create(
        node=NodeFactory(host=host),
        cl_protocol=factory.SubFactory(
            ClProtocolFactory,
            cl_protocol_name=factory.LazyAttribute(
                lambda _: generate_cl_protocol_name(no_ltp=True)
            ),
            node=factory.SelfAttribute('..node'),
        ),
    )
    induct.links.extend(links)
    session.commit()
    return induct


@pytest.fixture
def induct_null_type_on_host_with_links_simplex_outgoing_etc(
    session: Session,
) -> Induct:
    """A non-typed induct without any links on a host with at least two
    simplex outgoing links.
    """
    node: Node = NodeFactory.create()
    prefix = 'protocol'
    cl_protocol: ClProtocol = ClProtocolFactory.create(
        node=node,
        cl_protocol_name=fake.unique.pystr(max_chars=15 - len(prefix), prefix=prefix),
    )
    induct: Induct = InductFactory.create(
        node=node, cl_protocol=cl_protocol, induct_ip=False
    )
    links = []
    links.append(
        LinkFactory(direction=CommDirectionEnumInternal.SIMPLEX_OUT, host=node.host)
    )
    for _ in range(5):
        links.append(LinkFactory(host=node.host))
    links.append(
        LinkFactory(direction=CommDirectionEnumInternal.SIMPLEX_OUT, host=node.host)
    )
    session.commit()
    return induct


@pytest.fixture
def induct_max_and_one_links(session: Session) -> Induct:
    host: Host = HostFactory.create()
    links = []
    for _ in range(MAX_PAGE_SIZE + 1):
        links.append(
            LinkFactory(
                direction=fake.random_element(
                    [
                        CommDirectionEnumInternal.FULL_DUPLEX,
                        CommDirectionEnumInternal.HALF_DUPLEX,
                        CommDirectionEnumInternal.N_A,
                        CommDirectionEnumInternal.SIMPLEX_IN,
                    ]
                ),
                host=host,
            )
        )
    session.flush()
    induct: Induct = InductFactory.create(
        node=NodeFactory(host=host),
        cl_protocol=factory.SubFactory(
            ClProtocolFactory,
            cl_protocol_name=factory.LazyAttribute(
                lambda _: generate_cl_protocol_name(no_ltp=True)
            ),
            node=factory.SelfAttribute('..node'),
        ),
    )
    induct.links.extend(links)
    session.commit()
    return induct


@pytest.fixture
def induct_with_seat_on_node_with_seats(session: Session) -> Induct:
    """An LTP induct with a seat on a node with three other seats."""
    induct: Induct = InductFactory.create(
        cl_protocol=factory.SubFactory(
            ClProtocolFactory,
            cl_protocol_name='ltp',
            node=factory.SelfAttribute('..node'),
        ),
    )
    for _ in range(3):
        SeatFactory.create(node=induct.node)
    session.commit()
    return induct


@pytest.fixture
def induct_not_ltp_on_node_with_seats(session: Session) -> Induct:
    """A non-LTP induct on a node with seats."""
    induct: Induct = InductFactory.create(
        cl_protocol=factory.SubFactory(
            ClProtocolFactory,
            cl_protocol_name=factory.LazyAttribute(
                lambda _: generate_cl_protocol_name(no_ltp=True)
            ),
            node=factory.SelfAttribute('..node'),
        ),
    )
    for _ in range(3):
        SeatFactory.create(node=induct.node)
    session.commit()
    return induct


@pytest.fixture
def induct_with_seats(session: Session) -> Induct:
    """An LTP induct with two seats."""
    induct: Induct = InductFactory.create(
        cl_protocol=factory.SubFactory(
            ClProtocolFactory,
            cl_protocol_name='ltp',
            node=factory.SelfAttribute('..node'),
        ),
    )
    seats = []
    for _ in range(2):
        seats.append(SeatFactory.create(node=induct.node))
    induct.seats.extend(seats)
    session.commit()
    return induct


@pytest.fixture
def induct_max_and_one_seats(session: Session) -> Induct:
    induct: Induct = InductFactory.create(
        cl_protocol=factory.SubFactory(
            ClProtocolFactory,
            cl_protocol_name='ltp',
            node=factory.SelfAttribute('..node'),
        ),
    )
    seats = []
    for _ in range(MAX_PAGE_SIZE + 1):
        seats.append(SeatFactory.create(node=induct.node))
    induct.seats.extend(seats)
    session.commit()
    return induct


@pytest.fixture
def inducts_null_type_with_links(session: Session) -> tuple[Induct, Induct, Induct]:
    """Three inducts with null type on separate nodes associated with
    links.
    """
    res = []
    for _ in range(3):
        node: Node = NodeFactory.create()
        prefix = 'protocol'
        cl_protocol: ClProtocol = ClProtocolFactory.create(
            node=node,
            cl_protocol_name=fake.unique.pystr(
                max_chars=15 - len(prefix), prefix=prefix
            ),
        )
        induct: Induct = InductFactory.create(
            node=node, cl_protocol=cl_protocol, induct_ip=False
        )
        links = []
        for _ in range(2):
            links.append(
                LinkFactory(
                    direction=fake.random_element(
                        [
                            CommDirectionEnumInternal.FULL_DUPLEX,
                            CommDirectionEnumInternal.HALF_DUPLEX,
                            CommDirectionEnumInternal.N_A,
                            CommDirectionEnumInternal.SIMPLEX_IN,
                        ]
                    ),
                    host=node.host,
                )
            )
        session.flush()
        induct.links.extend(links)
        res.append(induct)
    session.commit()
    return res


@pytest.fixture
def induct_ip(session: Session) -> InductIp:
    """An induct_ip connnected to an induct (which has a node and CL
    protocol) and a destination (connected to the host of the induct's
    node).

    The induct is guaranteed to have a `cli_command` that depends on
    the CL protocol since the `cli_command` will be 'brsscla',
    'dccpcli', 'dgrcli', 'stcpcli', 'tcpcli', or 'udpcli'.
    """
    return InductIpFactory()


@pytest.fixture
def seat(session: Session) -> Seat:
    """A seat on a node on a host."""
    return SeatFactory()


@pytest.fixture
def seat_no_host(session: Session) -> Seat:
    """A seat on a node without a host."""
    return SeatFactory(
        type=None, node=NodeFactory(host=None, operator=OperatorFactory())
    )


@pytest.fixture
def seat_null_type(session: Session) -> Seat:
    """A non-typed seat record in the parent table. The seat has a
    non-null host_id.
    """
    return SeatFactory(type=None)


@pytest.fixture
def seat_with_link_on_host_with_links(session: Session) -> Seat:
    """A seat with a single link that is on a host with four links.
    None of the links are simplex (outgoing).
    """
    host: Host = HostFactory.create()
    l1 = LinkFactory(direction=CommDirectionEnumInternal.FULL_DUPLEX)
    l2 = LinkFactory(direction=CommDirectionEnumInternal.HALF_DUPLEX)
    l3 = LinkFactory(direction=CommDirectionEnumInternal.N_A)
    l4 = LinkFactory(direction=CommDirectionEnumInternal.SIMPLEX_IN)
    host.links.extend([l1, l2, l3, l4])
    session.flush()
    seat: Seat = SeatFactory.create(node=NodeFactory(host=host))
    seat.links.append(l1)
    session.commit()
    return seat


@pytest.fixture
def seat_on_host_with_links_simplex_outgoing_etc(session: Session) -> Seat:
    """A seat without any links on a host with at least two simplex
    outgoing links.
    """
    node: Node = NodeFactory.create()
    seat: Seat = SeatFactory.create(node=node)
    links = []
    links.append(
        LinkFactory(direction=CommDirectionEnumInternal.SIMPLEX_OUT, host=node.host)
    )
    for _ in range(5):
        links.append(LinkFactory(host=node.host))
    links.append(
        LinkFactory(direction=CommDirectionEnumInternal.SIMPLEX_OUT, host=node.host)
    )
    session.commit()
    return seat


@pytest.fixture
def seat_with_links(session: Session) -> Seat:
    """A seat with two links."""
    host: Host = HostFactory.create()
    links = []
    for _ in range(2):
        links.append(
            LinkFactory(
                direction=fake.random_element(
                    [
                        CommDirectionEnumInternal.FULL_DUPLEX,
                        CommDirectionEnumInternal.HALF_DUPLEX,
                        CommDirectionEnumInternal.N_A,
                        CommDirectionEnumInternal.SIMPLEX_IN,
                    ]
                ),
                host=host,
            )
        )
    session.flush()
    seat: Seat = SeatFactory.create(node=NodeFactory(host=host))
    seat.links.extend(links)
    session.commit()
    return seat


@pytest.fixture
def seat_max_and_one_links(session: Session) -> Seat:
    host: Host = HostFactory.create()
    links = []
    for _ in range(MAX_PAGE_SIZE + 1):
        links.append(
            LinkFactory(
                direction=fake.random_element(
                    [
                        CommDirectionEnumInternal.FULL_DUPLEX,
                        CommDirectionEnumInternal.HALF_DUPLEX,
                        CommDirectionEnumInternal.N_A,
                        CommDirectionEnumInternal.SIMPLEX_IN,
                    ]
                ),
                host=host,
            )
        )
    session.flush()
    seat: Seat = SeatFactory.create(node=NodeFactory(host=host))
    seat.links.extend(links)
    session.commit()
    return seat


@pytest.fixture
def seats(session: Session) -> list[Seat]:
    return [SeatFactory(), SeatFactory(), SeatFactory()]


@pytest.fixture
def seats_not_ip_with_links(session: Session) -> list[Seat]:
    res = []
    for _ in range(3):
        host: Host = HostFactory.create()
        links = []
        for _ in range(2):
            links.append(
                LinkFactory(
                    direction=fake.random_element(
                        [
                            CommDirectionEnumInternal.FULL_DUPLEX,
                            CommDirectionEnumInternal.HALF_DUPLEX,
                            CommDirectionEnumInternal.N_A,
                            CommDirectionEnumInternal.SIMPLEX_IN,
                        ]
                    ),
                    host=host,
                )
            )
        session.flush()
        seat: Seat = SeatFactory.create(node=NodeFactory(host=host), seat_ip=True)
        seat.links.extend(links)
        session.commit()
        res.append(seat)
    return res


@pytest.fixture
def seat_ip(session: Session) -> SeatIp:
    """seat_ip record connected to a seat."""
    return SeatIpFactory()

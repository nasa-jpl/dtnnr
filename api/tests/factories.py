from __future__ import annotations

import ipaddress
import random
from collections import OrderedDict

import factory
from factory.alchemy import SQLAlchemyModelFactory
from faker import Faker
from faker.exceptions import UniquenessException
from sqlalchemy.dialects.postgresql import Range

from app.models import (
    Allocator,
    Band,
    ClProtocol,
    CommDirectionEnumInternal,
    Contact,
    ContactPhoneNumber,
    Destination,
    EndpointIMC,
    EndpointIPN,
    Host,
    Induct,
    InductIp,
    Link,
    LinkRf,
    NewlineEnum,
    Node,
    Operator,
    Seat,
    SeatIp,
    UnderlyingCommunicationService,
    default_bands,
    default_underlying_communication_services,
    known_cl_protocol_name_to_class,
)

from .database import scoped_session_for_testing

fake = Faker()

UNDERLYING_COMMUNICATION_SERVICE_ID_DEFAULT_MIN = 1
UNDERLYING_COMMUNICATION_SERVICE_ID_DEFAULT_MAX = len(
    default_underlying_communication_services
)
BAND_ID_DEFAULT_MIN = 1
BAND_ID_DEFAULT_MAX = len(default_bands)


class BaseFactory(SQLAlchemyModelFactory):
    class Meta:
        abstract = True
        sqlalchemy_session = scoped_session_for_testing
        sqlalchemy_session_persistence = 'commit'


class UniqueFaker(factory.Faker):
    """Uses the .unique attribute on factory.Faker to generate unique
    values.

    From
    https://github.com/FactoryBoy/factory_boy/pull/820#issuecomment-1004802669
    """

    @classmethod
    def _get_faker(cls, locale=None):
        return super()._get_faker(locale=locale).unique


class PhoneNumberFactory(BaseFactory):
    class Meta:
        model = ContactPhoneNumber

    order_pos = factory.Sequence(lambda n: n)
    # phone_number can be any non-blank string
    phone_number = factory.Faker('phone_number')

    contact = factory.SubFactory('tests.factories.ContactFactory', phone_numbers=[])


class ContactFactory(BaseFactory):
    class Meta:
        model = Contact

    contact_name = factory.Faker('name')
    email = factory.Faker('email')

    phone_numbers = factory.RelatedFactoryList(
        PhoneNumberFactory, 'contact', size=lambda: random.randint(1, 3)
    )

    @factory.post_generation
    def allocators(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        self.allocators.append(*extracted)

    @factory.post_generation
    def operators(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        self.operators.append(*extracted)

    @factory.post_generation
    def hosts(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        self.hosts.append(*extracted)

    @factory.post_generation
    def nodes(self, create, extracted, **kwargs):
        if not create or not extracted:
            return

        self.nodes.append(*extracted)

    @factory.post_generation
    def reset_phone_number_counter(self, create, extracted, **kwargs):
        if not create:
            return
        PhoneNumberFactory.reset_sequence(0)


class AllocatorFactory(BaseFactory):
    class Meta:
        model = Allocator

    # factory.Sequence() starts at 0, but that's used by Default Allocator
    allocator_id = factory.Sequence(lambda n: n + 1)
    allocator_name = factory.Faker('catch_phrase')

    operators = factory.RelatedFactoryList(
        'tests.factories.OperatorFactory', 'allocator', size=0
    )
    nodes = factory.RelatedFactoryList(
        'tests.factories.NodeFactory', 'allocator', size=0
    )


class OperatorFactory(BaseFactory):
    """Creates an Operator under a new Allocator with 10 allocated node numbers."""

    class Meta:
        model = Operator

    operator_name = factory.Faker('bs')
    # For every new operator, we'll just give them 10 node numbers that haven't
    # been given out by any allocator so far.
    allocated_node_numbers = factory.Sequence(
        lambda n: [Range(n * 10, (n + 1) * 10, bounds='[)')]
    )

    allocator = factory.SubFactory(AllocatorFactory, operators=[])
    hosts = factory.RelatedFactoryList(
        'tests.factories.HostFactory', 'operator', size=0
    )
    nodes = factory.RelatedFactoryList(
        'tests.factories.NodeFactory', 'operator', size=0
    )


class HostFactory(BaseFactory):
    """By default, creates a Host under a new Operator."""

    class Meta:
        model = Host

    hostname = factory.Faker('hostname')
    host_description = factory.Faker('catch_phrase')
    # https://sanaregistry.org/r/spacecraftid/
    # VERSION 4 RANGE: SCID = [0x0000 – 0xFFFF]
    sana_scid = factory.Faker('random_int', min=0, max=65535)
    # Just made up a distribution, no idea what it actually is
    word_size = factory.Faker(
        'random_element',
        elements=OrderedDict([(64, 0.9), (32, 0.1)]),
    )
    newline = factory.Faker(
        'random_element', elements=[None] + [e.value for e in NewlineEnum]
    )

    operator = factory.SubFactory(OperatorFactory, hosts=[])
    destinations = factory.RelatedFactoryList(
        'tests.factories.DestinationFactory', 'host', size=1
    )
    nodes = factory.RelatedFactoryList('tests.factories.NodeFactory', 'host', size=0)
    links = factory.RelatedFactoryList('tests.factories.LinkFactory', 'host', size=0)


_ips = (ipaddress.ip_address('0.0.0.0'), ipaddress.ip_address('::'), None)


class DestinationFactory(BaseFactory):
    class Meta:
        model = Destination

    ip_address = factory.Faker('random_element', elements=_ips)
    """Do not use '0.0.0.0' or '::'. These are used by the factory to
    generate random IPv4 and IPv6 addresses, so if you use those values,
    they will be replaced.
    """

    host = factory.SubFactory(HostFactory, destinations=[])

    @factory.lazy_attribute
    def registered_name(self):
        if self.ip_address is None:
            return fake.unique.domain_name()
        return None

    @factory.post_generation
    def post(self, create, extracted, **kwargs):
        """Send a truthy value for post__ip to force a random IP
        address. Send a truthy value for post__name to force a random
        domain name. (post__name trumps post__ip)
        """
        if self.ip_address in _ips[: _ips.index(None)]:
            if self.ip_address.version == 4:
                self.ip_address = ipaddress.ip_address(fake.unique.ipv4_public())
            else:
                self.ip_address = ipaddress.ip_address(fake.unique.ipv6())
        if kwargs.get('ip') and self.ip_address is None:
            self.registered_name = None
            if random.choice([True, False]):
                self.ip_address = ipaddress.ip_address(fake.unique.ipv4_public())
            else:
                self.ip_address = ipaddress.ip_address(fake.unique.ipv6())
        if kwargs.get('name'):
            self.ip_address = None
            self.registered_name = fake.unique.domain_name()
        scoped_session_for_testing.commit()


class UnderlyingCommunicationServiceFactory(BaseFactory):
    class Meta:
        model = UnderlyingCommunicationService

    underlying_communication_service_name = factory.Sequence(
        lambda n: f'underlying_communication_service{n}'
    )


class LinkFactory(BaseFactory):
    class Meta:
        model = Link

    direction = factory.Faker(
        'random_element', elements=[e.value for e in CommDirectionEnumInternal]
    )
    host = factory.SubFactory(HostFactory, links=[])


class BandFactory(BaseFactory):
    class Meta:
        model = Band

    band_name = factory.Sequence(lambda n: f'band{n}')


class LinkRfFactory(BaseFactory):
    class Meta:
        model = LinkRf

    link = factory.SubFactory(LinkFactory, type='rf')
    band = factory.SubFactory(BandFactory, links=[])


class NodeFactory(BaseFactory):
    """A node that follows the Allocator -> Operator -> Node policy.
    Has the same operator as its host.
    """

    class Meta:
        model = Node

    sdr_config_flags = factory.Faker('random_int', min=1, max=15)
    # These 3 are the default values as described in ionconfig
    sdr_wm_size = 1000000
    heap_words = 250000
    wm_size = 5000000
    node_name = factory.Faker('domain_word')

    # Always create a host
    host = factory.SubFactory(HostFactory, nodes=[])
    # node.operator == host.operator
    operator = factory.SelfAttribute('host.operator')
    # node.allocator == node.operator.allocator
    allocator = factory.SelfAttribute('operator.allocator')
    ipn_endpoints = factory.RelatedFactoryList(
        'tests.factories.EndpointIPNFactory', 'node', size=3
    )
    imc_endpoints = factory.RelatedFactoryList(
        'tests.factories.EndpointIMCFactory', 'node', size=0
    )
    cl_protocols = factory.RelatedFactoryList(
        'tests.factories.ClProtocolFactory', 'node', size=0
    )
    inducts = factory.RelatedFactoryList(
        'tests.factories.InductFactory', 'node', size=0
    )
    seats = factory.RelatedFactoryList('tests.factories.SeatFactory', 'node', size=0)

    @factory.lazy_attribute
    def node_number(self):
        """Generate a random node number within the node's operator's
        allocated_node_numbers.
        """
        min = self.operator.allocated_node_numbers[0].lower
        max = self.operator.allocated_node_numbers[0].upper
        # random_int() generates a random integer between min and max inclusive
        return fake.unique.random_int(min=min, max=max - 1)

    @factory.post_generation
    def ipn_endpoints_constant(self, create, extracted, **kwargs):
        if not create:
            return

        # RelatedFactoryList(..., size=3) already created 3 random endpoints,
        # We create an additional 4 endpoints that nodes from this factory
        # always have.
        EndpointIPNFactory(service_number=3, application='bpecho', node=self)
        EndpointIPNFactory(service_number=65, application='cfdp', node=self)
        EndpointIPNFactory(service_number=99, application='bssp', node=self)
        EndpointIPNFactory(service_number=127, application='lgagent', node=self)


class EndpointIPNFactory(BaseFactory):
    class Meta:
        model = EndpointIPN

    # https://www.rfc-editor.org/rfc/rfc7116.html#page-7
    # Unassigned is [3, 63] union [1024, 2^16 - 1]
    # We'll just do [128, 2^16 - 1] to avoid potential conflicts from the
    # predefined endpoints added in NodeFactory()
    service_number = UniqueFaker('random_int', min=128, max=(2**16) - 1)
    disposition = factory.Faker('random_element', elements=('q', 'x'))
    application = factory.Faker(
        'random_element',
        elements=(
            # Not sure if you can actually put all of these on endpoints
            # or if they're actually valid application names, no matter
            'bpdriver',
            'bpcounter',
            'bpsource',
            'bpsink',
            'bpsendfile',
            'bprecvfile',
        ),
    )

    node = factory.SubFactory(NodeFactory, ipn_endpoints=[])


class EndpointIMCFactory(BaseFactory):
    class Meta:
        model = EndpointIMC

    # [128, 2^16 - 1] is arbitrary; there's little written about IMC so it doesn't
    # matter what we choose here. Choosing smaller numbers is nice if we serialize
    # numbers as int and strings.
    group_number = UniqueFaker('random_int', min=128, max=(2**16) - 1)
    disposition = factory.Faker('random_element', elements=('q', 'x'))
    application = factory.Faker(
        'random_element',
        elements=(
            # Not sure if you can actually put all of these on endpoints
            # or if they're actually valid application names, no matter
            'bpdriver',
            'bpcounter',
            'bpsource',
            'bpsink',
            'bpsendfile',
            'bprecvfile',
        ),
    )

    node = factory.SubFactory(NodeFactory, imc_endpoints=[])


def generate_cl_protocol_name(only_ip=False, no_ltp=False) -> str:
    try:
        e = ['brss', 'dccp', 'dgr', 'stcp', 'tcp', 'udp']
        if not only_ip:
            e.extend(['bibe', 'brsc', 'bssp'])
            if not no_ltp:
                e.append('ltp')
        return fake.unique.random_element(elements=tuple(e))
    except UniquenessException:
        prefix = 'protocol'
        return fake.unique.pystr(max_chars=15 - len(prefix), prefix=prefix)


class ClProtocolFactory(BaseFactory):
    """Create a record in the `cl_protocol` associated with a node."""

    class Meta:
        model = ClProtocol

    cl_protocol_name = factory.LazyAttribute(lambda _: generate_cl_protocol_name())

    node = factory.SubFactory(NodeFactory, cl_protocols=[])

    @factory.lazy_attribute
    def cl_protocol_class(self):
        return known_cl_protocol_name_to_class.get(self.cl_protocol_name, 8)


class InductFactory(BaseFactory):
    class Meta:
        model = Induct

    host_id = factory.SelfAttribute('node.host_id')

    node = factory.SubFactory(NodeFactory, inducts=[])
    cl_protocol = factory.SubFactory(
        ClProtocolFactory, node=factory.SelfAttribute('..node')
    )

    @factory.lazy_attribute
    def type(self):
        if self.cl_protocol and self.cl_protocol.cl_protocol_name in (
            'brss',
            'dccp',
            'dgr',
            'stcp',
            'tcp',
            'udp',
        ):
            return 'ip'
        return None

    @factory.lazy_attribute
    def cli_command(self):
        if not self.cl_protocol:
            return None
        p = self.cl_protocol.cl_protocol_name
        if p in ('brsc', 'brss'):
            return f'{p}cla'
        return f'{p}cli'

    @factory.lazy_attribute
    def uses_ltp(self):
        if not self.cl_protocol:
            return False
        return self.cl_protocol.cl_protocol_name == 'ltp'

    @factory.post_generation
    def induct_ip(obj, create, extracted, **kwargs):
        # Pass a truthy value for `extracted` to prevent creating an induct_ip
        if not create or extracted:
            return
        if obj.type == 'ip':
            if obj.host_id is None:
                InductIpFactory.create(induct=obj, destination=None)
            else:
                InductIpFactory.create(induct=obj)

    # TODO: can do post_generation with links here


class InductIpFactory(BaseFactory):
    class Meta:
        model = InductIp

    port_number = factory.Faker('random_int', min=0, max=(2**16) - 1)

    induct = factory.SubFactory(
        InductFactory,
        # Need to use a CL protocol with a CLI that uses ip:port
        cl_protocol=factory.SubFactory(
            ClProtocolFactory,
            cl_protocol_name=factory.LazyAttribute(
                lambda _: generate_cl_protocol_name(only_ip=True)
            ),
            node=factory.SelfAttribute('..node'),
        ),
        induct_ip=True,
    )
    destination = factory.SubFactory(
        DestinationFactory, host=factory.SelfAttribute('..induct.node.host')
    )


class SeatFactory(BaseFactory):
    class Meta:
        model = Seat

    type = 'ip'
    host_id = factory.SelfAttribute('node.host_id')
    lsi_command = factory.Faker(
        'random_element', elements=['udplsi', 'dccplsi', 'customlsi']
    )

    node = factory.SubFactory(NodeFactory, seats=[])

    @factory.post_generation
    def seat_ip(obj, create, extracted, **kwargs):
        # Pass a truthy value for `extracted` to prevent creating an seat_ip
        if not create or extracted:
            return
        if obj.type == 'ip':
            if obj.host_id is None:
                SeatIpFactory.create(seat=obj, destination=None)
            else:
                SeatIpFactory.create(seat=obj)


class SeatIpFactory(BaseFactory):
    class Meta:
        model = SeatIp

    port_number = factory.Faker('random_int', min=0, max=(2**16) - 1)

    seat = factory.SubFactory(SeatFactory)
    destination = factory.SubFactory(
        DestinationFactory, host=factory.SelfAttribute('..seat.node.host')
    )

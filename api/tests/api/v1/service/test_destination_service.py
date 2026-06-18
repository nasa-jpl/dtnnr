from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import exc

from tests.util import get_as_jsonb

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import Destination, Host, InductIp, SeatIp


def test_get(session: Session, destination_ip: Destination):
    from app.api.v1.destination.service import get

    t_destination = get(session, destination_ip.destination_id)
    assert destination_ip == t_destination


def test_get_by_host_id_and_ip_address(session: Session, destination_ip: Destination):
    from app.api.v1.destination.service import get_by_host_id_and_ip_address

    t_destination = get_by_host_id_and_ip_address(
        session, destination_ip.host_id, destination_ip.ip_address
    )
    assert destination_ip == t_destination


def test_get_by_host_id_and_registered_name(
    session: Session, destination_name: Destination
):
    from app.api.v1.destination.service import get_by_host_id_and_registered_name

    t_destination = get_by_host_id_and_registered_name(
        session, destination_name.host_id, destination_name.registered_name
    )
    assert destination_name == t_destination


def test_list_destinations(session: Session, host_with_destinations: Host):
    from app.api.v1.destination.service import list_destinations

    host = host_with_destinations
    destinations = []
    page = list_destinations(session, host.host_id, 1, None)
    destinations.extend([_ for (_,) in page])
    while page.paging.has_next:
        page = list_destinations(session, host.host_id, 1, page.paging.bookmark_next)
        destinations.extend([_ for (_,) in page])

    for d in host.destinations:
        assert d in destinations


def test_create(session: Session, host: Host):
    from app.api.v1.destination.service import create

    # Factory for destination uses Faker's ipv4_public(), so shouldn't
    # be violating unique constraint if we use private address (host fixture
    # uses the destination factory)
    ip_str = '192.168.10.10'
    # We can insert using a string
    t_destination: Destination = create(session, host.host_id, ip_address=ip_str)
    # But it isn't stored as a string, so we need str(). This is better than
    # using ip_interface(ip_str) as that adds /32 to ip_str while the record
    # isn't stored with the subnet mask (and so, not equal)
    assert str(t_destination.ip_address) == ip_str
    assert t_destination.registered_name is None
    assert t_destination.host == host

    # Unique constraint violation
    with pytest.raises(exc.IntegrityError):
        create(session, host.host_id, ip_address=ip_str)
    session.rollback()

    # Can pass a IPv4Address
    t_ipv4 = ipaddress.ip_address('192.168.10.11')
    t_destination = create(session, host.host_id, ip_address=t_ipv4)
    assert t_destination.ip_address == t_ipv4
    assert t_destination.registered_name is None
    assert t_destination.host == host

    # If /32, Postgres doesn't treat the value as indicating a subnet, instead
    # as a single host, so this violates unique constraint
    with pytest.raises(exc.IntegrityError):
        create(session, host.host_id, f'{ip_str}/32')
    session.rollback()

    # IPv6 addresses get shortened
    ip_str = '2001:0db8:0000:0000:0000:ff00:0042:8329'
    t_destination = create(session, host.host_id, ip_address=ip_str)
    assert str(t_destination.ip_address) != ip_str  # not equal
    assert t_destination.registered_name is None
    assert t_destination.host == host

    # Can pass a IPv6Address
    t_ipv6 = ipaddress.ip_address('::1')
    t_destination = create(session, host.host_id, ip_address=t_ipv6)
    assert t_destination.ip_address == t_ipv6
    assert t_destination.registered_name is None
    assert t_destination.host == host

    # IPv6 also has similar subnet mask rule
    ip_str = '2001:db8::ff00:42:8329/128'
    with pytest.raises(exc.IntegrityError):
        t_destination = create(session, host.host_id, ip_address=ip_str)
    session.rollback()

    with pytest.raises(exc.DataError):
        create(session, host.host_id, ip_address='not a valid address')
    session.rollback()

    # Registered name
    name = 'example.com'
    t_destination = create(session, host.host_id, registered_name=name)
    assert t_destination.ip_address is None
    assert t_destination.registered_name == name


def test_update(
    session: Session, destination_ip: Destination, destination_name: Destination
):
    from app.api.v1.destination.service import update

    # Private IP address is guaranteed to be different than existing value since
    # DestinationFactory only generates public addresses.
    new_ip_str = '10.1.2.3'
    t_dest = update(session, destination_ip.destination_id, ip_address=new_ip_str)
    assert t_dest == destination_ip
    assert str(t_dest.ip_address) == new_ip_str

    # Can pass IPv4Address and IPv6Address
    ipv4 = ipaddress.ip_address('192.168.1.1')
    t_dest = update(session, destination_ip.destination_id, ip_address=ipv4)
    assert t_dest == destination_ip
    assert t_dest.ip_address == ipv4

    ipv6 = ipaddress.ip_address('::1')
    t_dest = update(session, destination_ip.destination_id, ip_address=ipv6)
    assert t_dest == destination_ip
    assert t_dest.ip_address == ipv6

    # DestinationFactory generates domain names at one subdomain level, so use
    # more levels to guarantee a different value
    new_name = 'mail.example.com'
    t_dest = update(session, destination_name.destination_id, registered_name=new_name)
    assert t_dest == destination_name
    assert t_dest.registered_name == new_name

    # Change from IP to registered name
    t_dest = update(
        session,
        destination_ip.destination_id,
        ip_address=None,
        registered_name=new_name,
    )
    assert t_dest == destination_ip
    assert t_dest.ip_address is None
    assert t_dest.registered_name == new_name

    # Change from registered name to IP
    t_dest = update(
        session,
        destination_name.destination_id,
        ip_address=new_ip_str,
        registered_name=None,
    )
    assert t_dest == destination_name
    assert str(t_dest.ip_address) == new_ip_str
    assert t_dest.registered_name is None


def test_delete(
    session: Session, destination_ip: Destination, induct_ip: InductIp, seat_ip: SeatIp
):
    from sqlalchemy import select

    from app.api.v1.destination.service import delete, get
    from app.api.v1.induct.service import get as induct_get
    from app.api.v1.seat.service import get as seat_get
    from app.models import Destination
    from tests.util import verify_soft_deletion

    destination_id = destination_ip.destination_id
    jsonb = get_as_jsonb(
        session, select(Destination).where(Destination.destination_id == destination_id)
    )
    delete(session, destination_id)
    assert not get(session, destination_id)
    assert verify_soft_deletion(session, jsonb)

    destination_id = induct_ip.destination_id
    jsonb = get_as_jsonb(
        session, select(Destination).where(Destination.destination_id == destination_id)
    )
    delete(session, destination_id)
    assert not get(session, destination_id)
    assert verify_soft_deletion(session, jsonb)
    assert induct_get(session, induct_ip.induct_id)
    assert not induct_ip.destination_id

    destination_id = seat_ip.destination_id
    jsonb = get_as_jsonb(
        session, select(Destination).where(Destination.destination_id == destination_id)
    )
    delete(session, destination_id)
    assert not get(session, destination_id)
    assert verify_soft_deletion(session, jsonb)
    assert seat_get(session, seat_ip.seat_id)
    assert not seat_ip.destination_id

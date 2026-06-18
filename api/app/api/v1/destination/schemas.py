from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from litestar.params import Parameter
from msgspec import UNSET, Meta

from app.fields import DESTINATION_ID_MAX
from app.schemas import (
    BaseStruct,
    nonnegative_bigint_pathparam_schema_extra,
    nonnegative_bigint_reqbody_extra_json_schema,
)

from ..host.schemas import HostIDMeta

if TYPE_CHECKING:
    from app.models import Destination

DestinationIDMeta = Meta(
    ge=0,
    le=DESTINATION_ID_MAX,
    title='Destination ID',
    description='Surrogate key to identify a destination',
    examples=['152'],
    extra_json_schema=nonnegative_bigint_reqbody_extra_json_schema,
)

DestinationIDParam = Parameter(
    ge=DestinationIDMeta.ge,
    le=DestinationIDMeta.le,
    title=DestinationIDMeta.title,
    description=DestinationIDMeta.description,
    schema_extra=nonnegative_bigint_pathparam_schema_extra,
)

IPAddressMeta = Meta(
    title='IP Address',
    description='IPv4 or IPv6 adddress. Inputs are checked for errors.',
    examples=['192.0.2.1', '3fff::61:5403:4884:221:816'],
)

RegisteredNameMeta = Meta(
    title='Registered Name',
    description='A sequence of characters usually intended for lookup within a'
    ' locally defined host or service name registry.',
    examples=['destination.example'],
)

DestinationValueMeta = Meta(
    title='Destination Value',
    description=(
        'An IP address or a sequence of characters intended for lookup within a'
        ' locally defined host or a service name registry that resolves to an'
        ' IP address.'
    ),
    examples=['192.0.2.1', '3fff::61:5403:4884:221:816', 'destination.example'],
)

IPQueryParam = Parameter(
    title='IP',
    description=(
        'If `true`, the `destination_value` in the representation will be validated'
        ' as an IP address. Note that this only controls validation. If the'
        ' `destination_value` can be parsed as an IP address, it will be parsed'
        ' as such. For example, the IPv6 address'
        ' <i>3fff:0000:0000:0061:5403:4884:0221:0816</i> will be stored in its'
        ' canonical format as <i>3fff::61:5403:4884:221:816</i> regardless of the'
        ' value of this query parameter. `false` by default.'
    ),
)


def process_destination_value(destination: Destination) -> str | None:
    """Returns either registered_name or ip_address."""
    if destination.ip_address is None:
        return destination.registered_name
    return str(destination.ip_address)


def to_destination_schema(destination: Destination) -> DestinationSchema:
    return DestinationSchema(
        destination_id=str(destination.destination_id),
        host_id=str(destination.host_id),
        destination_value=process_destination_value(destination),
    )


def to_destination_without_host_id_schema(
    destination: Destination,
) -> DestinationWithoutHostIdSchema:
    return DestinationWithoutHostIdSchema(
        destination_id=str(destination.destination_id),
        destination_value=process_destination_value(destination),
    )


class DestinationWithoutHostIdSchema(BaseStruct):
    """Representation of a destination in responses where host_id is
    redundant.
    """

    destination_id: Annotated[
        str,
        Meta(
            title=DestinationIDMeta.title,
            description=DestinationIDMeta.description,
            examples=DestinationIDMeta.examples,
        ),
    ]
    destination_value: Annotated[
        str,
        Meta(
            title='Destination Value',
            description='IP address or registered name that resolves to an IP address'
            ' associated with an interface on a host',
            examples=IPAddressMeta.examples + RegisteredNameMeta.examples,
        ),
    ]


class DestinationSchema(DestinationWithoutHostIdSchema):
    """Representation of a destination in responses."""

    host_id: Annotated[
        str,
        Meta(
            title=HostIDMeta.title,
            description=HostIDMeta.description,
            examples=HostIDMeta.examples,
        ),
    ]


class DestinationCreateSchema(BaseStruct):
    """Specifies the request body for creating a destination."""

    destination_value: Annotated[str, DestinationValueMeta]


class DestinationUpdateSchema(BaseStruct):
    """Specifies the request body for updating a destination."""

    destination_value: Annotated[str, DestinationValueMeta] = UNSET

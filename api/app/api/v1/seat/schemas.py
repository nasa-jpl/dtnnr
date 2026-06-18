from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from litestar.openapi.spec import Example, Schema
from litestar.params import Body, Parameter
from msgspec import Meta

from app.fields import SEAT_ID_MAX
from app.schemas import (
    JSON_NULL,
    BaseStruct,
    nonnegative_bigint_pathparam_schema_extra,
    nonnegative_bigint_reqbody_extra_json_schema,
    nullable_nonnegative_bigint_reqbody_extra_json_schema,
    string_or_null_extra_json_schema,
)

from ..destination.schemas import (
    DestinationIDMeta,
    DestinationValueMeta,
    DestinationWithoutHostIdSchema,
    process_destination_value,
    to_destination_without_host_id_schema,
)
from ..induct.schemas import PortNumberMeta as InductIPPortNumberMeta
from ..node.schemas import NodeIDMeta

if TYPE_CHECKING:
    from app.models import Seat, SeatIp

SeatIDMeta = Meta(
    ge=0,
    le=SEAT_ID_MAX,
    title='Seat ID',
    description='Surrogate key to identify a seat',
    examples=['412'],
    extra_json_schema=nonnegative_bigint_reqbody_extra_json_schema,
)

SeatIDParam = Parameter(
    ge=SeatIDMeta.ge,
    le=SeatIDMeta.le,
    title=SeatIDMeta.title,
    description=SeatIDMeta.description,
    schema_extra=nonnegative_bigint_pathparam_schema_extra,
)

PortNumberMeta = Meta(
    ge=InductIPPortNumberMeta.ge,
    le=InductIPPortNumberMeta.le,
    title=InductIPPortNumberMeta.title,
    description='Port number used by the LSI command',
    examples=[1113],
    extra_json_schema=InductIPPortNumberMeta.extra_json_schema,
)

LsiCommandFullMeta = Meta(
    title='LSI Command (full)',
    description=(
        'This values maps onto the "lsi_command" argument of the seat-related'
        ' commands listed in ltprc(5). The link service input program handles'
        " an incoming LTP data stream. The LTP segments are processed by ION's"
        ' LTP engine and handled by an LTP convergence layer input program. This'
        ' property includes the LSI program and all of its arguments.'
    ),
    examples=[
        f'udplsi {DestinationValueMeta.examples[0]}:{PortNumberMeta.examples[0]}'
    ],
    extra_json_schema=string_or_null_extra_json_schema,
)

LsiCommandRawMeta = Meta(
    title='LSI Command',
    description=(
        'This value is equivalent to `lsi_command_full` if the seat is not typed.'
        ' This is available to easily access the raw value that the seat uses;'
        ' for most purposes, you just want `lsi_command_full`.'
    ),
    # Our seat example is typed, so don't have the arguments
    examples=['udplsi'],
    extra_json_schema=string_or_null_extra_json_schema,
)


def to_seat_ip_schema(seat_ip: SeatIp) -> SeatIpSchema:
    return SeatIpSchema(
        destination=(
            None
            if seat_ip.destination is None
            else to_destination_without_host_id_schema(seat_ip.destination)
        ),
        port_number=seat_ip.port_number,
    )


class SeatIpSchema(BaseStruct):
    """Fields specific only to IP seats."""

    destination: DestinationWithoutHostIdSchema | None
    port_number: Annotated[
        int | None,
        Meta(
            title=PortNumberMeta.title,
            description=PortNumberMeta.description,
            examples=PortNumberMeta.examples,
        ),
    ]


def process_lsi_command(seat: Seat) -> str | None:
    if seat.seat_ip is None:
        return seat.lsi_command
    if seat.seat_ip.destination_id is not None:
        arg = process_destination_value(seat.seat_ip.destination)
        if seat.seat_ip.port_number is not None:
            arg += f':{seat.seat_ip.port_number}'
        return ' '.join([seat.lsi_command, arg])
    return seat.lsi_command


def to_seat_without_node_id_schema(seat: Seat) -> SeatWithoutNodeIdSchema:
    return SeatWithoutNodeIdSchema(
        seat_id=str(seat.seat_id),
        lsi_command_full=process_lsi_command(seat),
        lsi_command=seat.lsi_command,
        seat_ip=None if seat.seat_ip is None else to_seat_ip_schema(seat.seat_ip),
    )


class SeatWithoutNodeIdSchema(BaseStruct):
    """Representation of a seat in responses where node_id is redudnant."""

    seat_id: Annotated[
        str,
        Meta(
            title=SeatIDMeta.title,
            description=SeatIDMeta.description,
            examples=SeatIDMeta.examples,
        ),
    ]
    lsi_command_full: Annotated[str | None, LsiCommandFullMeta]
    lsi_command: Annotated[str | None, LsiCommandRawMeta]
    seat_ip: SeatIpSchema


def to_seat_schema(seat: Seat) -> SeatSchema:
    return SeatSchema(
        seat_id=str(seat.seat_id),
        lsi_command_full=process_lsi_command(seat),
        lsi_command=seat.lsi_command,
        seat_ip=None if seat.seat_ip is None else to_seat_ip_schema(seat.seat_ip),
        node_id=str(seat.node_id),
    )


class SeatSchema(SeatWithoutNodeIdSchema):
    """Representation of a seat in responses."""

    node_id: Annotated[
        str,
        Meta(
            title=NodeIDMeta.title,
            description=NodeIDMeta.description,
            examples=NodeIDMeta.examples,
        ),
    ]


class SeatIpCreateSchema(BaseStruct):
    """Specifies the `seat_ip` object for `SeatCreateSchema`."""

    destination_id: Annotated[
        Annotated[int, Meta(ge=DestinationIDMeta.ge, le=DestinationIDMeta.le)] | None,
        Meta(
            title=DestinationIDMeta.title,
            description=DestinationIDMeta.description,
            examples=DestinationIDMeta.examples,
            extra_json_schema=nullable_nonnegative_bigint_reqbody_extra_json_schema,
        ),
    ] = JSON_NULL
    port_number: Annotated[
        Annotated[int, Meta(ge=PortNumberMeta.ge, le=PortNumberMeta.le)] | None,
        Meta(
            title=PortNumberMeta.title,
            description=PortNumberMeta.description,
            examples=PortNumberMeta.examples,
            extra_json_schema=PortNumberMeta.extra_json_schema,
        ),
    ] = JSON_NULL


SeatIpMeta = Meta(
    description=(
        '`seat_ip` describes the last argument to a LSI program where the argument'
        ' has the format "ip[:port]" and "ip" refers to a destination on the host.'
        ' When `seat_ip` is used, the `lsi_command` returned in representations'
        ' is the conatenation of the inputted `lsi_command` with ip[:port], so'
        ' do not repeat the ip[:port] argument in the inputted `lsi_command` or'
        ' the argument will be repeated in returned representations.'
    ),
    examples=[
        SeatIpCreateSchema(
            destination_id=DestinationIDMeta.examples[0],
            port_number=PortNumberMeta.examples[0],
        )
    ],
)


class SeatCreateSchema(BaseStruct):
    """Specifies the request body for creating a seat."""

    lsi_command: Annotated[
        str | None,
        Meta(
            title=LsiCommandFullMeta.title,
            description=LsiCommandFullMeta.description,
            examples=['udplsi'],
            extra_json_schema=string_or_null_extra_json_schema,
        ),
    ] = JSON_NULL
    seat_ip: Annotated[SeatIpCreateSchema | None, SeatIpMeta] = JSON_NULL

    def __post_init__(self):
        if self.lsi_command is JSON_NULL:
            self.lsi_command = None
        if self.seat_ip is JSON_NULL:
            self.seat_ip = None
        elif self.seat_ip is not None:
            if self.seat_ip.destination_id is JSON_NULL:
                self.seat_ip.destination_id = None
            if self.seat_ip.port_number is JSON_NULL:
                self.seat_ip.port_number = None


SEAT_WRITE_DESCRIPTION = (
    '`seat_ip` should only be used if you want `lsi_command_full` in returned'
    ' representations to end with an argument in the format "ip[:port]" where'
    ' "ip" is the destination value of a destination on a host. This comes with'
    ' benefits like avoiding typing an "ip" value that exactly matches the'
    ' destination, and updating `lsi_command_full` automatically when the destination'
    ' value changes. If the destination is deleted, then the returned'
    ' `lsi_command_full` in representations will be the regular `lsi_command` that was'
    f' requested. E.g., if destination ID {DestinationIDMeta.examples[0]} was'
    ' deleted, then the `lsi_command` would be "udplsi".<br />'
    '<br />'
    'An example with fake data: if the request body has "udplsi" as `lsi_command`,'
    f' {DestinationIDMeta.examples[0]} as `seat_ip.destination_id` (which'
    f' references a destination with the value "{DestinationValueMeta.examples[0]}"),'
    f' and {PortNumberMeta.examples[0]} as `seat_ip.port_number`, then the returned'
    f' `lsi_command_full` will be "udplsi {DestinationValueMeta.examples[0]}:'
    f'{PortNumberMeta.examples[0]}".<br />'
    '<br />'
    'If you want the seat to have a meaningful `lsi_command_full` in responses with'
    ' a hostless node, then you should input the whole command (program name'
    " with all of its arguments) in the request body's `lsi_command`."
)

SeatIDsReplaceBody = Body(
    schema_extra={
        'items': Schema(
            title=SeatIDMeta.title,
            description=SeatIDMeta.description,
            one_of=nonnegative_bigint_reqbody_extra_json_schema['extra']['oneOf'],
        )
    },
    examples=[Example(value=[int(i) for i in SeatIDMeta.examples])],
)

type SeatIDsReplaceSet = set[Annotated[int, Meta(ge=SeatIDMeta.ge, le=SeatIDMeta.le)]]

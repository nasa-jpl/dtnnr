from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Annotated

from litestar.openapi.spec import Example
from litestar.params import Body, Parameter
from msgspec import Meta

from app.fields import INDUCT_ID_MAX, PORT_NUMBER_MAX
from app.models import (
    cli_command_with_required_protocol_name,
    no_duct_name_known_cli_not_ip,
    no_uses_ltp_known_cli,
)
from app.schemas import (
    JSON_NULL,
    BaseStruct,
    nonnegative_bigint_pathparam_schema_extra,
    nonnegative_bigint_reqbody_extra_json_schema,
    nullable_nonnegative_bigint_reqbody_extra_json_schema,
    nullable_uint16_reqbody_extra_json_schema,
    string_or_null_extra_json_schema,
)

from ..allocator.schemas import AllocatorIDMeta
from ..cl_protocol.schemas import (
    ClProtocolClassPropertyMeta,
    ClProtocolIDMeta,
    ClProtocolNameMeta,
    ClProtocolWithoutNodeIdSchema,
    to_cl_protocol_without_node_id_schema,
)
from ..destination.schemas import (
    DestinationIDMeta,
    DestinationValueMeta,
    DestinationWithoutHostIdSchema,
    process_destination_value,
    to_destination_without_host_id_schema,
)
from ..node.schemas import NodeIDMeta, NodeNumberMeta

if TYPE_CHECKING:
    from app.models import Induct, InductIp

InductIDMeta = Meta(
    ge=0,
    le=INDUCT_ID_MAX,
    title='Induct ID',
    description='Surrogate key to identify an induct',
    examples=['105', '459'],
    extra_json_schema=nonnegative_bigint_reqbody_extra_json_schema,
)

InductIDParam = Parameter(
    ge=InductIDMeta.ge,
    le=InductIDMeta.le,
    title=InductIDMeta.title,
    description=InductIDMeta.description,
    schema_extra=nonnegative_bigint_pathparam_schema_extra,
)

PortNumberMeta = Meta(
    ge=0,
    le=PORT_NUMBER_MAX,
    title='Port Number',
    description='Port number used by the CLI command',
    examples=[4556],
    extra_json_schema=nullable_uint16_reqbody_extra_json_schema,
)

DuctNameResponseMeta = Meta(
    title='Duct Name',
    description=(
        'This value maps onto the *`duct_name`* argument of the commands listed'
        ' in `bprc(5) § INDUCT COMMANDS`. `bpadmin(1)` uses the protocol name and'
        ' duct name to identify an induct.'
    ),
    extra_json_schema=string_or_null_extra_json_schema,
)

DuctNameRequestMeta = Meta(
    title='Duct Name',
    description=(
        f'{DuctNameResponseMeta.description}<br />'
        '<br />'
        'If `duct_name` in the request is a string, then that exact `duct_name`'
        ' will be returned in `duct_name.value` in representations. If `duct_name`'
        ' in the request is an object, then `duct_name.value` in returned'
        ' representations will be generated based on the type of the object.<br />'
        '<br />'
        'An object with type `"ip"` will have a `duct_name.value` with the format'
        ' <code>"<i>ip</i>[:<i>port</i>]"</code>,'
        ' where *`ip`* is the `destination_value` of the destination'
        ' referenced by `destination_id` and'
        ' *`port`* is the `port_number` from the'
        ' object.'
        ' A null `destination_id` will result in a null `duct_name.value`'
        ' in responses.<br />'
        '<br />'
        'An object without a `type` property will have type `"ip"` by default.'
    ),
    examples=[
        str(NodeNumberMeta.examples[0]),
        f'{DestinationValueMeta.examples[0]}:{PortNumberMeta.examples[0]}',
        {
            'type': 'ip',
            'destination_id': DestinationIDMeta.examples[0],
            'port_number': PortNumberMeta.examples[0],
        },
    ],
)

CliCommandMeta = Meta(
    title='CLI Command',
    description=(
        'This value maps onto the *`cli_command`* argument of the commands listed'
        ' in `bprc(5) § INDUCT COMMANDS`.'
        ' This convergence layer input program'
        ' extracts bundles from protocol data units of the convergence layer'
        ' protocol and passes the bundles to a bundle protocol agent.'
        ' The CLI program determines what CL protocol is actually used;'
        ' the *`protocol_name`* argument in `bprc(5) § INDUCT COMMANDS`'
        ' is just a name that `ionadmin(1)`'
        ' uses to name protocols and inducts.'
        ' *`protocol_name`* could really be arbitrary if the CLI supported it;'
        ' as it happens, the CLIs that come with ION are hard-coded'
        ' to search for inducts with specific protocol names,'
        ' e.g., `ltpcli` looks for an induct with the `ltp` protocol name.'
    ),
    examples=['tcpcli', 'ltpcli'],
    extra_json_schema=string_or_null_extra_json_schema,
)

UsesLtpMeta = Meta(
    title='Uses LTP',
    description=(
        'Boolean value to track whether the CLI uses LTP. The API only lets a'
        ' seat associate with an induct if the CLI command of the induct uses'
        ' LTP, viz. `uses_ltp` is true.'
    ),
    examples=[False, True],
)


class DuctNameTagEnum(str, enum.Enum):
    PLAIN = 'plain'
    IP = 'ip'


class DuctNameResponseBase(
    BaseStruct, tag_field='type', tag=DuctNameTagEnum.PLAIN.value
):
    value: Annotated[str | None, DuctNameResponseMeta]


def to_duct_name_ip_schema(value: str | None, induct_ip: InductIp) -> DuctNameIpSchema:
    return DuctNameIpSchema(
        value=value,
        destination=(
            None
            if induct_ip.destination is None
            else to_destination_without_host_id_schema(induct_ip.destination)
        ),
        port_number=induct_ip.port_number,
    )


class DuctNameIpSchema(DuctNameResponseBase, tag=DuctNameTagEnum.IP.value):
    """Fields specific only to IP inducts."""

    destination: DestinationWithoutHostIdSchema | None
    port_number: Annotated[
        int | None,
        Meta(
            title=PortNumberMeta.title,
            description=PortNumberMeta.description,
            examples=PortNumberMeta.examples,
        ),
    ]


def process_duct_name(induct: Induct) -> DuctNameResponseBase | DuctNameIpSchema:
    """Returns the duct_name to be returned in responses for `induct`.
    Well-known CLI commands will have an appropriate duct_name value
    generated.
    """
    duct_name = induct.duct_name
    if duct_name is None:
        if induct.induct_ip is not None and induct.induct_ip.destination is not None:
            duct_name_str = process_destination_value(induct.induct_ip.destination)
            if induct.induct_ip.port_number is not None:
                duct_name_str += f':{induct.induct_ip.port_number}'
                duct_name = duct_name_str
        elif induct.cli_command == 'bsspcli':
            # ION 4.1.4-b.2 doesn't support allocator_id.node_number for
            # bsspcli/o yet. Regardless, this value is still correct, but ugly.
            duct_name = f'{(induct.node.allocator_id << 32) + induct.node.node_number}'
        elif induct.cli_command == 'ltpcli':
            duct_name = f'{induct.node.allocator_id}.{induct.node.node_number}'
    if induct.induct_ip is not None:
        return to_duct_name_ip_schema(duct_name, induct.induct_ip)
    return DuctNameResponseBase(value=duct_name)


def to_induct_without_node_id_schema(induct: Induct) -> InductWithoutNodeIdSchema:
    return InductWithoutNodeIdSchema(
        induct_id=str(induct.induct_id),
        cl_protocol=(
            None
            if induct.cl_protocol is None
            else to_cl_protocol_without_node_id_schema(induct.cl_protocol)
        ),
        duct_name=process_duct_name(induct),
        cli_command=induct.cli_command,
        uses_ltp=induct.uses_ltp,
    )


class InductWithoutNodeIdSchema(BaseStruct):
    """Representation of an induct in responses where node_id is
    redundant.
    """

    induct_id: Annotated[
        str,
        Meta(
            title=InductIDMeta.title,
            description=InductIDMeta.description,
            examples=InductIDMeta.examples,
        ),
    ]
    cl_protocol: ClProtocolWithoutNodeIdSchema | None
    duct_name: DuctNameResponseBase | DuctNameIpSchema
    cli_command: Annotated[str | None, CliCommandMeta]
    uses_ltp: Annotated[bool, UsesLtpMeta]


def to_induct_schema(induct: Induct) -> InductSchema:
    return InductSchema(
        induct_id=str(induct.induct_id),
        cl_protocol=(
            None
            if induct.cl_protocol is None
            else to_cl_protocol_without_node_id_schema(induct.cl_protocol)
        ),
        duct_name=process_duct_name(induct),
        cli_command=induct.cli_command,
        uses_ltp=induct.uses_ltp,
        node_id=str(induct.node_id),
    )


class InductSchema(InductWithoutNodeIdSchema):
    """Representation of an induct in responses."""

    node_id: Annotated[
        str,
        Meta(
            title=NodeIDMeta.title,
            description=NodeIDMeta.description,
            examples=NodeIDMeta.examples,
        ),
    ]


duct_name_ip_example = DuctNameIpSchema(
    value=f'{DestinationValueMeta.examples[0]}:{PortNumberMeta.examples[0]}',
    destination=DestinationWithoutHostIdSchema(
        destination_id=DestinationIDMeta.examples[0],
        destination_value=DestinationValueMeta.examples[0],
    ),
    port_number=PortNumberMeta.examples[0],
)

induct_ip_example = Example(
    summary='TCP Induct',
    description=(
        'Representation of an induct using tcpcli. The corresponding `bprc(5)`'
        ' command to add this induct is `a induct tcp'
        f' {duct_name_ip_example.value} {CliCommandMeta.examples[0]}`.'
    ),
    value=InductSchema(
        induct_id=InductIDMeta.examples[0],
        cl_protocol=ClProtocolWithoutNodeIdSchema(
            cl_protocol_id=ClProtocolIDMeta.examples[1],
            cl_protocol_name=ClProtocolNameMeta.examples[1],
            cl_protocol_class=ClProtocolClassPropertyMeta.examples[1],
        ),
        duct_name=duct_name_ip_example,
        cli_command=CliCommandMeta.examples[0],
        uses_ltp=UsesLtpMeta.examples[0],
        node_id=NodeIDMeta.examples[0],
    ),
)

duct_name_ltp_example = DuctNameResponseBase(
    value=f'{AllocatorIDMeta.examples[0]}.{NodeNumberMeta.examples[0]}'
)

induct_ltp_example = Example(
    summary='LTP Induct',
    description=(
        'Representation of an induct using ltpcli. The corresponding `bprc(5)`'
        ' command to add this induct is `a induct ltp'
        f' {duct_name_ltp_example.value} {CliCommandMeta.examples[1]}`.'
    ),
    value=InductSchema(
        induct_id=InductIDMeta.examples[1],
        cl_protocol=ClProtocolWithoutNodeIdSchema(
            cl_protocol_id=ClProtocolIDMeta.examples[0],
            cl_protocol_name=ClProtocolNameMeta.examples[0],
            cl_protocol_class=ClProtocolClassPropertyMeta.examples[0],
        ),
        duct_name=duct_name_ltp_example,
        cli_command=CliCommandMeta.examples[1],
        uses_ltp=UsesLtpMeta.examples[1],
        node_id=NodeIDMeta.examples[0],
    ),
)

induct_examples = [induct_ip_example, induct_ltp_example]


class DuctNameIpCreateSchema(BaseStruct, tag_field='type', tag='ip'):
    """Specifies the `duct_name` object for IP based duct names in
    `InductCreateSchema`.
    """

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


def supported_duct_name(cli_command: str) -> bool:
    return cli_command in no_duct_name_known_cli_not_ip


INDUCT_IP_HINT = (
    'An `"ip"` type `duct_name` object should be used'
    ' over a string for `duct_name` in request bodies'
    ' when you want `duct_name.value` in responses'
    ' to reference a destination on the host.'
    ' This comes with benefits like'
    ' avoiding typing an <code>"<i>ip</i>[:<i>port</i>]"</code> value'
    ' for `duct_name` that exactly matches the destination,'
    ' updating `duct_name` automatically when the destination value changes,'
    ' and nullifying `duct_name` when the destination is deleted.'
    ' Note that the `duct_name` object can only reference a destination'
    ' if the node is on a host.'
    ' If you want the induct to have a meaningful `duct_name`'
    ' in responses with a hostless node,'
    ' you have to use a string for `duct_name` in the request.'
)


class InductCreateSchema(BaseStruct):
    """Specifies the request body for creating an induct."""

    cl_protocol_id: Annotated[
        Annotated[int, Meta(ge=ClProtocolIDMeta.ge, le=ClProtocolIDMeta.le)] | None,
        Meta(
            title=ClProtocolIDMeta.title,
            description=ClProtocolIDMeta.description,
            examples=ClProtocolIDMeta.examples,
            extra_json_schema=nullable_nonnegative_bigint_reqbody_extra_json_schema,
        ),
    ] = JSON_NULL
    duct_name: Annotated[str | DuctNameIpCreateSchema | None, DuctNameRequestMeta] = (
        JSON_NULL
    )
    cli_command: Annotated[str | None, CliCommandMeta] = JSON_NULL
    uses_ltp: Annotated[bool, UsesLtpMeta] = False

    def __post_init__(self):
        if self.cl_protocol_id is JSON_NULL:
            self.cl_protocol_id = None
        if self.cli_command is JSON_NULL:
            self.cli_command = None
        if self.duct_name is JSON_NULL:
            self.duct_name = None
        elif isinstance(self.duct_name, DuctNameIpCreateSchema):
            if self.duct_name.destination_id is JSON_NULL:
                self.duct_name.destination_id = None
            if self.duct_name.port_number is JSON_NULL:
                self.duct_name.port_number = None


InductCreateBody = Body(
    examples=[
        Example(
            value=InductCreateSchema(
                cl_protocol_id=ClProtocolIDMeta.examples[1],
                duct_name=DuctNameIpCreateSchema(
                    destination_id=DestinationIDMeta.examples[0],
                    port_number=PortNumberMeta.examples[0],
                ),
                cli_command=CliCommandMeta.examples[0],
                uses_ltp=False,
            )
        ),
    ],
)


INDUCT_WRITE_DESCRIPTION = (
    'This API is aware of convergence layer input (CLI) programs'
    ' that come with ION'
    ' and performs the following additional checks'
    ' to prevent logic errors:'
    '<ul>'
    '<li><p>'
    'In the following list of key-value pairs,'
    ' if `cli_command` is equivalent to key,'
    ' then `cl_protocol_id` must refer to a CL protocol'
    " with a `cl_protocol_name` equivalent to the pair's value."
    ' These CLI programs are hard-coded to look for inducts'
    ' with a specific `bprc(5)` *`protocol_name`* and fail if not found.'
    '</p></li>'
    '<ul>'
    f'{
        "".join(
            [
                f'<li><p>`"{k}"`: `"{v}"`</p></li>'
                for k, v in cli_command_with_required_protocol_name
            ]
        )
    }'
    '</ul>'
    '<li><p>'
    'If `cli_command` is `"ltpcli"`, then `uses_ltp` must be true.'
    '</p></li>'
    '<li><p>'
    'If `cli_command` is in'
    f' ({", ".join([f'`"{n}"`' for n in no_uses_ltp_known_cli])}), then'
    ' `uses_ltp` must be false.'
    '</p></li>'
    '<li><p>'
    'If `cli_command` is in'
    f' ({", ".join([f'`"{n}"`' for n in no_duct_name_known_cli_not_ip])}),'
    ' then `duct_name` must be null.'
    " These programs use the node's node number as their `bprc(5)` *`duct_name`*"
    ' which is already known through `node_id`.'
    '</p></li>'
    '<li><p>'
    'If `cli_command` is `"brsccla"`, then `duct_name` cannot be an object'
    ' with type `"ip"`.'
    ' An object with type `"ip"` should only be used for CLIs'
    ' that need a `bprc(5)` *`duct_name`* in the format'
    ' <code>"<i>ip</i>[:<i>port</i>]"</code> which'
    ' this program is known not to use.'
    '</p></li>'
    '</ul>'
    f'<p>{INDUCT_IP_HINT}</p>'
)

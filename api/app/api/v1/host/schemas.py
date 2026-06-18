from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Annotated, Literal

from litestar.openapi.spec import Example
from litestar.params import Parameter
from msgspec import UNSET, Meta

import app.api.v1.node.schemas
from app.fields import HOST_ID_MAX, SANA_SCID_MAX
from app.models import NewlineEnum
from app.schemas import (
    JSON_NULL,
    BaseStruct,
    nonnegative_bigint_pathparam_schema_extra,
    nonnegative_bigint_reqbody_extra_json_schema,
    nullable_nonnegative_bigint_reqbody_extra_json_schema,
    nullable_nonnegative_int_reqbody_extra_json_schema,
    string_or_null_extra_json_schema,
)

from ..operator.schemas import (
    OperatorIDMeta,
    OperatorIDNullableWrite,
    OperatorNameMeta,
    OperatorReadMinimalSchema,
    to_operator_minimal_schema,
)
from ..schemas import (
    FIELDS_ALL,
    QueryRequest,
    create_fields_param,
)

if TYPE_CHECKING:
    from app.models import Host

HostIDMeta = Meta(
    ge=0,
    le=HOST_ID_MAX,
    title='Host ID',
    description='Surrogate key to identify a host',
    examples=['6'],
    extra_json_schema=nonnegative_bigint_reqbody_extra_json_schema,
)

HostIDParam = Parameter(
    ge=HostIDMeta.ge,
    le=HostIDMeta.le,
    title=HostIDMeta.title,
    description=HostIDMeta.description,
    schema_extra=nonnegative_bigint_pathparam_schema_extra,
)

type HostIDNullableWrite = Annotated[
    Annotated[int, Meta(ge=HostIDMeta.ge, le=HostIDMeta.le)] | None,
    Meta(
        title=HostIDMeta.title,
        description=HostIDMeta.description,
        examples=HostIDMeta.examples,
        extra_json_schema=nullable_nonnegative_bigint_reqbody_extra_json_schema,
    ),
]

HostnameMeta = Meta(
    title='Hostname',
    description=(
        'Hostname of the machine. On most systems, this is returned by the'
        ' `hostname` utility. Systems vary on allowed syntax. On Unix-like'
        ' machines, see hostname(7) for more information.'
    ),
    examples=['enterprise.example.com'],
)

HostDescriptionMeta = Meta(
    title='Host Description',
    description=(
        'Additional information about the host that is not captured by a property'
        ' of the schema.'
    ),
    examples=['Computer on a thing orbiting another thing'],
    extra_json_schema=string_or_null_extra_json_schema,
)

SANASCIDMeta = Meta(
    title='Spacecraft Identifier',
    description=(
        'Value from the Space Assigned Numbers Authority Spacecraft Identifier'
        ' registry. Used for hosts that are on spacecrafts.'
    ),
    examples=[14],
    extra_json_schema=nullable_nonnegative_int_reqbody_extra_json_schema,
)

WordSizeMeta = Meta(
    title='Word Size',
    description=(
        "Size of a word in the host's architecture. For relevant architectures"
        ' (nonvariable and binary), this is the number of bits in a word. This'
        " should be the hardware's actual word length. E.g., for a x86-64"
        ' processor, use `64` not `16`. ION is designed only with 32-bit and'
        ' 64-bit architectures in mind, so this value is restricted to `32`'
        ' and `64` anyway.'
    ),
    examples=[64],
    extra_json_schema={
        'extra': {
            'type': ['integer', 'string', 'null'],
            'enum': [32, '32', 64, '64', None],
        }
    },
)

NewlineMeta = Meta(
    title='Newline',
    description=(
        "Host's operating system's preferred newline representation. All characters"
        ' / sequences that cause mandatory breaks as defined in Unicode Standard'
        ' Annex #14 (version 16) are available, but the only relevant options'
        ' are `LF` (Unix-like systems) and `CRLF` (Windows).'
    ),
    examples=[NewlineEnum.LF],
)


class HostQueryFieldsEnum(str, Enum):
    ALL = FIELDS_ALL
    HOST_ID = 'host_id'
    HOSTNAME = 'hostname'
    HOST_DESCRIPTION = 'host_description'
    SANA_SCID = 'sana_scid'
    NEWLINE = 'newline'
    # TODO: how to handle nested stuff?
    # OPERATOR = 'operator'
    # OPERATOR_OPERATOR_ID = 'operator.operator_id'
    # OPERATOR_OPERATOR_NAME = 'operator.operator_name'


class HostQueryRequest(QueryRequest):
    """Specifies query parameters for querying hosts."""

    fields: Annotated[
        list[HostQueryFieldsEnum] | None,
        create_fields_param([e.value for e in HostQueryFieldsEnum]),
    ] = None


def to_host_schema(host: Host) -> HostSchema:
    return HostSchema(
        host_id=str(host.host_id),
        hostname=host.hostname,
        host_description=host.host_description,
        sana_scid=host.sana_scid,
        word_size=host.word_size,
        newline=host.newline,
        operator=(
            None if host.operator is None else to_operator_minimal_schema(host.operator)
        ),
        nodes=[
            app.api.v1.node.schemas.to_node_with_allocator_schema(n) for n in host.nodes
        ],
    )


class HostSchema(BaseStruct):
    """Representation of a host in responses."""

    # Give fields a default value so they don't appear as required in the
    # OpenAPI schema (we want to support `fields` mask later).
    host_id: Annotated[
        str,
        Meta(
            title=HostIDMeta.title,
            description=HostIDMeta.description,
            examples=HostIDMeta.examples,
        ),
    ] = UNSET
    hostname: Annotated[str, HostnameMeta] = UNSET
    host_description: Annotated[str | None, HostDescriptionMeta] = UNSET
    sana_scid: Annotated[
        int | None,
        Meta(
            title=SANASCIDMeta.title,
            description=SANASCIDMeta.description,
            examples=SANASCIDMeta.examples,
        ),
    ] = UNSET
    word_size: Annotated[
        int | None,
        Meta(
            title=WordSizeMeta.title,
            description=WordSizeMeta.description,
            examples=WordSizeMeta.examples,
        ),
    ] = UNSET
    newline: Annotated[NewlineEnum | None, NewlineMeta] = UNSET
    operator: OperatorReadMinimalSchema | None = UNSET
    nodes: Annotated[
        list[app.api.v1.node.schemas.NodeWithAllocatorSchema],
        Meta(
            description='DO NOT USE', extra_json_schema={'extra': {'deprecated': True}}
        ),
    ] = []


def to_host_minimal_schema(host: Host) -> HostReadMinimalSchema:
    return HostReadMinimalSchema(host_id=str(host.host_id), hostname=host.hostname)


class HostReadMinimalSchema(BaseStruct):
    """Minimal representation of a host in responses."""

    host_id: Annotated[
        str,
        Meta(
            title=HostIDMeta.title,
            description=HostIDMeta.description,
            examples=HostIDMeta.examples,
        ),
    ] = UNSET
    hostname: Annotated[str, HostnameMeta] = UNSET


class HostCreateSchema(BaseStruct):
    """Specifies the request body for creating a host."""

    hostname: Annotated[str, HostnameMeta]
    host_description: Annotated[str | None, HostDescriptionMeta] = JSON_NULL
    sana_scid: Annotated[
        Annotated[int, Meta(ge=0, le=SANA_SCID_MAX)] | None, SANASCIDMeta
    ] = JSON_NULL
    # Don't include "32" and "64" in the Literal. msgspec will convert str to
    # int. The view functions should think of this is as int | None and not
    # worry about strings.
    word_size: Annotated[Literal[32, 64] | None, WordSizeMeta] = JSON_NULL
    newline: Annotated[NewlineEnum | None, NewlineMeta] = JSON_NULL
    operator_id: OperatorIDNullableWrite = JSON_NULL

    def __post_init__(self):
        if self.host_description is JSON_NULL:
            self.host_description = None
        if self.sana_scid is JSON_NULL:
            self.sana_scid = None
        if self.word_size is JSON_NULL:
            self.word_size = None
        if self.newline is JSON_NULL:
            self.newline = None
        if self.operator_id is JSON_NULL:
            self.operator_id = None


class HostUpdateSchema(BaseStruct):
    """Specifies the request body for updating a host."""

    hostname: Annotated[str, HostnameMeta] = UNSET
    host_description: Annotated[str | None, HostDescriptionMeta] = UNSET
    sana_scid: Annotated[
        Annotated[int, Meta(ge=0, le=SANA_SCID_MAX)] | None, SANASCIDMeta
    ] = UNSET
    word_size: Annotated[Literal[32, 64] | None, WordSizeMeta] = UNSET
    newline: Annotated[NewlineEnum | None, NewlineMeta] = UNSET
    operator_id: Annotated[
        Annotated[int, Meta(ge=OperatorIDMeta.ge, le=OperatorIDMeta.le)] | None,
        Meta(
            title=OperatorIDMeta.title,
            description=OperatorIDMeta.description,
            examples=OperatorIDMeta.examples,
            extra_json_schema=nullable_nonnegative_bigint_reqbody_extra_json_schema,
        ),
    ] = UNSET


class HostCopySchema(BaseStruct):
    """Specifies the request body for copying a host."""

    operator_id: OperatorIDNullableWrite = JSON_NULL
    nodes: Annotated[
        list[app.api.v1.node.schemas.NodeCopyForHostSchema],
        Meta(extra_json_schema={'extra': {'default': []}}),
    ] = []

    def __post_init__(self):
        if self.operator_id is JSON_NULL:
            self.operator_id = None


host_copy_response_example = Example(
    summary='Copied Host',
    value=HostSchema(
        host_id='65',
        hostname=HostnameMeta.examples[0],
        host_description=HostDescriptionMeta.examples[0],
        sana_scid=SANASCIDMeta.examples[0],
        word_size=WordSizeMeta.examples[0],
        newline=NewlineMeta.examples[0],
        operator=OperatorReadMinimalSchema(
            operator_id=OperatorIDMeta.examples[0],
            operator_name=OperatorNameMeta.examples[0],
        ),
        nodes=UNSET,
    ),
)

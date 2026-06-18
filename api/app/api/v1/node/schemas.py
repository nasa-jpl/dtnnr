from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Annotated

from litestar.openapi.spec import Example, OpenAPIType, Schema
from litestar.params import Body, Parameter
from msgspec import UNSET, Meta

from app.fields import (
    HEAP_WORDS_MAX,
    NODE_ID_MAX,
    NODE_NUMBER_MAX,
    SDR_WM_SIZE_MAX,
    WM_SIZE_MAX,
)
from app.schemas import (
    JSON_NULL,
    BaseStruct,
    bigint,
    nonnegative_bigint_pathparam_schema_extra,
    nonnegative_bigint_reqbody_extra_json_schema,
    nullable_nonnegative_bigint_resbody_extra_json_schema,
    nullable_positive_bigint_reqbody_extra_json_schema,
    string_or_null_extra_json_schema,
)

from ..allocator.schemas import (
    AllocatorIDMeta,
    AllocatorNameMeta,
    AllocatorReadMinimalSchema,
)
from ..allocator.schemas import to_minimal_schema as to_allocator_minimal_schema
from ..host.schemas import (
    HostIDMeta,
    HostIDNullableWrite,
    HostnameMeta,
    HostReadMinimalSchema,
    to_host_minimal_schema,
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
from .service import DestinationRefModeEnum

if TYPE_CHECKING:
    from app.models import Node

NodeIDMeta = Meta(
    ge=0,
    le=NODE_ID_MAX,
    title='Node ID',
    description='Surrogate key to identify a node',
    examples=['8'],
    extra_json_schema=nonnegative_bigint_reqbody_extra_json_schema,
)

NodeIDParam = Parameter(
    ge=NodeIDMeta.ge,
    le=NodeIDMeta.le,
    title=NodeIDMeta.title,
    description=NodeIDMeta.description,
    schema_extra=nonnegative_bigint_pathparam_schema_extra,
)

NodeNumberMeta = Meta(
    ge=0,
    le=NODE_NUMBER_MAX,
    title='Node Number',
    description=(
        'Shared identifier assigned to all ipn URIs for resources co-located on'
        ' a single node'
    ),
    examples=[15498],
    extra_json_schema={
        'extra': {
            'minimum': None,
            'maximum': None,
            'type': None,
            'format': None,
            'oneOf': [
                Schema(
                    type='integer',
                    minimum=0,
                    maximum=NODE_NUMBER_MAX,
                    format='uint32',
                ),
                Schema(
                    type='string',
                    minimum=0,
                    maximum=NODE_NUMBER_MAX,
                    description='There will be an attempt to cast strings into an integer',
                    format='uint32',
                ),
            ],
        }
    },
)


def _null_ionconfig_param_meaning(parameter_name: str) -> str:
    return (
        f'`null` should be interpreted as omitting {parameter_name} from ionconfig(5)'
        " which means to use whatever default value the node's version of ionadmin(1)"
        ' uses.'
    )


SdrWmSizeMeta = Meta(
    title='SDR Working Memory Size',
    description=(
        'Size of the block of dynamic memory that will be reserved as private'
        ' working memory for the Simple Data Recorder. Note that this shared'
        " memory segment is independent from the node's working memory which"
        ' is controlled by `wm_size`.<br />'
        '<br />'
        f'{_null_ionconfig_param_meaning("sdrWmSize")}'
    ),
    examples=[1000000],
    extra_json_schema=nullable_positive_bigint_reqbody_extra_json_schema,
)


class SdrConfigFlagsEnum(str, Enum):
    SDR_IN_DRAM = 'SDR_IN_DRAM'
    SDR_IN_FILE = 'SDR_IN_FILE'
    SDR_REVERSIBLE = 'SDR_REVERSIBLE'
    SDR_BOUNDED = 'SDR_BOUNDED'


sdr_config_flags_map: dict[SdrConfigFlagsEnum, int] = {
    SdrConfigFlagsEnum.SDR_IN_DRAM.value: 1,
    SdrConfigFlagsEnum.SDR_IN_FILE.value: 2,
    SdrConfigFlagsEnum.SDR_REVERSIBLE.value: 4,
    SdrConfigFlagsEnum.SDR_BOUNDED.value: 8,
}


def config_flags_int_to_arr(config_flags: int | None) -> list[str] | None:
    if config_flags is None:
        return None
    res = list()
    for f, val in sdr_config_flags_map.items():
        if config_flags & val:
            res.append(f)
    return res


def config_flags_arr_to_int(config_flags: set[str] | None) -> int | None:
    if config_flags is None:
        return None
    res = 0
    for s in config_flags:
        res |= sdr_config_flags_map[s]
    return res


_sdr_config_flags_desc = [
    f'"{f.value}" maps to the number {sdr_config_flags_map[f.value]}'
    for f in SdrConfigFlagsEnum
]

SdrConfigFlagsMeta = Meta(
    title='SDR Config Flags',
    description=(
        'A set of values that characterizes the SDR database used by the node.'
        f' As of ION 4.1.3s, {", ".join(_sdr_config_flags_desc[:-1])}, and '
        f' {_sdr_config_flags_desc[-1]}. The bitwise OR of these numerical values'
        ' is what should be the argument for the "configFlags" parameter from'
        ' ionconfig(5).<br />'
        '<br />'
        f'{_null_ionconfig_param_meaning("configFlags")}'
    ),
    examples=[
        [
            SdrConfigFlagsEnum.SDR_IN_DRAM,
            SdrConfigFlagsEnum.SDR_REVERSIBLE,
            SdrConfigFlagsEnum.SDR_BOUNDED,
        ]
    ],
    # don't think this is right
    extra_json_schema={
        'extra': {
            'oneOf': [
                {
                    'items': {
                        'type': 'string',
                        'enum': [f.value for f in SdrConfigFlagsEnum],
                    },
                    'minItems': 1,
                    'maxItems': len(SdrConfigFlagsEnum),
                    # We don't actually validate uniqueness, we just deserialize
                    # as set, but being true makes it more clear what users
                    # should send.
                    'uniqueItems': True,
                },
                {'type': 'null'},
            ]
        }
    },
)

HeapWordsMeta = Meta(
    title='Heap Words',
    description=(
        'Number of words (usually of 32 bits each on a 32-bit machine and 64 bits'
        " on a 64-bit machine) of nominally non-volatile storage to use for ION's"
        ' SDR database.<br />'
        '<br />'
        f'{_null_ionconfig_param_meaning("heapWords")}'
    ),
    examples=[250000],
    extra_json_schema=nullable_positive_bigint_reqbody_extra_json_schema,
)

WmSizeMeta = Meta(
    title='Working Memory Size',
    description=(
        "Size of the block of dynamic memory used for the node's working memory."
        " Note that this shared memory segment is independent from the SDR's"
        ' working memory which is controlled by `sdr_wm_size`.<br />'
        '<br />'
        f'{_null_ionconfig_param_meaning("wmSize")}'
    ),
    examples=[5000000],
    extra_json_schema=nullable_positive_bigint_reqbody_extra_json_schema,
)


NodeNameMeta = Meta(
    title='Node Name',
    description=(
        "Name used by ION Config Tool to name files. E.g., if a node's name is"
        ' "node1", then the tool generates node1.bprc, node1.ionrc, etc.'
    ),
    examples=['node1'],
    extra_json_schema=string_or_null_extra_json_schema,
)

CommentsMeta = Meta(
    title='Comments',
    description='Arbitrary notes about this node',
    examples=["It's 5 o'clock on the sun"],
    extra_json_schema=string_or_null_extra_json_schema,
)

CreatedAtMeta = Meta(
    title='Created At',
    description=(
        'Timezone-aware date and time of when this node was created in a'
        ' RFC 3339 compatible format'
    ),
    examples=['2010-08-21T09:12:00Z'],
    extra_json_schema={'extra': {'format': 'date-time'}},
)

ModifiedAtMeta = Meta(
    title='Modified At',
    description=(
        'Timezone-aware date and time of when this node was last modified in a'
        ' RFC 3339 compatible format'
    ),
    examples=['2025-08-21T09:12:00Z'],
    extra_json_schema={'extra': {'format': 'date-time'}},
)


type DestinationRefModeParam = Annotated[
    DestinationRefModeEnum,
    Parameter(
        title='Destination Reference Mode',
        description=(
            'Behavior for handling destinations referenced by this'
            " node's inducts and seats."
            " This parameter has no effect if the node's host does not change.\n"
            '\n'
            f'* "{DestinationRefModeEnum.NULLIFY}": inducts and seats drop their'
            ' references to destinations. This is the default behavior.\n'
            f'* "{DestinationRefModeEnum.ASSOCIATE}": inducts and seats update'
            ' their destination references to an equivalent destination under'
            ' the new host.'
            ' References without an equivalent destination are dropped.'
            ' This option is not allowed if the node is currently on a host'
            ' and the update operation makes the node hostless.\n'
            f'* "{DestinationRefModeEnum.COPY}": inducts and seats update'
            ' their destination references to an equivalent destination under'
            ' the new host.'
            ' References without an equivalent destination are copied to'
            ' the new host.'
            ' This option is not allowed if the node is currently on a host'
            ' and the update operation makes the node hostless.'
        ),
        schema_extra={
            'oneOf': None,
            'enum': [e.value for e in DestinationRefModeEnum],
            'type': OpenAPIType.STRING,
        },
    ),
]

type DestinationRefModeParamCopyNode = Annotated[
    DestinationRefModeEnum,
    Parameter(
        title='Destination Reference Mode',
        description=(
            'Behavior for handling destinations referenced by the to-be-copied'
            " node's inducts and seats."
            ' This parameter has no effect if `host_id` in the request body'
            ' is the same as the `host_id` of the to-be-copied node.\n'
            '\n'
            f'* "{DestinationRefModeEnum.NULLIFY}": copied inducts and seats'
            ' will not reference destinations. This is the default behavior.\n'
            f'* "{DestinationRefModeEnum.ASSOCIATE}": copied inducts and seats'
            ' will reference equivalent destinations under the new host if they'
            ' exist, otherwise the induct / seat will not reference'
            ' a destination.'
            ' This option is not allowed if the to-be-copied node is currently'
            ' on a host and the copied node will be hostless.\n'
            f'* "{DestinationRefModeEnum.COPY}": copied inducts and seats'
            ' will reference equivalent destinations under the new host'
            ' if they exist.'
            ' If an equivalent destination does not exist, then the'
            ' destination is copied to the new host.'
            ' This option is not allowed if the to-be-copied node is currently'
            ' on a host and the copied node will be hostless.'
        ),
        schema_extra={
            'oneOf': None,
            'enum': [e.value for e in DestinationRefModeEnum],
            'type': OpenAPIType.STRING,
        },
        schema_component_key='DestinationRefModeEnum2',
    ),
]


class NodeQueryFieldsEnum(str, Enum):
    ALL = FIELDS_ALL
    NODE_ID = 'node_id'
    NODE_NUMBER = 'node_number'
    SDR_WM_SIZE = 'sdr_wm_size'
    SDR_CONFIG_FLAGS = 'sdr_config_flags'
    HEAP_WORDS = 'heap_words'
    WM_SIZE = 'wm_size'
    NODE_NAME = 'node_name'
    COMMENTS = 'comments'
    CREATED_AT = 'created_at'
    MODIFIED_AT = 'modified_at'
    # TODO: how to handle nested stuff?
    # ALLOCATOR = 'allocator'
    # ALLOCATOR_ALLOCATOR_ID = 'allocator.allocator_id'
    # ALLOCATOR_ALLOCATOR_NAME = 'allocator.allocator_name'
    # OPERATOR = 'operator'
    # OPERATOR_OPERATOR_ID = 'operator.operator_id'
    # OPERATOR_OPERATOR_NAME = 'operator.operator_name'
    # HOST = 'host'
    # HOST_HOST_ID = 'host.host_id'
    # HOST_HOSTNAME = 'host.hostname'


class NodeQueryRequest(QueryRequest):
    """Specifies query parameters for querying nodes."""

    fields: Annotated[
        list[NodeQueryFieldsEnum] | None,
        create_fields_param([e.value for e in NodeQueryFieldsEnum]),
    ] = None


def to_node_with_allocator_schema(node: Node) -> NodeWithAllocatorSchema:
    return NodeWithAllocatorSchema(
        node_id=str(node.node_id),
        node_number=node.node_number,
        allocator=to_allocator_minimal_schema(node.allocator),
    )


class NodeWithAllocatorSchema(BaseStruct):
    """Representation of a node with enough information to identify the
    node in the database and to know its FQNN.
    """

    node_id: Annotated[
        str,
        Meta(
            title=NodeIDMeta.title,
            description=NodeIDMeta.description,
            examples=NodeIDMeta.examples,
        ),
    ]
    node_number: Annotated[
        int,
        Meta(
            title=NodeNumberMeta.title,
            description=NodeNumberMeta.description,
            examples=NodeNumberMeta.examples,
        ),
    ]
    allocator: AllocatorReadMinimalSchema


def to_node_schema(node: Node) -> NodeSchema:
    return NodeSchema(
        node_id=str(node.node_id),
        node_number=node.node_number,
        allocator=to_allocator_minimal_schema(node.allocator),
        operator=(
            None if node.operator is None else to_operator_minimal_schema(node.operator)
        ),
        host=(None if node.host is None else to_host_minimal_schema(node.host)),
        sdr_wm_size=(None if node.sdr_wm_size is None else bigint(node.sdr_wm_size)),
        sdr_config_flags=config_flags_int_to_arr(node.sdr_config_flags),
        heap_words=(None if node.heap_words is None else bigint(node.heap_words)),
        wm_size=(None if node.wm_size is None else bigint(node.wm_size)),
        node_name=node.node_name,
        comments=node.comments,
        created_at=node.created_at,
        modified_at=node.modified_at,
    )


class NodeSchema(BaseStruct):
    """Representation of a node in responses."""

    node_id: Annotated[
        str,
        Meta(
            title=NodeIDMeta.title,
            description=NodeIDMeta.description,
            examples=NodeIDMeta.examples,
        ),
    ] = UNSET
    node_number: Annotated[
        int,
        Meta(
            title=NodeNumberMeta.title,
            description=NodeNumberMeta.description,
            examples=NodeNumberMeta.examples,
        ),
    ] = UNSET
    allocator: AllocatorReadMinimalSchema = UNSET
    operator: OperatorReadMinimalSchema | None = UNSET
    host: HostReadMinimalSchema | None = UNSET
    sdr_wm_size: Annotated[
        int | str | None,
        Meta(
            title=SdrWmSizeMeta.title,
            description=SdrWmSizeMeta.description,
            examples=SdrWmSizeMeta.examples,
            extra_json_schema=nullable_nonnegative_bigint_resbody_extra_json_schema,
        ),
    ] = UNSET
    sdr_config_flags: Annotated[
        list[SdrConfigFlagsEnum] | None,
        Meta(
            title=SdrConfigFlagsMeta.title,
            description=SdrConfigFlagsMeta.description,
            examples=SdrConfigFlagsMeta.examples,
        ),
    ] = UNSET
    heap_words: Annotated[
        int | str | None,
        Meta(
            title=HeapWordsMeta.title,
            description=HeapWordsMeta.description,
            examples=HeapWordsMeta.examples,
            extra_json_schema=nullable_nonnegative_bigint_resbody_extra_json_schema,
        ),
    ] = UNSET
    wm_size: Annotated[
        int | str | None,
        Meta(
            title=WmSizeMeta.title,
            description=WmSizeMeta.description,
            examples=WmSizeMeta.examples,
            extra_json_schema=nullable_nonnegative_bigint_resbody_extra_json_schema,
        ),
    ] = UNSET
    node_name: Annotated[str | None, NodeNameMeta] = UNSET
    comments: Annotated[str | None, CommentsMeta] = UNSET
    created_at: Annotated[datetime, CreatedAtMeta] = UNSET
    modified_at: Annotated[datetime, ModifiedAtMeta] = UNSET


type SdrWmSizeWrite = Annotated[
    Annotated[int, Meta(ge=1, le=SDR_WM_SIZE_MAX)] | None, SdrWmSizeMeta
]
type SdrConfigFlagsWrite = Annotated[
    Annotated[
        set[SdrConfigFlagsEnum], Meta(min_length=1, max_length=len(SdrConfigFlagsEnum))
    ]
    | None,
    SdrConfigFlagsMeta,
]

type HeapWordsWrite = Annotated[
    Annotated[int, Meta(ge=1, le=HEAP_WORDS_MAX)] | None, HeapWordsMeta
]

type WmSizeWrite = Annotated[
    Annotated[int, Meta(ge=1, le=WM_SIZE_MAX)] | None, WmSizeMeta
]


IONCONFIG_VALUES_DESC = (
    'Setting null for the ionconfig(5) related values (viz., `sdr_wm_size`,'
    ' `sdr_config_flags`, `heap_words`, `wm_size`) is the same as omitting those'
    ' parameters from the ionconfig file. Error checking for these parameters is'
    ' difficult because the what values are allowed depends on the host system.'
    ' Nonpositive values are not allowed since they crash ION, but the exact'
    ' minimum and maximum values will vary. What values *should* be used also'
    ' depends on your use-case. Here are some guidelines:'
    '<ul>'
    '<li><p>`sdr_wm_size` and `wm_size` need to be a multiple of the size of'
    " the hardware's double word length in bytes. Otherwise, ionadmin(1) will"
    ' fail to initialize ION.</p>'
    '<ul><li><p>Do not confuse this with "word" defined in languages. E.g.,'
    ' x86-64 assembly uses "dword" to mean something 32 bits in size, but ION is'
    ' thinking of double words as values that are 128 bits (16 bytes).</p></li>'
    '<li><p>What ION considers a double word can be modified when building, so'
    ' this guideline may not apply to esoteric builds.</p></li></ul>'
    '<li><p>`heap_words` should be at least 5 times more than the worst case'
    ' amount of bytes that the node needs to buffer.</p></li>'
    '<li><p>When using BP over LTP with the default "maxheap" value in bprc(5),'
    ' the recommended minimum value for `wm_size` is:</p>'
    f'<span>{"&nbsp;" * 8}'
    '`wm_size` = margin * `heap_words` * (number of octets per word)'
    ' * (percentage of heap space used for input/output)'
    ' / (ratio of heap and working memory footprints per bundle)'
    '</span><br />'
    '<p>With a 200% margin, 64-bit words, 40% of heap space for I/O, and 10:1'
    ' ratio between heap and working memory footprints per bundle we get:</p>'
    f'<span>{"&nbsp;" * 8}'
    '`wm_size` = 3 * `heap_words` * 8 * 0.4 / 10</span>'
    '</li>'
    '<li><p>`sdr_wm_size` should be at least 1/5 of `wm_size`.</p></li>'
    '</ul>'
)


class NodeCreateSchema(BaseStruct):
    """Specifies the request body for creating a node."""

    node_number: Annotated[int, NodeNumberMeta]
    allocator_id: Annotated[int, AllocatorIDMeta] = 0
    operator_id: OperatorIDNullableWrite = JSON_NULL
    host_id: HostIDNullableWrite = JSON_NULL
    sdr_wm_size: SdrWmSizeWrite = JSON_NULL
    sdr_config_flags: SdrConfigFlagsWrite = JSON_NULL
    heap_words: HeapWordsWrite = JSON_NULL
    wm_size: WmSizeWrite = JSON_NULL
    node_name: Annotated[str | None, NodeNameMeta] = JSON_NULL
    comments: Annotated[str | None, CommentsMeta] = JSON_NULL

    def __post_init__(self):
        if self.operator_id is JSON_NULL:
            self.operator_id = None
        if self.host_id is JSON_NULL:
            self.host_id = None
        if self.sdr_wm_size is JSON_NULL:
            self.sdr_wm_size = None
        if self.sdr_config_flags is JSON_NULL:
            self.sdr_config_flags = None
        if self.heap_words is JSON_NULL:
            self.heap_words = None
        if self.wm_size is JSON_NULL:
            self.wm_size = None
        if self.node_name is JSON_NULL:
            self.node_name = None
        if self.comments is JSON_NULL:
            self.comments = None


node_create_response_example = Example(
    summary='New Node',
    value=NodeSchema(
        node_id=NodeIDMeta.examples[0],
        node_number=NodeNumberMeta.examples[0],
        allocator=AllocatorReadMinimalSchema(
            allocator_id=AllocatorIDMeta.examples[0],
            allocator_name=AllocatorNameMeta.examples[0],
        ),
        operator=OperatorReadMinimalSchema(
            operator_id=OperatorIDMeta.examples[0],
            operator_name=OperatorNameMeta.examples[0],
        ),
        host=HostReadMinimalSchema(
            host_id=HostIDMeta.examples[0], hostname=HostnameMeta.examples[0]
        ),
        sdr_wm_size=SdrWmSizeMeta.examples[0],
        sdr_config_flags=SdrConfigFlagsMeta.examples[0],
        heap_words=HeapWordsMeta.examples[0],
        wm_size=WmSizeMeta.examples[0],
        node_name=NodeNameMeta.examples[0],
        comments=CommentsMeta.examples[0],
        created_at=CreatedAtMeta.examples[0],
        # created_at == modified_at when creating
        modified_at=CreatedAtMeta.examples[0],
    ),
)


class NodeUpdateSchema(BaseStruct):
    """Specifies the request body for updating a node."""

    node_number: Annotated[int, NodeNumberMeta] = UNSET
    allocator_id: Annotated[int, AllocatorIDMeta] = UNSET
    operator_id: OperatorIDNullableWrite = UNSET
    host_id: HostIDNullableWrite = UNSET
    sdr_wm_size: SdrWmSizeWrite = UNSET
    sdr_config_flags: SdrConfigFlagsWrite = UNSET
    heap_words: HeapWordsWrite = UNSET
    wm_size: WmSizeWrite = UNSET
    node_name: Annotated[str | None, NodeNameMeta] = UNSET
    comments: Annotated[str | None, CommentsMeta] = UNSET


class NodeCopySchema(BaseStruct):
    """Specifies the request body for copying a node."""

    node_number: Annotated[int, NodeNumberMeta]
    allocator_id: Annotated[int, AllocatorIDMeta] = 0
    operator_id: OperatorIDNullableWrite = JSON_NULL
    # null host_id by default since user may not be authorized to copy node
    # onto same host.
    host_id: HostIDNullableWrite = JSON_NULL

    def __post_init__(self):
        if self.operator_id is JSON_NULL:
            self.operator_id = None
        if self.host_id is JSON_NULL:
            self.host_id = None


_copy_node_number_example = 15532

NodeCopyBody = Body(
    examples=[
        Example(
            value=NodeCopySchema(
                node_number=_copy_node_number_example,
                allocator_id=int(AllocatorIDMeta.examples[0]),
                operator_id=int(OperatorIDMeta.examples[0]),
                host_id=int(HostIDMeta.examples[0]),
            )
        )
    ]
)

node_copy_response_example = Example(
    summary='Copied Node',
    value=NodeSchema(
        node_id='12',
        node_number=_copy_node_number_example,
        allocator=AllocatorReadMinimalSchema(
            allocator_id=AllocatorIDMeta.examples[0],
            allocator_name=AllocatorNameMeta.examples[0],
        ),
        operator=OperatorReadMinimalSchema(
            operator_id=OperatorIDMeta.examples[0],
            operator_name=OperatorNameMeta.examples[0],
        ),
        host=HostReadMinimalSchema(
            host_id=HostIDMeta.examples[0], hostname=HostnameMeta.examples[0]
        ),
        sdr_wm_size=SdrWmSizeMeta.examples[0],
        sdr_config_flags=SdrConfigFlagsMeta.examples[0],
        heap_words=HeapWordsMeta.examples[0],
        wm_size=WmSizeMeta.examples[0],
        node_name=NodeNameMeta.examples[0],
        comments=CommentsMeta.examples[0],
        created_at='2040-02-03T15:00:00Z',
        modified_at='2040-02-03T15:00:00Z',
    ),
)


class NodeCopyForHostSchema(BaseStruct):
    """Specifies an object in the "nodes" array for copying a host."""

    node_id: Annotated[int, NodeIDMeta]
    node_number: Annotated[int, NodeNumberMeta]
    allocator_id: Annotated[int, AllocatorIDMeta] = 0
    operator_id: OperatorIDNullableWrite = JSON_NULL

    def __post_init__(self):
        if self.operator_id is JSON_NULL:
            self.operator_id = None

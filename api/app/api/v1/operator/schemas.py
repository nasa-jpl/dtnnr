from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Annotated

from litestar.openapi.spec import OpenAPIType
from litestar.params import Parameter
from msgspec import UNSET, Meta, UnsetType

from app.fields import NODE_NUMBER_MAX, OPERATOR_ID_MAX
from app.problem_details import SchemaValidationError
from app.schemas import (
    BaseStruct,
    nonnegative_bigint_pathparam_schema_extra,
    nonnegative_bigint_reqbody_extra_json_schema,
    nullable_nonnegative_bigint_reqbody_extra_json_schema,
)

from ..allocator.schemas import (
    AllocatorIDMeta,
    AllocatorReadMinimalSchema,
)
from ..allocator.schemas import (
    to_minimal_schema as to_allocator_minimal_schema,
)
from ..schemas import (
    FIELDS_ALL,
    QueryRequest,
    create_fields_param,
)

if TYPE_CHECKING:
    from sqlalchemy.dialects.postgresql import Range

    from app.models import Operator

OperatorIDMeta = Meta(
    ge=0,
    le=OPERATOR_ID_MAX,
    title='Operator ID',
    description='Surrogate key to identify an operator',
    examples=['410'],
    extra_json_schema=nonnegative_bigint_reqbody_extra_json_schema,
)

type OperatorIDNullableWrite = Annotated[
    Annotated[int, Meta(ge=OperatorIDMeta.ge, le=OperatorIDMeta.le)] | None,
    Meta(
        title=OperatorIDMeta.title,
        description=OperatorIDMeta.description,
        examples=OperatorIDMeta.examples,
        extra_json_schema=nullable_nonnegative_bigint_reqbody_extra_json_schema,
    ),
]

OperatorNameMeta = Meta(
    title='Operator Name', description='Name of the operator', examples=['Mission C']
)

AllocatedNodeNumbersMeta = Meta(
    title='Allocated Node Numbers',
    description=(
        'List of discrete ranges that describe the node numbers given to the'
        ' operator by its allocator'
    ),
)

LowerMeta = Meta(
    ge=0,
    le=NODE_NUMBER_MAX,
    title='Lower Bound',
    description='Lower bound of a range',
    examples=[10000],
)

UpperMeta = Meta(
    ge=0,
    le=NODE_NUMBER_MAX,
    title='Upper Bound',
    description='Upper bound of a range',
    examples=[20001],
)


OperatorIDParam = Parameter(
    ge=OperatorIDMeta.ge,
    le=OperatorIDMeta.le,
    title=OperatorIDMeta.title,
    description=OperatorIDMeta.description,
    schema_extra=nonnegative_bigint_pathparam_schema_extra,
)


class RangeBoundsEnum(str, Enum):
    LOWER_EXC_UPPER_EXC = '()'
    LOWER_INC_UPPER_EXC = '[)'
    LOWER_EXC_UPPER_INC = '(]'
    LOWER_INC_UPPER_INC = '[]'


BoundsMeta = Meta(
    title='Bounds Inclusivity',
    description=(
        # https://www.postgresql.org/docs/17/rangetypes.html#RANGETYPES-INCLUSIVITY
        'An inclusive lower bound is represented by "[" while an exclusive lower'
        ' bound is represented by "(". Likewise, an inclusive upper bound is'
        ' represented by "]", while an exclusive upper bound is represented by ")".'
    ),
    examples=['[)'],
    extra_json_schema={
        'extra': {
            'oneOf': None,
            'type': OpenAPIType.STRING,
            'enum': [b.value for b in RangeBoundsEnum],
        }
    },
)


def to_range_schema(range: Range) -> RangeSchema:
    return RangeSchema(lower=range.lower, upper=range.upper, bounds=range.bounds)


class RangeSchema(BaseStruct):
    lower: Annotated[int, LowerMeta]
    upper: Annotated[int, UpperMeta]
    bounds: Annotated[RangeBoundsEnum | UnsetType, BoundsMeta]


def to_operator_minimal_schema(operator: Operator) -> OperatorReadMinimalSchema:
    return OperatorReadMinimalSchema(
        operator_id=str(operator.operator_id),
        operator_name=operator.operator_name,
    )


class OperatorReadMinimalSchema(BaseStruct):
    """Minimal representation of an operator in responses."""

    operator_id: Annotated[
        str,
        Meta(
            title=OperatorIDMeta.title,
            description=OperatorIDMeta.description,
            examples=OperatorIDMeta.examples,
        ),
    ] = UNSET
    operator_name: Annotated[str, OperatorNameMeta] = UNSET


import app.api.v1.host.schemas as host_schemas
import app.api.v1.node.schemas as node_schemas


def to_operator_schema(operator: Operator) -> OperatorSchema:
    return OperatorSchema(
        operator_id=str(operator.operator_id),
        operator_name=operator.operator_name,
        allocated_node_numbers=[
            to_range_schema(r) for r in operator.allocated_node_numbers
        ],
        allocator=to_allocator_minimal_schema(operator.allocator),
        hosts=[host_schemas.to_host_minimal_schema(h) for h in operator.hosts],
        nodes=[node_schemas.to_node_with_allocator_schema(n) for n in operator.nodes],
    )


class OperatorSchema(BaseStruct):
    """Representation of an operator in responses."""

    operator_id: Annotated[
        str,
        Meta(
            title=OperatorIDMeta.title,
            description=OperatorIDMeta.description,
            examples=OperatorIDMeta.examples,
        ),
    ] = UNSET
    operator_name: Annotated[str, OperatorNameMeta] = UNSET
    allocated_node_numbers: Annotated[list[RangeSchema], AllocatedNodeNumbersMeta] = (
        UNSET
    )
    allocator: AllocatorReadMinimalSchema = UNSET
    hosts: Annotated[
        list[host_schemas.HostReadMinimalSchema],
        Meta(
            description='DO NOT USE', extra_json_schema={'extra': {'deprecated': True}}
        ),
    ] = []
    nodes: Annotated[
        list[node_schemas.NodeWithAllocatorSchema],
        Meta(
            description='DO NOT USE', extra_json_schema={'extra': {'deprecated': True}}
        ),
    ] = []


class OperatorNewSchema(OperatorSchema):
    """Representation of an operator returned after creation. We set
    allocated_node_numbers to have an empty list as its example to
    prevent confusion.
    """

    allocated_node_numbers: Annotated[
        list[RangeSchema],
        Meta(
            title=AllocatedNodeNumbersMeta.title,
            description=AllocatedNodeNumbersMeta.description,
            examples=[[]],
        ),
    ] = UNSET


class OperatorQueryFieldsEnum(str, Enum):
    ALL = FIELDS_ALL
    OPERATOR_ID = 'operator_id'
    OPERATOR_NAME = 'operator_name'
    ALLOCATED_NODE_NUMBERS = 'allocated_node_numbers'
    # TODO: how to handle nested stuff?
    # ALLOCATOR = 'allocator'
    # ALLOCATOR_ALLOCATOR_ID = 'allocator.allocator_id'
    # ALLOCATOR_ALLOCATOR_NAME = 'allocator.allocator_name'


class OperatorQueryRequest(QueryRequest):
    """Specifies query parameters for querying operators."""

    fields: Annotated[
        list[OperatorQueryFieldsEnum] | None,
        create_fields_param([e.value for e in OperatorQueryFieldsEnum]),
    ] = None


class OperatorCreateSchema(BaseStruct):
    """Specifies the request body for creating an operator."""

    operator_name: Annotated[str, OperatorNameMeta]
    allocator_id: Annotated[int, AllocatorIDMeta] = 0


class OperationEnum(str, Enum):
    UNION = 'union'
    UNION_ALT = '+'
    INTERSECTION = 'intersection'
    INTERSECTION_ALT = '*'
    DIFFERENCE = 'difference'
    DIFFERENCE_ALT = '-'


OperationMeta = Meta(
    title='Multirange Operation',
    description=(
        'Specifies how the range in the request body should be applied to the'
        " multirange of allocated node numbers. Symbols come from Postgres'"
        ' [multirange operators](https://www.postgresql.org/docs/current/functions-range.html):'
        ' `+` is `union`, `*` is `intersection`, and `-` is `difference`.'
    ),
    examples=['union'],
    extra_json_schema={
        'extra': {
            'oneOf': None,
            'type': OpenAPIType.STRING,
            'enum': [o.value for o in OperationEnum],
        }
    },
)


class UpdateAllocatedNodeNumbersSchema(BaseStruct):
    """Specifies the request body for updating operator's allocated
    node numbers.
    """

    operation: Annotated[OperationEnum | UnsetType, OperationMeta]
    lower: Annotated[int, LowerMeta] = 0
    upper: Annotated[int, UpperMeta] = NODE_NUMBER_MAX
    bounds: Annotated[RangeBoundsEnum | UnsetType, BoundsMeta] = (
        RangeBoundsEnum.LOWER_INC_UPPER_INC
    )

    def __post_init__(self):
        if (
            self.lower is not None
            and self.upper is not None
            and self.lower > self.upper
        ):
            raise SchemaValidationError(
                key='lower',
                msg=(
                    f'Lower bound {self.lower} cannot be greater than upper'
                    f' bound {self.upper}'
                ),
            )


class OperatorUpdateSchema(BaseStruct):
    """Specifies the request body for updating an operator."""

    operator_name: Annotated[str, OperatorNameMeta] = UNSET
    allocator_id: Annotated[int, AllocatorIDMeta] = UNSET

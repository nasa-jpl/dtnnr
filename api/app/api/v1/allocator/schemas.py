from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Annotated

from litestar.params import Parameter
from msgspec import UNSET, Meta

from app.fields import ALLOCATOR_ID_MAX
from app.schemas import (
    BaseStruct,
    nonnegative_bigint_pathparam_schema_extra,
    nonnegative_bigint_reqbody_extra_json_schema,
)

from ..schemas import (
    FIELDS_ALL,
    QueryRequest,
    create_fields_param,
)

if TYPE_CHECKING:
    from app.models import Allocator

# The ID and name examples come from section 3.2.1 of RFC 9758
AllocatorIDMeta = Meta(
    ge=0,
    # Allocator identifiers >= 2^32 are reserved by RFC 9758, so maybe
    # lower this `le` value later?
    le=ALLOCATOR_ID_MAX,
    title='Allocator ID',
    description=(
        "ID of the allocator from the 'ipn' Scheme URI Allocator Identifiers registry"
    ),
    examples=['974994'],
    extra_json_schema=nonnegative_bigint_reqbody_extra_json_schema,
)

AllocatorNameMeta = Meta(
    title='Allocator Name',
    description=(
        "Name of the allocator from the 'ipn' Scheme URI Allocator Identifiers registry"
    ),
    examples=['Org D'],
)

AllocatorIDParam = Parameter(
    ge=AllocatorIDMeta.ge,
    le=AllocatorIDMeta.le,
    title=AllocatorIDMeta.title,
    description=AllocatorIDMeta.description,
    schema_extra=nonnegative_bigint_pathparam_schema_extra,
)


def to_minimal_schema(allocator: Allocator) -> AllocatorReadMinimalSchema:
    return AllocatorReadMinimalSchema(
        allocator_id=str(allocator.allocator_id),
        allocator_name=allocator.allocator_name,
    )


class AllocatorReadMinimalSchema(BaseStruct):
    """Minimal representation of an allocator in responses."""

    allocator_id: Annotated[
        str,
        Meta(
            title=AllocatorIDMeta.title,
            description=AllocatorIDMeta.description,
            examples=AllocatorIDMeta.examples,
        ),
    ] = UNSET
    allocator_name: Annotated[str, AllocatorNameMeta] = UNSET


import app.api.v1.node.schemas as node_schemas
import app.api.v1.operator.schemas as operator_schemas


def to_schema(allocator: Allocator) -> AllocatorSchema:
    return AllocatorSchema(
        allocator_id=str(allocator.allocator_id),
        allocator_name=allocator.allocator_name,
        operators=[
            operator_schemas.to_operator_minimal_schema(o) for o in allocator.operators
        ],
        nodes=[node_schemas.to_node_with_allocator_schema(n) for n in allocator.nodes],
    )


class AllocatorSchema(BaseStruct):
    """Representation of an allocator in repsonses."""

    allocator_id: Annotated[
        str,
        Meta(
            title=AllocatorIDMeta.title,
            description=AllocatorIDMeta.description,
            examples=AllocatorIDMeta.examples,
        ),
    ] = UNSET
    allocator_name: Annotated[str, AllocatorNameMeta] = UNSET
    operators: Annotated[
        list[operator_schemas.OperatorReadMinimalSchema],
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


# TODO: thinking of something like this for response:
# {
#     allocator_id: string,
#     allocator_name: string,
#     primary_contact: {
#         contact_id: string,
#         contact_name: string,
#     },
#     operators_count: int,
#     operators: [
#         {
#             operator_id: string,
#             operator_name: string,
#             allocated_node_numbers: [
#                 {
#                     lower: int,
#                     upper: int,
#                     bounds: string enum with () [) (] []
#                 },
#             ],
#         },
#     ],
#     nodes_count: int,
#     nodes: [
#         {
#             node_id: string,
#             node_number: int,
#         },
#     ],
# }


class AllocatorQueryFieldsEnum(str, Enum):
    ALL = FIELDS_ALL
    ALLOCATOR_ID = 'allocator_id'
    ALLOCATOR_NAME = 'allocator_name'


class AllocatorQuerySortEnum(str, Enum):
    ALLOCATOR_ID = 'allocator_id'
    # TODO: support allocator_name, operators_count, and nodes_count ?


class AllocatorQueryRequest(QueryRequest):
    """Specifies query parameters for querying allocators."""

    fields: Annotated[
        list[AllocatorQueryFieldsEnum] | None,
        create_fields_param([e.value for e in AllocatorQueryFieldsEnum]),
    ] = None
    # TODO: disable sorting parameters until I can think of an actual use case
    # sort: Annotated[AllocatorQuerySortEnum, SortParameter] = (
    #     AllocatorQuerySortEnum.ALLOCATOR_ID
    # )


class AllocatorCreateSchema(BaseStruct):
    """Specifies the request body for creating an allocator."""

    allocator_id: Annotated[int, AllocatorIDMeta]
    allocator_name: Annotated[str, AllocatorNameMeta]


class AllocatorUpdateSchema(BaseStruct):
    """Specifies the request body for updating an allocator."""

    allocator_id: Annotated[int, AllocatorIDMeta] = UNSET
    allocator_name: Annotated[str, AllocatorNameMeta] = UNSET

from __future__ import annotations

import operator
from enum import Enum
from functools import reduce
from typing import TYPE_CHECKING, Annotated

from litestar.params import Parameter
from msgspec import UNSET, Meta

from app.fields import CL_PROTOCOL_ID_MAX
from app.models import (
    cli_command_with_required_protocol_name,
    known_cl_protocol_name_to_class,
)
from app.problem_details import SchemaValidationError
from app.schemas import (
    BaseStruct,
    nonnegative_bigint_pathparam_schema_extra,
    nonnegative_bigint_reqbody_extra_json_schema,
)

from ..node.schemas import NodeIDMeta

if TYPE_CHECKING:
    from app.models import ClProtocol


ClProtocolIDMeta = Meta(
    ge=0,
    le=CL_PROTOCOL_ID_MAX,
    title='CL Protocol ID',
    description='Surrogate key to identify a CL protocol',
    examples=['16', '62'],
    extra_json_schema=nonnegative_bigint_reqbody_extra_json_schema,
)

ClProtocolIDParam = Parameter(
    ge=ClProtocolIDMeta.ge,
    le=ClProtocolIDMeta.le,
    title=ClProtocolIDMeta.title,
    description=ClProtocolIDMeta.description,
    schema_extra=nonnegative_bigint_pathparam_schema_extra,
)


ClProtocolNameMeta = Meta(
    title='CL Protocol Name',
    description=(
        'A unique, case-sensitive, name identifying a CL protocol on a node.'
        ' This value maps onto the *`protocol_name`* argument from'
        ' `bprc(5) § PROTOCOL COMMANDS`.'
    ),
    examples=['ltp', 'tcp'],
)


class ClProtocolClassEnum(str, Enum):
    BP_BEST_EFFORT = 'BP_BEST_EFFORT'
    BP_RELIABLE = 'BP_RELIABLE'


cl_protocol_class_map: dict[ClProtocolClassEnum, int] = {
    ClProtocolClassEnum.BP_BEST_EFFORT.value: 2,
    ClProtocolClassEnum.BP_RELIABLE.value: 8,
}

cl_protocol_num_to_class_map: dict[int, ClProtocolClassEnum] = {
    v: k for k, v in cl_protocol_class_map.items()
}

ClProtocolClassPropertyMeta = Meta(
    min_length=1,
    max_length=len(ClProtocolClassEnum),
    title='CL Protocol Class',
    description=(
        'A set of values that describes the reliability of the CL protocol.'
        f' As of ION 4.1.4, `"{ClProtocolClassEnum.BP_BEST_EFFORT.value}"`'
        ' maps to the number'
        f' `{cl_protocol_class_map[ClProtocolClassEnum.BP_BEST_EFFORT.value]}`,'
        f' and `"{ClProtocolClassEnum.BP_RELIABLE.value}"` maps to the number'
        f' `{cl_protocol_class_map[ClProtocolClassEnum.BP_RELIABLE.value]}`.'
        ' The bitwise OR of these numerical values is what should be passed'
        ' for the *`protocol_class`* argument from'
        ' `bprc(5) § PROTOCOL COMMANDS`.'
    ),
    examples=[
        [
            ClProtocolClassEnum.BP_BEST_EFFORT.value,
            ClProtocolClassEnum.BP_RELIABLE.value,
        ],
        [ClProtocolClassEnum.BP_RELIABLE.value],
    ],
    extra_json_schema={
        'extra': {
            'minItems': 1,
            'maxItems': len(ClProtocolClassEnum),
            # We don't actually validate uniqueness, we just deserialize as set,
            # but being true makes it more clear what users should send.
            'uniqueItems': True,
        }
    },
)


def protocol_class_int_to_arr(protocol_class: int) -> list[str]:
    # Can't use set() since set() isn't JSON serializable
    res = list()
    while protocol_class > 0:
        lsb = protocol_class & -protocol_class
        if (class_str := cl_protocol_num_to_class_map.get(lsb)) is not None:
            res.append(class_str)
        protocol_class -= lsb
    return res


def protocol_class_arr_to_int(protocol_class: set[str]) -> int:
    res = 0
    for s in protocol_class:
        res |= cl_protocol_class_map[s]
    return res


def to_cl_protocol_without_node_id_schema(
    cl_protocol: ClProtocol,
) -> ClProtocolWithoutNodeIdSchema:
    return ClProtocolWithoutNodeIdSchema(
        cl_protocol_id=str(cl_protocol.cl_protocol_id),
        cl_protocol_name=cl_protocol.cl_protocol_name,
        cl_protocol_class=protocol_class_int_to_arr(cl_protocol.cl_protocol_class),
    )


class ClProtocolWithoutNodeIdSchema(BaseStruct):
    """Representation of a CL protocol in responses where node_id is
    redundant.
    """

    cl_protocol_id: Annotated[
        str,
        Meta(
            title=ClProtocolIDMeta.title,
            description=ClProtocolIDMeta.description,
            examples=ClProtocolIDMeta.examples,
        ),
    ]
    cl_protocol_name: Annotated[str, ClProtocolNameMeta]
    cl_protocol_class: Annotated[set[ClProtocolClassEnum], ClProtocolClassPropertyMeta]


def to_cl_protocol_schema(cl_protocol: ClProtocol) -> ClProtocolSchema:
    return ClProtocolSchema(
        cl_protocol_id=str(cl_protocol.cl_protocol_id),
        cl_protocol_name=cl_protocol.cl_protocol_name,
        cl_protocol_class=protocol_class_int_to_arr(cl_protocol.cl_protocol_class),
        node_id=str(cl_protocol.node_id),
    )


class ClProtocolSchema(ClProtocolWithoutNodeIdSchema):
    """Representation of a CL protocol in responses."""

    node_id: Annotated[
        str,
        Meta(
            title=NodeIDMeta.title,
            description=NodeIDMeta.description,
            examples=NodeIDMeta.examples,
        ),
    ]


KNOWN_PROTOCOLS_STRING = ', '.join(
    [
        f'{
            "and " if p_name == cli_command_with_required_protocol_name[-1][1] else ""
        }`"{p_name}"`'
        for _, p_name in cli_command_with_required_protocol_name
    ]
)


def get_class_to_cl_protocol_names_dict() -> dict[int, list[str]]:
    d = {}
    for p_name, p_class in known_cl_protocol_name_to_class.items():
        if p_class in d:
            d[p_class].append(p_name)
        else:
            d[p_class] = [p_name]
    return d


def create_csv_names(protocol_class: int, conjunction: str = 'or') -> str:
    d = get_class_to_cl_protocol_names_dict()
    names = d[protocol_class]
    names_len = len(names)
    if names_len == 1:
        return f'`"{names[0]}"`'
    return f'{", ".join(map(lambda n: f'`"{n}"`', names[:-1]))} {conjunction} `"{
        names[-1]
    }"`'


CL_PROTOCOL_CLASS_DEFAULT_VALUES_DESC = (
    'Default value depends on the value of the `cl_protocol_name` property:'
    '<ul>'
    '</p></li>'
    f'{
        "".join(
            [
                "<li><p>If `cl_protocol_name` is"
                f" {
                    create_csv_names(
                        reduce(
                            operator.or_,
                            [cl_protocol_class_map[s] for s in p_class_strings],
                        )
                    )
                },"
                f" the default value is `[{
                    ', '.join(map(lambda s: f'"{s}"', p_class_strings))
                }]`."
                "</p></li>"
                for p_class_strings in (
                    [ClProtocolClassEnum.BP_RELIABLE.value],
                    [
                        ClProtocolClassEnum.BP_BEST_EFFORT.value,
                        ClProtocolClassEnum.BP_RELIABLE.value,
                    ],
                )
            ]
        )
    }'
    '<li><p>Otherwise, the default value is'
    f' `["{ClProtocolClassEnum.BP_BEST_EFFORT.value}"]`.</p></li>'
    '</ul>'
)

UPDATE_CL_PROTOCOL_CLASS_OMITTED_DESC = (
    'If the `cl_protocol_class` property is not defined in the request body, then'
    ' the value depends on the following conditions:'
    '<ul>'
    f'{
        "".join(
            [
                "<li><p>If `cl_protocol_name` is"
                f" {
                    create_csv_names(
                        reduce(
                            operator.or_,
                            [cl_protocol_class_map[s] for s in p_class_strings],
                        )
                    )
                },"
                f" the default value is `[{
                    ', '.join(map(lambda s: f'"{s}"', p_class_strings))
                }]`."
                "</p></li>"
                for p_class_strings in (
                    [ClProtocolClassEnum.BP_BEST_EFFORT.value],
                    [ClProtocolClassEnum.BP_RELIABLE.value],
                    [
                        ClProtocolClassEnum.BP_BEST_EFFORT.value,
                        ClProtocolClassEnum.BP_RELIABLE.value,
                    ],
                )
            ]
        )
    }'
    '<li><p>Otherwise, the value will be the current `cl_protocol_class` value'
    ' of the resource.</p></li>'
    '</ul>'
)

ClProtocolClassPropertyCreateMeta = Meta(
    min_length=ClProtocolClassPropertyMeta.min_length,
    max_length=ClProtocolClassPropertyMeta.max_length,
    title=ClProtocolClassPropertyMeta.title,
    description=(
        f'{ClProtocolClassPropertyMeta.description}<br />'
        '<br />'
        f'{CL_PROTOCOL_CLASS_DEFAULT_VALUES_DESC}'
    ),
    examples=ClProtocolClassPropertyMeta.examples,
    extra_json_schema=ClProtocolClassPropertyMeta.extra_json_schema,
)

ClProtocolClassPropertyUpdateMeta = Meta(
    min_length=ClProtocolClassPropertyMeta.min_length,
    max_length=ClProtocolClassPropertyMeta.max_length,
    title=ClProtocolClassPropertyMeta.title,
    description=(
        f'{ClProtocolClassPropertyMeta.description}<br />'
        '<br />'
        f'{UPDATE_CL_PROTOCOL_CLASS_OMITTED_DESC}'
    ),
    examples=ClProtocolClassPropertyMeta.examples,
    extra_json_schema=ClProtocolClassPropertyMeta.extra_json_schema,
)


def protocol_to_class_set(name: str) -> set[ClProtocolClassEnum]:
    p_class = known_cl_protocol_name_to_class.get(name, 8)
    return set(protocol_class_int_to_arr(p_class))


class ClProtocolCreateSchema(BaseStruct):
    """Specifies the request body for creating a CL protocol."""

    cl_protocol_name: Annotated[str, ClProtocolNameMeta]
    cl_protocol_class: Annotated[
        set[ClProtocolClassEnum], ClProtocolClassPropertyCreateMeta
    ] = UNSET

    def __post_init__(self):
        if not (1 <= len(self.cl_protocol_name.encode()) <= 15):
            raise SchemaValidationError(
                key='cl_protocol_name',
                msg='Length in bytes must be in the inclusive range [1, 15]',
            )
        if self.cl_protocol_class is UNSET:
            self.cl_protocol_class = protocol_to_class_set(self.cl_protocol_name)


class ClProtocolUpdateSchema(BaseStruct):
    """Specifies the request body for updating a CL protocol."""

    cl_protocol_name: Annotated[str, ClProtocolNameMeta] = UNSET
    cl_protocol_class: Annotated[
        set[ClProtocolClassEnum], ClProtocolClassPropertyUpdateMeta
    ] = UNSET

    def __post_init__(self):
        if self.cl_protocol_name is not UNSET and not (
            1 <= len(self.cl_protocol_name.encode()) <= 15
        ):
            raise SchemaValidationError(
                key='cl_protocol_name',
                msg='Length in bytes must be in the inclusive range [1, 15]',
            )
        if (
            self.cl_protocol_class is UNSET
            and self.cl_protocol_name in known_cl_protocol_name_to_class
        ):
            self.cl_protocol_class = protocol_to_class_set(self.cl_protocol_name)

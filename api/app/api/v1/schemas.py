from __future__ import annotations

from enum import Enum
from typing import Annotated, Generic, TypeVar

from litestar.openapi.spec.enums import OpenAPIType
from litestar.params import Parameter
from msgspec import UNSET, Meta

from app.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.schemas import BaseStruct

T = TypeVar('T')

FIELDS_ALL = '*'
GENERIC_QUERY_PARAM_USAGE_NOTE = (
    'To use the default value for a query parameter, omit the parameter from'
    ' the request URL. That is, to use the default `max_page_size`, do not use'
    ' a query string of `max_page_size=` since this is interpreted as assigning'
    ' the empty string `""` as the value for `max_page_size`.'
    # This is consistent with how the URLSearchParams API works
    # https://developer.mozilla.org/en-US/docs/Web/API/URLSearchParams
)
GENERIC_RESPONSE_DESCRIPTION = 'Request fulfilled, representation follows'


def create_fields_param(enum: list[str] = None) -> Parameter:
    return Parameter(
        schema_extra={
            # Specify the default in `schema_extra` rather than `default` since
            # Litestar will warn that the msgspec.field.value doesn't match
            # Parameter.default but trying to set msgspec.field.value to a non-empty
            # mutable collection will raise a TypeError.
            'default': ['*'],
            # See comments above QueryRequest.fields below. Need to set these
            # values to clean up the generated OpenAPI schema.
            'oneOf': None,
            'type': OpenAPIType.ARRAY,
            'items': {'type': OpenAPIType.STRING, 'enum': enum},
        },
        description=(
            '<b>NOT IMPLEMENTED</b><br />'
            'List of fields to fetch for each item. Multiple fields are passed as'
            ' separate parameters (e.g., `fields=a&fields=b`). An explicit value'
            ' of `*` will return all fields.'
            # TODO: talk about dot notation
        ),
        required=False,
        # TODO: show examples?
    )


# N.b. until sorting different columns is supporting ONLY show the default
# sort column as the only available option in the enum
SortParameter = Parameter(description='Field to sort on', required=False)


class DirectionEnum(str, Enum):
    ASC = 'asc'
    DESC = 'desc'


Direction = Annotated[DirectionEnum, Parameter(description='Direction to sort by')]

MaxPageSize = Annotated[
    int,
    Parameter(
        # Should validate ge=0, but don't validate less than. If someone passes
        # a number that's greater than the max we support, then coerce the value
        # down to max permitted size
        ge=0,
        required=False,
        description=(
            'Maximum number of results to return. If unset or 0, a default value'
            f' of {DEFAULT_PAGE_SIZE} is used. Values above {MAX_PAGE_SIZE} will'
            f' be coerced to {MAX_PAGE_SIZE}.'
        ),
        # ge=0 doesn't show in the OpenAPI schema, so add it ourselves
        schema_extra={'minimum': 0},
    ),
]

PageTokenParameter = Parameter(
    # Litestar will validate that the type of this default value matches
    # the type annotation. This is annoying for us because we don't want
    # a default value to be listed in the documentation. But if we want
    # that, then we need to have `None`. But that means we need a
    # `str | None` type when we just want `str`. So we need to set
    # 'oneOf' to None and 'type' to 'string' in `schema_extra`.
    # N.b., trying to have the type annotation as just `str` and default
    # value as `''` won't work since trying to set 'default' to None in
    # `schema_extra` won't replace the empty string.
    schema_extra={
        'oneOf': None,
        'type': OpenAPIType.STRING,
    },
    required=False,
    description=(
        'Page token provided by a previous query request. Provide the given'
        ' `previous_page_token` or `next_page_token` to retrieve the previous'
        ' or next page, respectively. If unset, retrieve the first page. If'
        ' the literal string `last` is provided, retrieve the last page.'
        # AIP-158 says it's unnecesary to document that tokens expire
    ),
)

PageTokenQuery = Annotated[
    str | None,
    Parameter(
        schema_extra=PageTokenParameter.schema_extra,
        required=PageTokenParameter.required,
        description=(
            f'{PageTokenParameter.description}<br />'
            '<br />'
            'When using a page token provided by a previous query request, the'
            ' `filter` parameter must match the previous request.'
        ),
    ),
]


class PaginatedRequest(BaseStruct):
    """Specifies query parameters for pagination."""

    max_page_size: MaxPageSize = DEFAULT_PAGE_SIZE
    page_token: Annotated[str | None, PageTokenParameter] = None


class QueryRequest(BaseStruct):
    """Base container for storing query parameters for query operations.

    Subclasses should define `fields` and annotate with at least the
    information found in `create_fields_param()`.
    """

    # Unlike `fields` and `sort` which should be Annotated in QueryRequest
    # subclasses since they should use enums, `filter` will have a complex
    # syntax that will just be presented as a string.
    # TODO: consider making this a function so you can pass a custom description
    # or examples in subclasses?
    filter: Annotated[
        str | None,
        Parameter(
            # See comment for PageTokenParameter to see why we use `str | None`,
            # `None` as the default value, and this `schema_extra`
            schema_extra={
                'oneOf': None,
                'type': OpenAPIType.STRING,
            },
            description=(
                '<b>NOT IMPLEMENTED</b><br />'
                'Search keywords and qualifiers to filter over the collection'
            ),
            required=False,
        ),
    ] = None
    # We can't use msgspec.field(default_factory) (nor `[]` which is syntatic
    # sugar for the same thing). It'll have the type `msgspec._core.Default`
    # which raises a validation error since it doesn't match with the expected
    # `list` type.
    # Workaround is to use `None` as default value and change it to `['*']`
    # in __post_init__().
    fields: Annotated[list[str] | None, create_fields_param()] = None
    """Keep default value as `None` in subclasses to use the default
    value `['*']`
    """

    # TODO: disable sorting parameters until I can think of an actual use case
    # sort: Annotated[str, SortParameter] = None
    # direction: Direction = DirectionEnum.ASC
    max_page_size: MaxPageSize = DEFAULT_PAGE_SIZE
    page_token: PageTokenQuery = None

    def __post_init__(self):
        if self.fields is None:
            self.fields = ['*']


PrevPageTokenMeta = Meta(
    title='Previous Page Token',
    description=(
        'If this field is not present in the response, then there are no'
        ' more resources in the previous direction'
    ),
    examples=[
        'gAAAAAAfhbuQ0bR_0dE7aMS8-P8qlPiRA2jMRWg1dwAMv3tzSfAF0Bfl1IDGKi'
        '_ke-4fj8BqiwqGRh8magXsSoCitmbg3QduvrQ023y3x7cU_boraJM8AA2d8kYt'
        'uHMOLdh4XqX9AwsL'
    ],
)

NextPageTokenMeta = Meta(
    title='Next Page Token',
    description=(
        'If this field is not present in the response, then there are no'
        ' more resources in the next direction'
    ),
    examples=[
        'gAAAAAAfhbuQWaxDAF08IyXCZENV1Z0H0aDRlO5NV3_ELyBvO0oSCPqzRPPSR1'
        'Igq_2zABwGu0fdou5NYMBO2wmvlFIuAv9aWVEfzlvH2t9ECisLNmr-6opTnzuk'
        '9gI3kUh1Fzg9UFkW'
    ],
)


class QueryResponse(BaseStruct, Generic[T]):
    """Container for data returned from a query."""

    items: Annotated[
        list[T],
        Meta(
            title='Items', description='Array of objects representing the query results'
        ),
    ] = []
    prev_page_token: Annotated[str, PrevPageTokenMeta] = UNSET
    next_page_token: Annotated[str, NextPageTokenMeta] = UNSET

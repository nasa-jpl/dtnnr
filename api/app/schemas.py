from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING

import msgspec
from litestar.datastructures import ResponseHeader
from litestar.openapi.spec import OpenAPIHeader, OpenAPIType, Operation, Schema
from msgspec import Struct

from app.fields import BIGINT_MAX, INT_MAX

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from litestar.openapi.spec import OpenAPI


class BaseStruct(Struct):
    def to_dict(self) -> dict[str, Any]:
        """Return serialized struct as a dictionary.

        In views tests, doing an equality comparison of this value with
        the JSON returned in responses is a tautology. That's just
        checking if a msgspec serialized struct is equal to a msgspec
        serialized struct.

        This method is useful when you want to check when something is
        present in a collection. E.g., tests involving pagination just
        care about whether the right number of resources were returned,
        not whether the representation correctly follows the documented
        schema.
        """
        return json.loads(
            msgspec.json.encode(self, enc_hook=bigint_enc_hook).decode('utf-8')
        )


nonnegative_bigint_pathparam_schema_extra = {
    'minimum': 0,
    'maximum': str(BIGINT_MAX),
    'type': 'integer',
    'format': 'int64',
}
"""Pass this as the `schema_extra` value of `Parameter` for non-negative
big integers in path parameters.

This should not affect the validation set by Parameter, it only affects
the generated documentation.
"""

# NOTE: We need to use Meta instead of Parameter for Structs because validation
# from Parameter is not respected by Structs if schema_extra is defined.

nonnegative_bigint_reqbody_extra_json_schema = {
    # 'extra' is what will be a ParameterKwarg's `schema_extra`
    # See litestar/plugins/core/_msgspec's kwarg_definition_from_field
    'extra': {
        # If we don't set these, Litestar will try to set them according to
        # the values of the msgspec.Meta.
        'minimum': None,  # 0,
        'maximum': None,  # str(BIGINT_MAX),
        'type': None,  # 'integer',
        # Setting the 'int64' format (or setting a minimum, or maximum) will
        # try to render an extra 'integer' type in the UI plugins, so keep
        # them null. It looks okay with Redoc though (integer will repeat the
        # Meta's description, but the string will use the specified description)
        # so if you're only using that, then feel free to use it.
        'format': None,  # 'int64',
        'oneOf': [
            Schema(
                type='integer',
                minimum=0,
                maximum=str(BIGINT_MAX),
                format='int64',
            ),
            Schema(
                type='string',
                minimum=0,
                maximum=str(BIGINT_MAX),
                description='There will be an attempt to cast strings into an integer',
                # Don't use `format` for Rapidoc since it replaces string with int64
                format='int64',
            ),
        ],
    }
}
"""Pass this as the `extra_json_schema` value of `msgspec.Meta` for
non-negative big integers in request bodies.

This should not affect the validation set by Meta, it only affects the
generated documentation.
"""

nullable_nonnegative_bigint_reqbody_extra_json_schema = deepcopy(
    nonnegative_bigint_reqbody_extra_json_schema
)
"""Pass this as the `extra_json_schema` value of `msgspec.Meta` for
nullable non-negative big integers in request bodies.

This should not affect the validation set by Meta, it only affects the
generated documentation.
"""
nullable_nonnegative_bigint_reqbody_extra_json_schema['extra']['oneOf'].append(
    Schema(type='null')
)

nullable_positive_bigint_reqbody_extra_json_schema = {
    'extra': {
        'minimum': None,
        'maximum': None,
        'type': None,
        'format': None,
        'oneOf': [
            Schema(
                type='integer',
                minimum=1,
                maximum=str(BIGINT_MAX),
                format='int64',
            ),
            Schema(
                type='string',
                minimum=1,
                maximum=str(BIGINT_MAX),
                description='There will be an attempt to cast strings into an integer',
                format='int64',
            ),
            Schema(type='null'),
        ],
    }
}
"""Pass this as the `extra_json_schema` value of `msgspec.Meta` for
nullable positive big integers in request bodies.

This should not affect the validation set by Meta, it only affects the
generated documentation.
"""


nonnegative_int_reqbody_extra_json_schema = {
    # 'extra' is what will be a ParameterKwarg's `schema_extra`
    # See litestar/plugins/core/_msgspec's kwarg_definition_from_field
    'extra': {
        # If we don't set these, Litestar will try to set them according to
        # the values of the msgspec.Meta.
        'minimum': None,  # 0,
        'maximum': None,  # str(INT_MAX),
        'type': None,  # 'integer',
        # Setting the 'int32' format (or setting a minimum, or maximum) will
        # try to render an extra 'integer' type in the UI plugins, so keep
        # them null. It looks okay with Redoc though (integer will repeat the
        # Meta's description, but the string will use the specified description)
        # so if you're only using that, then feel free to use it.
        'format': None,  # 'int32',
        'oneOf': [
            Schema(
                type='integer',
                minimum=0,
                maximum=INT_MAX,
                format='int32',
            ),
            Schema(
                type='string',
                minimum=0,
                maximum=INT_MAX,
                description='There will be an attempt to cast strings into an integer',
                # Don't use `format` for Rapidoc since it replaces string with int32
                format='int32',
            ),
        ],
    }
}
"""Pass this as the `extra_json_schema` value of `msgspec.Meta` for
non-negative integers in request bodies.

This should not affect the validation set by Meta, it only affects the
generated documentation.
"""

nullable_nonnegative_int_reqbody_extra_json_schema = deepcopy(
    nonnegative_int_reqbody_extra_json_schema
)
"""Pass this as the `extra_json_schema` value of `msgspec.Meta` for
nullable non-negative integers in request bodies.

This should not affect the validation set by Meta, it only affects the
generated documentation.
"""
nullable_nonnegative_int_reqbody_extra_json_schema['extra']['oneOf'].append(
    Schema(type='null')
)


nullable_uint16_reqbody_extra_json_schema = {
    'extra': {
        'minimum': None,
        'maximum': None,
        'type': None,
        'format': None,
        'oneOf': [
            Schema(
                type='integer',
                minimum=0,
                maximum=65536,
                format='uint16',
            ),
            Schema(
                type='string',
                minimum=0,
                maximum=65536,
                description='There will be an attempt to cast strings into an integer',
                format='uint16',
            ),
            Schema(type='null'),
        ],
    }
}
"""Pass this as the `extra_json_schema` value of `msgspec.Meta` for
nullable non-negative integers in request bodies.

This should not affect the validation set by Meta, it only affects the
generated documentation.
"""


nonnegative_bigint_resbody_extra_json_schema = {
    # 'extra' is what will be a ParameterKwarg's `schema_extra`
    # See litestar/plugins/core/_msgspec's kwarg_definition_from_field
    'extra': {
        # If we don't set these, Litestar will try to set them according to
        # the values of the msgspec.Meta.
        'minimum': None,  # 0,
        'maximum': None,  # str(BIGINT_MAX),
        'type': None,  # 'integer',
        # Setting the 'int64' format (or setting a minimum, or maximum) will
        # try to render an extra 'integer' type in the UI plugins, so keep
        # them null. It looks okay with Redoc though (integer will repeat the
        # Meta's description, but the string will use the specified description)
        # so if you're only using that, then feel free to use it.
        'format': None,  # 'int64',
        'oneOf': [
            Schema(
                type='integer',
                minimum=0,
                maximum=2**53 - 1,
                description='Numbers in [0, 2^53-1] are serialized as `integer`',
                format='int64',
            ),
            Schema(
                type='string',
                minimum=2**53,
                maximum=str(BIGINT_MAX),
                description='Numbers in [2^53, 2^63-1] are serialized as `string`',
                # Don't use `format` for Rapidoc since it replaces string with int64
                format='int64',
            ),
        ],
    }
}
"""Pass this as the `extra_json_schema` value of `msgspec.Meta` for
non-negative big integers in response bodies.
"""


nullable_nonnegative_bigint_resbody_extra_json_schema = deepcopy(
    nonnegative_bigint_resbody_extra_json_schema
)
"""Pass this as the `extra_json_schema` value of `msgspec.Meta` for
nullable non-negative big integers in response bodies.

This should not affect the validation set by Meta, it only affects the
generated documentation.
"""
nullable_nonnegative_bigint_resbody_extra_json_schema['extra']['oneOf'].append(
    Schema(type='null')
)


string_or_null_extra_json_schema = {
    'extra': {
        'oneOf': [
            {
                'type': OpenAPIType.STRING,
            },
            {
                'type': OpenAPIType.NULL,
            },
        ]
    }
}
"""Pass this as the `extra_json_schema` value for `msgspec.Meta` for
properties that should have these two types.

We only need this where `str | None` does not work correctly, namely
when we're using JSON_NULL as the default value which will add a
superfluous `default` property for the first object in `oneOf`.
"""


LocationHeader = ResponseHeader(
    name='Location',
    value='',  # Need a str value so type is added
    description='URI of newly created resource',
    documentation_only=True,
)

ContentLocationHeader = ResponseHeader(
    name='Content-Location',
    value='',  # Need a str value so type is added
    description='URI of resource corresponding to representation in payload',
    documentation_only=True,
)


def custom_reqbody(
    description: str | None = None, required: bool = False
) -> Callable[[Operation], None]:
    """Pass the return value of this function to `custom_operation`
    to modify the `description` and `required` fields of the generated
    OpenAPI Request Body Object.

    If you pass `True` for `required`, then you should also use
    `app.problem_details.required_request_body_guard` in the decorator's
    `guards` argument so that the error message for missing / empty
    request bodies is more informative.
    """

    def _f(op: Operation) -> None:
        op.request_body.description = description
        op.request_body.required = required

    return _f


def content_location_header_for_200(op: Operation) -> None:
    """Use this function as an argument for `custom_operation` to add a
    `Content-Location` header for the 200 OK response.
    """
    ok_response = op.responses.get('200')
    if not ok_response:
        return
    if not ok_response.headers:
        ok_response.headers = {}
    if ok_response.headers.get(ContentLocationHeader.name):
        ok_response.headers[
            ContentLocationHeader.name
        ].description = LocationHeader.description
        ok_response.headers[ContentLocationHeader.name].schema = Schema(
            type=OpenAPIType.STRING
        )
    else:
        ok_response.headers[ContentLocationHeader.name] = OpenAPIHeader(
            schema=Schema(type=OpenAPIType.STRING),
            name=ContentLocationHeader.name,
            description=ContentLocationHeader.description,
        )


def custom_operation(*args: Callable[[Operation], None]) -> Operation:
    """Pass functions in `args` to modify the generated OpenAPI schema
    for a Operation.

    Pass the return value of this function to a route handler
    decorator's `operation_class` argument to modify the generated
    OpenAPI schema of the operation.

    `args` are functions that take in an
    `litestar.openapi.spec.Operation` and perform changes on the
    Operation.
    """

    @dataclass
    class CustomOperation(Operation):
        def __post_init__(self) -> None:
            for f in args:
                f(self)

    return CustomOperation


class JSONNull:
    pass


JSON_NULL = JSONNull()
"""Litestar uses `None` to denote when something is not set in their
internal OpenAPI class, so when preparing to convert from their class
to JSON, they cannot distinguish between `None` and unset. A value that
is `None` is excluded from conversion. This means you cannot set a
default value of `None` for Struct fields to get a literal `null` as
the default value in JSON.

Note that the conversion function itself does encode `None` as `null`.

Our workaround is to create a custom type that is not `None`, so it
won't be excluded from conversion to JSON, and then use a custom type
encoder to convert the custom type to `None` during JSON conversion so
that it will be encoded as `null`.
"""


def jsonnull_enc_hook(obj):
    if isinstance(obj, JSONNull):
        return None
    raise TypeError(f'Cannot encode objects of type {type(obj)}')


class bigint(int):
    pass


def bigint_enc_hook(obj):
    if isinstance(obj, bigint):
        if -(2**53 - 1) <= obj and obj <= (2**53 - 1):
            return int(obj)
        return str(obj)
    raise TypeError(f'Cannot encode objects of type {type(obj)}')


def remove_incorrect_defaults(openapi_schema: OpenAPI):
    """When Struct X uses Struct Y as the type for a field, setting a
    default value for that Struct field will set `default` of the
    generated `litestar.openapi.spec.Schema` to be the same value, if
    the schema based on Struct X is generated before the schema based on
    Struct Y is generated. If Struct Y was generated first, then the
    schema's default is `None` regardless of what we put in Struct X.

    Trying to use `Annotated` and `Meta` for the Struct Y type in Struct
    X does not fix this.

    Rather than trying to find a way for Litestar to generate this
    correctly, it's probably easier to just explicitly set it to `None`.
    """
    from app.api.v1.link.schemas import LinkRfCreateSchema

    openapi_schema.components.schemas[LinkRfCreateSchema.__name__].default = None

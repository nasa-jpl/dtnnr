from __future__ import annotations

from enum import Enum
from http import HTTPStatus
from typing import TYPE_CHECKING, Annotated, Any

from litestar._signature.types import ExtendedMsgSpecValidationError
from litestar.exceptions import HTTPException, ValidationException
from litestar.openapi.datastructures import ResponseSpec
from litestar.openapi.spec import Example
from litestar.plugins.problem_details import (
    ProblemDetailsConfig,
    ProblemDetailsException,
    ProblemDetailsPlugin,
)
from msgspec import UNSET, Meta

from app.config import INVALID_PAGE_TOKEN_MESSAGE

from .schemas import BaseStruct

if TYPE_CHECKING:
    from litestar import Request
    from litestar.handlers.base import BaseRouteHandler
    from msgspec import UnsetType


class ExtraSourceEnum(str, Enum):
    # litestar._signature.model.ErrorMessage makes `source` a Union of 'body'
    # and the elements of litestar.enums.ParamType (the other strings we have
    # here)
    BODY = 'body'
    PATH = 'path'
    QUERY = 'query'
    COOKIE = 'cookie'
    HEADER = 'header'


class ProblemDetailsExtraSchema(BaseStruct):
    # See ErrorMessage class from litestar._signature.model
    message: Annotated[str, Meta(description='Message about this value')] = UNSET
    key: Annotated[str, Meta(description='Value name')] = UNSET
    source: Annotated[ExtraSourceEnum, Meta(description='Value location')] = UNSET


class ProblemDetailsExceptionSchema(BaseStruct):
    status: Annotated[int, Meta(description='HTTP status code')]
    title: Annotated[
        str, Meta(description='Short, human-readable summary of the problem type')
    ]
    detail: Annotated[
        str,
        Meta(
            description=(
                'Human-readable explanation specific to this occurrence of the problem'
            )
        ),
    ]
    extra: Annotated[
        list[ProblemDetailsExtraSchema | Any],
        Meta(description='Additional information about specific values'),
    ] = UNSET


def create_400_response_spec(
    description: str = 'Bad request',
    client_error_detail_example: str = None,
    client_error_extra: list[ProblemDetailsExtraSchema | Any] | UnsetType = UNSET,
    include_validation_error: bool = False,
    validation_detail_example: str = 'Validation failed for opreation',
    validation_message_example: str = 'Explanation for some path param error',
    validation_key_example: str = 'id',
    validation_source_example: str = 'path',
) -> ResponseSpec:
    # Include the explanation for the possible errors in `description` rather
    # than specifying a description in the example (an "example" description
    # is not the same as the actual description)
    examples = (
        []
        if client_error_detail_example is None
        else [
            Example(
                summary='Client Error',
                value=ProblemDetailsExceptionSchema(
                    status=400,
                    title='Bad Request',
                    detail=client_error_detail_example,
                    extra=client_error_extra,
                ),
            ),
        ]
    )
    if include_validation_error:
        examples.append(
            Example(
                summary='Validation Error',
                value=ProblemDetailsExceptionSchema(
                    status=400,
                    title='Validation Error',
                    detail=validation_detail_example,
                    extra=[
                        ProblemDetailsExtraSchema(
                            message=validation_message_example,
                            key=validation_key_example,
                            source=validation_source_example,
                        )
                    ],
                ),
            ),
        )
    return ResponseSpec(
        generate_examples=False,
        data_container=ProblemDetailsExceptionSchema,
        description=description,
        media_type=ProblemDetailsException._PROBLEM_DETAILS_MEDIA_TYPE,
        examples=examples,
    )


def pagination_400_response_spec(path: str) -> ResponseSpec:
    return create_400_response_spec(
        description='Bad request syntax, validation error, or invalid page token',
        client_error_detail_example=INVALID_PAGE_TOKEN_MESSAGE,
        include_validation_error=True,
        validation_detail_example=(
            f'Validation failed for GET {path}?max_page_size=-1'
        ),
        validation_message_example='Expected `int` >= 0',
        validation_key_example='max_page_size',
        validation_source_example='query',
    )


def create_404_response_spec(
    description: str = 'Not found',
    detail_example: str = 'Cannot find the requested resource',
    extra: Any = UNSET,
) -> ResponseSpec:
    # Include the explanation for the possible errors in `description` rather
    # than specifying a description in the example (an "example" description
    # is not the same as the actual description)
    return ResponseSpec(
        generate_examples=False,
        data_container=ProblemDetailsExceptionSchema,
        description=description,
        media_type=ProblemDetailsException._PROBLEM_DETAILS_MEDIA_TYPE,
        examples=[
            Example(
                summary='Client Error',
                value=ProblemDetailsExceptionSchema(
                    status=404,
                    title='Not Found',
                    detail=detail_example,
                    extra=extra,
                ),
            )
        ],
    )


async def required_request_body_guard(request: Request, _: BaseRouteHandler) -> None:
    """Add this function to a route handler decorator's `guards`
    argument to make the error message for missing / empty
    request bodies more informative.

    By default, Litestar shows
    ```json
    "extra": [
        {
            "message": "'data'",
            "key": "data",
            "source": "body"
        }
    ]
    ```
    With this guard, the message will be
    ```json
    "extra": [
        {
            "message": "Expected non-empty request body",
            "source": "body"
        }
    ]
    ```
    """
    # Implement this as a guard instead of a before_request handler
    # since we don't need to return any data (and we can have multiple
    # guards but not multiple before_request handlers)
    if await request.body() == b'':
        path = str(request.url).removeprefix(str(request.base_url))
        raise ValidationException(
            detail=f'Validation failed for {request.method} /{path}',
            extra=[
                ProblemDetailsExtraSchema(
                    message='Expected non-empty request body', source='body'
                ).to_dict()
            ],
        )


class SchemaValidationError(ExtendedMsgSpecValidationError):
    """Raising a `TypeError` or `msgspec.ValidationError` in
    `__post_init__` of Structs uses "data" as the value for "key" in the
    error message.

    E.g.,
    ```json
    "extra": [
        {
            "message": "`contact_name` cannot consist solely of whitespace",
            "key": "data",
            "source": "body"
        }
    ]
    ```
    Also, our `_validation_exception_to_problem_detail_exception` will
    remove the "key".

    To make the message more useful, we really want
    ```json
    "extra": [
        {
            "message": "`contact_name` cannot consist solely of whitespace",
            "key": "contact_name",
            "source": "body"
        }
    ]
    ```
    """

    def __init__(self, key: str, msg: str, in_body: bool = True):
        # This workaround abuses the internal class method from Litestar's
        # _signature.model.SignatureModel.parse_values_from_connection_kwargs.
        # Private implementations may change, so don't expect this to work
        # forever.
        # We can try rewriting this to inherit from ProblemDetailsException
        # or litestar.exceptions.ValidationException, but you'd need more
        # work to get the problem details 'detail' property match the one
        # generated by Litestar.
        super().__init__(
            [
                {
                    # 'loc' is converted to 'keys'
                    # Prepend with 'data.' so a 'source': 'body' is added
                    'loc': [f'{"data." if in_body else ""}{key}'],
                    'msg': msg,
                }
            ]
        )


def _validation_exception_to_problem_detail_exception(
    exc: ValidationException,
) -> ProblemDetailsException:
    # Route handlers that accept a request body have a `data` parameter, so
    # when validation is done on the entire request body (e.g., passing an
    # array when an object is expected), the validation exception's "key"
    # is shown as "data" which is confusing for users since they don't use
    # the "data" name anywhere.
    if isinstance(exc.extra, list):
        for x in exc.extra:
            if isinstance(x, dict) and x.get('key') == 'data':
                x.pop('key')
    return ProblemDetailsException(
        status_code=exc.status_code,
        title='Validation Error',
        detail=exc.detail,
        extra=exc.extra,
    )


def _http_exception_to_problem_detail_exception(
    exc: HTTPException,
) -> ProblemDetailsException:
    title = HTTPStatus(exc.status_code).phrase
    detail = exc.detail
    # If detail doesn't differ from the HTTPStatus.phrase, it's not
    # specified by us, so we should use a more descriptive string
    if title == detail:
        # We just replace the status codes that we know Litestar can return
        # from litestar.exceptions
        if exc.status_code == 400:
            detail = 'The request is invalid or malformed'
        elif exc.status_code == 401:
            detail = 'The request lacks valid authentication credentials'
        elif exc.status_code == 403:
            detail = (
                'Authentication succeeded, but user does not have permission for'
                ' the request'
            )
        elif exc.status_code == 404:
            detail = 'Cannot find the requested resource'
        elif exc.status_code == 405:
            detail = 'The target resource does not support this method'
        elif exc.status_code == 429:
            detail = 'Request limits have been exceeded'
        elif exc.status_code == 500:
            detail = (
                'An unexpected condition prevented the server from fulfilling'
                ' the request'
            )
        elif exc.status_code == 503:
            detail = 'Server is not ready to handle the request'
    return ProblemDetailsException(
        status_code=exc.status_code,
        title=title,
        detail=detail,
        extra=exc.extra,
    )


problem_details_plugin = ProblemDetailsPlugin(
    ProblemDetailsConfig(
        exception_to_problem_detail_map={
            ValidationException: _validation_exception_to_problem_detail_exception,
            HTTPException: _http_exception_to_problem_detail_exception,
        }
    )
)

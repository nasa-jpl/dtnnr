from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from litestar import Response, Router, patch, post
from litestar import delete as _delete
from litestar import get as _get
from litestar.di import Provide
from litestar.exceptions import (
    ClientException,
    InternalServerException,
    NotFoundException,
)
from msgspec import UNSET

from app.config import API_V1_PATH
from app.problem_details import (
    create_400_response_spec,
    create_404_response_spec,
    pagination_400_response_spec,
    required_request_body_guard,
)
from app.schemas import (
    ContentLocationHeader,
    LocationHeader,
    custom_operation,
    custom_reqbody,
)

from ..contact.schemas import (
    ContactAddSchema,
    ContactIDParam,
    ContactSchema,
)
from ..contact.views import (
    add_contact_decorator,
    add_contact_operation,
    list_resource_contacts_decorator,
    list_resource_contacts_operation,
    remove_contact_decorator,
    remove_contact_operation,
)
from ..query import create_page_tokens, process_page_size, process_page_token
from ..schemas import (
    GENERIC_QUERY_PARAM_USAGE_NOTE,
    GENERIC_RESPONSE_DESCRIPTION,
    PaginatedRequest,
    QueryResponse,
)
from .schemas import (
    AllocatorCreateSchema,
    AllocatorIDMeta,
    AllocatorIDParam,
    AllocatorQueryRequest,
    AllocatorSchema,
    AllocatorUpdateSchema,
    to_schema,
)
from .service import (
    associate_contact,
    contact_is_associated,
    create,
    delete,
    dissociate_contact,
    get,
    list_contacts,
    query,
    update,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@_get(
    path='/{allocator_id:int}',
    sync_to_thread=True,
    tags=['allocators'],
    summary='Get allocator',
    description='Retrieves an allocator by its `allocator_id`.',
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for GET {API_V1_PATH}/allocators/'
                f'{AllocatorIDMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {AllocatorIDMeta.le}',
            validation_key_example='allocator_id',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description=(
                'Allocator ID in path parameter is not associated with a resource'
            ),
            detail_example='Allocator ID 34 does not exist',
        ),
    },
)
def get_allocator(
    db_session: Session, allocator_id: Annotated[int, AllocatorIDParam]
) -> AllocatorSchema:
    allocator = get(db_session, allocator_id)
    if allocator is None:
        raise NotFoundException(f'Allocator ID {allocator_id} does not exist')
    return to_schema(allocator)


@_get(
    path='/',
    dependencies={
        'query_request': Provide(AllocatorQueryRequest, sync_to_thread=True),
    },
    sync_to_thread=True,
    tags=['allocators'],
    summary='Query allocators',
    description=(
        f'Search for and fetch allocators.<br /><br />{GENERIC_QUERY_PARAM_USAGE_NOTE}'
    ),
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={
        400: pagination_400_response_spec(f'{API_V1_PATH}/allocators'),
    },
)
def query_allocators(
    db_session: Session, query_request: AllocatorQueryRequest
) -> QueryResponse[AllocatorSchema]:
    path = '/allocators'
    try:
        bookmark = process_page_token(query_request, path)
    except Exception:
        # TODO: perhaps distinguish between the Fernet token being invalid and
        # a valid token being used for a different request?
        raise
    page = query(
        db_session,
        process_page_size(query_request.max_page_size),
        bookmark,
        # TODO: disable sorting parameters until I can think of an actual use case
        # query_request.direction == DirectionEnum.DESC,
    )
    return QueryResponse(
        [to_schema(a) for (a,) in page], *create_page_tokens(query_request, path, page)
    )


# TODO: query endpoints should be implemented with the HTTP QUERY method once
# that gains more software support


@post(
    path='/',
    guards=[required_request_body_guard],
    sync_to_thread=True,
    tags=['allocators'],
    summary='Create allocator',
    description=(
        'Creates a new allocator.<br />'
        '<br />'
        'Data should come from the registry proposed in'
        " [Section 9.1 'ipn' Scheme URI Allocator Identifiers Registry of RFC 9758]"
        '(https://datatracker.ietf.org/doc/html/rfc9758#name-ipn-scheme-uri-allocator-id).'
        ' E.g., if "Organization A" has the range 20 to 50 of Allocator'
        ' Identifiers, and you want to create at least one node using each ID,'
        ' you would need to create 31 resources for each ID with'
        ' `allocator_name` set to "Organization A".'
    ),
    response_headers=[LocationHeader, ContentLocationHeader],
    response_description='Allocator created, representation follows',
    responses={
        400: create_400_response_spec(
            description=(
                'Bad request syntax, validation error, or allocator ID already'
                ' associated with an existing resource'
            ),
            client_error_detail_example='Allocator ID 0 already exists',
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for POST {API_V1_PATH}/allocators'
            ),
            validation_message_example=f'Expected `int` <= {AllocatorIDMeta.le}',
            validation_key_example='allocator_id',
            validation_source_example='body',
        ),
    },
)
def create_allocator(
    db_session: Session,
    data: AllocatorCreateSchema,
) -> Response[AllocatorSchema]:
    if get(db_session, data.allocator_id) is not None:
        raise ClientException(f'Allocator ID {data.allocator_id} already exists')

    try:
        allocator = create(db_session, data.allocator_id, data.allocator_name)
    except Exception:
        raise InternalServerException
    return Response(
        content=to_schema(allocator),
        headers={
            'Location': f'{API_V1_PATH}/allocators/{data.allocator_id}',
            'Content-Location': f'{API_V1_PATH}/allocators/{allocator.allocator_id}',
        },
    )


@patch(
    path='/{allocator_id:int}',
    sync_to_thread=True,
    tags=['allocators'],
    summary='Update allocator',
    description=(
        'Updates the allocator specified by `allocator_id` in the path parameter.'
    ),
    operation_class=custom_operation(
        custom_reqbody(
            description=(
                'If `allocator_name` or `allocator_id` are not in the request body,'
                ' then these fields will not be updated.'
            ),
            required=False,
        )
    ),
    response_headers=[ContentLocationHeader],
    response_description='Allocator updated, representation follows',
    responses={
        400: create_400_response_spec(
            description=(
                'Bad request syntax, validation error, or allocator ID in request'
                ' body is already associated with an existing resource'
            ),
            client_error_detail_example='Allocator ID 0 already exists',
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for PATCH {API_V1_PATH}/allocators/'
                f'{AllocatorIDMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {AllocatorIDMeta.le}',
            validation_key_example='allocator_id',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description=(
                'Allocator ID in path parameter is not associated with a resource'
            ),
            detail_example='Allocator ID 34 does not exist',
        ),
    },
)
def update_allocator(
    db_session: Session,
    allocator_id: Annotated[int, AllocatorIDParam],
    data: AllocatorUpdateSchema = None,
) -> Response[AllocatorSchema]:
    if data is None:
        data = AllocatorUpdateSchema()
    allocator = get(db_session, allocator_id)
    if allocator is None:
        raise NotFoundException(f'Allocator ID {allocator_id} does not exist')

    new_allocator_id = (
        allocator.allocator_id if data.allocator_id is UNSET else data.allocator_id
    )

    # Someone could still pass the current allocator_id in rather than omitting
    # it, so need to check that it's not equal to current one
    if (
        new_allocator_id != allocator_id
        and get(db_session, new_allocator_id) is not None
    ):
        raise ClientException(f'Allocator ID {new_allocator_id} already exists')

    try:
        allocator = update(
            db_session,
            allocator_id,
            allocator.allocator_name
            if data.allocator_name is UNSET
            else data.allocator_name,
            new_allocator_id,
        )
    except Exception:
        raise InternalServerException
    return Response(
        content=to_schema(allocator),
        headers={
            'Content-Location': f'{API_V1_PATH}/allocators/{allocator.allocator_id}',
        },
    )


@_delete(
    path='/{allocator_id:int}',
    sync_to_thread=True,
    tags=['allocators'],
    summary='Delete allocator',
    description=(
        'Deletes the allocator specified by `allocator_id`.<br />'
        '<br />'
        'Deleting an allocator is restricted if there are still operators or'
        ' nodes associated with it.'
    ),
    responses={
        400: create_400_response_spec(
            description=(
                'Bad request syntax, validation error, or there are still operators'
                ' or nodes associated with the allocator to be deleted'
            ),
            client_error_detail_example=(
                'Allocator is still associated with operators or nodes'
            ),
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for DELETE {API_V1_PATH}/allocators/'
                f'{AllocatorIDMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {AllocatorIDMeta.le}',
            validation_key_example='allocator_id',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description=(
                'Allocator ID in path parameter is not associated with a resource'
            ),
            detail_example='Allocator ID 34 does not exist',
        ),
    },
)
def delete_allocator(
    db_session: Session, allocator_id: Annotated[int, AllocatorIDParam]
) -> None:
    allocator = get(db_session, allocator_id)
    if allocator is None:
        raise NotFoundException(f'Allocator ID {allocator_id} does not exist')
    if allocator.operators or allocator.nodes:
        raise ClientException('Allocator is still associated with operators or nodes')
    try:
        delete(db_session, allocator_id)
    except Exception:
        raise InternalServerException


@list_resource_contacts_decorator(
    'allocator_id', 'allocators', 'allocator', '832', '34'
)
def list_allocator_contacts(
    db_session: Session,
    allocator_id: Annotated[int, AllocatorIDParam],
    paginated_request: PaginatedRequest,
) -> QueryResponse[ContactSchema]:
    try:
        return list_resource_contacts_operation(
            db_session,
            allocator_id,
            paginated_request,
            get,
            'allocator',
            'allocators',
            list_contacts,
        )
    except Exception:
        raise


@add_contact_decorator('allocator_id', 'allocators', 'allocator', '832', '34')
def add_contact(
    db_session: Session,
    allocator_id: Annotated[int, AllocatorIDParam],
    data: ContactAddSchema,
) -> Response[ContactSchema]:
    try:
        return add_contact_operation(
            db_session,
            allocator_id,
            data,
            get,
            'allocator',
            contact_is_associated,
            associate_contact,
        )
    except Exception:
        raise


@remove_contact_decorator(
    'allocator_id', 'allocators', 'allocator', '832', AllocatorIDMeta.le, '34'
)
def remove_contact(
    db_session: Session,
    allocator_id: Annotated[int, AllocatorIDParam],
    contact_id: Annotated[int, ContactIDParam],
) -> None:
    try:
        remove_contact_operation(
            db_session,
            allocator_id,
            contact_id,
            get,
            'allocator',
            contact_is_associated,
            dissociate_contact,
        )
    except Exception:
        raise


allocator_router = Router(
    path='/allocators',
    route_handlers=[
        get_allocator,
        query_allocators,
        create_allocator,
        update_allocator,
        delete_allocator,
        list_allocator_contacts,
        add_contact,
        remove_contact,
    ],
)

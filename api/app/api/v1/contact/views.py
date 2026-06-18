from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Annotated

from litestar import Response, Router, patch, post, put
from litestar import delete as _delete
from litestar import get as _get
from litestar.di import Provide
from litestar.exceptions import (
    ClientException,
    InternalServerException,
    NotFoundException,
)
from litestar.openapi.datastructures import ResponseSpec
from litestar.params import Parameter
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT
from msgspec import UNSET

from app.config import API_V1_PATH
from app.fields import MAX_PHONE_NUMBERS
from app.problem_details import (
    create_400_response_spec,
    create_404_response_spec,
    pagination_400_response_spec,
    required_request_body_guard,
)
from app.schemas import (
    ContentLocationHeader,
    LocationHeader,
    content_location_header_for_200,
    custom_operation,
    custom_reqbody,
)

from ..query import create_page_tokens, process_page_size, process_page_token
from ..schemas import (
    GENERIC_QUERY_PARAM_USAGE_NOTE,
    GENERIC_RESPONSE_DESCRIPTION,
    PaginatedRequest,
    QueryResponse,
)
from .schemas import (
    ASSOCIATE_CONTACT_CUSTOM_REQBODY,
    ContactAddSchema,
    ContactIDMeta,
    ContactIDParam,
    ContactQueryRequest,
    ContactSchema,
    ContactUpdateSchema,
    PhoneNumberReplaceSchema,
    PhoneNumberSchema,
    associate_contact_description,
    dissociate_contact_description,
    to_contact_schema,
    to_phone_number_schema,
)
from .service import (
    create,
    delete,
    get,
    list_phone_numbers,
    query,
    replace_phone_numbers,
    update,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlakeyset import Page
    from sqlalchemy import Row, Tuple
    from sqlalchemy.orm import Session

    from app.models import Allocator, Contact, Host, Node, Operator


def list_resource_contacts_decorator(
    surrogate_key_name: str,
    resource_tag_name: str,
    resource_name: str,
    client_error_id: str,
    not_found_id: str,
) -> _get:
    return _get(
        path=f'/{{{surrogate_key_name}:int}}/contacts',
        sync_to_thread=True,
        tags=[resource_tag_name, 'contacts'],
        summary=f'List {resource_name} points of contact',
        description=(
            f'Lists all points of contact associated with the {resource_name}'
            f' identified by `{surrogate_key_name}`.<br />'
            '<br />'
            f'{GENERIC_QUERY_PARAM_USAGE_NOTE}'
        ),
        response_description=GENERIC_RESPONSE_DESCRIPTION,
        responses={
            400: pagination_400_response_spec(
                f'{API_V1_PATH}/{resource_tag_name}/{client_error_id}/contacts'
            ),
            404: create_404_response_spec(
                description=(
                    f'{resource_name.title()} ID in path parameter is not'
                    ' associated with a resource'
                ),
                detail_example=(
                    f'{resource_name.title()} ID {not_found_id} does not exist'
                ),
            ),
        },
    )


def list_resource_contacts_operation(
    db_session: Session,
    resource_id: int,
    paginated_request: PaginatedRequest,
    get_func: Callable[[Session, int], Allocator | Operator | Host | Node | None],
    resource_name: str,
    resource_tag_name: str,
    list_contacts_func: Callable[
        [Session, int, int, str | None], Page[Row[Tuple[Contact]]]
    ],
) -> QueryResponse[ContactSchema]:
    resource = get_func(db_session, resource_id)
    if resource is None:
        raise NotFoundException(
            f'{resource_name.title()} ID {resource_id} does not exist'
        )
    path = f'/{resource_tag_name}/{resource_id}/contacts'
    try:
        bookmark = process_page_token(paginated_request, path)
    except Exception:
        raise
    page = list_contacts_func(
        db_session,
        resource_id,
        process_page_size(paginated_request.max_page_size),
        bookmark,
    )
    return QueryResponse(
        [to_contact_schema(_) for (_,) in page],
        *create_page_tokens(paginated_request, path, page),
    )


def add_contact_decorator(
    surrogate_key_name: str,
    resource_tag_name: str,
    resource_name: str,
    client_error_id: str,
    not_found_id: str,
) -> post:
    return post(
        path=f'/{{{surrogate_key_name}:int}}/contacts',
        guards=[required_request_body_guard],
        sync_to_thread=True,
        tags=[resource_tag_name, 'contacts'],
        summary=f'Add point of contact for {resource_name}',
        description=associate_contact_description(resource_name, surrogate_key_name),
        operation_class=custom_operation(
            content_location_header_for_200,
            ASSOCIATE_CONTACT_CUSTOM_REQBODY,
        ),
        response_headers=[LocationHeader, ContentLocationHeader],
        response_description=(
            'Point of contact created and associated, representation follows'
        ),
        responses={
            200: ResponseSpec(
                ContactSchema,
                description=(
                    'Existing point of contact associated, representation follows'
                ),
            ),
            400: create_400_response_spec(
                description=(
                    'Bad request syntax, validation error, or existing contact is'
                    f' already associated with the {resource_name}'
                ),
                client_error_detail_example=(
                    f'Contact ID 45 is already associated with {resource_name} ID'
                    f' {client_error_id}'
                ),
                include_validation_error=True,
                validation_detail_example=(
                    f'Validation failed for POST {API_V1_PATH}/'
                    f'{resource_tag_name}/{client_error_id}/contacts'
                ),
                validation_message_example=(
                    'Object missing required field `contact_name`'
                ),
                validation_key_example='contact_name',
                validation_source_example='body',
            ),
            404: create_404_response_spec(
                description=(
                    f'{resource_name.title()} ID in path parameter (or existing'
                    ' contact ID in body) is not associated with a resource'
                ),
                detail_example=(
                    f'{resource_name.title()} ID {not_found_id} does not exist'
                ),
            ),
        },
    )


def add_contact_operation(
    db_session: Session,
    resource_id: int,
    data: ContactAddSchema,
    get_func: Callable[[Session, int], Allocator | Operator | Host | Node | None],
    resource_name: str,
    contact_is_associated_func: Callable[[Session, int, int], bool],
    associate_contact_func: Callable[[Session, int, int]],
) -> Response[ContactSchema]:
    if get_func(db_session, resource_id) is None:
        raise NotFoundException(
            f'{resource_name.title()} ID {resource_id} does not exist'
        )

    headers = {}
    if data.existing_contact_id is not UNSET:
        contact = get(db_session, data.existing_contact_id)
        if contact is None:
            raise NotFoundException(
                f'Contact ID {data.existing_contact_id} does not exist'
            )
        if contact_is_associated_func(
            db_session, resource_id, data.existing_contact_id
        ):
            raise ClientException(
                f'Contact ID {data.existing_contact_id} is already associated'
                f' with {resource_name} ID {resource_id}'
            )
        status_code = HTTP_200_OK
    else:
        try:
            contact = create(db_session, data.contact_name, data.email)
        except Exception:
            raise InternalServerException
        headers['Location'] = f'{API_V1_PATH}/contacts/{contact.contact_id}'
        status_code = HTTP_201_CREATED
    headers['Content-Location'] = f'{API_V1_PATH}/contacts/{contact.contact_id}'

    try:
        associate_contact_func(db_session, resource_id, contact.contact_id)
    except Exception:
        raise InternalServerException
    return Response(
        content=to_contact_schema(contact),
        headers=headers,
        status_code=status_code,
    )


def remove_contact_decorator(
    surrogate_key_name: str,
    resource_tag_name: str,
    resource_name: str,
    client_error_id: str,
    surrogate_key_max: int,
    not_found_id: str,
) -> _delete:
    return _delete(
        path=f'/{{{surrogate_key_name}:int}}/contacts/{{contact_id:int}}',
        sync_to_thread=True,
        tags=[resource_tag_name, 'contacts'],
        summary=f'Remove point of contact for {resource_name}',
        description=dissociate_contact_description(resource_name, surrogate_key_name),
        responses={
            400: create_400_response_spec(
                description=(
                    'Bad request syntax, validation error, or existing contact is'
                    f' not associated with the {resource_name}'
                ),
                client_error_detail_example=(
                    f'Contact ID 45 is not associated with {resource_name} ID'
                    f' {client_error_id}'
                ),
                include_validation_error=True,
                validation_detail_example=(
                    f'Validation failed for DELETE {API_V1_PATH}/{resource_tag_name}/'
                    f'{surrogate_key_max + 1}/contacts/45'
                ),
                validation_message_example=f'Expected `int` <= {surrogate_key_max}',
                validation_key_example=surrogate_key_name,
                validation_source_example='path',
            ),
            404: create_404_response_spec(
                description=(
                    f'{resource_name.title()} ID or contact ID path parameters'
                    ' are not associated with a resource'
                ),
                detail_example=(
                    f'{resource_name.title()} ID {not_found_id} does not exist'
                ),
            ),
        },
    )


def remove_contact_operation(
    db_session: Session,
    resource_id: int,
    contact_id: int,
    get_func: Callable[[Session, int], Allocator | Operator | Host | Node | None],
    resource_name: str,
    contact_is_associated_func: Callable[[Session, int, int], bool],
    dissociate_contact_func: Callable[[Session, int, int], None],
) -> None:
    if get_func(db_session, resource_id) is None:
        raise NotFoundException(
            f'{resource_name.title()} ID {resource_id} does not exist'
        )
    if get(db_session, contact_id) is None:
        raise NotFoundException(f'Contact ID {contact_id} does not exist')
    if not contact_is_associated_func(db_session, resource_id, contact_id):
        raise ClientException(
            f'Contact ID {contact_id} is not associated with {resource_name}'
            f' ID {resource_id}'
        )
    try:
        dissociate_contact_func(db_session, resource_id, contact_id)
    except Exception:
        raise InternalServerException
    return None


@_get(
    path='/{contact_id:int}',
    sync_to_thread=True,
    tags=['contacts'],
    summary='Get point of contact',
    description='Retrieves a point of contact by its `contact_id`.',
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for GET {API_V1_PATH}/contacts/'
                f'{ContactIDMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {ContactIDMeta.le}',
            validation_key_example='contact_id',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description='Contact ID in path parameter is not associated with a resource',
            detail_example='Contact ID 45 does not exist',
        ),
    },
)
def get_contact(
    db_session: Session, contact_id: Annotated[int, ContactIDParam]
) -> ContactSchema:
    contact = get(db_session, contact_id)
    if contact is None:
        raise NotFoundException(f'Contact ID {contact_id} does not exist')
    return to_contact_schema(contact)


@_get(
    path='/',
    dependencies={
        'query_request': Provide(ContactQueryRequest, sync_to_thread=True),
    },
    sync_to_thread=True,
    tags=['contacts'],
    summary='Query points of contact',
    description=(
        f'Search for and fetch points of contact.<br />'
        '<br />'
        f'{GENERIC_QUERY_PARAM_USAGE_NOTE}'
    ),
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={
        400: pagination_400_response_spec(f'{API_V1_PATH}/contacts'),
    },
)
def query_contacts(
    db_session: Session, query_request: ContactQueryRequest
) -> QueryResponse[ContactSchema]:
    path = '/contacts'
    try:
        bookmark = process_page_token(query_request, path)
    except Exception:
        raise
    page = query(db_session, process_page_size(query_request.max_page_size), bookmark)
    return QueryResponse(
        [to_contact_schema(c) for (c,) in page],
        *create_page_tokens(query_request, path, page),
    )


@patch(
    path='/{contact_id:int}',
    sync_to_thread=True,
    tags=['contacts'],
    summary='Update point of contact',
    description=(
        'Updates the point of contact identified by `contact_id`. This can only'
        ' update name and email information. Phone numbers are updated with'
        ' `PUT /contacts/{contact_id}/phone-numbers`.'
    ),
    operation_class=custom_operation(custom_reqbody(required=False)),
    response_description='Point of contact updated, representation follows',
    responses={
        400: create_400_response_spec(
            description=('Bad request syntax or validation error'),
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for PATCH {API_V1_PATH}/contacts/45'
            ),
            validation_message_example=(
                '`contact_name` cannot consist solely of whitespace'
            ),
            validation_key_example='contact_name',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description='Contact ID in path parameter is not associated with a resource',
            detail_example='Contact ID 45 does not exist',
        ),
    },
)
def update_contact(
    db_session: Session,
    contact_id: Annotated[int, ContactIDParam],
    data: ContactUpdateSchema = None,
) -> ContactSchema:
    if data is None:
        data = ContactUpdateSchema()
    contact = get(db_session, contact_id)
    if contact is None:
        raise NotFoundException(f'Contact ID {contact_id} does not exist')

    name = contact.contact_name if data.contact_name is UNSET else data.contact_name
    email = contact.email if data.email is UNSET else data.email

    try:
        contact = update(db_session, contact_id, name, email)
    except Exception:
        raise InternalServerException
    return to_contact_schema(contact)


@_delete(
    path='/{contact_id:int}',
    sync_to_thread=True,
    tags=['contacts'],
    summary='Delete point of contact',
    description=(
        'Deletes the point of contact identified by its `contact_id`.<br />'
        '<br />'
        'Note that deleting a contact that is associated with an entity will'
        " also delete all orphan contacts (contacts that aren't associated with"
        ' any entity).'
    ),
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for DELETE {API_V1_PATH}/contacts/'
                f'{ContactIDMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {ContactIDMeta.le}',
            validation_key_example='contact_id',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description='Contact ID in path parameter is not associated with a resource',
            detail_example='Contact ID 45 does not exist',
        ),
    },
)
def delete_contact(
    db_session: Session, contact_id: Annotated[int, ContactIDParam]
) -> None:
    if get(db_session, contact_id) is None:
        raise NotFoundException(f'Contact ID {contact_id} does not exist')
    try:
        delete(db_session, contact_id)
    except Exception:
        raise InternalServerException


@_get(
    path='/{contact_id:int}/phone-numbers',
    sync_to_thread=True,
    tags=['contacts'],
    summary='List contact phone numbers',
    description=(
        'Lists all phone numbers associated with the point of contact identified'
        ' by `contact_id`.<br />'
        '<br />'
        f'{GENERIC_QUERY_PARAM_USAGE_NOTE}'
    ),
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={
        400: pagination_400_response_spec(f'{API_V1_PATH}/contacts/45/phone-numbers'),
        404: create_404_response_spec(
            description='Contact ID in path parameter is not associated with a resource',
            detail_example='Contact ID 45 does not exist',
        ),
    },
)
def list_contact_phone_numbers(
    db_session: Session,
    contact_id: Annotated[int, ContactIDParam],
    paginated_request: PaginatedRequest,
) -> QueryResponse[PhoneNumberSchema]:
    if get(db_session, contact_id) is None:
        raise NotFoundException(f'Contact ID {contact_id} does not exist')
    path = f'/contacts/{contact_id}/phone-numbers'
    try:
        bookmark = process_page_token(paginated_request, path)
    except Exception:
        raise
    page = list_phone_numbers(
        db_session,
        contact_id,
        process_page_size(paginated_request.max_page_size),
        bookmark,
    )
    return QueryResponse(
        [to_phone_number_schema(_) for (_,) in page],
        *create_page_tokens(paginated_request, path, page),
    )


@put(
    path='/{contact_id:int}/phone-numbers',
    status_code=HTTP_204_NO_CONTENT,
    guards=[required_request_body_guard],
    sync_to_thread=True,
    tags=['contacts'],
    summary='Replace contact phone numbers',
    description=(
        'Provide an array of phone number representations in the request body to'
        ' *replace* the phone numbers associated with the point of contact'
        ' identified by `contact_id`.'
    ),
    operation_class=custom_operation(
        custom_reqbody(
            description=(
                'An empty array (`[]`) will clear all phone numbers.\n'
                '\n'
                'The order of the phone numbers in the request is respected.'
                ' The first phone number in the array is considered the'
                " point of contact's primary phone number."
            ),
            required=True,
        )
    ),
    response_description=HTTPStatus(HTTP_204_NO_CONTENT).description,
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for GET {API_V1_PATH}/contacts/'
                f'{ContactIDMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {ContactIDMeta.le}',
            validation_key_example='contact_id',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description='Contact ID in path parameter is not associated with a resource',
            detail_example='Contact ID 45 does not exist',
        ),
    },
)
def replace_contact_phone_numbers(
    db_session: Session,
    contact_id: Annotated[int, ContactIDParam],
    # MAX_PHONE_NUMBERS is never reached as request bodies are limited to 10 MB
    data: Annotated[
        list[PhoneNumberReplaceSchema], Parameter(max_items=MAX_PHONE_NUMBERS)
    ],
) -> None:
    contact = get(db_session, contact_id)
    if contact is None:
        raise NotFoundException(f'Contact ID {contact_id} does not exist')
    try:
        replace_phone_numbers(db_session, contact_id, data)
    except Exception:
        raise InternalServerException


contact_router = Router(
    path='/contacts',
    route_handlers=[
        get_contact,
        query_contacts,
        update_contact,
        delete_contact,
        list_contact_phone_numbers,
        replace_contact_phone_numbers,
    ],
)

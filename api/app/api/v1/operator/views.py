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
from litestar.status_codes import HTTP_200_OK
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

from ..allocator.schemas import AllocatorIDMeta
from ..allocator.service import get as allocator_get
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
    OperationEnum,
    OperatorCreateSchema,
    OperatorIDMeta,
    OperatorIDParam,
    OperatorNewSchema,
    OperatorQueryRequest,
    OperatorSchema,
    OperatorUpdateSchema,
    UpdateAllocatedNodeNumbersSchema,
    to_operator_schema,
)
from .service import (
    associate_contact,
    conflicting_node_numbers_under_new_allocator,
    contact_is_associated,
    create,
    delete,
    difference_allocated_node_numbers,
    difference_allocated_node_numbers_dry_run,
    difference_node_numbers_not_covered,
    dissociate_contact,
    get,
    get_allocated_node_numbers,
    intersection_allocated_node_numbers,
    intersection_allocated_node_numbers_dry_run,
    intersection_node_numbers_not_covered,
    list_contacts,
    operators_overlapping_allocated_node_numbers_under_new_allocator,
    query,
    union_allocated_node_numbers,
    union_allocated_node_numbers_dry_run,
    union_node_numbers_overlapping,
    update,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@_get(
    path='/{operator_id:int}',
    sync_to_thread=True,
    tags=['operators'],
    summary='Get operator',
    description='Retrieves an operator by its `operator_id`.',
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for GET {API_V1_PATH}/operators/'
                f'{OperatorIDMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {OperatorIDMeta.le}',
            validation_key_example='operator_id',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description=(
                'Operator ID in path parameter is not associated with a resource'
            ),
            detail_example='Operator ID 556 does not exist',
        ),
    },
)
def get_operator(
    db_session: Session, operator_id: Annotated[int, OperatorIDParam]
) -> OperatorSchema:
    operator = get(db_session, operator_id)
    if operator is None:
        raise NotFoundException(f'Operator ID {operator_id} does not exist')
    return to_operator_schema(operator)


@_get(
    path='/',
    dependencies={'query_request': Provide(OperatorQueryRequest, sync_to_thread=True)},
    sync_to_thread=True,
    tags=['operators'],
    summary='Query operators',
    description=(
        f'Search for and fetch operators.<br /><br />{GENERIC_QUERY_PARAM_USAGE_NOTE}'
    ),
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={400: pagination_400_response_spec(f'{API_V1_PATH}/operators')},
)
def query_operators(
    db_session: Session, query_request: OperatorQueryRequest
) -> QueryResponse[OperatorSchema]:
    path = '/operators'
    try:
        bookmark = process_page_token(query_request, path)
    except Exception:
        raise
    page = query(db_session, process_page_size(query_request.max_page_size), bookmark)
    return QueryResponse(
        [to_operator_schema(o) for (o,) in page],
        *create_page_tokens(query_request, path, page),
    )


@post(
    path='/',
    guards=[required_request_body_guard],
    sync_to_thread=True,
    tags=['operators'],
    summary='Create operator',
    description=(
        'Creates a new operator.<br />'
        '<br />'
        'By default, the operator will be under the Default Allocator. If you'
        ' want to put the operator under a different allocator, an `allocator`'
        ' resource needs to be created first.<br />'
        'Use the `/allocators` API for viewing existing allocators and creating'
        ' allocators.<br />'
        '<br />'
        'The operator will be created without any allocated node numbers. Use'
        ' the `/operators/{operator_id}/allocated-node-numbers` API to add or'
        ' remove allocated node numbers.'
    ),
    response_headers=[LocationHeader, ContentLocationHeader],
    response_description='Operator created, representation follows',
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for POST {API_V1_PATH}/operators'
            ),
            validation_message_example=f'Expected `int` <= {AllocatorIDMeta.le}',
            validation_key_example='allocator_id',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description='Allocator ID in body is not associated with a resource',
            detail_example='Allocator ID 34 does not exist',
        ),
    },
)
def create_operator(
    db_session: Session, data: OperatorCreateSchema
) -> Response[OperatorNewSchema]:
    if allocator_get(db_session, data.allocator_id) is None:
        raise NotFoundException(f'Allocator ID {data.allocator_id} does not exist')
    try:
        operator = create(db_session, data.operator_name, data.allocator_id)
    except Exception:
        raise InternalServerException
    return Response(
        content=to_operator_schema(operator),
        headers={
            'Location': f'{API_V1_PATH}/operators/{operator.operator_id}',
            'Content-Location': f'{API_V1_PATH}/operators/{operator.operator_id}',
        },
    )


@post(
    path='/{operator_id:int}/allocated-node-numbers',
    status_code=HTTP_200_OK,
    guards=[required_request_body_guard],
    sync_to_thread=True,
    tags=['operators'],
    summary='Update allocated node numbers of an operator',
    description=(
        'Updates the allocated node numbers of the operator identified by'
        ' `operator_id` by performing a union, intersection, or difference with'
        ' a range described by `lower`, `upper`, and `bounds`. Returns the'
        ' operator.'
    ),
    operation_class=custom_operation(
        custom_reqbody(
            description=' E.g., to increase the allocated node numbers to include'
            ' `[10, 100)`, inclusive 10 and exclusive 100, we send<br />'
            '<pre><code>'
            '{\n'
            '&nbsp;&nbsp;"operation": "union", // could also do "+"\n'
            '&nbsp;&nbsp;"lower": 10,\n'
            '&nbsp;&nbsp;"upper": 100,\n'
            '&nbsp;&nbsp;"bounds": "[)"\n'
            '}\n'
            '</code></pre>'
            '<p>'
            'Remember that under a given allocator, the allocated node numbers for'
            ' operators cannot overlap.<br />'
            '<br />'
            # TODO: We used to have the following message in the above paragraph:
            # 'Check what node numbers an allocator has given out and to which
            # operators using `GET /allocators/<allocator_id>`.' The schema returned
            # by allocators used to show all operators and all of their allocated
            # node numbers. I may not keep that structure, and once querying is
            # implemented, a better hint would be `GET /operators?filter=allocator_id
            # %3D{allocator_id}` or something of the like.
            "If an operator's node number is currently used by an existing node,"
            " trying to remove said node number from the operator's allocated node"
            ' numbers will error.<br />'
            '<br />'
            'The `operation` field is required and must be `union`, `+`,'
            ' `intersection`, `*`, `difference`, or `-`.<br />'
            'If `lower` or `upper` are not in the request body, they will be'
            ' treated as 0 and 2^32-1, respectively.<br />'
            ' `bounds` must be `()`, `[)`, `(]`, or `[]`, and is `[]` by default.'
            ' Note that Postgres uses `[)` by default, so even if you insert data'
            ' using `[50, 100]`, results will be returned in the form `[50, 101)`.</p>',
            required=True,
        )
    ),
    response_headers=[ContentLocationHeader],
    response_description='Allocated node numbers updated, operator representation follows',
    responses={
        400: create_400_response_spec(
            description=(
                'Bad request syntax, validation error, overlapping allocated'
                ' node numbers with existing operators, or trying to remove'
                ' allocated node numbers when they are currently used by nodes'
            ),
            client_error_detail_example=(
                'The updated allocated node numbers for operator ID 45, {[1000,'
                ' 1100), [1900, 2001)}, would not contain currently in-use node'
                ' numbers: 1200, 1500'
            ),
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for POST {API_V1_PATH}/operators/410/allocated'
                '-node-numbers'
            ),
            validation_message_example="Invalid enum value '/'",
            validation_key_example='operation',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description=(
                'Operator ID in path parameter is not associated with a resource'
            ),
            detail_example='Operator ID 556 does not exist',
        ),
    },
)
def update_allocated_node_numbers(
    db_session: Session,
    operator_id: Annotated[int, OperatorIDParam],
    data: UpdateAllocatedNodeNumbersSchema,
) -> Response[OperatorSchema]:
    operator = get(db_session, operator_id)
    if operator is None:
        raise NotFoundException(f'Operator ID {operator_id} does not exist')

    operation = data.operation
    lower = data.lower
    upper = data.upper
    bounds = data.bounds

    # Check if performing union would overlap with other allocations
    if operation in (OperationEnum.UNION, OperationEnum.UNION_ALT):
        overlapping_operators = union_node_numbers_overlapping(
            db_session, operator_id, lower, upper, bounds
        )
        if overlapping_operators:
            updated_range = union_allocated_node_numbers_dry_run(
                db_session, operator_id, lower, upper, bounds
            )
            raise ClientException(
                f'The updated allocated node numbers for operator ID {operator_id},'
                f' {updated_range}, would overlap with existing operators under'
                f' allocator ID {operator.allocator_id}, (operator_id):'
                f' {overlapping_operators}'
            )

    # If the *_not_covered functions return non-empty lists, then there are
    # node numbers currently in use which would not be covered if the update
    # was performed.
    nums_not_covered = False
    if operation in ('intersection', '*'):
        nums_not_covered = intersection_node_numbers_not_covered(
            db_session, operator_id, lower, upper, bounds
        )
        updated_range = intersection_allocated_node_numbers_dry_run(
            db_session, operator_id, lower, upper, bounds
        )
    elif operation in ('difference', '-'):
        nums_not_covered = difference_node_numbers_not_covered(
            db_session, operator_id, lower, upper, bounds
        )
        updated_range = difference_allocated_node_numbers_dry_run(
            db_session, operator_id, lower, upper, bounds
        )
    if nums_not_covered:
        raise ClientException(
            f'The updated allocated node numbers for operator ID {operator_id},'
            f' {updated_range}, would not contain currently in-use node number'
            f'{"s" if len(nums_not_covered) > 1 else ""}:'
            f' {str(sorted(nums_not_covered))[1:-1]}'
        )

    try:
        if operation in (OperationEnum.UNION, OperationEnum.UNION_ALT):
            union_allocated_node_numbers(db_session, operator_id, lower, upper, bounds)
        elif operation in (OperationEnum.INTERSECTION, OperationEnum.INTERSECTION_ALT):
            intersection_allocated_node_numbers(
                db_session, operator_id, lower, upper, bounds
            )
        elif operation in (OperationEnum.DIFFERENCE, OperationEnum.DIFFERENCE_ALT):
            difference_allocated_node_numbers(
                db_session, operator_id, lower, upper, bounds
            )
    except Exception:
        raise InternalServerException
    return Response(
        content=to_operator_schema(operator),
        headers={'Content-Location': f'{API_V1_PATH}/operators/{operator_id}'},
        status_code=HTTP_200_OK,
    )


@patch(
    path='/{operator_id:int}',
    sync_to_thread=True,
    tags=['operators'],
    summary='Update operator',
    description=(
        'Updates the operator specified by `operator_id` in the path parameter.'
    ),
    operation_class=custom_operation(
        custom_reqbody(
            description=(
                '`allocator_id` must be that of an existing allocator.<br />'
                '<br />'
                "Updating `allocator_id` will fail if the to-be-updated operator's"
                ' allocated node numbers overlap with existing operators under'
                ' the allocator.<br />'
                '<br />'
                'Updating `allocator_id` also updates the `allocator_id` of nodes'
                ' under the operator, so the update fails if doing so would violate'
                ' the unique constraint on fully-qualified node numbers.<br />'
                '<br />'
                'Use the `/allocators` API for viewing existing allocators and'
                ' creating allocators.'
            ),
            required=False,
        )
    ),
    response_description='Operator updated, representation follows',
    responses={
        400: create_400_response_spec(
            description=(
                "Bad request syntax, validation error, the to-be-updated operator's"
                ' allocated node numbers overlap with existing operators under the'
                ' allocator, or to-be-updated nodes violate the unique constraint'
                ' on fully-qualified node numbers'
            ),
            client_error_detail_example=(
                'Updating the allocator for operator ID 45 to allocator ID'
                ' 974994 would cause the allocated node numbers of the operator,'
                ' {[1100, 1201)}, to overlap with those of existing operators,'
                ' (operator_id): [410]'
            ),
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for PATCH {API_V1_PATH}/operators/'
                f'{OperatorIDMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {OperatorIDMeta.le}',
            validation_key_example='operator_id',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description=(
                'Operator ID in path parameter is not associated with a resource'
                ' or allocator ID in body is not associated with a resource'
            ),
            detail_example='Operator ID 556 does not exist',
        ),
    },
)
def update_operator(
    db_session: Session,
    operator_id: Annotated[int, OperatorIDParam],
    data: OperatorUpdateSchema = None,
) -> OperatorSchema:
    if data is None:
        data = OperatorUpdateSchema()
    operator = get(db_session, operator_id)
    if operator is None:
        raise NotFoundException(f'Operator ID {operator_id} does not exist')

    operator_name = (
        operator.operator_name if data.operator_name is UNSET else data.operator_name
    )
    allocator_id = (
        operator.allocator_id if data.allocator_id is UNSET else data.allocator_id
    )

    if allocator_get(db_session, allocator_id) is None:
        raise NotFoundException(f'Allocator ID {data.allocator_id} does not exist')
    same_allocator = allocator_id == operator.allocator_id

    overlapping_operators = (
        operators_overlapping_allocated_node_numbers_under_new_allocator(
            db_session, operator_id, allocator_id
        )
    )
    if not same_allocator and overlapping_operators:
        allocated_node_numbers = get_allocated_node_numbers(db_session, operator_id)
        raise ClientException(
            f'Updating the allocator for operator ID {operator_id} to allocator'
            f' ID {allocator_id} would cause the allocated node numbers of the'
            f' operator, {allocated_node_numbers}, to overlap with those of'
            f' existing operators, (operator_id): {overlapping_operators}'
        )

    conflicting_node_numbers = conflicting_node_numbers_under_new_allocator(
        db_session, operator_id, allocator_id
    )
    if not same_allocator and conflicting_node_numbers:
        raise ClientException(
            f'Updating the allocator for operator ID {operator_id} to allocator'
            f' ID {allocator_id} would also update the allocator ID of nodes'
            ' under the operator. This violates the unique constraint on'
            ' fully-qualified node numbers because nodes under allocator ID'
            f' {allocator_id} with the following node numbers already exist:'
            f' {conflicting_node_numbers}'
        )

    try:
        operator = update(db_session, operator_id, operator_name, allocator_id)
    except Exception:
        raise InternalServerException
    return to_operator_schema(operator)


@_delete(
    path='/{operator_id:int}',
    sync_to_thread=True,
    tags=['operators'],
    summary='Delete operator',
    description=(
        'Deletes the operator specified by `operator_id`.<br />'
        '<br />'
        'Deleting an operator will set `operator_id` to null in associated hosts'
        ' and nodes.'
    ),
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for DELETE {API_V1_PATH}/operators/'
                f'{OperatorIDMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {OperatorIDMeta.le}',
            validation_key_example='operator_id',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description=(
                'Operator ID in path parameter is not associated with a resource'
            ),
            detail_example='Operator ID 556 does not exist',
        ),
    },
)
def delete_operator(
    db_session: Session, operator_id: Annotated[int, OperatorIDParam]
) -> None:
    if get(db_session, operator_id) is None:
        raise NotFoundException(f'Operator ID {operator_id} does not exist')
    try:
        delete(db_session, operator_id)
    except Exception:
        raise InternalServerException


@list_resource_contacts_decorator('operator_id', 'operators', 'operator', '410', '556')
def list_operator_contacts(
    db_session: Session,
    operator_id: Annotated[int, OperatorIDParam],
    paginated_request: PaginatedRequest,
) -> QueryResponse[ContactSchema]:
    try:
        return list_resource_contacts_operation(
            db_session,
            operator_id,
            paginated_request,
            get,
            'operator',
            'operators',
            list_contacts,
        )
    except Exception:
        raise


@add_contact_decorator('operator_id', 'operators', 'operator', '410', '556')
def add_contact(
    db_session: Session,
    operator_id: Annotated[int, OperatorIDParam],
    data: ContactAddSchema,
) -> Response[ContactSchema]:
    try:
        return add_contact_operation(
            db_session,
            operator_id,
            data,
            get,
            'operator',
            contact_is_associated,
            associate_contact,
        )
    except Exception:
        raise


@remove_contact_decorator(
    'operator_id', 'operators', 'operator', '410', OperatorIDMeta.le, '556'
)
def remove_contact(
    db_session: Session,
    operator_id: Annotated[int, OperatorIDParam],
    contact_id: Annotated[int, ContactIDParam],
) -> None:
    try:
        remove_contact_operation(
            db_session,
            operator_id,
            contact_id,
            get,
            'operator',
            contact_is_associated,
            dissociate_contact,
        )
    except Exception:
        raise


operator_router = Router(
    path='/operators',
    route_handlers=[
        get_operator,
        query_operators,
        create_operator,
        update_allocated_node_numbers,
        update_operator,
        delete_operator,
        list_operator_contacts,
        add_contact,
        remove_contact,
    ],
)

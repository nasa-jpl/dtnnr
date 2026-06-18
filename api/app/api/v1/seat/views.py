from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Annotated

from litestar import Router, put
from litestar import delete as _delete
from litestar import get as _get
from litestar.exceptions import (
    ClientException,
    InternalServerException,
    NotFoundException,
)
from litestar.status_codes import HTTP_204_NO_CONTENT

from app.config import API_V1_PATH
from app.models import CommDirectionEnum
from app.problem_details import (
    create_400_response_spec,
    create_404_response_spec,
    pagination_400_response_spec,
    required_request_body_guard,
)
from app.schemas import custom_operation, custom_reqbody

from ..destination.service import get as destination_get
from ..host.schemas import HostIDMeta
from ..link.schemas import (
    LinkIDMeta,
    LinkIDsReplaceBody,
    LinkIDsReplaceSet,
    LinkWithoutHostIdSchema,
    to_link_schema,
)
from ..link.service import exclude_ids_not_under_host, keep_simplex_outgoing_ids
from ..query import create_page_tokens, process_page_size, process_page_token
from ..schemas import (
    GENERIC_QUERY_PARAM_USAGE_NOTE,
    GENERIC_RESPONSE_DESCRIPTION,
    PaginatedRequest,
    QueryResponse,
)
from .schemas import (
    SEAT_WRITE_DESCRIPTION,
    PortNumberMeta,
    SeatCreateSchema,
    SeatIDMeta,
    SeatIDParam,
    SeatSchema,
    to_seat_schema,
)
from .service import (
    create_ip,
    delete,
    delete_ip,
    get,
    list_links,
    replace_links,
    update,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@_get(
    path='/{seat_id:int}',
    sync_to_thread=True,
    tags=['seats'],
    summary='Get seat',
    description='Retrieves a seat by its `seat_id`.',
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for GET {API_V1_PATH}/seats/{SeatIDMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {SeatIDMeta.le}',
            validation_key_example='seat_id',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description='Seat ID in path parameter is not associated with a resource',
            detail_example='Seat ID 131 does not exist',
        ),
    },
)
def get_seat(db_session: Session, seat_id: Annotated[int, SeatIDParam]) -> SeatSchema:
    seat = get(db_session, seat_id)
    if seat is None:
        raise NotFoundException(f'Seat ID {seat_id} does not exist')
    return to_seat_schema(seat)


@_get(
    path='/{seat_id:int}/links',
    sync_to_thread=True,
    tags=['seats', 'links'],
    summary='List seat links',
    description=(
        'Lists links associated with the seat identified by `seat_id`.<br />'
        '<br />'
        f'{GENERIC_QUERY_PARAM_USAGE_NOTE}'
    ),
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={
        400: pagination_400_response_spec(f'{API_V1_PATH}/seats/412/links'),
        404: create_404_response_spec(
            description='Seat ID in path parameter is not associated with a resource',
            detail_example='Seat ID 131 does not exist',
        ),
    },
)
def list_seat_links(
    db_session: Session,
    seat_id: Annotated[int, SeatIDParam],
    paginated_request: PaginatedRequest,
) -> QueryResponse[LinkWithoutHostIdSchema]:
    if get(db_session, seat_id) is None:
        raise NotFoundException(f'Seat ID {seat_id} does not exist')
    path = f'/seats/{seat_id}/links'
    try:
        bookmark = process_page_token(paginated_request, path)
    except Exception:
        raise
    page = list_links(
        db_session,
        seat_id,
        process_page_size(paginated_request.max_page_size),
        bookmark,
    )
    return QueryResponse(
        [to_link_schema(l, with_host=False) for (l,) in page],
        *create_page_tokens(paginated_request, path, page),
    )


@put(
    path='/{seat_id:int}/links',
    status_code=HTTP_204_NO_CONTENT,
    guards=[required_request_body_guard],
    sync_to_thread=True,
    tags=['seats', 'links'],
    summary='Replace seat links',
    description=(
        'Provide an array of link IDs in the request body to *replace* the links'
        ' associated with the seat identified by `seat_id`.<br />'
        '<br />'
        'A seat can only associate with links if it belongs to a node that is'
        " associated with a host. Use the node's `host_id` with the"
        ' `/hosts/{host_id}/links` API to obtain IDs that can be passed in the'
        ' request body.'
    ),
    operation_class=custom_operation(
        custom_reqbody(
            description=(
                'An empty array (`[]`) will clear the links associated with the'
                ' seat.<br />'
                '<br />'
                'Duplicate values are removed.'
            ),
            required=True,
        )
    ),
    response_description=HTTPStatus(HTTP_204_NO_CONTENT).description,
    responses={
        400: create_400_response_spec(
            description=(
                'Bad request syntax; validation error; seat is on hostless node;'
                ' request body refers to links that do not exist, belong to a'
                " different host than the node's, or have a simplex outgoing"
                ' direction'
            ),
            client_error_detail_example=(
                '`extra` contains link IDs that are not associated with host ID'
                f' {HostIDMeta.examples[0]}'
            ),
            client_error_extra=['39', '434'],
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for PUT {API_V1_PATH}/seats/412/links'
            ),
            validation_message_example=f'Expected `int` <= {LinkIDMeta.le}',
            # TODO: Uncomment if Litestar accepts my PR
            # validation_key_example='[0]',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description='Seat ID in path parameter is not associated with a resource',
            detail_example='Seat ID 131 does not exist',
        ),
    },
)
def replace_seat_links(
    db_session: Session,
    seat_id: Annotated[int, SeatIDParam],
    data: Annotated[LinkIDsReplaceSet, LinkIDsReplaceBody],
) -> None:
    seat = get(db_session, seat_id)
    if seat is None:
        raise NotFoundException(f'Seat ID {seat_id} does not exist')

    if data:
        if seat.host_id is None:
            raise ClientException(
                f'Seat cannot associate with links because node ID {seat.node_id}'
                ' is not associated with a host'
            )

        # TODO: Would be more proper to return 404 for links that don't exist, but
        # would be less efficient since we have to do another or more complex query.
        dont_exist_wrong_host_link_ids = exclude_ids_not_under_host(
            db_session, data, seat.host_id
        )
        if dont_exist_wrong_host_link_ids:
            raise ClientException(
                '`extra` contains link IDs that are not associated with host ID'
                f' {seat.host_id}',
                extra=dont_exist_wrong_host_link_ids,
            )

        simplex_outgoing_ids = keep_simplex_outgoing_ids(db_session, data)
        if simplex_outgoing_ids:
            raise ClientException(
                '`extra` contains link IDs with direction'
                f" '{CommDirectionEnum.SIMPLEX_OUT.value}'",
                extra=simplex_outgoing_ids,
            )

    try:
        replace_links(db_session, seat_id, data)
    except Exception:
        raise InternalServerException


@put(
    path='/{seat_id:int}',
    sync_to_thread=True,
    tags=['seats'],
    summary='Replace seat',
    description=(
        'Replaces the seat identified by `seat_id` with the state defined by the'
        ' request body. A successful request will not modify relationships that'
        ' the seat has with links.<br />'
        '<br />'
        'Use the `/hosts/{host_id}/destinations` API to obtain IDs that can be'
        ' passed for `seat_ip.destination_id`. `host_id` must be that of the'
        " node's host, so if the node is hostless, setting"
        ' `seat_ip.destination_id` is not possible.'
    ),
    operation_class=custom_operation(
        custom_reqbody(description=SEAT_WRITE_DESCRIPTION, required=False)
    ),
    response_description='Seat replaced, representation follows',
    responses={
        400: create_400_response_spec(
            description=(
                'Bad request syntax, validation error, or `destination_id`'
                ' cannot be referenced by the node.'
            ),
            client_error_detail_example=(
                'A destination cannot be associated with a seat when the node is'
                ' not on a host.'
            ),
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for PUT {API_V1_PATH}/seats/412'
            ),
            validation_message_example=f'Expected `int` <= {PortNumberMeta.le}',
            validation_key_example='seat_ip.port_number',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description=(
                '`seat_id` in the path is not associated with a seat, or'
                ' `destination_id` is not associated with a destination.'
            ),
            detail_example='Seat ID 131 does not exist',
        ),
    },
)
def replace_seat(
    db_session: Session,
    seat_id: Annotated[int, SeatIDParam],
    data: SeatCreateSchema = None,
) -> SeatSchema:
    if data is None:
        data = SeatCreateSchema()
    seat = get(db_session, seat_id)
    if seat is None:
        raise NotFoundException(f'Seat ID {seat_id} does not exist')

    if data.seat_ip is not None and data.seat_ip.destination_id is not None:
        destination = destination_get(db_session, data.seat_ip.destination_id)
        if destination is None:
            raise NotFoundException(
                f'Destination ID {data.seat_ip.destination_id} does not exist'
            )
        if destination.host_id != seat.host_id:
            if seat.host_id is None:
                raise ClientException(
                    'A destination cannot be associated with a seat when'
                    ' the node is not on a host.'
                )
            raise ClientException(
                f'Destination ID {data.seat_ip.destination_id} belongs to a'
                f' different host than host ID {seat.host_id}, which node ID'
                f' {seat.node_id} belongs to'
            )

    try:
        if seat.seat_ip:
            delete_ip(db_session, seat_id)
        update(
            db_session,
            seat_id,
            'ip' if data.seat_ip is not None else None,
            data.lsi_command,
        )
        if data.seat_ip is not None:
            create_ip(
                db_session,
                seat_id,
                data.seat_ip.destination_id,
                data.seat_ip.port_number,
            )
        db_session.commit()
    except Exception:
        raise InternalServerException
    return to_seat_schema(seat)


@_delete(
    path='/{seat_id:int}',
    sync_to_thread=True,
    tags=['seats'],
    summary='Delete seat',
    description=(
        'Deletes the seat identified by `seat_id`.<br />'
        '<br />'
        'Note that LTP inducts associate with a seat to describe its links, so'
        ' if a seat is deleted, the induct loses its associations with links.'
    ),
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for DELETE {API_V1_PATH}/seats/{SeatIDMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {SeatIDMeta.le}',
            validation_key_example='seat_id',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description='Seat ID in path parameter is not associated with a resource',
            detail_example='Seat ID 131 does not exist',
        ),
    },
)
def delete_seat(db_session: Session, seat_id: Annotated[int, SeatIDParam]) -> None:
    if get(db_session, seat_id) is None:
        raise NotFoundException(f'Seat ID {seat_id} does not exist')
    try:
        delete(db_session, seat_id)
    except Exception:
        raise InternalServerException


seat_router = Router(
    path='/seats',
    route_handlers=[
        get_seat,
        list_seat_links,
        replace_seat_links,
        replace_seat,
        delete_seat,
    ],
)

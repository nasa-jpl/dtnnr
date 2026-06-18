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
from litestar.openapi.datastructures import ResponseSpec
from litestar.status_codes import HTTP_204_NO_CONTENT

from app.config import API_V1_PATH
from app.models import (
    CommDirectionEnum,
    cli_command_with_required_protocol_name,
    no_duct_name_known_cli_not_ip,
    no_induct_ip_known_cli,
    no_uses_ltp_known_cli,
)
from app.problem_details import (
    create_400_response_spec,
    create_404_response_spec,
    pagination_400_response_spec,
    required_request_body_guard,
)
from app.schemas import custom_operation, custom_reqbody

from ..cl_protocol.service import get as cl_protocol_get
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
from ..node.schemas import NodeIDMeta
from ..query import create_page_tokens, process_page_size, process_page_token
from ..schemas import (
    GENERIC_QUERY_PARAM_USAGE_NOTE,
    GENERIC_RESPONSE_DESCRIPTION,
    PaginatedRequest,
    QueryResponse,
)
from ..seat.schemas import (
    SeatIDMeta,
    SeatIDsReplaceBody,
    SeatIDsReplaceSet,
    SeatWithoutNodeIdSchema,
    to_seat_without_node_id_schema,
)
from ..seat.service import exclude_ids_not_under_node
from .schemas import (
    INDUCT_WRITE_DESCRIPTION,
    DuctNameIpCreateSchema,
    InductCreateBody,
    InductCreateSchema,
    InductIDMeta,
    InductIDParam,
    InductSchema,
    induct_examples,
    to_induct_schema,
)
from .service import (
    create_ip,
    delete,
    delete_ip,
    get,
    links_related_to_induct,
    list_links,
    list_seats,
    replace_links,
    replace_seats,
    seats_related_to_induct,
    update,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import ClProtocol


cli_p_name_dict = {
    cli: p_name for cli, p_name in cli_command_with_required_protocol_name
}


def check_induct_constraints(
    cl_protocol: ClProtocol | None,
    duct_name: str | DuctNameIpCreateSchema | None,
    cli_command: str | None,
    uses_ltp: bool,
):
    if cli_command in cli_p_name_dict and (
        cl_protocol is None
        or cl_protocol.cl_protocol_name != cli_p_name_dict[cli_command]
    ):
        raise ClientException(
            f"`cli_command` ('{cli_command}') must be associated with an induct"
            f" that uses a `cl_protocol_name` of '{cli_p_name_dict[cli_command]}'"
        )
    if cli_command == 'ltpcli' and not uses_ltp:
        raise ClientException("`uses_ltp` must be true when `cli_command` is 'ltpcli'")
    if cli_command in no_uses_ltp_known_cli and uses_ltp:
        raise ClientException(
            f'`uses_ltp` must be false when `cli_command` is in {no_uses_ltp_known_cli}'
        )
    if cli_command in no_duct_name_known_cli_not_ip and duct_name is not None:
        raise ClientException(
            '`duct_name` must be null when `cli_command` is in'
            f' {no_duct_name_known_cli_not_ip}'
        )
    # This only checks for brsccla since bsspcli and ltpcli are caught earlier
    # if duct_name is set.
    if cli_command in no_induct_ip_known_cli and isinstance(
        duct_name, DuctNameIpCreateSchema
    ):
        raise ClientException(
            f"`cli_command` ('{cli_command}') does not use an 'ip:port' format"
            ' for "duct_name", so an "ip" type object cannot be used for'
            ' `duct_name`'
        )


@_get(
    path='/{induct_id:int}',
    sync_to_thread=True,
    tags=['inducts'],
    summary='Get induct',
    description='Retrieves an induct by its `induct_id`.',
    responses={
        200: ResponseSpec(
            data_container=InductSchema,
            description=GENERIC_RESPONSE_DESCRIPTION,
            examples=induct_examples,
        ),
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for GET {API_V1_PATH}/inducts/{InductIDMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {InductIDMeta.le}',
            validation_key_example='induct_id',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description='Induct ID in path parameter is not associated with a resource',
            detail_example='Induct ID 523 does not exist',
        ),
    },
)
def get_induct(
    db_session: Session, induct_id: Annotated[int, InductIDParam]
) -> InductSchema:
    induct = get(db_session, induct_id)
    if induct is None:
        raise NotFoundException(f'Induct ID {induct_id} does not exist')
    return to_induct_schema(induct)


@_get(
    path='/{induct_id:int}/links',
    sync_to_thread=True,
    tags=['inducts', 'links'],
    summary='List induct links',
    description=(
        'Lists links associated with the induct identified by `induct_id`.<br />'
        '<br />'
        f'{GENERIC_QUERY_PARAM_USAGE_NOTE}'
    ),
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={
        400: pagination_400_response_spec(f'{API_V1_PATH}/inducts/105/links'),
        404: create_404_response_spec(
            description='Induct ID in path parameter is not associated with a resource',
            detail_example='Induct ID 523 does not exist',
        ),
    },
)
def list_induct_links(
    db_session: Session,
    induct_id: Annotated[int, InductIDParam],
    paginated_request: PaginatedRequest,
) -> QueryResponse[LinkWithoutHostIdSchema]:
    if get(db_session, induct_id) is None:
        raise NotFoundException(f'Induct ID {induct_id} does not exist')
    path = f'/inducts/{induct_id}/links'
    try:
        bookmark = process_page_token(paginated_request, path)
    except Exception:
        raise
    page = list_links(
        db_session,
        induct_id,
        process_page_size(paginated_request.max_page_size),
        bookmark,
    )
    return QueryResponse(
        [to_link_schema(l, with_host=False) for (l,) in page],
        *create_page_tokens(paginated_request, path, page),
    )


@put(
    path='/{induct_id:int}/links',
    status_code=HTTP_204_NO_CONTENT,
    guards=[required_request_body_guard],
    sync_to_thread=True,
    tags=['inducts', 'links'],
    summary='Replace induct links',
    description=(
        'Provide an array of link IDs in the request body to *replace* the links'
        ' associated with the induct identified by `induct_id`.<br />'
        '<br />'
        'Note that an LTP induct (i.e., `induct.uses_ltp` is true) cannot associate'
        ' with links. LTP inducts can only indirectly associate with links through'
        ' seats.<br />'
        '<br />'
        'An induct can only associate with links if it belongs to a node that is'
        " associated with a host. Use the node's `host_id` with the"
        ' `/hosts/{host_id}/links` API to obtain IDs that can be passed in the'
        ' request body.'
    ),
    operation_class=custom_operation(
        custom_reqbody(
            description=(
                'An empty array (`[]`) will clear the links associated with the'
                ' induct.<br />'
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
                'Bad request syntax; validation error; induct is on hostless node;'
                ' induct uses LTP; request body refers to links that do not exist,'
                " belong to a different host than the node's, or have a simplex"
                ' outgoing direction'
            ),
            client_error_detail_example=(
                '`extra` contains link IDs that are not associated with host ID'
                f' {HostIDMeta.examples[0]}'
            ),
            client_error_extra=['39', '434'],
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for PUT {API_V1_PATH}/inducts/105/links'
            ),
            validation_message_example=f'Expected `int` <= {LinkIDMeta.le}',
            # TODO: Uncomment if Litestar accepts my PR
            # validation_key_example='[0]',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description='Induct ID in path parameter is not associated with a resource',
            detail_example='Induct ID 523 does not exist',
        ),
    },
)
def replace_induct_links(
    db_session: Session,
    induct_id: Annotated[int, InductIDParam],
    data: Annotated[LinkIDsReplaceSet, LinkIDsReplaceBody],
) -> None:
    induct = get(db_session, induct_id)
    if induct is None:
        raise NotFoundException(f'Induct ID {induct_id} does not exist')

    if data:
        if induct.host_id is None:
            raise ClientException(
                f'Induct cannot associate with links because node ID {induct.node_id}'
                ' is not associated with a host'
            )

        if induct.uses_ltp:
            raise ClientException(
                'LTP inducts cannot directly associate with links; can only indirectly'
                ' associate with links through seats'
            )

        # TODO: Would be more proper to return 404 for links that don't exist, but
        # would be less efficient since we have to do another or more complex query.
        dont_exist_wrong_host_link_ids = exclude_ids_not_under_host(
            db_session, data, induct.host_id
        )
        if dont_exist_wrong_host_link_ids:
            raise ClientException(
                '`extra` contains link IDs that are not associated with host ID'
                f' {induct.host_id}',
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
        replace_links(db_session, induct_id, data)
    except Exception:
        raise InternalServerException


@_get(
    path='/{induct_id:int}/seats',
    sync_to_thread=True,
    tags=['inducts', 'seats'],
    summary='List induct seats',
    description=(
        'Lists seats associated with the induct identified by `induct_id`.<br />'
        '<br />'
        f'{GENERIC_QUERY_PARAM_USAGE_NOTE}'
    ),
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={
        400: pagination_400_response_spec(f'{API_V1_PATH}/inducts/459/seats'),
        404: create_404_response_spec(
            description='Induct ID in path parameter is not associated with a resource',
            detail_example='Induct ID 523 does not exist',
        ),
    },
)
def list_induct_seats(
    db_session: Session,
    induct_id: Annotated[int, InductIDParam],
    paginated_request: PaginatedRequest,
) -> QueryResponse[SeatWithoutNodeIdSchema]:
    if get(db_session, induct_id) is None:
        raise NotFoundException(f'Induct ID {induct_id} does not exist')
    path = f'/inducts/{induct_id}/seats'
    try:
        bookmark = process_page_token(paginated_request, path)
    except Exception:
        raise
    page = list_seats(
        db_session,
        induct_id,
        process_page_size(paginated_request.max_page_size),
        bookmark,
    )
    return QueryResponse(
        [to_seat_without_node_id_schema(s) for (s,) in page],
        *create_page_tokens(paginated_request, path, page),
    )


@put(
    path='/{induct_id:int}/seats',
    status_code=HTTP_204_NO_CONTENT,
    guards=[required_request_body_guard],
    sync_to_thread=True,
    tags=['inducts', 'seats'],
    summary='Replace induct seats',
    description=(
        'Provide an array of seat IDs in the request body to *replace* the seats'
        ' associated with the induct identified by `induct_id`.<br />'
        '<br />'
        'Note that only an LTP induct (i.e., `induct.uses_ltp` is true) can'
        ' associate with seats.<br />'
        '<br />'
        'Use the `/nodes/{node_id}/seats` API to obtain IDs that can be passed'
        ' in the request body.'
    ),
    operation_class=custom_operation(
        custom_reqbody(
            description=(
                'An empty array (`[]`) will clear the seats associated with the'
                ' induct.<br />'
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
                'Bad request syntax; validation error; induct does not use LTP;'
                ' request body refers to seats that do not exist or belong to a'
                " different node than the induct's"
            ),
            client_error_detail_example=(
                '`extra` contains seat IDs that are not associated with node ID'
                f' {NodeIDMeta.examples[0]}'
            ),
            client_error_extra=['620', '821'],
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for PUT {API_V1_PATH}/inducts/459/seats'
            ),
            validation_message_example=f'Expected `int` <= {SeatIDMeta.le}',
            # TODO: Uncomment if Litestar accepts my PR
            # validation_key_example='[0]',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description='Induct ID in path parameter is not associated with a resource',
            detail_example='Induct ID 523 does not exist',
        ),
    },
)
def replace_induct_seats(
    db_session: Session,
    induct_id: Annotated[int, InductIDParam],
    data: Annotated[SeatIDsReplaceSet, SeatIDsReplaceBody],
) -> None:
    induct = get(db_session, induct_id)
    if induct is None:
        raise NotFoundException(f'Induct ID {induct_id} does not exist')

    if data:
        if not induct.uses_ltp:
            raise ClientException(
                f'Induct ID {induct_id} does not use LTP; cannot associate with seats'
            )

        # TODO: Would be more proper to return 404 for seats that don't exist, but
        # would be less efficient since we have to do another or more complex query.
        dont_exist_wrong_node_seat_ids = exclude_ids_not_under_node(
            db_session, data, induct.node_id
        )
        if dont_exist_wrong_node_seat_ids:
            raise ClientException(
                '`extra` contains seat IDs that are not associated with node ID'
                f' {induct.node_id}',
                extra=dont_exist_wrong_node_seat_ids,
            )

    try:
        replace_seats(db_session, induct_id, data)
    except Exception:
        raise InternalServerException


@put(
    path='/{induct_id:int}',
    sync_to_thread=True,
    tags=['inducts'],
    summary='Replace induct',
    description=(
        'Replaces the induct identified by `induct_id` with the state defined'
        ' by the request body. A successful request will not modify relationships'
        ' that the induct has with links or seats.<br />'
        '<br />'
        'Use the `/nodes/{node_id}/cl-protocols` API to obtain IDs that can be'
        ' passed for `cl_protocol_id`.<br />'
        '<br />'
        'Use the `/hosts/{host_id}/destinations` API to obtain IDs that can be'
        ' passed for `duct_name.destination_id`. `host_id` must be that of the'
        " node's host, so if the node is hostless, setting"
        ' `duct_name.destination_id` is not possible.'
    ),
    operation_class=custom_operation(
        custom_reqbody(
            description=(
                f'{INDUCT_WRITE_DESCRIPTION}'
                '<p>'
                '`uses_ltp` cannot be changed to true if the induct is associated'
                ' with links. `uses_ltp` cannot be changed to false if the induct'
                ' is associated with seats. These relationships must be cleared'
                ' with their replace operations before `uses_ltp` can be changed.'
                '</p>'
            ),
            required=False,
        )
    ),
    responses={
        200: ResponseSpec(
            data_container=InductSchema,
            description='Induct replaced, representation follows',
            examples=induct_examples,
        ),
        400: create_400_response_spec(
            description=(
                'Bad request syntax, validation error, `cli_command` requires'
                ' a CL protocol with a specific value to be associated with'
                ' the induct, `cli_command` expects a particular `uses_ltp`'
                ' value, `cli_command` value must be paired with a null'
                ' `duct_name`, `duct_name` is an object with type "ip" paired'
                ' with an incompatible `cli_command`, `cl_protocol_id` refers'
                ' to a CL protocol that is not owned by the node,'
                ' `destination_id` cannot be referenced by the node, or changing'
                ' `uses_ltp` is not possible since the induct is associated with'
                ' links or seats.'
            ),
            client_error_detail_example=(
                'Cannot change `uses_ltp` from false to true when the induct is'
                ' associated with links. `extra` contains link IDs of links'
                ' associated with the induct'
            ),
            client_error_extra=['1986'],
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for PUT {API_V1_PATH}/inducts/105'
            ),
            validation_message_example="Invalid value 'IP'",
            validation_key_example='duct_name.type',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description=(
                '`induct_id` in the path is not associated with a induct,'
                ' `cl_protocol_id` is not associated with a CL protocol, or'
                ' `destination_id` is not associated with a destination.'
            ),
            detail_example='Induct ID 523 does not exist',
        ),
    },
)
def replace_induct(
    db_session: Session,
    induct_id: Annotated[int, InductIDParam],
    data: Annotated[InductCreateSchema, InductCreateBody] = None,
) -> InductSchema:
    if data is None:
        data = InductCreateSchema()
    induct = get(db_session, induct_id)
    if induct is None:
        raise NotFoundException(f'Induct ID {induct_id} does not exist')

    if data.cl_protocol_id is not None:
        cl_protocol = cl_protocol_get(db_session, data.cl_protocol_id)
        if cl_protocol is None:
            raise NotFoundException(
                f'CL protocol ID {data.cl_protocol_id} does not exist'
            )
        if cl_protocol.node_id != induct.node_id:
            raise ClientException(
                f'CL protocol ID {data.cl_protocol_id} does not belong to node ID'
                f' {induct.node_id}'
            )
    else:
        cl_protocol = None

    check_induct_constraints(
        cl_protocol, data.duct_name, data.cli_command, data.uses_ltp
    )

    is_ip_duct = isinstance(data.duct_name, DuctNameIpCreateSchema)

    if is_ip_duct and data.duct_name.destination_id is not None:
        destination = destination_get(db_session, data.duct_name.destination_id)
        if destination is None:
            raise NotFoundException(
                f'Destination ID {data.duct_name.destination_id} does not exist'
            )
        if destination.host_id != induct.host_id:
            if induct.host_id is None:
                raise ClientException(
                    'A destination cannot be associated with an induct when'
                    ' the node is not on a host.'
                )
            raise ClientException(
                f'Destination ID {data.duct_name.destination_id} belongs to a'
                f' different host than host ID {induct.host_id}, which node ID'
                f' {induct.node_id} belongs to'
            )

    link_ids = links_related_to_induct(db_session, induct_id)
    if link_ids and not induct.uses_ltp and data.uses_ltp:
        raise ClientException(
            'Cannot change `uses_ltp` from false to true when the induct is'
            ' associated with links. `extra` contains link IDs of links associated'
            ' with the induct',
            extra=link_ids,
        )
    seat_ids = seats_related_to_induct(db_session, induct_id)
    if seat_ids and induct.uses_ltp and not data.uses_ltp:
        raise ClientException(
            'Cannot change `uses_ltp` from true to false when the induct is'
            ' associated with seats. `extra` contains seat IDs of seats associated'
            ' with the induct',
            extra=seat_ids,
        )

    try:
        # Always delete induct_ip because FKs are weird when induct.type changes
        if induct.induct_ip:
            delete_ip(db_session, induct_id)
        update(
            db_session,
            induct_id,
            induct.node_id,
            'ip' if is_ip_duct else None,
            data.cl_protocol_id,
            data.duct_name if isinstance(data.duct_name, str) else None,
            data.cli_command,
            data.uses_ltp,
        )
        if is_ip_duct:
            create_ip(
                db_session,
                induct_id,
                data.duct_name.destination_id,
                data.duct_name.port_number,
            )
        db_session.commit()
    except Exception:
        raise InternalServerException
    return to_induct_schema(induct)


@_delete(
    path='/{induct_id:int}',
    sync_to_thread=True,
    tags=['inducts'],
    summary='Delete induct',
    description='Deletes the induct identified by `induct_id`.',
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for DELETE {API_V1_PATH}/inducts/{InductIDMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {InductIDMeta.le}',
            validation_key_example='induct_id',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description='Induct ID in path parameter is not associated with a resource',
            detail_example='Induct ID 523 does not exist',
        ),
    },
)
def delete_induct(
    db_session: Session, induct_id: Annotated[int, InductIDParam]
) -> None:
    if get(db_session, induct_id) is None:
        raise NotFoundException(f'Induct ID {induct_id} does not exist')
    try:
        delete(db_session, induct_id)
    except Exception:
        raise InternalServerException


induct_router = Router(
    path='/inducts',
    route_handlers=[
        get_induct,
        list_induct_links,
        replace_induct_links,
        list_induct_seats,
        replace_induct_seats,
        replace_induct,
        delete_induct,
    ],
)

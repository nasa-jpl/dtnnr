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
from litestar.openapi.datastructures import ResponseSpec
from msgspec import UNSET

from app.config import API_V1_PATH
from app.fields import NODE_NUMBER_MAX, SANA_SCID_MAX
from app.problem_details import (
    ExtraSourceEnum,
    ProblemDetailsExtraSchema,
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

from ..allocator.service import get as allocator_get
from ..band.service import get as band_get
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
from ..destination.schemas import (
    DestinationCreateSchema,
    DestinationSchema,
    DestinationWithoutHostIdSchema,
    IPQueryParam,
    to_destination_schema,
    to_destination_without_host_id_schema,
)
from ..destination.service import create as destination_create
from ..destination.service import (
    get_by_host_id_and_ip_address,
    get_by_host_id_and_registered_name,
    list_destinations,
)
from ..destination.views import validate_destination_value
from ..link.schemas import (
    LinkCreateSchema,
    LinkSchema,
    LinkWithoutHostIdSchema,
    to_link_schema,
)
from ..link.service import create as link_create
from ..link.service import create_rf as link_create_rf
from ..link.service import (
    list_links,
    replace_underlying_communication_services,
)
from ..node.service import get_by_FQNN
from ..operator.service import (
    check_node_number_allocated,
    format_allocated_node_numbers,
)
from ..operator.service import get as operator_get
from ..query import create_page_tokens, process_page_size, process_page_token
from ..schemas import (
    GENERIC_QUERY_PARAM_USAGE_NOTE,
    GENERIC_RESPONSE_DESCRIPTION,
    PaginatedRequest,
    QueryResponse,
)
from ..underlying_communication_service.schemas import (
    UnderlyingCommunicationServiceIDMeta,
)
from ..underlying_communication_service.service import get_nonmatching_ids
from .schemas import (
    HostCopySchema,
    HostCreateSchema,
    HostIDMeta,
    HostIDParam,
    HostQueryRequest,
    HostSchema,
    HostUpdateSchema,
    host_copy_response_example,
    to_host_schema,
)
from .service import (
    associate_contact,
    contact_is_associated,
    copy,
    create,
    delete,
    dissociate_contact,
    get,
    list_contacts,
    query,
    update,
)

if TYPE_CHECKING:
    from litestar import Request
    from sqlalchemy.orm import Session


@_get(
    path='/{host_id:int}',
    sync_to_thread=True,
    tags=['hosts'],
    summary='Get host',
    description='Retrieves a host by its `host_id`.',
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for GET {API_V1_PATH}/hosts/{HostIDMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {HostIDMeta.le}',
            validation_key_example='host_id',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description='Host ID in path parameter is not associated with a resource',
            detail_example='Host ID 86 does not exist',
        ),
    },
)
def get_host(db_session: Session, host_id: Annotated[int, HostIDParam]) -> HostSchema:
    host = get(db_session, host_id)
    if host is None:
        raise NotFoundException(f'Host ID {host_id} does not exist')
    return to_host_schema(host)


@_get(
    path='/',
    dependencies={'query_request': Provide(HostQueryRequest, sync_to_thread=True)},
    sync_to_thread=True,
    tags=['hosts'],
    summary='Query hosts',
    description=(
        f'Search for and fetch hosts.<br /><br />{GENERIC_QUERY_PARAM_USAGE_NOTE}'
    ),
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={400: pagination_400_response_spec(f'{API_V1_PATH}/hosts')},
)
def query_hosts(
    db_session: Session, query_request: HostQueryRequest
) -> QueryResponse[HostSchema]:
    path = '/hosts'
    try:
        bookmark = process_page_token(query_request, path)
    except Exception:
        raise
    page = query(db_session, process_page_size(query_request.max_page_size), bookmark)
    return QueryResponse(
        [to_host_schema(h) for (h,) in page],
        *create_page_tokens(query_request, path, page),
    )


@post(
    path='/',
    guards=[required_request_body_guard],
    sync_to_thread=True,
    tags=['hosts'],
    summary='Create host',
    description='Creates a new host.',
    operation_class=custom_operation(
        custom_reqbody(
            description=(
                'By default, the host is not under an operator.'
                ' Specify an operator for the host to be under with'
                ' the `operator_id` property.'
                ' Note that a node with a host that wants to associate with'
                ' an operator needs to be on a host under that operator.\n'
                '\n'
                'Use the `/operators` API for viewing existing operators and'
                ' creating new operators.'
            ),
            required=True,
        )
    ),
    response_headers=[LocationHeader, ContentLocationHeader],
    response_description='Host created, representation follows',
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=f'Validation failed for POST {API_V1_PATH}/hosts',
            validation_message_example=f'Invalid enum value 16',
            validation_key_example='word_size',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description='Operator ID in body is not associated with a resource',
            detail_example='Operator ID 556 does not exist',
        ),
    },
)
def create_host(db_session: Session, data: HostCreateSchema) -> Response[HostSchema]:
    if (
        data.operator_id is not None
        and operator_get(db_session, data.operator_id) is None
    ):
        raise NotFoundException(f'Operator ID {data.operator_id} does not exist')
    try:
        host = create(
            db_session,
            data.hostname,
            data.host_description,
            data.operator_id,
            data.sana_scid,
            data.word_size,
            data.newline,
        )
    except Exception:
        raise InternalServerException
    return Response(
        content=to_host_schema(host),
        headers={
            'Location': f'{API_V1_PATH}/hosts/{host.host_id}',
            'Content-Location': f'{API_V1_PATH}/hosts/{host.host_id}',
        },
    )


@patch(
    path='/{host_id:int}',
    sync_to_thread=True,
    tags=['hosts'],
    summary='Update host',
    description='Updates the host identified by `host_id` in the path parameter.',
    operation_class=custom_operation(
        custom_reqbody(
            description=(
                'If the host has nodes that are under an operator, updating'
                ' `host.operator_id` to `null` will also update all nodes under'
                ' the host to have a null `operator_id`. In contrast, setting'
                ' `host.operator_id` to a non-null value that is different from'
                ' the current `operator_id` will error because either 1) the new'
                ' operator is under a different allocator than the nodes under'
                ' the host, or 2) the new operator is under the same allocator'
                ' as the nodes under the host, but consequently the new operator'
                ' has not been allocated the node numbers used by the existing'
                ' nodes.<br />'
                '<br />'
                'If you want to update a host and all of its nodes to a new operator,'
                ' first update all the nodes with an operator to have a null'
                ' `operator_id`. Then update the host to the new operator, and update'
                ' the operator to have the right allocated node numbers. Finally,'
                ' update the nodes to use the new operator.<br />'
                '<br />'
                'Use the `/operators` API for viewing existing operators and creating'
                ' new operators.'
            ),
            required=False,
        )
    ),
    response_description='Host updated, representation follows',
    responses={
        400: create_400_response_spec(
            description=(
                'Bad request syntax, validation error, or the to-be-updated host'
                ' is being moved to a different operator which cannot currently'
                " be associated with the host's nodes"
            ),
            client_error_detail_example=(
                'Operator ID 451 is under allocator ID 974848, but node IDs: [8]'
                ' are under allocator ID 974994. You likely need to update these'
                ' nodes to have a null operator_id.'
            ),
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for PATCH {API_V1_PATH}/hosts/6'
            ),
            validation_message_example=f'Expected `int` <= {SANA_SCID_MAX}',
            validation_key_example='sana_scid',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description=(
                'Host ID in path parameter is not associated with a resource or'
                ' operator ID in body is not associated with a resource'
            ),
            detail_example='Host ID 86 does not exist',
        ),
    },
)
def update_host(
    db_session: Session,
    host_id: Annotated[int, HostIDParam],
    data: HostUpdateSchema = None,
) -> HostSchema:
    if data is None:
        data = HostUpdateSchema()
    host = get(db_session, host_id)
    if host is None:
        raise NotFoundException(f'Host ID {host_id} does not exist')

    operator_id = host.operator_id if data.operator_id is UNSET else data.operator_id

    if operator_id is not None:
        operator = operator_get(db_session, operator_id)
        if operator is None:
            raise NotFoundException(f'Operator ID {data.operator_id} does not exist')
        if operator_id != host.operator_id:
            node_ids_with_operator = [
                str(n.node_id) for n in host.nodes if n.operator is not None
            ]
            node_numbers_with_operator = [
                str(n.node_number) for n in host.nodes if n.operator is not None
            ]
            if (
                node_ids_with_operator
                and operator.allocator_id != host.operator.allocator_id
            ):
                raise ClientException(
                    f'Operator ID {operator_id} is under allocator ID'
                    f' {operator.allocator_id}, but node IDs:'
                    f' [{", ".join(node_ids_with_operator)}] are under allocator'
                    f' ID {host.operator.allocator_id}. You likely need to update'
                    ' these nodes to have a null operator_id.'
                )
            elif node_ids_with_operator:
                raise ClientException(
                    f'Node IDs: [{", ".join(node_ids_with_operator)}] use the node'
                    f' numbers: [{", ".join(node_numbers_with_operator)}] which have'
                    f' not been allocated to operator ID {operator_id}. You likely'
                    f' need to update these nodes to have a null operator_id.'
                )

    # TODO: consider making it possible to pass a query parameter that would
    # transfer the conflicting node numbers from the old operator to the new
    # operator.

    try:
        host = update(
            db_session,
            host_id,
            host.hostname if data.hostname is UNSET else data.hostname,
            (
                host.host_description
                if data.host_description is UNSET
                else data.host_description
            ),
            operator_id,
            host.sana_scid if data.sana_scid is UNSET else data.sana_scid,
            host.word_size if data.word_size is UNSET else data.word_size,
            host.newline if data.newline is UNSET else data.newline,
        )
    except Exception:
        raise InternalServerException
    return to_host_schema(host)


@post(
    path='/{host_id:int}/copies',
    sync_to_thread=True,
    tags=['hosts'],
    summary='Copy host',
    description=(
        'Copies the host identified by `host_id`.'
        ' This operation can also copy nodes on the to-be-copied host.'
    ),
    operation_class=custom_operation(
        custom_reqbody(
            description=(
                'By default, the copied host is not under an operator.'
                ' Specify an operator for the new host to be under with the'
                ' `operator_id` property.'
                ' Use the `/operators` API for viewing existing operators and'
                ' creating new operators.\n'
                '\n'
                'The `nodes` property which nodes of the host should be copied'
                ' to the new host.'
                ' Similar restrictions for creating nodes apply here:\n'
                '\n'
                '* By default, the node is under the Default Allocator'
                ' (`allocator_id` = 0).\n'
                '* If `operator_id` is not null, then `allocator_id` is not'
                ' used and the node will be created with'
                " the operator's allocator.\n"
                '\n'
                '* When placing a node under an operator, `node_number` must be'
                ' allocated to the operator, and the copied host must be under'
                ' the same operator.\n'
                '\n'
                '* The Fully Qualified Node Number (FQNN) of a copied node'
                ' cannot be used by an existing node or by another object in'
                ' `nodes`.'
                ' Use the `/nodes` API to view existing nodes.\n'
                '\n'
                'Note that you can make multiple copies of the same node'
                ' as long as the above restrictions are abided by.\n'
                '\n'
                'If `nodes` is an empty array (`[]`), then no nodes are copied.'
                ' This is the default behavior.'
            ),
            required=False,
        )
    ),
    response_headers=[LocationHeader, ContentLocationHeader],
    responses={
        201: ResponseSpec(
            data_container=HostSchema,
            description='Host copied, representation follows',
            examples=[host_copy_response_example],
        ),
        400: create_400_response_spec(
            description=(
                'Bad request syntax, validation error, `node_id` does not belong'
                ' under the host, node has non-null `operator_id` that does not'
                " match host's, node number is not allocated to operator,"
                ' allocator does not exist, or FQNN is already used or is'
                ' repeated.'
            ),
            client_error_detail_example=(
                '`nodes` contains objects that violate the rules for copying nodes'
            ),
            client_error_extra=[
                ProblemDetailsExtraSchema(
                    message='Node ID 9 does not belong to host ID 6',
                    key='nodes[0].node_id',
                    source=ExtraSourceEnum.BODY,
                ),
                ProblemDetailsExtraSchema(
                    message=(
                        'Operator ID 556 does not match with operator ID 410'
                        ' specified for the new host'
                    ),
                    key='nodes[0].operator_id',
                    source=ExtraSourceEnum.BODY,
                ),
                ProblemDetailsExtraSchema(
                    message=(
                        'Node number 8769 is not allocated to operator ID 410'
                        ' which has been allocated {[10000,20001)}'
                    ),
                    key='nodes[1].node_number',
                    source=ExtraSourceEnum.BODY,
                ),
                ProblemDetailsExtraSchema(
                    message='Allocator ID 34 does not exist',
                    key='nodes[2].allocator_id',
                    source=ExtraSourceEnum.BODY,
                ),
                ProblemDetailsExtraSchema(
                    message='FQNN (974994, 15498) already exists',
                    key='nodes[3].node_number',
                    source=ExtraSourceEnum.BODY,
                ),
                ProblemDetailsExtraSchema(
                    message=(
                        'FQNN (974994, 15532) is already specified to be used'
                        ' by nodes[4]'
                    ),
                    key='nodes[5].node_number',
                    source=ExtraSourceEnum.BODY,
                ),
            ],
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for POST {API_V1_PATH}/hosts/6/copies'
            ),
            validation_message_example=f'Expected `int` <= {NODE_NUMBER_MAX}',
            validation_key_example='nodes[0].node_number',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description=(
                'Host ID in path parameter is not associated with a resource or'
                ' `operator_id` in body for new host is not associated with a'
                ' resource'
            ),
            detail_example='Host ID 86 does not exist',
        ),
    },
)
def copy_host(
    db_session: Session,
    host_id: Annotated[int, HostIDParam],
    data: HostCopySchema = None,
) -> Response[HostSchema]:
    if data is None:
        data = HostCopySchema()
    host = get(db_session, host_id)
    if host is None:
        raise NotFoundException(f'Host ID {host_id} does not exist')

    operator = operator_get(db_session, data.operator_id)
    if data.operator_id is not None and operator is None:
        raise NotFoundException(f'Operator ID {data.operator_id} does not exist')

    nodes_errors: list[ProblemDetailsExtraSchema] = []
    # Map FQNN to index
    seen_FQNN: dict[tuple[int, int], int] = {}
    host_node_ids = [n.node_id for n in host.nodes]

    for n, index in zip(data.nodes, range(len(data.nodes))):
        key_prefix = f'nodes[{index}]'
        if n.node_id not in host_node_ids:
            nodes_errors.append(
                ProblemDetailsExtraSchema(
                    message=f'Node ID {n.node_id} does not belong to host ID {host_id}',
                    key=f'{key_prefix}.node_id',
                    source=ExtraSourceEnum.BODY,
                )
            )

        allocator_id = n.allocator_id
        if n.operator_id is not None and n.operator_id != data.operator_id:
            # Node is on copied host, so if it has an operator, it must match
            nodes_errors.append(
                ProblemDetailsExtraSchema(
                    message=(
                        f'Operator ID {n.operator_id} does not match with'
                        f' operator ID {data.operator_id} specified for the'
                        ' new host'
                    ),
                    key=f'{key_prefix}.operator_id',
                    source=ExtraSourceEnum.BODY,
                )
            )
        elif n.operator_id is not None:
            allocator_id = operator.allocator_id
            n.allocator_id = allocator_id
            if not check_node_number_allocated(
                db_session, n.operator_id, n.node_number
            ):
                nodes_errors.append(
                    ProblemDetailsExtraSchema(
                        message=(
                            f'Node number {n.node_number} is not allocated to'
                            f' operator ID {n.operator_id} which has been'
                            f' allocated {
                                format_allocated_node_numbers(db_session, n.operator_id)
                            }'
                        ),
                        key=f'{key_prefix}.node_number',
                        source=ExtraSourceEnum.BODY,
                    )
                )

        # Does not happen when operator_id is set, so safe to use allocator_id
        # as the key.
        if not allocator_get(db_session, allocator_id):
            nodes_errors.append(
                ProblemDetailsExtraSchema(
                    message=f'Allocator ID {allocator_id} does not exist',
                    key=f'{key_prefix}.allocator_id',
                    source=ExtraSourceEnum.BODY,
                )
            )
        else:
            if get_by_FQNN(db_session, allocator_id, n.node_number):
                nodes_errors.append(
                    ProblemDetailsExtraSchema(
                        message=(
                            f'FQNN ({allocator_id}, {n.node_number}) already exists'
                        ),
                        key=f'{key_prefix}.node_number',
                        source=ExtraSourceEnum.BODY,
                    )
                )

            using_FQNN_index = seen_FQNN.get((allocator_id, n.node_number))
            if using_FQNN_index is not None:
                nodes_errors.append(
                    ProblemDetailsExtraSchema(
                        message=(
                            f'FQNN ({allocator_id}, {n.node_number}) is already'
                            f' specified to be used by nodes[{using_FQNN_index}]'
                        ),
                        key=f'{key_prefix}.node_number',
                        source=ExtraSourceEnum.BODY,
                    )
                )
            else:
                seen_FQNN[(allocator_id, n.node_number)] = index

    if nodes_errors:
        raise ClientException(
            '`nodes` contains objects that violate the rules for copying nodes',
            extra=nodes_errors,
        )

    try:
        copied_host = copy(db_session, host_id, data.operator_id, data.nodes)
    except Exception:
        raise InternalServerException
    return Response(
        content=to_host_schema(copied_host),
        headers={
            'Location': f'{API_V1_PATH}/hosts/{copied_host.host_id}',
            'Content-Location': f'{API_V1_PATH}/hosts/{copied_host.host_id}',
        },
    )


@_delete(
    path='/{host_id:int}',
    sync_to_thread=True,
    tags=['hosts'],
    summary='Delete host',
    description=(
        'Deletes the host identified by `host_id`.<br />'
        '<br />'
        'Deleting a host will set `host_id` to `null` in associated nodes.'
        ' Inducts and seats that reference host children (links and destinations)'
        ' will have those referencing properties set to `null` as well.'
    ),
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for DELETE {API_V1_PATH}/hosts/{HostIDMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {HostIDMeta.le}',
            validation_key_example='host_id',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description='Host ID in path parameter is not associated with a resource',
            detail_example='Host ID 86 does not exist',
        ),
    },
)
def delete_host(db_session: Session, host_id: Annotated[int, HostIDParam]) -> None:
    if get(db_session, host_id) is None:
        raise NotFoundException(f'Host ID {host_id} does not exist')
    try:
        delete(db_session, host_id)
    except Exception:
        raise InternalServerException


@_get(
    path='/{host_id:int}/links',
    sync_to_thread=True,
    tags=['hosts', 'links'],
    summary='List host links',
    description=(
        'Lists all links associated with the host identified by `host_id`.<br />'
        '<br />'
        f'{GENERIC_QUERY_PARAM_USAGE_NOTE}'
    ),
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={
        400: pagination_400_response_spec(f'{API_V1_PATH}/hosts/6/links'),
        404: create_404_response_spec(
            description='Host ID in path parameter is not associated with a resource',
            detail_example='Host ID 86 does not exist',
        ),
    },
)
def list_host_links(
    db_session: Session,
    host_id: Annotated[int, HostIDParam],
    paginated_request: PaginatedRequest,
) -> QueryResponse[LinkWithoutHostIdSchema]:
    if get(db_session, host_id) is None:
        raise NotFoundException(f'Host ID {host_id} does not exist')
    path = f'/hosts/{host_id}/links'
    try:
        bookmark = process_page_token(paginated_request, path)
    except Exception:
        raise
    page = list_links(
        db_session,
        host_id,
        process_page_size(paginated_request.max_page_size),
        bookmark,
    )
    return QueryResponse(
        [to_link_schema(_, with_host=False) for (_,) in page],
        *create_page_tokens(paginated_request, path, page),
    )


@post(
    path='/{host_id:int}/links',
    sync_to_thread=True,
    tags=['hosts', 'links'],
    summary='Create link connected to host',
    description=(
        'Creates a new link under the host identified by `host_id`.<br />'
        '<br />'
        'Use the `/underlying-communication-services` API to obtain IDs that can'
        ' be passed in the `underlying_communication_service_ids` array.<br />'
        'Use the `/bands` API to obtain IDs that can be passed for'
        ' `link_rf.band_id`.'
    ),
    operation_class=custom_operation(
        custom_reqbody(
            description=(
                '`underlying_communication_service_ids` can consist of an array of'
                ' strings or integers. Duplicate values are eliminated. There is no'
                ' guarantee that links and services are associated in the order of'
                ' IDs in the array.'
            ),
            required=False,
        )
    ),
    response_headers=[LocationHeader, ContentLocationHeader],
    response_description='Link created, representation follows',
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for POST {API_V1_PATH}/hosts/6/links'
            ),
            validation_message_example=(
                f'Expected `int` <= {UnderlyingCommunicationServiceIDMeta.le}'
            ),
            validation_key_example='underlying_communication_service_ids[0]',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description=(
                'Host ID in path parameter is not associated with a resource,'
                ' some ID from `underlying_communication_service_ids` is not'
                ' associated with a resource, or band ID in `link_rf` is not'
                ' associated with a resource'
            ),
            detail_example=(
                '`extra` contains IDs from `underlying_communication_service_ids`'
                ' that refer to services that do not exist'
            ),
            extra=[str(2**31 - 2), str(2**31 - 1)],
        ),
    },
)
def create_link(
    db_session: Session,
    host_id: Annotated[int, HostIDParam],
    data: LinkCreateSchema = None,
) -> Response[LinkSchema]:
    if data is None:
        data = LinkCreateSchema()
    if get(db_session, host_id) is None:
        raise NotFoundException(f'Host ID {host_id} does not exist')

    if data.underlying_communication_service_ids:
        ids = get_nonmatching_ids(db_session, data.underlying_communication_service_ids)
        if ids:
            raise NotFoundException(
                '`extra` contains IDs from `underlying_communication_service_ids`'
                ' that refer to services that do not exist',
                extra=ids,
            )

    if (
        data.link_rf is not None
        and data.link_rf.band_id is not None
        and band_get(db_session, data.link_rf.band_id) is None
    ):
        raise NotFoundException(f'Band ID {data.link_rf.band_id} does not exist')

    try:
        link = link_create(
            db_session,
            host_id,
            data.direction,
            'rf' if data.link_rf is not None else None,
        )
        if data.link_rf is not None:
            link = link_create_rf(db_session, link.link_id, data.link_rf.band_id)
        replace_underlying_communication_services(
            db_session, link.link_id, data.underlying_communication_service_ids
        )
        db_session.commit()
    except Exception:
        raise InternalServerException

    return Response(
        content=to_link_schema(link),
        headers={
            'Location': f'{API_V1_PATH}/links/{link.link_id}',
            'Content-Location': f'{API_V1_PATH}/links/{link.link_id}',
        },
    )


@_get(
    path='/{host_id:int}/destinations',
    sync_to_thread=True,
    tags=['hosts', 'destinations'],
    summary='List host destinations',
    description=(
        'Lists all destinations associated with the host identified by `host_id`.'
        '<br /><br />'
        f'{GENERIC_QUERY_PARAM_USAGE_NOTE}'
    ),
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={
        400: pagination_400_response_spec(f'{API_V1_PATH}/hosts/6/destinations'),
        404: create_404_response_spec(
            description='Host ID in path parameter is not associated with a resource',
            detail_example='Host ID 86 does not exist',
        ),
    },
)
def list_host_destinations(
    db_session: Session,
    host_id: Annotated[int, HostIDParam],
    paginated_request: PaginatedRequest,
) -> QueryResponse[DestinationWithoutHostIdSchema]:
    if get(db_session, host_id) is None:
        raise NotFoundException(f'Host ID {host_id} does not exist')
    path = f'/hosts/{host_id}/destinations'
    try:
        bookmark = process_page_token(paginated_request, path)
    except Exception:
        raise
    page = list_destinations(
        db_session,
        host_id,
        process_page_size(paginated_request.max_page_size),
        bookmark,
    )
    return QueryResponse(
        [to_destination_without_host_id_schema(_) for (_,) in page],
        *create_page_tokens(paginated_request, path, page),
    )


@post(
    path='/{host_id:int}/destinations',
    guards=[required_request_body_guard],
    sync_to_thread=True,
    tags=['hosts', 'destinations'],
    summary='Create destination',
    description=(
        'Creates a new destination under the host identified by `host_id`.<br />'
        '<br />'
        'Destinations with duplicate values are not allowed under the same host.'
        ' Use the `GET /hosts/{host_id}/destinations` API to see what values are'
        ' already used.'
    ),
    response_headers=[LocationHeader, ContentLocationHeader],
    response_description='Destination created, representation follows',
    responses={
        400: create_400_response_spec(
            description=(
                'Bad request syntax, validation error, or destination value'
                ' already used by an existing resource'
            ),
            client_error_detail_example=(
                "A destination with value '192.0.2.1' is already associated with"
                ' host ID 6'
            ),
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for POST {API_V1_PATH}/hosts/6/destinations?ip=true'
            ),
            validation_message_example=(
                "'192.000.002.001' does not appear to be an IPv4 or IPv6 address"
            ),
            validation_key_example='destination_value',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description='Host ID in path parameter is not associated with a resource',
            detail_example='Host ID 86 does not exist',
        ),
    },
)
def create_destination(
    request: Request,
    db_session: Session,
    host_id: Annotated[int, HostIDParam],
    data: DestinationCreateSchema,
    ip: Annotated[bool, IPQueryParam] = False,
) -> Response[DestinationSchema]:
    destination_value, is_ip = validate_destination_value(
        request, data.destination_value, ip
    )
    if get(db_session, host_id) is None:
        raise NotFoundException(f'Host ID {host_id} does not exist')

    if (
        is_ip and get_by_host_id_and_ip_address(db_session, host_id, destination_value)
    ) or get_by_host_id_and_registered_name(db_session, host_id, destination_value):
        raise ClientException(
            f"A destination with value '{destination_value}' is already associated"
            f' with host ID {host_id}'
        )

    try:
        if is_ip:
            destination = destination_create(
                db_session, host_id, ip_address=destination_value
            )
        else:
            destination = destination_create(
                db_session, host_id, registered_name=destination_value
            )
    except Exception:
        raise InternalServerException

    return Response(
        content=to_destination_schema(destination),
        headers={
            'Location': f'{API_V1_PATH}/destinations/{destination.destination_id}',
            'Content-Location': (
                f'{API_V1_PATH}/destinations/{destination.destination_id}'
            ),
        },
    )


@list_resource_contacts_decorator('host_id', 'hosts', 'host', '6', '86')
def list_host_contacts(
    db_session: Session,
    host_id: Annotated[int, HostIDParam],
    paginated_request: PaginatedRequest,
) -> QueryResponse[ContactSchema]:
    try:
        return list_resource_contacts_operation(
            db_session, host_id, paginated_request, get, 'host', 'hosts', list_contacts
        )
    except Exception:
        raise


@add_contact_decorator('host_id', 'hosts', 'host', '6', '556')
def add_contact(
    db_session: Session,
    host_id: Annotated[int, HostIDParam],
    data: ContactAddSchema,
) -> Response[ContactSchema]:
    try:
        return add_contact_operation(
            db_session,
            host_id,
            data,
            get,
            'host',
            contact_is_associated,
            associate_contact,
        )
    except Exception:
        raise


@remove_contact_decorator('host_id', 'hosts', 'host', '6', HostIDMeta.le, '86')
def remove_contact(
    db_session: Session,
    host_id: Annotated[int, HostIDParam],
    contact_id: Annotated[int, ContactIDParam],
) -> None:
    try:
        remove_contact_operation(
            db_session,
            host_id,
            contact_id,
            get,
            'host',
            contact_is_associated,
            dissociate_contact,
        )
    except Exception:
        raise


host_router = Router(
    path='/hosts',
    route_handlers=[
        get_host,
        query_hosts,
        create_host,
        update_host,
        copy_host,
        delete_host,
        list_host_links,
        create_link,
        list_host_destinations,
        create_destination,
        list_host_contacts,
        add_contact,
        remove_contact,
    ],
)

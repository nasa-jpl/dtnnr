from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Annotated

from litestar import Request, Response, Router, patch, post, put
from litestar import delete as _delete
from litestar import get as _get
from litestar.di import Provide
from litestar.exceptions import (
    ClientException,
    InternalServerException,
    NotFoundException,
    ValidationException,
)
from litestar.openapi.datastructures import ResponseSpec
from litestar.openapi.spec import Example
from litestar.status_codes import HTTP_204_NO_CONTENT
from msgspec import UNSET

from app.config import API_V1_PATH
from app.models import no_duct_name_known_cli_not_ip
from app.problem_details import (
    ExtraSourceEnum,
    ProblemDetailsExceptionSchema,
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
from ..cl_protocol.schemas import (
    CL_PROTOCOL_CLASS_DEFAULT_VALUES_DESC,
    ClProtocolClassEnum,
    ClProtocolCreateSchema,
    ClProtocolSchema,
    ClProtocolWithoutNodeIdSchema,
    protocol_class_arr_to_int,
    protocol_class_int_to_arr,
    to_cl_protocol_schema,
    to_cl_protocol_without_node_id_schema,
)
from ..cl_protocol.service import create as cl_protocol_create
from ..cl_protocol.service import get as cl_protocol_get
from ..cl_protocol.service import get_by_details as cl_protocol_get_by_details
from ..cl_protocol.service import get_cl_protocol_check_value, list_cl_protocols
from ..contact.schemas import ContactAddSchema, ContactIDParam, ContactSchema
from ..contact.views import (
    add_contact_decorator,
    add_contact_operation,
    list_resource_contacts_decorator,
    list_resource_contacts_operation,
    remove_contact_decorator,
    remove_contact_operation,
)
from ..destination.service import get as destination_get
from ..endpoint.schemas import (
    EndpointIMCCreateBody,
    EndpointIMCReplaceBody,
    EndpointIMCReplaceSchema,
    EndpointIMCSchema,
    EndpointIMCUpdateBody,
    EndpointIMCUpdateSchema,
    EndpointIPNCreateBody,
    EndpointIPNReplaceBody,
    EndpointIPNReplaceSchema,
    EndpointIPNSchema,
    EndpointIPNUpdateBody,
    EndpointIPNUpdateSchema,
    GroupNumberMeta,
    GroupNumberParam,
    ServiceNumberMeta,
    ServiceNumberParam,
    parse_ipn_uri,
    to_endpoint_imc_schema,
    to_endpoint_ipn_schema,
    to_imc_uri,
    to_ipn_uri,
)
from ..endpoint.service import (
    create_imc,
    create_ipn,
    delete_imc,
    delete_ipn,
    get_imc,
    get_ipn,
    list_imc,
    list_ipn,
    replace_imc,
    replace_ipn,
    update_imc,
    update_ipn,
)
from ..host.service import get as host_get
from ..induct.schemas import (
    INDUCT_WRITE_DESCRIPTION,
    DuctNameIpCreateSchema,
    InductCreateBody,
    InductCreateSchema,
    InductSchema,
    InductWithoutNodeIdSchema,
    induct_examples,
    to_induct_schema,
    to_induct_without_node_id_schema,
)
from ..induct.service import create as induct_create
from ..induct.service import create_ip as induct_create_ip
from ..induct.service import list_inducts
from ..induct.views import check_induct_constraints
from ..operator.service import (
    check_node_number_allocated,
    format_allocated_node_numbers,
)
from ..operator.service import get as operator_get
from ..query import create_page_tokens, process_page_size, process_page_token
from ..schemas import (
    GENERIC_QUERY_PARAM_USAGE_NOTE,
    GENERIC_RESPONSE_DESCRIPTION,
    NextPageTokenMeta,
    PaginatedRequest,
    PrevPageTokenMeta,
    QueryResponse,
)
from ..seat.schemas import (
    SEAT_WRITE_DESCRIPTION,
    PortNumberMeta,
    SeatCreateSchema,
    SeatSchema,
    SeatWithoutNodeIdSchema,
    to_seat_schema,
    to_seat_without_node_id_schema,
)
from ..seat.service import create as seat_create
from ..seat.service import create_ip as seat_create_ip
from ..seat.service import list_seats
from .schemas import (
    IONCONFIG_VALUES_DESC,
    DestinationRefModeParam,
    DestinationRefModeParamCopyNode,
    NodeCopyBody,
    NodeCopySchema,
    NodeCreateSchema,
    NodeIDMeta,
    NodeIDParam,
    NodeNumberMeta,
    NodeQueryRequest,
    NodeSchema,
    NodeUpdateSchema,
    config_flags_arr_to_int,
    node_copy_response_example,
    node_create_response_example,
    to_node_schema,
)
from .service import (
    DestinationRefModeEnum,
    associate_contact,
    contact_is_associated,
    copy,
    create,
    delete,
    dissociate_contact,
    get,
    get_by_FQNN,
    list_contacts,
    query,
    update,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@_get(
    path='/{node_id:int}',
    sync_to_thread=True,
    tags=['nodes'],
    summary='Get node',
    description='Retrieves a node by its `node_id`.',
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for GET {API_V1_PATH}/nodes/{NodeIDMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {NodeIDMeta.le}',
            validation_key_example='node_id',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description='Node ID in path parameter is not associated with a resource',
            detail_example='Node ID 429204 does not exist',
        ),
    },
)
def get_node(db_session: Session, node_id: Annotated[int, NodeIDParam]) -> NodeSchema:
    node = get(db_session, node_id)
    if node is None:
        raise NotFoundException(f'Node ID {node_id} does not exist')
    return to_node_schema(node)


@_get(
    path='/',
    dependencies={'query_request': Provide(NodeQueryRequest, sync_to_thread=True)},
    sync_to_thread=True,
    tags=['nodes'],
    summary='Query nodes',
    description=(
        f'Search for and fetch nodes.<br /><br />{GENERIC_QUERY_PARAM_USAGE_NOTE}'
    ),
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={400: pagination_400_response_spec(f'{API_V1_PATH}/nodes')},
)
def query_nodes(
    db_session: Session, query_request: NodeQueryRequest
) -> QueryResponse[NodeSchema]:
    path = '/nodes'
    try:
        bookmark = process_page_token(query_request, path)
    except Exception:
        raise
    page = query(db_session, process_page_size(query_request.max_page_size), bookmark)
    return QueryResponse(
        [to_node_schema(n) for (n,) in page],
        *create_page_tokens(query_request, path, page),
    )


@post(
    path='/',
    guards=[required_request_body_guard],
    sync_to_thread=True,
    tags=['nodes'],
    summary='Create node',
    description=(
        'Creates a new node.'
        ' To associate the node with an allocator, operator, and host,'
        ' those resources need to exist.\n'
        '<br />'
        'Use the `/allocators` API for viewing existing allocators and creating'
        ' new allocators.<br />'
        '<br />'
        'Use the `/operators` API for viewing existing operators and creating new'
        ' operators.<br />'
        '<br />'
        'Use the `/hosts` API for viewing existing hosts and creating new hosts.'
    ),
    operation_class=custom_operation(
        custom_reqbody(
            description=(
                'By default, the node is under the Default Allocator'
                ' (`allocator_id` = 0).<br />'
                '<br />'
                'If `operator_id` is not null, then `allocator_id` in the request'
                ' body will not be used and the node will be created with the'
                " operator's allocator.<br />"
                '<br />'
                'When placing a node under an operator, `node_number` must be'
                ' allocated to the operator.<br />'
                '<br />'
                'The Fully Qualified Node Number (FQNN) of the to-be-created node'
                ' cannot be used by an existing node. Use the `/nodes` API to view'
                ' existing nodes.<br />'
                '<br />'
                "If `host_id` and `operator_id` are both not null, then the host's"
                ' `operator_id` must match what you pass for `operator_id`. Note'
                ' that you cannot have both `host_id` and `operator_id` as not'
                ' null if the host is not under an operator.<br />'
                '<br />'
                f'{IONCONFIG_VALUES_DESC}'
            ),
            required=True,
        )
    ),
    response_headers=[LocationHeader, ContentLocationHeader],
    response_description='Node created, representation follows',
    responses={
        201: ResponseSpec(
            data_container=NodeSchema,
            description='Node created, representation follows',
            examples=[node_create_response_example],
        ),
        400: create_400_response_spec(
            description=(
                'Bad request syntax, validation error, tried to associate node'
                ' with an operator while placing node on host with a different'
                ' operator, node number is not allocated to operator, or FQNN is'
                ' already used'
            ),
            client_error_detail_example=(
                'Node number 8769 is not allocated to operator ID 410 which has'
                ' been allocated {[10000,20001)}'
            ),
            include_validation_error=True,
            validation_detail_example=f'Validation failed for POST {API_V1_PATH}/nodes',
            validation_message_example=f'Expected `int` <= {NodeNumberMeta.le}',
            validation_key_example='node_number',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description=(
                'Host ID, operator ID, or allocator ID in body are not associated'
                ' with resources'
            ),
            detail_example='Operator ID 556 does not exist',
        ),
    },
)
def create_node(db_session: Session, data: NodeCreateSchema) -> Response[NodeSchema]:
    if data.host_id is not None:
        host = host_get(db_session, data.host_id)
        if host is None:
            raise NotFoundException(f'Host ID {data.host_id} does not exist')
    else:
        host = None

    allocator_id = data.allocator_id

    # Use Allocator -> Operator -> Node policy if operator_id is not null.
    # Regardless of what allocator_id was sent, it's replaced by the operator's.
    if data.operator_id is not None:
        operator = operator_get(db_session, data.operator_id)
        if operator is None:
            raise NotFoundException(f'Operator ID {data.operator_id} does not exist')
        if host is not None and host.operator_id != data.operator_id:
            if host.operator_id is None:
                raise ClientException(
                    'Node cannot associate with an operator while on a host without'
                    ' an operator'
                )
            raise ClientException(
                f'Operator ID {data.operator_id} does not match host operator ID'
                f' {host.operator_id}'
            )
        allocator_id = operator.allocator_id
        if not check_node_number_allocated(
            db_session, data.operator_id, data.node_number
        ):
            raise ClientException(
                f'Node number {data.node_number} is not allocated to operator ID'
                f' {data.operator_id} which has been allocated'
                f' {format_allocated_node_numbers(db_session, data.operator_id)}'
            )

    # Should never be true when data.operator_id is not null
    if allocator_get(db_session, allocator_id) is None:
        raise NotFoundException(f'Allocator ID {allocator_id} does not exist')

    _other = get_by_FQNN(db_session, allocator_id, data.node_number)
    if _other is not None:
        raise ClientException(
            f'FQNN ({allocator_id}, {data.node_number}) is already used by node'
            f' ID {_other.node_id}'
        )

    try:
        node = create(
            db_session,
            data.node_number,
            allocator_id,
            operator_id=data.operator_id,
            host_id=data.host_id,
            sdr_wm_size=data.sdr_wm_size,
            sdr_config_flags=config_flags_arr_to_int(data.sdr_config_flags),
            heap_words=data.heap_words,
            wm_size=data.wm_size,
            node_name=data.node_name,
            comments=data.comments,
        )
    except Exception:
        raise InternalServerException

    return Response(
        content=to_node_schema(node),
        headers={
            'Location': f'{API_V1_PATH}/nodes/{node.node_id}',
            'Content-Location': f'{API_V1_PATH}/nodes/{node.node_id}',
        },
    )


@patch(
    path='/{node_id:int}',
    sync_to_thread=True,
    tags=['nodes'],
    summary='Update node',
    description=(
        'Updates the node identified by `node_id` in the path.'
        ' To associate the node with an allocator, operator, and host,'
        ' those resources need to exist.\n'
        '\n'
        'Use the `/allocators` API for viewing existing allocators and creating'
        ' new allocators.\n'
        '\n'
        'Use the `/operators` API for viewing existing operators and creating new'
        ' operators.\n'
        '\n'
        'Use the `/hosts` API for viewing existing hosts and creating new hosts.'
    ),
    operation_class=custom_operation(
        custom_reqbody(
            description=(
                "If fulfilling the request means the node's `operator_id` is"
                ' not null, then the node will be updated to use'
                " the operator's allocator, regardless of what value is"
                ' passed for `allocator_id`.\n'
                '\n'
                "When placing a node under an operator, the node's node number"
                ' must be allocated to the operator.\n'
                '\n'
                'The Fully Qualified Node Number (FQNN) cannot be updated to'
                ' conflict with another existing node. Use the `/nodes` API to'
                ' view existing nodes.\n'
                '\n'
                'If the request would make the node be on a host and an'
                ' operator, then the host must be associated with said operator.\n'
                '\n'
                "If a node changes host, all associations between the node's"
                ' inducts / seats with links will be **deleted**.\n'
                '\n'
                f'{IONCONFIG_VALUES_DESC}'
            ),
            required=False,
        )
    ),
    response_description='Node updated, representation follows',
    responses={
        400: create_400_response_spec(
            description=(
                'Bad request syntax, validation error, tried to associate node'
                ' with an operator while placing node on host with a different'
                ' operator, node number is not allocated to operator, FQNN is'
                ' already used, or invalid "destination_ref_mode"'
            ),
            client_error_detail_example=(
                f"Cannot use '{DestinationRefModeEnum.COPY}' for"
                ' `destination_ref_mode` when node is on a host but the'
                ' operation would make the node hostless'
            ),
            include_validation_error=True,
            validation_detail_example=(
                'Validation failed for PATCH'
                f' {API_V1_PATH}/nodes/{NodeIDMeta.examples[0]}'
            ),
            validation_message_example="Invalid enum value 'blah'",
            validation_key_example='destination_ref_mode',
            validation_source_example='query',
        ),
        404: create_404_response_spec(
            description=(
                'Node ID in path parameter is not associated with a resource.'
                ' Host ID, operator ID, or allocator ID in body are not associated'
                ' with resources'
            ),
            detail_example='Host ID 86 does not exist',
        ),
    },
)
def update_node(
    db_session: Session,
    node_id: Annotated[int, NodeIDParam],
    destination_ref_mode: DestinationRefModeParam = DestinationRefModeEnum.NULLIFY,
    data: NodeUpdateSchema = None,
) -> NodeSchema:
    if data is None:
        data = NodeUpdateSchema()
    node = get(db_session, node_id)
    if node is None:
        raise NotFoundException(f'Node ID {node_id} does not exist')

    if data.host_id is UNSET:
        host_id = node.host_id
        host = node.host
    elif data.host_id is None:
        host_id = None
        host = None
    else:
        host_id = data.host_id
        host = host_get(db_session, host_id)
        if host is None:
            raise NotFoundException(f'Host ID {data.host_id} does not exist')

    if (
        node.host_id is not None
        and host_id is None
        and destination_ref_mode
        in (DestinationRefModeEnum.ASSOCIATE, DestinationRefModeEnum.COPY)
    ):
        raise ClientException(
            f"Cannot use '{destination_ref_mode}' for `destination_ref_mode` when"
            ' node is on a host but the operation would make the node hostless'
        )

    node_number = node.node_number if data.node_number is UNSET else data.node_number
    allocator_id = (
        node.allocator_id if data.allocator_id is UNSET else data.allocator_id
    )
    operator_id = node.operator_id if data.operator_id is UNSET else data.operator_id
    if operator_id is not None:
        operator = operator_get(db_session, operator_id)
        if operator is None:
            raise NotFoundException(f'Operator ID {operator_id} does not exist')
        if host is not None and host.operator_id != operator_id:
            if host.operator_id is None:
                raise ClientException(
                    'Node cannot associate with an operator while on a host without'
                    ' an operator'
                )
            raise ClientException(
                f'Operator ID {operator_id} does not match host operator ID'
                f' {host.operator_id}'
            )
        allocator_id = operator.allocator_id
        if not check_node_number_allocated(db_session, operator_id, node_number):
            raise ClientException(
                f'Node number {node_number} is not allocated to operator ID'
                f' {operator_id} which has been allocated'
                f' {format_allocated_node_numbers(db_session, operator_id)}'
            )

    # Should never be true when operator_id is not None
    if (
        allocator_id != node.allocator_id
        and allocator_get(db_session, allocator_id) is None
    ):
        raise NotFoundException(f'Allocator ID {allocator_id} does not exist')

    _other = get_by_FQNN(db_session, allocator_id, node_number)
    if node_number != node.node_number and _other is not None:
        raise ClientException(
            f'FQNN ({allocator_id}, {node_number}) is already used by node'
            f' ID {_other.node_id}'
        )

    try:
        update(
            db_session,
            node_id,
            node_number,
            allocator_id,
            operator_id,
            host_id,
            (
                node.sdr_config_flags
                if data.sdr_config_flags is UNSET
                else config_flags_arr_to_int(data.sdr_config_flags)
            ),
            node.wm_size if data.wm_size is UNSET else data.wm_size,
            node.sdr_wm_size if data.sdr_wm_size is UNSET else data.sdr_wm_size,
            node.heap_words if data.heap_words is UNSET else data.heap_words,
            node.node_name if data.node_name is UNSET else data.node_name,
            node.comments if data.comments is UNSET else data.comments,
            destination_ref_mode,
        )
    except Exception:
        raise InternalServerException
    return to_node_schema(node)


@post(
    path='/{node_id:int}/copies',
    guards=[required_request_body_guard],
    sync_to_thread=True,
    tags=['nodes'],
    summary='Copy node',
    description=(
        'Copies the node identified by `node_id` in the path.'
        ' To associate the new node with an allocator, operator, and host,'
        ' those resources need to exist.\n'
        '\n'
        'Use the `/allocators` API for viewing existing allocators and creating'
        ' new allocators.\n'
        '\n'
        'Use the `/operators` API for viewing existing operators and creating new'
        ' operators.\n'
        '\n'
        'Use the `/hosts` API for viewing existing hosts and creating new hosts.'
    ),
    operation_class=custom_operation(
        custom_reqbody(
            description=(
                'A new FQNN is required since a new node is being created.'
                ' By default, the node is under the Default Allocator'
                ' (`allocator_id` = 0).\n'
                '\n'
                'If `operator_id` is not null, then `allocator_id` in the request'
                ' body will not be used and the node will be created with the'
                " operator's allocator.\n"
                '\n'
                'When placing a node under an operator, `node_number` must be'
                ' allocated to the operator.\n'
                '\n'
                'The Fully Qualified Node Number (FQNN) of the to-be-created node'
                ' cannot be used by an existing node. Use the `/nodes` API to view'
                ' existing nodes.\n'
                '\n'
                "If `host_id` and `operator_id` are both not null, then the host's"
                ' `operator_id` must match what you pass for `operator_id`. Note'
                ' that you cannot have both `host_id` and `operator_id` as not'
                ' null if the host is not under an operator.\n'
                '\n'
                'If the copied node is on a different host than the'
                ' node identified by `node_id`, then the copied node will'
                ' not have any associations between inducts / seats with links.'
            ),
            required=True,
        )
    ),
    response_headers=[LocationHeader, ContentLocationHeader],
    responses={
        201: ResponseSpec(
            data_container=NodeSchema,
            description='Node copied, representation follows',
            examples=[node_copy_response_example],
        ),
        400: create_400_response_spec(
            description=(
                'Bad request syntax, validation error, tried to associate node'
                ' with an operator while placing node on host with a different'
                ' operator, node number is not allocated to operator, FQNN is'
                ' already used, or invalid "destination_ref_mode"'
            ),
            client_error_detail_example=(
                f"Cannot use '{DestinationRefModeEnum.COPY}' for"
                ' `destination_ref_mode` when node is on a host but the'
                ' operation would make the node hostless'
            ),
            include_validation_error=True,
            validation_detail_example=(
                'Validation failed for POST'
                f' {API_V1_PATH}/nodes/{NodeIDMeta.examples[0]}/copies'
            ),
            validation_message_example="Invalid enum value 'blah'",
            validation_key_example='destination_ref_mode',
            validation_source_example='query',
        ),
        404: create_404_response_spec(
            description=(
                'Node ID in path parameter is not associated with a resource.'
                ' Host ID, operator ID, or allocator ID in body are not associated'
                ' with resources'
            ),
            detail_example='Allocator ID 34 does not exist',
        ),
    },
)
def copy_node(
    db_session: Session,
    node_id: Annotated[int, NodeIDParam],
    data: Annotated[NodeCopySchema, NodeCopyBody],
    destination_ref_mode: DestinationRefModeParamCopyNode = DestinationRefModeEnum.NULLIFY,
) -> Response[NodeSchema]:
    node = get(db_session, node_id)
    if node is None:
        raise NotFoundException(f'Node ID {node_id} does not exist')

    if data.host_id is not None:
        host = host_get(db_session, data.host_id)
        if host is None:
            raise NotFoundException(f'Host ID {data.host_id} does not exist')
    else:
        host = None

    if (
        node.host_id is not None
        and data.host_id is None
        and destination_ref_mode
        in (DestinationRefModeEnum.ASSOCIATE, DestinationRefModeEnum.COPY)
    ):
        raise ClientException(
            f"Cannot use '{destination_ref_mode}' for `destination_ref_mode` when"
            ' the to-be-copied node is on a host but the node to be created will'
            ' be hostless'
        )

    # API says destination_ref_mode only has an effect when host_id is different,
    # but internally, we do everything through a single service function, so we
    # need to make destination_ref_mode right.
    if node.host_id is None:
        destination_ref_mode = DestinationRefModeEnum.NULLIFY
    elif node.host_id == data.host_id:
        # We can use either associate or copy, the service function handles
        # them the same in this case.
        destination_ref_mode = DestinationRefModeEnum.ASSOCIATE

    allocator_id = data.allocator_id

    # Use Allocator -> Operator -> Node policy if operator_id is not null.
    # Regardless of what allocator_id was sent, it's replaced by the operator's.
    if data.operator_id is not None:
        operator = operator_get(db_session, data.operator_id)
        if operator is None:
            raise NotFoundException(f'Operator ID {data.operator_id} does not exist')
        if host is not None and host.operator_id != data.operator_id:
            if host.operator_id is None:
                raise ClientException(
                    'Node cannot associate with an operator while on a host without'
                    ' an operator'
                )
            raise ClientException(
                f'Operator ID {data.operator_id} does not match host operator ID'
                f' {host.operator_id}'
            )
        allocator_id = operator.allocator_id
        if not check_node_number_allocated(
            db_session, data.operator_id, data.node_number
        ):
            raise ClientException(
                f'Node number {data.node_number} is not allocated to operator ID'
                f' {data.operator_id} which has been allocated'
                f' {format_allocated_node_numbers(db_session, data.operator_id)}'
            )

    # Should never be true when data.operator_id is not null
    if allocator_get(db_session, allocator_id) is None:
        raise NotFoundException(f'Allocator ID {allocator_id} does not exist')

    _other = get_by_FQNN(db_session, allocator_id, data.node_number)
    if _other is not None:
        raise ClientException(
            f'FQNN ({allocator_id}, {data.node_number}) is already used by node'
            f' ID {_other.node_id}'
        )

    try:
        node_copy = copy(
            db_session,
            node_id,
            allocator_id,
            data.node_number,
            data.host_id,
            data.operator_id,
            destination_ref_mode,
        )
    except Exception:
        raise InternalServerException

    return Response(
        content=to_node_schema(node_copy),
        headers={
            'Location': f'{API_V1_PATH}/nodes/{node_copy.node_id}',
            'Content-Location': f'{API_V1_PATH}/nodes/{node_copy.node_id}',
        },
    )


@_delete(
    path='/{node_id:int}',
    sync_to_thread=True,
    tags=['nodes'],
    summary='Delete node',
    description='Deletes the node identified by `node_id`.',
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for DELETE {API_V1_PATH}/nodes/{NodeIDMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {NodeIDMeta.le}',
            validation_key_example='node_id',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description='Node ID in path parameter is not associated with a resource',
            detail_example='Node ID 429204 does not exist',
        ),
    },
)
def delete_node(db_session: Session, node_id: Annotated[int, NodeIDParam]) -> None:
    if get(db_session, node_id) is None:
        raise NotFoundException(f'Node ID {node_id} does not exist')
    try:
        delete(db_session, node_id)
    except Exception:
        raise InternalServerException


@_get(
    path='/{node_id:int}/endpoints/ipn',
    sync_to_thread=True,
    tags=['nodes', 'endpoints'],
    summary='List node ipn endpoints',
    description=(
        "Lists endpoints using the 'ipn' URI scheme associated with the node"
        ' identified by `node_id`.<br />'
        '<br />'
        f'{GENERIC_QUERY_PARAM_USAGE_NOTE}'
    ),
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={
        400: pagination_400_response_spec(f'{API_V1_PATH}/nodes/8/endpoints/ipn'),
        404: create_404_response_spec(
            description='Node ID in path parameter is not associated with a resource',
            detail_example='Node ID 429204 does not exist',
        ),
    },
)
def list_node_endpoints_ipn(
    db_session: Session,
    node_id: Annotated[int, NodeIDParam],
    paginated_request: PaginatedRequest,
) -> QueryResponse[EndpointIPNSchema]:
    if get(db_session, node_id) is None:
        raise NotFoundException(f'Node ID {node_id} does not exist')
    path = f'/nodes/{node_id}/endpoints/ipn'
    try:
        bookmark = process_page_token(paginated_request, path)
    except Exception:
        raise
    page = list_ipn(
        db_session,
        node_id,
        process_page_size(paginated_request.max_page_size),
        bookmark,
    )
    return QueryResponse(
        [to_endpoint_ipn_schema(_) for (_,) in page],
        *create_page_tokens(paginated_request, path, page),
    )


@_get(
    path='/{node_id:int}/endpoints/imc',
    sync_to_thread=True,
    tags=['nodes', 'endpoints'],
    summary='List node imc endpoints',
    description=(
        "Lists endpoints using the 'imc' URI scheme (described in I-D.burleigh"
        '-dtnrg-imc-00) associated with the node identified by `node_id`.<br />'
        '<br />'
        f'{GENERIC_QUERY_PARAM_USAGE_NOTE}'
    ),
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={
        400: pagination_400_response_spec(f'{API_V1_PATH}/nodes/8/endpoints/imc'),
        404: create_404_response_spec(
            description='Node ID in path parameter is not associated with a resource',
            detail_example='Node ID 429204 does not exist',
        ),
    },
)
def list_node_endpoints_imc(
    db_session: Session,
    node_id: Annotated[int, NodeIDParam],
    paginated_request: PaginatedRequest,
) -> QueryResponse[EndpointIMCSchema]:
    if get(db_session, node_id) is None:
        raise NotFoundException(f'Node ID {node_id} does not exist')
    path = f'/nodes/{node_id}/endpoints/imc'
    try:
        bookmark = process_page_token(paginated_request, path)
    except Exception:
        raise
    page = list_imc(
        db_session,
        node_id,
        process_page_size(paginated_request.max_page_size),
        bookmark,
    )
    return QueryResponse(
        [to_endpoint_imc_schema(_) for (_,) in page],
        *create_page_tokens(paginated_request, path, page),
    )


def _handle_validation_exception(
    request: Request, exc: ValidationException
) -> Response:
    """Since the replace endpoints route handlers are performing
    validation rather than Litestar, we need to mimic how
    litestar._signature.model.SignatureModel._create_exception() formats
    messages.
    """
    path = str(request.url).removeprefix(str(request.base_url))
    detail = f'Validation failed for {request.method} /{path}'
    return Response(
        status_code=exc.status_code,
        content=ProblemDetailsExceptionSchema(
            status=exc.status_code,
            title='Validation Error',
            detail=detail,
            extra=exc.extra,
        ),
    )


@put(
    path='/{node_id:int}/endpoints/ipn',
    status_code=HTTP_204_NO_CONTENT,
    exception_handlers={ValidationException: _handle_validation_exception},
    guards=[required_request_body_guard],
    sync_to_thread=True,
    tags=['nodes', 'endpoints'],
    summary='Replace ipn endpoints',
    description=(
        'Provide an array of ipn endpoint representations in the request body to'
        ' *replace* the ipn endpoints associated with the node identified by'
        ' `node_id`.'
    ),
    operation_class=custom_operation(
        custom_reqbody(
            description=(
                'An empty array (`[]`) will clear the ipn endpoints associated'
                ' with the node.<br />'
                '<br />'
                'A service number can be specified with either the `uri` property'
                ' or the `service_number` property. `uri` and `service_number`'
                ' cannot both be `null` in the same object. If both `uri` and'
                ' `service_number` are not `null`, then their value for Service'
                ' Number cannot conflict.<br />'
                '<br />'
                'A `uri` cannot have a different Fully Qualified Node Number from'
                ' the node identified by `node_id`.<br />'
                '<br />'
                'Multiple objects in the request body with the same Service Number'
                ' value will fail.'
            ),
            required=True,
        )
    ),
    response_description=HTTPStatus(HTTP_204_NO_CONTENT).description,
    responses={
        400: create_400_response_spec(
            description=(
                'Bad request syntax, validation error, FQNN of a `uri` does'
                ' not match that of the node, or multiple objects in the'
                ' request body have the same Service Number value'
            ),
            client_error_detail_example=(
                'Fully Qualified Node Number of ipn:974994.15532.61152 does not'
                ' match that of node ID 8 (974994, 15498)'
            ),
            client_error_extra=[
                ProblemDetailsExtraSchema(
                    message='ipn:974994.15532.61152 cannot be associated with the node',
                    key='[0].uri',
                    source='body',
                )
            ],
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for PUT {API_V1_PATH}/nodes/8/endpoints/ipn'
            ),
            validation_message_example=(
                "'imc:11.0' does not comply with the text syntax of an ipn URI"
            ),
            validation_key_example='[0].uri',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description='Node ID in path parameter is not associated with a resource',
            detail_example='Node ID 429204 does not exist',
        ),
    },
)
def replace_endpoints_ipn(
    db_session: Session,
    node_id: Annotated[int, NodeIDParam],
    data: Annotated[list[EndpointIPNReplaceSchema], EndpointIPNReplaceBody],
) -> None:
    # Map service numbers to a list of array indices and whether a uri is present
    seen_service_numbers: dict[int, list[tuple[int, bool]]] = dict()
    at_least_one_service_nbr_seen_more_than_once = False
    # Map FQNN to uri and array index
    seen_fqnn: dict[tuple[int, int], tuple[str, int]] = dict()

    for endpoint, i in zip(data, range(len(data))):
        endpoint.validate(i)
        if endpoint.service_number in seen_service_numbers:
            seen_service_numbers[endpoint.service_number].append(
                (i, bool(endpoint.uri))
            )
            at_least_one_service_nbr_seen_more_than_once = True
        else:
            seen_service_numbers[endpoint.service_number] = [(i, bool(endpoint.uri))]
        # Keep track of the first uri and index for a FQNN
        if endpoint.uri is not None:
            (allocator_id, node_number, _) = parse_ipn_uri(endpoint.uri)
            if (allocator_id, node_number) not in seen_fqnn:
                seen_fqnn[(allocator_id, node_number)] = (endpoint.uri, i)

    # Returning multiple indices at once is nicer for the UI, though the UI
    # should be able to verify before making a PUT request.
    if at_least_one_service_nbr_seen_more_than_once:
        # This could be a ValidationException, but I'd rather just have the docs
        # say you can't repeat service numbers than try to make an OpenAPI schema
        # that says that.
        raise ClientException(
            detail='Service numbers are repeated across objects in the request body',
            extra={
                'extra': [
                    ProblemDetailsExtraSchema(
                        message=f'Service number {s_n} appears in multiple objects',
                        key=f'[{i}].{"uri" if uri else "service_number"}',
                        source=ExtraSourceEnum.BODY.value,
                    )
                    for i, uri in arr
                ]
                for s_n, arr in seen_service_numbers.items()
            },
        )

    node = get(db_session, node_id)
    if node is None:
        raise NotFoundException(f'Node ID {node_id} does not exist')

    for (allocator_id, node_number), (uri, index) in seen_fqnn.items():
        if allocator_id != node.allocator_id or node_number != node.node_number:
            raise ClientException(
                f'Fully Qualified Node Number of {uri} does not match that of node'
                f' ID {node_id} ({node.allocator_id}, {node.node_number})',
                extra={
                    'extra': [
                        ProblemDetailsExtraSchema(
                            message=f'{uri} cannot be associated with the node',
                            key=f'[{index}].uri',
                            source=ExtraSourceEnum.BODY.value,
                        )
                    ]
                },
            )

    try:
        replace_ipn(db_session, node_id, data)
    except Exception:
        raise InternalServerException


@post(
    path='/{node_id:int}/endpoints/ipn',
    exception_handlers={ValidationException: _handle_validation_exception},
    guards=[required_request_body_guard],
    sync_to_thread=True,
    tags=['nodes', 'endpoints'],
    summary='Create an ipn endpoint',
    description=(
        'Create an ipn endpoint that is associated with the node identified by'
        ' `node_id`.\n'
        '\n'
        'The EID cannot conflict with an existing endpoint.'
        ' Use the `GET /nodes/{node_id}/endpoints/ipn` API to see what EIDs are'
        ' already used.'
    ),
    operation_class=custom_operation(
        custom_reqbody(
            description=(
                'A service number can be specified with either the `uri` property'
                ' or the `service_number` property. `uri` and `service_number`'
                ' cannot both be `null` in the same object. If both `uri` and'
                ' `service_number` are not `null`, then their value for Service'
                ' Number cannot conflict.\n'
                '\n'
                'A `uri` cannot have a different Fully Qualified Node Number from'
                ' the node identified by `node_id`.\n'
            ),
            required=True,
        )
    ),
    response_headers=[LocationHeader],
    response_description='ipn endpoint created, representation follows',
    responses={
        400: create_400_response_spec(
            description=(
                'Bad request syntax, validation error, FQNN of a `uri` does'
                ' not match that of the node, or another endpoint with the'
                ' given EID already exists'
            ),
            client_error_detail_example=(
                'An endpoint with the URI ipn:974994.15498.61152 already exists'
            ),
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for POST {API_V1_PATH}/nodes/8/endpoints/ipn'
            ),
            validation_message_example=(
                "'imc:11.0' does not comply with the text syntax of an ipn URI"
            ),
            validation_key_example='uri',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description='Node ID in path parameter is not associated with a resource',
            detail_example='Node ID 429204 does not exist',
        ),
    },
)
def create_endpoint_ipn(
    db_session: Session,
    node_id: Annotated[int, NodeIDParam],
    data: Annotated[EndpointIPNReplaceSchema, EndpointIPNCreateBody],
) -> Response[EndpointIPNSchema]:
    data.validate()
    node = get(db_session, node_id)
    if node is None:
        raise NotFoundException(f'Node ID {node_id} does not exist')

    if data.uri is not None:
        allocator_id, node_number, _ = parse_ipn_uri(data.uri)
        if allocator_id != node.allocator_id or node_number != node.node_number:
            raise ClientException(
                f'Fully Qualified Node Number of {data.uri} does not match that'
                f' of node ID {node_id}'
                f' ({node.allocator_id}, {node.node_number})',
                extra={
                    'extra': [
                        ProblemDetailsExtraSchema(
                            message=f'{data.uri} cannot be associated with the node',
                            key=f'uri',
                            source=ExtraSourceEnum.BODY.value,
                        )
                    ]
                },
            )

    if get_ipn(db_session, node_id, data.service_number) is not None:
        raise ClientException(
            'An endpoint with the URI'
            f' {to_ipn_uri(node.allocator_id, node.node_number, data.service_number)}'
            ' already exists'
        )

    try:
        endpoint = create_ipn(
            db_session, node_id, data.service_number, data.disposition, data.application
        )
    except Exception:
        raise InternalServerException
    return Response(
        content=to_endpoint_ipn_schema(endpoint),
        headers={
            'Location': (
                f'{API_V1_PATH}/nodes/{node_id}/endpoints/ipn/{data.service_number}'
            ),
        },
    )


@patch(
    path='/{node_id:int}/endpoints/ipn/{service_number:int}',
    exception_handlers={ValidationException: _handle_validation_exception},
    sync_to_thread=True,
    tags=['nodes', 'endpoints'],
    summary='Update an ipn endpoint',
    description=(
        'Update the ipn endpoint associated with the node identified by `node_id`'
        ' with the service number `service_number`.\n'
        '\n'
        'If you are changing the EID, the new value'
        ' cannot conflict with an existing endpoint.'
        ' Use the `GET /nodes/{node_id}/endpoints/ipn` API to see what EIDs are'
        ' already used.'
    ),
    operation_class=custom_operation(
        custom_reqbody(
            description=(
                'If a value is ommitted from the request body,'
                ' then it will not be changed.\n'
                '\n'
                'A service number can be updated with either the `uri` property'
                ' or the `service_number` property. If both `uri` and'
                ' `service_number` are present, then their value for'
                ' Service Number cannot conflict.\n'
                '\n'
                'A `uri` cannot have a different Fully Qualified Node Number from'
                ' the node identified by `node_id`.\n'
            ),
            required=False,
        )
    ),
    response_headers=[ContentLocationHeader],
    response_description='ipn endpoint updated, representation follows',
    responses={
        400: create_400_response_spec(
            description=(
                'Bad request syntax, validation error, FQNN of a `uri` does'
                ' not match that of the node, or another endpoint with the'
                ' given EID already exists'
            ),
            client_error_detail_example=(
                'An endpoint with the URI ipn:974994.15498.61152 already exists'
            ),
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for PATCH {API_V1_PATH}/nodes/8/endpoints/ipn/61152'
            ),
            validation_message_example=(
                "'imc:11.0' does not comply with the text syntax of an ipn URI"
            ),
            validation_key_example='uri',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description='Node ID or EID in path is not associated with a resource',
            detail_example='EID ipn:974994.15498.61167 does not exist',
        ),
    },
)
def update_endpoint_ipn(
    db_session: Session,
    node_id: Annotated[int, NodeIDParam],
    service_number: Annotated[int, ServiceNumberParam],
    data: Annotated[EndpointIPNUpdateSchema, EndpointIPNUpdateBody] = None,
) -> Response[EndpointIPNSchema]:
    if data is None:
        data = EndpointIPNUpdateSchema()
    data.validate()
    node = get(db_session, node_id)
    if node is None:
        raise NotFoundException(f'Node ID {node_id} does not exist')
    endpoint = get_ipn(db_session, node_id, service_number)
    if endpoint is None:
        raise NotFoundException(
            f'EID {to_ipn_uri(node.allocator_id, node.node_number, service_number)}'
            ' does not exist'
        )

    if data.uri is not UNSET:
        allocator_id, node_number, _ = parse_ipn_uri(data.uri)
        if allocator_id != node.allocator_id or node_number != node.node_number:
            raise ClientException(
                f'Fully Qualified Node Number of {data.uri} does not match that'
                f' of node ID {node_id}'
                f' ({node.allocator_id}, {node.node_number})',
                extra={
                    'extra': [
                        ProblemDetailsExtraSchema(
                            message=f'{data.uri} cannot be associated with the node',
                            key='uri',
                            source=ExtraSourceEnum.BODY.value,
                        )
                    ]
                },
            )

    if (
        data.service_number is not UNSET
        and data.service_number != endpoint.service_number
        and get_ipn(db_session, node_id, data.service_number)
    ):
        raise ClientException(
            'An endpoint with the URI'
            f' {to_ipn_uri(node.allocator_id, node.node_number, data.service_number)}'
            ' already exists'
        )

    try:
        endpoint = update_ipn(
            db_session,
            node_id,
            service_number,
            endpoint.disposition if data.disposition is UNSET else data.disposition,
            endpoint.application if data.application is UNSET else data.application,
            None if data.service_number is UNSET else data.service_number,
        )
    except Exception:
        raise InternalServerException
    return Response(
        content=to_endpoint_ipn_schema(endpoint),
        headers={
            'Content-Location': (
                f'{API_V1_PATH}/nodes/{node_id}/endpoints/ipn/{endpoint.service_number}'
            ),
        },
    )


@_delete(
    path='/{node_id:int}/endpoints/ipn/{service_number:int}',
    sync_to_thread=True,
    tags=['nodes', 'endpoints'],
    summary='Delete ipn endpoint',
    description=(
        'Deletes the ipn endpoint identified by `node_id` and `service_number`.'
    ),
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                'Validation failed for DELETE'
                f' {API_V1_PATH}/nodes/8/endpoints/ipn/{ServiceNumberMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {ServiceNumberMeta.le}',
            validation_key_example='service_number',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description='Node ID or EID in path is not associated with a resource',
            detail_example='EID ipn:974994.15498.61167 does not exist',
        ),
    },
)
def delete_endpoint_ipn(
    db_session: Session,
    node_id: Annotated[int, NodeIDParam],
    service_number: Annotated[int, ServiceNumberParam],
) -> None:
    node = get(db_session, node_id)
    if node is None:
        raise NotFoundException(f'Node ID {node_id} does not exist')
    endpoint = get_ipn(db_session, node_id, service_number)
    if endpoint is None:
        raise NotFoundException(
            f'EID {to_ipn_uri(node.allocator_id, node.node_number, service_number)}'
            ' does not exist'
        )
    try:
        delete_ipn(db_session, node_id, service_number)
    except Exception:
        raise InternalServerException


@put(
    path='/{node_id:int}/endpoints/imc',
    status_code=HTTP_204_NO_CONTENT,
    exception_handlers={ValidationException: _handle_validation_exception},
    guards=[required_request_body_guard],
    sync_to_thread=True,
    tags=['nodes', 'endpoints'],
    summary='Replace imc endpoints',
    description=(
        'Provide an array of imc endpoint representations in the request body to'
        ' *replace* the imc endpoints associated with the node identified by'
        ' `node_id`.'
    ),
    operation_class=custom_operation(
        custom_reqbody(
            description=(
                'An empty array (`[]`) will clear the imc endpoints associated'
                ' with the node.<br />'
                '<br />'
                'A group number can be specified with either the `uri` property'
                ' or the `group_number` property. `uri` and `group_number`'
                ' cannot both be `null` in the same object. If both `uri` and'
                ' `group_number` are not `null`, then their value for Group'
                ' Number cannot conflict.<br />'
                '<br />'
                'Multiple objects in the request body with the same Group Number'
                ' value will fail.'
            ),
            required=True,
        )
    ),
    response_description=HTTPStatus(HTTP_204_NO_CONTENT).description,
    responses={
        400: create_400_response_spec(
            description=(
                'Bad request syntax, validation error, or multiple objects in'
                ' the request body have the same Group Number value'
            ),
            client_error_detail_example=(
                'Group numbers are repeated across objects in the request body'
            ),
            client_error_extra=[
                ProblemDetailsExtraSchema(
                    message='Group number 11 appears in multiple objects',
                    key='[0].uri',
                    source='body',
                ),
                ProblemDetailsExtraSchema(
                    message='Group number 11 appears in multiple objects',
                    key='[1].group_number',
                    source='body',
                ),
            ],
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for PUT {API_V1_PATH}/nodes/8/endpoints/imc'
            ),
            validation_message_example=(
                "'ipn:1.2' does not comply with the text syntax of an imc URI"
            ),
            validation_key_example='[0].uri',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description='Node ID in path parameter is not associated with a resource',
            detail_example='Node ID 429204 does not exist',
        ),
    },
)
def replace_endpoints_imc(
    db_session: Session,
    node_id: Annotated[int, NodeIDParam],
    data: Annotated[list[EndpointIMCReplaceSchema], EndpointIMCReplaceBody],
) -> None:
    # Map group numbers to a list of array indices and whether a uri is present
    seen_group_numbers: dict[int, list[tuple[int, bool]]] = dict()
    at_least_one_group_nbr_seen_more_than_once = False

    for endpoint, i in zip(data, range(len(data))):
        endpoint.validate(i)
        if endpoint.group_number in seen_group_numbers:
            seen_group_numbers[endpoint.group_number].append((i, bool(endpoint.uri)))
            at_least_one_group_nbr_seen_more_than_once = True
        else:
            seen_group_numbers[endpoint.group_number] = [(i, bool(endpoint.uri))]

    # Returning multiple indices at once is nicer for the UI, though the UI
    # should be able to verify before making a PUT request.
    if at_least_one_group_nbr_seen_more_than_once:
        # This could be a ValidationException, but I'd rather just have the docs
        # say you can't repeat group numbers than try to make an OpenAPI schema
        # that says that.
        raise ClientException(
            detail='Group numbers are repeated across objects in the request body',
            extra={
                'extra': [
                    ProblemDetailsExtraSchema(
                        message=f'Group number {g_n} appears in multiple objects',
                        key=f'[{i}].{"uri" if uri else "group_number"}',
                        source=ExtraSourceEnum.BODY.value,
                    )
                    for i, uri in arr
                ]
                for g_n, arr in seen_group_numbers.items()
            },
        )

    node = get(db_session, node_id)
    if node is None:
        raise NotFoundException(f'Node ID {node_id} does not exist')

    try:
        replace_imc(db_session, node_id, data)
    except Exception:
        raise InternalServerException


@post(
    path='/{node_id:int}/endpoints/imc',
    exception_handlers={ValidationException: _handle_validation_exception},
    guards=[required_request_body_guard],
    sync_to_thread=True,
    tags=['nodes', 'endpoints'],
    summary='Create an imc endpoint',
    description=(
        'Create an imc endpoint that is associated with the node identified by'
        ' `node_id`.\n'
        '\n'
        'The operation fails if the node is already associated with the'
        ' requested imc group.'
        ' Use the `GET /nodes/{node_id}/endpoints/imc` API to see what groups'
        ' the node is already in.'
    ),
    operation_class=custom_operation(
        custom_reqbody(
            description=(
                'A group number can be specified with either the `uri` property'
                ' or the `group_number` property. `uri` and `group_number`'
                ' cannot both be `null` in the same object. If both `uri` and'
                ' `group_number` are not `null`, then their value for Group'
                ' Number cannot conflict.'
            ),
            required=True,
        )
    ),
    response_headers=[LocationHeader],
    response_description='imc endpoint created, representation follows',
    responses={
        400: create_400_response_spec(
            description=(
                'Bad request syntax, validation error, or node is already in'
                ' the requested imc group'
            ),
            client_error_detail_example=(
                'Node ID 8 is already associated with multicast EID imc:11.0'
            ),
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for POST {API_V1_PATH}/nodes/8/endpoints/imc'
            ),
            validation_message_example=(
                "'ipn:1.2' does not comply with the text syntax of an imc URI"
            ),
            validation_key_example='uri',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description='Node ID in path parameter is not associated with a resource',
            detail_example='Node ID 429204 does not exist',
        ),
    },
)
def create_endpoint_imc(
    db_session: Session,
    node_id: Annotated[int, NodeIDParam],
    data: Annotated[EndpointIMCReplaceSchema, EndpointIMCCreateBody],
) -> Response[EndpointIMCSchema]:
    data.validate()
    node = get(db_session, node_id)
    if node is None:
        raise NotFoundException(f'Node ID {node_id} does not exist')

    if get_imc(db_session, node_id, data.group_number) is not None:
        raise ClientException(
            f'Node ID {node_id} is already associated with multicast'
            f' EID {to_imc_uri(data.group_number)}'
        )

    try:
        endpoint = create_imc(
            db_session, node_id, data.group_number, data.disposition, data.application
        )
    except Exception:
        raise InternalServerException
    return Response(
        content=to_endpoint_imc_schema(endpoint),
        headers={
            'Location': (
                f'{API_V1_PATH}/nodes/{node_id}/endpoints/imc/{data.group_number}'
            ),
        },
    )


@patch(
    path='/{node_id:int}/endpoints/imc/{group_number:int}',
    exception_handlers={ValidationException: _handle_validation_exception},
    sync_to_thread=True,
    tags=['nodes', 'endpoints'],
    summary='Update an imc endpoint',
    description=(
        'Update the imc endpoint associated with the node identified by `node_id`'
        ' with the group number `group_number`.\n'
        '\n'
        'If you are changing the EID, the new value'
        ' cannot conflict with an existing endpoint.'
        ' Use the `GET /nodes/{node_id}/endpoints/imc` API to see what EIDs are'
        ' already used.'
    ),
    operation_class=custom_operation(
        custom_reqbody(
            description=(
                'If a value is ommitted from the request body,'
                ' then it will not be changed.\n'
                '\n'
                'A group number can be updated with either the `uri` property'
                ' or the `group_number` property. If both `uri` and'
                ' `group_number` are present, then their value for'
                ' Group Number cannot conflict.'
            ),
            required=False,
        )
    ),
    response_headers=[ContentLocationHeader],
    response_description='imc endpoint updated, representation follows',
    responses={
        400: create_400_response_spec(
            description=(
                'Bad request syntax, validation error, or another endpoint with'
                ' the given EID already exists'
            ),
            client_error_detail_example=(
                'An endpoint with the URI imc:11.0 already exists'
            ),
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for PATCH {API_V1_PATH}/nodes/8/endpoints/imc/11'
            ),
            validation_message_example=(
                "'ipn:1.2' does not comply with the text syntax of an imc URI"
            ),
            validation_key_example='uri',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description='Node ID or EID in path is not associated with a resource',
            detail_example='EID imc:12.0 does not exist',
        ),
    },
)
def update_endpoint_imc(
    db_session: Session,
    node_id: Annotated[int, NodeIDParam],
    group_number: Annotated[int, GroupNumberParam],
    data: Annotated[EndpointIMCUpdateSchema, EndpointIMCUpdateBody] = None,
) -> Response[EndpointIMCSchema]:
    if data is None:
        data = EndpointIMCUpdateSchema()
    data.validate()
    node = get(db_session, node_id)
    if node is None:
        raise NotFoundException(f'Node ID {node_id} does not exist')
    endpoint = get_imc(db_session, node_id, group_number)
    if endpoint is None:
        raise NotFoundException(
            f'Node ID {node_id} is not associated with multicast EID'
            f' {to_imc_uri(group_number)}'
        )

    if (
        data.group_number is not UNSET
        and data.group_number != endpoint.group_number
        and get_imc(db_session, node_id, data.group_number)
    ):
        raise ClientException(
            f'Node ID {node_id} is already associated with multicast'
            f' EID {to_imc_uri(data.group_number)}'
        )

    try:
        endpoint = update_imc(
            db_session,
            node_id,
            group_number,
            endpoint.disposition if data.disposition is UNSET else data.disposition,
            endpoint.application if data.application is UNSET else data.application,
            None if data.group_number is UNSET else data.group_number,
        )
    except Exception:
        raise InternalServerException
    return Response(
        content=to_endpoint_imc_schema(endpoint),
        headers={
            'Content-Location': (
                f'{API_V1_PATH}/nodes/{node_id}/endpoints/imc/{endpoint.group_number}'
            ),
        },
    )


@_delete(
    path='/{node_id:int}/endpoints/imc/{group_number:int}',
    sync_to_thread=True,
    tags=['nodes', 'endpoints'],
    summary='Delete imc endpoint',
    description=(
        'Deletes the imc endpoint identified by `node_id` and `group_number`.'
    ),
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                'Validation failed for DELETE'
                f' {API_V1_PATH}/nodes/8/endpoints/imc/{GroupNumberMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {GroupNumberMeta.le}',
            validation_key_example='group_number',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description='Node ID or EID in path is not associated with a resource',
            detail_example='EID imc:12.0 does not exist',
        ),
    },
)
def delete_endpoint_imc(
    db_session: Session,
    node_id: Annotated[int, NodeIDParam],
    group_number: Annotated[int, GroupNumberParam],
) -> None:
    node = get(db_session, node_id)
    if node is None:
        raise NotFoundException(f'Node ID {node_id} does not exist')
    endpoint = get_imc(db_session, node_id, group_number)
    if endpoint is None:
        raise NotFoundException(
            f'Node ID {node_id} is not associated with multicast EID'
            f' {to_imc_uri(group_number)}'
        )
    try:
        delete_imc(db_session, node_id, group_number)
    except Exception:
        raise InternalServerException


@_get(
    path='/{node_id:int}/cl-protocols',
    sync_to_thread=True,
    tags=['nodes', 'cl protocols'],
    summary='List node CL protocols',
    description=(
        'Lists CL protocols associated with the node identified by `node_id`.<br />'
        '<br />'
        f'{GENERIC_QUERY_PARAM_USAGE_NOTE}'
    ),
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={
        400: pagination_400_response_spec(f'{API_V1_PATH}/nodes/8/cl-protocols'),
        404: create_404_response_spec(
            description='Node ID in path parameter is not associated with a resource',
            detail_example='Node ID 429204 does not exist',
        ),
    },
)
def list_node_cl_protocols(
    db_session: Session,
    node_id: Annotated[int, NodeIDParam],
    paginated_request: PaginatedRequest,
) -> QueryResponse[ClProtocolWithoutNodeIdSchema]:
    if get(db_session, node_id) is None:
        raise NotFoundException(f'Node ID {node_id} does not exist')
    path = f'/nodes/{node_id}/cl-protocols'
    try:
        bookmark = process_page_token(paginated_request, path)
    except Exception:
        raise
    page = list_cl_protocols(
        db_session,
        node_id,
        process_page_size(paginated_request.max_page_size),
        bookmark,
    )
    return QueryResponse(
        [to_cl_protocol_without_node_id_schema(_) for (_,) in page],
        *create_page_tokens(paginated_request, path, page),
    )


@post(
    path='/{node_id:int}/cl-protocols',
    guards=[required_request_body_guard],
    sync_to_thread=True,
    tags=['nodes', 'cl protocols'],
    summary='Create CL protocol connected to node',
    description=(
        'Creates a new CL protocol for the node identified by `node_id`.<br />'
        '<br />'
        'CL protocols on a given node cannot have duplicate names in terms of'
        ' bytes. Use the `GET /nodes/{node_id}/cl-protocols` API to see what names'
        ' are already used.'
    ),
    operation_class=custom_operation(
        custom_reqbody(
            description=(
                '`cl_protocol_name` must have a byte length in the inclusive range'
                ' 1 to 15.<br/>'
                '<br />'
                'Do not specify `cl_protocol_class` in the request body to use a'
                ' default value for that field.'
                f' {CL_PROTOCOL_CLASS_DEFAULT_VALUES_DESC}'
                '<p>Note that using a different `cl_protocol_class` for one of the'
                ' `cl_protocol_name` values explicitly listed here and using a value'
                f' besides `["{ClProtocolClassEnum.BP_BEST_EFFORT.value}"]` when'
                ' `cl_protocol_name` is `"udp"` will fail.</p>'
            ),
            required=True,
        )
    ),
    response_headers=[LocationHeader, ContentLocationHeader],
    response_description='CL protocol created, representation follows',
    responses={
        400: create_400_response_spec(
            description=(
                'Bad request syntax, validation error, CL protocol name is already'
                ' used by an existing resource on the same node, or invalid class'
                ' for a well known protocol'
            ),
            client_error_detail_example=(
                "CL protocol name 'udp' must use protocol class ['BP_RELIABLE']"
            ),
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for POST {API_V1_PATH}/nodes/8/cl-protocols'
            ),
            validation_message_example=(
                'Length in bytes must be in the inclusive range [1, 15]'
            ),
            validation_key_example='cl_protocol_name',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description='Node ID in path parameter is not associated with a resource',
            detail_example='Node ID 429204 does not exist',
        ),
    },
)
def create_cl_protocol(
    db_session: Session,
    node_id: Annotated[int, NodeIDParam],
    data: ClProtocolCreateSchema,
) -> Response[ClProtocolSchema]:
    if get(db_session, node_id) is None:
        raise NotFoundException(f'Node ID {node_id} does not exist')

    if (
        cl_protocol_get_by_details(db_session, node_id, data.cl_protocol_name)
        is not None
    ):
        raise ClientException(
            f"A CL protocol with the name '{data.cl_protocol_name}' is already"
            f' associated with node ID {node_id}'
        )

    class_val = protocol_class_arr_to_int(data.cl_protocol_class)
    _check_val = get_cl_protocol_check_value(data.cl_protocol_name)
    if _check_val is not None and class_val != _check_val:
        raise ClientException(
            f"CL protocol name '{data.cl_protocol_name}' must use protocol class"
            f' {protocol_class_int_to_arr(_check_val)}'
        )

    try:
        cl_protocol = cl_protocol_create(
            db_session, node_id, data.cl_protocol_name, class_val
        )
    except Exception:
        raise InternalServerException

    return Response(
        content=to_cl_protocol_schema(cl_protocol),
        headers={
            'Location': f'{API_V1_PATH}/cl-protocols/{cl_protocol.cl_protocol_id}',
            'Content-Location': (
                f'{API_V1_PATH}/cl-protocols/{cl_protocol.cl_protocol_id}'
            ),
        },
    )


@_get(
    path='/{node_id:int}/inducts',
    sync_to_thread=True,
    tags=['nodes', 'inducts'],
    summary='List node inducts',
    description=(
        'Lists inducts associated with the node identified by `node_id`.<br />'
        '<br />'
        f'{GENERIC_QUERY_PARAM_USAGE_NOTE}'
    ),
    responses={
        200: ResponseSpec(
            data_container=QueryResponse[InductWithoutNodeIdSchema],
            description=GENERIC_RESPONSE_DESCRIPTION,
            examples=[
                Example(
                    summary='Inducts',
                    value=QueryResponse(
                        items=[i.value for i in induct_examples],
                        prev_page_token=PrevPageTokenMeta.examples[0],
                        next_page_token=NextPageTokenMeta.examples[0],
                    ),
                )
            ],
        ),
        400: pagination_400_response_spec(f'{API_V1_PATH}/nodes/8/inducts'),
        404: create_404_response_spec(
            description='Node ID in path parameter is not associated with a resource',
            detail_example='Node ID 429204 does not exist',
        ),
    },
)
def list_node_inducts(
    db_session: Session,
    node_id: Annotated[int, NodeIDParam],
    paginated_request: PaginatedRequest,
) -> QueryResponse[InductWithoutNodeIdSchema]:
    if get(db_session, node_id) is None:
        raise NotFoundException(f'Node ID {node_id} does not exist')
    path = f'/nodes/{node_id}/inducts'
    try:
        bookmark = process_page_token(paginated_request, path)
    except Exception:
        raise
    page = list_inducts(
        db_session,
        node_id,
        process_page_size(paginated_request.max_page_size),
        bookmark,
    )
    return QueryResponse(
        [to_induct_without_node_id_schema(_) for (_,) in page],
        *create_page_tokens(paginated_request, path, page),
    )


@post(
    path='/{node_id:int}/inducts',
    sync_to_thread=True,
    tags=['nodes', 'inducts'],
    summary='Create induct connected to node',
    description=(
        'Creates a new induct under the node identified by `node_id`.'
        'The induct can be associated with links after the induct has been'
        ' created with the `/inducts/{induct_id}/links` API.<br />'
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
        custom_reqbody(description=INDUCT_WRITE_DESCRIPTION, required=False)
    ),
    response_headers=[LocationHeader, ContentLocationHeader],
    responses={
        201: ResponseSpec(
            data_container=InductSchema,
            description='Induct created, representation follows',
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
                ' to a CL protocol that is not owned by the node, or'
                ' `destination_id` cannot be referenced by the node.'
            ),
            client_error_detail_example=(
                '`duct_name` must be null when `cli_command` is in'
                f' {no_duct_name_known_cli_not_ip}'
            ),
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for POST {API_V1_PATH}/nodes/8/inducts'
            ),
            validation_message_example="Invalid value 'IP'",
            validation_key_example='duct_name.type',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description=(
                '`node_id` in the path is not associated with a node,'
                ' `cl_protocol_id` is not associated with a CL protocol, or'
                ' `destination_id` is not associated with a destination.'
            ),
            detail_example='Node ID 429204 does not exist',
        ),
    },
)
def create_induct(
    db_session: Session,
    node_id: Annotated[int, NodeIDParam],
    data: Annotated[InductCreateSchema, InductCreateBody] = None,
) -> Response[InductSchema]:
    if data is None:
        data = InductCreateSchema()
    node = get(db_session, node_id)
    if node is None:
        raise NotFoundException(f'Node ID {node_id} does not exist')

    if data.cl_protocol_id is not None:
        cl_protocol = cl_protocol_get(db_session, data.cl_protocol_id)
        if cl_protocol is None:
            raise NotFoundException(
                f'CL protocol ID {data.cl_protocol_id} does not exist'
            )
        if cl_protocol.node_id != node_id:
            raise ClientException(
                f'CL protocol ID {data.cl_protocol_id} does not belong to node ID'
                f' {node_id}'
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
        if destination.host_id != node.host_id:
            if node.host_id is None:
                raise ClientException(
                    'A destination cannot be associated with an induct when'
                    ' the node is not on a host.'
                )
            raise ClientException(
                f'Destination ID {data.duct_name.destination_id} belongs to a'
                f' different host than host ID {node.host_id}, which node ID'
                f' {node_id} belongs to'
            )

    try:
        induct = induct_create(
            db_session,
            node_id,
            'ip' if is_ip_duct else None,
            data.cl_protocol_id,
            data.duct_name if isinstance(data.duct_name, str) else None,
            data.cli_command,
            data.uses_ltp,
        )
        if is_ip_duct:
            induct = induct_create_ip(
                db_session,
                induct.induct_id,
                data.duct_name.destination_id,
                data.duct_name.port_number,
            )
        db_session.commit()
    except Exception:
        raise InternalServerException

    return Response(
        content=to_induct_schema(induct),
        headers={
            'Location': f'{API_V1_PATH}/inducts/{induct.induct_id}',
            'Content-Location': f'{API_V1_PATH}/inducts/{induct.induct_id}',
        },
    )


@_get(
    path='/{node_id:int}/seats',
    sync_to_thread=True,
    tags=['nodes', 'seats'],
    summary='List node seats',
    description=(
        'Lists seats associated with the node identified by `node_id`.<br />'
        '<br />'
        f'{GENERIC_QUERY_PARAM_USAGE_NOTE}'
    ),
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={
        400: pagination_400_response_spec(f'{API_V1_PATH}/nodes/8/seats'),
        404: create_404_response_spec(
            description='Node ID in path parameter is not associated with a resource',
            detail_example='Node ID 429204 does not exist',
        ),
    },
)
def list_node_seats(
    db_session: Session,
    node_id: Annotated[int, NodeIDParam],
    paginated_request: PaginatedRequest,
) -> QueryResponse[SeatWithoutNodeIdSchema]:
    if get(db_session, node_id) is None:
        raise NotFoundException(f'Node ID {node_id} does not exist')
    path = f'/nodes/{node_id}/seats'
    try:
        bookmark = process_page_token(paginated_request, path)
    except Exception:
        raise
    page = list_seats(
        db_session,
        node_id,
        process_page_size(paginated_request.max_page_size),
        bookmark,
    )
    return QueryResponse(
        [to_seat_without_node_id_schema(_) for (_,) in page],
        *create_page_tokens(paginated_request, path, page),
    )


@post(
    path='/{node_id:int}/seats',
    sync_to_thread=True,
    tags=['nodes', 'seats'],
    summary='Create seat connected to node',
    description=(
        'Creates a new seat under the node identified by `node_id`.'
        'The seat can be associated with links after the seat has been'
        ' created with the `/seats/{seat_id}/links` API.<br />'
        '<br />'
        'Use the `/hosts/{host_id}/destinations` API to obtain IDs that can be'
        ' passed for `seat_ip.destination_id`. `host_id` must be that of the'
        " node's host, so if the node is hostless, setting"
        ' `seat_ip.destination_id` is not possible.'
    ),
    operation_class=custom_operation(
        custom_reqbody(description=SEAT_WRITE_DESCRIPTION, required=False)
    ),
    response_headers=[LocationHeader, ContentLocationHeader],
    response_description='Seat created, representation follows',
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
                f'Validation failed for POST {API_V1_PATH}/nodes/8/seats'
            ),
            validation_message_example=f'Expected `int` <= {PortNumberMeta.le}',
            validation_key_example='seat_ip.port_number',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description=(
                '`node_id` in the path is not associated with a node, or'
                ' `destination_id` is not associated with a destination.'
            ),
            detail_example='Node ID 429204 does not exist',
        ),
    },
)
def create_seat(
    db_session: Session,
    node_id: Annotated[int, NodeIDParam],
    data: SeatCreateSchema = None,
) -> Response[SeatSchema]:
    if data is None:
        data = SeatCreateSchema()
    node = get(db_session, node_id)
    if node is None:
        raise NotFoundException(f'Node ID {node_id} does not exist')

    if data.seat_ip is not None and data.seat_ip.destination_id is not None:
        destination = destination_get(db_session, data.seat_ip.destination_id)
        if destination is None:
            raise NotFoundException(
                f'Destination ID {data.seat_ip.destination_id} does not exist'
            )
        if destination.host_id != node.host_id:
            if node.host_id is None:
                raise ClientException(
                    'A destination cannot be associated with a seat when'
                    ' the node is not on a host.'
                )
            raise ClientException(
                f'Destination ID {data.seat_ip.destination_id} belongs to a'
                f' different host than host ID {node.host_id}, which node ID'
                f' {node_id} belongs to'
            )

    try:
        seat = seat_create(
            db_session,
            node_id,
            'ip' if data.seat_ip is not None else None,
            data.lsi_command,
        )
        if data.seat_ip is not None:
            seat = seat_create_ip(
                db_session,
                seat.seat_id,
                data.seat_ip.destination_id,
                data.seat_ip.port_number,
            )
        db_session.commit()
    except Exception:
        raise InternalServerException

    return Response(
        content=to_seat_schema(seat),
        headers={
            'Location': f'{API_V1_PATH}/seats/{seat.seat_id}',
            'Content-Location': f'{API_V1_PATH}/seats/{seat.seat_id}',
        },
    )


@list_resource_contacts_decorator('node_id', 'nodes', 'node', '8', '429204')
def list_node_contacts(
    db_session: Session,
    node_id: Annotated[int, NodeIDParam],
    paginated_request: PaginatedRequest,
) -> QueryResponse[ContactSchema]:
    try:
        return list_resource_contacts_operation(
            db_session, node_id, paginated_request, get, 'node', 'nodes', list_contacts
        )
    except Exception:
        raise


@add_contact_decorator('node_id', 'nodes', 'node', '8', '429204')
def add_contact(
    db_session: Session,
    node_id: Annotated[int, NodeIDParam],
    data: ContactAddSchema,
) -> Response[ContactSchema]:
    try:
        return add_contact_operation(
            db_session,
            node_id,
            data,
            get,
            'node',
            contact_is_associated,
            associate_contact,
        )
    except Exception:
        raise


@remove_contact_decorator('node_id', 'nodes', 'node', '8', NodeIDMeta.le, '429204')
def remove_contact(
    db_session: Session,
    node_id: Annotated[int, NodeIDParam],
    contact_id: Annotated[int, ContactIDParam],
) -> None:
    try:
        remove_contact_operation(
            db_session,
            node_id,
            contact_id,
            get,
            'node',
            contact_is_associated,
            dissociate_contact,
        )
    except Exception:
        raise


node_router = Router(
    path='/nodes',
    route_handlers=[
        get_node,
        query_nodes,
        create_node,
        update_node,
        copy_node,
        delete_node,
        list_node_endpoints_ipn,
        list_node_endpoints_imc,
        replace_endpoints_ipn,
        create_endpoint_ipn,
        update_endpoint_ipn,
        delete_endpoint_ipn,
        replace_endpoints_imc,
        create_endpoint_imc,
        update_endpoint_imc,
        delete_endpoint_imc,
        list_node_cl_protocols,
        create_cl_protocol,
        list_node_inducts,
        create_induct,
        list_node_seats,
        create_seat,
        list_node_contacts,
        add_contact,
        remove_contact,
    ],
)

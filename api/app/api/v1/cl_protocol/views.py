from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from litestar import Router, patch
from litestar import delete as _delete
from litestar import get as _get
from litestar.exceptions import (
    ClientException,
    InternalServerException,
    NotFoundException,
)
from msgspec import UNSET

from app.config import API_V1_PATH
from app.problem_details import create_400_response_spec, create_404_response_spec
from app.schemas import (
    custom_operation,
    custom_reqbody,
)

from ..schemas import GENERIC_RESPONSE_DESCRIPTION
from .schemas import (
    KNOWN_PROTOCOLS_STRING,
    UPDATE_CL_PROTOCOL_CLASS_OMITTED_DESC,
    ClProtocolIDMeta,
    ClProtocolIDParam,
    ClProtocolSchema,
    ClProtocolUpdateSchema,
    protocol_class_arr_to_int,
    protocol_class_int_to_arr,
    to_cl_protocol_schema,
)
from .service import (
    delete,
    get,
    get_by_details,
    get_cl_protocol_check_value,
    inducts_depend_on_cl_protocol,
    known_protocol_name_to_cli_map,
    update,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@_get(
    path='/{cl_protocol_id:int}',
    sync_to_thread=True,
    tags=['cl protocols'],
    summary='Get CL protocol',
    description='Retrieves a CL protocol by its `cl_protocol_id`.',
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for GET {API_V1_PATH}/cl-protocols/'
                f'{ClProtocolIDMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {ClProtocolIDMeta.le}',
            validation_key_example='cl_protocol_id',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description=(
                'CL protocol ID in path parameter is not associated with a resource'
            ),
            detail_example='CL protocol ID 173 does not exist',
        ),
    },
)
def get_cl_protocol(
    db_session: Session, cl_protocol_id: Annotated[int, ClProtocolIDParam]
) -> ClProtocolSchema:
    cl_protocol = get(db_session, cl_protocol_id)
    if cl_protocol is None:
        raise NotFoundException(f'CL protocol ID {cl_protocol_id} does not exist')
    return to_cl_protocol_schema(cl_protocol)


@patch(
    path='/{cl_protocol_id:int}',
    sync_to_thread=True,
    tags=['cl protocols'],
    summary='Update CL protocol',
    description=(
        'Updates the CL protocol identified by `cl_protocol_id` in the path'
        ' parameter.<br />'
        '<br />'
        'CL protocols on a given node cannot have duplicate names in terms of'
        ' bytes. Use the `GET /nodes/{node_id}/cl-protocols` API to see what names'
        ' are already used.<br />'
        '<br />'
        'If there are any inducts that use the CL protocol and whose `cli_command`'
        f' requires a particular `cl_protocol_name` (viz. {KNOWN_PROTOCOLS_STRING}),'
        " then trying to update the CL protocol's `cl_protocol_name`"
        ' will fail. Such inducts must be updated to use a different `cli_command`'
        ' or be removed before `cl_protocol_name` can be safely updated.'
    ),
    operation_class=custom_operation(
        custom_reqbody(
            description=(
                'If `cl_protocol_name` is defined, it must have a byte length in'
                ' the inclusive range 1 to 15.<br/>'
                '<br />'
                f'{UPDATE_CL_PROTOCOL_CLASS_OMITTED_DESC}'
                '<p>Note that using a different `cl_protocol_class` for one of the'
                ' `cl_protocol_name` values explicitly listed here will fail.</p>'
            ),
            required=False,
        )
    ),
    response_description='CL protocol updated, representation follows',
    responses={
        400: create_400_response_spec(
            description=(
                'Bad request syntax, validation error, CL protocol name is already'
                ' used by an existing resource on the same node, invalid class'
                ' for a well known protocol, or CL protocol is used by inducts'
                ' that rely on the CL protocol'
            ),
            client_error_detail_example=(
                '`extra` contains induct IDs of inducts that have a `cli_command`'
                " that must use `cl_protocol_name` = 'ltp'"
            ),
            client_error_extra=['459'],
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for PATCH {API_V1_PATH}/cl-protocols/'
                f'{ClProtocolIDMeta.le + 1}'
            ),
            validation_message_example=(
                'Length in bytes must be in the inclusive range [1, 15]'
            ),
            validation_key_example='cl_protocol_name',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description=(
                'CL protocol ID in path parameter is not associated with a resource'
            ),
            detail_example='CL protocol ID 173 does not exist',
        ),
    },
)
def update_cl_protocol(
    db_session: Session,
    cl_protocol_id: Annotated[int, ClProtocolIDParam],
    data: ClProtocolUpdateSchema = None,
) -> ClProtocolSchema:
    if data is None:
        data = ClProtocolUpdateSchema()
    cl_protocol = get(db_session, cl_protocol_id)
    if cl_protocol is None:
        raise NotFoundException(f'CL protocol ID {cl_protocol_id} does not exist')

    old_cl_protocol_name = cl_protocol.cl_protocol_name

    cl_protocol_name = (
        old_cl_protocol_name
        if data.cl_protocol_name is UNSET
        else data.cl_protocol_name
    )
    cl_protocol_class = (
        cl_protocol.cl_protocol_class
        if data.cl_protocol_class is UNSET
        else protocol_class_arr_to_int(data.cl_protocol_class)
    )

    cl_protocol_name_changed = cl_protocol_name != old_cl_protocol_name
    cl_protocol_class_changed = cl_protocol_class != cl_protocol.cl_protocol_class

    # No change
    if not (cl_protocol_name_changed or cl_protocol_class_changed):
        return to_cl_protocol_schema(cl_protocol)

    if (
        cl_protocol_name_changed
        and old_cl_protocol_name in known_protocol_name_to_cli_map.keys()
    ):
        inducts = inducts_depend_on_cl_protocol(db_session, cl_protocol_id)
        if inducts:
            raise ClientException(
                '`extra` contains induct IDs of inducts that have a'
                ' `cli_command` that must use `cl_protocol_name` ='
                f" '{old_cl_protocol_name}'",
                extra=inducts,
            )
        # TODO: if the new cl_protocol_name is also well known, then we could
        # try updating induct.cli_command to a new well known CLI, but we need
        # to be careful about induct_ip switching to a non-IP CLI.

    node_id = cl_protocol.node_id
    if (
        cl_protocol_name_changed
        and get_by_details(db_session, node_id, cl_protocol_name) is not None
    ):
        raise ClientException(
            f"A CL protocol with the name '{cl_protocol_name}' is already"
            f' associated with node ID {node_id}'
        )

    _check_val = get_cl_protocol_check_value(cl_protocol_name)
    if _check_val is not None and cl_protocol_class != _check_val:
        raise ClientException(
            f"CL protocol name '{cl_protocol_name}' must use protocol class"
            f' {protocol_class_int_to_arr(_check_val)}'
        )

    try:
        cl_protocol = update(
            db_session, cl_protocol_id, cl_protocol_name, cl_protocol_class
        )
    except Exception:
        raise InternalServerException
    return to_cl_protocol_schema(cl_protocol)


@_delete(
    path='/{cl_protocol_id:int}',
    sync_to_thread=True,
    tags=['cl protocols'],
    summary='Delete CL protocol',
    description=(
        'Deletes the CL protocol identified by `cl_protocol_id`.<br />'
        '<br />'
        'If there are any inducts that use the CL protocol and whose `cli_command`'
        f' requires a particular `cl_protocol_name` (viz. {KNOWN_PROTOCOLS_STRING}),'
        ' then trying to delete the CL protocol will fail. Such'
        ' inducts must be updated to use a different `cli_command` or be removed'
        ' before the CL protocol can be safely deleted.'
    ),
    responses={
        400: create_400_response_spec(
            description=(
                'Bad request syntax, validation error, or CL protocol is used by'
                ' inducts that rely on the CL protocol'
            ),
            client_error_detail_example=(
                '`extra` contains induct IDs of inducts that have a `cli_command`'
                " that must use `cl_protocol_name` = 'ltp'"
            ),
            client_error_extra=['459'],
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for DELETE {API_V1_PATH}/cl-protocols/'
                f'{ClProtocolIDMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {ClProtocolIDMeta.le}',
            validation_key_example='cl_protocol_id',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description=(
                'CL protocol ID in path parameter is not associated with a resource'
            ),
            detail_example='CL protocol ID 173 does not exist',
        ),
    },
)
def delete_cl_protocol(
    db_session: Session, cl_protocol_id: Annotated[int, ClProtocolIDParam]
) -> None:
    cl_protocol = get(db_session, cl_protocol_id)
    if cl_protocol is None:
        raise NotFoundException(f'CL protocol ID {cl_protocol_id} does not exist')
    inducts = inducts_depend_on_cl_protocol(db_session, cl_protocol_id)
    if inducts:
        raise ClientException(
            '`extra` contains induct IDs of inducts that have a `cli_command` that'
            f" must use `cl_protocol_name` = '{cl_protocol.cl_protocol_name}'",
            extra=inducts,
        )
    try:
        delete(db_session, cl_protocol_id)
    except Exception:
        raise InternalServerException


cl_protocol_router = Router(
    path='/cl-protocols',
    route_handlers=[get_cl_protocol, update_cl_protocol, delete_cl_protocol],
)

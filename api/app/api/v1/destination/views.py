from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING, Annotated

from litestar import Router, patch
from litestar import delete as _delete
from litestar import get as _get
from litestar.exceptions import (
    ClientException,
    InternalServerException,
    NotFoundException,
    ValidationException,
)
from msgspec import UNSET

from app.config import API_V1_PATH
from app.problem_details import (
    ProblemDetailsExtraSchema,
    create_400_response_spec,
    create_404_response_spec,
)
from app.schemas import custom_operation, custom_reqbody

from ..schemas import GENERIC_RESPONSE_DESCRIPTION
from .schemas import (
    DestinationIDMeta,
    DestinationIDParam,
    DestinationSchema,
    DestinationUpdateSchema,
    IPQueryParam,
    to_destination_schema,
)
from .service import (
    delete,
    get,
    get_by_host_id_and_ip_address,
    get_by_host_id_and_registered_name,
    update,
)

if TYPE_CHECKING:
    from litestar import Request
    from sqlalchemy.orm import Session


def validate_destination_value(
    request: Request, destination_value: str, validate_ip: bool
) -> tuple[str, bool]:
    """Call this at the start of a route handler. If `validate_ip` is
    `True`, a `ValidationException` is raised if `destination_value`
    could not be parsed as an IP address.

    Returns a 2-tuple with the parsed value and a boolean value where
    `True` means the value could be parsed as an IP address and `False`
    otherwise.
    """
    path = str(request.url).removeprefix(str(request.base_url))
    detail = f'Validation failed for {request.method} /{path}'
    ip = None
    try:
        ip = ipaddress.ip_address(destination_value)
    except ValueError as e:
        if validate_ip:
            raise ValidationException(
                detail=detail,
                extra=[
                    ProblemDetailsExtraSchema(
                        message=str(e), key='destination_value', source='body'
                    ).to_dict()
                ],
            )
    if ip is not None:
        return (str(ip), True)
    return (destination_value, False)


@_get(
    path='/{destination_id:int}',
    sync_to_thread=True,
    tags=['destinations'],
    summary='Get destination',
    description='Retrieves a destination by its `destination_id`.',
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                'Validation failed for GET'
                f' {API_V1_PATH}/destinations/{DestinationIDMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {DestinationIDMeta.le}',
            validation_key_example='destination_id',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description=(
                'Destination ID in path parameter is not associated with a resource'
            ),
            detail_example='Destination ID 1024 does not exist',
        ),
    },
)
def get_destination(
    db_session: Session, destination_id: Annotated[int, DestinationIDParam]
) -> DestinationSchema:
    destination = get(db_session, destination_id)
    if destination is None:
        raise NotFoundException(f'Destination ID {destination_id} does not exist')
    return to_destination_schema(destination)


@patch(
    path='/{destination_id:int}',
    sync_to_thread=True,
    tags=['destinations'],
    summary='Update destination',
    description=(
        'Updates the destination identified by `destination_id` in the path.'
        '<br /><br />'
        'Destinations with duplicate values are not allowed under the same host.'
        ' Use the `GET /hosts/{host_id}/destinations` API to see what values are'
        ' already used.'
    ),
    operation_class=custom_operation(custom_reqbody(required=False)),
    response_description='Destination updated, representation follows',
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
                f'Validation failed for PATCH {API_V1_PATH}/destinations/152?ip=true'
            ),
            validation_message_example=(
                "'192.000.0002.001' does not appear to be an IPv4 or IPv6 address"
            ),
            validation_key_example='destination_value',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description=(
                'Destination ID in path parameter is not associated with a resource'
            ),
            detail_example='Destination ID 1024 does not exist',
        ),
    },
)
def update_destination(
    request: Request,
    db_session: Session,
    destination_id: Annotated[int, DestinationIDParam],
    data: DestinationUpdateSchema = None,
    ip: Annotated[bool, IPQueryParam] = False,
) -> DestinationSchema:
    if data is None:
        data = DestinationUpdateSchema()
    destination_value, is_ip = validate_destination_value(
        request, data.destination_value, ip
    )
    destination = get(db_session, destination_id)
    if destination is None:
        raise NotFoundException(f'Destination ID {destination_id} does not exist')

    # No change
    if (
        data.destination_value is UNSET
        or data.destination_value == str(destination.ip_address)
        or data.destination_value == destination.registered_name
    ):
        return to_destination_schema(destination)

    host_id = destination.host_id

    if (
        is_ip and get_by_host_id_and_ip_address(db_session, host_id, destination_value)
    ) or get_by_host_id_and_registered_name(db_session, host_id, destination_value):
        raise ClientException(
            f"A destination with value '{destination_value}' is already associated"
            f' with host ID {host_id}'
        )

    try:
        if is_ip:
            destination = update(
                db_session, destination.destination_id, ip_address=destination_value
            )
        else:
            destination = update(
                db_session,
                destination.destination_id,
                registered_name=destination_value,
            )
    except Exception:
        raise InternalServerException
    return to_destination_schema(destination)


@_delete(
    path='/{destination_id:int}',
    sync_to_thread=True,
    tags=['destinations'],
    summary='Delete destination',
    description=(
        'Deletes the destination identified by `destination_id`.<br />'
        '<br />'
        'If any inducts or seats are using the destination, their reference will'
        ' be set to null.'
    ),
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                'Validation failed for DELETE'
                f' {API_V1_PATH}/destinations/{DestinationIDMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {DestinationIDMeta.le}',
            validation_key_example='destination_id',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description=(
                'Destination ID in path parameter is not associated with a resource'
            ),
            detail_example='Destination ID 1024 does not exist',
        ),
    },
)
def delete_destination(
    db_session: Session, destination_id: Annotated[int, DestinationIDParam]
) -> None:
    destination = get(db_session, destination_id)
    if destination is None:
        raise NotFoundException(f'Destination ID {destination_id} does not exist')
    try:
        delete(db_session, destination_id)
    except Exception:
        raise InternalServerException


destination_router = Router(
    path='/destinations',
    route_handlers=[get_destination, update_destination, delete_destination],
)

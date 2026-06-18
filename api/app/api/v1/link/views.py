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
from app.models import CommDirectionEnumInternal
from app.problem_details import (
    create_400_response_spec,
    create_404_response_spec,
)
from app.schemas import custom_operation, custom_reqbody

from ..band.service import get as band_get
from ..schemas import GENERIC_RESPONSE_DESCRIPTION
from ..underlying_communication_service.schemas import (
    UnderlyingCommunicationServiceIDMeta,
)
from ..underlying_communication_service.service import get_nonmatching_ids
from .schemas import (
    LinkIDMeta,
    LinkIDParam,
    LinkSchema,
    LinkUpdateSchema,
    to_link_schema,
)
from .service import (
    create_rf,
    delete,
    delete_rf,
    get,
    inducts_using_link,
    replace_underlying_communication_services,
    update,
    update_rf,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@_get(
    path='/{link_id:int}',
    sync_to_thread=True,
    tags=['links'],
    summary='Get link',
    description='Retrieves a link by its `link_id`.',
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for GET {API_V1_PATH}/links/{LinkIDMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {LinkIDMeta.le}',
            validation_key_example='link_id',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description='Link ID in path parameter is not associated with a resource',
            detail_example='Link ID 434 does not exist',
        ),
    },
)
def get_link(db_session: Session, link_id: Annotated[int, LinkIDParam]) -> LinkSchema:
    link = get(db_session, link_id)
    if link is None:
        raise NotFoundException(f'Link ID {link_id} does not exist')
    return to_link_schema(link)


@patch(
    path='/{link_id:int}',
    sync_to_thread=True,
    tags=['links'],
    summary='Update link',
    description=(
        'Updates the link specified by `link_id` in the path parameter.<br />'
        '<br />'
        'Use the `/underlying-communication-services` API to obtain IDs that can'
        ' be passed in the `underlying_communication_service_ids` array.<br />'
        'Use the `/bands` API to obtain IDs that can be paased for'
        ' `link_rf.band_id`.'
    ),
    operation_class=custom_operation(
        custom_reqbody(
            description=(
                '`underlying_communication_service_ids` can consist of an array of'
                ' strings or integers. Duplicate values are eliminated. There is no'
                ' guarantee that links and services are associated in the order of'
                ' IDs in the array. Note that the value for'
                ' `underlying_communication_service_ids` replaces the underlying'
                ' communication services associated with the link. That is, an'
                ' empty array (`[]`) will clear associated services.<br />'
                '<br />'
                'Note that passing an empty object (`{}`) for `link_rf` will not'
                ' result in any changes. If `link_rf` is currently null, then'
                ' it will stay null. If `link_rf` is an object, then it will not'
                ' be updated. This behavior is different from the `POST /hosts/'
                '{host_id}/links` API where an empty object for `link_rf` will'
                ' set `link_rf.band_id` to null. The difference is that'
                ' LinkCreateSchema has a default value for `band_id` while'
                ' LinkUpdateSchema does not.<br />'
                '<br />'
                'If a property is absent from the request body, then it will not'
                ' be updated.'
            ),
            required=False,
        )
    ),
    response_description='Link updated, representation follows',
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for PATCH {API_V1_PATH}/hosts/6/links'
            ),
            validation_message_example=(
                f'Expected `int` <= {UnderlyingCommunicationServiceIDMeta.le}'
            ),
            validation_key_example='underlying_communication_service_ids[0]',
            validation_source_example='body',
        ),
        404: create_404_response_spec(
            description=(
                'Link ID in path parameter is not associated with a resource,'
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
def update_link(
    db_session: Session,
    link_id: Annotated[int, LinkIDParam],
    data: LinkUpdateSchema = None,
) -> LinkSchema:
    if data is None:
        data = LinkUpdateSchema()
    link = get(db_session, link_id)
    if link is None:
        raise NotFoundException(f'Link ID {link_id} does not exist')

    direction = link.direction if data.direction is UNSET else data.direction

    link_rf_is_empty = (
        data.link_rf not in (UNSET, None) and data.link_rf.band_id is UNSET
    )
    link_rf_is_unset_or_empty = data.link_rf is UNSET or link_rf_is_empty

    link_type = (
        link.type
        if link_rf_is_unset_or_empty
        else 'rf'
        if data.link_rf is not None
        else None
    )
    # If data.link_rf is UNSET or {}, then nothing changes. Use the current
    # band_id if link_rf exists.
    if link_rf_is_unset_or_empty and link.link_rf is not None:
        band_id = link.link_rf.band_id
    # If data.link_rf is {band_id: ...}, then either update link_rf.band_id if
    # link_rf already exists or create a new link_rf record.
    elif data.link_rf not in (UNSET, None) and data.link_rf.band_id is not UNSET:
        band_id = data.link_rf.band_id
    else:
        band_id = None

    if (
        data.underlying_communication_service_ids is not UNSET
        and data.underlying_communication_service_ids
    ):
        ids = get_nonmatching_ids(db_session, data.underlying_communication_service_ids)
        if ids:
            raise NotFoundException(
                '`extra` contains IDs from `underlying_communication_service_ids`'
                ' that refer to services that do not exist',
                extra=ids,
            )

    if band_id is not None and band_get(db_session, band_id) is None:
        raise NotFoundException(f'Band ID {band_id} does not exist')

    if (
        direction != link.direction
        and direction == CommDirectionEnumInternal.SIMPLEX_OUT.value
    ):
        inducts = inducts_using_link(db_session, link_id)
        if inducts:
            raise ClientException(
                '`extra` contains induct IDs of inducts associated with the'
                ' link which prevents updating direction to'
                f" '{CommDirectionEnumInternal.SIMPLEX_OUT.value}'",
                extra=inducts,
            )

    try:
        # Remove _rf child if needed before changing link.type column
        if link.link_rf is not None and data.link_rf is None:
            delete_rf(db_session, link_id)
        link = update(
            db_session,
            link_id,
            link.host_id,
            direction,
            link_type,
        )
        if link_type == 'rf':
            if link.link_rf is None:
                create_rf(db_session, link_id, band_id)
            else:
                update_rf(db_session, link_id, band_id)
        if data.underlying_communication_service_ids is not UNSET:
            replace_underlying_communication_services(
                db_session, link_id, data.underlying_communication_service_ids
            )
        db_session.commit()
    except Exception:
        raise InternalServerException
    return to_link_schema(link)


@_delete(
    path='/{link_id:int}',
    sync_to_thread=True,
    tags=['links'],
    summary='Delete link',
    description=(
        'Deletes the link specified by `link_id`.<br />'
        '<br />'
        'Deleting a link will dissociate inducts and spans from the link.'
    ),
    responses={
        400: create_400_response_spec(
            description='Bad request syntax or validation error',
            include_validation_error=True,
            validation_detail_example=(
                f'Validation failed for DELETE {API_V1_PATH}/links/{LinkIDMeta.le + 1}'
            ),
            validation_message_example=f'Expected `int` <= {LinkIDMeta.le}',
            validation_key_example='link_id',
            validation_source_example='path',
        ),
        404: create_404_response_spec(
            description='Link ID in path parameter is not associated with a resource',
            detail_example='Link ID 434 does not exist',
        ),
    },
)
def delete_link(db_session: Session, link_id: Annotated[int, LinkIDParam]) -> None:
    if get(db_session, link_id) is None:
        raise NotFoundException(f'Link ID {link_id} does not exist')
    delete(db_session, link_id)


link_router = Router(path='/links', route_handlers=[get_link, update_link, delete_link])

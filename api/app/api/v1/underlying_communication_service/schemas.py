from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Annotated

from msgspec import Meta

from app.fields import UNDERLYING_COMMUNICATION_SERVICE_ID_MAX
from app.schemas import BaseStruct, nonnegative_int_reqbody_extra_json_schema

from ..schemas import FIELDS_ALL, QueryRequest, create_fields_param

if TYPE_CHECKING:
    from app.models import UnderlyingCommunicationService

UnderlyingCommunicationServiceIDMeta = Meta(
    ge=0,
    le=UNDERLYING_COMMUNICATION_SERVICE_ID_MAX,
    title='Underlying Communication Service ID',
    description='Surrogate key to identify an underlying communication service',
    examples=['1'],
    extra_json_schema=nonnegative_int_reqbody_extra_json_schema,
)


def to_underlying_communication_service_schema(
    service: UnderlyingCommunicationService,
) -> UnderlyingCommunicationServiceSchema:
    return UnderlyingCommunicationServiceSchema(
        underlying_communication_service_id=str(
            service.underlying_communication_service_id
        ),
        underlying_communication_service_name=service.underlying_communication_service_name,
        underlying_communication_service_abbreviation=(
            service.underlying_communication_service_abbreviation
        ),
    )


class UnderlyingCommunicationServiceSchema(BaseStruct):
    """Representation of an underlying commuication service in
    responses.
    """

    underlying_communication_service_id: Annotated[
        str,
        Meta(
            title=UnderlyingCommunicationServiceIDMeta.title,
            description=UnderlyingCommunicationServiceIDMeta.description,
            examples=UnderlyingCommunicationServiceIDMeta.examples,
        ),
    ]
    underlying_communication_service_name: Annotated[
        str,
        Meta(
            title='Underlying Communication Service Name',
            description=(
                'Name of some technology or service used at the data link layer'
                ' or lower'
            ),
            examples=['Unified Space Data Link Protocol'],
        ),
    ]
    underlying_communication_service_abbreviation: Annotated[
        str,
        Meta(
            title='Underlying Communication Service Abbreviation',
            description=(
                'Short label for a technology or service used at the data link'
                ' layer or lower'
            ),
            examples=['USLP'],
        ),
    ]

    # TODO: consider having a used_by_links relationship


class UnderlyingCommunicationServiceFieldsEnum(str, Enum):
    ALL = FIELDS_ALL
    UNDERLYING_COMMUNICATION_SERVICE_ID = 'underlying_communication_service_id'
    UNDERLYING_COMMUNICATION_SERVICE_NAME = 'underlying_communication_service_name'
    UNDERLYING_COMMUNICATION_SERVICE_ABBREVIATION = (
        'underlying_communication_service_abbreviation'
    )


class UnderlyingCommunicationServiceQueryRequest(QueryRequest):
    """Specifies query parameters for querying underlying communication
    services.
    """

    fields: Annotated[
        list[UnderlyingCommunicationServiceFieldsEnum] | None,
        create_fields_param(
            [e.value for e in UnderlyingCommunicationServiceFieldsEnum]
        ),
    ] = None

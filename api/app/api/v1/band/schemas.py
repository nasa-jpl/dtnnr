from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Annotated

from msgspec import Meta

from app.fields import BAND_ID_MAX
from app.schemas import BaseStruct, nonnegative_int_reqbody_extra_json_schema

from ..schemas import FIELDS_ALL, QueryRequest, create_fields_param

if TYPE_CHECKING:
    from app.models import Band

BandIDMeta = Meta(
    ge=0,
    le=BAND_ID_MAX,
    title='Band ID',
    description='Surrogate key to identify a band',
    examples=['1'],
    extra_json_schema=nonnegative_int_reqbody_extra_json_schema,
)


def to_schema(band: Band) -> BandSchema:
    return BandSchema(band_id=str(band.band_id), band_name=band.band_name)


class BandSchema(BaseStruct):
    """Representation of a band in responses."""

    band_id: Annotated[
        str,
        Meta(
            title=BandIDMeta.title,
            description=BandIDMeta.description,
            examples=BandIDMeta.examples,
        ),
    ]
    band_name: Annotated[
        str,
        Meta(
            title='Band Name',
            description='Name of the radar band, preferably from IEEE 521-2002',
            examples=['UHF'],
        ),
    ]


class BandFieldsEnum(str, Enum):
    ALL = FIELDS_ALL
    BAND_ID = 'band_id'
    BAND_NAME = 'band_name'


class BandQueryRequest(QueryRequest):
    """Specifies query parameters for querying bands."""

    fields: Annotated[
        list[BandFieldsEnum] | None,
        create_fields_param([e.value for e in BandFieldsEnum]),
    ] = None

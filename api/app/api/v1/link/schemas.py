from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from litestar.openapi.spec import Example, Schema
from litestar.params import Body, Parameter
from msgspec import UNSET, Meta

from app.fields import LINK_ID_MAX
from app.models import CommDirectionEnum, CommDirectionEnumInternal
from app.schemas import (
    JSON_NULL,
    BaseStruct,
    nonnegative_bigint_pathparam_schema_extra,
    nonnegative_bigint_reqbody_extra_json_schema,
    nonnegative_int_reqbody_extra_json_schema,
    nullable_nonnegative_int_reqbody_extra_json_schema,
)

from ..band.schemas import BandIDMeta, BandSchema
from ..band.schemas import to_schema as to_band_schema
from ..host.schemas import HostIDMeta
from ..underlying_communication_service.schemas import (
    UnderlyingCommunicationServiceIDMeta,
    UnderlyingCommunicationServiceSchema,
    to_underlying_communication_service_schema,
)

if TYPE_CHECKING:
    from app.models import Link, LinkRf


LinkIDMeta = Meta(
    ge=0,
    le=LINK_ID_MAX,
    title='Link ID',
    description='Surrogate key to identify a link',
    examples=['1986'],
    extra_json_schema=nonnegative_bigint_reqbody_extra_json_schema,
)

CommDirectionMeta = Meta(
    title='Direction',
    description='Duplex capacity of the communication system',
    examples=[CommDirectionEnum.FULL_DUPLEX],
)

LinkIDParam = Parameter(
    ge=LinkIDMeta.ge,
    le=LinkIDMeta.le,
    title=LinkIDMeta.title,
    description=LinkIDMeta.description,
    schema_extra=nonnegative_bigint_pathparam_schema_extra,
)


def to_link_rf_schema(link_rf: LinkRf) -> LinkRfSchema:
    return LinkRfSchema(
        band=to_band_schema(link_rf.band) if link_rf.band is not None else None
    )


class LinkRfSchema(BaseStruct):
    """Fields specific only to radio links."""

    band: BandSchema | None


def render_direction(direction: str) -> str | None:
    if direction == CommDirectionEnumInternal.N_A:
        return None
    return direction


def to_link_schema(
    link: Link, with_host: bool = True
) -> LinkSchema | LinkWithoutHostIdSchema:
    """If `with_host` is True (default), return `link` converted to
    `LinkSchema`, else converts to `LinkWithoutHostIdSchema`.
    """
    if with_host:
        return LinkSchema(
            link_id=str(link.link_id),
            direction=render_direction(link.direction),
            host_id=str(link.host_id),
            underlying_communication_services=[
                to_underlying_communication_service_schema(s)
                for s in link.underlying_communication_services
            ],
            link_rf=(
                to_link_rf_schema(link.link_rf) if link.link_rf is not None else None
            ),
        )
    else:
        return LinkWithoutHostIdSchema(
            link_id=str(link.link_id),
            direction=render_direction(link.direction),
            underlying_communication_services=[
                to_underlying_communication_service_schema(s)
                for s in link.underlying_communication_services
            ],
            link_rf=(
                to_link_rf_schema(link.link_rf) if link.link_rf is not None else None
            ),
        )


class LinkWithoutHostIdSchema(BaseStruct, kw_only=True):
    """Representation of a link in responses where host_id is redundant."""

    link_id: Annotated[
        str,
        Meta(
            title=LinkIDMeta.title,
            description=LinkIDMeta.description,
            examples=LinkIDMeta.examples,
        ),
    ]
    direction: Annotated[CommDirectionEnum | None, CommDirectionMeta]
    underlying_communication_services: list[UnderlyingCommunicationServiceSchema]
    # `LinkRfSchema | None` needs to be inside an Annotated[] to be added to the
    # list of required properties of the generated LinkSchema for some reason
    link_rf: Annotated[LinkRfSchema | None, None]


class LinkSchema(LinkWithoutHostIdSchema):
    """Representation of a link in responses."""

    host_id: Annotated[
        str,
        Meta(
            title=HostIDMeta.title,
            description=HostIDMeta.description,
            examples=HostIDMeta.examples,
        ),
    ]


class LinkRfCreateSchema(BaseStruct):
    """Specifies the `link_rf` object for `LinkCreateSchema`."""

    band_id: Annotated[
        Annotated[int, Meta(ge=BandIDMeta.ge, le=BandIDMeta.le)] | None,
        Meta(
            title=BandIDMeta.title,
            description=BandIDMeta.description,
            examples=BandIDMeta.examples,
            extra_json_schema=nullable_nonnegative_int_reqbody_extra_json_schema,
        ),
    ] = JSON_NULL


class LinkCreateSchema(BaseStruct):
    """Specifies the request body for creating a link."""

    direction: Annotated[CommDirectionEnum | None, CommDirectionMeta] = JSON_NULL
    underlying_communication_service_ids: Annotated[
        # The Meta inside the list[Annotated] still performs validation, but
        # it does not generate any documentation
        list[
            Annotated[
                int,
                Meta(
                    ge=UnderlyingCommunicationServiceIDMeta.ge,
                    le=UnderlyingCommunicationServiceIDMeta.le,
                ),
            ]
        ],
        Meta(
            extra_json_schema={
                'extra': {
                    'items': {
                        'description': UnderlyingCommunicationServiceIDMeta.description,
                        'oneOf': UnderlyingCommunicationServiceIDMeta.extra_json_schema[
                            'extra'
                        ]['oneOf'],
                    },
                    'examples': [[1, 2, 3]],
                    'default': [],
                }
            }
        ),
    ] = []
    link_rf: LinkRfCreateSchema | None = JSON_NULL

    def __post_init__(self):
        if self.direction is JSON_NULL or self.direction is None:
            self.direction = CommDirectionEnumInternal.N_A
        if self.underlying_communication_service_ids:
            self.underlying_communication_service_ids = list(
                set(self.underlying_communication_service_ids)
            )
        if self.link_rf is JSON_NULL:
            self.link_rf = None
        elif self.link_rf is not None and self.link_rf.band_id is JSON_NULL:
            self.link_rf.band_id = None


class LinkRfUpdateSchema(BaseStruct):
    """Specifies the `link_rf` object for `LinkUpdateSchema`."""

    band_id: Annotated[
        Annotated[int, Meta(ge=BandIDMeta.ge, le=BandIDMeta.le)] | None,
        Meta(
            title=BandIDMeta.title,
            description=BandIDMeta.description,
            examples=BandIDMeta.examples,
            extra_json_schema=nullable_nonnegative_int_reqbody_extra_json_schema,
        ),
    ] = UNSET


class LinkUpdateSchema(BaseStruct):
    """Specifies the request body for updating a link."""

    direction: Annotated[CommDirectionEnum | None, CommDirectionMeta] = UNSET
    underlying_communication_service_ids: Annotated[
        # The Meta inside the list[Annotated] still performs validation, but
        # it does not generate any documentation
        list[
            Annotated[
                int,
                Meta(
                    ge=UnderlyingCommunicationServiceIDMeta.ge,
                    le=UnderlyingCommunicationServiceIDMeta.le,
                ),
            ]
        ],
        Meta(
            extra_json_schema={
                'extra': {
                    'items': {
                        'description': UnderlyingCommunicationServiceIDMeta.description,
                        'oneOf': nonnegative_int_reqbody_extra_json_schema['extra'][
                            'oneOf'
                        ],
                    },
                    'examples': [[1, 2, 3]],
                }
            }
        ),
    ] = UNSET
    link_rf: LinkRfUpdateSchema | None = UNSET

    def __post_init__(self):
        if self.direction is None:
            self.direction = CommDirectionEnumInternal.N_A
        if self.underlying_communication_service_ids is not UNSET:
            self.underlying_communication_service_ids = list(
                set(self.underlying_communication_service_ids)
            )


LinkIDsReplaceBody = Body(
    schema_extra={
        'items': Schema(
            title=LinkIDMeta.title,
            description=LinkIDMeta.description,
            one_of=nonnegative_bigint_reqbody_extra_json_schema['extra']['oneOf'],
        )
    },
    examples=[Example(value=[int(i) for i in LinkIDMeta.examples])],
)

type LinkIDsReplaceSet = set[Annotated[int, Meta(ge=LinkIDMeta.ge, le=LinkIDMeta.le)]]

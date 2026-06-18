from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from litestar.exceptions import ValidationException
from litestar.openapi.spec import OpenAPIType, Schema
from litestar.params import Body, Parameter
from msgspec import UNSET, Meta

from app.fields import GROUP_NUMBER_MAX, SERVICE_NUMBER_MAX
from app.models import DispositionEnum
from app.problem_details import (
    ExtraSourceEnum,
    ProblemDetailsExtraSchema,
)
from app.schemas import (
    JSON_NULL,
    BaseStruct,
    bigint,
    nonnegative_bigint_pathparam_schema_extra,
    nonnegative_bigint_reqbody_extra_json_schema,
    nonnegative_bigint_resbody_extra_json_schema,
    nullable_nonnegative_bigint_reqbody_extra_json_schema,
    nullable_positive_bigint_reqbody_extra_json_schema,
)

from ..allocator.schemas import AllocatorIDMeta
from ..node.schemas import NodeNumberMeta

if TYPE_CHECKING:
    from app.models import EndpointIMC, EndpointIPN

ServiceNumberMeta = Meta(
    ge=0,
    le=SERVICE_NUMBER_MAX,
    title='Service Number',
    # Description from Section 3.5 of RFC 0759
    description=(
        'Unsigned integer that identifies a particular service operating on a'
        ' node. A service in this case is some logical function that requires'
        ' its own resource identifier to distinguish it from other functions'
        ' operating on the same node'
    ),
    # RFC 9758 reserves 0xEEE0 .. 0xEEEF as an example range of well-known
    # service numbers.
    examples=[61152],
    extra_json_schema=nullable_nonnegative_bigint_reqbody_extra_json_schema,
)

ServiceNumberParam = Parameter(
    ge=ServiceNumberMeta.ge,
    le=ServiceNumberMeta.le,
    title=ServiceNumberMeta.title,
    description=ServiceNumberMeta.description,
    schema_extra=nonnegative_bigint_pathparam_schema_extra,
)

GroupNumberMeta = Meta(
    ge=1,
    le=GROUP_NUMBER_MAX,
    title='Group Number',
    description='Number identifying an IMC multicast group',
    # imc:11.0 example from Section 2.1 of I-D.burleigh-dtnrg-imc-00
    examples=[11],
    extra_json_schema=nullable_positive_bigint_reqbody_extra_json_schema,
)

GroupNumberParam = Parameter(
    ge=GroupNumberMeta.ge,
    le=GroupNumberMeta.le,
    title=GroupNumberMeta.title,
    description=GroupNumberMeta.description,
    schema_extra=nonnegative_bigint_pathparam_schema_extra,
)

DispositionMeta = Meta(
    title='Disposition',
    description=(
        'Controls behavior of bundles destined for this endpoint arrive when no'
        " application has the endpoint open for reception. 'x' means to discard"
        " silently and immediately. 'q' means enqueue for later delivery."
    ),
    examples=[DispositionEnum.DISCARD],
)

ApplicationMeta = Meta(
    title='Application',
    description='The application that has this endpoint open for reception',
    examples=['bprecvfile'],
)

ipnURIMeta = Meta(
    title='ipn URI',
    description=(
        'ipn URI identifying this endpoint complying with the ipn URI scheme'
        ' described in RFC 9758. The API only supports limited ranges for number'
        f' parts. Allocator Identifiers are expected to be in [{AllocatorIDMeta.ge},'
        f' {AllocatorIDMeta.le}]. Node Numbers are expected to be in ['
        f'{NodeNumberMeta.ge}, {NodeNumberMeta.le}]. Service Numbers are expected'
        f' to be in [{ServiceNumberMeta.ge}, {ServiceNumberMeta.le}].'
    ),
    examples=[
        (
            f'ipn:{AllocatorIDMeta.examples[0]}.'
            f'{NodeNumberMeta.examples[0]}.'
            f'{ServiceNumberMeta.examples[0]}'
        )
    ],
)

imcURIMeta = Meta(
    title='imc URI',
    description=(
        'imc URI identifying this endpoint complying with the imc URI scheme'
        ' described in I-D.burleigh-dtnrg-imc-00. The API only supports a limited'
        f' range for group numbers: [{GroupNumberMeta.ge}, {GroupNumberMeta.le}].'
    ),
    examples=[f'imc:{GroupNumberMeta.examples[0]}.0'],
)


def to_ipn_uri(allocator_id: int, node_number: int, service_number: int) -> str:
    # RFC 9758 says "<allocator_id>." MAY be ommitted when allocator_id == 0.
    # I'd prefer to not do this since it's not a recommendation (just MAY),
    # but since ION 4.1.3s does not support allocator identifiers, omitting
    # them will make ION Config Tool's usage of the API easier.
    # RFC also says '!' SHOULD be used instead of the FQNN when
    # allocator_id == 0 and node_number == 2^32 - 1.
    if allocator_id == 0 and node_number == 2**32 - 1:
        fqnn = '!'
    elif allocator_id == 0:
        fqnn = str(node_number)
    else:
        fqnn = f'{allocator_id}.{node_number}'
    return f'ipn:{fqnn}.{service_number}'


def to_endpoint_ipn_schema(endpoint: EndpointIPN) -> EndpointIPNSchema:
    allocator_id = endpoint.node.allocator_id
    node_number = endpoint.node.node_number
    service_number = endpoint.service_number
    return EndpointIPNSchema(
        uri=to_ipn_uri(allocator_id, node_number, service_number),
        # TODO: reconsider always serializing as str if API users don't like having
        # to deal with numbers and strings.
        service_number=bigint(service_number),
        disposition=endpoint.disposition,
        application=endpoint.application,
    )


class EndpointIPNSchema(BaseStruct):
    """Representation of an endpoint_ipn in responses."""

    uri: Annotated[str, ipnURIMeta]
    service_number: Annotated[
        int | str,
        Meta(
            title=ServiceNumberMeta.title,
            description=ServiceNumberMeta.description,
            examples=ServiceNumberMeta.examples,
            extra_json_schema=nonnegative_bigint_resbody_extra_json_schema,
        ),
    ]
    disposition: Annotated[DispositionEnum, DispositionMeta]
    application: Annotated[str | None, ApplicationMeta]


def _is_number(n: str) -> bool:
    if not n:
        return False
    if n == '0':
        return True
    if n[0] != '0' and n.isdigit() and n.isascii():
        return True
    return False


def parse_ipn_uri(uri: str) -> tuple[int, int, int]:
    """Parses `uri` to return a 3-tuple (allocator identifier, node
    number, service number).
    """
    assert uri[:4] == 'ipn:'
    ipn_hier_part = uri[4:]
    dot_before_service_number = ipn_hier_part.rfind('.')
    assert dot_before_service_number > 0
    fqnn = ipn_hier_part[:dot_before_service_number]
    if fqnn == '!':
        allocator_identifier = 0
        node_number = 2**32 - 1
    else:
        allocator_id_dot = fqnn.find('.')
        if allocator_id_dot > 0:  # allocator present
            assert allocator_id_dot > 0
            allocator_identifier = fqnn[:allocator_id_dot]
            node_number = fqnn[allocator_id_dot + 1 :]
            assert _is_number(allocator_identifier)
            assert _is_number(node_number)
        else:
            assert allocator_id_dot == -1
            allocator_identifier = 0
            assert _is_number(fqnn)
            node_number = fqnn
    service_number = ipn_hier_part[dot_before_service_number + 1 :]
    assert _is_number(service_number)
    return (int(allocator_identifier), int(node_number), int(service_number))


def validate_uri_and_service_number(
    struct: 'EndpointIPNReplaceSchema' | 'EndpointIPNUpdateSchema', key_prefix: str = ''
) -> None:
    # ValidationException `detail` will be replaced by an exception handler
    # on the route handler, so it doesn't matter what we pass there.
    detail = ''
    if struct.uri is None and struct.service_number is None:
        raise ValidationException(
            detail,
            extra=[
                ProblemDetailsExtraSchema(
                    message='`uri` and `service_number` cannot both be `null`',
                    key=f'{key_prefix}uri',
                    source=ExtraSourceEnum.BODY.value,
                )
            ],
        )
    if struct.uri not in (None, UNSET):
        try:
            (allocator_id, node_number, uri_serv_num) = parse_ipn_uri(struct.uri)
        except Exception:
            raise ValidationException(
                detail,
                extra=[
                    ProblemDetailsExtraSchema(
                        message=(
                            f"'{struct.uri}' does not comply with the text syntax"
                            ' of an ipn URI'
                        ),
                        key=f'{key_prefix}uri',
                        source=ExtraSourceEnum.BODY.value,
                    )
                ],
            )
        # The "ge" checks are for negative numbers, but these should never
        # execute since parse_ipn_uri() should reject negative numbers for
        # these fields.
        if allocator_id < AllocatorIDMeta.ge:
            raise ValidationException(
                detail,
                extra=[
                    ProblemDetailsExtraSchema(
                        message=(
                            f'Expected Allocator Identifier in `uri` ({struct.uri}) >='
                            f' {AllocatorIDMeta.ge}, but got {allocator_id}'
                        ),
                        key=f'{key_prefix}uri',
                        source=ExtraSourceEnum.BODY.value,
                    )
                ],
            )
        if node_number < NodeNumberMeta.ge:
            raise ValidationException(
                detail,
                extra=[
                    ProblemDetailsExtraSchema(
                        message=(
                            f'Expected Node Number in `uri` ({struct.uri}) >='
                            f' {AllocatorIDMeta.ge}, but got {allocator_id}'
                        ),
                        key=f'{key_prefix}uri',
                        source=ExtraSourceEnum.BODY.value,
                    )
                ],
            )
        if uri_serv_num < ServiceNumberMeta.ge:
            raise ValidationException(
                detail,
                extra=[
                    ProblemDetailsExtraSchema(
                        message=(
                            f'Expected Service Number in `uri` ({struct.uri}) >='
                            f' {AllocatorIDMeta.ge}, but got {allocator_id}'
                        ),
                        key=f'{key_prefix}.uri',
                        source=ExtraSourceEnum.BODY.value,
                    )
                ],
            )
        if allocator_id > AllocatorIDMeta.le:
            raise ValidationException(
                detail,
                extra=[
                    ProblemDetailsExtraSchema(
                        message=(
                            f'Expected Allocator Identifier in `uri` ({struct.uri}) <='
                            f' {AllocatorIDMeta.le}, but got {allocator_id}'
                        ),
                        key=f'{key_prefix}uri',
                        source=ExtraSourceEnum.BODY.value,
                    )
                ],
            )
        if node_number > NodeNumberMeta.le:
            raise ValidationException(
                detail,
                extra=[
                    ProblemDetailsExtraSchema(
                        message=(
                            f'Expected Node Number in `uri` ({struct.uri}) <='
                            f' {NodeNumberMeta.le}, but got {node_number}'
                        ),
                        key=f'{key_prefix}uri',
                        source=ExtraSourceEnum.BODY.value,
                    )
                ],
            )
        if uri_serv_num > ServiceNumberMeta.le:
            raise ValidationException(
                detail,
                extra=[
                    ProblemDetailsExtraSchema(
                        message=(
                            f'Expected Service Number in `uri` ({struct.uri}) <='
                            f' {ServiceNumberMeta.le}, but got {uri_serv_num}'
                        ),
                        key=f'{key_prefix}uri',
                        source=ExtraSourceEnum.BODY.value,
                    )
                ],
            )
        if struct.service_number in (None, UNSET):
            struct.service_number = uri_serv_num
    if (
        struct.uri not in (None, UNSET)
        and struct.service_number not in (None, UNSET)
        and uri_serv_num != struct.service_number
    ):
        raise ValidationException(
            detail,
            extra=[
                ProblemDetailsExtraSchema(
                    message=(
                        f'`service_number` ({struct.service_number}) conflicts with'
                        f' service number of `uri` ({struct.uri})'
                    ),
                    key=f'{key_prefix}service_number',
                    source=ExtraSourceEnum.BODY.value,
                )
            ],
        )
    return None


class EndpointIPNReplaceSchema(BaseStruct):
    """Specifies the request body for replacing endpoint_ipn's."""

    uri: Annotated[str | None, ipnURIMeta] = None
    service_number: Annotated[
        Annotated[int, Meta(ge=ServiceNumberMeta.ge, le=ServiceNumberMeta.le)] | None,
        Meta(
            title=ServiceNumberMeta.title,
            description=ServiceNumberMeta.description,
            examples=ServiceNumberMeta.examples,
            extra_json_schema=ServiceNumberMeta.extra_json_schema,
        ),
    ] = None
    application: Annotated[str | None, ApplicationMeta] = None
    disposition: Annotated[DispositionEnum, DispositionMeta] = (
        DispositionEnum.DISCARD.value
    )

    def validate(self, index: int = None):
        """Validate in a route handler rather than with __post_init__().
        Litestar uses a fixed format for msgspec Struct validation which
        is hard to modify. Most importantly, we lose the index of the
        object in the array.

        If calling this did not raise an exception, then you should
        access the service number through
        `EndpointIPNReplaceSchema.service_number`.
        """
        try:
            return validate_uri_and_service_number(
                self, '' if index is None else f'[{index}].'
            )
        except Exception:
            raise


class EndpointIPNUpdateSchema(BaseStruct):
    """Specifies the request body for updating endpoint_ipn's."""

    uri: Annotated[str, ipnURIMeta] = UNSET
    service_number: Annotated[
        int,
        Meta(
            ge=ServiceNumberMeta.ge,
            le=ServiceNumberMeta.le,
            title=ServiceNumberMeta.title,
            description=ServiceNumberMeta.description,
            examples=ServiceNumberMeta.examples,
        ),
    ] = UNSET
    application: Annotated[str | None, ApplicationMeta] = UNSET
    disposition: Annotated[DispositionEnum, DispositionMeta] = UNSET

    def validate(self):
        """Validate in a route handler rather than with __post_init__().
        Litestar uses a fixed format for msgspec Struct validation which
        is hard to modify.

        If calling this did not raise an exception, then you should
        access the service number through
        `EndpointIPNUpdateSchema.service_number`.
        """
        try:
            return validate_uri_and_service_number(self)
        except Exception:
            raise


def _create_endpoint_col_schema(meta: Meta, default=JSON_NULL) -> Schema:
    return Schema(
        title=meta.title,
        description=meta.description,
        default=default,
        examples=meta.examples,
        minimum=meta.extra_json_schema.get('extra').get('minimum'),
        maximum=meta.extra_json_schema.get('extra').get('maximum'),
        type=meta.extra_json_schema.get('extra').get('type'),
        format=meta.extra_json_schema.get('extra').get('format'),
        one_of=meta.extra_json_schema.get('extra').get('oneOf'),
    )


def _create_disposition_schema(default=DispositionEnum.DISCARD.value) -> Schema:
    return Schema(
        type=OpenAPIType.STRING,
        title=DispositionMeta.title,
        description=DispositionMeta.description,
        default=default,
        examples=DispositionMeta.examples,
        enum=[e.value for e in DispositionEnum],
    )


def _create_application_schema(default=JSON_NULL) -> Schema:
    return Schema(
        type=[OpenAPIType.STRING, OpenAPIType.NULL],
        title=ApplicationMeta.title,
        description=ApplicationMeta.description,
        default=default,
        examples=ApplicationMeta.examples,
    )


EndpointIPNReplaceBody = Body(
    schema_extra={
        'items': Schema(
            schema_not=Schema(
                properties={
                    'uri': Schema(type='null'),
                    'service_number': Schema(type='null'),
                }
            ),
            properties={
                'uri': Schema(
                    type=[OpenAPIType.STRING, OpenAPIType.NULL],
                    title=ipnURIMeta.title,
                    description=ipnURIMeta.description,
                    default=JSON_NULL,
                    examples=ipnURIMeta.examples,
                ),
                'service_number': _create_endpoint_col_schema(ServiceNumberMeta),
                'disposition': _create_disposition_schema(),
                'application': _create_application_schema(),
            },
        )
    },
)

EndpointIPNCreateBody = Body(
    schema_component_key='EndpointIPNCreateBody',
    schema_extra={
        'not': Schema(
            properties={
                'uri': Schema(type='null'),
                'service_number': Schema(type='null'),
            }
        ),
        'properties': {
            'uri': Schema(
                type=[OpenAPIType.STRING, OpenAPIType.NULL],
                title=ipnURIMeta.title,
                description=ipnURIMeta.description,
                default=JSON_NULL,
                examples=ipnURIMeta.examples,
            ),
            'service_number': _create_endpoint_col_schema(ServiceNumberMeta),
            'disposition': _create_disposition_schema(),
            'application': _create_application_schema(),
        },
    },
)

EndpointIPNUpdateBody = Body(
    schema_component_key='EndpointIPNUpdateBody',
    schema_extra={
        'properties': {
            'uri': Schema(
                type=OpenAPIType.STRING,
                title=ipnURIMeta.title,
                description=ipnURIMeta.description,
                examples=ipnURIMeta.examples,
            ),
            'service_number': _create_endpoint_col_schema(
                Meta(
                    ge=ServiceNumberMeta.ge,
                    le=ServiceNumberMeta.le,
                    title=ServiceNumberMeta.title,
                    description=ServiceNumberMeta.description,
                    examples=ServiceNumberMeta.examples,
                    extra_json_schema=nonnegative_bigint_reqbody_extra_json_schema,
                ),
                None,
            ),
            'disposition': _create_disposition_schema(None),
            'application': _create_application_schema(None),
        },
    },
)


def to_imc_uri(group_number: int) -> str:
    return f'imc:{group_number}.0'


def to_endpoint_imc_schema(endpoint: EndpointIMC) -> EndpointIMCSchema:
    group_number = endpoint.group_number
    return EndpointIMCSchema(
        uri=to_imc_uri(group_number),
        # TODO: reconsider always serializing as str if API users don't like having
        # to deal with numbers and strings.
        group_number=bigint(group_number),
        disposition=endpoint.disposition,
        application=endpoint.application,
    )


class EndpointIMCSchema(BaseStruct):
    """Representation of an endpoint_imc in responses."""

    uri: Annotated[str, imcURIMeta]
    group_number: Annotated[
        int | str,
        Meta(
            title=GroupNumberMeta.title,
            description=GroupNumberMeta.description,
            examples=GroupNumberMeta.examples,
            # This schema shows range [0, 2^63 - 1], but group number 0 is not
            # valid. I don't think it really matters - validation happens when
            # writing, not reading.
            extra_json_schema=nonnegative_bigint_resbody_extra_json_schema,
        ),
    ]
    disposition: Annotated[DispositionEnum, DispositionMeta]
    application: Annotated[str | None, ApplicationMeta]


def parse_imc_uri(uri: str) -> int:
    """Parses `uri` to return group number."""
    assert uri[:4] == 'imc:'
    imc_hier_part = uri[4:]
    nbr_delim = imc_hier_part.rfind('.')
    assert nbr_delim > 0
    assert imc_hier_part[nbr_delim + 1 :] == '0'
    group_nbr = imc_hier_part[:nbr_delim]
    assert _is_number(group_nbr)
    return int(group_nbr)


def validate_uri_and_group_number(
    struct: 'EndpointIMCReplaceSchema', key_prefix: str = ''
) -> None:
    # ValidationException `detail` will be replaced by an exception handler
    # on the route handler, so it doesn't matter what we pass there.
    detail = ''
    if struct.uri is None and struct.group_number is None:
        raise ValidationException(
            detail,
            extra=[
                ProblemDetailsExtraSchema(
                    message='`uri` and `group_number` cannot both be `null`',
                    key=f'{key_prefix}uri',
                    source=ExtraSourceEnum.BODY.value,
                )
            ],
        )
    if struct.uri not in (None, UNSET):
        try:
            group_number = parse_imc_uri(struct.uri)
        except Exception:
            raise ValidationException(
                detail,
                extra=[
                    ProblemDetailsExtraSchema(
                        message=(
                            f"'{struct.uri}' does not comply with the text syntax"
                            ' of an imc URI'
                        ),
                        key=f'{key_prefix}uri',
                        source=ExtraSourceEnum.BODY.value,
                    )
                ],
            )
        # The "ge" check is for negative numbers, but this should never
        # execute since parse_imc_uri() should reject negative group numbers.
        if group_number < GroupNumberMeta.ge:
            raise ValidationException(
                detail,
                extra=[
                    ProblemDetailsExtraSchema(
                        message=(
                            f'Expected Group Number in `uri` ({struct.uri}) >='
                            f' {GroupNumberMeta.ge}, but got {group_number}'
                        ),
                        key=f'{key_prefix}uri',
                        source=ExtraSourceEnum.BODY.value,
                    )
                ],
            )
        if group_number > GroupNumberMeta.le:
            raise ValidationException(
                detail,
                extra=[
                    ProblemDetailsExtraSchema(
                        message=(
                            f'Expected Group Number in `uri` ({struct.uri}) <='
                            f' {GroupNumberMeta.le}, but got {group_number}'
                        ),
                        key=f'{key_prefix}uri',
                        source=ExtraSourceEnum.BODY.value,
                    )
                ],
            )
        if struct.group_number in (None, UNSET):
            struct.group_number = group_number
    if (
        struct.uri not in (None, UNSET)
        and struct.group_number not in (None, UNSET)
        and group_number != struct.group_number
    ):
        raise ValidationException(
            detail,
            extra=[
                ProblemDetailsExtraSchema(
                    message=(
                        f'`group_number` ({struct.group_number}) conflicts with'
                        f' group number of `uri` ({struct.uri})'
                    ),
                    key=f'{key_prefix}group_number',
                    source=ExtraSourceEnum.BODY.value,
                )
            ],
        )
    return None


class EndpointIMCReplaceSchema(BaseStruct):
    """Specifies the request body for replacing endpoint_imc's."""

    uri: Annotated[str | None, imcURIMeta] = None
    group_number: Annotated[
        Annotated[int, Meta(ge=GroupNumberMeta.ge, le=GroupNumberMeta.le)] | None,
        Meta(
            title=GroupNumberMeta.title,
            description=GroupNumberMeta.description,
            examples=GroupNumberMeta.examples,
            extra_json_schema=GroupNumberMeta.extra_json_schema,
        ),
    ] = None
    application: Annotated[str | None, ApplicationMeta] = None
    disposition: Annotated[DispositionEnum, DispositionMeta] = (
        DispositionEnum.DISCARD.value
    )

    def validate(self, index: int = None):
        """Validate in a route handler rather than with __post_init__().
        Litestar uses a fixed format for msgspec Struct validation which
        is hard to modify. Most importantly, we lose the index of the
        object in the array.
        """
        try:
            return validate_uri_and_group_number(
                self, '' if index is None else f'[{index}].'
            )
        except Exception:
            raise


class EndpointIMCUpdateSchema(BaseStruct):
    """Specifies the request body for updating endpoint_imc's."""

    uri: Annotated[str, imcURIMeta] = UNSET
    group_number: Annotated[
        int,
        Meta(
            ge=GroupNumberMeta.ge,
            le=GroupNumberMeta.le,
            title=GroupNumberMeta.title,
            description=GroupNumberMeta.description,
            examples=GroupNumberMeta.examples,
            extra_json_schema=GroupNumberMeta.extra_json_schema,
        ),
    ] = UNSET
    application: Annotated[str | None, ApplicationMeta] = UNSET
    disposition: Annotated[DispositionEnum, DispositionMeta] = UNSET

    def validate(self):
        """Validate in a route handler rather than with __post_init__().
        Litestar uses a fixed format for msgspec Struct validation which
        is hard to modify. Most importantly, we lose the index of the
        object in the array.
        """
        try:
            return validate_uri_and_group_number(self)
        except Exception:
            raise


EndpointIMCReplaceBody = Body(
    schema_extra={
        'items': Schema(
            schema_not=Schema(
                properties={
                    'uri': Schema(type='null'),
                    'group_number': Schema(type='null'),
                }
            ),
            properties={
                'uri': Schema(
                    type=[OpenAPIType.STRING, OpenAPIType.NULL],
                    title=imcURIMeta.title,
                    description=imcURIMeta.description,
                    default=JSON_NULL,
                    examples=imcURIMeta.examples,
                ),
                'group_number': _create_endpoint_col_schema(GroupNumberMeta),
                'disposition': _create_disposition_schema(),
                'application': _create_application_schema(),
            },
        )
    },
)

EndpointIMCCreateBody = Body(
    schema_component_key='EndpointIMCCreateBody',
    schema_extra={
        'not': Schema(
            properties={
                'uri': Schema(type='null'),
                'group_number': Schema(type='null'),
            }
        ),
        'properties': {
            'uri': Schema(
                type=[OpenAPIType.STRING, OpenAPIType.NULL],
                title=imcURIMeta.title,
                description=imcURIMeta.description,
                default=JSON_NULL,
                examples=imcURIMeta.examples,
            ),
            'group_number': _create_endpoint_col_schema(GroupNumberMeta),
            'disposition': _create_disposition_schema(),
            'application': _create_application_schema(),
        },
    },
)

EndpointIMCUpdateBody = Body(
    schema_component_key='EndpointIMCUpdateBody',
    schema_extra={
        'properties': {
            'uri': Schema(
                type=[OpenAPIType.STRING, OpenAPIType.NULL],
                title=imcURIMeta.title,
                description=imcURIMeta.description,
                examples=imcURIMeta.examples,
            ),
            'group_number': _create_endpoint_col_schema(
                Meta(
                    ge=GroupNumberMeta.ge,
                    le=GroupNumberMeta.le,
                    title=GroupNumberMeta.title,
                    description=GroupNumberMeta.description,
                    examples=GroupNumberMeta.examples,
                    extra_json_schema=nonnegative_bigint_reqbody_extra_json_schema,
                ),
                None,
            ),
            'disposition': _create_disposition_schema(None),
            'application': _create_application_schema(None),
        },
    },
)

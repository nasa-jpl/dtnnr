from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Annotated

from litestar.params import Parameter
from msgspec import UNSET, Meta

from app.fields import CONTACT_ID_MAX
from app.problem_details import SchemaValidationError
from app.schemas import (
    JSON_NULL,
    BaseStruct,
    custom_reqbody,
    nonnegative_bigint_pathparam_schema_extra,
    nonnegative_bigint_reqbody_extra_json_schema,
    string_or_null_extra_json_schema,
)

from ..schemas import (
    FIELDS_ALL,
    QueryRequest,
    create_fields_param,
)

if TYPE_CHECKING:
    from app.models import Contact, ContactPhoneNumber

ContactIDMeta = Meta(
    ge=0,
    le=CONTACT_ID_MAX,
    title='Contact ID',
    description='Surrogate key to identify a point of contact',
    examples=['3342'],
    extra_json_schema=nonnegative_bigint_reqbody_extra_json_schema,
)

ContactNameMeta = Meta(
    title='Contact Name',
    description='Name of this point of contact. Cannot be blank.',
    examples=['John Doe'],
)

ContactEmailMeta = Meta(
    title='Email',
    description=(
        "Email address of this point of contact, but there's no validation for"
        " email addresses, so users are free to input whatever they'd like here."
    ),
    examples=['contact@example.com'],
    extra_json_schema=string_or_null_extra_json_schema,
)

PhoneNumberMeta = Meta(
    title='Phone Number',
    description=(
        'There is no enforced format for phone numbers; any string is acceptable'
        ' as long as it is not blank.'
    ),
    examples=['+1 800-555-0100'],
)

PhoneNumberPreferredMeta = Meta(
    title='Preferred',
    description='True if a phone number is marked as preferred, false otherwise.',
)

ContactIDParam = Parameter(
    ge=ContactIDMeta.ge,
    le=ContactIDMeta.le,
    title=ContactIDMeta.title,
    description=ContactIDMeta.description,
    schema_extra=nonnegative_bigint_pathparam_schema_extra,
)


def to_contact_schema(contact: Contact) -> ContactSchema:
    number = contact.phone_numbers[0].phone_number if contact.phone_numbers else None
    return ContactSchema(
        contact_id=str(contact.contact_id),
        contact_name=contact.contact_name,
        email=contact.email,
        primary_phone_number=number,
    )


class ContactSchema(BaseStruct):
    """Representation of a point of contact in responses."""

    # TODO: default value is UNSET so that they're not shown as required since
    # we plan to support a read mask with `fields`. Consider having a separate
    # struct only for the query endpoint since we don't plan to support `fields`
    # when requesting for a single resource.
    contact_id: Annotated[
        str,
        Meta(
            title=ContactIDMeta.title,
            description=ContactIDMeta.description,
            examples=ContactIDMeta.examples,
        ),
    ] = UNSET
    contact_name: Annotated[str, ContactNameMeta] = UNSET
    email: Annotated[str | None, ContactEmailMeta] = UNSET
    primary_phone_number: Annotated[str | None, PhoneNumberMeta] = UNSET


# TODO: current ContactSchema is fine to for both /contacts/{contact_id}
# and /allocators/{allocator_id}/contacts. what we're worried about are the
# links / related resources (what should be shown, and should it differ for
# looking at individual contacts and collection of contacts)
# {
#     contact_id: string,
#     contact_name: string,
#     email: string | null,
#     primary_phone_number: string | null,
#     phone_numbers: string, (i.e., /contacts/{contact_id}/phone-numbers)
#     allocators / operators / hosts / nodes:
#         either a link like
#         /allocators?filter=contacts.contact_id%3D{contact_id}
#         since frontend is using this for minimal data, may want to add
#         &fields=allocator_id&fields=allocator_name
#         alternatively, an array of objects with minimal data, like
#         [
#             {
#                 allocator_id: string,
#                 allocator_name: string,
#             }
#         ]
#        filtering won't be implemented until 0.3.0, so we'll have to go
#        with the array approach if we want them accessible before that
# }


class ContactQueryFieldsEnum(str, Enum):
    ALL = FIELDS_ALL
    CONTACT_ID = 'contact_id'
    CONTACT_NAME = 'contact_name'


class ContactQueryRequest(QueryRequest):
    """Specifies query parameters for querying points of contact."""

    fields: Annotated[
        list[ContactQueryFieldsEnum] | None,
        create_fields_param([e.value for e in ContactQueryFieldsEnum]),
    ] = None


class ContactUpdateSchema(BaseStruct):
    """Specifies the request body for updating a point of contact."""

    contact_name: Annotated[str, ContactNameMeta] = UNSET
    email: Annotated[str | None, ContactEmailMeta] = UNSET

    def __post_init__(self):
        if isinstance(self.contact_name, str) and not self.contact_name.strip():
            raise SchemaValidationError(
                key='contact_name',
                msg='`contact_name` cannot consist solely of whitespace',
            )


def associate_contact_description(resource_name: str, resource_id: str) -> str:
    return (
        'Either associates an existing point of contact identified by'
        ' `existing_contact_id` or creates a new point of contact with the'
        ' information from the request body and associates said point of'
        f' contact with the {resource_name} identified by `{resource_id}`.<br />'
        '<br />'
        'Use the `GET /contacts` API to check if the desired point of contact'
        ' already exists (and use that existing `contact_id` here).'
    )


def dissociate_contact_description(resource_name: str, resource_id: str) -> str:
    return (
        'Dissociates the point of contact identified by `contact_id` from the'
        f' {resource_name} identified by `{resource_id}`.<br />'
        '<br />'
        'Note that after this action is successfully performed, all contacts'
        ' which are not associated with any entities (allocators, operators,'
        ' hosts, or nodes) will be deleted from the database.<br />'
        '<br />'
        'Use the `GET /contacts` API to see if this contact is associated with'
        f' anything else besides this {resource_name}. If you want to change a'
        ' contact which is only used by one entity to another entity, you should'
        ' add the contact to that other entity first before removing it from this'
        f' {resource_name}. Otherwise, the contact would be deleted and you would'
        ' have to create it again.'
    )


ASSOCIATE_CONTACT_CUSTOM_REQBODY = custom_reqbody(
    description=(
        'A `contact_name` is required for a new contact, but an `email`'
        ' is not required.<br />'
        '<br />'
        'If an `existing_contact_id` is in the request, then a new point'
        ' of contact will not be created. `contact_name` and `email` are'
        ' ignored and the existing contact will be associated if possible.'
    ),
    required=True,
)


class ContactAddSchema(ContactUpdateSchema):
    """Specifies the request body for adding a point of contact to a
    parent.
    """

    email: Annotated[str | None, ContactEmailMeta] = JSON_NULL
    existing_contact_id: Annotated[int, ContactIDMeta] = UNSET

    def __post_init__(self):
        if self.existing_contact_id is UNSET and self.contact_name is UNSET:
            raise SchemaValidationError(
                key='contact_name', msg='Object missing required field `contact_name`'
            )
        if self.email is JSON_NULL:
            self.email = None
        super().__post_init__()


def to_phone_number_schema(phone_number: ContactPhoneNumber) -> PhoneNumberSchema:
    return PhoneNumberSchema(
        phone_number=phone_number.phone_number,
        preferred=phone_number.preferred,
    )


class PhoneNumberSchema(BaseStruct):
    """Representation of a phone number entity in responses."""

    phone_number: Annotated[str, PhoneNumberMeta]
    preferred: Annotated[bool, PhoneNumberPreferredMeta]


class PhoneNumberReplaceSchema(PhoneNumberSchema):
    """Specifies the request body for replacing the phone numbers of a
    point of contact.
    """

    preferred: Annotated[bool, PhoneNumberPreferredMeta] = False

    def __post_init__(self):
        if isinstance(self.phone_number, str) and not self.phone_number.strip():
            raise SchemaValidationError(
                key='phone_number',
                msg='`phone_number` cannot consist solely of whitespace',
            )

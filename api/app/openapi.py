from litestar.openapi import OpenAPIConfig
from litestar.openapi.plugins import SwaggerRenderPlugin
from litestar.openapi.spec import Contact, Server

from app.config import (
    ISSUE_TRACKER_URL,
    MAINTAINER_EMAIL,
    OPENAPI_SERVER_URL,
    REFERENCE_POLICY,
)

# fmt: off
description = (
f"""OpenAPI document: [openapi.json][0]

## Introduction

This document describes the HTTP API to interact with
the DTN Node Registry (DTNNR).

The DTNNR contains information about general characteristics of
Interplanetary Overlay Network (ION) nodes.

While the DTNNR has enough information to generate some parameters for
ION configuration files (mainly bprc(5), ionconfig(5), and ltprc(5)),
the DTNNR is <em>not</em> intended to have enough information
to generate every configuration file that ION uses.

The API is primarily designed to be used by the DTNNR web application
and the ION Config Tool.
Beyond these uses, no guarantees are made about the stability or applicability
of the API.

## Resources

The DTNNR has four main resources: allocators, operators, hosts, and nodes.

### Allocators

Allocators are organizations as described in RFC 9758.
The `allocator_id` property in schemas are equivalent
to the "Allocator Identifier" defined in Section 3.2 of RFC 9758.

### Operators

RFC 9758 does not prescribe how allocators are to assign node numbers.
The DTNNR uses the concept of operators as the main way
for allocating node numbers.
Underneath a given allocator, there may exist multiple operators
which have disjoint sets of allocated node numbers.
A given operator then operates computers which host nodes,
and these nodes must use a node number that is allocated to the operator.

This operator concept is the only policy of assigning node numbers
that is supported by the DTNNR.
Nodes that do not fall under this policy can still be stored in the DTNNR;
they are simply related to an allocator.

### Hosts

Hosts are machines that run instances of ION.
The host resource has two chilren:
* links
* destinations

These children should be viewed "locally" — what links do I (a host)
have access to, and what destinations are locally available on the host?

Links describe any underlying information below the convergence layer (CL).

Destinations describe IP addresses or registered names
that locally resolve to local IP addresses.

### Nodes

Nodes are instances of ION.
The node resource has four children:
* endpoints
* cl protocols
* inducts
* seats

Endpoints, CL protocols, and inducts map onto the eponymous concepts in bprc(5).
Seats are eponymous with seats described in ltprc(5).

The DTNNR cannot say anything meaningful about outgoing information
like outducts or LTP spans.

### Reference

Links can associate with bands and underlying communication services.
These are called reference resources.
The API currently does not have an operation to create new references.
{
'The maintainer is responsible for managing reference resources.'
if REFERENCE_POLICY is None
else REFERENCE_POLICY
}

## Usage

Authentication is currently disabled as the DTNNR is in an experimental state.

The API has CSRF protections for unsafe methods (viz., not `GET`).
Responses to a safe request will have a `Set-Cookie` header
for a session cookie with the name `XSRF-TOKEN`.
Unsafe requests need to send this cookie
and also have a request header named `X-XSRF-TOKEN` with the cookie's value.

The request entity for any operation is limited to 10 MB.
This restriction really only matters for operations which can accept
arrays in the request body
and should be more than enough for any application.
If you really do need requests larger than this,
contact the instance's maintainer for support.

### Pagination

List and query `GET` operations support pagination through
the `max_page_size` and `page_token` query parameters.
If the `GET` request's response has a `prev_page_token` or a `next_page_token`,
then that value can be used
to go to the next page in the previous or next direction, respectively.

### Querying

Querying is planned for the DTNNR's four main resources and reference resources.
Support for filtering and field masks is planned.
At the moment, querying is functionally equivalent to listing.

{
'## Contact'
if MAINTAINER_EMAIL is not None or ISSUE_TRACKER_URL is not None
else ''
}
{
''
if ISSUE_TRACKER_URL is None
else f'''
Issue tracker: [{ISSUE_TRACKER_URL}][iss-tracker]
'''
}

[0]: {'' if OPENAPI_SERVER_URL == '/' else OPENAPI_SERVER_URL}/schema/openapi.json
{'' if ISSUE_TRACKER_URL is None else f'[iss-tracker]: {ISSUE_TRACKER_URL}'}
"""

)
# fmt: on

openapi_config = OpenAPIConfig(
    title='DTN Node Registry API',
    summary='HTTP API to interact with the DTNNR',
    description=description,
    contact=(
        None
        if MAINTAINER_EMAIL is None
        else Contact('maintainer', email=MAINTAINER_EMAIL)
    ),
    servers=[Server(OPENAPI_SERVER_URL)],
    # `version` refers to the version of the OpenAPI Document. This is distinct
    # from the OpenAPI Description (we only have one document so this doesn't
    # matter for us) and the version of the API being described.
    # But this easily confuses people, so just keep this matching with the
    # API version.
    version='0.5.0',
    security=None,  # TODO
    render_plugins=[SwaggerRenderPlugin('latest', path='/')],
)

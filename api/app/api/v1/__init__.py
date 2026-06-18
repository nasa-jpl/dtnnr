from __future__ import annotations

from litestar import Router
from litestar.di import Provide

from app.config import API_V1_PATH

from .allocator.views import allocator_router
from .band.views import band_router
from .cl_protocol.views import cl_protocol_router
from .contact.views import contact_router
from .destination.views import destination_router
from .host.views import host_router
from .induct.views import induct_router
from .link.views import link_router
from .node.views import node_router
from .operator.views import operator_router
from .schemas import PaginatedRequest
from .seat.views import seat_router
from .underlying_communication_service.views import (
    underlying_communication_service_router,
)

api_v1_router = Router(
    path=API_V1_PATH,
    dependencies={
        'paginated_request': Provide(PaginatedRequest, sync_to_thread=True),
    },
    route_handlers=[
        allocator_router,
        band_router,
        cl_protocol_router,
        contact_router,
        destination_router,
        host_router,
        induct_router,
        link_router,
        node_router,
        operator_router,
        seat_router,
        underlying_communication_service_router,
    ],
)

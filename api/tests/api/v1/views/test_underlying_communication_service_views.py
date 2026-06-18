from __future__ import annotations

from typing import TYPE_CHECKING

from app.api.v1.underlying_communication_service.schemas import (
    to_underlying_communication_service_schema as to_schema,
)
from app.config import API_V1_PATH, MAX_PAGE_SIZE
from tests.util import (
    check_invalid_page_token_query,
    check_page_size,
    check_query_request_validation,
    collect_paginated_data,
)

if TYPE_CHECKING:
    from litestar import Litestar
    from litestar.testing import TestClient

    from app.models import UnderlyingCommunicationService

path_prefix = f'{API_V1_PATH}/underlying-communication-services'


def test_query_underlying_communication_services(
    client: TestClient[Litestar],
    underlying_communication_services: list[UnderlyingCommunicationService],
):
    items = collect_paginated_data(client, path_prefix, MAX_PAGE_SIZE)
    for s in underlying_communication_services:
        assert to_schema(s).to_dict() in items


def test_query_underlying_communication_services_pagination(
    client: TestClient[Litestar],
    underlying_communication_services: list[UnderlyingCommunicationService],
):
    items = collect_paginated_data(client, path_prefix, 1)
    for s in underlying_communication_services:
        assert to_schema(s).to_dict() in items

    params = {'max_page_size': 1, 'page_token': 'last'}
    response = client.get(path_prefix, params=params)
    assert response.status_code == 200
    assert len(response.json()['items']) == params['max_page_size']
    assert response.json().get('prev_page_token') is not None
    assert response.json().get('next_page_token') is None
    assert items[-1] == response.json()['items'][0]


def test_query_underlying_communication_services_page_size(
    client: TestClient[Litestar],
    underlying_communication_services_max_and_one: list[UnderlyingCommunicationService],
):
    check_page_size(client, path_prefix)


def test_query_underlying_communication_services_invalid_page_token(
    client: TestClient[Litestar],
    underlying_communication_services: list[UnderlyingCommunicationService],
):
    check_invalid_page_token_query(client, path_prefix)


def test_query_underlying_communication_services_validation(
    client: TestClient[Litestar],
):
    check_query_request_validation(client, path_prefix)

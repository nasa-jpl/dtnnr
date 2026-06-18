from __future__ import annotations

from typing import TYPE_CHECKING

from app.api.v1.band.schemas import to_schema
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

    from app.models import Band

path_prefix = f'{API_V1_PATH}/bands'


def test_query_bands(client: TestClient[Litestar], bands: list[Band]):
    items = collect_paginated_data(client, path_prefix, MAX_PAGE_SIZE)
    for b in bands:
        assert to_schema(b).to_dict() in items


def test_query_bands_pagination(client: TestClient[Litestar], bands: list[Band]):
    items = collect_paginated_data(client, path_prefix, 1)
    for b in bands:
        assert to_schema(b).to_dict() in items

    params = {'max_page_size': 1, 'page_token': 'last'}
    response = client.get(path_prefix, params=params)
    assert response.status_code == 200
    assert len(response.json()['items']) == params['max_page_size']
    assert response.json().get('prev_page_token') is not None
    assert response.json().get('next_page_token') is None
    assert items[-1] == response.json()['items'][0]


def test_query_bands_page_size(
    client: TestClient[Litestar], bands_max_and_one: list[Band]
):
    check_page_size(client, path_prefix)


def test_query_bands_invalid_page_token(
    client: TestClient[Litestar], bands: list[Band]
):
    check_invalid_page_token_query(client, path_prefix)


def test_query_bands_validation(client: TestClient[Litestar]):
    check_query_request_validation(client, path_prefix)

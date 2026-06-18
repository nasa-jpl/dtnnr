from __future__ import annotations

from typing import TYPE_CHECKING

from litestar import Router, get
from litestar.di import Provide

from app.config import API_V1_PATH
from app.problem_details import pagination_400_response_spec

from ..query import create_page_tokens, process_page_size, process_page_token
from ..schemas import (
    GENERIC_QUERY_PARAM_USAGE_NOTE,
    GENERIC_RESPONSE_DESCRIPTION,
    QueryResponse,
)
from .schemas import BandQueryRequest, BandSchema, to_schema
from .service import query

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@get(
    path='/',
    dependencies={'query_request': Provide(BandQueryRequest, sync_to_thread=True)},
    sync_to_thread=True,
    tags=['links', 'reference'],
    summary='Query bands',
    description=(
        f'Search for and fetch bands.<br /><br />{GENERIC_QUERY_PARAM_USAGE_NOTE}'
    ),
    response_description=GENERIC_RESPONSE_DESCRIPTION,
    responses={400: pagination_400_response_spec(f'{API_V1_PATH}/bands')},
)
def query_bands(
    db_session: Session, query_request: BandQueryRequest
) -> QueryResponse[BandSchema]:
    path = '/bands'
    try:
        bookmark = process_page_token(query_request, path)
    except Exception:
        raise
    page = query(db_session, process_page_size(query_request.max_page_size), bookmark)
    return QueryResponse(
        [to_schema(s) for (s,) in page],
        *create_page_tokens(query_request, path, page),
    )


band_router = Router(
    path='/bands',
    route_handlers=[query_bands],
)

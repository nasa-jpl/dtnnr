from __future__ import annotations

from hashlib import md5
from typing import TYPE_CHECKING

import msgspec
from cryptography.fernet import Fernet
from litestar.exceptions import ClientException
from msgspec import UNSET, UnsetType

from app.config import (
    DEFAULT_PAGE_SIZE,
    INVALID_PAGE_TOKEN_MESSAGE,
    MAX_PAGE_SIZE,
    PAGE_TOKEN_KEY,
    PAGE_TOKEN_TTL,
)
from app.schemas import BaseStruct

from .schemas import PaginatedRequest, QueryRequest

if TYPE_CHECKING:
    from sqlakeyset import Page

f = Fernet(PAGE_TOKEN_KEY)


# PageToken should be internal to the application, the API should only
# expose an opaque string as a page token.
# We encrypt the token to enforce opacity, not for security reasons.
# Can use array_like since the JSON is never exposed.
class PageToken(BaseStruct, array_like=True):
    request_hash: str
    bookmark: str | tuple[None, bool]


def hash_request_contents(request: PaginatedRequest | QueryRequest, path: str) -> str:
    if isinstance(request, PaginatedRequest):
        contents = path
    elif isinstance(request, QueryRequest):
        # TODO: disable sorting parameters until I can think of an actual use case
        contents = [request.filter, path]
    return md5(str(contents).encode('utf-8')).hexdigest()


def process_page_token(
    request: PaginatedRequest | QueryRequest, path: str
) -> str | None:
    """Checks if `request.page_token` is a valid page token. Raises an
    exception if invalid. Returns the sqlakeyset bookmark if valid.

    `path` needs to be something unique to a route handler such that
    the page tokens given for one endpoint can't be used at another.
    The path of the endpoint is an obvious candidate, but it can
    really be anything.
    """
    if request.page_token == None:
        return None  # first page
    elif request.page_token == 'last':
        return (None, True)  # last page
    try:
        raw_page_token = f.decrypt(request.page_token, PAGE_TOKEN_TTL)
    except Exception:
        raise ClientException(INVALID_PAGE_TOKEN_MESSAGE)
    page_token = msgspec.json.decode(raw_page_token, type=PageToken)
    if hash_request_contents(request, path) != page_token.request_hash:
        raise ClientException(INVALID_PAGE_TOKEN_MESSAGE)
    return page_token.bookmark


def _create_page_token(
    request: PaginatedRequest | QueryRequest, path: str, bookmark: str
) -> str:
    """Create a page token for a sqlakeyset bookmark."""
    page_token = PageToken(
        request_hash=hash_request_contents(request, path),
        bookmark=bookmark,
    )
    raw_page_token = msgspec.json.encode(page_token)
    return f.encrypt(raw_page_token).decode('utf-8')


def create_page_tokens(
    request: PaginatedRequest | QueryRequest, path: str, page: Page
) -> tuple[str | UnsetType]:
    """Returns a 2-tuple (prev_page_token, next_page_token)."""
    prev_page_token = (
        _create_page_token(request, path, page.paging.bookmark_previous)
        if page.paging.has_previous
        else UNSET
    )
    next_page_token = (
        _create_page_token(request, path, page.paging.bookmark_next)
        if page.paging.has_next
        else UNSET
    )
    return (prev_page_token, next_page_token)


def process_page_size(max_page_size: int) -> int:
    if max_page_size == 0:
        return DEFAULT_PAGE_SIZE
    return min(max_page_size, MAX_PAGE_SIZE)

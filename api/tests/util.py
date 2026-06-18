from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Subquery, literal_column, select
from sqlalchemy.orm import Session

from app.config import DEFAULT_PAGE_SIZE, INVALID_PAGE_TOKEN_MESSAGE, MAX_PAGE_SIZE
from app.models import DeletedRecord

if TYPE_CHECKING:
    from litestar import Litestar
    from litestar.testing import TestClient


def collect_paginated_data(
    client: TestClient[Litestar], url: str, max_page_size: int
) -> list[dict]:
    """Performs repeated requests on paginated endpoints to collect and
    return all `items`.
    """
    items: list[dict] = []
    params = {'max_page_size': max_page_size}
    response = client.get(url, params=params)
    assert response.status_code == 200
    assert len(response.json()['items']) <= params['max_page_size']
    assert response.json().get('prev_page_token') is None
    items.extend(response.json()['items'])

    while response.json().get('next_page_token'):
        params = {
            'max_page_size': max_page_size,
            'page_token': response.json().get('next_page_token'),
        }
        response = client.get(url, params=params)
        assert response.status_code == 200
        assert len(response.json()['items']) <= params['max_page_size']
        assert response.json().get('prev_page_token') is not None
        items.extend(response.json()['items'])
    assert response.json().get('next_page_token') is None

    return items


def check_page_size(client: TestClient[Litestar], url: str) -> None:
    """Checks if default page size is used when no `max_page_size`
    is used and when `max_page_size` is 0. Checks if `max_page_size`
    values above the max page size are coerced down.

    Pass the base `url` without query parameters.
    """
    # Default max_page_size matches envvar
    response = client.get(url)
    assert response.status_code == 200
    assert len(response.json()['items']) == DEFAULT_PAGE_SIZE

    # max_page_size = 0 matches default page size
    params = {'max_page_size': 0}
    assert response.status_code == 200
    assert len(response.json()['items']) == DEFAULT_PAGE_SIZE

    # Excessive values are coerced down
    params = {'max_page_size': MAX_PAGE_SIZE + 1}
    response = client.get(url, params=params)
    assert response.status_code == 200
    assert len(response.json()['items']) == MAX_PAGE_SIZE
    assert response.json().get('next_page_token') is not None


def _check_invalid_page_token(client: TestClient[Litestar], url: str) -> None:
    """Checks that the following are invalid:
    - `page_token=blah`
    - `page_token=`
    - `page_token=null`
    """
    for params in [
        {'page_token': 'blah'},
        {'page_token': None},  # ?page_token=
        {'page_token': 'null'},  # ?page_token=null
    ]:
        response = client.get(url, params=params)
        assert response.status_code == 400
        assert INVALID_PAGE_TOKEN_MESSAGE in response.json()['detail']


def check_invalid_page_token_query(client: TestClient[Litestar], url: str) -> None:
    """Checks that the following are invalid:
    - `page_token=blah`
    - `page_token=`
    - `page_token=null`
    - Changing `filter` in a subsequent query while using the
      `next_page_token` from a previous successful query

    Endpoints check if the resource exists before validating that the
    request hasn't changed, so ensure that `url` refers to an existing
    resource.
    """
    _check_invalid_page_token(client, url)

    params = {'max_page_size': 1}
    response = client.get(url, params=params)
    assert response.status_code == 200

    # Using token for different request
    params = {
        'filter': 'abc',
        'max_page_size': 1,
        'page_token': response.json().get('next_page_token'),
    }
    response = client.get(url, params=params)
    assert response.status_code == 400
    assert INVALID_PAGE_TOKEN_MESSAGE in response.json()['detail']


def check_invalid_page_token_different_url(
    client: TestClient[Litestar],
    url_1: str,
    url_2: str,
) -> None:
    """Checks that the following are invalid:
    - `page_token=blah`
    - `page_token=`
    - `page_token=null`
    - Using the `next_page_token` from a successful request at `url_1`
      at `url_2`

    Endpoints check if the resource exists before validating that the
    request hasn't changed, so ensure that `url_1` and `url_2` both
    point to existing and discrete resources.
    """
    _check_invalid_page_token(client, url_1)

    params = {'max_page_size': 1}
    response = client.get(url_1, params=params)
    assert response.status_code == 200

    # Using token for different request
    params = {
        'max_page_size': 1,
        'page_token': response.json().get('next_page_token'),
    }
    response = client.get(url_2, params=params)
    assert response.status_code == 400
    assert INVALID_PAGE_TOKEN_MESSAGE in response.json()['detail']


def check_paginated_request_validation(client: TestClient[Litestar], url: str):
    """Checks validation for `PaginatedRequest` query parameters."""
    params = {'max_page_size': -1}
    response = client.get(url, params=params)
    assert response.status_code == 400
    assert response.json()['extra'] == [
        {'message': 'Expected `int` >= 0', 'key': 'max_page_size', 'source': 'query'}
    ]

    for params in [
        # `?x=` is assigning the empty string '' to x
        # `page_token` will pass Litestar's validation, but will fail our token
        # check since a blank string isn't a valid token
        {
            'max_page_size': None,
            'page_token': None,  # Ok
        },
        # `?x=null` is assigning the string 'null' to x
        {
            'max_page_size': 'null',
            'page_token': 'null',  # Ok
        },
    ]:
        response = client.get(url, params=params)
        assert response.status_code == 400
        assert response.json()['extra'] == [
            {
                'message': 'Expected `int`, got `str`',
                'key': 'max_page_size',
                'source': 'query',
            }
        ]


def check_query_request_validation(client: TestClient[Litestar], url: str):
    """Checks validation for `QueryRequest` query parameters."""
    # TODO: disable sorting parameters until I can think of an actual use case
    params = {
        'fields': 'blah',
        # 'sort': 'blah',
        # 'direction': 'blah',
        'max_page_size': -1,
    }
    response = client.get(url, params=params)
    assert response.status_code == 400
    assert response.json()['extra'] == [
        {'message': "Invalid enum value 'blah'", 'key': 'fields', 'source': 'query'},
        # {'message': "Invalid enum value 'blah'", 'key': 'sort', 'source': 'query'},
        # {'message': "Invalid enum value 'blah'", 'key': 'direction', 'source': 'query'},
        {'message': 'Expected `int` >= 0', 'key': 'max_page_size', 'source': 'query'},
    ]

    # `?x=` is assigning the empty string '' to x
    # Apart from `filter` and `page_token`, the empty string fails validation
    # for all parameters. (`page_token` passes Litestar's validation, but will
    # fail our token check since a blank string isn't a valid token)
    params = {
        'filter': None,  # Ok
        'fields': None,
        # 'sort': None,
        # 'direction': None,
        'max_page_size': None,
        'page_token': None,  # Ok
    }
    response = client.get(url, params=params)
    assert response.status_code == 400
    assert response.json()['extra'] == [
        {'message': "Invalid enum value ''", 'key': 'fields', 'source': 'query'},
        # {'message': "Invalid enum value ''", 'key': 'sort', 'source': 'query'},
        # {'message': "Invalid enum value ''", 'key': 'direction', 'source': 'query'},
        {
            'message': 'Expected `int`, got `str`',
            'key': 'max_page_size',
            'source': 'query',
        },
    ]

    # `?x=null` is assigning the string 'null' to x
    params = {
        'filter': 'null',  # Ok
        'fields': 'null',
        # 'sort': 'null',
        # 'direction': 'null',
        'max_page_size': 'null',
        'page_token': 'null',  # Ok
    }
    response = client.get(url, params=params)
    assert response.status_code == 400
    assert response.json()['extra'] == [
        {'message': "Invalid enum value 'null'", 'key': 'fields', 'source': 'query'},
        # {'message': "Invalid enum value 'null'", 'key': 'sort', 'source': 'query'},
        # {'message': "Invalid enum value 'null'", 'key': 'direction', 'source': 'query'},
        {
            'message': 'Expected `int`, got `str`',
            'key': 'max_page_size',
            'source': 'query',
        },
    ]


def get_as_jsonb(session: Session, subq: Subquery):
    """Performs `SELECT to_jsonb(rows) FROM rows` where `rows` is the
    given `subq` as a CTE, and then returns the jsonb.
    """
    stmt = select(literal_column('to_jsonb(rows)').label('res')).select_from(
        subq.cte('rows')
    )
    return session.execute(stmt).first().res


def get_most_recently_deleted_record(session: Session, data) -> DeletedRecord:
    """Returns the most recently deleted record with data that is equal
    to `data`.
    `data` should be the result from calling get_as_jsonb.
    """
    return session.scalar(
        select(DeletedRecord)
        .where(DeletedRecord.data == data)
        .order_by(
            DeletedRecord.deleted_at.desc(), DeletedRecord.deleted_record_id.desc()
        )
        .limit(1)
    )


def check_deleted_time(deleted_record: DeletedRecord, target_time, delta):
    """Returns true if the `deleted_at` time for `deleted_record` is
    within `delta` of `target_time`.
    """
    lower = target_time - delta
    upper = target_time + delta
    deleted_at = deleted_record.deleted_at
    return deleted_at >= lower and deleted_at <= upper


def verify_soft_deletion(session: Session, data):
    """Returns true if a record with `data` was recently deleted."""
    deleted_record = get_most_recently_deleted_record(session, data)
    if not deleted_record:
        return False
    return check_deleted_time(
        deleted_record,
        target_time=datetime.now(timezone.utc),
        delta=timedelta(seconds=1),
    )

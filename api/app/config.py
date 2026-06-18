from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import pathlib
import sys
from dataclasses import dataclass
from io import StringIO

import litestar.concurrency
import litestar.middleware
import litestar.routes
import structlog
from litestar.config.compression import CompressionConfig
from litestar.config.cors import CORSConfig
from litestar.config.csrf import CSRFConfig
from litestar.exceptions import ClientException
from litestar.logging.config import (
    LoggingConfig,
    StructlogEventFilter,
    StructLoggingConfig,
)
from litestar.middleware.logging import LoggingMiddlewareConfig
from litestar.plugins.structlog import StructlogConfig
from sqlalchemy import URL

SECRET_NAMES = {'SECRET_KEY', 'PAGE_TOKEN_KEY', 'DATABASE_PASSWORD'}
MISSING = object()


def get_config(name: str, default=MISSING):
    """Retrieve config from env or secret file.

    Keep `default` as None if a value is required.
    Secret values are always required.
    """
    secret_file_path = os.getenv(f'{name}_FILE')
    if secret_file_path:
        if os.path.isfile(secret_file_path):
            with open(secret_file_path, 'r') as f:
                return f.read().strip()
        raise RuntimeError(f'{secret_file_path} file not found')

    if name in SECRET_NAMES:
        if os.getenv(name):
            raise RuntimeError(
                f'Do not set {name} as an envvar.'
                f' Use the {name}_FILE envvar to refer to a file'
                ' with the value you want.'
            )
        raise RuntimeError(f'{name}_FILE envvar is required')

    value = os.getenv(name)
    if value is not None:
        return value
    if default is not MISSING:
        return default
    raise RuntimeError(f'Missing {name} or {name}_FILE envvar')


# Generate a nice key using secrets.token_urlsafe()
SECRET_KEY = get_config('SECRET_KEY')
# Generate with cryptography.fernet.Fernet.generate_key()
PAGE_TOKEN_KEY = get_config('PAGE_TOKEN_KEY')
# AIP-158 says 3 days is a good rule of thumb for expiring page tokens
PAGE_TOKEN_TTL = int(get_config('PAGE_TOKEN_TTL', 86400 * 3))
INVALID_PAGE_TOKEN_MESSAGE = get_config(
    'INVALID_PAGE_TOKEN_MESSAGE', 'Invalid page token'
)

DEFAULT_PAGE_SIZE = int(get_config('DEFAULT_PAGE_SIZE', 10))
MAX_PAGE_SIZE = int(get_config('MAX_PAGE_SIZE', 1000))

REFERENCE_POLICY = get_config('REFERENCE_POLICY', None)
ISSUE_TRACKER_URL = get_config('ISSUE_TRACKER_URL', None)
MAINTAINER_EMAIL = get_config('MAINTAINER_EMAIL', None)
OPENAPI_SERVER_URL = get_config('OPENAPI_SERVER_URL', '/')

# Do not have a trailing '/'
API_V1_PATH = get_config('API_V1_PATH', '')

DATABASE_HOSTNAME = get_config('DATABASE_HOSTNAME')
DATABASE_USER = get_config('DATABASE_USER')
DATABASE_PASSWORD = get_config('DATABASE_PASSWORD')
DATABASE_NAME = get_config('DATABASE_NAME')
DATABASE_PORT = get_config('DATABASE_PORT')
SQLALCHEMY_DATABASE_URI = URL.create(
    'postgresql+psycopg',
    username=DATABASE_USER,
    password=DATABASE_PASSWORD,
    host=DATABASE_HOSTNAME,
    port=DATABASE_PORT,
    database=DATABASE_NAME,
)

ALEMBIC_INI_PATH = get_config(
    'ALEMBIC_INI_PATH',
    default=f'{pathlib.Path(__file__).parent.resolve().parent}/alembic.ini',
)

ALLOWED_CORS_ORIGIN: list[str] | str = get_config('ALLOWED_CORS_ORIGIN')
# https://github.com/litestar-org/litestar-fullstack/blob/e4dd330917e3c500e73f68a6b4f9d1d2f71cc75f/src/app/config/base.py#L409
# Check if the ALLOWED_CORS_ORIGINS is a string.
if isinstance(ALLOWED_CORS_ORIGIN, str):
    # Check if the string starts with "[" and "]", indicating a list.
    if ALLOWED_CORS_ORIGIN.startswith('[') and ALLOWED_CORS_ORIGIN.endswith(']'):
        try:
            # Safely evaluate the string as a Python list.
            ALLOWED_CORS_ORIGIN = json.loads(ALLOWED_CORS_ORIGIN)
        except SyntaxError, ValueError:
            # Handle potential errors if the string is not a valid Python literal.
            msg = 'ALLOWED_CORS_ORIGIN is not a valid list representation.'
            raise ValueError(msg) from None
    else:
        # Split the string by commas into a list if it is not meant to be a list
        # representation.
        ALLOWED_CORS_ORIGIN = [host.strip() for host in ALLOWED_CORS_ORIGIN.split(',')]
cors_config = CORSConfig(allow_origins=ALLOWED_CORS_ORIGIN)

compress_config = CompressionConfig(backend='gzip', gzip_compress_level=9)

csrf_config = CSRFConfig(
    secret=SECRET_KEY, cookie_name='XSRF-TOKEN', header_name='X-XSRF-TOKEN'
)


def remove_module_pathname_add_logger(
    _, __, event_dict: structlog.typing.EventDict
) -> structlog.typing.EventDict:
    """Removes 'module' and 'pathname' from the `event_dict` and adds
    `logger = 'litestar'` if the event comes from Litestar, otherwise
    adds `logger = module`.

    This is our workaround to `structlog.stdlib.add_logger_name` not
    working with `WriteLoggerFactory` (Litestar's default logger
    factory). We can't use that processor because `WriteLogger` doesn't
    have a `name` field.
    """
    module = event_dict.pop('module')
    pathname = event_dict.pop('pathname')
    if pathname is not None:
        if 'litestar' in pathname:
            event_dict['logger'] = 'litestar'
            event_dict.pop('filename')
            event_dict.pop('func_name')
        elif module is not None:
            event_dict['logger'] = module
    return event_dict


def hide_client_exception_trace(_, __, event_dict: structlog.typing.EventDict):
    """Processor to hide traceback for `ClientException`."""
    # We want to always log exceptions, but Litestar's approach to raising
    # 4xx status codes is by raising an exception. Traceback for these
    # errors aren't interesting because we expect them.
    if event_dict.get('exc_info', False) != False and isinstance(
        sys.exception(), ClientException
    ):
        event_dict.pop('exc_info')
        # ClientException.__str__ without extra args is
        # "{status_code}: {detail}"
        # We're already using structured logging, so we store those values as
        # separate keys instead of just one str(sys.exception()) value.
        if 'status_code' not in event_dict:
            event_dict['status_code'] = sys.exception().status_code
        if 'detail' not in event_dict:
            event_dict['detail'] = str(sys.exception().detail)
    return event_dict


shared_processors = [
    structlog.contextvars.merge_contextvars,
    hide_client_exception_trace,
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt='iso'),
    # Don't think ExtraAdder() has any effect for either structlog or stdlib,
    # but Litestar's default stdlib processors uses it, so whatever
    structlog.stdlib.ExtraAdder(),
    # Hide 'message' since it pointlessly repeats the message.
    # Litestar's default stdlib processors hides 'color_message'
    StructlogEventFilter(['color_message', 'message']),
]


@dataclass
class CustomColumnFormatter:
    """Formatter to use different colors for HTTP status codes."""

    def __call__(self, key: str, value: object) -> str:
        sio = StringIO()

        key_style = structlog.dev.CYAN
        reset_style = structlog.dev.RESET_ALL
        value_style = structlog.dev.MAGENTA
        if key == 'status_code':
            if 200 <= value <= 299:
                value_style = structlog.dev.GREEN
            elif 300 <= value <= 399:
                value_style = structlog.dev.YELLOW
            elif 400 <= value <= 599:
                value_style = structlog.dev.RED

        sio.write(key_style)
        sio.write(key)
        sio.write(reset_style)
        sio.write('=')
        sio.write(value_style)
        sio.write(str(value))
        sio.write(reset_style)
        return sio.getvalue()


console_renderer = structlog.dev.ConsoleRenderer(
    colors=True,
    # Exceptions in application code like `1/0` use this formatter, regardless
    # if we imported structlog or stdlib logging for getLogger.
    exception_formatter=structlog.dev.RichTracebackFormatter(
        # Rich's Traceback defines max_frames as max(4, max_frames), so we
        # always have at least 4 frames.
        # This is annoying with show_locals since the early frames are Litestar
        # frames with a lot of large local objects. My workaround is to suppress
        # the traceback of the Litestar exceptions (you still see the function
        # names in the error, just not the code block and locals).
        max_frames=4,
        show_locals=True,
        suppress=[
            litestar.middleware,
            litestar.routes,
            litestar.concurrency,
            concurrent.futures,
        ],
        width=80,
    ),
)
console_renderer._default_column_formatter = CustomColumnFormatter()


log_config = StructlogConfig(
    structlog_logging_config=StructLoggingConfig(
        log_exceptions='always',
        # `processors` only applies for structlog, not stdlib logging
        processors=shared_processors
        + [
            structlog.processors.CallsiteParameterAdder(
                [
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.MODULE,
                    structlog.processors.CallsiteParameter.PATHNAME,
                ]
            ),
            # Delete 'module' and 'pathname' and add 'logger'.
            # We can't use structlog.stdlib.add_logger_name because the default
            # logger factory (WriteLoggerFactory) nor PrintLoggerFactory have
            # a `name` field.
            # Setting logger_factory to LoggerFactory() will make the structlog
            # log message (already formatted) be logged again by stdlib as the
            # `message` value, so we'll stick with WriteLoggerFactory which
            # hasn't caused any problems so far.
            remove_module_pathname_add_logger,
            console_renderer,
        ],
        # The log level set on the root logger doesn't affect structlog logs
        # since structlog is not passing the logs to stdlib logging. We
        # need to create a bound logger and use the same level as the root
        # logger below.
        # https://github.com/litestar-org/litestar/issues/3424
        wrapper_class=structlog.make_filtering_bound_logger(
            int(get_config('LOG_LEVEL', logging.INFO))
        ),
        # Was running into `TypeError: can only concatenate str (not "bytes") to
        # str` upon test startup. The problem is we use ConsoleRenderer which is
        # using strings while the default logger factory uses bytes. Workaround
        # is to use a logger factory that uses strings.
        # https://github.com/litestar-org/litestar/issues/2151
        logger_factory=structlog.PrintLoggerFactory(),
        # This config only affects the logs using stdlib logging
        standard_lib_logging_config=LoggingConfig(
            root={
                'level': int(get_config('LOG_LEVEL', logging.INFO)),
                'handlers': ['queue_listener'],
            },
            formatters={
                'standard': {
                    '()': structlog.stdlib.ProcessorFormatter,
                    'foreign_pre_chain': shared_processors,
                    'processors': [
                        # We can use add_logger_name since stdlib logging is not
                        # using WriteLoggerFactory
                        structlog.stdlib.add_logger_name,
                        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                        structlog.dev.ConsoleRenderer(
                            # Note: for debugging, colors=False is good for
                            # seeing what came from structlog and what came from
                            # stdlib logger
                            colors=True,
                            # Reasons above don't apply here since Litestar logs
                            # don't go through stdlib logging. I still use
                            # show_locals=True in case it may be helpful.
                            exception_formatter=structlog.dev.RichTracebackFormatter(
                                max_frames=4, show_locals=True, width=80
                            ),
                        ),
                    ],
                }
            },
            loggers={
                # We don't use uvicorn in production. Can use these uvicorn
                # settings to supppress some uvicorn logs during development.
                # 'uvicorn.access': {
                #     'propagate': False,
                #     'level': int(get_config('UVICORN_ACCESS_LEVEL', logging.INFO)),
                #     'handlers': ['queue_listener'],
                # },
                # 'uvicorn.error': {
                #     'propagate': False,
                #     'level': int(get_config('UVICORN_ERROR_LEVEL', logging.INFO)),
                #     'handlers': ['queue_listener'],
                # },
                # Granian (and uvicorn) logs are pretty much the same as
                # Litestar's middleware, except that the middleware splits the
                # request and response, so it's possible to not know which request
                # a response is for. If you enable Granian access logs though,
                # they will be outputted with the same time as the Litestar
                # response logs.
                '_granian': {
                    'propagate': False,
                    'level': int(get_config('GRANIAN_GENERIC_LEVEL', logging.INFO)),
                    'handlers': ['queue_listener'],
                },
                # GRANIAN_LOG_ACCESS_FMT is meant for formatting the string that
                # gets logged, not for the actual log format which is just `%(message)s`,
                # so you want to mess with that env var or pass it in --access-log-fmt
                # %(addr)s - "%(method)s %(path)s %(protocol)s %(status)d %(dt_ms).3f"
                'granian.access': {
                    'propagate': False,
                    'level': int(get_config('GRANIAN_ACCESS_LEVEL', logging.INFO)),
                    'handlers': ['queue_listener'],
                },
                'sqlalchemy.engine': {
                    'propagate': False,
                    # logging.INFO is equivalent to echo=True on create_engine.echo
                    'level': int(get_config('SQLALCHEMY_ENGINE_LEVEL', logging.WARN)),
                    'handlers': ['queue_listener'],
                },
                'sqlalchemy.pool': {
                    'propagate': False,
                    # logging.INFO is equivalent to pool_echo=True on
                    # create_engine.pool_echo
                    'level': int(get_config('SQLALCHEMY_POOL_LEVEL', logging.WARN)),
                    'handlers': ['queue_listener'],
                },
                'alembic': {
                    'propagate': False,
                    'level': int(get_config('ALEMBIC_LOG_LEVEL', logging.INFO)),
                    'handlers': ['queue_listener'],
                },
            },
        ),
    ),
    middleware_logging_config=LoggingMiddlewareConfig(
        # TODO: If you want to include 'body', need to filter out sensitive info
        # Not sure best way to do this, maybe add a processor that will check if `body`
        # is available, then convert to dict if possible, and then make password
        # an empty string? We can deal with this once we get to authn.
        request_log_fields=['method', 'path', 'query', 'body', 'client'],
        response_log_fields=['status_code'],
        request_cookies_to_obfuscate={'session', 'XSRF-TOKEN'},
        request_headers_to_obfuscate={
            'Authorization',
            'X-API-KEY',
            'X-XSRF-TOKEN',
            'cookie',
        },
    ),
)

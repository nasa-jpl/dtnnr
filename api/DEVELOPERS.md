# Development information

This document aims to introduce the backend's codebase
to enable developers to contribute.

## Overview

The project is written in Python.

[PostgreSQL] is the project's DBMS,
and all database interactions are done through [SQLAlchemy].
We can't use SQLAlchemy's default Postgres driver, Psycopg 2,
because [it doesn't support][psycopg-iss-1485] Postgres' [multirange] data type.
Instead, we use [Psycopg 3].
Migrations are handled with [Alembic].

The HTTP API uses [Litestar] as its framework.
Additional tools include [msgspec] for serialization and validation,
[structlog] for logging, and [sqlakeyset] for keyset-based pagination.
Regression tests use [pytest] as its framework
and [factory_boy] for generating database records in tests.

[PostgreSQL]: https://www.postgresql.org/
[SQLAlchemy]: https://www.sqlalchemy.org/
[psycopg-iss-1485]: https://github.com/psycopg/psycopg2/issues/1485
[multirange]: https://www.postgresql.org/docs/17/rangetypes.html
[Psycopg 3]: https://www.psycopg.org/psycopg3/
[Alembic]: https://alembic.sqlalchemy.org/en/latest/
[Litestar]: https://litestar.dev/
[msgspec]: https://jcristharif.com/msgspec/index.html
[structlog]: https://www.structlog.org/en/stable/
[sqlakeyset]: https://sqlakeyset.readthedocs.io/en/latest/
[pytest]: https://docs.pytest.org/en/stable/
[factory_boy]: https://factoryboy.readthedocs.io/en/stable/

## Database schema

The database has four main tables: allocators, operators, hosts, and nodes.
Other tables should be seen as children or supporting these main tables.

### Allocators and operators

The `allocator` table contains records which use the Allocator Identifiers
from the "'ipn' Scheme URI Allocator Identifiers registry"
as proposed in [Section 9.1 of RFC 9758](https://datatracker.ietf.org/doc/html/rfc9758#name-ipn-scheme-uri-allocator-id).

Per RFC 9758, an allocator assigns node numbers according to its own policies.
Other than ensuring that the node numbers it allocates are unique,
an allocator doesn't need to coordinate its actions with other allocators.

One way to allocate node numbers is through an "operator policy".
Underneath a given allocator, there may exist multiple operators
which all have disjoint sets of allocated node numbers.
A given operator then operates computers which host nodes,
and the nodes on these computers must use a node number that was allocated
to the operator.
Such an operator is represented by a record in the `operator` table.

This operator policy is the only specific allocator policy modeled
in the database.
Other nodes are simply related to their allocator.
That is to say, given a `node` record, the database only allows
two possible node number policies:

* `allocator` -> `node`
* `allocator` -> `operator` -> `node`

### Hosts and nodes

A `host` record represents a machine that can run an instance of ION.
An ION instance is represented by a `node` record.
One machine may host multiple nodes, and the database needs to be aware
of nodes whose hosts are unknown.

While information associated with `node` is meant to map onto concepts
in ION's configuration files,
`host`'s associated information is lower level and not directly involved
in configuration files.

Note that the data related to `host` and `node` should be viewed "locally"
without knowledge of other hosts or nodes.
The database should not have enough data such that you can create a network
of hosts or nodes.

#### Host children

`host` has two children, `link` and `destination`.

`link` is meant to describe anything meaningful below the convergence layer.
`link` uses a table-per-type inheritance design where typed tables
can store more specific information for a link.
E.g., `link_rf` can keep track of what radio band a link uses.
Any information not captured by a typed table is handled by
`link`'s M:N relationship with `underlying_communication_service`.
Expect to see information like "UDP", "Encapsulation Packet Protocol",
and "Unified Space Data Link Protocol" in the latter.
Each service stores both its full `underlying_communication_service_name`
and a compact `underlying_communication_service_abbreviation` used by the UI.

Note that since CL protocols can be in varying layers in protocol layer stacks,
expect to see some protocols in `underlying_communication_service` to also appear
in `cl_protocol` (described in [Node children](#node-children)).

`destination` stores local IP addresses or names in a registry
(e.g., DNS or a hosts file) that resolve to local IP addresses
from the host's perspective.
`destination` is not meant to keep track of IP addresses that are remote
from the host;
it should only refer to IP addresses that the host uses for receiving.

#### Node children

`node` has multiple children: endpoints (`endpoint_ipn` or `endpoint_imc`),
`cl_protocol`, `induct`, and `seat`.

`node` has information that directly maps onto parameters in bprc(5)
(`node_number` and `allocator_id`)
and ionconfig(5) (`sdr_config_flags`, `wm_size`, `sdr_wm_size`, and `heap_words`).
Since `node` is the most important table in the database,
it also has `created_at` and `modified_at` timestamp columns.
Triggers will update `node.modified_at` when changes are made to a node
or its children.

The endpoint children, `cl_protocol`, and `induct` all map
onto bprc(5) parameters.

There is no `endpoint_dtn` because the "dtn" URI is not planned for use in space.

`induct` uses a table-per-type inheritance design where typed tables
represent inducts whose duct name can be fully constructed from the columns
of the typed table.
`induct`'s design is quite messy because it has to support custom CLI commands
which can have arbitrary duct name formats
while preventing users from inputting bad data that will fail for the CLIs
that ION comes with.

`induct` has a M:N relationship with `link` when the `induct` is on a `node`
that is on a `host`.
This relationship is only allowed when the induct does not use LTP.

LTP inducts receive their bundles from seats.
The `seat` table maps onto the ltprc(5) parameter of the same name.
`seat` uses a table-per-type inheritance design where typed tables
represent seats whose LSI command can be fully constructed from the columns
of the typed table.

`seat` has a M:N relationship with `link`,
and `seat` has a M:N relationship with `induct` if the induct is an LTP induct.
Since seats necessarily operate below the convergence layer,
seats rely on the relationship with `link` to describe details
beyond the LSI command.

Notice that `induct` and `seat` records can be related to `host` children.
The database handles hostless nodes by making `node.host_id` nullable.
Convoluted triggers are needed to ensure node children can only
refer to host children of the node's host
and that no host children are referenced when a node is hostless.

### Operators and hosts

The schema is complicated by the need to model

* Operators having control over both hosts and nodes
* The ability for nodes to associate with hosts
* Hosts that are not under an operator
* Nodes that are not associated with a host

Since allocators are a new concept and all previously existing nodes
are under the Default Allocator,
it's likely that operators in the near future will manage a mix
of hosts with nodes that are under the Default Allocator
and another allocator, with the operator under the latter.
The `operator` cannot directly associate with the `node`
through `node.operator_id` because that violates the restriction
that `operator.allocator_id = node.allocator_id`.
If the node is on a host, then the host can be under the operator
with `host.operator_id`, and the operator can "own" the node
indirectly via the host.

However, it does not make sense for operator A to manage hosts with nodes
where some of the nodes are under operator B.
Even if operator B is under the same allocator as operator A,
this is still mistaken since the nodes have node numbers allocated to operator B,
not to operator A.

In summary,

* Nodes with null `operator_id` can be on any host, regardless of whether
  the host is under an operator
* Nodes with a non-null `operator_id` can only be on hosts that have the same
  `operator_id`

### Points of contact

Points of contact store contact information for the owners of `allocator`,
`operator`, `host`, and `node` records.
`contact` has a M:N relationship with each of the four main tables.

Do not confuse points of contact with ION's concept of contacts.
These have nothing to do with each other.

### Deleted records

Triggers on all tables will store deleted records in `deleted_record`.
This is **not** an archiving tool.
The DTNNR is not a temporal database where we know when data was valid/effective
and when it was written.
This table is just a log of records that were deleted;
do not rely on it for anything more than that.

If you want to archive information,
perform backups regularly with tools like [pg_dump].

[pg_dump]: https://www.postgresql.org/docs/current/app-pgdump.html

## Application

An API operation is created with service functions, schemas, and view functions.

Service functions use SQLAlchemy to perform some interaction with the database.

Schemas are msgspec `Struct`s which are used for validating requests
and for serializing data to create representations.

View functions are registered with a Litestar router.
They handle an HTTP request at a particular path.
View functions that need to process request data rely on schemas
to validate the data.
View functions should exhaustively check for client errors
before performing the main operation through a service function.
If the request should have a response with data,
an instance of a schema is created and returned.

### OpenAPI documentation

Frameworks like Litestar have you program first
and then generate OpenAPI documentation
rather than using documentation to generate code.
It's hard to translate between Python and OpenAPI,
so the generated documentation is usually lacking or inaccurate.
Strive to correct the documentation to be as accurate as possible.
[app/schemas.py](app/schemas.py) contains utilities that are used in schemas
and view functions to improve the generated documentation.

Litestar has multiple OpenAPI UI plugins.
Swagger UI is not flawless (as of v5.27.0, it does not use BigInt
to handle unsafe numbers), but it has the least amount of problems
compared to the other UI plugins.

## Regression tests

Factories for generating database records are defined in [factories.py](tests/factories.py).
Pytest fixtures are defined in [conftest.py][conftest].

Tests are divided into [service tests](tests/api/v1/service)
and [views tests](tests/api/v1/views).
Service tests are usually not exhaustive
because API operations should only invoke the service functions through views,
so the view functions and their tests must be exhaustive.
Especially for views tests, try to separate tests by their use case.
It can be hard to follow when only one test function handles all the test cases
for a view function.

[test_database.py](tests/test_database.py) is mostly a sanity check file.
Historically, tests were added to this file when making changes
to the database schema so that the tests didn't have to be manually performed.

## Contributing

### Project layout

Condensed view of the source tree:

```
.
├── alembic
│   ├── env.py  # Migration functions
│   └── script.py.mako
├── alembic.ini  # Alembic configuration
├── app
│   ├── api
│   │   └── v1
│   │       │  # All directories have a "schemas", "service", and "views",
│   │       │  # only allocator's is shown for illustration
│   │       ├── allocator
│   │       │   ├── schemas.py
│   │       │   ├── service.py
│   │       │   └── views.py
│   │       ├── band
│   │       │   └── ...
│   │       ├── cl_protocol
│   │       │   └── ...
│   │       ├── contact
│   │       │   └── ...
│   │       ├── destination
│   │       │   └── ...
│   │       ├── endpoint
│   │       │   └── ...
│   │       ├── host
│   │       │   └── ...
│   │       ├── induct
│   │       │   └── ...
│   │       ├── link
│   │       │   └── ...
│   │       ├── node
│   │       │   └── ...
│   │       ├── operator
│   │       │   └── ...
│   │       ├── seat
│   │       │   └── ...
│   │       ├── underlying_communication_service
│   │       │   └── ...
│   │       ├── query.py  # Query / pagination processor
│   │       ├── schemas.py  # Query / pagination schemas
│   │       └── __init__.py  # Litestar router
│   ├── asgi.py  # Litestar application
│   ├── config.py  # Env vars, dependency setup
│   ├── database.py  # SQLAlchemy setup
│   ├── fields.py  # Constants for max value of fields
│   ├── models.py  # Database schema
│   ├── openapi.py  # OpenAPI setup
│   ├── problem_details.py  # Error handlers
│   ├── schemas.py  # Utils for better OpenAPI docs
│   └── util.py  # SQL service functions also used in tests
└── tests
    ├── api
    │   └── v1
    │       ├── service
    │       │   │  # One test_x_service.py file per service file
    │       │   ├── test_allocator_service.py
    │       │   └── ...
    │       └── views
    │           │  # One test_x_views.py file per views file
    │           ├── test_allocator_views.py
    │           ├── ...
    │           │  # Contact views for allocators, operators, hosts, and nodes
    │           │  # use the same code, so it's handled in one file
    │           └── test_resource_contact_views.py
    ├── conftest.py  # Test setup/teardown, fixtures
    ├── database.py  # SQLAlchemy setup for tests
    ├── factories.py  # Factories to mock records
    ├── test_database.py  # Sanity-check tests
    └── util.py  # Utilities only meant for tests
```

### Contributing guidelines

* Format your code and sort your imports with `ruff`:

  ```sh
  uv run ruff format
  uv run ruff check --select I --fix
  ```

* New API operations need to have exhaustive views tests
* Commits should rarely be pushed directly to `main`.
  A PR should generally be created for any change.
  Rebasing onto `main` is preferred over merging.
  * Separate logical changes into separate commits.
  * It's okay for a commit to break tests as long as it says that it does so.
    The PR as a whole should not be accepted until all tests pass.
  * Keep the subject line short, ideally in a 63 character limit.
    Limit the body to 72 columns.

## Miscellaneous

### Populating with fake data

The records created by factory_boy are normally removed after each test,
and the test database is dropped after a pytest session.
The idea here is to modify the test configuration to keep this data.

In [tests/conftest.py][conftest], change the name of the database to be created
in a pytest session.
E.g., replace `dtnnr_test` with `dtnnr_fake_data`:

```diff
-os.environ['DATABASE_NAME'] = 'dtnnr_test'
+os.environ['DATABASE_NAME'] = 'dtnnr_fake_data'
```

In [tests/conftest.py][conftest], within the `db()` function
which creates and drops the database created for the pytest session,
comment out the `drop_database()` call after the `yield` statement.

```diff
yield

-drop_database(SQLALCHEMY_DATABASE_URI)
+# drop_database(SQLALCHEMY_DATABASE_URI)
```

This call drops the database after the tests are done,
so by commenting it out, we keep the database.

In [tests/conftest.py][conftest], within the `session()` function
which provides an SQLAlchemy session for a test,
comment out `cleanup(session)` and the second call to `session.rollback()`.

```diff
@pytest.fixture(scope='function', autouse=True)
def session(db) -> Generator[Session, None]:
    session = scoped_session_for_testing()
    yield session
    # .rollback() in case of PendingRollbackError
    session.rollback()
-    cleanup(session)
-    session.rollback()
+    # cleanup(session)
+    # session.rollback()
    scoped_session_for_testing.remove()
```

Normally, after one test function is completed,
`cleanup()` is used to delete the records that were created
during that test function's run.
So when we comment it out, the fake data we generated won't be deleted.

Now run all the tests:

```sh
docker compose run --rm api pytest
```

Expect to see several failures and errors.
Some tests are written with the assumption that there aren't any records
in the database except for the fixtures that the test uses.

In your `.env` file, change `DATABASE_NAME` to the name of the database
we just created.
E.g., using the example above, we use

```sh
DATABASE_NAME=dtnnr_fake_data
```

Restart the application to pick up the application change:

```sh
docker compose up -d
```

The database with fake data is now used by the application.

After you verified that the fake data is there,
you should go back and undo all the changes you made in tests/conftest.py.

### Testing with `pg_dump` generated schema

The DDL statements generated from `pg_dump` create tables and constraints
in an order that is different from the order that SQLAlchemy emits
when creating the database.

To test that the application works with a dump from `pg_dump`:
create a new database from the application,
dump the database,
create a new database based on the dump,
and then use that database in the regression tests.
There are several ways you could do this; the following is just one.

In `.env`, pick a name for a new database that we'll create to test with:

```sh
DATABASE_NAME=db_to_test
```

Start the application to create the database:

```sh
docker compose up -d api
docker compose stop api
```

We stop the service because the development Compose file is configured to reload
when files in `api/` are modified, which could mess with our experiment.

Use `pg_dump` from inside the `db` container
to dump the database into a SQL-script file
and pipe the output to a file on your host machine:

```sh
docker compose exec -T db \
  /bin/sh -c 'pg_dump -U $POSTGRES_USER -cC db_to_test' \
  > db.sql
```

`-cC` means that a `DROP DATABASE` and `CREATE DATABASE` will be present.

Run `psql` with the SQL-script file:

```sh
docker compose exec -T db \
  /bin/sh -c 'psql -U $POSTGRES_USER' \
  < db.sql
```

In [tests/conftest.py][conftest], change the name of the database
used for testing to the one we created:

```diff
-os.environ['DATABASE_NAME'] = 'dtnnr_test'
+os.environ['DATABASE_NAME'] = 'db_to_test'
```

In [tests/conftest.py][conftest], comment out the code in the `db()` function
that drops and creates a new database:

```diff
def db():
-    if database_exists(SQLALCHEMY_DATABASE_URI):
-        drop_database(SQLALCHEMY_DATABASE_URI)
-    create_database(SQLALCHEMY_DATABASE_URI)
+    # if database_exists(SQLALCHEMY_DATABASE_URI):
+    #     drop_database(SQLALCHEMY_DATABASE_URI)
+    # create_database(SQLALCHEMY_DATABASE_URI)
```

Run all the tests with `pytest`:

```sh
docker compose run --rm api pytest
```

Expect to see identical results to what you get when testing normally.

After testing, remember to undo the changes you made in .env
and tests/conftest.py to prevent confusion.

[conftest]: tests/conftest.py

# DTN Node Registry

The DTN Node Registry (DTNNR) is a part of a proposed workflow
to increase the accessibility of the [Interplanetary Overlay Network (ION)][ion].

For a computer to run ION, complicated configuration files need to be created.
The proposed workflow seeks to enable people interested in using ION
with minimal knowledge about the software to send information
to specialists who will create configuration files for them.
The DTNNR sits between these two groups:
the database will help users interested in ION understand what information
they need to send,
and it will help the specialists retrieve the information they need
to create configuration files.

Information that should be stored in this database
includes an ION node's general characteristics
(the allocator, operator, contact information, name of the spacecraft,
address information, name),
capabilities (available applications and storage options for ION),
available convergence layer protocols, and underlying link information.

## Setup

To run using the Compose file, create a directory with three files:

```
secrets
├── api_secret_key.txt
├── db_password.txt
└── page_token_key.txt
```

The content of `page_token_key.txt` must be 32 base64url-encoded bytes.

The environment also needs to have the following variables defined:

* `POSTGRES_DB`
* `POSTGRES_USER`
* `DATABASE_NAME`

[.env.example](.env.example) is a file you can use as an `.env` that meets
these requirements.

> [!NOTE]
> Avoid setting `DATABASE_NAME` to `dtnnr_test`
> since this is the name of the database created and dropped
> by tests in `api/`.

## Usage

During development, you can start the services with `docker compose up`:

```sh
docker compose up -d
```

The API documentation will be available at http://localhost:5000/schema/.
The web application will be available at http://localhost:5173/.

Run the backend's regression tests with `pytest`:

```sh
docker compose run --rm api pytest
```

For production, you can just use the production Compose file with:

```sh
docker compose -f compose.yaml up -d
```

The web application will be available at http://localhost:8000/.
The API is accessed through a reverse proxy at http://localhost:8000/api,
with the documentation available at http://localhost:8000/api/schema/.

[ion]: https://github.com/nasa-jpl/ION-DTN

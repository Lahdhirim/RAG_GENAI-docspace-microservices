# Document Manager read API

Document Manager owns SQL access for the interface. Parser execution, Redis and SQL connections are not accessed by the browser.

- `GET /documents`: existing `{ "documents": [...] }` response, including `submission_status` and `is_parsed` as separate fields.
- `GET /jobs`: `{ "jobs": [...] }` job history from SQL, ordered by `submitted_at DESC, job_id DESC`.
- `GET /jobs?document_id=<id>`: the same history restricted to a document, using a bound SQL parameter. IDs must contain 1–64 characters. A document without jobs returns an empty list.

Each job includes its IDs, recorded status, submitted/started/finished timestamps, waiting/execution durations in seconds, error text, and the document's filename and relative path. A left join preserves job records if joined document metadata is unavailable. Missing metadata, durations and error text remain null. Zero duration is a recorded value, not a missing value.

`models/job.py` defines the response contract using the shared job-status enum. Reads use the API's existing database lock and connection. No job mutation, parser submission or parsing implementation is added. SQL failures propagate as HTTP 500 rather than a successful empty history.

The UI displays SQL's last recorded state. `COMPLETED` represents the job status only; document parsing state remains the separate `is_parsed` flag. A missing error string means no error was recorded, not that a failed job succeeded.

## Tests

With the service's FastAPI/Pydantic dependencies and `httpx` installed:

```sh
python -m unittest discover -s src/services/doc_manager_service/tests -v
```

Run from the repository root. The tests exercise the actual query mapping and FastAPI response serialization with a mocked SQL connection. They cover all enum statuses, datetime/null/zero values, missing joined metadata, parameterized filtering, input validation, database errors, read-only routes and the existing document response. They do not require or validate a live MySQL or Redis instance.

## Document previews

`GET /documents/{document_id}/preview` looks up the document through Document Manager and returns its bytes inline only when it is marked present and its file exists under the document directory. Missing, absent or inaccessible files return HTTP 404 with `This document is currently unavailable.` No SQL writes or parser calls are made.

The root defaults to the repository's `data/` directory (`/app/data` in the existing container layout), independently of the process working directory. Set `DOCUMENTS_ROOT` to use another directory. Absolute paths, parent traversal and symlinks resolving outside that root are rejected. The filename comes from the resolved file; responses use `no-store` and `nosniff` headers.

Supported previews: PDF; PNG, JPEG, GIF, WebP and BMP images; TXT, MD, CSV, JSON, LOG and XML as plain text. HTML, SVG and other formats return HTTP 415. Files larger than 50 MiB return HTTP 413. Text is rendered as text, not HTML, by the frontend.

**Deployment requirement:** the API process must have read access to the same current document files as the scanner. The current Compose file mounts `data/` into the worker and Parser Service, but not `doc_manager_api`, and the Docker build excludes `data/`. Therefore container preview needs an API-side read-only mount or equivalent file access supplied by infrastructure. This change does not modify Compose or Dockerfiles. Until files are accessible to the API, the UI displays the unavailable message even if SQL's last presence flag is true.

Preview tests use temporary real files with the SQL document lookup mocked. They cover file bytes, media types, absent/missing files, root/path boundaries, unsupported types and size limits.

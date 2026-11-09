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

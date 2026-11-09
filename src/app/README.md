# Docspace — Document management frontend

A standalone Angular 21 / TypeScript application. **All frontend source, configuration and tests live inside the repository's `src/app/` directory.** The job-history read endpoint and SQL query live in Document Manager; no parser or infrastructure changes are included.

## Getting started

Requirements: Node.js 22.12+ or 24 and npm.

```sh
cd src/app
npm ci
npm start
```

Open http://localhost:4200. The Angular development server proxies **`/documents`, `/documents/*/preview` and `/jobs`** to FastAPI through `proxy.conf.cjs` (default target: http://127.0.0.1:8000, the port published by the existing Compose configuration). Document Manager and its database must already be running; the frontend does not start them. If the API runs elsewhere, update the frontend proxy target.

The application reads `GET /documents` and `GET /jobs` from Document Manager. `/documents` is also an Angular page route: the development proxy distinguishes HTML navigation from API data requests. Preview uses `GET /documents/{id}/preview`; no mutation endpoints are called.

## Features

- Document names, paths, extensions, sizes, modification dates, availability and parsing status.
- API-derived counters; total storage includes registered documents currently marked absent.
- Local filters for name/path, availability, submission status and extension, sorting by name, size or modification date, and pagination with 10 rows per page.
- A metadata dialog without additional API requests; null dates display as `—`.
- Preview actions in each row and the metadata dialog. Present documents support PDF, image and plain-text previews; absent documents show “This document is currently unavailable.” without a content request. Missing files reported by the API show the same message.
- Preview loading, retryable errors, unsupported-format and 50 MiB size-limit messages. Preview requests are cancelled and blob URLs released when the dialog closes. PDF uses the browser viewer, with a download fallback for browsers without embedded PDF support.
- Loading, empty library, no matching results, HTTP/network errors, invalid responses, a 15-second timeout and retry.
- Responsive layout, a horizontally scrollable table on smaller screens, keyboard navigation and a native dialog with Escape support and focus restoration.
- A read-only Parsing screen with all seven recorded job statuses, filters, pagination, timestamps, waiting/execution durations, error details and document-specific job history.
- OpenSearch search and AI agent navigation remain disabled and marked “Coming soon”.

Filtering and sorting run **locally** on the fetched list; they do not use OpenSearch. Parsing indicators reflect only the API response. A failed refresh hides the table; previous counters remain visible alongside “Refresh failed”. Interface text, accessibility labels, date and number formatting, documentation and PR descriptions use English. File sizes use binary units (B, KiB, MiB and GiB).

## API contract

Sources inspected on `feat/parser-service`: `src/services/doc_manager_service/app.py`, `models/document.py` and `database/queries.py`. The response is `{ "documents": [...] }`, containing `filename` (rather than the SQL column `file_name`), `id`, `relative_path`, `extension`, `content_hash`, `size_bytes`, `is_present`, `submission_status`, `is_parsed`, `file_created_at`, `file_modified_at`, `file_accessed_at`, `created_at` and `updated_at`. All five dates are nullable. Pydantic serializes flags as JSON booleans.

`submission_status` is `NOT_SUBMITTED`, `SUBMITTED` or `FAILED`, independently of `is_parsed`.

`GET /jobs` returns `{ "jobs": [...] }`; the optional `document_id` query parameter narrows the SQL history to one document (1–64 characters). Job fields are `job_id`, `document_id`, `filename`, `relative_path`, `submitted_at`, `status`, `started_at`, `finished_at`, `waiting_duration`, `execution_duration` and `error`. Names and paths are joined from documents and may be null. Durations are recorded seconds, including zero; unavailable times, durations and errors are null. Results are ordered by submission time descending, then job ID descending.

Supported job statuses: `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`, `NOT_STARTED`, `NOT_FOUND`, `UNKNOWN`. “Needs attention” counts failed, not-found and unknown jobs. Counts reflect the loaded history (or the selected document), independently of local table filters. A completed job does **not** imply `is_parsed=true`, and no parsing action is offered while parser execution is under construction. Manual refresh retrieves the last SQL state; there is no direct SQL, Redis or Parser Service access from the browser.

The service validates response structure before rendering. The application contains no fallback demo data.

## Architecture

- `src/core/documents/`: typed contract, validation and HTTP access.
- `src/features/documents/`: lazy-loaded document screen, signal-based state and computed filters.
- `src/core/jobs/`, `src/features/jobs/`: typed job-history client and lazy-loaded monitor.
- `src/shared/`: file size and date formatting.
- `src/app.component.ts`, `src/app.routes.ts`: application shell and navigation. Future features can add independent routes and services without coupling the document screen to other microservices.
- Angular, TypeScript, proxy configuration and locked dependencies at the root of this directory.

## Build and tests

```sh
npm run build
npm test
npx playwright install chromium
npm run test:e2e
npm run format:check
```

The production build is generated in `dist/documents/browser/`. Unit tests cover the API contract, invalid responses, HTTP errors and timeouts. Playwright starts Angular and intercepts `GET /documents` and `GET /jobs` responses to test rendering, filters, sorting, pagination, metadata, loading/error/empty states, retry, request method/count, JavaScript errors and document overflow on desktop and mobile.

To use an existing Chromium installation:

```sh
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium npm run test:e2e
```

Mock-based tests do not replace integration testing against a running FastAPI instance and database.

## Future hosting

The build uses relative `/documents` and `/jobs` data URLs and the `/documents` and `/parsing` page routes. Production hosting must forward API data requests to Document Manager and serve Angular's entry point for HTML navigation, including direct access to `/documents` and `/parsing`. The Angular proxy is development-only and is not included in the production build. Production routing remains an infrastructure responsibility; no Dockerfile or Compose files are modified.

## Pull request convention

Write PR titles and descriptions in English. Begin every Codex-generated PR description with a sentence identifying Codex and the model used, for example: “This pull request was generated by Codex using GPT-6.” Use the model actually reported for that session; do not guess a more specific model identifier.

## Preview integration

Preview bytes are fetched only from Document Manager's `GET /documents/{id}/preview`. Text formats render as escaped text; PDF and allowlisted raster images use temporary blob URLs. Closing the modal or leaving the page cancels the request and releases those URLs. PDF display depends on the browser's native viewer; a download fallback is provided. Other formats show an unsupported-preview message.

The Document Manager API must have read access to the current document directory (`DOCUMENTS_ROOT`, default repository `data/` or container `/app/data`). The current Compose configuration does not expose those files to `doc_manager_api`; infrastructure must supply that access for deployed previews. Docker/Compose are unchanged. If SQL says present but the API cannot read the file, the UI shows the unavailable message.

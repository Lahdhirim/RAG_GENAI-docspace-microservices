# Docspace — Document management frontend

A standalone Angular 21 / TypeScript application. **All frontend source, configuration and tests live inside the repository's `src/app/` directory.** The existing visual styling is preserved. The only backend additions are the explicitly authorized file-preview route and its SQL path lookup in Document Manager. Infrastructure is unchanged.

## Getting started

Requirements: Node.js 22.12+ or 24 and npm.

```sh
cd src/app
npm ci
npm start
```

Open http://localhost:4200. The Angular development server proxies **`/documents`, `/parsing_statuses` and document preview requests** to FastAPI through `proxy.conf.cjs` (default target: http://127.0.0.1:8000, the port published by the existing Compose configuration). Document Manager and its database must already be running; the frontend does not start them. If the API runs elsewhere, update the frontend proxy target.

The application reads `GET /documents` and `GET /parsing_statuses`. `/documents` is also an Angular page route: the development proxy distinguishes HTML navigation from API data requests. Original and Markdown bytes are read from `GET /documents/{id}/preview?kind=original|markdown`; the optional `job_id` selects a specific job’s output. No mutation endpoints are called.

## Features

- Document names, paths, extensions, sizes, modification dates, availability and parsing status.
- API-derived counters; total storage includes registered documents currently marked absent.
- Local filters for name/path, availability, submission status and extension, sorting by name, size or modification date, and pagination with 10 rows per page.
- A metadata dialog without additional API requests; null dates display as `—`.
- Loading, empty library, no matching results, HTTP/network errors, invalid responses, a 15-second timeout and retry.
- Responsive layout, a horizontally scrollable table on smaller screens, keyboard navigation and a native dialog with Escape support and focus restoration.
- Submission status and submission error in the document table and metadata dialog.
- A Parsing tab showing job status and document parsing state separately, durations, errors and saved Markdown paths, using the existing `/parsing_statuses` endpoint.
- Original-file previews and rendered/source Markdown previews from Documents and job details. Missing files show English unavailable messages.
- OpenSearch search and AI agent navigation remain disabled and marked “Coming soon”.

Filtering and sorting run **locally** on the fetched list; they do not use OpenSearch. Parsing indicators reflect only the API response. A failed refresh hides the table; previous counters remain visible alongside “Refresh failed”. Interface text, accessibility labels, date and number formatting, documentation and PR descriptions use English. File sizes use binary units (B, KiB, MiB and GiB).

## API contract

Sources inspected on `feat/parser-service`: `src/services/doc_manager_service/app.py`, `models/document.py` and `database/queries.py`. The response is `{ "documents": [...] }`, containing `filename` (rather than the SQL column `file_name`), `id`, `relative_path`, `extension`, `content_hash`, `size_bytes`, `is_present`, `submission_status`, `submission_error`, `is_parsed`, `file_created_at`, `file_modified_at`, `file_accessed_at`, `created_at` and `updated_at`. All five dates are nullable. Pydantic serializes flags as JSON booleans.

The service validates response structure before rendering. The application contains no fallback demo data.

## Architecture

- `src/core/documents/`: typed contract, validation and HTTP access.
- `src/features/documents/`: lazy-loaded document screen, signal-based state and computed filters.
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

The production build is generated in `dist/documents/browser/`. Unit tests cover the API contract, invalid responses, HTTP errors and timeouts. Playwright starts Angular and intercepts `GET /documents` responses to test rendering, filters, sorting, pagination, metadata, loading/error/empty states, retry, request method/count, JavaScript errors and document overflow on desktop and mobile.

To use an existing Chromium installation:

```sh
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium npm run test:e2e
```

Mock-based tests do not replace integration testing against a running FastAPI instance and database.

## Future hosting

The build uses the relative `/documents` URL. Production hosting must forward API data requests to Document Manager and serve Angular's entry point for HTML navigation, including direct access to `/documents`. The Angular proxy is development-only and is not included in the production build. Production routing remains an infrastructure responsibility; no Dockerfile or Compose files are modified.

## Pull request convention

Write PR titles and descriptions in English. Begin every Codex-generated PR description with a sentence identifying Codex and the model used, for example: “This pull request was generated by Codex using GPT-6.” Use the model actually reported for that session; do not guess a more specific model identifier.

## Parsing response and previews

`GET /parsing_statuses` returns `{ "statuses": [...] }` with positional rows: job ID, document ID, filename, job status, submitted time, started time, finished time, waiting duration, execution duration, error, and the appended `silver_relative_path`. The first ten existing columns are unchanged, and the frontend also accepts older ten-column responses. Filters run locally; no `/jobs` endpoint or direct Parser Service/SQL access is used. Job history still displays if document metadata cannot be loaded.

Preview file paths are resolved server-side from SQL by document/job ID, not supplied by the browser. Originals resolve under `data/bronze`; Markdown resolves under `data/silver`. Documents use the latest completed job with a stored output path; job details target that exact job. Missing originals show “This document is currently unavailable.” Missing Markdown shows “Markdown is not available for this document.” Markdown may remain available after the original disappears.

PDF uses the browser viewer, raster images use image previews, and text is escaped. Markdown supports rendered headings, tables and code plus a Source view; raw HTML is escaped and remote images/links are not loaded. Requests are cancelled when closed or switched, and blob URLs are released. Unsupported original formats and files larger than 50 MiB have explicit messages.

**Deployment:** Document Manager must be able to read the original and silver files. The API follows the existing `load_dotenv()` / `ENV` convention: `data_path` is `/app/data` when `ENV=production`, otherwise `data` relative to the process working directory. The current Compose configuration does not mount this directory into `doc_manager_api`; that file access remains an infrastructure responsibility. Docker and Compose are unchanged. Paths outside the respective bronze/silver roots are rejected.

Additional unit/API/browser scenarios are run internally outside the repository. No new test files or test folders are included in this change; existing tests remain in place.

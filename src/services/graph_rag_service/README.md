# GraphRAG Service

This standalone FastAPI service builds a knowledge graph from Markdown using Cognee and Neo4j. It provides graph-completion answers, natural-language-to-Cypher retrieval, and an HTML graph visualization.

The Document Manager owns the application's MySQL database. It sends Markdown content over HTTP, so this service does not need MySQL credentials, SQL queries, access to the parser's files, or Redis. Cognee keeps its own internal metadata and vector storage under the service state directory.

## Run locally

Run these commands from the repository root with Python 3.11+ and [uv](https://docs.astral.sh/uv/) installed. Keep the existing Neo4j Docker service running.

1. Copy `.env.example` to `.env` if needed, and fill in your existing application settings and the GraphRAG settings:

   ```dotenv
   GRAPH_RAG_SERVICE_URL=http://host.docker.internal:8002
   GRAPH_RAG_DATASET=docspace
   GRAPH_RAG_STATE_DIR=data/graph_rag
   LLM_PROVIDER=custom
   LLM_MODEL=openrouter/openai/gpt-5-nano
   LLM_ENDPOINT=https://openrouter.ai/api/v1
   LLM_API_KEY=<YOUR_OPENROUTER_KEY>
   EMBEDDING_PROVIDER=custom
   EMBEDDING_MODEL=openrouter/openai/text-embedding-3-small
   EMBEDDING_API_KEY=<YOUR_OPENROUTER_KEY>
   GRAPH_DATABASE_PROVIDER=neo4j
   GRAPH_DATABASE_URL=bolt://localhost:7687
   GRAPH_DATABASE_USERNAME=neo4j
   GRAPH_DATABASE_PASSWORD=<YOUR_NEO4J_PASSWORD>
   GRAPH_DATABASE_NAME=neo4j
   ENABLE_BACKEND_ACCESS_CONTROL=false
   ALLOW_CYPHER_QUERY=true
   ```

   `neo4j` is the existing database on Neo4j Community. With backend access control disabled, Cognee datasets share that graph. This API therefore serves only the configured `GRAPH_RAG_DATASET` and rejects other dataset names; this is not database-level isolation. Use a dedicated Neo4j database/server for this service if another application needs a separate graph.

   This URL lets Document Manager running in Docker Desktop reach GraphRAG on your host. If Document Manager also runs locally, change `GRAPH_RAG_SERVICE_URL` to `http://localhost:8002`. The GraphRAG service itself still connects to Neo4j at `localhost:7687`. No new Docker service is introduced here.

2. Install this service's locked dependencies:

   ```bash
   uv sync --locked --package graph-rag-service
   ```

3. Start one API process:

   ```bash
   uv run --locked --package graph-rag-service uvicorn app:app --app-dir src/services/graph_rag_service --host 0.0.0.0 --port 8002 --workers 1
   ```

   Open http://localhost:8002/docs for interactive requests. `GET /health` checks that the serial worker is running; it does not probe Neo4j or your model provider.

4. Initialize the Document Manager tables once, including on an existing installation:

   ```bash
   uv run --locked --package doc-manager-service --directory src/services/doc_manager_service python -m database.tables
   ```

   For an existing Docker installation, run `docker compose exec doc_manager_api python -m database.tables` after rebuilding the Document Manager image to include these changes. The existing API startup command also initializes tables when the container is recreated. Restart the Document Manager worker after updating its code and environment.

Keep the same state directory across service restarts. It contains the ingestion journal, received Markdown, and Cognee's internal stores; Neo4j data remains in its existing Docker volume. `SYSTEM_ROOT_DIRECTORY` and `DATA_ROOT_DIRECTORY` can override Cognee's subdirectories if needed, but do not point this service at notebook stores that another process is using.

## Ingestion flow

1. The Document Manager finds the latest completed parsing job containing nonempty Markdown for each present document.
2. It reserves an ingestion job in MySQL before submitting anything over HTTP. Each job records the document, parser job, dataset, and attempt.
3. It submits that Markdown to `POST /ingest` and polls `GET /job_status/{job_id}` on subsequent scheduler cycles. Only one ingestion is active at a time.
4. The GraphRAG service builds the graph and embeddings with Cognee. A job becomes `COMPLETED` only when that work finishes successfully.
5. `GET /documents` exposes `is_ingested` for the latest completed parser version. A newer parsed version needs its own successful ingestion.

An unavailable GraphRAG service does not stop document synchronization or parsing. A submission whose response was lost is reconciled with the same job ID. Failed ingestions require explicit retry through the Document Manager; they are not repeatedly sent to the model provider automatically.

Ingestion is **append-only**: a new parser version adds a versioned source, and earlier ingested versions remain searchable. Deleting documents or replacing old graph facts is not implemented. Source metadata includes the document ID and parser version. Repeating the same job ID and request returns its saved status; reusing that ID with different content returns `409`.

The GraphRAG journal stores accepted jobs before returning `202`. After restart, queued jobs resume; interrupted running jobs become `FAILED` because part of their graph may already exist. A retry can complete partial work, but ingestion across Cognee's stores is not an atomic transaction. Run one Uvicorn worker and one service instance per state directory; a file lock rejects a second instance.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Check the API and serial worker. |
| POST | `/ingest` | Submit Markdown and receive a job immediately. |
| GET | `/job_status/{job_id}` | Read a persisted ingestion status. |
| POST | `/query` | Answer a question using `GRAPH_COMPLETION` with references. |
| POST | `/query_cypher` | Translate a question into read-only Cypher and return its rows. |
| GET | `/generate_html?dataset=docspace` | Return an interactive HTML visualization. |

Example ingestion body, usable independently of Document Manager:

```json
{
  "job_id": "2a09f68a-3085-47a6-8a4b-bd52d1c3038d",
  "dataset": "docspace",
  "documents": [
    {
      "document_id": "document-123",
      "version": "parser-job-456",
      "filename": "regulation-report.pdf",
      "content": "# Regulation report\n\nThe report discusses stablecoin regulation."
    }
  ]
}
```

`job_id` can be omitted for standalone use; the service then generates a UUID. Supply your own UUID when you need safe submission retries. Each request accepts 1–20 documents, with up to 10 million characters of Markdown per document.

The job response contains `job_id`, `status` (`QUEUED`, `RUNNING`, `COMPLETED`, or `FAILED`), `document_ids`, timestamps, and an optional error. Unknown job IDs return `404`.

Both query endpoints accept:

```json
{
  "dataset": "docspace",
  "question": "Which documents discuss stablecoin regulation?"
}
```

They return `{ "dataset": "docspace", "results": [...] }`. `/query` returns Cognee recall results with generated answers and references. `/query_cypher` supplies the actual graph types, properties, and directed relationships to the model; generated parameters are bound separately. It rejects write operations and procedures, then verifies the query through Neo4j's read-only execution path. Results are limited to 100 rows. An empty result means the query matched no records; generation or execution failures return an error rather than a successful empty answer. This endpoint returns records, without an additional answer-writing model call.

Ingestion, queries, and HTML generation share one operation lock. Queries and HTML requests return `503` with `Retry-After: 5` while another graph operation is running. Job status and submission remain available.

The HTML visualization includes source content. Save the response as `.html` to inspect or share it; generated temporary files are removed after the response is prepared.

## Document Manager API additions

- `GET /ingestion_statuses`: list ingestion jobs with document names, versions, attempts, states, timestamps, and errors.
- `POST /documents/{document_id}/ingestion/retry`: reserve a new attempt after the latest ingestion fails; the scheduler submits it on its next cycle.
- `GET /documents`: includes `is_ingested`, derived from successful ingestion of the latest completed parser job.

The new `ingestion_jobs` table is created with `CREATE TABLE IF NOT EXISTS`; existing document and parser tables are preserved. GraphRAG never reads this table directly.

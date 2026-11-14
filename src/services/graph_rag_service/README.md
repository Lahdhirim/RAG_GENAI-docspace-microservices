# GraphRAG Service

A standalone FastAPI service that ingests Markdown with Cognee, answers questions using Neo4j, and generates an HTML graph.

## Code structure

- `app.py`: request models, endpoints, in-memory jobs, and one serial ingestion worker.
- `components/graph.py`: ordinary functions for ingestion, graph completion, Cypher queries, and HTML generation.
- Document Manager's `database/queries.py`: all application SQL queries, including ingestion tracking.
- Document Manager's `components/ingestion_manager.py`: submit jobs, fetch their status, and update SQL, following the parser manager's flow.

Only Document Manager accesses the application's MySQL database. It sends the Markdown already stored by the parser; GraphRAG does not read application SQL or shared document paths. Cognee manages its own internal stores.

## Run locally

Keep the existing Neo4j container running. From the repository root:

1. Fill in the GraphRAG settings from `.env.example`, including your LLM and embedding API keys and Neo4j credentials. Neo4j Community uses `GRAPH_DATABASE_NAME=neo4j` and `ENABLE_BACKEND_ACCESS_CONTROL=false`.
2. Install and start the service:

   ```bash
   uv sync --locked --package graph-rag-service
   uv run --locked --package graph-rag-service uvicorn app:app --app-dir src/services/graph_rag_service --host 0.0.0.0 --port 8002 --workers 1
   ```

3. Initialize Document Manager's tables before starting its updated API and worker:

   ```bash
   uv run --locked --package doc-manager-service --directory src/services/doc_manager_service python -m database.tables
   ```

   For an existing Docker installation, rebuild Document Manager with the updated code, then run `docker compose exec doc_manager_api python -m database.tables` and restart its worker. The existing API startup command also initializes tables when its container is recreated.

Document Manager uses `GRAPH_RAG_SERVICE_URL=http://host.docker.internal:8002` when it runs in Docker Desktop and GraphRAG runs on the host. Use `http://localhost:8002` when both services run locally. Neo4j remains reachable from the local GraphRAG service at `bolt://localhost:7687`.

Open http://localhost:8002/docs to try the API. Cognee's stores and the HTML export live under `GRAPH_RAG_STATE_DIR` (default: `data/graph_rag`). Docker configuration is unchanged.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Check that the ingestion worker is running. |
| POST | `/ingest` | Submit one Markdown document and immediately receive its job ID. |
| GET | `/job_status/{job_id}` | Get the job's status, timings, and error. |
| POST | `/query` | Answer a question with Cognee `GRAPH_COMPLETION` and references. |
| POST | `/query_cypher` | Translate a question into Cypher and return matching records. |
| GET | `/generate_html` | Generate and return the graph visualization. |

Example ingestion request:

```json
{
  "job_id": "2a09f68a-3085-47a6-8a4b-bd52d1c3038d",
  "document_id": "document-123",
  "version": "parser-job-456",
  "filename": "regulation-report.pdf",
  "content": "# Regulation report\n\nThe report discusses stablecoin regulation."
}
```

`job_id` is optional for standalone use. Document Manager supplies one and reuses it if an HTTP response is lost. Repeating an identical job does not ingest it twice while the service is running; different content with the same job ID returns `409`. States are `QUEUED`, `RUNNING`, `COMPLETED`, and `FAILED`.

Both query endpoints accept `{"question": "Which documents discuss stablecoin regulation?"}` and return `{"dataset": "docspace", "results": [...]}`. The Cypher function reads the real graph schema, asks the model for a query and parameters, then checks the query plan before executing a read transaction. Procedures and external functions are disabled, results are capped at 100 rows, and the database transaction times out after 30 seconds.

Requests use the configured `GRAPH_RAG_DATASET` by default. A supplied `dataset` must match it. Neo4j Community shares one graph across datasets; run this service against a dedicated graph. Queries and HTML generation return `503` while a graph operation is running.

## Ingestion tracking

Document Manager reserves an `ingestion_jobs` row before submitting a parsed document. Each scheduler cycle first refreshes active jobs, then submits the next document when the queue is free. `GET /documents` includes `is_ingested` for the latest completed parser version. `GET /ingestion_statuses` lists attempts; `POST /documents/{document_id}/ingestion/retry` queues a new attempt after a failure.

The service's queue and job statuses are kept in memory. Run one Uvicorn worker. Restarting GraphRAG clears remote jobs; Document Manager marks jobs previously acknowledged as accepted as failed if they disappear, and they can be retried explicitly. If a submission response was lost before a restart, the pending submission can be sent again. SQL history, Cognee's stores, and Neo4j data remain persistent. A failed ingestion may have written partial graph data.

New parser versions add versioned sources to the graph. Earlier ingested versions remain searchable.

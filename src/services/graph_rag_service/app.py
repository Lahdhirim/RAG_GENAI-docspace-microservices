import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID, uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Response
from filelock import FileLock, Timeout
from jobs import JobConflict, JobStore, SerialIngestion
from models import IngestRequest, JobResponse, QueryRequest

load_dotenv()
logger = logging.getLogger(__name__)


def create_app(engine=None, state_dir: Path | None = None, dataset: str | None = None):
    """Create a standalone graph service with a persistent serial ingestion queue."""
    root = Path(
        state_dir or os.getenv("GRAPH_RAG_STATE_DIR", "data/graph_rag")
    ).resolve()
    configured_dataset = dataset or os.getenv("GRAPH_RAG_DATASET", "docspace")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        root.mkdir(parents=True, exist_ok=True)
        process_lock = FileLock(str(root / ".service.lock"))
        try:
            process_lock.acquire(timeout=0)
        except Timeout as exc:
            raise RuntimeError(
                "GraphRAG already uses this state directory; run one worker."
            ) from exc
        worker = None
        try:
            active_engine = engine
            if active_engine is None:
                os.environ.setdefault("GRAPH_DATABASE_PROVIDER", "neo4j")
                os.environ.setdefault("ENABLE_BACKEND_ACCESS_CONTROL", "false")
                os.environ.setdefault("ALLOW_CYPHER_QUERY", "true")
                os.environ.setdefault("SYSTEM_ROOT_DIRECTORY", str(root / "system"))
                os.environ.setdefault("DATA_ROOT_DIRECTORY", str(root / "data"))
                from components.engine import CogneeEngine

                active_engine = CogneeEngine(root)
            app.state.engine = active_engine
            app.state.engine_lock = asyncio.Lock()
            app.state.store = JobStore(root / "jobs")
            worker = SerialIngestion(
                app.state.store, active_engine, app.state.engine_lock
            )
            app.state.worker = worker
            worker.start()
            yield
        finally:
            if worker is not None:
                await worker.stop()
            process_lock.release()

    app = FastAPI(title="Docspace GraphRAG Service", lifespan=lifespan)

    def check_dataset(value: str) -> None:
        if value != configured_dataset:
            raise HTTPException(
                422, f"This instance serves dataset '{configured_dataset}'."
            )

    @app.get("/health")
    async def health():
        check_worker()
        return {"status": "OK", "dataset": configured_dataset}

    def check_worker() -> None:
        if app.state.worker.task.done():
            raise HTTPException(
                503, "The ingestion worker stopped; inspect the service logs."
            )

    @app.post("/ingest", response_model=JobResponse, status_code=202)
    async def ingest(request: IngestRequest):
        """Queue Markdown documents and return a job ID immediately."""
        check_dataset(request.dataset)
        check_worker()
        try:
            return app.state.worker.submit(request)
        except JobConflict as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/job_status/{job_id}", response_model=JobResponse)
    async def job_status(job_id: UUID):
        """Return the persisted state of an ingestion job."""
        record = app.state.store.records.get(job_id)
        if record is None:
            raise HTTPException(404, "Ingestion job not found.")
        return record.response()

    async def run_query(request: QueryRequest, method: str):
        check_dataset(request.dataset)
        if app.state.engine_lock.locked():
            raise HTTPException(
                503,
                "The graph is busy; retry after the active operation.",
                headers={"Retry-After": "5"},
            )
        async with app.state.engine_lock:
            try:
                results = await getattr(app.state.engine, method)(
                    request.question, request.dataset
                )
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            except Exception as exc:
                logger.exception("Graph query failed")
                raise HTTPException(
                    502, "Graph query failed; inspect the service logs."
                ) from exc
        return {"dataset": request.dataset, "results": results}

    @app.post("/query")
    async def query(request: QueryRequest):
        """Answer a question with Cognee graph completion and source references."""
        return await run_query(request, "query")

    @app.post("/query_cypher")
    async def query_cypher(request: QueryRequest):
        """Translate a question to Cypher and return the query results."""
        return await run_query(request, "query_cypher")

    @app.get("/generate_html", response_class=Response)
    async def generate_html(
        dataset: str = Query(default="docspace", min_length=1, max_length=64)
    ):
        """Generate and return an HTML visualization of the graph."""
        check_dataset(dataset)
        if app.state.engine_lock.locked():
            raise HTTPException(
                503,
                "The graph is busy; retry after the active operation.",
                headers={"Retry-After": "5"},
            )
        async with app.state.engine_lock:
            output = root / f"graph-{uuid4().hex}.html"
            try:
                await app.state.engine.generate_html(dataset, output)
                content = output.read_bytes()
            except Exception as exc:
                logger.exception("Graph visualization failed")
                raise HTTPException(
                    502, "Unable to generate the graph visualization."
                ) from exc
            finally:
                output.unlink(missing_ok=True)
        return Response(
            content, media_type="text/html", headers={"Cache-Control": "no-store"}
        )

    return app


app = create_app()

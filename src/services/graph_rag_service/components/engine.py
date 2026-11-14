"""Build and query document knowledge graphs with Cognee and Neo4j."""

import hashlib
import json
import re
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from fastapi import UploadFile
from pydantic import BaseModel, Field

MAX_QUERY_ROWS = 100
QUERY_TIMEOUT_SECONDS = 30

CYPHER_RULES = """Translate the question into one read-only Neo4j Cypher query.
Use only the supplied node types, properties and directed relationships.
Every data node has the label __Node__; its type property identifies its node type.
Node types are property values, not labels: match (n:__Node__) and filter n.type.
Follow the actual relationships to connect entities, chunks and source documents.
Use case-insensitive name matching for concepts unless an exact match is requested.
Use DISTINCT for document lists and count distinct chunks for chunk occurrence counts.
Return useful scalar properties or maps, rather than entire nodes or relationships.
Put question values in parameters and return those values in parameters_json as a JSON object.
Do not use CALL, procedures, external functions, writes, administrative commands or multiple statements.
Limit the final results to 100 rows. Return an empty result when no data matches;
do not invent relationships, document names or an answer to the question.
"""

_CYPHER_TOKENS = re.compile(
    r"//[^\n]*|/\*.*?\*/|'(?:\\.|''|[^'\\])*'|"
    r'"(?:\\.|""|[^"\\])*"|`(?:``|[^`])*`|'
    r"[A-Za-z_][A-Za-z_0-9]*|[^\s]",
    re.DOTALL,
)
_WRITE_CLAUSES = {
    "ALTER",
    "CALL",
    "CREATE",
    "CYPHER",
    "DEALLOCATE",
    "DELETE",
    "DENY",
    "DETACH",
    "DROP",
    "ENABLE",
    "EXPLAIN",
    "FINISH",
    "FOREACH",
    "GRANT",
    "INSERT",
    "LOAD",
    "MERGE",
    "PROFILE",
    "REALLOCATE",
    "REMOVE",
    "RENAME",
    "REVOKE",
    "SET",
    "SHOW",
    "START",
    "STOP",
    "TERMINATE",
    "USE",
}


class CypherPlan(BaseModel):
    """Describe a generated query and its bound parameter values."""

    query: str = Field(min_length=1)
    parameters_json: str = Field(
        description="A JSON object of Cypher parameter values."
    )


def validate_read_query(query: str) -> None:
    """Reject commands and procedures before Neo4j checks the query plan."""
    tokens = []
    for token in _CYPHER_TOKENS.findall(query):
        if token.startswith(("//", "/*")):
            continue
        if token.startswith(("'", '"', "`")):
            tokens.append("__QUOTED__")
        else:
            tokens.append(token)
    words = [token.upper() for token in tokens]
    if not words or words[0] not in {"MATCH", "OPTIONAL", "WITH", "UNWIND", "RETURN"}:
        raise ValueError("Only read-only Cypher queries are supported.")
    if ";" in words or "RETURN" not in words or _WRITE_CLAUSES.intersection(words):
        raise ValueError(
            "Cypher writes, procedures and multiple statements are disabled."
        )
    # Namespaced functions can execute nested queries, so accept built-in functions only.
    for index in range(len(tokens) - 3):
        if tokens[index + 1] == "." and tokens[index + 3] == "(":
            raise ValueError("External Cypher functions are disabled.")


def _json_value(value: Any) -> Any:
    """Convert Cognee results and Neo4j values into JSON-compatible objects."""
    if isinstance(value, BaseModel):
        return _json_value(value.model_dump(mode="python"))
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "items"):
        return {str(key): _json_value(item) for key, item in value.items()}
    return str(value)


async def execute_read_query(graph: Any, query: str, parameters: dict) -> list[dict]:
    """Run a parameterized query after Neo4j confirms that its plan only reads data."""
    from neo4j import unit_of_work

    validate_read_query(query)

    @unit_of_work(timeout=QUERY_TIMEOUT_SECONDS)
    async def read(transaction):
        explanation = await transaction.run("EXPLAIN " + query, parameters=parameters)
        summary = await explanation.consume()
        if summary.query_type != "r":
            raise ValueError("Neo4j rejected a query that is not read-only.")
        result = await transaction.run(query, parameters=parameters)
        records = await result.fetch(MAX_QUERY_ROWS)
        return [record.data() for record in records]

    async with graph.get_session() as session:
        return await session.execute_read(read)


class CogneeEngine:
    """Provide document ingestion, graph retrieval and visualization through Cognee."""

    def __init__(self, root: Path):
        self.root = root
        self._cognee = None

    def _load_cognee(self):
        """Import Cognee after the application has loaded its environment settings."""
        if self._cognee is None:
            import cognee

            self._cognee = cognee
        return self._cognee

    async def ingest(self, documents: list[dict], dataset: str) -> None:
        """Add supplied Markdown documents and their source metadata to the graph."""
        cognee = self._load_cognee()
        from cognee.tasks.ingestion.data_item import DataItem

        uploads = []
        items = []
        try:
            for document in documents:
                content = document["content"].encode("utf-8")
                filename = Path(document["filename"].replace("\\", "/")).stem + ".md"
                upload = UploadFile(filename=filename, file=BytesIO(content))
                uploads.append(upload)
                identity = json.dumps(
                    [
                        dataset,
                        document["document_id"],
                        document["version"],
                        hashlib.sha256(content).hexdigest(),
                    ],
                    separators=(",", ":"),
                )
                items.append(
                    DataItem(
                        data=upload,
                        label=filename,
                        external_metadata={
                            "document_id": document["document_id"],
                            "version": document["version"],
                            "filename": document["filename"],
                        },
                        data_id=uuid5(NAMESPACE_URL, identity),
                    )
                )
            result = await cognee.remember(
                items,
                dataset_name=dataset,
                run_in_background=False,
                self_improvement=False,
                raise_on_error=True,
            )
            if result.status != "completed":
                raise RuntimeError(
                    result.error or "Cognee did not complete document ingestion."
                )
        finally:
            for upload in uploads:
                await upload.close()

    async def query(self, question: str, dataset: str) -> list[dict]:
        """Answer a question using graph retrieval with document references."""
        cognee = self._load_cognee()
        results = await cognee.recall(
            query_text=question,
            query_type=cognee.SearchType.GRAPH_COMPLETION,
            datasets=[dataset],
            include_references=True,
        )
        return _json_value(results)

    async def query_cypher(self, question: str, dataset: str) -> list[dict]:
        """Translate a question into read-only Cypher and return the matching graph rows."""
        cognee = self._load_cognee()
        from cognee.modules.retrieval.natural_language_retriever import (
            NaturalLanguageRetriever,
        )
        from cognee.modules.retrieval.register_retriever import use_retriever
        from cognee.modules.retrieval.registered_community_retrievers import (
            registered_community_retrievers,
        )

        engine = self

        class DocumentGraphRetriever(NaturalLanguageRetriever):
            def __init__(self, **kwargs):
                super().__init__(session_id=kwargs.get("session_id"))

            async def _execute_cypher_query(self, query, graph_engine):
                return await engine._query_graph(query, graph_engine)

        search_type = cognee.SearchType.NATURAL_LANGUAGE
        previous = registered_community_retrievers.get(search_type)
        use_retriever(search_type, DocumentGraphRetriever)
        try:
            results = await cognee.recall(
                query_text=question,
                query_type=search_type,
                datasets=[dataset],
            )
            return _json_value(results)
        finally:
            if previous is None:
                registered_community_retrievers.pop(search_type, None)
            else:
                use_retriever(search_type, previous)

    async def _graph_schema(self, graph: Any) -> str:
        """Describe the actual node types, useful properties and directed graph relationships."""
        nodes = await graph.query("""
            MATCH (n:__Node__)
            WHERE coalesce(n.is_internal, false) = false
            UNWIND keys(n) AS property
            RETURN n.type AS type, collect(DISTINCT property) AS properties
            ORDER BY type
        """)
        edges = await graph.query("""
            MATCH (source:__Node__)-[r]->(target:__Node__)
            WHERE coalesce(source.is_internal, false) = false
              AND coalesce(target.is_internal, false) = false
            RETURN DISTINCT source.type AS source, type(r) AS relation, target.type AS target
            ORDER BY source, relation, target
        """)
        useful_properties = {
            "id",
            "type",
            "name",
            "title",
            "text",
            "data_id",
            "source_document",
        }
        node_lines = [
            f"{node['type']}: {', '.join(sorted(useful_properties.intersection(node['properties'])))}"
            for node in nodes
            if node["type"]
        ]
        edge_lines = [
            f"{edge['source']} -[{edge['relation']}]-> {edge['target']}"
            for edge in edges
            if edge["source"] and edge["target"]
        ]
        return (
            "Node types and properties:\n"
            + "\n".join(node_lines)
            + "\nRelationships:\n"
            + "\n".join(edge_lines)
        )

    async def _query_graph(self, question: str, graph: Any) -> list[dict]:
        """Generate a query from the live graph schema and bind its parameters before execution."""
        from cognee.infrastructure.llm.LLMGateway import LLMGateway
        from cognee.modules.retrieval.natural_language_retriever import (
            _contains_internal_node,
        )

        schema = await self._graph_schema(graph)
        failures = []
        last_error = None
        for _ in range(3):
            try:
                plan = await LLMGateway.acreate_structured_output(
                    text_input=question,
                    system_prompt=CYPHER_RULES
                    + "\nActual graph schema:\n"
                    + schema
                    + "\nPrevious errors:\n"
                    + "\n".join(failures),
                    response_model=CypherPlan,
                )
                parameters = json.loads(plan.parameters_json)
                if not isinstance(parameters, dict):
                    raise ValueError("Cypher parameters must be a JSON object.")
                rows = await execute_read_query(graph, plan.query, parameters)
                return [
                    _json_value(row) for row in rows if not _contains_internal_node(row)
                ]
            except Exception as error:
                last_error = error
                failures.append(str(error)[:1000])
        raise RuntimeError(
            "Could not generate and execute a valid read-only Cypher query."
        ) from last_error

    async def generate_html(self, dataset: str, output_path: Path) -> None:
        """Save an interactive HTML visualization of the dataset graph."""
        cognee = self._load_cognee()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        await cognee.visualize_graph(str(output_path), dataset=dataset, full=True)

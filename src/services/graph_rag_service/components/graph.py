import json
import re
from io import BytesIO
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from fastapi import UploadFile
from pydantic import BaseModel


class CypherPlan(BaseModel):
    query: str
    parameters_json: str


CYPHER_RULES = """Translate the question into one read-only Neo4j Cypher query.
Use the supplied node types, properties and directed relationships.
All nodes have label __Node__; their type property identifies their node type.
Follow the graph relationships between entities, chunks and documents.
Match concept names case-insensitively and deduplicate document titles.
Put question values in parameters_json, a JSON object bound separately to the query.
Return scalar properties or maps, never whole nodes or relationships; limit results to 100.
Do not use comments, procedures, external functions, writes or administrative commands.
"""


async def ingest_document(document: dict, dataset: str) -> None:
    """Add a Markdown document and its source metadata to the knowledge graph."""
    import cognee
    from cognee.tasks.ingestion.data_item import DataItem

    filename = Path(document["filename"].replace("\\", "/")).stem + ".md"
    upload = UploadFile(
        filename=filename, file=BytesIO(document["content"].encode("utf-8"))
    )
    identity = json.dumps([dataset, document["document_id"], document["version"]])
    try:
        item = DataItem(
            data=upload,
            label=filename,
            data_id=uuid5(NAMESPACE_URL, identity),
            external_metadata={
                key: document[key] for key in ("document_id", "version", "filename")
            },
        )
        result = await cognee.remember(
            item,
            dataset_name=dataset,
            self_improvement=False,
            run_in_background=False,
            raise_on_error=True,
        )
        if result.status != "completed":
            raise RuntimeError(result.error or "Document ingestion failed.")
    finally:
        await upload.close()


async def query(question: str, dataset: str) -> list[dict]:
    """Answer a question using graph retrieval and document references."""
    import cognee

    results = await cognee.recall(
        query_text=question,
        datasets=[dataset],
        query_type=cognee.SearchType.GRAPH_COMPLETION,
        include_references=True,
    )
    return [result.model_dump(mode="json") for result in results]


async def graph_schema(graph) -> str:
    """Describe the node types, useful properties and relationships currently in the graph."""
    nodes = await graph.query("""
        MATCH (n:__Node__)
        WHERE coalesce(properties(n).is_internal, false) = false
        UNWIND keys(n) AS property
        RETURN n.type AS type, collect(DISTINCT property) AS properties
    """)
    edges = await graph.query("""
        MATCH (source:__Node__)-[r]->(target:__Node__)
        WHERE coalesce(properties(source).is_internal, false) = false
          AND coalesce(properties(target).is_internal, false) = false
        RETURN DISTINCT source.type AS source, type(r) AS relation, target.type AS target
    """)
    properties = {"id", "type", "name", "title", "text", "data_id", "source_document"}
    node_types = [
        f"{n['type']}: {', '.join(sorted(properties.intersection(n['properties'])))}"
        for n in nodes
        if n["type"]
    ]
    relationships = [
        f"{e['source']} -[{e['relation']}]-> {e['target']}"
        for e in edges
        if e["source"] and e["target"]
    ]
    return (
        "Node types and properties:\n"
        + "\n".join(node_types)
        + "\nRelationships:\n"
        + "\n".join(relationships)
    )


async def query_cypher(question: str, dataset: str) -> list[dict]:
    """Translate a question into Cypher and return matching graph rows."""
    from cognee.infrastructure.databases.graph import get_graph_engine
    from cognee.infrastructure.llm.LLMGateway import LLMGateway
    from neo4j import unit_of_work

    graph = await get_graph_engine()
    schema = await graph_schema(graph)
    plan = await LLMGateway.acreate_structured_output(
        text_input=question,
        system_prompt=CYPHER_RULES + "\nActual graph schema:\n" + schema,
        response_model=CypherPlan,
    )
    parameters = json.loads(plan.parameters_json)
    if not isinstance(parameters, dict):
        raise ValueError("Cypher parameters must be a JSON object.")
    if not re.match(r"\s*(MATCH|OPTIONAL|WITH|UNWIND|RETURN)\b", plan.query, re.I):
        raise ValueError("Only document graph queries are supported.")
    # A read plan can still invoke a procedure or external function with side effects.
    identifier = r"(?:\w+|`(?:``|[^`])+`)"
    if re.search(
        r"\bCALL\b|/\*|//|" + identifier + r"\s*\.\s*" + identifier + r"\s*\(",
        plan.query,
        re.I,
    ):
        raise ValueError(
            "Cypher procedures, external functions and comments are disabled."
        )

    @unit_of_work(timeout=30)
    async def read(transaction):
        explanation = await transaction.run(
            "EXPLAIN " + plan.query, parameters=parameters
        )
        if (await explanation.consume()).query_type != "r":
            raise ValueError("Only read-only Cypher queries are supported.")
        result = await transaction.run(plan.query, parameters=parameters)
        rows = [record.data() for record in await result.fetch(100)]
        return json.loads(json.dumps(rows, default=str))

    async with graph.get_session() as session:
        return await session.execute_read(read)


async def generate_html(dataset: str, output_path: Path) -> None:
    """Save an interactive HTML visualization of the knowledge graph."""
    import cognee

    output_path.parent.mkdir(parents=True, exist_ok=True)
    await cognee.visualize_graph(str(output_path), dataset=dataset, full=True)

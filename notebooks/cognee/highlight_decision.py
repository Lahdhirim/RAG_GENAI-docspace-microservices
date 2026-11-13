"""Highlight recall evidence in Cognee's existing D3 canvas HTML."""

import json
import webbrowser
from pathlib import Path


def highlight_cognee_html(
    evidence, source="graph.html", output="graph_highlighted.html", open_browser=True
):
    source = Path(source)
    html = source.read_text(encoding="utf-8")
    if "/* RECALL_EVIDENCE_OVERLAY */" in html:
        raise ValueError("Use the original graph.html, not an already highlighted copy")

    node_ids, chunk_ids, edge_keys = set(), set(), set()
    for ev in evidence:
        kind = ev.get("kind")
        if kind == "graph_node" and ev.get("artifact_id"):
            node_ids.add(str(ev["artifact_id"]))
        elif kind == "graph_edge":
            source_id, target_id = ev.get("source_node_id"), ev.get("target_node_id")
            if source_id and target_id:
                node_ids.update((str(source_id), str(target_id)))
                edge_keys.add(
                    (
                        str(source_id),
                        str(target_id),
                        str(ev.get("relationship_name") or ""),
                    )
                )
        elif kind == "segment" and ev.get("chunk_id"):
            chunk_ids.add(str(ev["chunk_id"]))

    payload = json.dumps(
        {
            "nodes": sorted(node_ids),
            "chunks": sorted(chunk_ids),
            "edges": sorted(map(list, edge_keys)),
        },
        ensure_ascii=True,
    )
    setup = """
/* RECALL_EVIDENCE_OVERLAY */
var recallEvidence = __PAYLOAD__;
var recallNodes = new Set(recallEvidence.nodes);
var recallChunks = new Set(recallEvidence.chunks);
var recallEdges = new Set(recallEvidence.edges.map(e => JSON.stringify(e)));
""".replace("__PAYLOAD__", payload)

    # Insert directly in Cognee's existing canvas draw() pipeline, after normal nodes,
    # before labels. No dependency on vis-network or on globals outside its script.
    overlay = """
  // Recall evidence overlay: drawn in graph coordinates, so pan/zoom still work.
  ctx.save();
  links.forEach(function(l) {
    const sid = String(typeof l.source === 'object' ? l.source.id : l.source);
    const tid = String(typeof l.target === 'object' ? l.target.id : l.target);
    const rel = String(l.relation || '');
    if (!recallEdges.has(JSON.stringify([sid, tid, rel]))) return;
    const s = nodeMap[sid], t = nodeMap[tid];
    if (!s || !t || !Number.isFinite(s.x) || !Number.isFinite(t.x)) return;
    ctx.beginPath();
    ctx.moveTo(s.x, s.y);
    ctx.lineTo(t.x, t.y);
    ctx.strokeStyle = '#ef4444';
    ctx.lineWidth = 3.5 / scale;
    ctx.globalAlpha = 0.95;
    ctx.stroke();
  });
  nodes.forEach(function(n) {
    const id = String(n.id);
    const isChunk = recallChunks.has(id);
    if (!isChunk && !recallNodes.has(id)) return;
    if (!Number.isFinite(n.x) || !Number.isFinite(n.y)) return;
    const radius = Math.max(n._r || 5, 5) + 5 / scale;
    ctx.beginPath();
    ctx.arc(n.x, n.y, radius, 0, Math.PI * 2);
    ctx.strokeStyle = isChunk ? '#f59e0b' : '#2563eb';
    ctx.lineWidth = 4 / scale;
    ctx.globalAlpha = 1;
    ctx.stroke();
  });
  ctx.restore();
"""
    draw_marker = "function draw(){"
    labels_marker = "  // ── Labels (Phase 3e: adaptive; Phase 1b: budget-aware) ──"
    if html.count(draw_marker) != 1 or html.count(labels_marker) != 1:
        raise ValueError(
            "Unexpected Cognee HTML version: canvas draw() markers not found"
        )
    html = html.replace(draw_marker, setup + "\n" + draw_marker, 1)
    html = html.replace(labels_marker, overlay + "\n" + labels_marker, 1)
    output = Path(output).resolve()
    output.write_text(html, encoding="utf-8")
    print(
        f"Saved: {output} | evidence nodes: {len(node_ids)} | supporting chunks: {len(chunk_ids)} | evidence edges: {len(edge_keys)}"
    )
    if open_browser:
        webbrowser.open(output.as_uri())
    return output

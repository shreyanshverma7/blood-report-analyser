from typing import Optional
from qdrant_client.models import Filter, FieldCondition, MatchValue
from langchain_core.tools import tool

from src.core import user_context
from src.core.clients import get_embedding_model, get_qdrant
from src.db.supabase_client import get_client


@tool
def query_my_reports(question: str, report_id: Optional[str] = None) -> str:
    """Search the user's blood report panels for information relevant to the question.
    If report_id is provided, filter results to that specific report only.
    Returns a summary of the most relevant panel findings."""
    user_id = user_context.user_id()
    if not user_id:
        return "No signed-in user — report data is unavailable."

    vector = get_embedding_model().encode(question, normalize_embeddings=True).tolist()

    # Qdrant has no RLS: the user_id filter is the isolation boundary here
    must = [FieldCondition(key="user_id", match=MatchValue(value=user_id))]
    if report_id:
        must.append(FieldCondition(key="report_id", match=MatchValue(value=report_id)))
    query_filter = Filter(must=must)

    results = get_qdrant().query_points(
        collection_name="report_chunks",
        query=vector,
        query_filter=query_filter,
        limit=3,
        with_payload=True,
    )

    if not results.points:
        return "No relevant report data found."

    lines = []
    for point in results.points:
        panel = point.payload.get("panel", "Unknown")
        summary = point.payload.get("summary_text", "")
        lines.append(f"[{panel}] {summary}")

    return "\n\n".join(lines)


@tool
def compare_reports(marker_name: str) -> str:
    """Compare values of a specific blood marker across all ingested reports, ordered by date.
    Returns a chronological comparison showing how the marker has changed over time."""
    # Escape LIKE wildcards so a name containing % or _ can't match everything
    pattern = marker_name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    result = (
        get_client().from_("markers")
        .select("name, value, unit, flag, reports(report_date)")
        .ilike("name", f"%{pattern}%")
        .execute()
    )

    rows = result.data
    if not rows:
        return f"No data found for marker: {marker_name}"

    # (r.get("reports") or {}): the joined parent can be present-but-None
    rows.sort(key=lambda r: (r.get("reports") or {}).get("report_date") or "")

    header = f"## {marker_name} across all reports\n\n| Date | Value | Unit | Flag |\n|------|-------|------|------|\n"
    table_rows = "\n".join(
        f"| {(row.get('reports') or {}).get('report_date') or 'Unknown'} "
        f"| {row.get('value')} "
        f"| {row.get('unit') or '—'} "
        f"| {row.get('flag').upper() if row.get('flag') else '—'} |"
        for row in rows
    )
    return header + table_rows


@tool
def search_medical_kb(query: str) -> str:
    """Search the medical knowledge base for information about lab tests, markers, and health conditions.
    Returns relevant excerpts from medical reference documents with source citations."""
    vector = get_embedding_model().encode(query, normalize_embeddings=True).tolist()

    results = get_qdrant().query_points(
        collection_name="medical_kb",
        query=vector,
        limit=3,
        with_payload=True,
    )

    if not results.points:
        return "No relevant medical information found."

    lines = []
    for point in results.points:
        source = point.payload.get("source", "unknown")
        text = point.payload.get("text", "")[:300]
        lines.append(f"[{source}] {text}")

    return "\n\n".join(lines)

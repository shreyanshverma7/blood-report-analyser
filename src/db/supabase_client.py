import os
from typing import List
from supabase import Client, create_client

from src import config  # noqa: F401 — loads env before the client is built
from src.core import user_context
from src.ingestion.marker_extractor import Marker
from src.ingestion.report_metadata import ReportMetadata

# Clients keyed by access token ("" = anonymous). One shared client whose auth
# header is mutated per request would race across concurrent user sessions.
_clients: dict[str, Client] = {}


def new_anon_client() -> Client:
    """Fresh anon-key client — used by app.py for the per-session auth flow."""
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])


def get_client() -> Client:
    """Anon-key client carrying the current user's JWT (from user_context),
    so RLS scopes every query to that user. Without a signed-in user the
    client is anonymous and RLS returns nothing."""
    token = user_context.access_token() or ""
    client = _clients.get(token)
    if client is None:
        if len(_clients) > 16:  # tokens rotate hourly; don't accumulate stale pools
            _clients.clear()
        client = new_anon_client()
        if token:
            client.postgrest.auth(token)
        _clients[token] = client
    return client


def get_service_client() -> Client:
    """service_role client — bypasses RLS. Offline scripts only; never call
    this from the app path."""
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_KEY not set (offline scripts only)")
    return create_client(os.environ["SUPABASE_URL"], key)


def insert_report(metadata: ReportMetadata, raw_text: str) -> str:
    row = {
        "report_date": metadata.report_date,
        "patient_age": metadata.patient_age,
        "patient_gender": metadata.patient_gender,
        "lab_name": metadata.lab_name,
        "raw_text": raw_text,
    }
    result = get_client().from_("reports").insert(row).execute()
    return result.data[0]["id"]


def get_existing_report(lab_name: str, report_date: str) -> str | None:
    result = (
        get_client().from_("reports")
        .select("id")
        .eq("lab_name", lab_name)
        .eq("report_date", report_date)
        .limit(1)
        .execute()
    )
    return result.data[0]["id"] if result.data else None


def get_reports() -> list:
    result = (
        get_client().from_("reports")
        .select("id, report_date, patient_age, patient_gender, lab_name")
        .order("report_date", desc=True)
        .execute()
    )
    return result.data or []


def get_report(report_id: str) -> dict | None:
    # maybe_single, not single: single() raises APIError on zero rows
    result = (
        get_client().from_("reports")
        .select("id, report_date, patient_age, patient_gender, lab_name")
        .eq("id", report_id)
        .maybe_single()
        .execute()
    )
    return result.data if result else None


def get_markers_for_report(report_id: str) -> list:
    result = (
        get_client().from_("markers")
        .select("name, value, value_text, unit, ref_low, ref_high, flag")
        .eq("report_id", report_id)
        .execute()
    )
    return result.data or []


def insert_markers(report_id: str, markers: List[Marker]) -> None:
    if not markers:
        return  # PostgREST raises on an empty insert payload
    rows = [
        {
            "report_id": report_id,
            "name": m.name,
            "value": m.value,
            "value_text": m.value_text,
            "unit": m.unit,
            "ref_low": m.ref_low,
            "ref_high": m.ref_high,
            "flag": m.flag,
        }
        for m in markers
    ]
    get_client().from_("markers").insert(rows).execute()

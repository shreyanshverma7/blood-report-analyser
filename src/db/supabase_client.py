import os
from typing import List
from supabase import create_client

from src import config  # noqa: F401 — loads env before the client is built
from src.ingestion.marker_extractor import Marker
from src.ingestion.report_metadata import ReportMetadata

_client = None


def get_client():
    global _client
    if _client is None:
        _client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    return _client


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
    result = (
        get_client().from_("reports")
        .select("id, report_date, patient_age, patient_gender, lab_name")
        .eq("id", report_id)
        .single()
        .execute()
    )
    return result.data


def get_markers_for_report(report_id: str) -> list:
    result = (
        get_client().from_("markers")
        .select("name, value, unit, ref_low, ref_high, flag")
        .eq("report_id", report_id)
        .execute()
    )
    return result.data or []


def insert_markers(report_id: str, markers: List[Marker]) -> None:
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

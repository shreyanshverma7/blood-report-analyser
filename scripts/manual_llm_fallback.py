# Manual driver, not a test: ingests the sample PDFs into the LIVE database.
# NOTE: after the auth migration (scripts/setup_auth.sql), inserts require a
# signed-in user JWT (reports.user_id is NOT NULL DEFAULT auth.uid()), so the
# ingest calls here will fail — upload through the app instead. The read-back
# below uses the service client and still works.
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.INFO, format="%(name)s — %(message)s")

from src.ingestion.pipeline import ingest
from src.db.supabase_client import get_service_client as get_client

SAMPLES = [
    "samples/complete-blood-count-(cbc).pdf",
    "samples/lipid-profile-test.pdf",
    "samples/liver-function-tests-(lft).pdf",
]

for pdf_path in SAMPLES:
    print("\n" + "=" * 60)
    print(f"FILE: {os.path.basename(pdf_path)}")
    print("=" * 60)

    result = ingest(pdf_path)
    report_id = result.report_id
    print(f"report_id: {report_id} (path: {result.extraction_path})")

    report_meta = (
        get_client()
        .from_("reports")
        .select("report_date, lab_name, patient_age, patient_gender")
        .eq("id", report_id)
        .single()
        .execute()
        .data
    )
    print(f"  report_date:    {report_meta.get('report_date')}")
    print(f"  lab_name:       {report_meta.get('lab_name')}")
    print(f"  patient_age:    {report_meta.get('patient_age')}")
    print(f"  patient_gender: {report_meta.get('patient_gender')}")

    markers = (
        get_client()
        .from_("markers")
        .select("name, value, unit, ref_low, ref_high, flag")
        .eq("report_id", report_id)
        .execute()
        .data
    )

    print(f"Markers extracted: {len(markers)}")
    print(f"{'Name':<40} {'Value':>8} {'Unit':<12} {'Ref Low':>8} {'Ref High':>9} {'Flag':<8}")
    print("-" * 95)
    for m in markers:
        val = "" if m['value'] is None else str(m['value'])
        low = "" if m['ref_low'] is None else str(m['ref_low'])
        high = "" if m['ref_high'] is None else str(m['ref_high'])
        print(
            f"{str(m['name']):<40} "
            f"{val:>8} "
            f"{str(m['unit'] or ''):<12} "
            f"{low:>8} "
            f"{high:>9} "
            f"{str(m['flag'] or ''):<8}"
        )

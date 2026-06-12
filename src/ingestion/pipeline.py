from src.ingestion.pdf_parser import extract_text_from_pdf
from src.ingestion.marker_extractor import extract_markers
from src.ingestion.report_metadata import extract_metadata
from src.db.supabase_client import insert_report, insert_markers, get_existing_report
from src.ingestion.embedder import embed_report


def ingest(pdf_path: str) -> str:
    text = extract_text_from_pdf(pdf_path)
    metadata = extract_metadata(text)

    existing_id = get_existing_report(metadata.lab_name, str(metadata.report_date))
    if existing_id:
        print(f"Report already exists: {existing_id} — skipping ingestion")
        return existing_id

    markers = extract_markers(text)
    report_id = insert_report(metadata, text)
    insert_markers(report_id, markers)
    embed_report(report_id, markers)
    return report_id

import logging

from src.ingestion.pdf_parser import extract_text_from_pdf, is_lpl_format
from src.ingestion.marker_extractor import extract_markers, compute_flag
from src.ingestion.llm_extractor import extract_with_llm
from src.ingestion.report_metadata import extract_metadata
from src.db.supabase_client import insert_report, insert_markers, get_existing_report
from src.ingestion.embedder import embed_report

logger = logging.getLogger(__name__)


def ingest(pdf_path: str) -> str:
    text = extract_text_from_pdf(pdf_path)
    metadata = extract_metadata(text)

    _lab = metadata.lab_name
    _date = str(metadata.report_date) if metadata.report_date is not None else None
    if _lab and _date and _date != "None":
        existing_id = get_existing_report(_lab, _date)
        if existing_id:
            print(f"Report already exists: {existing_id} — skipping ingestion")
            return existing_id

    if is_lpl_format(text):
        markers = extract_markers(text)
        logger.info("Extraction path: regex (LPL format, %d markers)", len(markers))
    else:
        llm_result = extract_with_llm(text)
        markers = llm_result.markers
        logger.info("Extraction path: llm (non-LPL format, %d markers)", len(markers))

        llm_meta = llm_result.metadata
        if metadata.report_date is None and llm_meta.report_date:
            metadata.report_date = llm_meta.report_date
        if metadata.lab_name is None and llm_meta.lab_name:
            metadata.lab_name = llm_meta.lab_name
        if metadata.patient_age is None and llm_meta.patient_age:
            metadata.patient_age = llm_meta.patient_age
        if metadata.patient_gender is None and llm_meta.patient_gender:
            metadata.patient_gender = llm_meta.patient_gender

        logger.info("Resolved metadata — lab_name: %s, report_date: %s", metadata.lab_name, metadata.report_date)

    for m in markers:
        m.flag = compute_flag(m.value, m.ref_low, m.ref_high)

    report_id = insert_report(metadata, text)
    insert_markers(report_id, markers)
    embed_report(report_id, markers)
    return report_id

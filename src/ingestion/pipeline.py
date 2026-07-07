import logging
from dataclasses import dataclass

from src.ingestion.pdf_parser import extract_text_from_pdf, is_lpl_format
from src.ingestion.marker_extractor import extract_markers, compute_flag
from src.ingestion.llm_extractor import extract_with_llm
from src.ingestion.errors import ExtractionError
from src.ingestion.report_metadata import extract_metadata
from src.db.supabase_client import insert_report, insert_markers, get_existing_report
from src.ingestion.embedder import embed_report

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    report_id: str
    n_total: int
    n_flagged: int
    extraction_path: str  # "regex" | "llm" | "dedup"


def ingest(pdf_path: str) -> IngestResult:
    text = extract_text_from_pdf(pdf_path)

    # Fail before the LLM sees near-empty text: given a blank page, the
    # extractor fabricates a plausible report (observed: "MedLab", invented
    # glucose/urea rows) instead of returning nothing.
    if len(text.strip()) < 100:
        raise ExtractionError(
            "This PDF contains no readable text — it may be scanned or empty. "
            "Scanned PDFs are not supported yet."
        )

    metadata = extract_metadata(text)

    if is_lpl_format(text):
        markers = extract_markers(text)
        extraction_path = "regex"
        logger.info("Extraction path: regex (LPL format, %d markers)", len(markers))
    else:
        llm_result = extract_with_llm(text)
        markers = llm_result.markers
        extraction_path = "llm"
        logger.info("Extraction path: llm (non-LPL format, %d markers)", len(markers))
        metadata.merge_missing_from(llm_result.metadata)
        logger.info("Resolved metadata — lab_name: %s, report_date: %s", metadata.lab_name, metadata.report_date)

    if not markers:
        raise ExtractionError("No test results could be extracted from this PDF.")

    # Dedup only after metadata is fully resolved — before the LLM merge,
    # non-LPL reports had no lab/date and every re-upload inserted a duplicate.
    _lab = metadata.lab_name
    _date = str(metadata.report_date) if metadata.report_date is not None else None
    if _lab and _date and _date != "None":
        existing_id = get_existing_report(_lab, _date)
        if existing_id:
            logger.info("Report already exists: %s — skipping ingestion", existing_id)
            return IngestResult(existing_id, 0, 0, "dedup")

    for m in markers:
        m.flag = compute_flag(m.value, m.ref_low, m.ref_high)

    report_id = insert_report(metadata, text)
    insert_markers(report_id, markers)
    embed_report(report_id, markers)

    n_flagged = sum(1 for m in markers if m.flag and m.flag != "normal")
    return IngestResult(report_id, len(markers), n_flagged, extraction_path)

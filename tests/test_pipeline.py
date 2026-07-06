import pytest

import src.ingestion.pipeline as pipeline
from src.ingestion.errors import ExtractionError
from src.ingestion.llm_extractor import ExtractedMetadata, ExtractionResult
from src.ingestion.marker_extractor import Marker

# Non-LPL text: long enough to pass the empty-text guard, no header fields the
# regex metadata extractor recognises, no "l p l-rohini" signature.
NON_LPL_TEXT = (
    "ACME DIAGNOSTICS test report for routine health screening. "
    "The following biochemical parameters were measured on an automated analyser. "
    "Values outside the reference interval are marked accordingly."
)

LLM_MARKERS = [
    Marker(name="Glucose", value=100.0, unit="mg/dL", ref_low=70.0, ref_high=110.0),
    Marker(name="Urea", value=55.0, unit="mg/dL", ref_low=10.0, ref_high=40.0),
]


@pytest.fixture
def mocks(monkeypatch):
    """Patch every side-effecting collaborator; return the call log."""
    calls = {"get_existing_report": [], "insert_report": [], "insert_markers": [], "embed_report": [], "llm": 0}

    monkeypatch.setattr(pipeline, "extract_text_from_pdf", lambda path: NON_LPL_TEXT)

    def fake_llm(text):
        calls["llm"] += 1
        return ExtractionResult(
            metadata=ExtractedMetadata(report_date="2026-01-15", lab_name="ACME DIAGNOSTICS"),
            markers=[m.model_copy() for m in LLM_MARKERS],
        )
    monkeypatch.setattr(pipeline, "extract_with_llm", fake_llm)

    def fake_get_existing(lab, date):
        calls["get_existing_report"].append((lab, date))
        return None
    monkeypatch.setattr(pipeline, "get_existing_report", fake_get_existing)

    def fake_insert_report(metadata, text):
        calls["insert_report"].append(metadata)
        return "new-report-id"
    monkeypatch.setattr(pipeline, "insert_report", fake_insert_report)
    monkeypatch.setattr(pipeline, "insert_markers", lambda rid, markers: calls["insert_markers"].append(markers))
    monkeypatch.setattr(pipeline, "embed_report", lambda rid, markers: calls["embed_report"].append(markers))

    return calls


def test_llm_path_inserts_and_flags(mocks):
    result = pipeline.ingest("whatever.pdf")
    assert result.report_id == "new-report-id"
    assert result.extraction_path == "llm"
    assert result.n_total == 2
    assert result.n_flagged == 1  # Urea 55 > 40; flags recomputed deterministically
    assert mocks["insert_markers"][0][1].flag == "high"


def test_dedup_uses_llm_merged_metadata(mocks, monkeypatch):
    # Regex metadata finds nothing in NON_LPL_TEXT, so the dedup lookup must
    # only happen with the LLM-provided lab/date — i.e. after the merge.
    monkeypatch.setattr(pipeline, "get_existing_report", lambda lab, date: "existing-id")
    result = pipeline.ingest("whatever.pdf")
    assert result.extraction_path == "dedup"
    assert result.report_id == "existing-id"
    assert mocks["insert_report"] == []  # nothing re-inserted


def test_dedup_lookup_receives_resolved_fields(mocks):
    pipeline.ingest("whatever.pdf")
    assert mocks["get_existing_report"] == [("ACME DIAGNOSTICS", "2026-01-15")]


def test_zero_markers_raises(mocks, monkeypatch):
    monkeypatch.setattr(
        pipeline, "extract_with_llm",
        lambda text: ExtractionResult(metadata=ExtractedMetadata(), markers=[]),
    )
    with pytest.raises(ExtractionError):
        pipeline.ingest("whatever.pdf")
    assert mocks["insert_report"] == []


def test_near_empty_text_fails_before_llm(mocks, monkeypatch):
    monkeypatch.setattr(pipeline, "extract_text_from_pdf", lambda path: "   \n  ")
    with pytest.raises(ExtractionError):
        pipeline.ingest("whatever.pdf")
    assert mocks["llm"] == 0  # the fabrication-prone LLM call must never fire


def test_lpl_text_uses_regex_not_llm(mocks, monkeypatch):
    lpl_text = (
        "Collected at: L P L-ROHINI (NATIONAL REFERENCE LAB)\n"
        "Hemoglobin 15.00 g/dL 13.00 - 17.00\n"
        "ESR 25 mm/hr < 15\n"
    ) + NON_LPL_TEXT  # padding past the empty-text guard
    monkeypatch.setattr(pipeline, "extract_text_from_pdf", lambda path: lpl_text)
    result = pipeline.ingest("whatever.pdf")
    assert result.extraction_path == "regex"
    assert mocks["llm"] == 0
    assert result.n_total == 2
    assert result.n_flagged == 1  # ESR high

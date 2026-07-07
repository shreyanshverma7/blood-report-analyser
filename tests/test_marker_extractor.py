from pathlib import Path

import pytest

from src.ingestion.marker_extractor import compute_flag, extract_markers
from src.ingestion.pdf_parser import is_lpl_format

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


class TestComputeFlag:
    def test_no_value_is_none(self):
        assert compute_flag(None, 1.0, 2.0) is None

    def test_no_ranges_is_none(self):
        assert compute_flag(5.0, None, None) is None

    def test_high(self):
        assert compute_flag(2.5, 1.0, 2.0) == "high"

    def test_low(self):
        assert compute_flag(0.5, 1.0, 2.0) == "low"

    def test_normal(self):
        assert compute_flag(1.5, 1.0, 2.0) == "normal"

    def test_genuine_zero_is_low_not_missing(self):
        # Basophils 0 vs ref_low 0.02 — 0.0 must not be treated as "no value"
        assert compute_flag(0.0, 0.02, 0.10) == "low"

    def test_boundary_values_are_normal(self):
        assert compute_flag(2.0, 1.0, 2.0) == "normal"
        assert compute_flag(1.0, 1.0, 2.0) == "normal"

    def test_ref_high_only(self):
        assert compute_flag(3.0, None, 2.0) == "high"
        assert compute_flag(1.0, None, 2.0) == "normal"

    def test_ref_low_only(self):
        assert compute_flag(0.5, 1.0, None) == "low"
        assert compute_flag(1.5, 1.0, None) == "normal"


class TestExtractMarkers:
    def test_basic_row(self):
        [m] = extract_markers("Hemoglobin 15.00 g/dL 13.00 - 17.00")
        assert m.name == "Hemoglobin"
        assert m.value == 15.0
        assert m.unit == "g/dL"
        assert (m.ref_low, m.ref_high) == (13.0, 17.0)
        assert m.flag == "normal"

    def test_upper_bound_only_ref(self):
        [m] = extract_markers("ESR 25 mm/hr < 15")
        assert m.ref_high == 15.0 and m.ref_low is None
        assert m.flag == "high"

    def test_text_result_row(self):
        [m] = extract_markers("GFR Category G1")
        assert m.value_text == "G1" and m.value is None

    def test_single_lowercase_word_dropped(self):
        assert extract_markers("glucose 100") == []

    def test_footnote_year_row_dropped(self):
        line = "As per Clinical Guidelines Committee recommendation 2019"
        assert extract_markers(line) == []

    def test_lines_without_digits_skipped(self):
        assert extract_markers("COMPLETE BLOOD COUNT\nInterpretation follows") == []


class TestIsLplFormat:
    def test_lpl_signature_case_insensitive(self):
        assert is_lpl_format("Collected at: L P L-ROHINI (NATIONAL REFERENCE LAB)")

    def test_other_lab_is_not_lpl(self):
        assert not is_lpl_format("Collected at: Metropolis Healthcare, Mumbai")


@pytest.mark.skipif(
    not (SAMPLES / "WM17S.pdf").exists(),
    reason="local-only sample PDF (gitignored, contains PHI)",
)
class TestWm17sRegression:
    def test_57_marker_baseline(self):
        from src.ingestion.pdf_parser import extract_text_from_pdf

        text = extract_text_from_pdf(str(SAMPLES / "WM17S.pdf"))
        assert is_lpl_format(text)
        markers = extract_markers(text)
        assert len(markers) == 57  # v2 baseline — see PLAN.md T1.8

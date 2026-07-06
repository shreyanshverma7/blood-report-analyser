from src.export.pdf_generator import _fmt, _latin1_safe, _ref_range


class TestRefRange:
    def test_both_bounds(self):
        assert _ref_range(1.0, 2.0) == "1.0 - 2.0"

    def test_high_only(self):
        assert _ref_range(None, 2.0) == "< 2.0"

    def test_low_only(self):
        assert _ref_range(1.0, None) == "> 1.0"

    def test_neither(self):
        assert _ref_range(None, None) == "-"


class TestFmt:
    def test_none_is_dash(self):
        assert _fmt(None) == "-"

    def test_zero_renders_not_blank(self):
        assert _fmt(0.0) == "0.0"


class TestLatin1Safe:
    def test_em_dash_and_curly_quotes_transliterated(self):
        assert _latin1_safe("normal — it’s “fine”…") == 'normal - it\'s "fine"...'

    def test_unmappable_chars_replaced_not_raising(self):
        out = _latin1_safe("value ↑ high")
        out.encode("latin-1")  # must be encodable now

    def test_micro_sign_survives(self):
        assert _latin1_safe("µL") == "µL"  # µ is in latin-1

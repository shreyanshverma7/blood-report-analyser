from src.agent.response_parser import parse_agent_response, strip_json_block

VALID = (
    "Your ALP is elevated.\n"
    "<json>\n"
    '{"summary": "ALP is high.", '
    '"flagged_markers": [{"name": "ALP", "value": 150, "unit": "U/L", "flag": "high"}], '
    '"recommendations": ["Discuss with your doctor"], "sources": ["liver-panel"]}\n'
    "</json>"
)

MALFORMED = "Prose answer.\n<json>\n{not valid json,,,\n</json>"

NO_BLOCK = "Just a plain markdown answer with no envelope."


def test_valid_block_parses():
    resp = parse_agent_response(VALID)
    assert resp is not None
    assert resp.summary == "ALP is high."
    assert resp.flagged_markers[0].name == "ALP"
    assert resp.flagged_markers[0].value == 150
    assert resp.recommendations == ["Discuss with your doctor"]


def test_malformed_block_returns_none():
    assert parse_agent_response(MALFORMED) is None


def test_missing_block_returns_none():
    assert parse_agent_response(NO_BLOCK) is None


def test_last_block_wins():
    two = VALID + '\n<json>\n{"summary": "second"}\n</json>'
    assert parse_agent_response(two).summary == "second"


def test_zero_value_preserved():
    text = '<json>{"summary": "s", "flagged_markers": [{"name": "Basophils", "value": 0.0}]}</json>'
    assert parse_agent_response(text).flagged_markers[0].value == 0.0


def test_strip_removes_block_keeps_prose():
    assert strip_json_block(VALID) == "Your ALP is elevated."


def test_strip_safe_on_malformed():
    assert strip_json_block(MALFORMED) == "Prose answer."


def test_strip_noop_without_block():
    assert strip_json_block(NO_BLOCK) == NO_BLOCK

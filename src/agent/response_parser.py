import re

from src.agent.response_model import AgentResponse

_JSON_BLOCK = re.compile(r"<json>\s*(.*?)\s*</json>", re.DOTALL)


def parse_agent_response(text: str) -> AgentResponse | None:
    """Extract and validate the <json> envelope. Returns None on any failure
    (missing block, malformed JSON, schema mismatch) so the caller can fall
    back to raw markdown."""
    matches = _JSON_BLOCK.findall(text)
    if not matches:
        return None
    raw = matches[-1]
    try:
        return AgentResponse.model_validate_json(raw)
    except Exception:
        return None


def strip_json_block(text: str) -> str:
    """Remove the <json>...</json> block (and surrounding whitespace) from the
    text, leaving just the natural-language prose. Safe to call even when the
    JSON is malformed — it's a pure text removal, no parsing required."""
    return _JSON_BLOCK.sub("", text).strip()

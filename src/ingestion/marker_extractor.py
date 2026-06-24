import re
from typing import List, Optional
from pydantic import BaseModel


class Marker(BaseModel):
    name: str
    value: Optional[float] = None
    value_text: Optional[str] = None
    unit: Optional[str] = None
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None
    flag: Optional[str] = None


# Ref interval anchored to end of line
_REF_SUFFIX = re.compile(
    r"\s+(?:(\d+\.?\d*)\s*-\s*(\d+\.?\d*)|<\s*(\d+\.?\d*)|>\s*(\d+\.?\d*))$"
)

# Lines to skip unconditionally
_SKIP_LINE = re.compile(
    r"^("
    r"Name\s*:|Lab No\.|Ref By\s*:|Collected\s*:|A/c Status|Report Status|"
    r"Collected at\s*:|Processed at\s*:|National Reference|DELHI|Test Report|"
    r"Test Name|SwasthFit|Page \d+ of|\*\d+\*|\.$|"
    r"\d+\.\s|Note$|Note\s*\d|^\|"
    r")"
)

_METHOD_LINE = re.compile(r"^\(.*\)$")

# A purely numeric token
_NUMERIC = re.compile(r"^\d+\.?\d*$")


def compute_flag(
    value: Optional[float],
    ref_low: Optional[float],
    ref_high: Optional[float],
) -> Optional[str]:
    """Deterministic high/low/normal from numeric bounds. Single source of truth for flags."""
    if value is None:
        return None
    if ref_high is not None and value > ref_high:
        return "high"
    if ref_low is not None and value < ref_low:
        return "low"
    if ref_low is not None or ref_high is not None:
        return "normal"
    return None


def _parse_line(line: str) -> Optional[Marker]:
    """
    Parse right-to-left:
    1. Strip ref interval suffix if present
    2. Strip unit (last non-numeric token) if present
    3. Strip value (last numeric token)
    4. Remainder = name
    """
    remainder = line

    # Step 1: strip ref interval from end
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None
    m = _REF_SUFFIX.search(remainder)
    if m:
        remainder = remainder[: m.start()]
        if m.group(1) is not None:
            ref_low, ref_high = float(m.group(1)), float(m.group(2))
        elif m.group(3) is not None:
            ref_high = float(m.group(3))
        elif m.group(4) is not None:
            ref_low = float(m.group(4))

    tokens = remainder.split()
    if not tokens:
        return None

    # Step 2: check last token — if non-numeric, treat as unit
    unit: Optional[str] = None
    if not _NUMERIC.match(tokens[-1]):
        # Could be a unit like "g/dL", "%", "thou/mm3", or a text result like "G1"
        # If the second-to-last token is numeric, last token is the unit
        if len(tokens) >= 2 and _NUMERIC.match(tokens[-2]):
            unit = tokens.pop()
        elif len(tokens) >= 2 and not _NUMERIC.match(tokens[-2]):
            # Last token is non-numeric and second-to-last is also non-numeric:
            # might be a text-result line like "GFR Category G1"
            # Only treat as text result if the last token looks like a category code
            if re.match(r"^[A-Z]\d+\w*$", tokens[-1]):
                value_text = tokens.pop()
                name = " ".join(tokens)
                return Marker(name=name, value_text=value_text)
            return None

    # Step 3: last token must now be numeric (the value)
    if not tokens or not _NUMERIC.match(tokens[-1]):
        return None

    value = float(tokens.pop())
    if not tokens:
        return None

    name = " ".join(tokens)

    flag = compute_flag(value, ref_low, ref_high)
    return Marker(
        name=name, value=value, unit=unit,
        ref_low=ref_low, ref_high=ref_high, flag=flag,
    )


def extract_markers(raw_text: str) -> List[Marker]:
    markers: List[Marker] = []

    for line in raw_text.splitlines():
        line = line.strip()

        if not line:
            continue
        if _SKIP_LINE.search(line):
            continue
        if _METHOD_LINE.match(line):
            continue
        # Skip lines with no digits at all (section headers, notes)
        if not re.search(r"\d", line):
            continue
        # Skip table-header, footnote-style, and bullet lines
        if line.startswith("|") or line.startswith("*") or line.startswith("·") or line.startswith("•"):
            continue

        marker = _parse_line(line)
        if marker:
            # Drop footnote lines: year-like value (1900–2099) with a long name
            if (
                marker.value is not None
                and 1900 <= marker.value <= 2099
                and marker.value == int(marker.value)
                and len(marker.name) > 30
            ):
                continue
            # Drop prose leakage: single all-lowercase word is never a marker name
            if marker.name == marker.name.lower() and " " not in marker.name:
                continue
            markers.append(marker)

    return markers

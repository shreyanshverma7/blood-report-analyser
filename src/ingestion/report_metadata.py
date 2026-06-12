import re
from typing import Optional
from pydantic import BaseModel


class ReportMetadata(BaseModel):
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    report_date: Optional[str] = None
    lab_name: Optional[str] = None


_AGE = re.compile(r"Age\s*:\s*(\d+)\s*Years", re.IGNORECASE)
_GENDER = re.compile(r"Gender\s*:\s*(Male|Female)", re.IGNORECASE)
_DATE = re.compile(r"Collected\s*:\s*(\d{1,2}/\d{1,2}/\d{4})")
_LAB = re.compile(r"Collected at\s*:\s*(.+?)\s*Processed at\s*:", re.IGNORECASE)


def _parse_date(raw: str) -> Optional[str]:
    try:
        day, month, year = raw.split("/")
        return f"{year}-{int(month):02d}-{int(day):02d}"
    except Exception:
        return None


def extract_metadata(raw_text: str) -> ReportMetadata:
    # Only look at the first 15 lines — header repeats on every page, one pass is enough
    header = "\n".join(raw_text.splitlines()[:15])

    age = None
    m = _AGE.search(header)
    if m:
        age = int(m.group(1))

    gender = None
    m = _GENDER.search(header)
    if m:
        gender = m.group(1).capitalize()

    report_date = None
    m = _DATE.search(header)
    if m:
        report_date = _parse_date(m.group(1))

    lab_name = None
    m = _LAB.search(header)
    if m:
        # Clean up OCR-spaced single letters like "L P L" → "LPL"
        # Only collapse spaces between isolated single uppercase letters
        raw_lab = m.group(1).strip()
        lab_name = re.sub(r"(?<!\w)([A-Z])\s(?=[A-Z](?:\s|-))", r"\1", raw_lab)

    return ReportMetadata(
        patient_age=age,
        patient_gender=gender,
        report_date=report_date,
        lab_name=lab_name,
    )

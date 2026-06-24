import logging
import os
from typing import List, Optional

from langchain_groq import ChatGroq
from pydantic import BaseModel

from src.ingestion.marker_extractor import Marker

logger = logging.getLogger(__name__)


class ExtractedMetadata(BaseModel):
    report_date: Optional[str] = None   # ISO format YYYY-MM-DD if determinable, else None
    lab_name: Optional[str] = None
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None  # "Male" / "Female" / None


class ExtractionResult(BaseModel):
    metadata: ExtractedMetadata
    markers: List[Marker]


_SYSTEM_PROMPT = (
    "You are a medical lab report parser. Given the raw text of a lab report, extract two things:\n\n"
    "1. REPORT HEADER METADATA — from the patient/report header section:\n"
    "   - report_date: the report or collection date, normalised to YYYY-MM-DD. Return null if you cannot determine it.\n"
    "   - lab_name: the name of the diagnostic centre or laboratory. Return null if not found.\n"
    "   - patient_age: the patient's age as an integer. Return null if not found.\n"
    "   - patient_gender: exactly 'Male' or 'Female'. Return null if not found or ambiguous.\n\n"
    "2. TEST RESULTS — every row in the results table:\n"
    "   - name: test name\n"
    "   - value: numeric result (float)\n"
    "   - unit: unit string (e.g. mg/dL, g/dL, %)\n"
    "   - ref_low and ref_high: numeric bounds from the reference range\n"
    "   - flag: 'high' if value > ref_high, 'low' if value < ref_low, 'normal' otherwise\n\n"
    "Only extract test rows that have a numeric value and a reference range. "
    "Skip headers, footnotes, and non-test rows. "
    "Return null for any metadata field you genuinely cannot find — do not guess."
)


def extract_with_llm(raw_text: str) -> ExtractionResult:
    try:
        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=os.getenv("GROQ_API_KEY"),
        ).with_structured_output(ExtractionResult)

        result: ExtractionResult = llm.invoke([
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ])
        return result
    except Exception as e:
        logger.error("LLM extraction failed: %s", e)
        return ExtractionResult(metadata=ExtractedMetadata(), markers=[])

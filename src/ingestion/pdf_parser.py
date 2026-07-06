import pdfplumber

from src.ingestion.errors import ExtractionError

# Real lab reports run ~1-15 pages; the cap blocks decompression-bomb PDFs
# from tying up the shared Community Cloud instance.
_MAX_PAGES = 40


def extract_text_from_pdf(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) > _MAX_PAGES:
            raise ExtractionError(
                f"PDF has {len(pdf.pages)} pages — the limit is {_MAX_PAGES}."
            )
        return "\n".join(
            page.extract_text() or "" for page in pdf.pages
        )


def is_lpl_format(text: str) -> bool:
    """True only when the raw text matches the LPL-Rohini layout the regex extractor was built for."""
    return "l p l-rohini" in text.lower()

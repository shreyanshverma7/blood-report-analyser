import pdfplumber


def extract_text_from_pdf(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(
            page.extract_text() or "" for page in pdf.pages
        )


def is_lpl_format(text: str) -> bool:
    """True only when the raw text matches the LPL-Rohini layout the regex extractor was built for."""
    return "l p l-rohini" in text.lower()

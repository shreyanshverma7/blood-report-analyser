class ExtractionError(Exception):
    """Ingestion could not produce usable data. Messages are user-safe —
    the UI shows them verbatim, so never include internals or secrets."""

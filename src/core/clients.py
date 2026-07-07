"""Shared heavyweight clients — one embedding model (~90 MB resident) and one
Qdrant client per process, whichever module asks first."""
import os

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from src import config  # noqa: F401 — loads env before any client is built

_MODEL = None
_QDRANT = None


def get_embedding_model() -> SentenceTransformer:
    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _MODEL


def get_qdrant() -> QdrantClient:
    global _QDRANT
    if _QDRANT is None:
        _QDRANT = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"])
    return _QDRANT

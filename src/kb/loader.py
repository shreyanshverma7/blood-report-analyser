import os
import uuid
from glob import glob
from typing import List
from qdrant_client.models import PointStruct

from src.core.clients import get_embedding_model, get_qdrant

_SOURCES_DIR = os.path.join(os.path.dirname(__file__), "sources")
_CHUNK_WORDS = 400
_OVERLAP_WORDS = 50


def _chunk_text(text: str) -> List[str]:
    # Split on paragraph or sentence boundaries
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    chunks: List[str] = []
    current_words: List[str] = []

    for para in paragraphs:
        para_words = para.split()
        current_words.extend(para_words)

        if len(current_words) >= _CHUNK_WORDS:
            chunks.append(" ".join(current_words))
            # Keep last N words as overlap for next chunk
            current_words = current_words[-_OVERLAP_WORDS:]

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


def load_kb() -> None:
    txt_files = sorted(glob(os.path.join(_SOURCES_DIR, "*.txt")))
    all_points: List[PointStruct] = []

    for filepath in txt_files:
        filename = os.path.basename(filepath)
        source = os.path.splitext(filename)[0]

        with open(filepath, encoding="utf-8") as f:
            text = f.read()

        chunks = _chunk_text(text)
        embeddings = get_embedding_model().encode(chunks, normalize_embeddings=True)

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{filename}:{i}"))
            all_points.append(PointStruct(
                id=point_id,
                vector=embedding.tolist(),
                payload={"source": source, "chunk_index": i, "text": chunk},
            ))

    batch_size = 100
    for i in range(0, len(all_points), batch_size):
        get_qdrant().upsert(collection_name="medical_kb", points=all_points[i : i + batch_size])

    print(f"Loaded {len(all_points)} chunks from {len(txt_files)} files into medical_kb")

import os
import uuid
from glob import glob
from typing import List
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

load_dotenv()

_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
_QDRANT = QdrantClient(
    url=os.environ["QDRANT_URL"],
    api_key=os.environ["QDRANT_API_KEY"],
)

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
        embeddings = _MODEL.encode(chunks, normalize_embeddings=True)

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{filename}:{i}"))
            all_points.append(PointStruct(
                id=point_id,
                vector=embedding.tolist(),
                payload={"source": source, "chunk_index": i, "text": chunk},
            ))

    batch_size = 100
    for i in range(0, len(all_points), batch_size):
        _QDRANT.upsert(collection_name="medical_kb", points=all_points[i : i + batch_size])

    print(f"Loaded {len(all_points)} chunks from {len(txt_files)} files into medical_kb")

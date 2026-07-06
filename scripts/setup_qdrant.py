import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from src import config

config.validate()

client = QdrantClient(
    url=os.environ["QDRANT_URL"],
    api_key=os.environ["QDRANT_API_KEY"],
)

COLLECTIONS = {
    "report_chunks": VectorParams(size=384, distance=Distance.COSINE),
    "medical_kb": VectorParams(size=384, distance=Distance.COSINE),
}

existing = {c.name for c in client.get_collections().collections}

for name, params in COLLECTIONS.items():
    if name in existing:
        print(f"  skipped {name!r} — already exists")
    else:
        client.create_collection(collection_name=name, vectors_config=params)
        print(f"  created {name!r}")

print("\nAll collections:")
for c in client.get_collections().collections:
    info = client.get_collection(c.name)
    cfg = info.config.params.vectors
    print(f"  {c.name}: size={cfg.size}, distance={cfg.distance}")

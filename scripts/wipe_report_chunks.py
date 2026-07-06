"""One-time companion to scripts/setup_auth.sql: drop and recreate the
report_chunks collection so no pre-auth (unowned) embeddings survive the
migration. The shared medical_kb collection is untouched."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from qdrant_client.models import Distance, VectorParams

from src import config
from src.core.clients import get_qdrant

config.validate()

client = get_qdrant()

answer = input("Drop and recreate 'report_chunks' (deletes ALL report embeddings)? [y/N] ")
if answer.strip().lower() != "y":
    print("aborted")
    sys.exit(1)

client.delete_collection("report_chunks")
client.create_collection(
    collection_name="report_chunks",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
)
print("report_chunks recreated empty")

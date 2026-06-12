import os
import uuid
from typing import List, Dict
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from src.ingestion.marker_extractor import Marker

load_dotenv()

_MODEL = None
_QDRANT = None


def _get_model():
    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _MODEL


def _get_qdrant():
    global _QDRANT
    if _QDRANT is None:
        _QDRANT = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"])
    return _QDRANT

_PANEL_KEYWORDS: Dict[str, List[str]] = {
    "CBC": [
        "hemoglobin", "pcv", "packed cell", "rbc", "mcv", "mch", "mchc", "rdw",
        "leukocyte", "tlc", "neutrophil", "lymphocyte", "monocyte", "eosinophil",
        "basophil", "platelet", "mpv", "mean platelet",
    ],
    "Liver": [
        "ast", "sgot", "alt", "sgpt", "ggtp", "alkaline phosphatase", "alp",
        "bilirubin", "total protein", "albumin", "globulin", "a : g", "a:g",
    ],
    "Kidney": [
        "creatinine", "gfr", "urea", "bun", "uric acid", "calcium",
        "phosphorus", "sodium", "potassium", "chloride",
    ],
    "Lipid": [
        "cholesterol", "triglyceride", "hdl", "ldl", "vldl", "non-hdl",
    ],
    "Thyroid": ["t3", "t4", "tsh"],
    "Vitamins": ["vitamin b12", "vitamin d", "cyanocobalamin", "hydroxy", "folate", "hba1c", "glucose"],
}


def _assign_panel(name: str) -> str:
    lower = name.lower()
    for panel, keywords in _PANEL_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return panel
    return "Other"


def build_summary(panel_name: str, markers: List[Marker]) -> str:
    parts = [f"{panel_name} panel:"]
    for m in markers:
        if m.value is not None:
            flag_str = f" ({m.flag.upper()})" if m.flag and m.flag != "normal" else " (normal)"
            ref_str = ""
            if m.ref_low is not None and m.ref_high is not None:
                ref_str = f", ref {m.ref_low}-{m.ref_high}"
            elif m.ref_high is not None:
                ref_str = f", ref <{m.ref_high}"
            elif m.ref_low is not None:
                ref_str = f", ref >{m.ref_low}"
            unit_str = f" {m.unit}" if m.unit else ""
            parts.append(f"{m.name} {m.value}{unit_str}{flag_str}{ref_str}")
        elif m.value_text is not None:
            parts.append(f"{m.name} {m.value_text}")
    return " | ".join(parts)


def embed_report(report_id: str, markers: List[Marker]) -> None:
    # Group markers by panel
    groups: Dict[str, List[Marker]] = {}
    for m in markers:
        panel = _assign_panel(m.name)
        groups.setdefault(panel, []).append(m)

    # Build summaries and embed
    summaries = {panel: build_summary(panel, panel_markers) for panel, panel_markers in groups.items()}
    texts = list(summaries.values())
    embeddings = _get_model().encode(texts, normalize_embeddings=True)

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=embeddings[i].tolist(),
            payload={
                "report_id": report_id,
                "panel": panel,
                "summary_text": summaries[panel],
            },
        )
        for i, panel in enumerate(summaries)
    ]

    _get_qdrant().upsert(collection_name="report_chunks", points=points)

import uuid
from typing import List, Dict
from qdrant_client.models import PointStruct

from src.core.clients import get_embedding_model, get_qdrant
from src.ingestion.marker_extractor import Marker

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
            if m.flag and m.flag != "normal":
                flag_str = f" ({m.flag.upper()})"
            elif m.flag == "normal":
                flag_str = " (normal)"
            else:
                # flag is None when there's no reference range — don't assert normality
                flag_str = " (no reference range)"
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
    if not markers:
        return  # encode([]) and upsert(points=[]) both raise

    # Group markers by panel
    groups: Dict[str, List[Marker]] = {}
    for m in markers:
        panel = _assign_panel(m.name)
        groups.setdefault(panel, []).append(m)

    # Build summaries and embed
    summaries = {panel: build_summary(panel, panel_markers) for panel, panel_markers in groups.items()}
    texts = list(summaries.values())
    embeddings = get_embedding_model().encode(texts, normalize_embeddings=True)

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

    get_qdrant().upsert(collection_name="report_chunks", points=points)

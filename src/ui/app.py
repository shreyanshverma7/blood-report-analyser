import sys
import os
from pathlib import Path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Load .env first (override=True so blank secrets.toml values don't win locally)
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env", override=True)

try:
    import streamlit as st
    for key in [
        "GROQ_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_KEY",
        "QDRANT_URL", "QDRANT_API_KEY", "LANGCHAIN_API_KEY",
        "LANGCHAIN_TRACING_V2", "LANGCHAIN_PROJECT",
    ]:
        if key in st.secrets and st.secrets[key]:
            os.environ[key] = st.secrets[key]
except Exception:
    pass

import uuid
import tempfile

import streamlit as st
from langchain_core.messages import HumanMessage

from src.ingestion.pipeline import ingest
from src.ingestion.pdf_parser import extract_text_from_pdf
from src.ingestion.marker_extractor import extract_markers
from src.agent.graph import create_graph
from src.agent.response_parser import parse_agent_response, strip_json_block
from src.db.supabase_client import get_reports

# ── Response renderer ─────────────────────────────────────────────────────────
FLAG_COLORS = {"high": "red", "low": "orange", "normal": "green"}


def render_assistant_message(text: str):
    """Render an assistant turn as structured cards when the <json> envelope
    parses, else as plain markdown with the raw block stripped."""
    resp = parse_agent_response(text)
    if resp is None:
        st.markdown(strip_json_block(text))
        return

    st.markdown(resp.summary)

    if resp.flagged_markers:
        st.markdown("**Flagged markers**")
        for m in resp.flagged_markers:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 1])
                c1.markdown(f"**{m.name}**")
                value = "—" if m.value is None else str(m.value)
                unit = f" {m.unit}" if m.unit else ""
                c2.markdown(f"{value}{unit}")
                color = FLAG_COLORS.get((m.flag or "").lower(), "gray")
                c3.markdown(f":{color}[{(m.flag or 'N/A').upper()}]")

    if resp.recommendations:
        st.markdown("**Recommendations**")
        for r in resp.recommendations:
            st.markdown(f"- {r}")

    if resp.sources:
        st.caption("Sources: " + ", ".join(resp.sources))


# ── Module-level singletons ───────────────────────────────────────────────────
_graph = create_graph()

# ── Session state defaults ────────────────────────────────────────────────────
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_report_id" not in st.session_state:
    st.session_state.selected_report_id = None
if "ingested_files" not in st.session_state:
    st.session_state.ingested_files = set()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Blood Report Analyser")

    uploaded = st.file_uploader("Upload Blood Report PDF", type=["pdf"])
    if uploaded is not None and uploaded.name not in st.session_state.ingested_files:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name
        with st.spinner("Ingesting report…"):
            _text = extract_text_from_pdf(tmp_path)
            _markers = extract_markers(_text)
            n_total = len(_markers)
            n_flagged = sum(1 for m in _markers if m.flag and m.flag != "normal")
            report_id = ingest(tmp_path)
            os.unlink(tmp_path)
        st.session_state.ingested_files.add(uploaded.name)
        st.success(f"✅ Report ingested — {n_total} markers extracted, {n_flagged} flagged")
        st.rerun()
    elif uploaded is not None:
        st.sidebar.success("✅ Already ingested")

    st.divider()

    reports = get_reports()
    if reports:
        options = {
            r["id"]: f"{r['lab_name'] or 'Unknown Lab'} — {r['report_date']} ({r['patient_age']}y {r['patient_gender']})"
            for r in reports
        }
        selected_label = st.selectbox(
            "Active report",
            options=list(options.keys()),
            format_func=lambda rid: options[rid],
        )
        st.session_state.selected_report_id = selected_label
    else:
        st.info("No reports yet — upload a PDF above.")

# ── Main: chat interface ──────────────────────────────────────────────────────
st.title("Blood Report Chat")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            render_assistant_message(msg["content"])
        else:
            st.markdown(msg["content"])

if prompt := st.chat_input("Ask about your blood report…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    with st.chat_message("assistant"):
        with st.spinner("Analyzing…"):
            result = _graph.invoke(
                {"messages": [HumanMessage(content=prompt)]},
                config,
            )
            full_text = result["messages"][-1].content
        render_assistant_message(full_text)

    st.session_state.messages.append({"role": "assistant", "content": full_text})

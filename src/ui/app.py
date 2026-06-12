import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

try:
    import streamlit as st
    for key in [
        "GROQ_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_KEY",
        "QDRANT_URL", "QDRANT_API_KEY", "LANGCHAIN_API_KEY",
        "LANGCHAIN_TRACING_V2", "LANGCHAIN_PROJECT",
    ]:
        if key in st.secrets:
            os.environ[key] = st.secrets[key]
except Exception:
    pass  # local — .env is loaded by dotenv in each module

import uuid
import tempfile

import streamlit as st
from langchain_core.messages import HumanMessage

from src.ingestion.pipeline import ingest
from src.ingestion.pdf_parser import extract_text_from_pdf
from src.ingestion.marker_extractor import extract_markers
from src.agent.graph import create_graph
from src.db.supabase_client import get_reports

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
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask about your blood report…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            result = _graph.invoke(
                {"messages": [HumanMessage(content=prompt)]},
                config,
            )
            response = result["messages"][-1].content
        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})

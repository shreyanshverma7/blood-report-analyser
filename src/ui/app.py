import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src import config  # loads .env + Streamlit secrets bridge

import logging
import uuid
import tempfile

import streamlit as st
from langchain_core.messages import HumanMessage

from src.ingestion.pipeline import ingest
from src.ingestion.errors import ExtractionError
from src.agent.graph import create_graph
from src.agent.response_parser import parse_agent_response, strip_json_block
from src.db.supabase_client import get_reports

logger = logging.getLogger(__name__)

try:
    config.validate()
except RuntimeError as e:
    st.error(str(e))
    st.stop()

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


# ── Cached resources ──────────────────────────────────────────────────────────
# cache_resource, not module scope: Streamlit re-runs this script every
# interaction, and a fresh graph means a fresh MemorySaver — wiping chat memory.
@st.cache_resource
def _build_graph():
    return create_graph()


@st.cache_data(ttl=30)
def _list_reports() -> list:
    return get_reports()


_graph = _build_graph()

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
        try:
            with st.spinner("Ingesting report…"):
                result = ingest(tmp_path)
        except ExtractionError as e:
            st.error(f"Could not ingest this report: {e}")
        except Exception:
            logger.exception("Ingestion failed")
            st.error("Something went wrong while ingesting this report. Please try another PDF.")
        else:
            st.session_state.ingested_files.add(uploaded.name)
            _list_reports.clear()
            if result.extraction_path == "dedup":
                st.info("This report was already ingested — using the existing copy.")
            else:
                st.success(
                    f"✅ Report ingested — {result.n_total} markers extracted, "
                    f"{result.n_flagged} flagged"
                )
            st.rerun()
        finally:
            os.unlink(tmp_path)
    elif uploaded is not None:
        st.sidebar.success("✅ Already ingested")

    st.divider()

    reports = _list_reports()
    if reports:
        labels = {
            r["id"]: f"{r['lab_name'] or 'Unknown Lab'} — {r['report_date']} ({r['patient_age']}y {r['patient_gender']})"
            for r in reports
        }
        selected = st.selectbox(
            "Active report",
            options=[None] + list(labels.keys()),
            format_func=lambda rid: "All reports" if rid is None else labels[rid],
        )
        st.session_state.selected_report_id = selected
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

    invoke_config = {
        "configurable": {
            "thread_id": st.session_state.thread_id,
            "report_id": st.session_state.selected_report_id,
        }
    }
    with st.chat_message("assistant"):
        full_text = None
        with st.spinner("Analyzing…"):
            try:
                result = _graph.invoke(
                    {"messages": [HumanMessage(content=prompt)]},
                    invoke_config,
                )
                full_text = result["messages"][-1].content
            except Exception:
                logger.exception("Agent invocation failed")
        if full_text is None:
            st.error("Something went wrong while answering. Please try again.")
        else:
            render_assistant_message(full_text)

    if full_text is not None:
        st.session_state.messages.append({"role": "assistant", "content": full_text})

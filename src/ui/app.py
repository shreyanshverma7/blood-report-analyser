import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src import config  # loads .env + Streamlit secrets bridge

import logging
import uuid
import tempfile

import streamlit as st
from langchain_core.messages import HumanMessage

from src.core import user_context
from src.ingestion.pipeline import ingest
from src.ingestion.errors import ExtractionError
from src.agent.graph import create_graph
from src.agent.response_parser import parse_agent_response, strip_json_block
from src.db.supabase_client import get_reports, new_anon_client
from src.export.pdf_generator import generate_report_pdf

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


# user_key: st.cache_data is process-global, so without it one user's cached
# rows would be served to every other session
@st.cache_data(ttl=30)
def _list_reports(user_key: str) -> list:
    return get_reports()


@st.cache_data(ttl=60)
def _report_pdf(user_key: str, report_id: str, summary: str | None) -> bytes:
    return generate_report_pdf(report_id, summary)


def _last_agent_summary() -> str | None:
    """Summary of the most recent structured assistant reply, for the PDF."""
    for msg in reversed(st.session_state.messages):
        if msg["role"] == "assistant":
            resp = parse_agent_response(msg["content"])
            if resp is not None:
                return resp.summary
    return None


_graph = _build_graph()

# ── Auth gate ─────────────────────────────────────────────────────────────────
# One anon client per browser session; it holds and auto-refreshes the user's
# tokens. Everything below the gate runs only with a signed-in user.
if "sb_auth" not in st.session_state:
    st.session_state.sb_auth = new_anon_client()

_session = None
try:
    _session = st.session_state.sb_auth.auth.get_session()  # refreshes if expired
except Exception:
    logger.exception("Session refresh failed")

if _session is None:
    st.title("Blood Report Analyser")
    st.caption("Log in to upload reports and chat about your results.")
    tab_login, tab_signup = st.tabs(["Log in", "Sign up"])
    with tab_login, st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Log in"):
            try:
                st.session_state.sb_auth.auth.sign_in_with_password(
                    {"email": email, "password": password}
                )
                st.rerun()
            except Exception:
                st.error("Login failed — check your email and password.")
    with tab_signup, st.form("signup"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Sign up"):
            try:
                res = st.session_state.sb_auth.auth.sign_up(
                    {"email": email, "password": password}
                )
                if res.session is None:
                    st.info("Check your email to confirm the account, then log in.")
                else:
                    st.rerun()
            except Exception:
                st.error("Sign-up failed — try a different email or a longer password.")
    st.stop()

# Contextvars are per-thread-of-execution: set them on every rerun so the DB
# layer and Qdrant filters act as this user.
user_context.set_current(_session.user.id, _session.access_token)

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
    st.caption(f"Signed in as {_session.user.email}")
    col_logout, col_clear = st.columns(2)
    if col_logout.button("Log out", use_container_width=True):
        try:
            st.session_state.sb_auth.auth.sign_out()
        except Exception:
            logger.exception("Sign-out failed")
        user_context.clear()
        st.session_state.clear()
        st.rerun()
    if col_clear.button("Clear chat", use_container_width=True):
        st.session_state.messages = []
        # new thread_id so the agent's checkpointer memory starts fresh too
        st.session_state.thread_id = str(uuid.uuid4())
        st.rerun()

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

    reports = _list_reports(_session.user.id)
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

        if selected:
            report = next(r for r in reports if r["id"] == selected)
            try:
                pdf_bytes = _report_pdf(_session.user.id, selected, _last_agent_summary())
            except Exception:
                logger.exception("PDF export failed")
                st.caption("PDF export is unavailable for this report.")
            else:
                st.download_button(
                    "Download Report PDF",
                    data=pdf_bytes,
                    file_name=f"report_{report['report_date'] or 'unknown'}.pdf",
                    mime="application/pdf",
                )
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

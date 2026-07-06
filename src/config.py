"""Central configuration: one .env load, one Streamlit-secrets bridge, one
startup validation. Importing this module loads the environment; call
validate() at entrypoints to fail fast with every missing key named."""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_KEYS = (
    "GROQ_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "QDRANT_URL",
    "QDRANT_API_KEY",
)
# SUPABASE_SERVICE_KEY bypasses RLS: offline scripts only, never the app path.
# LANGCHAIN_* are opt-in observability — absent means LangSmith tracing stays off.
OPTIONAL_KEYS = (
    "SUPABASE_SERVICE_KEY",
    "LANGCHAIN_API_KEY",
    "LANGCHAIN_TRACING_V2",
    "LANGCHAIN_PROJECT",
)


def _read_streamlit_secrets() -> dict:
    """Return the non-empty st.secrets values (Streamlit Cloud path).

    A missing secrets.toml is normal for local/script runs and is ignored;
    any other failure is logged instead of silently swallowed. Caution: merely
    accessing st.secrets makes Streamlit auto-export every top-level secret
    into os.environ — including blank placeholders — which is why the caller
    must load .env AFTER this runs, then apply these values on top.
    """
    try:
        import streamlit as st
    except ImportError:
        return {}
    try:
        return {
            key: st.secrets[key]
            for key in REQUIRED_KEYS + OPTIONAL_KEYS
            if key in st.secrets and st.secrets[key]
        }
    except FileNotFoundError:
        return {}  # no secrets.toml — .env-only run (StreamlitSecretNotFoundError subclasses this)
    except Exception:
        logger.exception("Failed to read Streamlit secrets")
        return {}


def validate() -> None:
    """Raise one clear error naming every missing required key, instead of a
    KeyError surfacing mid-request."""
    missing = [k for k in REQUIRED_KEYS if not os.environ.get(k)]
    if missing:
        raise RuntimeError(
            "Missing required configuration: " + ", ".join(missing)
            + ". Set them in .env (local) or Streamlit secrets (cloud)."
        )


# Order matters: reading st.secrets blanks os.environ with any placeholder
# values, so read secrets first, repair with .env (override=True also beats
# stale shell vars), then let non-empty cloud secrets win.
_secrets = _read_streamlit_secrets()
load_dotenv(PROJECT_ROOT / ".env", override=True)
os.environ.update(_secrets)

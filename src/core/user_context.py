"""Per-request auth context. app.py sets it once per rerun after login; the
DB layer and Qdrant filters read it. Contextvars (not module globals) so
concurrent Streamlit sessions in one process can't see each other's identity —
LangChain/LangGraph executors propagate contextvars into tool threads."""
from contextvars import ContextVar
from typing import Optional

_access_token: ContextVar[Optional[str]] = ContextVar("sb_access_token", default=None)
_user_id: ContextVar[Optional[str]] = ContextVar("sb_user_id", default=None)


def set_current(user_id: Optional[str], access_token: Optional[str]) -> None:
    _user_id.set(user_id)
    _access_token.set(access_token)


def clear() -> None:
    set_current(None, None)


def user_id() -> Optional[str]:
    return _user_id.get()


def access_token() -> Optional[str]:
    return _access_token.get()

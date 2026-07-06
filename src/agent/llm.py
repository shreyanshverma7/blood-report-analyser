from langchain_groq import ChatGroq

from src import config  # noqa: F401 — loads env before the client is built

_LLM = None


def get_llm():
    global _LLM
    if _LLM is None:
        primary = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
        fallback = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
        _LLM = primary.with_fallbacks([fallback])
    return _LLM

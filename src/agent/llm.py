from langchain_groq import ChatGroq


def get_llm():
    primary = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    fallback = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
    return primary.with_fallbacks([fallback])

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import config

config.validate()

failures = []


def check(service, fn):
    try:
        fn()
        print(f"✓ {service} OK")
    except Exception as e:
        print(f"✗ {service} FAILED: {e}")
        failures.append(service)


def test_groq():
    from langchain_groq import ChatGroq
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.environ["GROQ_API_KEY"],
    )
    response = llm.invoke("ping")
    print(f"  response: {response.content!r}")


def test_supabase():
    from supabase import create_client
    # anon key: reachability only — RLS hides rows without a user JWT
    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])
    try:
        client.from_("reports").select("count", count="exact").limit(0).execute()
    except Exception as e:
        msg = str(e).lower()
        if "not found" in msg or "does not exist" in msg or "42p01" in msg or "pgrst205" in msg or "could not find" in msg:
            print("  table not found — service reachable")
            return
        raise


def test_qdrant():
    from qdrant_client import QdrantClient
    client = QdrantClient(
        url=os.environ["QDRANT_URL"],
        api_key=os.environ["QDRANT_API_KEY"],
    )
    collections = client.get_collections().collections
    names = [c.name for c in collections]
    print(f"  collections: {names}")


def test_langsmith():
    from langsmith import Client
    client = Client(api_key=os.environ["LANGCHAIN_API_KEY"])
    projects = client.list_projects()
    first = next(iter(projects), None)
    print(f"  first project: {first.name if first else '(none)'}")


check("Groq", test_groq)
check("Supabase", test_supabase)
check("Qdrant", test_qdrant)
check("LangSmith", test_langsmith)

if failures:
    print(f"\nFailed: {', '.join(failures)}")
    sys.exit(1)
else:
    print("\nAll services reachable.")

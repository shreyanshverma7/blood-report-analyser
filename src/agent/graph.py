from langgraph.graph import StateGraph, MessagesState, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage

from src.agent.llm import get_llm
from src.agent.tools import query_my_reports, compare_reports, search_medical_kb

TOOLS = [query_my_reports, compare_reports, search_medical_kb]

_SYSTEM_PROMPT = (
    "You are a medical assistant specialising in blood test analysis. "
    "You have access to the user's blood report data and a medical knowledge base. "
    "Always cite which panel or source your information comes from. "
    "Never diagnose — instead explain what markers mean and suggest the user "
    "consult a doctor for anything concerning."
)


def _agent_node(state: MessagesState):
    llm = get_llm().bind_tools(TOOLS)
    messages = [SystemMessage(content=_SYSTEM_PROMPT)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}


def _should_continue(state: MessagesState):
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


def create_graph(checkpointer=None):
    builder = StateGraph(MessagesState)

    builder.add_node("agent", _agent_node)
    builder.add_node("tools", ToolNode(TOOLS))

    builder.set_entry_point("agent")
    builder.add_conditional_edges("agent", _should_continue)
    builder.add_edge("tools", "agent")

    return builder.compile(checkpointer=checkpointer or MemorySaver())

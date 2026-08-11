import urllib.error
import urllib.request

from langchain.agents import create_agent
from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

# SYSTEM_PROMPT = """You are a literary data assistant.
#
# ## Capabilities
#
# - `fetch_text_from_url`: loads document text from a URL into the conversation.
# Do not guess line counts or positions—ground them in tool results from the saved file."""
#
#
# @tool
# def fetch_text_from_url(url: str) -> str:
#     """Fetch the document from a URL.
#     """
#     req = urllib.request.Request(
#         url,
#         headers={"User-Agent": "Mozilla/5.0 (compatible; quickstart-research/1.0)"},
#     )
#     try:
#         with urllib.request.urlopen(req, timeout=120) as resp:
#             raw = resp.read()
#     except urllib.error.URLError as e:
#         return f"Fetch failed: {e}"
#     text = raw.decode("utf-8", errors="replace")
#     return text
#
#
# model = init_chat_model(
#     "gemini-3.1-pro-preview",
#     model_provider="google-genai",
#     temperature=0.5,
#     timeout=600,
#     max_tokens=25000,
#     streaming=True,
# )
#
# checkpointer = InMemorySaver()
#
# agent = create_agent(
#     model=model,
#     tools=[fetch_text_from_url],
#     system_prompt=SYSTEM_PROMPT,
#     checkpointer=checkpointer,
# )



from langgraph.graph import StateGraph, MessagesState, START, END

def mock_llm(state: MessagesState):
    return {"messages": [{"role": "ai", "content": "hello world"}]}

graph = StateGraph(MessagesState)
graph.add_node(mock_llm)
graph.add_edge(START, "mock_llm")
graph.add_edge("mock_llm", END)
graph = graph.compile()

print(graph.invoke({"messages": [{"role": "user", "content": "hi!"}]}))

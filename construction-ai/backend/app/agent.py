from langchain_tavily import TavilySearch
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from app.config import load_google_llm

def create_agent_executor():
    model = load_google_llm()
    search = TavilySearch(max_results=2)
    tools = [search]
    memory = MemorySaver()
    agent_executor = create_react_agent(model, tools, checkpointer=memory)
    return agent_executor

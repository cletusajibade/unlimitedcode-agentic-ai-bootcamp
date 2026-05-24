from langgraph.graph import StateGraph, START, END
from typing import TypedDict
from pydantic import BaseModel, Field


# Create a state schema
class AgentState(TypedDict):
    message: str
    name: str
    age: int


# Create a node
def message_node(state: AgentState) -> dict:
    message = state.get("message", "Default message")

    print(f"Initial State: {state}")

    return {
        "message": message,
        "age": 31
    }


# Create the Graph
graph = StateGraph(AgentState)

#Add nodes
graph.add_node("messenger", message_node)

graph.add_edge(START, "messenger")
graph.add_edge("messenger", END)

# Run the graph
workflow = graph.compile()


# Invoke the graph
initState = {
    "message": "Welcome to LangGraph!",
    "name": "James",
    "age": 26
}
result = workflow.invoke(initState)

print(result)

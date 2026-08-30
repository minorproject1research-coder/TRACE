from langgraph.graph import StateGraph, START, END
from apps.api.graph.state import SharedResearchState
from apps.api.graph.nodes.planner_node import planner_node


def build_graph():
    graph = StateGraph(SharedResearchState)
    graph.add_node("planner", planner_node)

    graph.add_edge(START, "planner")   
    graph.add_edge("planner", END)     

    return graph.compile()
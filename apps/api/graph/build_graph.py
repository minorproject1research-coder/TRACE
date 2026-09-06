from langgraph.graph import StateGraph, START, END
from apps.api.graph.state import SharedResearchState
from apps.api.graph.nodes.planner_node import planner_node
from apps.api.graph.nodes.paper_retrieval_node import paper_retrieval_node


def build_graph():
    graph = StateGraph(SharedResearchState)

    graph.add_node("planner", planner_node)
    graph.add_node("paper_retrieval", paper_retrieval_node)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "paper_retrieval")
    graph.add_edge("paper_retrieval", END)

    return graph.compile()
from langgraph.graph import StateGraph, START, END
from apps.api.graph.state import SharedResearchState
from apps.api.graph.nodes.planner_node import planner_node
from apps.api.graph.nodes.paper_retrieval_node import paper_retrieval_node
from apps.api.graph.nodes.web_search_node import web_search_node


def build_graph():
    graph = StateGraph(SharedResearchState)

    graph.add_node("planner", planner_node)
    graph.add_node("paper_retrieval", paper_retrieval_node)
    graph.add_node("web_search", web_search_node)

    graph.add_edge(START, "planner")

    # After the Planner, both retrieval agents run in parallel.
    graph.add_edge("planner", "paper_retrieval")
    graph.add_edge("planner", "web_search")

    graph.add_edge("paper_retrieval", END)
    graph.add_edge("web_search", END)

    return graph.compile()
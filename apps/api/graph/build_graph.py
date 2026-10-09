from langgraph.graph import StateGraph, START, END
from apps.api.graph.state import SharedResearchState
from apps.api.graph.nodes.planner_node import planner_node
from apps.api.graph.nodes.paper_retrieval_node import paper_retrieval_node
from apps.api.graph.nodes.web_search_node import web_search_node
from apps.api.graph.nodes.summarizer_node import summarizer_node


def build_graph():
    graph = StateGraph(SharedResearchState)

    graph.add_node("planner", planner_node)
    graph.add_node("paper_retrieval", paper_retrieval_node)
    graph.add_node("web_search", web_search_node)
    graph.add_node("summarizer", summarizer_node)

    graph.add_edge(START, "planner")

    # After the Planner, both retrieval agents run in parallel.
    graph.add_edge("planner", "paper_retrieval")
    graph.add_edge("planner", "web_search")

    # Summarizer (Stage 3) waits for BOTH retrieval branches to finish.
    graph.add_edge(["paper_retrieval", "web_search"], "summarizer")
    graph.add_edge("summarizer", END)

    return graph.compile()
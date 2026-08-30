from apps.api.graph.build_graph import build_graph
from apps.api.graph.state import SharedResearchState

app = build_graph()
result = app.invoke(SharedResearchState(raw_query="Impact of RAG on hallucination rates in LLMs"))
print(result["task_plan"])
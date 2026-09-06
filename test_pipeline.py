import logging
from pathlib import Path

log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "pipeline.log"),
        logging.StreamHandler(),
    ],
)

from apps.api.graph.build_graph import build_graph
from apps.api.graph.state import SharedResearchState

app = build_graph()
result = app.invoke(SharedResearchState(raw_query="Impact of RAG on hallucination rates in LLMs"))
print(result["task_plan"])
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

stage_files = {
    "apps.api.agents.stage1_planner": "stage1_planner.log",
    "apps.api.agents.stage2_retrieval": "stage2_retrieval.log",
    "apps.api.agents.stage3_summarizer": "stage3_summarizer.log",
    "apps.api.agents.stage4_factcheck": "stage4_factcheck.log",
    "apps.api.agents.stage5_report": "stage5_report.log",
}

for logger_name, filename in stage_files.items():
    logger = logging.getLogger(logger_name)
    logger.addHandler(logging.FileHandler(log_dir / filename))

from apps.api.graph.build_graph import build_graph
from apps.api.graph.state import SharedResearchState

app = build_graph()
result = app.invoke(SharedResearchState(raw_query="Impact of RAG on hallucination rates in LLMs"))
print(result["task_plan"])
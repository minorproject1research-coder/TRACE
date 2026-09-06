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

print("\n=== TASK PLAN ===")
print(result["task_plan"])

print("\n=== WEB SOURCES ===")
web_sources = result.get("web_sources", [])
print(f"Total web sources: {len(web_sources)}")
for s in web_sources[:10]:
    print(f"  [{s.provider}] {s.title} — {s.url}")

print("\n=== PAPERS ===")
papers = result.get("paper_results", []) 
print(f"Total papers: {len(papers)}")
for p in papers[:10] if papers else []:
    title = p.get("title") if isinstance(p, dict) else getattr(p, "title", "")
    print(f"  {title}")
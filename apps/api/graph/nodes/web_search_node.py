# apps/api/graph/nodes/web_search_node.py
import asyncio
from apps.api.graph.state import SharedResearchState
from apps.api.agents.stage2_retrieval import web_search_agent, reliability_scorer
from apps.api.services import db_service, progress


def web_search_node(state: SharedResearchState) -> dict:
    qid = state.task_plan.query_id
    sub_questions = state.task_plan.sub_questions
    progress.report(qid, "web", "branch", "running", "Web search started")
    all_web_sources = []

    progress.report(qid, "web", "search", "running", "Searching the web",
                    subQuestions=len(sub_questions), queries=sum(len(sq.queries or []) for sq in sub_questions), done=0, total=len(sub_questions))
    for done, sq in enumerate(sub_questions, start=1):
        sources = asyncio.run(web_search_agent.search_all(sq.queries))

        for src in sources:
            src.sub_question_id = sq.id
            # query_id line removed — not needed for web_sources

        all_web_sources.extend(sources)
        progress.report(qid, "web", "search", "running", f"Searched sub-question {done} of {len(sub_questions)}",
                        done=done, total=len(sub_questions), found=len(all_web_sources))
    progress.report(qid, "web", "search", "completed", f"Found {len(all_web_sources)} web sources", found=len(all_web_sources))

    progress.report(qid, "web", "scoring", "running", "Scoring source reliability", sources=len(all_web_sources))
    all_web_sources = reliability_scorer.score_all(all_web_sources)
    progress.report(qid, "web", "scoring", "completed", f"Scored {len(all_web_sources)} sources", scored=len(all_web_sources))

    progress.report(qid, "web", "store", "running", "Saving the web sources", sources=len(all_web_sources))
    db_service.write_web_sources(all_web_sources)
    progress.report(qid, "web", "store", "completed", f"Saved {len(all_web_sources)} web sources", stored=len(all_web_sources))

    return {"web_sources": all_web_sources}

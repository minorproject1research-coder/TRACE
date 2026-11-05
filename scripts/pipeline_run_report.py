#!/usr/bin/env python3
"""
Build a Markdown status report for ONE pipeline run from logs/pipeline.log (the last run in the file) and the database.

  python scripts/pipeline_run_report.py                         # last run in logs/pipeline.log
  python scripts/pipeline_run_report.py --log logs/pipeline.log --query-id <id> --out docs/reports/runs/my_run.md

Everything in the tables comes from the log or the database (nothing is estimated). The "Checks" section is rule based: it only lists
what the log shows (unavailable sources, empty sub-questions, failures, unjudged aspects, rate limiting). Add your own reading
below it. Run it right after the run: the log file is appended to by every run, and a later run does not erase this one, but the
database rows of old runs can be pruned.
"""
import argparse
import re
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "tests"))

LINE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3}) \[(\w+)\] ([\w\.]+): (.*)$")


def ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S,%f")


def dur(seconds: float) -> str:
    seconds = int(round(seconds))
    return f"{seconds // 60}m {seconds % 60:02d}s" if seconds >= 60 else f"{seconds}s"


def read_run(path: str):
    """Lines of the LAST run: from the last 'Starting planner for query' on."""
    raw = Path(path).read_bytes().decode("utf-8", errors="replace").splitlines()
    starts = [i for i, l in enumerate(raw) if "stage1_planner: Starting planner for query:" in l]
    if not starts:
        raise SystemExit("no 'Starting planner for query' line in the log")
    out = []
    for l in raw[starts[-1]:]:
        m = LINE.match(l)
        if m:
            out.append((ts(m.group(1)), m.group(2), m.group(3), m.group(4)))
    return out


def first(lines, pred):
    return next((l for l in lines if pred(l)), None)


def last(lines, pred):
    return next((l for l in reversed(lines) if pred(l)), None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="logs/pipeline.log")
    ap.add_argument("--query-id")
    ap.add_argument("--out")
    args = ap.parse_args()

    from dotenv import load_dotenv
    load_dotenv()
    lines = read_run(args.log)
    t_start, t_end = lines[0][0], lines[-1][0]
    msgs = [(t, lvl, name, msg) for t, lvl, name, msg in lines if not name.startswith(("httpx", "sentence_transformers", "urllib3", "filelock"))]

    qid = args.query_id
    if not qid:
        m = first(msgs, lambda l: l[3].startswith("Saved task plan with ID:"))
        qid = m[3].split(":")[-1].strip() if m else None
    if not qid:
        raise SystemExit("could not find the query id; pass --query-id")

    from apps.api.services.db_service import supabase
    query = supabase.table("research_queries").select("*").eq("id", qid).execute().data[0]
    sqs = supabase.table("sub_questions").select("*").eq("query_id", qid).execute().data
    papers = supabase.table("retrieved_papers").select("*").eq("query_id", qid).execute().data
    paper_ids = [p["id"] for p in papers]
    parsed = supabase.table("parsed_papers").select("retrieved_paper_id").in_("retrieved_paper_id", paper_ids).execute().data if paper_ids else []
    webs = supabase.table("web_sources").select("id,sub_question_id,title,url,reliability_score").in_("sub_question_id", [s["id"] for s in sqs]).execute().data
    digests = supabase.table("digests").select("*").eq("query_id", qid).execute().data
    covs = supabase.table("coverage_results").select("*").eq("query_id", qid).execute().data

    # ---------------------------------------------------------------- phases
    M = lambda pat: first(msgs, lambda l: re.search(pat, l[3]))
    ML = lambda pat: last(msgs, lambda l: re.search(pat, l[3]))
    t_plan = M(r"^Saved task plan")[0]
    t_web0, t_web1 = M(r"^Starting web search")[0], ML(r"^Web search complete")[0]
    t_pf0 = M(r"^Embedding pre-filter")[0]
    t_pf1 = ML(r"^Relevance filter \[")[0]
    t_enr0 = M(r"^Citation enrichment")
    t_ret = M(r"^Retrieved \d+ relevant papers")[0]
    t_parse0 = M(r"^Parsing the top")[0]
    t_parse1 = M(r"^Parsing done")[0]
    st3 = M(r"^Stage 3: \d+ digests")
    t_st3 = st3[0]
    t_judge0 = first(msgs, lambda l: l[0] > t_st3 and "detail_aspects: Aspect cache hit" in (l[2] + ": " + l[3]) or (l[0] > t_st3 and l[2].endswith("detail_aspects") and l[3].startswith("Aspect cache hit")))
    t_judge0 = t_judge0[0] if t_judge0 else t_st3
    t_last_sq = ML(r"Judge used:")[0]
    phases = [("Planner (decompose, 5 sub-questions)", t_start, t_plan), ("Web search (Tavily)", t_web0, t_web1),
              ("Paper search (arXiv, IEEE, OpenAlex, Semantic Scholar, Scopus)", t_web1, t_pf0), ("Embedding pre-filter + relevance judge", t_pf0, t_pf1)]
    if t_enr0:
        phases.append(("Citation enrichment (Semantic Scholar)", t_enr0[0], t_ret))
    phases += [("Store papers in the database", t_ret, t_parse0), ("PDF download + Docling parsing", t_parse0, t_parse1),
               ("Stage 3 preparation (aspect split, chunking, embedding)", t_parse1, t_st3), ("Stage 3 digest generation (Groq)", t_st3, t_judge0),
               ("Stage 3 judge + coverage (per sub-question)", t_judge0, t_last_sq)]
    total = (t_end - t_start).total_seconds()

    # ---------------------------------------------------------------- retrieval + filter
    web_variant = [int(re.search(r"(\d+) unique", l[3]).group(1)) for l in msgs if l[3].startswith("Web search complete")]
    prefilter = [tuple(int(x) for x in re.search(r"(\d+) candidates -> (\d+) cleared min_similarity \(([\d.]+)\) -> top (\d+)", l[3]).group(1, 2, 4)) for l in msgs if l[3].startswith("Embedding pre-filter")]
    pf_text = [l[3] for l in msgs if l[3].startswith("Embedding pre-filter")]
    judged = [re.search(r"Relevance filter \[(.*?)\] for \[(.*?)\]: (\d+) shortlisted -> (\d+) passed \((\d+) kept without", l[3]).groups() for l in msgs if l[3].startswith("Relevance filter [")]
    rejects = Counter()
    for l in msgs:
        m = re.match(r"Filtered out \[(.*?)\] ", l[3])
        if m:
            rejects[m.group(1)] += 1
    reject_examples = defaultdict(list)
    for l in msgs:
        m = re.match(r"Filtered out \[(.*?)\] '(.*?)'.*?reason: (.*)", l[3])
        if m and len(reject_examples[m.group(1)]) < 3:
            reject_examples[m.group(1)].append((m.group(2), m.group(3)[:140]))

    # ---------------------------------------------------------------- parsing
    obtained = Counter(re.search(r"PDF obtained via (.*?) \(", l[3]).group(1) for l in msgs if l[3].startswith("PDF obtained via"))
    n_cache = sum(1 for l in msgs if l[3].startswith("Parse cache hit"))
    n_unpaywall_found = sum(1 for l in msgs if l[3].startswith("Unpaywall found OA URL"))
    n_landing = sum(1 for l in msgs if l[3].startswith("Found the PDF through the landing"))
    n_dl_fail = [l for l in msgs if l[3].startswith("Failed to download from")]
    dl_fail_reason = Counter(re.search(r"(HTTPStatusError\('\d+ [A-Za-z ]+'\)|ValueError\('Non-PDF[^)]*\)?|[A-Za-z]+Error)", l[3]).group(1)[:40] if re.search(r"(HTTPStatusError\('\d+ [A-Za-z ]+'\)|ValueError\('Non-PDF|[A-Za-z]+Error)", l[3]) else "other" for l in n_dl_fail)
    n_pw_try = sum(1 for l in msgs if l[3].startswith("Trying undetected Playwright"))
    n_pw_fail = sum(1 for l in msgs if l[3].startswith("Playwright fallback failed"))
    n_docling_url = sum(1 for l in msgs if "Docling fetches and parses" in l[3])
    n_html_fail = sum(1 for l in msgs if l[3].startswith("HTML full-text attempt failed"))
    final_fail = [(re.search(r"failed for ([\w-]+): (.*)", l[3]).groups()) for l in msgs if l[3].startswith("All PDF URLs failed")]
    parse_err = [(re.search(r"Failed to parse paper ([\w-]+): (.*)", l[3]).groups()) for l in msgs if l[3].startswith("Failed to parse paper")]
    done = re.search(r"(\d+) usable full texts out of (\d+) papers attempted \((\d+) saved", M(r"^Parsing done")[3])
    title_of = {p["id"]: p.get("title") or "?" for p in papers}

    # ---------------------------------------------------------------- scopus / s2 / groq
    notes = [l for l in msgs if l[1] in ("WARNING", "ERROR")]
    scopus_down = first(msgs, lambda l: "Scopus unavailable" in l[3])
    s2_down = first(msgs, lambda l: "Semantic Scholar probe failed" in l[3])
    s2_batch_429 = sum(1 for l in msgs if l[3].startswith("S2 batch response: status=429"))
    groq_events = [(l[0], re.search(r"key \.\.\.(\w+) rate limited, parked (\d+)s", l[3]).groups()) for l in msgs if "groq_pool" in l[2] and "rate limited" in l[3]]
    groq_by_key = defaultdict(lambda: [0, 0])
    for _, (k, s) in groq_events:
        groq_by_key[k][0] += 1
        groq_by_key[k][1] += int(s)
    judge_batches = [int(re.search(r"latency_ms=(\d+), items=(\d+)", l[3]).group(1)) for l in msgs if l[3].startswith("Judge batch: status=200")]

    # ---------------------------------------------------------------- stage 3 per sub-question
    from audit_tag_precision import covered_indices
    from apps.api.agents.stage3_summarizer.chunk_selector import _clean_topic
    from apps.api.agents.stage3_summarizer.detail_aspects import flatten_aspects, run_merge_mode
    cov_by_sq = {}
    for c in sorted(covs, key=lambda c: c["created_at"]):
        cov_by_sq[c["sub_question_id"]] = c
    web_by_sq, paper_by_sq, parsed_ids = Counter(w["sub_question_id"] for w in webs), Counter(p["sub_question_id"] for p in papers), {r["retrieved_paper_id"] for r in parsed}
    parsed_by_sq = Counter(p["sub_question_id"] for p in papers if p["id"] in parsed_ids)
    dg_by_sq = defaultdict(list)
    for d in digests:
        dg_by_sq[d["sub_question_id"]].append(d)

    def key(topic):
        return topic[:40]

    j_by_sq = {name: (int(sh), int(pa)) for _, name, sh, pa, _k in judged}
    pf_by_sq = {}
    for (cand, cleared, shortlist), (_, name, _, _, _) in zip(prefilter, judged):
        pf_by_sq[name] = (cand, cleared, shortlist)

    out = []
    w = out.append
    title = f"Pipeline run report - {query['raw_query']}"
    w(f"# {title}\n")
    w(f"Generated {datetime.now():%Y-%m-%d %H:%M} by `scripts/pipeline_run_report.py` from `{args.log}` (last run in the file) and the database. Query id `{qid}`.\n")

    w("## 1. Summary\n")
    n_pass = sum(p for _, p in j_by_sq.values())
    n_short = sum(s for s, _ in j_by_sq.values())
    n_full = sum(1 for d in digests if d.get("evidence_level") == "full_text")
    ver = sum(d.get("verified_count") or 0 for d in digests)
    tot = sum(d.get("total_count") or 0 for d in digests)
    n_cov_ok = sum(1 for c in cov_by_sq.values() if c.get("sufficient"))
    w("| | |\n|---|---|")
    w(f"| Question | {query['raw_query']} |")
    anchor_line = first(msgs, lambda l: l[3].startswith("Domain anchor"))
    if anchor_line:
        anchor_shown = anchor_line[3].replace("Domain anchor", "").strip(" :")
    else:
        # no log line (it can be lost, e.g. by a log-file encoding error): look at the stored queries instead
        qtexts = [q["query_text"] for q in supabase.table("queries").select("query_text").in_("sub_question_id", [s["id"] for s in sqs]).execute().data]
        ends = Counter(" ".join(t.split()[-k:]) for t in qtexts for k in (1, 2, 3) if len(t.split()) > k)
        best = max(ends.items(), key=lambda kv: (kv[1], len(kv[0]))) if ends else None
        anchor_shown = (f"'{best[0]}' ends {best[1]} of {len(qtexts)} stored queries (the log line is missing)"
                        if best and best[1] >= 0.6 * len(qtexts) else "not used (switch off, or no trace in the log or in the queries)")
    w(f"| Domain anchor | {anchor_shown} |")
    w(f"| Started / finished | {t_start:%Y-%m-%d %H:%M:%S} / {t_end:%H:%M:%S} |")
    w(f"| **Total execution time** | **{dur(total)}** ({total:.0f} s) |")
    planner = M(r"^Planner \(")
    per_sq = re.search(r"-> (\[.*?\])", planner[3]).group(1) if planner else "?"
    n_queries = re.search(r"(\d+) search queries", planner[3]).group(1) if planner else "?"
    w(f"| Sub-questions / search queries | {len(sqs)} / {n_queries} (per sub-question {per_sq}) |")
    plan_source = re.match(r"Planner \(([^)]*)\)", planner[3]).group(1) if planner else "?"
    w(f"| Plan source | {plan_source}" + (" (stored plan reused, PLAN_CACHE=true)" if plan_source == "plan-cache" else "") + " |")
    w(f"| Paper candidates retrieved (all sources), after the similarity floor, shortlisted | {sum(c for c, _, _ in prefilter)} candidates -> {sum(c for _, c, _ in prefilter)} cleared the similarity floor -> {n_short} shortlisted |")
    w(f"| **Papers kept after the relevance judge** | **{len(papers)}** (log: {n_pass}); {n_short - n_pass} shortlisted papers rejected |")
    w(f"| **Web sources** | **{len(webs)}** (per sub-question {web_variant}) |")
    w(f"| Papers attempted for parsing | {done.group(2)} (top-N per sub-question) |")
    w(f"| **Papers parsed to usable full text** | **{done.group(1)}** of {done.group(2)} attempted ({n_cache} from the parse cache) |")
    w(f"| Papers not parsed (all routes failed) | {len(final_fail)} download/route failures + {len(parse_err)} database/parse error(s); the rest of the shortfall is abstract-only |")
    w(f"| PDF download attempts that failed | {len(n_dl_fail)} (individual URL failures; most papers recovered through another route) |")
    w(f"| Stage 3 digests | {len(digests)} ({n_full} from full text, {sum(1 for d in digests if d.get('evidence_level') == 'abstract')} from abstracts, {sum(1 for d in digests if d.get('evidence_level') == 'web_snippet')} from web snippets) |")
    w(f"| Findings (verified / total) | {ver} / {tot} |")
    w(f"| Coverage sufficient | {n_cov_ok} of {len(cov_by_sq)} sub-questions |")
    w(f"| Judge | {dur(sum(judge_batches) / 1000)} in {len(judge_batches)} batches; model id `{__import__('os').getenv('JUDGE_MODEL_ID', '?')}` (from .env at report time) |")
    w(f"| Groq rate limiting | {len(groq_events)} parking events, {sum(int(s) for _, (_, s) in groq_events)} key-seconds parked |\n")

    w("## 2. Time per phase\n")
    w("| Phase | Start | End | Duration | Share |\n|---|---|---|---|---|")
    for name, a, b in phases:
        d = (b - a).total_seconds()
        w(f"| {name} | {a:%H:%M:%S} | {b:%H:%M:%S} | {dur(d)} | {100 * d / total:.0f}% |")
    w(f"| **Total** | {t_start:%H:%M:%S} | {t_end:%H:%M:%S} | **{dur(total)}** | 100% |\n")

    w("## 3. Sub-questions: retrieval, filtering, parsing, Stage 3\n")
    w("| # | Sub-question | Pre-filter (cand. -> cleared -> shortlist) | Judge passed | Parsed full text | Web | Digests (full / abs / web) | Verified / total findings | Coverage |")
    w("|---|---|---|---|---|---|---|---|---|")
    for i, sq in enumerate(sqs, 1):
        k = next((n for n in j_by_sq if sq["main_topic"].startswith(n.rstrip())), key(sq["main_topic"]))
        pf = pf_by_sq.get(k, ("?", "?", "?"))
        dgs = dg_by_sq.get(sq["id"], [])
        lv = Counter(d.get("evidence_level") for d in dgs)
        c = cov_by_sq.get(sq["id"], {})
        w(f"| {i} | {sq['main_topic']} | {pf[0]} -> {pf[1]} -> {pf[2]} | {j_by_sq.get(k, ('?', '?'))[1]} of {j_by_sq.get(k, ('?', '?'))[0]} | {parsed_by_sq.get(sq['id'], 0)} | {web_by_sq.get(sq['id'], 0)} | {len(dgs)} ({lv.get('full_text', 0)} / {lv.get('abstract', 0)} / {lv.get('web_snippet', 0)}) | {sum(d.get('verified_count') or 0 for d in dgs)} / {sum(d.get('total_count') or 0 for d in dgs)} | {'sufficient' if c.get('sufficient') else 'NOT sufficient'} |")
    w("")
    for name, ex in reject_examples.items():
        w(f"- Relevance judge rejected {rejects[name]} papers for [{name}]. Examples: " + "; ".join(f"'{t}' ({r})" for t, r in ex))
    w("")

    w("### Sources behind each sub-question's digests\n")
    for i, sq in enumerate(sqs, 1):
        w(f"**{i}. {sq['main_topic']}**\n")
        w("| Source | Type | Evidence | Verified / total findings |\n|---|---|---|---|")
        for d in sorted(dg_by_sq.get(sq["id"], []), key=lambda d: (d.get("evidence_level") != "full_text", d.get("source_title") or "")):
            w(f"| {(d.get('source_title') or '?')[:95].replace('|', '/')} | {d.get('source_type')} | {d.get('evidence_level')} | {d.get('verified_count')} / {d.get('total_count')} |")
        w("")

    w("## 4. Stage 3: aspects and coverage\n")
    w("An aspect is covered when at least 2 judge \"yes\" verdicts come from at least 2 sources. States: covered, uncovered (judged, too few yes), no candidates, unjudged (a verdict failed).\n")
    for i, sq in enumerate(sqs, 1):
        c = cov_by_sq.get(sq["id"], {})
        if not c:
            w(f"### {i}. {sq['main_topic']}\n\nNo coverage row found.\n")
            continue
        aspects, _ = flatten_aspects(sq["detail_questions"], sq["id"], _clean_topic(sq["main_topic"]), merge_mode=run_merge_mode(c))
        cov_idx = covered_indices(c, len(aspects))
        ev = c.get("aspect_evidence") or {}
        reasons = c.get("uncovered_reasons") or {}
        st = c.get("judge_stats") or {}
        w(f"### {i}. {sq['main_topic']}\n")
        w(f"Sufficient: **{c.get('sufficient')}**; judge used: {c.get('judge_used')}; sources {c.get('source_count')} ({c.get('full_text_source_count')} full text); judge candidates {st.get('candidates')} = yes {st.get('yes')}, partial {st.get('partial')}, no {st.get('no')}, error {st.get('error')}; digest failures {c.get('digest_failures')}.\n")
        w("| # | Aspect | State | Yes verdicts | Sources |\n|---|---|---|---|---|")
        for a_i, text in enumerate(aspects):
            e = ev.get(str(a_i)) or ev.get(a_i) or []
            yes_src = len({x.get("source_id") for x in e})
            if text in (c.get("unjudged_aspects") or []):
                state = "unjudged"
            elif a_i in cov_idx:
                state = "covered"
            else:
                state = {"no_candidates": "no candidates", "judged_insufficient": "uncovered"}.get(reasons.get(text), "uncovered")
            w(f"| {a_i + 1} | {text} | {state} | {len(e)} | {yes_src} |")
        if c.get("uncovered_details"):
            w("\nUncovered details: " + "; ".join(c["uncovered_details"]))
        w("")

    w("## 5. Retrieval details\n")
    w(f"- Web search variants: {web_variant} unique sources after de-duplication per sub-question (Tavily, 3 queries each, 5 results per query).")
    w(f"- Pre-filter lines: " + "; ".join(pf_text_i[len("Embedding pre-filter: "):] for pf_text_i in pf_text))
    kept_by_source = Counter(p.get("source") for p in papers)
    openalex_requests = sum(1 for l in lines if "api.openalex.org" in l[3])
    w(f"- Kept papers by source: {dict(kept_by_source)}; requests to api.openalex.org in the log: {openalex_requests}")
    w(f"- Scopus: {'UNAVAILABLE - ' + scopus_down[3] if scopus_down else 'used'}")
    w(f"- Semantic Scholar: {'search skipped, probe failed - ' + s2_down[3] if s2_down else 'used'}; citation-enrichment batch calls answered 429: {s2_batch_429}")
    if t_enr0:
        w(f"- Citation enrichment: {t_enr0[3]}; took {dur((t_ret - t_enr0[0]).total_seconds())} in total")
    w("")

    w("## 6. Parsing details\n")
    w(f"- Attempted {done.group(2)} papers, usable full text {done.group(1)}, {done.group(3)} papers saved in the database.")
    w("- PDF obtained via: " + (", ".join(f"{k}: {v}" for k, v in obtained.items()) or "-") + f"; parse cache hits: {n_cache}; Unpaywall OA links found: {n_unpaywall_found}; landing-page citation_pdf_url: {n_landing}")
    w(f"- Individual download failures: {len(n_dl_fail)} -> " + ", ".join(f"{k}: {v}" for k, v in dl_fail_reason.most_common()))
    w(f"- Headless-browser fallback: {n_pw_try} tried, {n_pw_fail} failed; Docling fetch-by-URL attempts: {n_docling_url}; HTML full-text attempts that failed: {n_html_fail}")
    if final_fail or parse_err:
        w("\nPapers with NO usable text from any route:\n")
        w("| Paper | Reason |\n|---|---|")
        for pid, err in final_fail:
            w(f"| {title_of.get(pid, pid)[:90]} | all PDF routes failed: {err[:90]} |")
        for pid, err in parse_err:
            w(f"| {title_of.get(pid, pid)[:90]} | parse/database error: {err[:110]} |")
    w("")

    w("## 7. Groq and judge\n")
    st3m = M(r"^Stage 3: \d+ digests")
    w(f"- {st3m[3]}")
    w(f"- Rate-limit parking events: {len(groq_events)}; per key (events / parked seconds): " + ", ".join(f"...{k}: {v[0]} / {v[1]}s" for k, v in sorted(groq_by_key.items())))
    w(f"- Judge batch latencies (s): {[round(x / 1000, 1) for x in judge_batches]}")
    w("")

    judge_errors = []
    for d in digests:
        for f in d.get("findings") or []:
            for a_idx, v in (f.get("judge") or {}).items():
                if v.get("final") == "error":
                    judge_errors.append((d.get("source_title"), a_idx, v.get("reason")))
    w("- Judge verdicts that came back as error: " + (str(len(judge_errors)) + " -> " + "; ".join(f"aspect {int(a) + 1} of '{(t or '?')[:40]}': {(r or '')[:120]}" for t, a, r in judge_errors) if judge_errors else "0"))
    w("")

    w("## 8. Warnings and errors in the log (grouped)\n")

    def norm(m):
        m = re.sub(r"https?://\S+", "<url>", m)
        m = re.sub(r"[0-9a-f]{8}-[0-9a-f-]{27,}", "<id>", m)
        m = re.sub(r"'[^']{12,}'", "'<text>'", m)
        return re.sub(r"\d+", "N", m)[:110]
    grouped = Counter((l[1], norm(l[3])) for l in notes)
    w("| Level | Count | Message (numbers, urls and titles replaced) |\n|---|---|---|")
    for (lvl, m), n in sorted(grouped.items(), key=lambda x: (x[0][0] != "ERROR", -x[1])):
        w(f"| {lvl} | {n} | {m.replace('|', '/')} |")
    w("")

    w("## 9. Checks (rule based, from the log)\n")
    flags = []
    if openalex_requests == 0:
        flags.append("OpenAlex was not queried at all (0 requests in the log): the agent skips it silently when no OPENALEX_API_KEYS is set; kept papers by source: " + str(dict(kept_by_source)))
    elif kept_by_source and kept_by_source.get("openalex", 0) + kept_by_source.get("both", 0) == 0:
        flags.append("OpenAlex was queried but none of the kept papers came from it.")
    if scopus_down:
        flags.append("Scopus was unavailable (host returned 404 for /scopus/search): no Scopus papers in this run.")
    if s2_down:
        flags.append("Semantic Scholar search was skipped (probe returned 429)" + (f" and citation enrichment still spent {dur((t_ret - t_enr0[0]).total_seconds())} on {s2_batch_429} rate-limited batch calls." if t_enr0 and s2_batch_429 else "."))
    for name, (sh, pa) in j_by_sq.items():
        if pa == 0:
            flags.append(f"Sub-question [{name}]: 0 of {sh} shortlisted papers passed the relevance judge; it has web sources only.")
    for sq in sqs:
        if not any(d.get("evidence_level") == "full_text" for d in dg_by_sq.get(sq["id"], [])):
            flags.append(f"Sub-question '{sq['main_topic']}': no full-text digest (evidence is abstracts / web snippets only).")
    for sq in sqs:
        c = cov_by_sq.get(sq["id"], {})
        if c.get("unjudged_aspects"):
            flags.append(f"Sub-question '{sq['main_topic']}': {len(c['unjudged_aspects'])} unjudged aspect(s) (a judge verdict failed): {c['unjudged_aspects']}")
        if c.get("fallback_reason"):
            flags.append(f"Sub-question '{sq['main_topic']}': fell back to the tag rule ({c['fallback_reason']}).")
        if (c.get("digest_failures") or 0) > 0:
            flags.append(f"Sub-question '{sq['main_topic']}': {c['digest_failures']} digest JSON failure(s).")
    if parse_err:
        flags.append(f"{len(parse_err)} paper(s) failed at the parse/database step: " + "; ".join(f"{title_of.get(p, p)[:50]} ({e[:80]})" for p, e in parse_err))
    if final_fail:
        flags.append(f"{len(final_fail)} paper(s) could not be downloaded by any route.")
    if groq_events:
        flags.append(f"Groq rate limiting: {len(groq_events)} parking events; digest generation took {dur((t_judge0 - t_st3).total_seconds())}.")
    big = max(phases, key=lambda p: (p[2] - p[1]).total_seconds())
    flags.append(f"Longest phase: {big[0]} ({dur((big[2] - big[1]).total_seconds())}, {100 * (big[2] - big[1]).total_seconds() / total:.0f}% of the run).")
    for f in flags:
        w(f"- {f}")
    w(f"\nWarnings in the log: {sum(1 for l in notes if l[1] == 'WARNING')}; errors: {sum(1 for l in notes if l[1] == 'ERROR')}.\n")

    text = "\n".join(out)
    slug = re.sub(r"[^a-z0-9]+", "-", query["raw_query"].lower())[:40].strip("-")
    path = Path(args.out) if args.out else Path("docs/reports/runs") / f"run_{t_start:%Y%m%d_%H%M}_{qid[:8]}_{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    marker = "<!-- MANUAL NOTES (kept when this report is regenerated) -->"
    kept = path.read_text(encoding="utf-8").split(marker, 1)[1] if path.exists() and marker in path.read_text(encoding="utf-8") else "\n\n## 10. Notes\n\n(write your reading of this run here)\n"
    text = text.rstrip("\n") + "\n\n" + marker + kept
    path.write_text(text, encoding="utf-8")
    print(f"wrote {path} ({len(text.split())} words)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Publish the labeled relevance-judge benchmark to the Hugging Face Hub as a dataset.

  python -m evaluation.relevance_judge.upload_to_huggingface --dry-run          # build + check everything locally, no network
  python -m evaluation.relevance_judge.upload_to_huggingface                    # upload as a PRIVATE dataset (asks to confirm)
  python -m evaluation.relevance_judge.upload_to_huggingface --public           # upload as a public dataset

Put your token in .env (a Hugging Face "write" token from https://huggingface.co/settings/tokens):

  HF_TOKEN=hf_xxx
  HF_DATASET_REPO=<username>/trace-relevance-judge      # optional; default is <your username>/trace-relevance-judge

What is uploaded (a staging folder is built first, see --out):
  README.md                 dataset card generated from hf_dataset_card.md, with statistics computed from the data
  data/test.jsonl           dataset.jsonl flattened into plain columns (relevant, label_confidence, label_reason, quality_flag, ...)
  metadata/sub_questions.json

NOT uploaded: raw/ (API cache), candidates.jsonl and labels/ (everything in them is already inside data/test.jsonl).
"""
import argparse
import json
import os
import re
import statistics
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).parent
REPO_ROOT = HERE.parents[1]
CARD_TEMPLATE = HERE / "hf_dataset_card.md"
DATASET = HERE / "dataset.jsonl"
SUB_QUESTIONS = HERE / "sub_questions.json"

DEFAULT_REPO_NAME = "trace-relevance-judge"
TOKEN_VARS = ("HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGINGFACE_API_KEY", "HF_API_KEY")
JUDGE_CHAR_LIMIT = 2500
PROD_THRESHOLD = 0.56  # min_similarity in relevance_filter.filter_relevant

# Records whose upstream title/abstract metadata is broken (found while labeling).
QUALITY_FLAGS = {
    "sq22_09": ("title_abstract_mismatch", "Title is the Codex paper, abstract describes an unrelated LLVM toolchain project"),
    "sq29_09": ("title_abstract_mismatch", "Title is Kaplan et al. scaling laws, abstract is about agentic-AI scale-up transport"),
    "sq21_03": ("contaminated_abstract", "Abstract is truncated and contains scraped website text"),
    "sq29_11": ("truncated_abstract", "Abstract is cut off mid-sentence"),
}


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def flatten(row: dict) -> dict:
    flag = QUALITY_FLAGS.get(row["id"])
    return {
        "id": row["id"],
        "sub_question_id": row["sub_question_id"],
        "sub_question": row["sub_question"],
        "title": row["title"],
        "abstract": row["abstract"],
        "year": row.get("year"),
        "source": row.get("source"),
        "doi": row.get("doi"),
        "arxiv_id": row.get("arxiv_id"),
        "embedding_similarity": round(float(row["embedding_similarity"]), 4),
        "relevant": bool(row["label"]["relevant"]),
        "label_confidence": float(row["label"]["confidence"]),
        "label_reason": row["label"]["reason"],
        "label_source": row.get("label_source", "claude-manual"),
        "quality_flag": flag[0] if flag else None,
    }


def pct(x: float, digits: int = 0) -> str:
    return f"{100 * x:.{digits}f}"


def md_table(header: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def compute_stats(rows: list[dict]) -> dict:
    n = len(rows)
    pos = sum(r["relevant"] for r in rows)
    neg = n - pos
    sims = [r["embedding_similarity"] for r in rows]

    def acc_at(t):
        return sum((r["embedding_similarity"] >= t) == r["relevant"] for r in rows) / n

    best_acc, best_thr = max((acc_at(t / 100), t / 100) for t in range(40, 95))
    prod_acc = acc_at(PROD_THRESHOLD)
    prod_recall = sum(r["embedding_similarity"] >= PROD_THRESHOLD for r in rows if r["relevant"]) / max(pos, 1)
    prod_kept_neg = sum(r["embedding_similarity"] >= PROD_THRESHOLD for r in rows if not r["relevant"])

    by_source = defaultdict(lambda: [0, 0])
    for r in rows:
        by_source[r["source"]][0] += 1
        by_source[r["source"]][1] += r["relevant"]
    order = ["openalex", "arxiv", "both", "semantic_scholar"]
    source_rows = [[s, by_source[s][0], by_source[s][1], pct(by_source[s][1] / by_source[s][0]) + "%"]
                   for s in order + sorted(set(by_source) - set(order)) if s in by_source]

    bands = [(0, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.01)]
    sim_rows = []
    for lo, hi in bands:
        sel = [r for r in rows if lo <= r["embedding_similarity"] < hi]
        label = f"< {hi}" if lo == 0 else (f">= {lo}" if hi > 1 else f"{lo} - {hi}")
        sim_rows.append([label, len(sel), sum(r["relevant"] for r in sel),
                         pct(sum(r["relevant"] for r in sel) / len(sel)) + "%" if sel else "-"])

    per_q = defaultdict(int)
    for r in rows:
        per_q[r["sub_question_id"]] += r["relevant"]

    flagged = [r for r in rows if r["quality_flag"]]
    flag_rows = [[f"`{r['id']}`", f"`{r['quality_flag']}`", QUALITY_FLAGS[r["id"]][1]] for r in flagged]

    return {
        "n_rows": n, "n_relevant": pos, "n_not_relevant": neg, "n_irrelevant": neg,
        "pct_relevant": pct(pos / n), "n_questions": len(per_q),
        "n_low_conf": sum(r["label_confidence"] < 0.7 for r in rows),
        "majority_acc": pct(max(pos, neg) / n, 1),
        "best_thr": f"{best_thr:.2f}", "best_acc": pct(best_acc, 1),
        "prod_acc": pct(prod_acc, 1), "prod_recall": pct(prod_recall),
        "prod_kept_irrelevant": prod_kept_neg,
        "min_rel_per_q": min(per_q.values()), "max_rel_per_q": max(per_q.values()),
        "pct_fit": pct(sum(len(r["abstract"]) <= JUDGE_CHAR_LIMIT for r in rows) / n, 1),
        "n_s2": sum(r["source"] == "semantic_scholar" for r in rows),
        "source_table": md_table(["Source", "Rows", "Relevant", "Relevant rate"], source_rows),
        "sim_table": md_table(["embedding_similarity", "Rows", "Relevant", "Relevant rate"], sim_rows),
        "flag_table": (md_table(["Row", "Flag", "Problem"], flag_rows) if flag_rows
                       else "No records are flagged in this release."),
        "sim_median": statistics.median(sims),
    }


def render_card(template: str, stats: dict, license_id: str, example: dict) -> str:
    ex = dict(example)
    ex["abstract"] = ex["abstract"][:220].rstrip() + " ..."
    values = {**stats, "license": license_id, "example_json": json.dumps(ex, ensure_ascii=False, indent=2)}
    card = template
    for key, val in values.items():
        card = card.replace("{{" + key + "}}", str(val))
    leftover = re.findall(r"\{\{[a-z_0-9]+\}\}", card)
    if leftover:
        raise SystemExit(f"unfilled placeholders in dataset card: {sorted(set(leftover))}")
    return card


def build_staging(out: Path, args) -> dict:
    if not DATASET.exists():
        raise SystemExit(f"{DATASET} not found. Build it first: python -m evaluation.relevance_judge.merge_labels")
    rows = [flatten(r) for r in read_jsonl(DATASET)]
    if args.exclude_sources:
        excluded = set(args.exclude_sources)
        rows = [r for r in rows if r["source"] not in excluded]
    if args.drop_flagged:
        rows = [r for r in rows if not r["quality_flag"]]
    if not rows:
        raise SystemExit("no rows left after filtering")

    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate ids in dataset")
    for r in rows:
        if not r["title"].strip() or not r["abstract"].strip() or not r["label_reason"].strip():
            raise SystemExit(f"empty field in row {r['id']}")

    (out / "data").mkdir(parents=True, exist_ok=True)
    (out / "metadata").mkdir(parents=True, exist_ok=True)
    (out / "data" / "test.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    (out / "metadata" / "sub_questions.json").write_text(SUB_QUESTIONS.read_text(encoding="utf-8"), encoding="utf-8")

    stats = compute_stats(rows)
    example = next((r for r in rows if r["id"] == "sq02_02"), rows[0])
    (out / "README.md").write_text(
        render_card(CARD_TEMPLATE.read_text(encoding="utf-8"), stats, args.license, example), encoding="utf-8")
    return stats


def get_token() -> str | None:
    for name in TOKEN_VARS:
        val = (os.getenv(name) or "").strip()
        if val:
            return val
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo-id", help="target dataset repo, e.g. username/trace-relevance-judge (default: $HF_DATASET_REPO or <you>/trace-relevance-judge)")
    ap.add_argument("--public", action="store_true", help="create the dataset as public (default: private)")
    ap.add_argument("--license", default="cc-by-4.0", help="license id for the annotations, shown on the card (default: cc-by-4.0)")
    ap.add_argument("--exclude-sources", nargs="*", default=[], help="drop rows from these sources, e.g. semantic_scholar")
    ap.add_argument("--drop-flagged", action="store_true", help="drop the rows with a quality_flag instead of just flagging them")
    ap.add_argument("--dry-run", action="store_true", help="build and validate the upload folder, do not contact Hugging Face")
    ap.add_argument("--out", help="folder for the staged upload (default: a temp folder)")
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = ap.parse_args()

    load_dotenv(REPO_ROOT / ".env")

    out = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="trace_relevance_judge_hf_"))
    stats = build_staging(out, args)
    print(f"Staged {stats['n_rows']} rows ({stats['n_relevant']} relevant / {stats['n_not_relevant']} not) in {out}")
    for p in sorted(out.rglob("*")):
        if p.is_file():
            print(f"  {p.relative_to(out)}  ({p.stat().st_size / 1024:.0f} KB)")

    if args.dry_run:
        print("\nDry run only: nothing was uploaded. Review the staged README.md, then run without --dry-run.")
        return

    token = get_token()
    if not token:
        raise SystemExit(f"No Hugging Face token found. Add HF_TOKEN=... to {REPO_ROOT / '.env'} "
                         f"(accepted names: {', '.join(TOKEN_VARS)}).")

    try:
        from huggingface_hub import HfApi
    except ImportError:
        raise SystemExit("huggingface_hub is not installed: pip install huggingface_hub")

    api = HfApi(token=token)
    try:
        user = api.whoami()["name"]
    except Exception as e:
        raise SystemExit(f"Could not authenticate with Hugging Face ({type(e).__name__}). Check the token and that it has write access.")

    repo_id = args.repo_id or os.getenv("HF_DATASET_REPO", "").strip() or f"{user}/{DEFAULT_REPO_NAME}"
    visibility = "PUBLIC" if args.public else "private"
    print(f"\nAuthenticated as '{user}'. Target: https://huggingface.co/datasets/{repo_id}  ({visibility})")

    if not args.yes:
        prompt = "Make this dataset PUBLIC now? [y/N] " if args.public else "Upload as a private dataset? [y/N] "
        if input(prompt).strip().lower() not in ("y", "yes"):
            raise SystemExit("Cancelled, nothing uploaded.")

    api.create_repo(repo_id=repo_id, repo_type="dataset", private=not args.public, exist_ok=True)
    info = api.upload_folder(
        folder_path=str(out), repo_id=repo_id, repo_type="dataset",
        commit_message="Upload TRACE relevance judge benchmark",
    )
    print(f"\nDone: {info}")
    print(f"Dataset: https://huggingface.co/datasets/{repo_id}")
    if not args.public:
        print("It is private. Flip it to public in the dataset's Settings once you have checked the card and the licensing section.")


if __name__ == "__main__":
    sys.exit(main())

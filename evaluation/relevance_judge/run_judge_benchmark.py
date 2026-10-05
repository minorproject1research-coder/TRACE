"""Step 3: run candidate judge models over dataset.jsonl and score them.

  python -m evaluation.relevance_judge.run_judge_benchmark --models qwen3.5-4b-q8 gpt-oss-20b
  python -m evaluation.relevance_judge.run_judge_benchmark --all
  python -m evaluation.relevance_judge.run_judge_benchmark --report       # re-score existing results only

Per-model raw outputs go to results/<name>.jsonl (resumable: finished rows are skipped).
The summary is written to results/summary.md and printed.
"""
import argparse
import json
import math
import os
import statistics
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

from .common import build_judge_prompt, parse_verdict, read_jsonl

load_dotenv()
HERE = Path(__file__).parent
RESULTS = HERE / "results"

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

# Mirrors filter_relevant(): a paper passes only if relevant AND confidence >= this.
PROD_CONFIDENCE_THRESHOLD = 0.6


# ── backends ──────────────────────────────────────────────────────────────────

def call_ollama(client: httpx.Client, cfg: dict, prompt: str) -> str:
    body = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1},
        "keep_alive": "30m",
    }
    if "think" in cfg:
        body["think"] = cfg["think"]
    r = client.post(f"{OLLAMA_URL}/api/chat", json=body)
    r.raise_for_status()
    return r.json()["message"]["content"]


def call_nvidia(client: httpx.Client, cfg: dict, prompt: str) -> str:
    headers = {"Authorization": f"Bearer {os.environ['NVIDIA_API_KEY']}"}
    body = {"model": cfg["model"], "temperature": 0.1, "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}]}
    for attempt in range(5):
        r = client.post(NVIDIA_URL, headers=headers, json=body)
        if r.status_code in (429, 502, 503):
            time.sleep(2 ** attempt * 3)
            continue
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"] or ""
    raise RuntimeError("NVIDIA endpoint kept rate-limiting")


BACKENDS = {"ollama": call_ollama, "nvidia": call_nvidia}


# ── running ───────────────────────────────────────────────────────────────────

def run_model(cfg: dict, rows: list[dict]):
    RESULTS.mkdir(exist_ok=True)
    out_path = RESULTS / f"{cfg['name']}.jsonl"
    done = {r["id"] for r in read_jsonl(out_path)} if out_path.exists() else set()
    call = BACKENDS[cfg["backend"]]

    with httpx.Client(timeout=300) as client, out_path.open("a", encoding="utf-8") as f:
        for i, row in enumerate(rows, 1):
            if row["id"] in done:
                continue
            prompt = build_judge_prompt(row)
            raw, err = "", None
            t0 = time.perf_counter()
            try:
                raw = call(client, cfg, prompt)
            except Exception as e:
                err = str(e)[:200]
            latency = time.perf_counter() - t0
            verdict = parse_verdict(raw)
            f.write(json.dumps({"id": row["id"], "verdict": verdict, "raw": raw[:1500],
                                "error": err, "latency_s": round(latency, 3)}, ensure_ascii=False) + "\n")
            f.flush()
            if i % 20 == 0 or i == len(rows):
                print(f"  {cfg['name']}: {i}/{len(rows)}")


# ── scoring ───────────────────────────────────────────────────────────────────

def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - m) / d, (c + m) / d)


def prf(pairs: list[tuple[bool, bool]]) -> dict:
    """pairs = (gold, predicted); positive class = relevant."""
    tp = sum(g and p for g, p in pairs)
    fp = sum((not g) and p for g, p in pairs)
    fn = sum(g and (not p) for g, p in pairs)
    correct = sum(g == p for g, p in pairs)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    lo, hi = wilson(correct, len(pairs))
    return {"acc": correct / len(pairs), "acc_lo": lo, "acc_hi": hi, "prec": prec, "rec": rec, "f1": f1}


def score_model(name: str, gold: dict[str, dict]) -> dict | None:
    path = RESULTS / f"{name}.jsonl"
    if not path.exists():
        return None
    res = {r["id"]: r for r in read_jsonl(path) if r["id"] in gold}
    if not res:
        return None

    raw_pairs, prod_pairs, briers, conf_ok, conf_bad = [], [], [], [], []
    valid = 0
    for rid, r in res.items():
        g = gold[rid]["label"]["relevant"]
        v = r["verdict"]
        if v is None:                       # unparseable -> treated as "not relevant", like production
            raw_pairs.append((g, False))
            prod_pairs.append((g, False))
            continue
        valid += 1
        raw_pairs.append((g, v["relevant"]))
        prod_pairs.append((g, v["relevant"] and v["confidence"] >= PROD_CONFIDENCE_THRESHOLD))
        p_rel = v["confidence"] if v["relevant"] else 1 - v["confidence"]
        briers.append((p_rel - float(g)) ** 2)
        (conf_ok if v["relevant"] == g else conf_bad).append(v["confidence"])

    lat = sorted(r["latency_s"] for r in res.values() if not r["error"])
    raw, prod = prf(raw_pairs), prf(prod_pairs)
    return {
        "name": name, "n": len(res), "valid_json": valid / len(res), "errors": sum(bool(r["error"]) for r in res.values()),
        "acc": raw["acc"], "acc_lo": raw["acc_lo"], "acc_hi": raw["acc_hi"],
        "prec": raw["prec"], "rec": raw["rec"], "f1": raw["f1"],
        "prod_prec": prod["prec"], "prod_rec": prod["rec"], "prod_f1": prod["f1"],
        "brier": statistics.mean(briers) if briers else float("nan"),
        "conf_when_right": statistics.mean(conf_ok) if conf_ok else float("nan"),
        "conf_when_wrong": statistics.mean(conf_bad) if conf_bad else float("nan"),
        "lat_mean": statistics.mean(lat) if lat else float("nan"),
        "lat_p95": lat[int(0.95 * (len(lat) - 1))] if lat else float("nan"),
    }


def report(names: list[str], gold: dict[str, dict]):
    scores = [s for s in (score_model(n, gold) for n in names) if s]
    if not scores:
        print("No results to report.")
        return
    scores.sort(key=lambda s: s["f1"], reverse=True)
    n_pos = sum(g["label"]["relevant"] for g in gold.values())
    lines = [
        f"Gold set: {len(gold)} rows ({n_pos} relevant / {len(gold) - n_pos} not). "
        f"Majority-class baseline accuracy: {max(n_pos, len(gold) - n_pos) / len(gold):.3f}",
        "",
        "| model | n | valid JSON | acc (95% CI) | prec | rec | F1 | prod F1 @0.6 | Brier | conf right/wrong | lat mean/p95 s |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in scores:
        lines.append(
            f"| {s['name']} | {s['n']} | {s['valid_json']:.1%} | {s['acc']:.3f} ({s['acc_lo']:.2f}-{s['acc_hi']:.2f}) "
            f"| {s['prec']:.3f} | {s['rec']:.3f} | {s['f1']:.3f} | {s['prod_f1']:.3f} | {s['brier']:.3f} "
            f"| {s['conf_when_right']:.2f}/{s['conf_when_wrong']:.2f} | {s['lat_mean']:.2f}/{s['lat_p95']:.2f} |")
    text = "\n".join(lines)
    (RESULTS / "summary.md").write_text(text + "\n", encoding="utf-8")
    print("\n" + text)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", help="model names from models.json")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--report", action="store_true", help="only (re)score existing results")
    ap.add_argument("--limit", type=int, help="quick smoke test on the first N rows")
    a = ap.parse_args()

    cfgs = {m["name"]: m for m in json.loads((HERE / "models.json").read_text(encoding="utf-8"))["models"]}
    rows = read_jsonl(HERE / "dataset.jsonl")
    gold = {r["id"]: r for r in rows}
    if a.limit:
        rows = rows[: a.limit]

    selected = list(cfgs) if a.all else (a.models or [])
    if not a.report:
        for name in selected:
            if name not in cfgs:
                print(f"Unknown model '{name}'. Known: {', '.join(cfgs)}")
                continue
            print(f"Running {name} ({cfgs[name]['backend']}:{cfgs[name]['model']})")
            run_model(cfgs[name], rows)
    report(selected or list(cfgs), {r["id"]: r for r in rows} if a.limit else gold)

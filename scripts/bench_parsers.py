"""Throughput benchmark for the Docling (and optionally PDFFigures) containers.

Sends the same set of arXiv PDFs at increasing concurrency and reports wall time, per-request latency and papers/min.
With several Docling URLs the requests are spread round-robin, which is how a multi-container deployment would be used.

    python scripts/bench_parsers.py --docling http://localhost:5101
    python scripts/bench_parsers.py --docling http://localhost:5101,http://localhost:5102,http://localhost:5103 --concurrency 3,6,9
    python scripts/bench_parsers.py --docling http://localhost:5101 --figures http://localhost:5002

The PDFs are downloaded once and cached in the temp folder, so the downloads are not part of the timing.
"""
import argparse
import asyncio
import base64
import itertools
import statistics
import tempfile
import time
from pathlib import Path

import httpx

PDFS = [
    "https://arxiv.org/pdf/2411.13157", "https://arxiv.org/pdf/2311.08981", "https://arxiv.org/pdf/2404.08856",
    "https://arxiv.org/pdf/2405.19261", "https://arxiv.org/pdf/2504.09775", "https://arxiv.org/pdf/2503.00491",
    "https://arxiv.org/pdf/2305.13048", "https://arxiv.org/pdf/2302.01318", "https://arxiv.org/pdf/2211.17192",
]
CACHE = Path(tempfile.gettempdir()) / "trace_bench_pdfs"


async def load_pdfs(client: httpx.AsyncClient) -> list[bytes]:
    CACHE.mkdir(exist_ok=True)
    out = []
    for url in PDFS:
        f = CACHE / (url.rsplit("/", 1)[1] + ".pdf")
        if not f.exists():
            r = await client.get(url, follow_redirects=True)
            if r.status_code != 200 or b"%PDF" not in r.content[:10]:
                print("skip (download failed):", url)
                continue
            f.write_bytes(r.content)
        out.append(f.read_bytes())
    return out


DOCLING_OPTIONS: dict = {}          # set from --options; sent as the "options" object of /v1/convert/source


async def docling_call(client, base, pdf):
    t = time.time()
    body = {"sources": [{"kind": "file", "base64_string": base64.b64encode(pdf).decode(), "filename": "paper.pdf"}],
            "output_formats": ["markdown"]}
    if DOCLING_OPTIONS:
        body["options"] = DOCLING_OPTIONS
    r = await client.post(f"{base}/v1/convert/source", json=body)
    md = ""
    if r.status_code == 200:
        d = r.json()
        md = (d.get("document") or {}).get("md_content") or d.get("md_content") or ""
    return time.time() - t, r.status_code, len(md)


async def figures_call(client, base, pdf):
    t = time.time()
    r = await client.post(f"{base}/extract", files={"file": ("paper.pdf", pdf, "application/pdf")})
    return time.time() - t, r.status_code, 0


async def run_level(client, fn, bases, pdfs, n):
    rr = itertools.cycle(bases)
    t0 = time.time()
    res = await asyncio.gather(*(fn(client, next(rr), pdfs[i % len(pdfs)]) for i in range(n)), return_exceptions=True)
    wall = time.time() - t0
    ok = [r for r in res if not isinstance(r, Exception) and r[1] == 200]
    lat = sorted(r[0] for r in ok)
    errs = [type(r).__name__ if isinstance(r, Exception) else r[1] for r in res if isinstance(r, Exception) or r[1] != 200]
    print(f"  {n:>2} concurrent | wall {wall:6.1f}s | per-request min/median/max "
          f"{(lat[0] if lat else 0):.0f}/{(statistics.median(lat) if lat else 0):.0f}/{(lat[-1] if lat else 0):.0f}s "
          f"| ok {len(ok)}/{n} | {len(ok) / wall * 60:5.1f} papers/min" + (f" | errors {errs}" if errs else ""))
    return len(ok) / wall * 60 if wall else 0


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docling", default="http://localhost:5001", help="comma-separated Docling base URLs")
    ap.add_argument("--figures", default="", help="comma-separated PDFFigures base URLs (optional)")
    ap.add_argument("--concurrency", default="1,3,6", help="comma-separated levels")
    ap.add_argument("--options", default="", help="Docling options as JSON, e.g. {\"do_ocr\": false}")
    args = ap.parse_args()
    if args.options:
        import json
        DOCLING_OPTIONS.update(json.loads(args.options))
    levels = [int(x) for x in args.concurrency.split(",")]
    async with httpx.AsyncClient(timeout=600) as client:
        pdfs = await load_pdfs(client)
        print(f"{len(pdfs)} PDFs, sizes KB: {[len(p) // 1024 for p in pdfs]}")
        for label, fn, urls in (("Docling", docling_call, args.docling), ("PDFFigures", figures_call, args.figures)):
            bases = [u.strip().rstrip("/") for u in urls.split(",") if u.strip()]
            if not bases:
                continue
            print(f"\n{label}: {len(bases)} instance(s) {bases}")
            await run_level(client, fn, bases, pdfs, 1)             # warm-up (model load on first call)
            for n in levels:
                await run_level(client, fn, bases, pdfs, n)


if __name__ == "__main__":
    asyncio.run(main())

#!/bin/bash
# Does running more Docling containers raise parsing throughput on THIS machine?
#
# For each N in CONFIGS it starts N Docling containers (ports 5201..520N), each limited to an equal share of the CPU
# cores, sends papers round-robin at several concurrency levels (OCR off, the pipeline's setting), prints papers/min
# and removes the containers. It does not touch the real stack on ports 5001/5002.
#
#   bash scripts/bench_host.sh                  # N = 1, 2 and 4
#   CONFIGS="1 2" bash scripts/bench_host.sh    # only some
#   MEM_PER_CONTAINER_GB=3 CONFIGS="1 3" bash scripts/bench_host.sh
#
# Needs: docker, python3 with httpx (pip install httpx), internet (arXiv PDFs, cached after the first run).
# Run it while nothing else heavy is running, and do not run a pipeline at the same time.
set -u
cd "$(dirname "$0")/.."

IMAGE=${IMAGE:-ghcr.io/docling-project/docling-serve-cpu:latest}
CONFIGS=${CONFIGS:-"1 2 4"}
MEM_PER_CONTAINER_GB=${MEM_PER_CONTAINER_GB:-3}
PY=${PYTHON:-python3}
command -v "$PY" >/dev/null 2>&1 || PY=python
OPTIONS='{"do_ocr": false, "include_images": false}'

CORES=$(nproc 2>/dev/null || echo 4)
MEM_GB=$(awk '/MemAvailable/ {printf "%d", $2/1048576}' /proc/meminfo 2>/dev/null)
[ -z "$MEM_GB" ] && MEM_GB=$(docker info --format '{{.MemTotal}}' 2>/dev/null | awk '{printf "%d", $1/1073741824}')
echo "== host: $CORES cores, ~${MEM_GB:-?} GB available memory, image $IMAGE"
$PY -c "import httpx" 2>/dev/null || { echo "install httpx first:  pip install httpx"; exit 1; }
docker image inspect "$IMAGE" >/dev/null 2>&1 || docker pull "$IMAGE" || exit 1

cleanup() { docker rm -f $(docker ps -aq --filter "name=trace-hostbench-") >/dev/null 2>&1; }
trap cleanup EXIT
cleanup

for N in $CONFIGS; do
  if [ -n "$MEM_GB" ] && [ $((N * MEM_PER_CONTAINER_GB)) -gt "$MEM_GB" ]; then
    echo; echo "##### N=$N skipped: needs ~$((N * MEM_PER_CONTAINER_GB)) GB, only ~$MEM_GB GB available"; continue
  fi
  SHARE=$((CORES / N)); [ "$SHARE" -lt 1 ] && SHARE=1
  URLS=""
  for i in $(seq 1 "$N"); do
    PORT=$((5200 + i))
    docker run -d --name "trace-hostbench-$i" -p "$PORT:5001" --cpus "$SHARE" \
      -e DOCLING_SERVE_ENABLE_UI=false -e DOCLING_SERVE_LOG_LEVEL=WARNING -e DOCLING_SERVE_MAX_SYNC_WAIT=900 \
      "$IMAGE" >/dev/null
    URLS="$URLS${URLS:+,}http://localhost:$PORT"
  done
  for i in $(seq 1 "$N"); do                                   # wait until every instance answers
    for t in $(seq 1 60); do curl -sf "http://localhost:$((5200 + i))/health" >/dev/null && break; sleep 3; done
  done
  echo; echo "##### N=$N containers, each limited to $SHARE core(s)"
  $PY scripts/bench_parsers.py --docling "$URLS" --concurrency "$N,$((N * 2)),$((N * 4))" --options "$OPTIONS" 2>&1 \
    | grep -E "concurrent|instance"
  cleanup
done
echo; echo "== done. Compare the 'papers/min' column across N (best value per row group wins)."

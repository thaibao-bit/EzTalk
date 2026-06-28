#!/usr/bin/env sh
set -eu

WORKERS="${WEB_CONCURRENCY:-}"
if [ -z "$WORKERS" ]; then
  CPU_CORES="$(python - <<'PY'
import os
print(os.cpu_count() or 1)
PY
)"
  WORKERS="$((2 * CPU_CORES + 1))"
fi

exec gunicorn app.main:app \
  -w "$WORKERS" \
  -k uvicorn.workers.UvicornWorker \
  -b 0.0.0.0:8080 \
  --keep-alive "${GUNICORN_KEEP_ALIVE:-65}" \
  --access-logfile - \
  --error-logfile -

#!/usr/bin/env bash
# Start guardian-ai in Testbed mode on the GPU machine (run inside WSL). plan.md §6.9 B.
#   bash ~/guardian-ai/scripts/start_testbed.sh        # (re)start in tmux session "ai"
#   tmux attach -t ai                                   # watch the log; Ctrl+B then D to detach
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "missing $(pwd)/.env (copy .env.example and set the Testbed block)"; exit 1; }
tmux kill-session -t ai 2>/dev/null || true
tmux new-session -d -s ai "cd $(pwd) && ~/venv/bin/python -m uvicorn guardian_ai.main:app --host 0.0.0.0 --port 8000 2>&1 | tee -a $(pwd)/uvicorn.log"
for _ in $(seq 40); do curl -s -o /dev/null localhost:8000/health && break; sleep 1; done
curl -s localhost:8000/health | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['status'], d['mode'], d['host'], d['gpu']); [print(' ', k, [(r['name'], r['ready']) for r in v]) for k,v in d['backends'].items()]"

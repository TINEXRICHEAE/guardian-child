#!/usr/bin/env bash
# Serve Qwen3-VL-2B-Instruct (official GGUF: Q8_0 LLM + F16 vision encoder) with llama.cpp on the GTX 1060.
# Used for text (explain, generate) and uploaded images (extract) via guardian-ai's "qwen" backend. plan.md §4.6.
#   bash ~/guardian-ai/scripts/start_llama_server.sh     # tmux session "qwen", OpenAI-compatible API on 127.0.0.1:8081
set -euo pipefail
BIN=${LLAMA_SERVER:-$HOME/llama.cpp/build/bin/llama-server}
M=$HOME/models/qwen3vl-2b-gguf-official
[ -x "$BIN" ] || { echo "llama-server not found at $BIN (build llama.cpp first, plan.md §4.6)"; exit 1; }
export LD_LIBRARY_PATH=$HOME/cuda-12.6/lib64:/usr/lib/wsl/lib:${LD_LIBRARY_PATH:-}
tmux kill-session -t qwen 2>/dev/null || true
tmux new-session -d -s qwen "$BIN -m $M/Qwen3VL-2B-Instruct-Q8_0.gguf --mmproj $M/mmproj-Qwen3VL-2B-Instruct-F16.gguf \
  --host 127.0.0.1 --port 8081 --alias qwen3-vl-2b -ngl 99 -c 8192 --jinja 2>&1 | tee -a $HOME/llama-server.log"
for _ in $(seq 60); do curl -s -o /dev/null 127.0.0.1:8081/v1/models && break; sleep 1; done
curl -s 127.0.0.1:8081/v1/models && echo && nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader

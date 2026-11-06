#!/usr/bin/env bash
# Start everything Guardian needs on the GPU machine, from WSL. Survives SSH disconnects (tmux).
#   1. Qwen3-VL-2B (official GGUF) with the Hugging Face "Llama" Windows app on the GTX 1060   → tmux "qwen", port 8081
#   2. guardian-ai (FastAPI)                                                                      → tmux "ai",   port 8000
# Usage (inside WSL):  bash ~/guardian-ai/scripts/start_all.sh            # start what is not running
#                      bash ~/guardian-ai/scripts/start_all.sh restart    # stop both first, then start
# From another computer (use the full path: ~ is not expanded when the command arrives through Windows):
#   ssh -i ~/.ssh/hackathon_ed25519 hackathon@137.63.190.11 "wsl -d Ubuntu-24.04 -- bash /home/hackathon/guardian-ai/scripts/start_all.sh"
set -uo pipefail

LLAMA=/mnt/c/Users/hackathon/AppData/Local/Microsoft/WindowsApps/llama.exe
WIN_MODELS='C:\Users\hackathon\models\qwen3vl-2b-gguf'
WIN_KEY='C:\Users\hackathon\guardian-llama\api-key.txt'
WIN_HOST=$(ip route show default | awk '{print $3}')
NETSTAT=/mnt/c/Windows/System32/NETSTAT.EXE
TASKKILL=/mnt/c/Windows/System32/taskkill.exe

qwen_up() { curl -s -m 3 -o /dev/null -w '%{http_code}' "http://$WIN_HOST:8081/health" | grep -q 200; }
ai_up()   { curl -s -m 3 -o /dev/null localhost:8000/health; }

if [ "${1:-}" = restart ]; then
    tmux kill-session -t ai 2>/dev/null
    tmux kill-session -t qwen 2>/dev/null
    # Stop whatever listens on 8081 (leaves the Llama app's own server on 9931 alone)
    pids=$("$NETSTAT" -ano 2>&1 | tr -d '\r' | awk '$2 ~ /:8081$/ && $4 == "LISTENING" {print $5}' | sort -u)
    echo "Windows processes listening on 8081: ${pids:-none}"
    for pid in $pids; do
        out=$("$TASKKILL" /PID "$pid" /F 2>&1 | tr -d '\r')
        echo "  taskkill $pid: ${out:-no output}"
    done
    sleep 3
    left=$("$NETSTAT" -ano 2>&1 | tr -d '\r' | awk '$2 ~ /:8081$/ && $4 == "LISTENING" {print $5}' | sort -u)
    [ -n "$left" ] && echo "still listening on 8081: $left (end these llama.exe processes in Task Manager)"
fi

if qwen_up; then
    echo "qwen: already running on $WIN_HOST:8081"
else
    [ -x "$LLAMA" ] || { echo "Llama app not found at $LLAMA (install LlamaApp on Windows)"; exit 1; }
    tmux kill-session -t qwen 2>/dev/null
    tmux new-session -d -s qwen "'$LLAMA' serve -m '$WIN_MODELS\\Qwen3VL-2B-Instruct-Q8_0.gguf' \
        -mm '$WIN_MODELS\\mmproj-Qwen3VL-2B-Instruct-F16.gguf' --host 0.0.0.0 --port 8081 -ngl 99 -c 8192 \
        --alias qwen3-vl-2b --api-key-file '$WIN_KEY' 2>&1 | tee -a $HOME/llama-server.log"
    printf 'qwen: starting'; for _ in $(seq 60); do qwen_up && break; printf '.'; sleep 2; done; echo
    qwen_up && echo "qwen: ready on $WIN_HOST:8081" || { echo "qwen: did not start, see ~/llama-server.log"; tail -5 ~/llama-server.log; }
fi

if [ "${1:-}" != restart ] && ai_up; then
    echo "guardian-ai: already running on :8000"
else
    bash "$(dirname "$0")/start_testbed.sh"
fi

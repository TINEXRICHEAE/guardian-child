#!/usr/bin/env bash
# Laptop side: keep the SSH tunnel to the GPU machine up, reconnecting after sleep, Wi-Fi changes or drops.
#   bash guardian-ai/scripts/tunnel.sh        # leave running; Ctrl+C to stop
# Django then reaches guardian-ai at http://localhost:8100 (GUARDIAN_AI_URL in pita/.env).
KEY=${GUARDIAN_GPU_KEY:-$HOME/.ssh/hackathon_ed25519}
HOST=${GUARDIAN_GPU_HOST:-hackathon@137.63.190.11}
PORT=${GUARDIAN_AI_LOCAL_PORT:-8100}

while true; do
    echo "$(date +%T) connecting tunnel localhost:$PORT -> $HOST guardian-ai:8000"
    ssh -i "$KEY" -N -o BatchMode=yes -o ExitOnForwardFailure=yes -o ConnectTimeout=10 \
        -o ServerAliveInterval=15 -o ServerAliveCountMax=2 -L "$PORT:127.0.0.1:8000" "$HOST"
    echo "$(date +%T) tunnel closed (exit $?); reconnecting in 3 s"
    sleep 3
done

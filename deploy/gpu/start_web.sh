#!/usr/bin/env bash
# Start (or restart) the public Guardian web server on the GPU machine, from WSL (plan.md §20).
#   tmux "web"   gunicorn + Django on 127.0.0.1:8001 inside WSL
#   tmux "proxy" Caddy on Windows (ports 80/443, HTTPS) forwarding to 127.0.0.1:8001
# Usage:  bash ~/guardian-web/app/deploy/gpu/start_web.sh [restart]
set -uo pipefail
ROOT=$HOME/guardian-web
APP=$ROOT/app
WIN_DIR='C:\Users\hackathon\guardian-web'
CADDY=/mnt/c/Users/hackathon/guardian-web/caddy.exe

web_up()   { curl -s -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:8001/ | grep -qE '200|302'; }

PIDFILE=$ROOT/gunicorn.pid
if [ "${1:-}" = restart ]; then
    tmux kill-session -t web 2>/dev/null
    # Stop the old gunicorn and wait for the process itself to exit (it may still answer while shutting down)
    if [ -f "$PIDFILE" ]; then
        OLD=$(cat "$PIDFILE")
        kill "$OLD" 2>/dev/null
        for _ in $(seq 20); do kill -0 "$OLD" 2>/dev/null || break; sleep 1; done
        kill -9 "$OLD" 2>/dev/null; rm -f "$PIDFILE"
    fi
    pkill -9 -f 'gunicorn pita.wsgi' 2>/dev/null; sleep 1
    /mnt/c/Windows/System32/taskkill.exe /IM caddy.exe /F >/dev/null 2>&1
    sleep 2
fi

if web_up; then
    echo "web: already running on 127.0.0.1:8001"
else
    tmux kill-session -t web 2>/dev/null
    tmux new-session -d -s web "cd $APP/pita && $ROOT/venv/bin/gunicorn pita.wsgi:application \
        --bind 127.0.0.1:8001 --workers 2 --threads 4 --timeout 700 --graceful-timeout 10 --pid $PIDFILE \
        --access-logfile $ROOT/logs/access.log --error-logfile $ROOT/logs/error.log"
    for _ in $(seq 30); do web_up && break; sleep 1; done
    web_up && echo "web: started" || echo "web: NOT answering, see $ROOT/logs/error.log"
fi

# Caddy is a Windows program. Launch it straight from this WSL session, detached (setsid + nohup), and not
# from tmux: the long-lived tmux server cannot reach Windows once the WSL session that started it has ended.
# Windows processes launched this way keep running after the session ends (as llama.exe does). No admin needed.
caddy_running() { /mnt/c/Windows/System32/tasklist.exe /FI "IMAGENAME eq caddy.exe" 2>/dev/null | tr -d '\r' | grep -qi caddy.exe; }
if caddy_running; then
    echo "proxy: Caddy already running"
else
    [ -x "$CADDY" ] || { echo "caddy.exe missing at $CADDY (run deploy/deploy_gpu.sh again)"; exit 1; }
    ( cd /mnt/c/Users/hackathon/guardian-web && setsid nohup "$CADDY" run --config 'C:\Users\hackathon\guardian-web\Caddyfile' \
        --adapter caddyfile > "$ROOT/logs/caddy-start.log" 2>&1 < /dev/null & )
    sleep 6
    if caddy_running; then echo "proxy: Caddy started (log: $WIN_DIR\\caddy.log)"
    elif [ -n "${SSH_CONNECTION:-}${SSH_CLIENT:-}" ] || ! /mnt/c/Windows/System32/tasklist.exe >/dev/null 2>&1; then
        echo "proxy: not started over SSH (Windows closes it when SSH ends)."
        echo "       At the machine's desktop, double-click C:\\Users\\hackathon\\guardian-web\\Start Guardian Web.bat"
    else echo "proxy: Caddy did not start:"; cat "$ROOT/logs/caddy-start.log"; fi
fi

#!/usr/bin/env bash
# Runs inside WSL on the GPU machine after deploy_gpu.sh has uploaded the code (plan.md §20).
# Unpacks the release, installs dependencies, migrates, collects static files, optionally loads data, restarts.
#   bash server_setup.sh <release.tar.gz> <server.env> [data.json]
set -euo pipefail
RELEASE=$1; ENVFILE=$2; DATA=${3:-}
ROOT=$HOME/guardian-web
mkdir -p "$ROOT/data/media" "$ROOT/logs"

# Fresh copy of the code (data and venv live outside app/ and survive redeploys)
rm -rf "$ROOT/app.new" && mkdir -p "$ROOT/app.new"
tar -xzf "$RELEASE" -C "$ROOT/app.new"
cp "$ENVFILE" "$ROOT/app.new/pita/.env" && chmod 600 "$ROOT/app.new/pita/.env"
rm -rf "$ROOT/app.old"; [ -d "$ROOT/app" ] && mv "$ROOT/app" "$ROOT/app.old"
mv "$ROOT/app.new" "$ROOT/app"

[ -d "$ROOT/venv" ] || python3 -m venv "$ROOT/venv"
"$ROOT/venv/bin/pip" install -q --upgrade pip
"$ROOT/venv/bin/pip" install -q -r "$ROOT/app/requirements.txt"

cd "$ROOT/app/pita"
"$ROOT/venv/bin/python" manage.py migrate --noinput
"$ROOT/venv/bin/python" manage.py collectstatic --noinput -v 0
if [ -n "$DATA" ]; then
    echo "loading data from $DATA"
    "$ROOT/venv/bin/python" manage.py loaddata "$DATA"
fi
"$ROOT/venv/bin/python" manage.py check --deploy 2>&1 | tail -3 || true
bash "$ROOT/app/deploy/gpu/start_web.sh" restart

#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_dir"

if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -e ".[dev]"
fi

if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm install)
fi

trap 'kill 0' EXIT INT TERM
.venv/bin/uvicorn neroops.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000 &
(cd frontend && npm run dev -- --host 127.0.0.1) &
wait


#!/bin/zsh

set -u

PROJECT_DIR="${0:A:h}"
AGENT="$HOME/Library/LaunchAgents/com.neroops.server.plist"
SERVICE="gui/$(id -u)/com.neroops.server"
PID_FILE="$PROJECT_DIR/logs/server.pid"
URL="http://localhost:8000"

cd "$PROJECT_DIR" || exit 1

if ! curl --silent --fail --max-time 1 "$URL/api/v1/health" >/dev/null 2>&1; then
  if [[ -f "$AGENT" ]]; then
    if ! launchctl print "$SERVICE" >/dev/null 2>&1; then
      launchctl bootstrap "gui/$(id -u)" "$AGENT"
    else
      launchctl kickstart "$SERVICE"
    fi
  else
    mkdir -p logs
    nohup .venv/bin/uvicorn neroops.main:app \
      --app-dir backend \
      --host 127.0.0.1 \
      --port 8000 \
      >>logs/server.log 2>>logs/server-error.log &
    echo $! > "$PID_FILE"
  fi
fi

for _ in {1..30}; do
  if curl --silent --fail --max-time 1 "$URL/api/v1/health" >/dev/null 2>&1; then
    open "$URL"
    echo "NeroOps запущен: $URL"
    exit 0
  fi
  sleep 0.5
done

echo "Не удалось запустить NeroOps."
echo "Проверьте журнал: $PROJECT_DIR/logs/server-error.log"
exit 1

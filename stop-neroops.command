#!/bin/zsh

set -u

PROJECT_DIR="${0:A:h}"
SERVICE="gui/$(id -u)/com.neroops.server"
PID_FILE="$PROJECT_DIR/logs/server.pid"
STOPPED=0

if launchctl print "$SERVICE" >/dev/null 2>&1; then
  if launchctl bootout "$SERVICE"; then
    STOPPED=1
  else
    echo "Не удалось остановить службу NeroOps."
    exit 1
  fi
fi

if [[ -f "$PID_FILE" ]]; then
  PID="$(<"$PID_FILE")"
  if [[ "$PID" == <-> ]] && kill -0 "$PID" >/dev/null 2>&1; then
    kill "$PID"
    STOPPED=1
  fi
  rm -f "$PID_FILE"
fi

# Stop a NeroOps process started manually or by an older launcher.
for PID in ${(f)"$(lsof -tiTCP:8000 -sTCP:LISTEN 2>/dev/null)"}; do
  PROCESS_CWD="$(lsof -a -p "$PID" -d cwd -Fn 2>/dev/null)"
  if [[ "$PROCESS_CWD" == *"n$PROJECT_DIR"* ]]; then
    kill "$PID" 2>/dev/null
    STOPPED=1
  fi
done

for _ in {1..20}; do
  if ! lsof -tiTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

if lsof -tiTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Порт 8000 всё ещё занят другим процессом."
  echo "NeroOps не был полностью выключен."
  exit 1
fi

if (( STOPPED )); then
  echo "NeroOps выключен. Записи сохранены."
else
  echo "NeroOps уже выключен."
fi

echo "Браузер может показывать сохранённую офлайн-копию страницы."
echo "Без сервера новые записи останутся только в офлайн-очереди."

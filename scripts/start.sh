#!/usr/bin/env bash
# 后台启动本地 Web 服务，用法：./scripts/start.sh [port]
# 示例：WEB_PORT=9000 ./scripts/start.sh
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PORT="${1:-${WEB_PORT:-8765}}"
WEB_PORT="${WEB_PORT:-8765}"
HOST="${WEB_HOST:-127.0.0.1}"
WEB_HOST="${WEB_HOST:-127.0.0.1}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
LOG_FILE="${LOG_FILE:-/tmp/spellforge-web-$PORT.log}"
PID_FILE="${PID_FILE:-/tmp/spellforge-web-$PORT.pid}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "找不到 Python：$PYTHON_BIN" >&2
  exit 1
fi

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -n 2 | tail -n +2 | grep -q .; then
  echo "端口 $PORT 已被占用" >&2
  echo "如需停掉本仓库服务：./scripts/stop.sh $PORT" >&2
  exit 1
fi

echo "启动 http://127.0.0.1:$PORT（日志：$LOG_FILE）"
WEB_PORT="$PORT" WEB_HOST="$HOST" nohup "$PYTHON_BIN" -m web.app > "$LOG_FILE" 2>&1 &
PID=$!
echo "$PID" > "$PID_FILE"

ready=0
for _ in {1..40}; do
  if curl -s --noproxy '*' -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/api/version" | grep -q '^200$'; then
    ready=1
    break
  fi
  if ! kill -0 "$PID" 2>/dev/null; then
    break
  fi
  sleep 0.25
done

if [[ "$ready" -ne 1 ]]; then
  echo "服务没有在 10 秒内响应，最近日志：" >&2
  tail -n 40 "$LOG_FILE" >&2 || true
  kill "$PID" 2>/dev/null || true
  rm -f "$PID_FILE"
  exit 1
fi

echo "服务已就绪，PID：$PID"
echo "停止服务：./scripts/stop.sh $PORT"

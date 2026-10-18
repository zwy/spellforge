#!/usr/bin/env bash
# 停止本仓库的 SpellForge Web 服务，用法：./scripts/stop.sh [port]
# 示例：./scripts/stop.sh
#       WEB_PORT=9000 ./scripts/stop.sh
#       ./scripts/stop.sh --dry-run
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
  shift
fi
PORT="${1:-${WEB_PORT:-8765}}"

listeners="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | tail -n +2 | awk '{print $2}' | sort -u)"
if [[ -z "$listeners" ]]; then
  echo "端口 $PORT 上没有监听进程。"
  exit 0
fi

stopped_any=0
for PID in $listeners; do
  CMD="$(ps -p "$PID" -o command= 2>/dev/null || true)"
  CWD="$(lsof -a -p "$PID" -d cwd -F n 2>/dev/null | sed -n 's/^n//p' | head -n 1)"
  SAFE=0
  if [[ "$CWD" == "$ROOT" && "$CMD" == *web.app* ]]; then
    SAFE=1
  fi

  echo "PID $PID"
  echo "  cwd: ${CWD:-未知}"
  echo "  command: ${CMD:-未知}"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "  dry-run: $([[ "$SAFE" -eq 1 ]] && echo '会停止' || echo '会拒绝')"
    continue
  fi

  if [[ "$SAFE" -ne 1 ]]; then
    echo "  拒绝停止：当前目录或命令不是本仓库的 SpellForge web.app" >&2
    continue
  fi

  kill "$PID"
  for _ in {1..30}; do
    if ! kill -0 "$PID" 2>/dev/null; then
      break
    fi
    sleep 0.1
  done
  if kill -0 "$PID" 2>/dev/null; then
    kill -9 "$PID" 2>/dev/null || true
  fi
  echo "  已发送停止信号，进程已退出。"
  stopped_any=1
done

rm -f "/tmp/spellforge-web-$PORT.pid" 2>/dev/null || true

if [[ "$stopped_any" -eq 1 ]]; then
  echo "SpellForge 已停止。"
elif [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Dry run 已检查，未执行停止。"
else
  echo "没有找到可安全停止的 SpellForge 进程。"
fi

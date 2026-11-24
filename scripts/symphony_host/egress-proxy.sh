#!/usr/bin/env bash
# Startet/stoppt den Allowlist-Egress-Proxy als Nutzerprozess (kein Root).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
: "${PILOT_DIR:=/workspace/symphony-pilot}"
PORT="${GMV_EGRESS_PROXY_PORT:-18443}"
PIDFILE="$PILOT_DIR/log/egress-proxy.pid"
LOG="$PILOT_DIR/log/egress-proxy.log"
mkdir -p "$PILOT_DIR/log"
PROXY_PY="$HERE/symphony_egress_proxy.py"
[ -f "$PROXY_PY" ] || PROXY_PY="$HERE/../symphony_egress_proxy.py"
running() { [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }
case "${1:-status}" in
  start)
    if ! running; then
      nohup python3 "$PROXY_PY" --port "$PORT" >>"$LOG" 2>&1 &
      echo $! >"$PIDFILE"
      for _ in $(seq 1 20); do
        (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null && break
        sleep 0.2
      done
    fi
    running && echo "egress-proxy läuft auf 127.0.0.1:$PORT" ;;
  stop) running && kill "$(cat "$PIDFILE")"; rm -f "$PIDFILE"; echo "egress-proxy gestoppt" ;;
  status) running && echo "läuft" || { echo "gestoppt"; exit 1; } ;;
esac

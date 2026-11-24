#!/usr/bin/env bash
# Nachweis ohne Symphony-Lauf und ohne Modell-Call (ENG-003).
# 1. Außerhalb: Secret-Pfade lesbar.
# 2. Im bwrap-Namespace: Secret-Pfade leer/fehlend.
# 3. In der Codex-Sandbox (codex app-server, command/exec mit der Turn-Policy
#    aus WORKFLOW.md): Secrets, Schreibgrenzen, Netz über den Egress-Proxy.
# Ausgegeben werden nur Existenz, Größen und HTTP-Status, keine Inhalte.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "$HERE/bwrap-env.sh"
WORKFLOW="${1:-$PILOT_DIR/WORKFLOW.md}"
PROXY_PORT="${GMV_EGRESS_PROXY_PORT:-18443}"
"$HERE/egress-proxy.sh" start >/dev/null

probe_paths='for p in "$HOME/secrets/gmv-symphony-worker.pem" "$HOME/.config/gh/hosts.yml" "$HOME/.gitconfig" "$HOME/.git-credentials" "$HOME/.codex/sessions" "$HOME/cli-config"; do
  if [ -d "$p" ]; then echo "$p: dir, $(ls -A "$p" 2>/dev/null | wc -l) Einträge";
  elif [ -r "$p" ] && [ -s "$p" ]; then echo "$p: LESBAR ($(wc -c < "$p") Bytes)";
  elif [ -e "$p" ]; then echo "$p: leer/nicht lesbar"; else echo "$p: fehlt"; fi; done'

echo "== 1 außerhalb"
bash -c "$probe_paths"
mapfile -d '' BW < <(gmv_bwrap_args)
echo "== 2 bwrap-Namespace"
bwrap "${BW[@]}" -- bash -c "$probe_paths"
echo "== 2b Modell-Hosts direkt aus dem Namespace (ohne Auth, nur Status)"
bwrap "${BW[@]}" -- bash -c 'for u in https://chatgpt.com/ https://auth.openai.com/; do echo "$u $(curl -s -o /dev/null -w %{http_code} --max-time 10 "$u")"; done'
echo "== 3 Codex-Sandbox (Turn-Policy aus $WORKFLOW)"
mkdir -p "$PILOT_DIR/workspaces/SELFTEST-A" "$PILOT_DIR/workspaces/SELFTEST-B"
PY="${GMV_TOOLS_PYTHON:-$PILOT_DIR/tools-venv/bin/python}"  # braucht PyYAML
bwrap "${BW[@]}" -- "$PY" "$HERE/codex_exec_probe.py" "$WORKFLOW" "$PILOT_DIR/workspaces/SELFTEST-A" "$probe_paths"
rm -rf "$PILOT_DIR/workspaces/SELFTEST-A" "$PILOT_DIR/workspaces/SELFTEST-B"

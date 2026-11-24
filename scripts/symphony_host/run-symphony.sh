#!/usr/bin/env bash
# Einziger zulässiger Start von Symphony auf dem Pilot-Host (ENG-003).
#
# 1. Startfreigabe prüfen (GMV_SYMPHONY_START_APPROVED=yes, nur mit CEO-Go).
# 2. Allowlist-Egress-Proxy als Nutzerprozess starten (egress-proxy.sh).
# 3. Installation-Token der App gmv-symphony-worker erzeugen (symphony_app_token.py,
#    außerhalb von bwrap, weil nur hier der App-Key lesbar ist).
# 4. Symphony in bwrap starten: App-Key, gh-Konfiguration, Git-Credentials,
#    ~/.codex (außer auth.json), Browser-/CLI-Profile, /cursor und /workspace
#    (außer dem Pilot-Verzeichnis) sind ausgeblendet (bwrap-env.sh).
# Kein Root, keine Rechteänderung.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "$HERE/bwrap-env.sh"
cd "$PILOT_DIR"
if [ "${GMV_SYMPHONY_START_APPROVED:-}" != "yes" ]; then
  echo "BLOCKED: Symphony-Start nicht freigegeben (GMV_SYMPHONY_START_APPROVED)" >&2
  exit 2
fi
TOKEN_PY="$HERE/symphony_app_token.py"
[ -f "$TOKEN_PY" ] || TOKEN_PY="$HERE/../symphony_app_token.py"
"$HERE/egress-proxy.sh" start
mapfile -d '' BW < <(gmv_bwrap_args)
# Symphony verlangt zusätzlich das Guardrail-Flag
# (--i-understand-that-this-will-be-running-without-the-usual-guardrails).
# Es wird bewusst NICHT hier hinterlegt, sondern erst mit dem CEO-Go ergänzt.
exec python3 "$TOKEN_PY" exec -- \
  bwrap "${BW[@]}" --chdir "$PILOT_DIR" -- \
  ./symphony-nightly-linux_x86_64 --logs-root ./log ./WORKFLOW.md

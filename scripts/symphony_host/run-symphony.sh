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
# 5. Externer Wächter (symphony_watchdog.py, nur hinter der Startfreigabe) startet
#    Symphony als Kind und stoppt den ganzen Prozessbaum per SIGTERM (SIGKILL nach
#    Frist, danach verifiziert), sobald 2M - 300k Tokens erreicht sind, ein zweites
#    Issue, ein zweiter Dispatch oder ein Retry-Zyklus beginnt, der erste Lauf endet
#    oder eine Schleife erkennbar ist. Danach widerruft symphony_app_token.py das
#    Installation-Token.
# 6. Genau ein Lauf: log/pilot-run.once wird angelegt; existiert sie, kein Start.
# 7. Guardrail-Flag nur per Opt-in GMV_SYMPHONY_GUARDRAIL_FLAG_APPROVED=yes für
#    genau diesen Aufruf; nie dauerhaft hinterlegt.
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
WATCHDOG="$HERE/symphony_watchdog.py"
[ -f "$WATCHDOG" ] || { echo "BLOCKED: Wächter fehlt ($WATCHDOG)" >&2; exit 2; }
ONCE="$PILOT_DIR/log/pilot-run.once"
if [ -e "$ONCE" ]; then
  echo "BLOCKED: Pilot-Lauf wurde bereits gestartet ($ONCE); kein zweiter Lauf" >&2
  exit 2
fi
SYM_FLAGS=()
if [ "${GMV_SYMPHONY_GUARDRAIL_FLAG_APPROVED:-}" = "yes" ]; then
  SYM_FLAGS+=(--i-understand-that-this-will-be-running-without-the-usual-guardrails)
fi
unset GMV_SYMPHONY_GUARDRAIL_FLAG_APPROVED GMV_SYMPHONY_START_APPROVED
"$HERE/egress-proxy.sh" start
mapfile -d '' BW < <(gmv_bwrap_args)
TS="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$PILOT_DIR/log/log"
date -Iseconds > "$ONCE"
exec python3 "$TOKEN_PY" exec -- \
  python3 "$WATCHDOG" --log "$PILOT_DIR/log/log" \
    --stdout-file "$PILOT_DIR/log/run-$TS.out" \
    --budget 2000000 --reserve 300000 --max-sessions 3 --max-runtime 3600 -- \
  bwrap "${BW[@]}" --chdir "$PILOT_DIR" -- \
  ./symphony-nightly-linux_x86_64 "${SYM_FLAGS[@]}" --logs-root ./log ./WORKFLOW.md \
  2>>"$PILOT_DIR/log/watchdog-$TS.log"

#!/usr/bin/env bash
# Einziger zulässiger Start von Symphony auf dem Pilot-Host (ENG-003).
# Ein Aufruf = genau ein Issue (GMV_SYMPHONY_ISSUE). Parallelität entsteht nur
# über getrennte Aufrufe je Issue; jeder belegt einen Slot im gemeinsamen
# Zähler mit research.sh (max. 10 Läufe Codex+Symphony insgesamt).
#
# 1. Startfreigabe prüfen (GMV_SYMPHONY_START_APPROVED=yes, nur mit CEO-Go).
# 2. Issue prüfen; Einmal-Sperre pro Issue: log/once/issue-<n>.once existiert -> kein Start.
# 3. Quota-Stopp-Marker prüfen (fail-closed, rc=9, docs/symphony/quota-refresh.md).
# 4. Slot im gemeinsamen Zähler belegen (flock auf /workspace/research/.research.lock,
#    Slot-Datei state/slots/<pid>; rc=5, wenn voll). Freigabe beim Beenden (trap).
#    Symphony-Anteil: höchstens gmv.dispatch_gate.max_concurrent aus WORKFLOW.md.
# 5. Einmal-Sperre per O_EXCL anlegen: bei einem Race gewinnt genau ein Aufruf.
# 5b. Lauf-Verzeichnis runs/issue-<n>/ exklusiv anlegen: eigene WORKFLOW.md (eigenes
#    Tracker-Label gmv-symphony-issue-<n>, eigener workspace.root), logs-root, Protokolle.
#    In bwrap ist nur dieses Verzeichnis beschreibbar (Pilot-Verzeichnis read-only).
# 6. Allowlist-Egress-Proxy als Nutzerprozess starten (egress-proxy.sh), unter dem
#    Slot-Lock; gestoppt wird er nur, wenn kein Symphony-Slot mehr lebt (run-wave.sh).
# 7. Installation-Token der App gmv-symphony-worker erzeugen (symphony_app_token.py,
#    außerhalb von bwrap, weil nur hier der App-Key lesbar ist).
# 8. Symphony in bwrap starten: App-Key, gh-Konfiguration, Git-Credentials,
#    ~/.codex (außer auth.json, read-only), Browser-/CLI-Profile, /mnt, /cursor und
#    /workspace (außer dem Pilot-Verzeichnis) sind ausgeblendet (bwrap-env.sh).
# 9. Externer Wächter (symphony_watchdog.py) startet Symphony als Kind und stoppt den
#    ganzen Prozessbaum per SIGTERM (SIGKILL nach Frist, danach verifiziert), sobald
#    5M - 300k Tokens erreicht sind, ein zweites Issue, ein zweiter Dispatch oder ein
#    Retry-Zyklus beginnt, der erste Lauf endet oder eine Schleife erkennbar ist.
#    Danach widerruft symphony_app_token.py das Installation-Token.
# 10. Nach dem Lauf: Protokolle auf Quota/Rate-Limit/Auth/Refresh prüfen. Treffer ->
#    ALERTS.log + Stopp-Marker, rc=9, kein Retry. Danach den Ausgang bewerten: nur
#    bekannte Wächter-Stopps gelten als geklärt; jeder unklare Ausgang (auch ein
#    Abbruch nach der Einmal-Sperre) -> ALERTS.log + Lauf-Stopp-Marker, rc=13.
#    Freigabe von Sperren nur manuell und protokolliert (symphony_dispatch_gate.py
#    release), nie aus diesem Skript.
# Pfade für Slots, Lock, ALERTS.log und Marker sind im Gate fest verdrahtet;
# GMV_SHARED_SLOT_*/GMV_ALERTS_LOG/GMV_QUOTA_STOP/GMV_RUN_STOP mit anderem Wert -> rc=2.
# 11. Guardrail-Flag nur per Opt-in GMV_SYMPHONY_GUARDRAIL_FLAG_APPROVED=yes für
#    genau diesen Aufruf; nie dauerhaft hinterlegt.
# Kein Root, keine Rechteänderung, kein Schreibzugriff auf auth.json.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "$HERE/bwrap-env.sh"
cd "$PILOT_DIR"
if [ "${GMV_SYMPHONY_START_APPROVED:-}" != "yes" ]; then
  echo "BLOCKED: Symphony-Start nicht freigegeben (GMV_SYMPHONY_START_APPROVED)" >&2
  exit 2
fi
ISSUE="${GMV_SYMPHONY_ISSUE:-}"
if ! [[ "$ISSUE" =~ ^[1-9][0-9]{0,6}$ ]]; then
  echo "BLOCKED: GMV_SYMPHONY_ISSUE fehlt oder ist ungültig" >&2
  exit 2
fi
TOKEN_PY="$HERE/symphony_app_token.py"
[ -f "$TOKEN_PY" ] || TOKEN_PY="$HERE/../symphony_app_token.py"
GATE_PY="$HERE/symphony_dispatch_gate.py"
[ -f "$GATE_PY" ] || GATE_PY="$HERE/../symphony_dispatch_gate.py"
[ -f "$GATE_PY" ] || { echo "BLOCKED: Dispatch-Gate fehlt ($GATE_PY)" >&2; exit 2; }
WATCHDOG="$HERE/symphony_watchdog.py"
[ -f "$WATCHDOG" ] || { echo "BLOCKED: Wächter fehlt ($WATCHDOG)" >&2; exit 2; }
ONCE_DIR="$PILOT_DIR/log/once"
ONCE="$ONCE_DIR/issue-$ISSUE.once"
if [ -e "$ONCE" ]; then
  echo "BLOCKED: Issue #$ISSUE wurde bereits gestartet ($ONCE); kein zweiter Lauf" >&2
  exit 2
fi
python3 "$GATE_PY" quota-check || exit $?
SLOT_HELD=0
ONCE_TAKEN=0
VERDICT_DONE=0
WD_LOG=""
release_slot() {
  local rc=$?
  # Unklarer Abbruch nach once-acquire (Proxy, Token, Signal, set -e): fail-closed.
  if [ "$ONCE_TAKEN" = 1 ] && [ "$VERDICT_DONE" = 0 ]; then
    VERDICT_DONE=1
    python3 "$GATE_PY" run-verdict --issue "$ISSUE" --rc 99 || rc=13
  fi
  if [ "$SLOT_HELD" = 1 ]; then
    python3 "$GATE_PY" slot-release --issue "$ISSUE" --pid "$$" || true
    SLOT_HELD=0
  fi
  exit "$rc"
}
trap release_slot EXIT
python3 "$GATE_PY" slot-acquire --issue "$ISSUE" --pid "$$" \
  --workflow "$PILOT_DIR/WORKFLOW.md" || exit $?
SLOT_HELD=1
if ! python3 "$GATE_PY" once-acquire --issue "$ISSUE" --dir "$ONCE_DIR"; then
  echo "BLOCKED: Issue #$ISSUE wurde bereits gestartet; kein zweiter Lauf" >&2
  exit 2
fi
ONCE_TAKEN=1
SYM_FLAGS=()
if [ "${GMV_SYMPHONY_GUARDRAIL_FLAG_APPROVED:-}" = "yes" ]; then
  SYM_FLAGS+=(--i-understand-that-this-will-be-running-without-the-usual-guardrails)
fi
unset GMV_SYMPHONY_GUARDRAIL_FLAG_APPROVED GMV_SYMPHONY_START_APPROVED
# Eigener Lauf-Zustand je Issue (Samira, Bedingung 1): runs/issue-<n>/ mit eigener
# WORKFLOW.md (Label gmv-symphony-issue-<n>, workspace.root im Lauf-Verzeichnis),
# logs-root, Dashboard-Ausgabe und Wächter-Log. Exklusiv angelegt; existiert es: kein Start.
RUN_DIR=$(python3 "$GATE_PY" prepare-run --issue "$ISSUE" --runs-dir "$PILOT_DIR/runs" \
  --workflow "$PILOT_DIR/WORKFLOW.md") || exit 2
LOGROOT="$RUN_DIR/log"
RUN_OUT="$RUN_DIR/run.out"
WD_LOG="$RUN_DIR/watchdog.log"
# Gemeinsamer Egress-Proxy: Start nur unter dem Slot-Lock (kein Start-/Stop-Race).
python3 "$GATE_PY" proxy-start --proxy-script "$HERE/egress-proxy.sh"
mapfile -d '' BW < <(gmv_bwrap_args)
# Einengung im Wrapper (bwrap-env.sh unverändert): Pilot-Verzeichnis nur lesbar,
# beschreibbar nur das eigene Lauf-Verzeichnis. Spätere Mounts überdecken frühere.
ISO=(--ro-bind "$PILOT_DIR" "$PILOT_DIR" --bind "$RUN_DIR" "$RUN_DIR")
set +e
python3 "$TOKEN_PY" exec -- \
  python3 "$WATCHDOG" --log "$LOGROOT/log" \
    --stdout-file "$RUN_OUT" \
    --budget 5000000 --reserve 300000 --max-sessions 3 --max-runtime 3600 -- \
  bwrap "${BW[@]}" "${ISO[@]}" --chdir "$RUN_DIR" -- \
  "$PILOT_DIR/symphony-nightly-linux_x86_64" "${SYM_FLAGS[@]}" --logs-root "$LOGROOT" \
  "$RUN_DIR/WORKFLOW.md" \
  2>>"$WD_LOG" &
CHILD=$!
trap 'kill -TERM "$CHILD" 2>/dev/null' TERM INT
wait "$CHILD"; RC=$?
while kill -0 "$CHILD" 2>/dev/null; do wait "$CHILD"; RC=$?; done
set -e
shopt -s nullglob
if ! python3 "$GATE_PY" quota-scan --issue "$ISSUE" "$RUN_OUT" "$WD_LOG" "$LOGROOT"/log/*; then
  VERDICT_DONE=1
  echo "ALERT: Quota/Auth fail-closed für Issue #$ISSUE (ALERTS.log); kein Retry" >&2
  exit 9
fi
VERDICT_DONE=1
if ! python3 "$GATE_PY" run-verdict --issue "$ISSUE" --rc "$RC" --watchdog-log "$WD_LOG"; then
  echo "ALERT: unklarer Ausgang für Issue #$ISSUE (ALERTS.log); weitere Starts gesperrt" >&2
  exit 13
fi
exit "$RC"

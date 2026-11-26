#!/usr/bin/env bash
# Ein Paket für genau ein Issue: Labels setzen, Lauf (pilot-one-run.sh), Proxy-Regel.
# Host: /workspace/symphony-pilot/run-wave.sh (Vorlage im Repo, siehe
# docs/symphony/parallel-isolation.md).
#
# Labels: gmv-symphony-pilot (gemeinsam) und gmv-symphony-issue-<n> (nur dieses Issue).
# Die je Lauf erzeugte WORKFLOW.md verlangt beide; so routet jeder Symphony-Prozess
# nur sein eigenes Issue (tracker.required_labels ist eine UND-Bedingung).
#
# Proxy-Regel (Samira, Bedingung 2): Der gemeinsame Egress-Proxy wird nur gestoppt,
# wenn kein Symphony-Slot mehr lebt. Prüfung und Stopp laufen atomar unter dem
# flock des gemeinsamen Slot-Zählers (symphony_dispatch_gate.py proxy-stop-if-idle).
# Lebt noch ein Slot: kein Stopp, Eintrag in ALERTS.log, rc=14.
set -uo pipefail
N=${1:-}
[[ "$N" =~ ^[1-9][0-9]{0,6}$ ]] || { echo "ABBRUCH: Issue-Nummer fehlt/ungültig"; exit 20; }
R=tiktokagentur-art/gmv-foundation
P=${PILOT_DIR:-/workspace/symphony-pilot}
cd "$P" || exit 20
GATE_PY="$P/bin/symphony_dispatch_gate.py"
[ -f "$GATE_PY" ] || { echo "ABBRUCH: Dispatch-Gate fehlt ($GATE_PY)"; exit 20; }
[ -e "runs/issue-$N" ] && { echo "ABBRUCH: runs/issue-$N existiert (Issue schon gelaufen)"; exit 20; }
gh issue edit "$N" -R "$R" --add-label gmv-symphony-pilot --add-label "gmv-symphony-issue-$N" >/dev/null \
  || { echo "ABBRUCH: Labels nicht gesetzt"; exit 21; }
sleep "${GMV_WAVE_LABEL_DELAY:-6}"
mkdir -p log
./pilot-one-run.sh "$N" 2>&1 | tee "log/pilot-one-run-$N.out"
RUN_RC=${PIPESTATUS[0]}
gh issue edit "$N" -R "$R" --remove-label "gmv-symphony-issue-$N" >/dev/null || true
python3 "$GATE_PY" proxy-stop-if-idle --proxy-script "$P/bin/egress-proxy.sh" --issue "$N"
PRC=$?
if [ "$PRC" -eq 14 ]; then
  echo "FEHLER: Egress-Proxy nicht gestoppt, es lebt noch ein Symphony-Slot (ALERTS.log)" >&2
  exit 14
elif [ "$PRC" -ne 0 ]; then
  echo "FEHLER: Proxy-Prüfung rc=$PRC" >&2
  exit "$PRC"
fi
exit "$RUN_RC"

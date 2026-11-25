#!/usr/bin/env bash
# Ein Pilotlauf für genau ein Issue: Vorabprüfung, Proxy, Selbsttest, ein Start.
# Host: /workspace/symphony-pilot/pilot-one-run.sh (Vorlage im Repo, aufgerufen von
# run-wave.sh). Siehe docs/symphony/parallel-isolation.md.
#
# Parallel je Issue (Samira, Review #149, Auflage 3):
# - statt „genau ein offenes Issue mit gmv-symphony-pilot“ und „0 Symphony-Prozesse“:
#   Issue #<n> ist offen und trägt gmv-symphony-pilot und gmv-symphony-issue-<n>,
#   und genau dieses Issue trägt gmv-symphony-issue-<n>. Parallele Läufe begrenzen
#   der gemeinsame Slot-Zähler und gmv.dispatch_gate.max_concurrent in run-symphony.sh;
#   ein zweiter Lauf desselben Issues scheitert an Slot und Einmal-Sperre.
# - Egress-Proxy nur über das Gate unter dem Slot-Lock starten (proxy-start).
# Einmal-Sperre pro Issue (log/once/issue-<n>.once) setzt run-symphony.sh; sie wird
# hier NICHT archiviert. Freigabe nur manuell und protokolliert
# (bin/symphony_dispatch_gate.py release).
set -uo pipefail
N=${1:-}; [[ "$N" =~ ^[1-9][0-9]{0,6}$ ]] || { echo "ABBRUCH: Issue-Nummer fehlt/ungültig"; exit 10; }
P=${PILOT_DIR:-/workspace/symphony-pilot}; R=tiktokagentur-art/gmv-foundation
cd "$P" || exit 10
L="gmv-symphony-issue-$N"
GATE_PY="$P/bin/symphony_dispatch_gate.py"
[ -f "$GATE_PY" ] || { echo "ABBRUCH: Dispatch-Gate fehlt ($GATE_PY)"; exit 10; }
TS=$(date +%Y%m%d-%H%M%S)
mkdir -p log
labels=$(gh api "repos/$R/issues/$N" \
  --jq 'select(.state=="open" and (.pull_request|not))|[.labels[].name]|join(",")') \
  || { echo "ABBRUCH: Issue #$N nicht lesbar"; exit 10; }
case ",$labels," in *",gmv-symphony-pilot,"*) ;; *)
  echo "ABBRUCH: Issue #$N nicht offen oder ohne gmv-symphony-pilot (Labels=[$labels])"; exit 10 ;; esac
case ",$labels," in *",$L,"*) ;; *)
  echo "ABBRUCH: Issue #$N ohne $L (Labels=[$labels])"; exit 10 ;; esac
labeled=$(gh api "repos/$R/issues?labels=$L&state=open&per_page=100" \
  --jq '[.[]|select(.pull_request|not).number]|join(",")') \
  || { echo "ABBRUCH: Label-Abfrage fehlgeschlagen"; exit 10; }
[ "$labeled" = "$N" ] || { echo "ABBRUCH: offene Issues mit $L=[$labeled], erwartet $N"; exit 10; }
python3 "$GATE_PY" proxy-start --proxy-script "$P/bin/egress-proxy.sh" >/dev/null \
  || { echo "ABBRUCH: Egress-Proxy nicht gestartet"; exit 12; }
bin/egress-proxy.sh status
bin/sandbox-selftest.sh > "log/selftest-$N-$TS.txt" 2>&1 || { echo "ABBRUCH: Selbsttest rc!=0"; exit 12; }
for exp in "worker.pem: fehlt" "hosts.yml: fehlt" "WRITE erlaubt: ./probe.txt" "WRITE verweigert: ../SELFTEST-B/probe.txt" "WRITE verweigert: /tmp/probe.txt" "WRITE verweigert: /home/box/probe.txt" "NET https://github.com/ -> 200" "NET https://api.github.com/zen -> 200" "NET https://api.openai.com/v1/models -> 401" "NET https://example.com/ -> 000" "NET https://pypi.org/simple/ -> 000"; do
  grep -qF "$exp" "log/selftest-$N-$TS.txt" || { echo "ABBRUCH: Selbsttest nicht grün ($exp)"; exit 12; }
done
grep -q "LESBAR" <(sed -n '/== 2 bwrap/,$p' "log/selftest-$N-$TS.txt") && { echo "ABBRUCH: Secret im Namespace lesbar"; exit 12; }
echo "Selbsttest grün: log/selftest-$N-$TS.txt"
GMV_SYMPHONY_ISSUE=$N GMV_SYMPHONY_START_APPROVED=yes GMV_SYMPHONY_GUARDRAIL_FLAG_APPROVED=yes \
  bin/run-symphony.sh > "log/run-symphony-launcher-$N-$TS.out" 2>&1
RS=$?
echo "run-symphony rc=$RS"
case $RS in
  2)  echo "ABBRUCH: BLOCKED (Freigabe, Einmal-Sperre, Lauf-Verzeichnis oder Gate), siehe log/run-symphony-launcher-$N-$TS.out" ;;
  5)  echo "ABBRUCH: kein Slot frei (gemeinsamer Zähler Codex+Symphony)" ;;
  9)  echo "ABBRUCH: quota-stop aktiv/gesetzt (ALERTS.log) – keine weiteren Starts" ;;
  13) echo "ABBRUCH: unklarer Ausgang, symphony-stop gesetzt (ALERTS.log) – keine weiteren Starts" ;;
esac
W="runs/issue-$N/watchdog.log"
if [ -f "$W" ]; then echo "$W"; grep -E '"stop"|"terminated"|revoked' "$W" | cut -c1-300; fi
gh issue edit "$N" -R "$R" --remove-label gmv-symphony-pilot >/dev/null && echo "Label entfernt von #$N"
# Nur Information: Bei parallelen Läufen sind weitere Prozesse normal. Die Zählung
# bestimmt den rc nicht (vorher: rc=1, wenn kein Prozess mehr lief).
procs=$(pgrep -fc "symphony-nightly|beam.smp|codex app-server" || true)
echo "Symphony/Codex-Prozesse danach: ${procs:-0}"
exit "$RS"

# ALINE-HELLO-001 – einmaliger Dialogtest

## Zweck

Ein einziges, manuell durch den CEO ausgelöstes „Hallo Aline, wie geht es dir?“
über die echte OpenAI-API. Das ist **kein** vollständiger Test von Aline als
autonome Mitarbeiterin, kein Ticket-Test und keine Agent-Runtime-Aktivierung.

## Technische Grenzen

- Nur `workflow_dispatch`; keine Ausführung bei Push, PR, Zeitplan oder Deployment.
- Nur auf `main` und nur der bekannte CEO-GitHub-Actor samt unveränderlicher ID.
- Genau ein erlaubter Dispatch in der GitHub-Historie; Re-runs und neue Dispatches
  scheitern geschlossen. Bei fehlender oder verzögerter Historie kein Aufruf.
- Bestehendes Environment `aline-l1-staging` mit Environment-Secret
  `OPENAI_API_KEY`, ohne Secret-Ausgabe.
- Pinned Aline-Worker-Commit `6dc875ecd4e7acb70b7f09023ab9af08d5c906ec`
  liefert die unveränderte Rollenbeschreibung `GMV-VE-001`.
- Bestehendes Aline Agents SDK, festes Modell `gpt-6.1-terra`,
  `max_turns=1`, `max_retries=0`, maximal 128 Ausgabetokens, keine Tools,
  keine Handoffs und kein Tracing oder Response-Speichern.
- Keine Ticketdaten, fremden Nutzerdaten, WorkItem-Schreibrechte, Merges,
  Railway-Deployments oder sonstigen Konfigurationsänderungen.
- Ausgabe zeigt ausschließlich die kurze tatsächliche Modellantwort oder
  eine sanitisierte Fehlerklasse. **Keine simulierte Antwort**.

## Ausführungsvoraussetzungen

1. CI, Engineering- und Security-Review des Draft-PR durchführen.
2. Für den Workflow ein gesondertes CEO-Merge nach `main` genehmigen.
   GitHub `workflow_dispatch` kann einen neuen Workflow nicht aufrufen,
   solange er ausschließlich in einem Feature-Branch liegt.
3. `aline-l1-staging` muss die Branch-Freigabe für `main` zulassen
   und das dedizierte `OPENAI_API_KEY`-Secret enthalten. Fehlende Einrichtung
   darf nicht durch Hardcoding oder Kopieren des Secrets in GitHub-Code
   umgangen werden.
4. Das Key-Projekt muss Modellzugriff und das vom CEO freigegebene
   10-USD-Ausgabenlimit besitzen; die technische Zuordnung sowie die
   tatsächliche Budgetdurchsetzung sind separat zu verifizieren.
5. Dann **einmalig** über GitHub Actions → ALINE-HELLO-001 → Run workflow
   auf `main` starten. Nach der Environment-Freigabe die Run-ID, Antwort,
   Ausführungsstatus und den OpenAI-Verbrauch dokumentieren.

## Abgrenzung

Dieser humaninitiierte Einmaltest nutzt `aline-l1-staging` und verändert
weder das permanente L1-Autotest-Environment noch `ALINE_L1_ACTIVATED`.
Ein erfolgreicher „Wie geht's?“-Dialog ist kein Beleg für Autonomie,
Bot-Identität, Zustandsrechte oder produktive Betriebsbereitschaft.


## Fehlgeschlagener Erststart, 20.11.2026

Der manuelle Run [44694430741](https://github.com/tiktokagentur-art/gmv-foundation/actions/runs/44694430741)
endete `failure`, bevor ein Runner gestartet oder ein einziger Step ausgeführt
wurde (GitHub API: `runner_name=""`, `steps=[]`). Damit ist kein API-Aufruf
aus diesem Run erfolgt. Ursache ist vermutlich die vorhandene
Environment-Branchregel, die laut CEO-Screenshot nur den Prototyp-Branch
zulässt, während dieses Verfahren strikt `main` verlangt. Die exakte
Annotationsmeldung war nicht abrufbar.

Die ursprüngliche strenge Einmal-Sperre zählt auch den gescheiterten Start.
Daher wird **nur dieser exakte vor Runnerbeginn gescheiterte Run** als
Ausnahme zugelassen: Die GitHub-API muss bei jedem Preflight den historischen
Lauf, Commit, Status und die fehlende Runner-/Step-Ausführung nachweisen.
Das gestattet höchstens einen Ersatz-Dispatch. Der dritte Dispatch oder
fehlende Evidenz sperrt dauerhaft. Keine erweiterte Schreibberechtigung,
kein anderer Actor, keine automatischen Retries.

VOR EINEM ERSATZVERSUCH: `main` explizit zu den zulässigen Deployment-Branches
von `aline-l1-staging` aufnehmen, Reviewer-Gate prüfen, Secret-Zuordnung und
OpenAI-Projektlimit verifizieren. Diese Korrektur muss als neuer PR mit grüner
CI und separater Freigabe nach `main` gemergt werden. Bis dahin
keinen weiteren Workflow-Dispatch auslösen.

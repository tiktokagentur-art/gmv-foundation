# Aline – OpenAI Worker Pilot (L1)

**Status:** Implementierungsentwurf; nicht deployed, nicht live, keine attestierte technische Identität.
**Worker-Rollenkennung:** `GMV-VE-001`. Organisation: Pizza Club / GMVGANG.

## Zweck

Aline prüft als AI Chief of Staff einen **übergebenen** Ticket-Snapshot auf
P0/P1, Blocker, fehlende Nachweise und CEO-Gates. Nur Empfehlungen und
lesende Prüfaufträge; **keine** Aufgabenvergabe, Ticketänderung oder Freigabe.

## Architektur und Grenzen

- OpenAI Agents SDK / Responses API mit strukturiertem Pydantic-Output.
- Kein Tool, kein Handoff, kein Notion-/GitHub-/Railway-Schreibzugang.
- Keine autonom ausgeführten Folgeaktionen und keine periodische Ausführung.
- Snapshot-Evidenzlinks werden nicht selbst aufgerufen.
- Nachfilter weist unbekannte Ticket-IDs/Links und fingierte verified-Belege ab.
- OpenAI-Tracing aus, aber Snapshot wird an den OpenAI-API-Anbieter übermittelt.
- Für Modellaufrufe ist ausschließlich der unveränderte, gebündelte synthetische
  Testsnapshot zulässig; die Kennzeichnung synthetic=true allein reicht nicht.
- Modellfreigabe-Vorlage: gpt-6.1-terra; ein Agent-Turn, maximal 2.000
  Ausgabetokens, keine automatischen HTTP-Retries, API store=False.
- Ein administrativer Pilotbudget-Vorschlag (2 USD) ist KEINE automatische
  OpenAI-Account-Ausgabensperre; externe Kostenfreigabe bleibt notwendig.
- Noch keine ausdrückliche Datentransferfreigabe, kein API-Aufruf und kein
  unabhaengig bestaetigtes Sicherheitsreview. Keinen produktiven Deploy ausloesen.

- Nur freigegebene, minimierte Daten an ein explizit freigegebenes Modell senden.
- Assignment Authority bleibt gemäß Accepted ADR-0003 ausschließlich bei der
  Control Plane: keine Claims, Leases, Fencing oder WorkItem-Statusschreibrechte.
- Rollenkennung im Prompt ersetzt keine technische Workload-Identität.
- Keine Secrets in diesem öffentlichen Repository.

## Tests / Probelauf

```bash
python -m pip install 'pydantic>=2.9,<3'
python -m unittest discover -s prototypes/aline-openai-worker/tests -v
python prototypes/aline-openai-worker/worker.py \
  --input prototypes/aline-openai-worker/examples/synthetic.json --validate-only
python prototypes/aline-openai-worker/worker.py \
  --input prototypes/aline-openai-worker/examples/synthetic.json --offline-demo
```

## Echter LLM-Aufruf – nur nach separater API- und Datenfreigabe

```bash
python -m pip install openai-agents 'pydantic>=2.9,<3'
# OPENAI_API_KEY über Secret-Manager / geschützte Runtime injizieren
# OPENAI_MODEL explizit freigeben und als Umgebungsvariable setzen
python prototypes/aline-openai-worker/worker.py \
  --input prototypes/aline-openai-worker/examples/synthetic.json \
  --confirm-api-call --confirm-data-transfer
```

`--offline-demo` liefert einen deterministischen Prüfbericht **ohne SDK, API-Key, Netzwerkzugriff oder echte Modellantwort**. Eine echte API-Anfrage erfordert zwei getrennte Bestätigungen: `--confirm-api-call` und `--confirm-data-transfer`. Auch für synthetische Eingaben wird die Übertragung explizit freigegeben; nur die unveränderte gebündelte Testdatei ist zulässig. Nicht-synthetische Daten sind in diesem Pilot unabhängig von den Flags blockiert. Der Modellname muss explizit über `OPENAI_MODEL` gesetzt werden. API-Kosten, Modellzugriff und Datenverarbeitung sind vorab separat zu klären.

Die Beispieldaten sind synthetisch; kein echter Ticket- oder Abnahmenachweis.
Vor Staging: unabhängiges Review, CI, Modell-/Budget-/Datenschutzfreigabe,
technische Worker-Identität, read-only Adapter mit echten Quellen,
Negativtests und separate CEO-Freigabe. Keine Merges oder Deployments aus
diesem Draft ohne weitere Freigabe.

**Referenzen:** `docs/ARCHITECTURE.md`, `docs/GOVERNANCE.md`,
`docs/WORKITEM_LIFECYCLE.md`, `docs/adr/0003-single-assignment-authority.md`,
GitHub #29 / Draft PR #30. ADR-0008 ist auf `main` Proposed; PR #22 ist separat.

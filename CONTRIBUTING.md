# Mitwirken

Regeln für Änderungen an diesem Repository. Was GitHub technisch durchsetzt,
dokumentiert [ADR-0004](docs/adr/0004-branch-protection-codeowners.md).

## Sprache

Dokumentation ist Deutsch. Dateinamen, Workflow-Namen und Bezeichner im Code sind
Englisch. Architekturbegriffe bleiben in der englischen Form, wenn sie ein
Bezeichner sind: `WorkItem`, `Assignment Authority`, `Claim`, `Lease`, `Fencing`.

## Kein direkter Push auf main

`main` nimmt keine direkten Pushes an, auch keine Force-Pushes.

Jede Änderung ist ein Pull Request gegen `main`. Das gilt für Dokumentation,
ADRs, CI und später für Anwendungscode. Es gibt keine Ausnahme für Administratoren.

## Pull Request und Merge-Voraussetzungen

Ein Pull Request gegen `main` braucht keine Approval-Zahl größer 0.
Merge-Voraussetzung sind die drei erforderlichen, aktuellen Checks
(`Lint and structure`, `Backend`, `Image`), jeweils grün gegen den
aktuellen Head ([ADR-0004](docs/adr/0004-branch-protection-codeowners.md)).

Quelle: CEO-Auswahl im Chat des Head of Engineering, 10.11.2026 05:49 MEZ.

Eine inhaltliche Review bleibt möglich und prüft:

- Passt die Änderung zur Architektur und zu ADRs mit Status `Accepted`?
- Wird ein Vorschlag (`Proposed`) behandelt, als wäre er beschlossen?
- Enthält der Diff Secrets, Verbindungsdaten oder Betriebsdetails?
- Braucht die Änderung ein neues ADR oder eine Statusänderung?

Kleine, abgegrenzte Pull Requests. Eine Entscheidung pro ADR-Änderung.

## Architekturentscheidungen

Eine Entscheidung, die Architektur, Sicherheit, Daten, Identität oder Betrieb
festlegt, ist ein ADR unter `docs/adr/`. Vorlage: [docs/adr/template.md](docs/adr/template.md).
Ablauf: [docs/GOVERNANCE.md](docs/GOVERNANCE.md).

Python / FastAPI ist entschieden
([ADR-0002](docs/adr/0002-python-fastapi.md)), CEO-Entscheidung vom 09.11.2026.
Domänenmodelle folgen aus diesem ADR nicht.

## Sicherheit im Diff

Das Repository ist öffentlich (CEO-Entscheidung vom 10.11.2026,
[ADR-0013](docs/adr/0013-repository-visibility-public.md)). Der Diff darf keine
Secrets, Schlüssel, Verbindungszeichenfolgen, Tokens oder internen
Betriebsdetails enthalten. Beispiele und Fixtures ebenso wenig.
Details: [SECURITY.md](SECURITY.md).

## Prüfung vor dem Pull Request

Lokal, im Repository-Root:

```bash
npx --yes markdownlint-cli2@0.24.0
python3 scripts/validate_structure.py
python3 scripts/gitleaks_scan.py
python -m pip install -e ".[dev]"
ruff check app tests migrations scripts
pytest
```

Dieselbe Prüfung läuft in [`.github/workflows/ci.yml`](.github/workflows/ci.yml).
`markdownlint-cli2` ist auf `0.24.0` festgelegt. Die Konfiguration liegt in
[`.markdownlint-cli2.jsonc`](.markdownlint-cli2.jsonc).

`scripts/gitleaks_scan.py` lädt gitleaks `8.30.1` für Linux x86_64 und prüft die
gepinnte SHA-256-Summe. `gitleaks git --log-opts=--all` liest die vorhandene
Git-Historie; ein shallow Clone endet mit einem Fehler. Anschließend legt das
Skript ein temporäres Repository außerhalb dieses Baums an und erwartet, dass
gitleaks dort ein synthetisches Secret meldet. Der Wert wird erst zur Laufzeit
zusammengesetzt. Der Job `Lint and structure` startet dieses Skript. Die
gehostete Action bleibt ungenutzt, weil sie für Repositories einer Organisation
einen Lizenzschlüssel verlangt.

`pytest` ohne `DATABASE_URL` überspringt die Tests, die PostgreSQL brauchen.
In CI ist die Variable gesetzt und zeigt auf den Dienst-Container PostgreSQL 18.
Ein übersprungener Datenbanktest in CI ist ein Fehler.

## Durchsetzung in GitHub

Die Regeln oben gelten als Arbeitsregel. Was GitHub technisch durchsetzt,
dokumentiert [ADR-0004](docs/adr/0004-branch-protection-codeowners.md):
Schutz von `main` durch das aktive Ruleset, erforderliche Checks, 0 Approvals,
kein direkter Push und kein Force-Push. CODEOWNERS hat keine aktiven Owner.

Diese Datei ändert keine Repository-Einstellungen.

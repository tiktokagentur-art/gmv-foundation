# Mitwirken

Regeln für Änderungen an diesem Repository. Was davon in GitHub-Einstellungen
technisch durchgesetzt wird, ist offen und am Ende benannt.

## Sprache

Dokumentation ist Deutsch. Dateinamen, Workflow-Namen und Bezeichner im Code sind
Englisch. Architekturbegriffe bleiben in der englischen Form, wenn sie ein
Bezeichner sind: `WorkItem`, `Assignment Authority`, `Claim`, `Lease`, `Fencing`.

## Kein direkter Push auf main

`main` nimmt keine direkten Pushes an, auch keine Force-Pushes.

Jede Änderung ist ein Pull Request gegen `main`. Das gilt für Dokumentation,
ADRs, CI und später für Anwendungscode. Es gibt keine Ausnahme für Administratoren.

## Pull Request und unabhängige Review

Ein Pull Request braucht mindestens eine Freigabe.

Unabhängig heißt: die freigebende Person hat keinen Commit zu dieser Änderung
beigetragen. Wer den Pull Request geschrieben hat, gibt ihn nicht frei. Das gilt
auch für Personen, die nur einen Teil der Commits beigetragen haben.

Die Review prüft den Inhalt, nicht nur die Form:

- Passt die Änderung zur Architektur und zu ADRs mit Status `Accepted`?
- Wird ein Vorschlag (`Proposed`) behandelt, als wäre er beschlossen?
- Enthält der Diff Secrets, Verbindungsdaten oder Betriebsdetails?
- Braucht die Änderung ein neues ADR oder eine Statusänderung?

Kleine, abgegrenzte Pull Requests. Eine Entscheidung pro ADR-Änderung.

## Architekturentscheidungen

Eine Entscheidung, die Architektur, Sicherheit, Daten, Identität oder Betrieb
festlegt, ist ein ADR unter `docs/adr/`. Vorlage: [docs/adr/template.md](docs/adr/template.md).
Ablauf: [docs/GOVERNANCE.md](docs/GOVERNANCE.md).

Python / FastAPI ist ein Vorschlag
([ADR-0002](docs/adr/0002-python-fastapi.md)). Das Skelett in `app/` prüft ihn
und nimmt ihn nicht an. Domänenmodelle bleiben draußen, solange der Status
`Proposed` ist.

## Sicherheit im Diff

Das Repository ist öffentlich. Der Diff darf keine Secrets, Schlüssel,
Verbindungszeichenfolgen, Tokens oder internen Betriebsdetails enthalten.
Beispiele und Fixtures ebenso wenig. Details: [SECURITY.md](SECURITY.md).

## Prüfung vor dem Pull Request

Lokal, im Repository-Root:

```bash
npx --yes markdownlint-cli2@0.24.0
python3 scripts/validate_structure.py
python -m pip install -e ".[dev]"
ruff check app tests migrations scripts
pytest
```

Dieselbe Prüfung läuft in [`.github/workflows/ci.yml`](.github/workflows/ci.yml).
`markdownlint-cli2` ist auf `0.24.0` festgelegt. Die Konfiguration liegt in
[`.markdownlint-cli2.jsonc`](.markdownlint-cli2.jsonc).

`pytest` ohne `DATABASE_URL` überspringt die Tests, die PostgreSQL brauchen.
In CI ist die Variable gesetzt und zeigt auf den Dienst-Container PostgreSQL 18.
Ein übersprungener Datenbanktest in CI ist ein Fehler.

## Durchsetzung in GitHub

Die Regeln oben gelten als Arbeitsregel. In diesem Stand ist nur belegt, was im
Repository steht: CODEOWNERS hat keine aktiven Owner, und die CI-Prüfung liegt
als Workflow vor. Ob GitHub direkte Pushes auf `main` bereits blockiert, ist
von dieser Änderung aus nicht festgestellt.

Das ist absichtlich offen und in [ADR-0004](docs/adr/0004-branch-protection-codeowners.md)
festgehalten. Diese Baseline ändert keine Repository-Einstellungen.

# Software Factory

- Status: `implemented` für vorhandene CI; autonome Orchestrierung offen.
- Quellen: [CI](../../../.github/workflows/ci.yml),
  [Contributing](../../../CONTRIBUTING.md),
  [Tests](../../../tests/README.md),
  [Branch-Protection-ADR](../../adr/0004-branch-protection-codeowners.md).

Vorhanden sind Markdownlint, Struktur- und Secret-Checks, Ruff,
Pytest, OpenAPI-Validierung und Image-Tests. Ein grüner Check
ist kein Nachweis für Produktionsbetrieb oder autonomes Release.

Codex Code Review ist ergänzend; die formale Merge-Autorität
bleibt bei den GitHub-Regeln. Siehe
[Dokumentationsprüfung](../automation.md).

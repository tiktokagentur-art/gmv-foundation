# GMVGANG Developer Handbook

Der zentrale technische Einstieg für Menschen und KI-Entwickler. Dokumentation
liegt als Markdown im Code-Repository, wird mit Pull Requests geprüft und
benötigt keinen zusätzlichen Dokumentationsgenerator oder Hostingdienst.

## Navigation

- [Entwicklung und Tests](onboarding.md)
- [Systemlandkarte](systems.md)
- [Factory-Katalog](factories/README.md)
- [Factory-, API- und Agenten-Vorlagen](templates/README.md)
- [Automatische Dokumentationsprüfungen](automation.md)

## Verbindliche Quellen

- [Architektur](../ARCHITECTURE.md)
- [Datenmodell](../DATA_MODEL.md)
- [WorkItem-Lebenszyklus](../WORKITEM_LIFECYCLE.md)
- [Identitätsmodell](../IDENTITY_MODEL.md)
- [API-Vertrag](../API_SPECIFICATION.md) und [OpenAPI](../../api/openapi.yaml)
- [Governance](../GOVERNANCE.md) und [ADR-Index](../adr/README.md)
- [Security](../../SECURITY.md) und [Entwicklungsregeln](../../CONTRIBUTING.md)

## Quellen- und Statusdisziplin

`main` belegt nur gemergten Code; offene PRs sind keine vorhandene
Implementierung. `Accepted`-ADRs gelten, `Proposed`-ADRs sind offen.
Jede Factory unterscheidet `implemented`, `contract-only`, `planned`
und `unverified`. Notion-Planung ist keine technische Laufzeit-Evidenz.

Da das Repository öffentlich ist, gehören keine Secrets, internen
Betriebsdaten oder personenbezogenen Mitarbeiterangaben in diese Seiten.
Dokumentation begründet weder neue Agentenrechte noch Deployment-Autorität.

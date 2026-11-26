# Dokumentation

Einstieg in die Foundation. Die Dokumente beschreiben den Soll-Zustand der Regeln.
Sie legen keine Infrastruktur an und enthalten keinen Anwendungscode.

| Dokument | Inhalt |
| --- | --- |
| [developer/README.md](developer/README.md) | Developer Handbook: Einstieg, Factories, Vorlagen und Checks |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Schichten, Zustandsregel, Begriffe |
| [DATA_MODEL.md](DATA_MODEL.md) | Kernentitäten der V1 |
| [WORKITEM_LIFECYCLE.md](WORKITEM_LIFECYCLE.md) | Zustände, Übergänge, Lease, Fencing |
| [PROJECT_TICKET_STANDARD.md](PROJECT_TICKET_STANDARD.md) | GMVGANG-Standard für Ticketqualität, Priorisierung, DoR/DoD und Projektsteuerung |
| [IDENTITY_MODEL.md](IDENTITY_MODEL.md) | Identitäten, Rollen, Autorisierung |
| [API_SPECIFICATION.md](API_SPECIFICATION.md) | HTTP-Vertrag, Verweis auf OpenAPI |
| [GOVERNANCE.md](GOVERNANCE.md) | Entscheidungen, Review, Änderung |
| [github-moderator.md](github-moderator.md) | GitHub Moderator V1: Architektur, Modi, Berechtigungen |
| [github-moderator-security-review.md](github-moderator-security-review.md) | Sicherheits- und Testnachweis für den Moderator |
| [SYMPHONY-GITHUB-V1.md](SYMPHONY-GITHUB-V1.md) | Symphony auf GitHub Issues: Entwurf, Grenzen, Phasen |
| [symphony/github-app-spec.md](symphony/github-app-spec.md) | Symphony GitHub App: Rechteliste, nicht angelegt |
| [symphony/dispatch-gate.md](symphony/dispatch-gate.md) | Symphony Dispatch-Gate: Entwurf, standardmäßig aus |
| [symphony/sandbox.md](symphony/sandbox.md) | Symphony/Codex-Sandbox: was erzwungen ist, was nicht |
| [symphony/quota-refresh.md](symphony/quota-refresh.md) | Symphony und Codex: Quota-, Rate-Limit- und Login-Regel (fail-closed) |
| [symphony/parallel-isolation.md](symphony/parallel-isolation.md) | Symphony parallel: Zustand je Issue, Schreibpfade, Proxy-Regel in run-wave.sh |
| [adr/README.md](adr/README.md) | Index der ADRs, einschließlich offener Punkte |
| [../SECURITY.md](../SECURITY.md) | Secrets, Rechte, Identität, Autorisierung, Audit |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Branch, Pull Request, unabhängige Review |

Gültig ist eine Architekturaussage, wenn sie hier steht und ein ADR mit Status
`Accepted` sie trägt oder sie ausdrücklich als Regel dieser Baseline formuliert ist.
Vorschläge (`Proposed`) sind keine Bauvorlage.

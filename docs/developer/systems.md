# Systemlandkarte

Diese Seite ist ein Wegweiser; die [Architektur](../ARCHITECTURE.md)
und akzeptierte ADRs bleiben die technischen Originalquellen.

| Schicht | Nachweis | Status auf main |
| --- | --- | --- |
| Foundation | [Verträge](../API_SPECIFICATION.md), [ADR-Index](../adr/README.md) | Dokumentiert |
| Control Plane | [Lifecycle](../WORKITEM_LIFECYCLE.md), [OpenAPI](../../api/openapi.yaml) | Vertragsstand; FastAPI-Skelett |
| Worker Runtime | [Architektur](../ARCHITECTURE.md) | Zielbild, Laufzeit nicht belegt |
| Software Factory | [CI](../../.github/workflows/ci.yml) | Baseline-Checks vorhanden |
| Infrastructure | [Railway-ADR](../adr/0005-railway-environments.md) | Staging beschrieben; Produktion nicht belegt |

[Factory-Katalog](factories/README.md) und
[Sicherheitsregeln](../../SECURITY.md) liefern weitere Einstiege.

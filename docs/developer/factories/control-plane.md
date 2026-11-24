# Control Plane

- Status: `contract-only` für die Domäne, FastAPI-Skelett vorhanden.
- Code: [app/](../../../app/README.md)
- Vertrag: [Lifecycle](../../WORKITEM_LIFECYCLE.md),
  [Datenmodell](../../DATA_MODEL.md), [API](../../API_SPECIFICATION.md),
  [OpenAPI](../../../api/openapi.yaml).
- Architekturgrundsatz: [ADR-0003](../../adr/0003-single-assignment-authority.md).

Die Control Plane soll WorkItems, Assignments, Claims, Leases,
Fencing und Audit besitzen. Worker beantragen Zustandsänderungen,
sind aber nicht selbst State Owner.

Die `/v1`-Endpunkte des Baseline-API-Vertrags sind auf `main`
nicht implementiert. Offene PRs sind als eigener Status zu prüfen.

# MVP-Vertrag für das Portal

Der [OpenAPI-Vertrag](../../api/openapi.yaml) beschreibt die Portal-Schnittstelle für fiktive Daten. Fachliche Grundlagen sind der [MVP-Umfang](mvp-umfang.md) und der [Datenfeldkatalog](datenfelder.md). Die Vertragsergänzung definiert die Schnittstelle für die spätere Implementierung.

## Ressourcen und Kernablauf

Alle Portal-Pfade beginnen mit `/v1/portal/`. `GET /creators`, `GET /sellers` und `GET /products` unter diesem Präfix liefern fiktive Katalogeinträge oder eine leere Liste. Produkte sind einem Händler zugeordnet.

| Schritt | Operation unter `/v1/portal` | Eingabe und Bezug |
| --- | --- | --- |
| Kampagne | `POST /campaigns` | Produkt-ID, gewünschtes Videoformat und Musterverfügbarkeit |
| Interesse | `POST /interests` | Kampagnen-ID und Creator-ID |
| Musteranfrage | `POST /sample-requests` | Interesse-ID und Musteranzahl. Kampagne und Produkt ergeben sich aus dem Interesse |
| Entscheidung | `POST /decisions` | Musteranfrage-ID, Zusage oder Absage und fiktive Begründung |
| Videolink | `POST /video-links` | ID der zustimmenden Entscheidung und Platzhalter-URL unter `https://example.invalid/` |
| Feedback | `POST /feedback-items` | Videolink-ID und fiktive Rückmeldung zum Video |

Jeder erfolgreiche Schreibschritt gibt die ID der angelegten Ressource zurück. Eine Absage beendet den Ablauf vor dem Videolink.

## Workload-Zugriff und Fehler

Der Vertrag verwendet das bestehende Workload-Bearer-Schema `callerCredential`. Jede Portal-Operation dokumentiert genau einen erforderlichen Scope in `x-required-scope`. Lesende Operationen verwenden `portal.read`, schreibende Operationen `portal.write`. `portal.admin` ist für administrative Operationen vorgesehen. Der MVP-Vertrag enthält keine administrative Operation.

Fehler verwenden die bestehende Antwort `Error` mit `ErrorBody`. Ein fehlender oder ungültiger Workload-Key ergibt `401`, ein fehlender Scope `403`. Schreiboperationen dokumentieren außerdem `400` für ungültige Eingaben, `404` für unbekannte Referenzen und `409` für Zustandskonflikte, etwa einen Videolink zu einer Absage.

Die Menschenrollen `creator`, `seller` und `admin` sind fachliche Datenwerte ohne Berechtigungswirkung. Der Vertrag definiert weder Login- noch IdP-Endpunkte. Freitext und Bezeichnungen bleiben fiktiv. Personen-, Kontakt- und Preisfelder sind ausgeschlossen.

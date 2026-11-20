# UI-FOUND-001 – Pizza Club Command Center (isolierter Prototyp)

Status: **Draft / Design-Demo**. Dieser Ordner enthaelt eine lokal lauffaehige,
responsive Benutzeroberflaeche fuer CEO, Aline und exemplarische
Abteilungsarbeitsraeume. Der Prototyp ist **nicht** mit OpenAI, Railway,
GitHub, Notion, der Control Plane oder einer Datenbank verbunden.

> WICHTIG: Das bestehende Repository ist oeffentlich. Keine Zugangsdaten,
> personenbezogenen Daten, vertraulichen Auftraege oder echten
> Unternehmensdaten in diesen Prototyp eingeben.

## Start

Ohne Build-Prozess und ohne externe Pakete:

```bash
cd prototypes/pizza-club-command-center
python3 -m http.server 8080 --bind 127.0.0.1
# Im eigenen Browser: http://127.0.0.1:8080/
```

Alternativ `index.html` lokal oeffnen. Der Demo-Code laedt keine externen
Ressourcen. Bei einem spaeteren Produktaufbau kann der HTML/CSS/JS-Prototyp
in Next.js/React uebernommen werden. **Next.js ist hier absichtlich noch nicht
eingefuehrt**, da die finale Authentisierung und der API-Integrationsvertrag
noch offen sind und diese Designabnahme kein produktives Laufzeitsystem verlangt.

## Funktionen

| Bereich | Sichtbar und lokal testbar | Explizit NICHT enthalten |
| --- | --- | --- |
| CEO | Cockpit, Navigation und Beispieldaten | Live-KPIs, echte Autorisierung |
| Aline Chat | Texteingabe, Schnelleinstiege, lokale Nachrichten, Auftragsentwuerfe | LLM-Aufruf, persistenter Chat |
| Abteilungen | Chat-/Entwurfsraeume fuer Deniz, Samira, Malik, Lea | Echte KI-Leiter- oder Rollenidentitaeten |
| Auftraege | Liste, Status, Ergebnisbeispiele und Detaildialog | WorkItems, Assignment Authority, Claims |
| Freigaben | Lokaler Statuswechsel nach Browser-Bestaetigung | Backend-Freigabe, Rechteaenderung, Audit-Trail |
| Kosten | 0 EUR Demo-API-Kosten und Beispiel-Budgetprozess | Provider Usage, Rechnung, wirksames Budgetlimit |

Die Sitzung ist rein fluechtig. Beim Neuladen gehen lokale Entwuerfe und
simulierte Freigabeaenderungen verloren. Alle Eingaben werden als DOM-Text
angezeigt; es gibt keine Netzwerkaufrufe, Browser-Storage, Telemetrie,
externe Skripte oder Backend-Endpunkte.

## Duplikat- und Bestandspruefung (20.11.2026)

- `main`: FastAPI, docs, OpenAPI-Vertrag und Python-Tests. Kein bestehender
  Web-Client bzw. Command-Center-Frontend im vollstaendig gelesenen Git-Tree.
- Offene PRs vor diesem Auftrag: #31 (Aline Worker), #32 (L1 API-Gate),
  #33 (Notion Read-only Adapter), #36 (PR-Triage) und andere. Keiner war ein
  UI-FOUND-001- oder vergleichbarer Frontend-PR.
- Kein Legacy-Portal-Code importiert; keine bestehenden Dateien unter
  `app/`, `api/`, `docs/adr/` oder `.github/` geaendert.
- Das Repo hat den Python/FastAPI-Stack bereits als Backend-Baseline.
  Die spaetere UI darf die fachliche Zustandsfuehrung NICHT duplizieren.

## Vorgeschlagene Produktarchitektur (nicht umgesetzt)

```text
Human Operator (CEO, berechtigte Mitarbeitende)
  -> Web-UI (spaeter Next.js/React; OIDC + MFA nach ADR-0008)
  -> Authentifizierte FastAPI / Control Plane
     -> WorkItem-Status und Ergebnisnachweise (einzige State Authority)
     -> CEO-Freigaben, Budget-Gates und revisionsfester Audit-Trail
     -> Assignment Authority (einziger Zuordner, Leases/Fencing)
        -> Worker Runtime Aline und Abteilungs-Worker
     -> Metrik-/Usage-Aggregation (Kosten nach Provider-Nachweis)
```

### API-Zuordnung und zusaetzliche Endpunkte

Der vorhandene Vertrag unter `api/openapi.yaml` sieht bereits
`/v1/work-items`, Worker- und Assignment-Ressourcen vor.
Die UI wird spaeter ausschliesslich berechtigte, serverseitig autorisierte
Schnittstellen konsumieren; sie schreibt nie direkt in PostgreSQL.

Vor einem produktiven Chat benoetigt es zusaetzlich designte Ressourcen:

- `POST /v1/command-drafts`: Auftrag als nicht ausfuehrbarer Entwurf,
  inkl. Ziel, Zweck, Risiko, Kostenbudget und eindeutiger Auftraggeber-Identitaet
- `GET /v1/command-drafts/{id}`: Entwurf und Review-Nachweis
- `POST /v1/approvals/{id}/decisions`: idempotent, autorisiert,
  actor-gebunden, auditierbar, mit Ablauf und Versionspruefung
- `GET /v1/execution-results`: referenzierte Ergebnisse und Artefakt-IDs
- `GET /v1/usage-summary`: aggregierte gemessene Nutzung je Provider/
  Modell/Worker/Budget; geschaetzte und abgerechnete Kosten getrennt

Diese Pfade sind **Vorschlaege**, keine existierenden API-Endpunkte. Ihre
Zustandsgrenzen, Schemas, Zugriffsregeln und Statusuebergaenge sind mit
`docs/DATA_MODEL.md`, `docs/WORKITEM_LIFECYCLE.md`,
`docs/API_SPECIFICATION.md` und ADR-0003 abzugleichen, bevor Code entsteht.

### Sicherheit / Governance

- ADR-0008 (Identitaet) steht auf `Proposed`. Der Prototyp faellt keine
  implizite Entscheidung ueber IdP, Tokenformat oder Auth-Library.
- Menschliche Sessions und Workload-Identitaeten muessen getrennt bleiben.
  Die Anzeige einer Abteilungsrolle verleiht keine Rechte.
- Freigaben duerfen NIEMALS durch die alleinige UI-Aktion als tatsaechliche
  Genehmigung gelten. Backend-RBAC/ABAC, Identitaet, Revision,
  Idempotenzschluessel, Audit, Kostenlimit und zweite Schutzstufe bei
  Hochrisiko-Aktionen sind vor Live-Schaltung zu spezifizieren.
- Freigabe und Ausfuehrung sind eigene Schritte. Kein stiller Worker-Start.
- Backend-seitige Datenminimierung und Geheimnisschutz fuer Chats/
  Artefakte, ggf. EU-/USA-Datenverarbeitung, Retention und Loeschkonzept.
- Vor der Anbindung: Content Security Policy, CSRF-Abwehr (falls Cookies),
  Eingabevalidierung, Rate-Limits, Session-Revoke, XSS-Tests und
  Rollen-/Datenisolationstests.
- Kein Deployment, Merge, IAM-Write, DB-Schema, echter API-Test oder
  Aenderung an Secrets ist Teil dieses PRs.

## Definition of Done fuer den DESIGN-Prototyp

- [x] Isoliertes Verzeichnis, keine Aenderung an produktiven Dateien
- [x] Responsive Navigation fuer Desktop/Tablet/Smartphone
- [x] Chat-Eingabe erzeugt nur lokale Entwuerfe
- [x] Auftraege und Beispielergebnisse mit Detailansicht
- [x] Simulierte Freigaben mit eindeutiger Demo-Kennzeichnung
- [x] Getrennte Darstellung von nicht angefallenen Demo-Kosten
- [x] Aline-/Abteilungsansichten mit eindeutiger Nicht-Verbindung
- [ ] Browser- und Accessibility-Review durch unabhaengige Pruefer
- [ ] CI/Nachweise zu Javascript- und HTML-Validierung
- [ ] Security-Review durch Shafo, Engineering-Abnahme Deniz
- [ ] Fachliche Abnahme Aline, Entscheidung zur Auth-/Integrationsphase

## Testplan (ohne produktive Aktionen)

1. Lokal oeffnen: alle 9 Sidebar-Ansichten erreichbar.
2. Auf dem iPhone-Simulator und bei 320, 390, 768 und 1440 px pruefen.
3. Einen Beispieltext in Aline Chat absenden: lokaler Entwurf erscheint;
   kein Network-Request.
4. Auftragsdetail oeffnen: Status und Ergebnis nur Demo.
5. Demo-Freigabe aendern, Seite neu laden: Ursprungszustand wiederhergestellt.
6. Entwicklerwerkzeuge: Network ohne XHR/fetch/WebSocket,
   Storage ohne Eintraege, keine entfernten Skripte.
7. Tastatur: Fokus, Navigation, Dialog, Escape und mobile Menues testen.
8. Kein OAuth, LLM/Worker-Call, externer Link, GitHub Write oder Deploy.

## Ownership und Pruefgates

- **Engineering Owner**: Deniz (Design- und Code-Abnahme)
- **Koordination**: Aline (fachliche Anforderungen und offene Gates)
- **Security Review**: Shafo (unabhaengig; vor Merge)
- **CEO**: Freigabe jeglicher produktiver Integrations-, Kosten- und
  Berechtigungsentscheidung

Die Namen beschreiben die vorgesehenen Verantwortlichkeiten. Diese Datei
nimmt keine Mitarbeiterregistrierung oder tatsaechliche Aufgabenuebergabe vor.

# UI-FOUND-001 — Konzept fuer persoenliche Mitarbeiterzugaenge

Status: **Entwurf, noch keine Authentisierung implementiert**.
Datum: 20.11.2026. Zugehoerig zu Draft-PR #37.

## Ziel

Das Pizza Club Command Center muss spaeter fuer mehrere reale,
individuell authentifizierte Menschen nutzbar sein. Nicht jeder Benutzer
bekommt die CEO-Ansicht. Eine Person kann Mitglied einer oder mehrerer
Abteilungen sein; ihr Zugang und ihre Rechte bleiben der Person
eindeutig zugeordnet. KI-Worker wie Aline und technische Dienste sind
**keine** Menschenkonten.

Dieses Dokument praezisiert die UI-Anforderungen. Es aendert keine
Berechtigungen, Identitaeten, Authentisierungsentscheidungen,
GitHub-Rulesets oder produktiven Systeme.

## Architekturgrenze

```text
Browser (realer Mensch, individuelle Session)
    |
    v
OIDC-Login mit MFA (erst nach Entscheidung ADR-0008)
    |
    v
Session-/BFF-Schicht der Web-App (kein Access-Token in LocalStorage)
    |
    v
FastAPI / Control Plane
    |-- serverseitige Autorisierung (Rolle UND Ressourcenbereich)
    |-- Mitarbeiter-/Abteilungszuordnung und Audit
    |-- WorkItems / Freigaben (einzige fachliche State Authority)
    +-- Worker Runtime (separate worker/service identities)
```

Die UI blendet Menues nach Rueckgabe der effektiven Berechtigungen aus,
aber **niemals** ersetzt das die Backend-Autorisierung. Aufrufe
aus anderen Browser-Sessions, APIs oder Worker-Kontexten muessen
ebenfalls geprueft werden. Kein zweiter WorkItem-Statusspeicher.

## Login- und Einladungsablauf (Ziel)

1. Autorisierter Administrator/HR legt eine Einladung zu einer
   eindeutig bestimmten realen Person an (kein oeffentliches
   Selbstregistrierungsformular). Noch kein Account und kein
   Zugang wird durch diesen Prototyp angelegt.
2. Person akzeptiert ueber einen zeitlich befristeten, einmalig
   verwendbaren Link aus einem geeigneten Identity Provider.
3. Person meldet sich mit individueller Identitaet an. MFA ist fuer
   Mitarbeiter obligatorisch; fuer kritische Rollen phishing-resistente
   MFA vorsehen, vorbehaltlich des Auth-ADRs.
4. Serverseitige Session wird anhand des IdP-Subjects einer aktiven
   Human-Identity und ihren Mitgliedschaften zugeordnet.
5. Backend liefert die fuer die Ansicht erforderlichen Daten
   und Berechtigungen, niemals eine privilegierte Datenmenge zum
   anschliessenden Filtern nur im Browser.
6. Berechtigungsentzug, Abteilungswechsel, Sperrung und Offboarding
   muessen aktive Sessions und erteilte Zugriffe zeitnah entwerten.
7. Jede sensitive Handlung wird mit Person, Zeit,
   Berechtigungsentscheidung, Ressource und Ergebnis auditiert.
   Datenschutzgerechte Aufbewahrungs- und Loeschfristen festlegen.

### Ausdruecklich nicht bauen

- Keine eigenen Passworttabellen oder selbst entwickelten Logindialoge.
- Keine gemeinsam benutzten Mitarbeiter- oder KI-Konten.
- Keine Tokens/Passwoerter in Browser-Storage, URLs, Git oder Logs.
- Keine automatischen Einladungen, Mails, Rechtevergaben oder
  Live-Freigaben ueber den Prototyp.
- Kein Zugriff allein aufgrund ausgewaehlter UI-Rolle.

## Datenmodell-Vorschlag (nur Entwurf)

| Entitaet | Zweck | Sicherheitsrelevanz |
| --- | --- | --- |
| HumanIdentity | unveraenderliche interne ID, IdP-Aussteller + Subject, Status | `issuer, subject`-Kombination eindeutig; serverseitige Zuordnung |
| EmployeeProfile | Anzeigename, Arbeitskontext, Kontakt mit Datenschutz | Keine echten Personendaten im oeffentlichen Repo |
| Department | Abteilung und Leitungsbezug | getrennt von der IdP-Identitaet |
| DepartmentMembership | HumanIdentity, Department, Rolle, aktiv von/bis | Rollen- und Scope-Basis |
| PermissionGrant | Ressource, Aktion, Scope, genehmigender Akteur, Ablauf | Least Privilege; kein direktes UI-Schreiben |
| Invitation | signierte/gebundene Einladung, Ablauf, Einmaligkeit | nie den Token im Klartext protokollieren |
| HumanSession | Ablauf, Sperrung, MFA-Level, Session-ID | serverseitiges Revocation-Verfahren |
| AuditEvent | Akteur, Ressource, Entscheidung, Revision, Request-ID | unveraenderlicher Nachweis |

`HumanIdentity` soll an das vorhandene `docs/IDENTITY_MODEL.md` andocken
(`kind = human`). Erweiterungen muessen vor dem Coding mit
`docs/DATA_MODEL.md`, `api/openapi.yaml` und ADR-0003 konsolidiert
werden. Unternehmens-, Projekt- und Abteilungs-Scopes werden als
`organization_id`, `department_id` und `resource_id` modelliert;
damit ist eine spaetere weitere Organisation denkbar, ohne heute
Mehrmandantenbetrieb zu behaupten.

## Rollen- und Rechteentwurf (kein produktives Grant)

| Rolle | Bereich | Beispiele fuer moegliche Rechte | Nicht automatisch erlaubt |
| --- | --- | --- | --- |
| CEO | unternehmensweit | Gesamtstatus, Budgetentscheidungen, delegierte Freigaben | Secrets lesen, Auth-Bypass |
| Administrator (Human) | Access Administration | User-Lifecycle, Einladungen, Rollen beantragen und nach Gate vergeben | Eigene Privilegien erhoehen, WorkItems ohne Scope manipulieren |
| Abteilungsleitung | eigene Abteilung | Teamauftraege lesen/entwerfen, Ergebnisse bewerten | Andere Abteilungen, CEO-Budgets |
| Mitarbeiter | eigene zugewiesene Ressourcen | Aline/Teamchat, eigene Auftraege und Ergebnisse | Mitarbeiterverwaltung, sensible Finanzdaten |
| Finance | zugewiesene Budgetbereiche | Kostenberichte, Budgetvorschlaege | CEO-Kostenfreigaben ohne Delegation |
| Auditor | definierter Audit-Scope | Audit und Freigabehistorie lesen | Aendern, loeschen, ausfuehren |
| Worker/Service | kein menschlicher Login | nur explizit erlaubte Machine-API-Funktionen | Browser-Session, Freigabe per UI |

Eine Rolle allein ist nicht ausreichend: Backend prueft zudem
Scope, Ressourcenbesitz, Status, Vertrauens-/MFA-Level
und moegliche Trennung von Auftraggeber, Ausfuehrer und Abnehmer.
Ressourcen duerfen nicht zwischen Abteilungen auslaufen.
Voraussetzungen fuer delegated approvals muessen separat entschieden werden.

## UI-Informationsarchitektur

- Nicht angemeldet: neutraler Login-Einstieg ueber externen IdP
  (noch nicht im Prototyp).
- Angemeldet: eigenes Profil, eigene Abteilung, eigener Arbeitsbereich,
  individuelle Berechtigungen.
- Abteilungsleiter: Abteilungs-Dashboard + eigener Chat mit Aline,
  abteilungsspezifische Auftragsliste.
- CEO: alle berechtigten Abteilungen, eskalierte Aufgaben,
  Finanzuebersicht und Freigabepostfach.
- Access Administration (nur Berechtigte): Mitarbeiterliste,
  Einladung, Rollen-/Abteilungswechsel, Sperrung, Session-Widerruf
  mit getrennten Bestätigungsschritten.
- Jeder Benutzer sieht, in welchem Teamkontext er handelt;
  Kontextwechsel veraendert die zulässigen Daten nicht ohne
  erneute serverseitige Pruefung.
- KI-Agenten bleiben im Worker-Register, nicht im Mitarbeiter-Login.

## Backend-Schnittstellen (Vorschlaege, nicht implementiert)

```text
GET  /v1/me                       Profile, aktive Scopes, erlaubte Aktionen
GET  /v1/my-departments           sichtbare Abteilungszugehoerigkeiten
GET  /v1/my-work-items            serverseitig gefilterte Auftraege
GET  /v1/admin/humans             nur fuer autorisierte Access Admins
POST /v1/admin/invitations        Berechtigung + idempotenter Audit
POST /v1/admin/role-requests      getrennte Pruefung vor Grant
POST /v1/admin/sessions/revoke    entzieht aktive Sessions
```

Fachliche WorkItems und Freigaben bleiben in den bestehenden bzw.
noch zu definierenden Authority-APIs. Endpunktnamen sind Vorschlaege
und noch keine Endpunktvertraege.

## Vor produktivem Login zu entscheiden

1. ADR-0008: OIDC-Provider, MFA-Niveau, Sitzungsarchitektur,
   Datenregion/DSGVO und Wiederherstellungsverfahren.
2. Zulassungs- und Einladungsberechtigte; HR und Admin nicht stillschweigend
   als bestehende technische Rollen behandeln.
3. Rechte-Matrix mit Scope und Hochrisiko-Freigabeprozess; Separation of Duties.
4. Modell fuer Austritt, Entzug, Passwort-/MFA-Reset, Admin-Notfallzugang.
5. Protokollierung/Retention von Benutzerstammdaten und Chat-Inhalten.

## Akzeptanztests fuer die kuenftige reale Implementierung

- Mitarbeiter A aus Abteilung X darf WorkItems aus Y nicht lesen,
  auch nicht ueber manipulierte API-URLs oder IDs (403/404 je Policy).
- Ein eingeladener, nicht aktivierter Benutzer kann sich nicht einloggen.
- Deaktivierung/Offboarding invalidiert laufende Sessions und
  verhindert neue Authentisierung.
- Abteilungsleiter kann keine CEO-Freigabe ausloesen.
- CEO und Mitarbeiter duerfen ihre Identitaeten nicht durch
  einen Client-Parameter austauschen.
- Human kann keinen `worker`-Token generieren und umgekehrt.
- Bei gleichzeitigen Rollen wird die Berechtigung explizit
  anhand der aktiven Abteilung/Ressource entschieden.
- Fehlender/abgelaufener CSRF-Nachweis wird abgelehnt
  (wenn Cookie-basierte Sessions gewaehlt werden).
- Sensitive Aktionen erfordern aktuellen MFA-/Reauth-Nachweis,
  nicht nur einen offenen Browser-Tab.
- Jeder akzeptierte Rollenwechsel und jede Freigabe erzeugt ein AuditEvent.

## Prototyp-Status

Die neue Ansicht **Mitarbeiterzugang** im Draft-PR zeigt nur
Login- und Rollen-Konzept mit synthetischen Beispielen. Es gibt
keine echten Mitarbeiterlisten, Einladungen, Rollen- oder IAM-Writes.

Deniz: technische Ausarbeitung/Abnahme.
Aline: fachliche Rollen- und Abteilungsvorgaenge.
Shafo: Security-/Datenschutz-Review.
CEO: Entscheidung fuer die produktive Auth- und Access-Einfuehrung.

# ADR-0008: Authentisierungsstandard

- Status: Proposed
- Datum: 2026-11-09
- Überarbeitet: 2026-11-10 (Vorschlag ergänzt, nicht entschieden)
- Entscheider: offen

## Kontext

[../../SECURITY.md](../../SECURITY.md) und [ADR-0003](0003-single-assignment-authority.md)
legen fest, was von einem Standard unabhängig schon gilt:

- eigene Identität je Dienst und je Worker
- Menschen und Workloads sind verschiedene Subjekte
- jede Zustandsänderung wird von der besitzenden Instanz autorisiert
- Anträge ohne passende Identität ändern nichts

Offen ist der Standard, mit dem eine Identität nachgewiesen wird. Ein Standard
wird nicht gewählt, indem ein Protokoll im ersten Dienst hart codiert wird.
[ADR-0002](0002-python-fastapi.md) ist der beschlossene Stack und liefert keine
Authentisierung mit.

### Ist-Stand im Repository

- [../IDENTITY_MODEL.md](../IDENTITY_MODEL.md) kennt die Identitätsarten human,
  service und worker. Das Feld `subject` wird externer Bezug, sobald dieses ADR
  einen Aussteller benennt.
- [../../api/openapi.yaml](../../api/openapi.yaml) beschreibt `callerCredential`
  als `type: http, scheme: bearer` mit dem Vermerk „Platzhalter, kein gewählter
  Standard“. Das legt faktisch schon ein Übertragungsformat nahe und steht in
  Spannung zur Konsequenz unten („kein Token-Format als Default“).
- Die Anwendung hat heute keine Authentisierung. `pyproject.toml` enthält keine
  Auth-Bibliothek.

### Fakten aus Primärquellen

- NIST SP 800-63B-4 definiert AAL1 bis AAL3. Ab AAL2 muss eine
  phishing-resistente Option angeboten werden. E-Mail ist kein zulässiger
  Out-of-Band-Authenticator.
  ([NIST SP 800-63B-4](https://pages.nist.gov/800-63-4/sp800-63b.html))
- OWASP ASVS 5.0 verlangt ab Level 2 MFA (V6.3) und für Self-contained Tokens
  die Prüfung von Signatur, Algorithmus-Allowlist, `exp`, Tokentyp und `aud` (V9).
  ([OWASP ASVS](https://asvs.owasp.org/))
- RFC 9700 (OAuth 2.0 Security BCP): Der Resource Owner Password Credentials
  Grant darf nicht verwendet werden (§2.4). Für Client-Authentisierung wird
  asymmetrische Kryptografie empfohlen, z. B. `private_key_jwt` (§2.5).
  ([RFC 9700](https://www.rfc-editor.org/rfc/rfc9700.html))
- OWASP REST Security Cheat Sheet: Authentisierung zentral, Zugriffsentscheidung
  lokal. API-Keys nicht als einzigen Schutz sensibler Ressourcen.
  ([OWASP REST Security](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html))
- OWASP Password Storage: Argon2id mit mindestens m=19 MiB, t=2, p=1.
  ([OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html))
- Datenregionen gehosteter IdPs laut Anbieter: Auth0 mit wählbarer Region
  einschließlich US und EU
  ([Auth0](https://auth0.com/docs/get-started/auth0-overview/create-tenants)),
  Clerk ohne regionale Datenhaltung ([Clerk](https://clerk.com/security)),
  Supabase mit wählbarer Primärregion
  ([Supabase](https://supabase.com/docs/guides/platform/regions)).
- Keycloak ist Open Source (Apache 2.0) und ein CNCF-Projekt.
  ([CNCF Keycloak](https://www.cncf.io/projects/keycloak/))

### Annahmen (getrennt von den Fakten)

- A1: [ADR-0012](0012-hosting-region-usa.md) gilt nur für Railway-Dienste. Ein
  gehosteter IdP ist frei wählbar. Übermittelt vom Head of Engineering, vom CEO
  nicht bestätigt. NICHT VERIFIZIERT.
- A2: Der Hauptverkehr ist Maschine-zu-Maschine. Menschliche Nutzer gibt es
  anfangs wenige, keine Endkunden-Logins. NICHT VERIFIZIERT.
- A3: Ziel ist ASVS Level 2, also MFA für Menschen. NICHT VERIFIZIERT.
- A4: Worker laufen in kontrollierter Umgebung. Externe Fremd-Worker gibt es
  vorerst nicht. NICHT VERIFIZIERT.

## Entscheidung

Nicht entschieden. Der Authentisierungsstandard für Menschen und für Workloads ist offen.

### Vorschlag zur Prüfung (keine Entscheidung)

1. Workloads: pro Identität ausgestellte, gehasht gespeicherte und einzeln
   widerrufbare API-Keys, von der Control Plane geprüft. Später OAuth 2.0
   Client Credentials mit `private_key_jwt`, sobald externe Worker hinzukommen.
2. Menschen: ein Standard-OIDC-IdP mit MFA statt Eigenbau. Bei A1 ist ein
   gehosteter IdP zulässig. Gilt A1 nicht, bleibt Keycloak in Railway `sfo`.
   Kein Password Grant.
3. Tokens von Menschen und von Workloads sind am Server unterscheidbar
   (RFC 9700 §4.15). Die Autorisierung bleibt in der besitzenden Instanz.
4. Der Platzhalter in `openapi.yaml` wird mit dem Entscheid angepasst.

### Zu klären

- ob A1 gilt (CEO-Bestätigung) und welcher IdP, mit welchem Budget
- welche Menschen sich anmelden, wie viele, und ob SAML nötig ist
- Zielniveau (ASVS L2 bzw. AAL2 oder höher für bestimmte Rollen)
- höchste Lebensdauer eines Maschinen-Credentials und wie schnell ein Widerruf wirken muss
- was ein Worker vor der ersten Zuweisung vorzeigen muss

## Konsequenzen

- Es wird kein Token-Format, kein Aussteller und keine Bibliothek als Default eingeführt.
- Autorisierung bleibt serverseitig, auch nachdem ein Standard gewählt ist. Der Standard ersetzt die Assignment Authority nicht.
- Worker teilen sich keinen Nachweis.
- Wird der Vorschlag angenommen: Schlüssel und Client-Secrets folgen
  [ADR-0007](0007-secret-management.md). Ein selbst betriebener IdP braucht
  Backup ([ADR-0006](0006-backup-retention-rpo-rto.md)) und Überwachung
  ([ADR-0010](0010-slo-alerting-incident.md)).

## Alternativen

| Option | Vorteil | Nachteil |
| --- | --- | --- |
| Eigene Auth in FastAPI (Passwörter, JWT) | keine Abhängigkeit | volle Verantwortung für MFA, Passwortspeicher und Sitzungen; Tutorial-Muster nutzt den Password-Flow (RFC 9700 §2.4) |
| Gehosteter IdP (Auth0, Clerk, Supabase Auth, WorkOS) | MFA und OIDC fertig, wenig Betrieb | Lock-in, Kosten (NICHT VERIFIZIERT), Region abhängig von A1 |
| Keycloak selbst betrieben auf Railway | Standard-OIDC, in `sfo` betreibbar | zweiter sicherheitskritischer Dienst mit eigener Datenbank |
| API-Keys für Workloads | einfach, je Identität widerrufbar | kein Standardprotokoll; nicht allein für sensible Ressourcen |

## Bezug

- [ADR-0002](0002-python-fastapi.md)
- [ADR-0003](0003-single-assignment-authority.md)
- [ADR-0006](0006-backup-retention-rpo-rto.md)
- [ADR-0007](0007-secret-management.md)
- [ADR-0010](0010-slo-alerting-incident.md)
- [ADR-0012](0012-hosting-region-usa.md)
- [../IDENTITY_MODEL.md](../IDENTITY_MODEL.md)
- [../../SECURITY.md](../../SECURITY.md)

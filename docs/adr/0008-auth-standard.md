# ADR-0008: Authentisierungsstandard

- Status: Accepted
- Datum: 2026-11-10
- Entscheider: Head of Engineering (delegiert vom CEO, 10.11.2026)

## Kontext

[../../SECURITY.md](../../SECURITY.md) und [ADR-0003](0003-single-assignment-authority.md)
legen fest, was von einem Standard unabhängig schon gilt:

- eigene Identität je Dienst und je Worker
- Menschen und Workloads sind verschiedene Subjekte
- jede Zustandsänderung wird von der besitzenden Instanz autorisiert
- Anträge ohne passende Identität ändern nichts

Offen war der Standard, mit dem eine Identität nachgewiesen wird.
[ADR-0002](0002-python-fastapi.md) ist der beschlossene Stack und liefert keine
Authentisierung mit. Der Vorschlag vom 09.11.2026 ist am 10.11.2026 für
Workloads entschieden worden. Die CEO hat technische Entscheidungen an den
Head of Engineering delegiert.

### Fakten aus Primärquellen

- NIST SP 800-63B-4 definiert AAL1 bis AAL3. Ab AAL2 muss eine
  phishing-resistente Option angeboten werden.
  ([NIST SP 800-63B-4](https://pages.nist.gov/800-63-4/sp800-63b.html))
- OWASP ASVS 5.0 verlangt ab Level 2 MFA für Menschen.
  ([OWASP ASVS](https://asvs.owasp.org/))
- RFC 9700 (OAuth 2.0 Security BCP): Der Resource Owner Password Credentials
  Grant darf nicht verwendet werden (§2.4). Für Client-Authentisierung wird
  asymmetrische Kryptografie empfohlen, z. B. `private_key_jwt` (§2.5).
  Tokens von Menschen und von Maschinen müssen am Server unterscheidbar sein
  (§4.15).
  ([RFC 9700](https://www.rfc-editor.org/rfc/rfc9700.html))
- OWASP REST Security Cheat Sheet: Authentisierung zentral, Zugriffsentscheidung
  lokal.
  ([OWASP REST Security](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html))
- OWASP Password Storage: Argon2id ist der Speicher für Passwörter. Ein
  API-Key mit hoher Entropie ist kein Passwort. Dafür ist ein schnelles
  Hashverfahren zulässig, hier SHA-256.
  ([OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html))
- A1 ist bestätigt. CEO-Entscheidung vom 10.11.2026: [ADR-0012](0012-hosting-region-usa.md)
  gilt nur für Railway. Ein späterer IdP ist dadurch nicht auf Railway `sfo`
  festgelegt.

## Entscheidung

Entschieden. Workloads der Art service und worker weisen sich mit einem API-Key je Identität aus. Menschen-Authentisierung ist zurückgestellt.

Die CEO hat technische Entscheidungen an den Head of Engineering delegiert.
Dieser Entscheid gilt seit dem 10.11.2026.

### Workloads

- Jede Identität der Art `service` oder `worker` erhält eigene API-Keys.
  Worker teilen sich keinen Key.
- Ein Key besteht aus dem erkennbaren Präfix `gmv_wk_` und mindestens 32 Byte
  Zufall.
- Gespeichert wird nur der SHA-256-Hash des Schlüssels. Klartext steht nicht
  in der Datenbank und nicht im Log. Argon2id bleibt Passwörtern vorbehalten
  und wird hier nicht verwendet.
- Jeder Key ist einzeln widerrufbar und hat ein optionales Ablaufdatum.
- Ausstellen und Widerrufen laufen nur über `python -m app.credentials`. Es
  gibt keinen HTTP-Endpunkt dafür. Der Schlüssel wird einmal bei der Ausgabe
  gezeigt.
- Sobald externe Worker hinzukommen, folgt OAuth 2.0 Client Credentials mit
  `private_key_jwt`. Das ist die vorgesehene Nachfolge und nicht Teil dieser
  Umsetzung.

### Menschen

Ein OIDC-IdP mit MFA ist zurückgestellt. Ein IdP bedeutet Vertrag und Kosten
und braucht die Freigabe der CEO. Bis dahin gibt es keine Menschen-Logins und
keinen Password Grant.

### Abgrenzung

Workload- und Menschen-Credentials sind am Server unterscheidbar. Nur ein
Schlüssel mit dem Präfix `gmv_wk_` ist ein Workload-Key. Andere Credentials
werden nicht als Workload angenommen. Die Autorisierung bleibt in der
besitzenden Instanz.

[../../api/openapi.yaml](../../api/openapi.yaml) beschreibt `callerCredential`
als diesen Workload-API-Key. Ein Platzhaltervermerk steht dort nicht mehr.

## Konsequenzen

- Die Control Plane prüft den Hash in konstanter Zeit und lehnt widerrufene
  und abgelaufene Schlüssel ab. `/health` und `/ready` bleiben ohne Nachweis.
- Autorisierung von Zustandsänderungen bleibt serverseitig in der besitzenden
  Instanz. Dieser Standard ersetzt die Assignment Authority nicht.
- Schlüssel und ihr Umgang folgen [ADR-0007](0007-secret-management.md), sobald
  der Secret-Provider entschieden ist. Bis dahin liegt der Klartext nur beim
  Empfänger der Ausgabe, der Hash nur in `credentials`.
- Ein IdP wird nicht eingebaut und keine Auth-Bibliothek eines Anbieters
  verwendet. Die Wahl des IdP, der Vertrag und die Kosten bleiben eine
  CEO-Freigabe. A1 erlaubt dafür auch einen Dienst außerhalb von Railway.
- Ein selbst betriebener IdP, falls die CEO ihn später freigibt, braucht
  Backup ([ADR-0006](0006-backup-retention-rpo-rto.md)) und Überwachung
  ([ADR-0010](0010-slo-alerting-incident.md)).

## Alternativen

| Option | Vorteil | Nachteil |
| --- | --- | --- |
| Eigene Auth in FastAPI (Passwörter, JWT) | keine Abhängigkeit | volle Verantwortung für MFA, Passwortspeicher und Sitzungen; der Password-Flow widerspricht RFC 9700 §2.4 |
| Gehosteter IdP (Auth0, Clerk, Supabase Auth, WorkOS) | MFA und OIDC fertig, wenig Betrieb | Vertrag und Kosten, braucht die CEO-Freigabe |
| Keycloak selbst betrieben auf Railway | Standard-OIDC, in `sfo` betreibbar | zweiter sicherheitskritischer Dienst mit eigener Datenbank |
| API-Keys für Workloads | je Identität widerrufbar, ohne IdP-Vertrag | kein Standardprotokoll; für externe Worker folgt `private_key_jwt` |

Für Workloads gilt die Zeile API-Keys. Ein IdP ist nicht gewählt.

## Bezug

- [ADR-0002](0002-python-fastapi.md)
- [ADR-0003](0003-single-assignment-authority.md)
- [ADR-0006](0006-backup-retention-rpo-rto.md)
- [ADR-0007](0007-secret-management.md)
- [ADR-0010](0010-slo-alerting-incident.md)
- [ADR-0012](0012-hosting-region-usa.md)
- [../IDENTITY_MODEL.md](../IDENTITY_MODEL.md)
- [../../SECURITY.md](../../SECURITY.md)
- [../../api/openapi.yaml](../../api/openapi.yaml)

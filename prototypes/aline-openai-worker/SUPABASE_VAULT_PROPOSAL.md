# CODEX-VAULT-001: optionale Supabase-Vault-Quelle für Aline

**Status:** Vorschlag für Review. Keine SQL-Ausführung, keine Railway-Änderung,
keine Freigabe eines Modellaufrufs. ADR-0007 ist weiterhin Proposed.

## Laufzeitvertrag

Der Worker liest den Schlüssel erst nach beiden expliziten Aufruffreigaben und
der Prüfung der unveränderten synthetischen Fixture. `--offline-demo` und
`--validate-only` greifen nie auf die Datenbank zu. Bei fehlendem Secret oder
einem Datenbankfehler stoppt der Modellpfad ohne Fallback auf `OPENAI_API_KEY`.

| Railway-Variable (Vorschlag) | Zweck |
| --- | --- |
| `ALINE_SECRET_SOURCE` | `env` (Standard) oder `supabase-vault` (explizites Opt-in) |
| `ALINE_VAULT_DATABASE_URL` | Nur im Vault-Modus: Zugang der Aline-spezifischen Postgres-Login-Rolle; als geschützte Laufzeitvariable speichern |
| `OPENAI_MODEL` | Bestehendes Modell-Gate: ausschließlich `gpt-6.1-terra` |
| `OPENAI_API_KEY` | Bestehende Quelle bei `ALINE_SECRET_SOURCE=env`; im Vault-Modus nicht verwendet |

Der Postgres-Treiber erzwingt `sslmode=verify-full`, maximal drei Sekunden
Verbindungsaufbau und drei Sekunden Statement-Laufzeit. Die Verbindung benötigt
ein vom Client vertrauenswürdiges Serverzertifikat und einen passenden
Hostnamen. Vor Staging muss die konkrete Supabase-Verbindungsart darauf geprüft
werden. Die Rolle darf keine Tabellen, Views oder sonstige Vault-Funktionen
direkt lesen; der Worker ruft nur die unten genannte Funktion auf.

## Supabase-SQL zur manuellen Prüfung

Die folgenden SQL-Fragmente sind ein **nicht ausgeführter Vorschlag**. Eine
zuständige Person muss vorhandene Rollen und Grants, Namenskollisionen sowie
die Berechtigung zum Eigentümerwechsel im Zielprojekt prüfen. Die Login-Rolle
erhält ihr Passwort über den freigegebenen Secret-Prozess, niemals über
Repository oder PR.

```sql
BEGIN;
CREATE ROLE aline_vault_function_owner NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS
  NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE aline_vault_reader LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS
  NOCREATEDB NOCREATEROLE NOREPLICATION;
GRANT USAGE ON SCHEMA vault TO aline_vault_function_owner;
GRANT SELECT ON vault.decrypted_secrets TO aline_vault_function_owner;

CREATE SCHEMA aline_private;
REVOKE ALL ON SCHEMA aline_private FROM PUBLIC;
GRANT CREATE ON SCHEMA aline_private TO aline_vault_function_owner;
GRANT USAGE ON SCHEMA aline_private TO aline_vault_reader;

CREATE FUNCTION aline_private.get_openai_api_key()
RETURNS text
LANGUAGE sql
SECURITY DEFINER
SET search_path = ''
AS $$
  SELECT ds.decrypted_secret
  FROM vault.decrypted_secrets AS ds
  WHERE ds.name = 'aline_openai_api_key'
$$;
ALTER FUNCTION aline_private.get_openai_api_key()
  OWNER TO aline_vault_function_owner;
REVOKE CREATE ON SCHEMA aline_private FROM aline_vault_function_owner;

REVOKE EXECUTE ON FUNCTION aline_private.get_openai_api_key() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION aline_private.get_openai_api_key()
  FROM anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION aline_private.get_openai_api_key()
  TO aline_vault_reader;
COMMIT;
```

Die Funktion hat **keine Argumente**. Der Secret-Name ist fest. Es gibt keinen
generischen Schlüssel-Lookup. Nur der nicht einloggbare Funktionsinhaber erhält
`USAGE` auf Schema `vault` und `SELECT` auf `vault.decrypted_secrets`; diese
Rechte gehen **nicht** an `aline_vault_reader`. `SECURITY DEFINER` läuft mit
den Rechten des Inhabers und kann RLS umgehen. Das private Schema darf nicht
für die Supabase Data API exponiert sein. `REVOKE` und `GRANT` stehen in
derselben Transaktion wie die Anlage, damit kein Zwischenzustand mit
allgemeinem `EXECUTE` sichtbar wird.

## Noch nötige manuelle Staging-Schritte

1. Secret-Provider- und Datenverarbeitungsentscheidung gemäß Governance
   klären; keine implizite Annahme von ADR-0007.
2. Die dedizierte Rolle, Funktionsrechte und TLS-Verbindungsart im Supabase-
   Projekt prüfen; SQL erst nach zuständiger Freigabe ausführen. Unabhängig
   kontrollieren, dass die Login-Rolle nur die feste Funktion ausführen kann
   und `SELECT` auf die Vault-View für sie verweigert wird. Den Secret-Wert
   manuell im Vault anlegen.
3. Nur Variablennamen und Konfigurationsmodell prüfen, danach ggf. geschützte
   Railway-Laufzeitvariablen für `GMV-V3/staging/aline-openai-worker-l1`
   setzen. Keine Werte in Logs, PR oder Testausgaben kopieren.
4. Separates Review, CI, Modell-/Budget-/Datentransferfreigaben und einen
   Staging-Testplan einholen. Dieser Draft löst keinen Deploy oder echten
   OpenAI-Aufruf aus.

Referenzen: [Supabase Vault](https://supabase.com/docs/guides/database/vault),
[Supabase Database Functions](https://supabase.com/docs/guides/database/functions),
`docs/adr/0007-secret-management.md`, `SECURITY.md`.

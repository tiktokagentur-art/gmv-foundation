# Sicherheit

Sicherheitsregeln für Greenfield V1. Sie gelten ab dieser Baseline. Ein produktives
System gibt es noch nicht. Die Regeln sind trotzdem verbindlich, damit der erste
Code und die erste Infrastruktur nicht gegen sie entstehen.

Das Repository ist öffentlich. Nichts in Git, in einem Issue oder in einem Pull
Request ist vertraulich.

## Keine Secrets

Secrets stehen nicht im Git. Dazu gehören Schlüssel, Tokens, Passwörter,
Verbindungszeichenfolgen, Zertifikate und Zugriff auf Backups.

Dasselbe gilt für:

- Logs und CI-Ausgaben
- Beispiele, Fixtures und Vorlagen
- Kommentare, ADRs und Fehlermeldungen
- lokal eingecheckte Umgebungsdateien

Ein Beispiel zeigt die Form, niemals einen verwendbaren Wert. Ein widerrufener
Wert bleibt ein Secret und gehört nicht in die Historie.

Welche Secret-Verwaltung, welche Rotation und welcher Break-glass-Zugang gelten,
ist nicht entschieden ([ADR-0007](docs/adr/0007-secret-management.md)). Bis dahin
wird kein Secret benötigt, weil es keinen laufenden Dienst gibt.

## Least Privilege

Jedes Subjekt bekommt nur die Rechte, die seine Aufgabe braucht. Das gilt für
Menschen, CI, Dienste und Worker.

Ein gemeinsames Konto für mehrere Dienste oder mehrere Worker ist nicht zulässig.
Rechte auf Produktion folgen nicht aus Rechten auf ein nicht-produktives System.
Lesen von Backups ist ein eigenes Recht und nicht dasselbe wie Schreiben der
primären Datenbank.

## Eigene Identität je Dienst und Worker

Jeder Dienst und jeder Worker hat eine eigene Identität. Menschen und Workloads
sind verschiedene Subjekte. Eine Identität wird nicht weitergegeben und nicht
in Git abgelegt.

Ein Worker führt nur Arbeit aus, die an seine Identität gebunden ist. Die
Registrierung dieser Identität hat genau einen Eigentümer
([ADR-0003](docs/adr/0003-single-assignment-authority.md)).

Welcher Authentisierungsstandard das technisch ist, ist offen
([ADR-0008](docs/adr/0008-auth-standard.md)).

## Autorisierung serverseitig

Jede Zustandsänderung wird auf dem Server autorisiert, der die Domäne besitzt.
Der Client, der Worker und ein Proxy entscheiden das nicht.

Ein Antrag (Claim, Heartbeat, Ergebnis, Fehler) ändert nichts, solange die
zuständige Instanz ihn nicht annimmt. Ablehnung ist der Normalfall bei
fehlender Identität, abgelaufenem Lease oder ungültigem Fencing.

## Nachvollziehbare Änderungen

Jede angenommene Zustandsänderung ist einem Subjekt zuzuordnen und wird im
Audit-Trail der zuständigen Instanz festgehalten. Der Audit-Trail ist nur
anhängend: eine Korrektur ist ein neuer Eintrag, keine stille Änderung.

Änderungen an diesem Repository laufen über Pull Request und unabhängige Review
([CONTRIBUTING.md](CONTRIBUTING.md)). Git ist der Audit-Trail der Dokumentation.
Ein ADR hält fest, wer eine Architekturentscheidung getroffen hat und welchen
Status sie hat.

## Schwachstellen melden

Es gibt noch keinen festgelegten vertraulichen Meldeweg. Schwachstellen nicht in
Issues, Pull Requests, Commits oder Diskussionen beschreiben.

Bis ein Meldeweg entschieden ist: die Repository-Eigentümer über GitHub
kontaktieren. Der erste Kontakt nennt keine technischen Details, keine Logs und
keine Zugangsdaten.

## Abgrenzung

Diese Datei ist kein Pentest, kein Betriebshandbuch und keine Liste von
Schritten zur Umgehung der Regeln. Konkrete Kontrollen in Railway, in der
Datenbank und im Dienst entstehen erst mit der Infrastructure und verweisen auf
diese Regeln.

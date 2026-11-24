# Factory-Katalog

Das Zielmodell sieht zwölf fachliche Factories vor. Deren endgültige
Namen, organisatorische Zuordnung und technische Implementierung
sind auf `main` noch nicht als vollständiges Zwölferinventar verifiziert.
Deshalb werden keine neun zusätzlichen Codebereiche erfunden.

| Dokumentationspilot | Stand | Referenz |
| --- | --- | --- |
| Control Plane | contract-only | [Control Plane](control-plane.md) |
| Software Factory | CI implementiert, autonome Runtime offen | [Software Factory](software-factory.md) |
| Content Factory | planned | [Content Factory](content-factory.md) |

Diese technischen Piloten sind keine bestätigte Untermenge der
zwölf organisatorischen Fach-Factories.

## Aufnahme einer neuen Factory

1. Offiziellen Namen und Zuständigkeit anhand aktueller Quellen prüfen.
2. Repository, `main`-Commit und Codepfade nachweisen.
3. State Owner, APIs, Tests, Review- und Security-Grenzen zuordnen.
4. Status sauber ausweisen; fehlende Nachweise als `unverified` führen.
5. [Factory-Vorlage](../templates/factory.md) ausfüllen und PR prüfen.

Eine organisatorische Abteilung ist nicht automatisch eine Factory.

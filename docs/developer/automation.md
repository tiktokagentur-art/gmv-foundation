# Documentation as Code

Dokumentation liegt neben dem Code, ohne zusätzliche
Dokumentationsplattform. Ein PR aktualisiert betroffene
Technikseiten zusammen mit seiner Implementierung.

## Automatisierte Prüfungen

[docs.yml](../../.github/workflows/docs.yml) führt
[check_docs.py](../../scripts/check_docs.py) bei relevanten
Pull Requests aus. Der Prüfer kontrolliert Pflichtseiten
und relative Links im Handbook und seinen Einstiegspunkten.
Externe URLs, Sprungmarken und fachliche Korrektheit
werden nicht automatisch validiert.

Die vorhandene [CI](../../.github/workflows/ci.yml)
prüft weiterhin Markdown, Struktur, Secrets und Backend.

## Codex als unabhängiger Reviewer

Wenn die separate Codex-Autoreview-Einstellung aktiv ist,
soll der technische Review prüfen, ob Architektur-,
Code- und API-Änderungen korrekt dokumentiert sind:

1. Stimmen Seiten und Code-Diff überein?
2. Werden offene PRs oder `Proposed`-ADRs als fertig dargestellt?
3. Sind Identität, State Ownership und Security-Gates beachtet?
4. Sind Quellen, Testevidenz und Änderungen vollständig?
5. Enthalten die öffentlichen Texte vertrauliche Informationen?

Dieser PR aktiviert keinen Codex-Dienst, keinen autonom
schreibenden Bot und keine neuen Merge-Rechte.
Ein KI-Review ist kein Ersatz für formale Freigabe.

GitHub Pages und produktive Veröffentlichungen gehören
nicht zum Umfang dieses Pakets.

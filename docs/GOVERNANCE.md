# Governance

Wie Entscheidungen in Greenfield V1 entstehen, gelten und geändert werden.
Personen sind hier nicht namentlich besetzt. Offene Rollen bleiben offen, statt
mit einem Platzhalter belegt zu werden.

## Was gilt

| Quelle | Wirkung |
| --- | --- |
| ADR mit Status `Accepted` | beschlossen, für nachfolgende Änderungen verbindlich |
| ADR mit Status `Proposed` | festgehaltener Vorschlag, keine Bauvorlage |
| [ARCHITECTURE.md](ARCHITECTURE.md), [../SECURITY.md](../SECURITY.md), [../CONTRIBUTING.md](../CONTRIBUTING.md) | Regeln der Baseline, soweit sie nicht einem `Accepted`-ADR widersprechen |
| README und Kommentare | Einstieg, nicht die Entscheidung selbst |

Widerspricht ein Dokument einem `Accepted`-ADR, gilt das ADR. Der Widerspruch
wird im nächsten Pull Request aufgelöst, nicht stillschweigend im Code.

## Leitsatz

Build first. Verify everything. Scale after proof.

Eine Regel, die nicht geprüft werden kann, wird nicht um einen Zahlwert ergänzt,
nur damit sie vollständig aussieht. Offene Ziele bleiben `Proposed`.

## Änderungen

Jede Änderung an `main` ist ein Pull Request mit unabhängiger Review.
[../CONTRIBUTING.md](../CONTRIBUTING.md) ist die Arbeitsregel:

- kein direkter Push und kein Force-Push auf `main`
- mindestens eine Freigabe
- die freigebende Person hat keinen Commit an dieser Änderung
- Autorinnen und Autoren geben ihre eigene Änderung nicht frei
- keine Ausnahme für Administratoren

[ADR-0004](adr/0004-branch-protection-codeowners.md) ist der offene Beschluss über
Branch Protection, erforderliche Checks und CODEOWNERS. Diese Baseline schaltet
keine Repository-Einstellung ein und stellt nicht fest, ob eine bestehende
Einstellung der Organisation bereits greift.
[`.github/CODEOWNERS`](../.github/CODEOWNERS) ist ein Entwurf ohne aktive Owner.

## ADR-Verfahren

Eine Entscheidung über Architektur, Sicherheit, Datenhaltung, Identität,
Betrieb, Release oder Kompatibilität wird ein ADR. Kleine Klarstellungen an
einem bestehenden Dokument brauchen kein ADR, solange sie keine neue Regel einführen.

Ablauf:

1. Vorlage [adr/template.md](adr/template.md) nach `docs/adr/NNNN-kurzer-titel.md` kopieren.
2. Status `Proposed`, solange nicht entschieden ist. Der erste Satz der Entscheidung lautet `Nicht entschieden.`
3. Pull Request, unabhängige Review.
4. Ein Entscheid setzt den Status auf `Accepted` und beginnt die Entscheidung mit `Entschieden.` Wer entscheiden darf, muss im ADR stehen. Fehlt die Rolle, bleibt der Status `Proposed`.
5. Eine Ersetzung ist ein neues ADR. Das alte wird `Superseded` und verlinkt das neue. Der alte Text bleibt lesbar.
6. Der Index [adr/README.md](adr/README.md) führt jede Nummer.

`scripts/validate_structure.py` prüft Dateinamen, Statuszeile, Pflichtabschnitte
und den ersten Satz der Entscheidung. Die Prüfung ist ein Geländer gegen stilles
Umschreiben. Sie ersetzt die Review nicht.

Die CEO-Entscheidung vom 09.11.2026 ist in [ADR-0001](adr/0001-postgresql-on-railway.md)
und für die Region in [ADR-0012](adr/0012-hosting-region-usa.md) festgehalten.
Python / FastAPI ist ausdrücklich nicht entschieden
([ADR-0002](adr/0002-python-fastapi.md)). Das Skelett GF-006 steht auf diesem
Vorschlag, ohne den Status zu ändern.

## Eine Instanz je Domäne

[ADR-0003](adr/0003-single-assignment-authority.md) gilt für jede Umsetzung:

- genau eine autoritative Instanz je Zustandsdomäne
- genau eine Assignment Authority
- die Foundation definiert die Verträge
- die Infrastructure implementiert diese Verträge und testet sie

Ein Pull Request, der für dieselbe Domäne einen zweiten Schreiber einführt,
widerspricht einem `Accepted`-ADR und wird nicht freigegeben.

## Sprache und Öffentlichkeit

Dokumentation ist Deutsch. Dateinamen und technische Bezeichner sind Englisch.
Neue Begriffe werden in [ARCHITECTURE.md](ARCHITECTURE.md) einmal definiert.

Das Repository ist öffentlich. Governance-Dokumente nennen keine privaten
Konten, keine internen Hostnamen und keine Zugangswege.

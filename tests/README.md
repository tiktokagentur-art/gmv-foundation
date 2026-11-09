# Tests

Platzhalter. Es gibt noch keine Verträge und keine Laufzeit, die ein Test prüfen könnte.

Die heute laufende Prüfung ist die Repository-Struktur:

```bash
python3 scripts/validate_structure.py
```

Spätere Tests gehören zur Infrastructure: sie weisen die Verträge der Foundation
nach. Ein Test ist keine zweite Quelle für denselben Zustand.

`scripts/validate_structure.py` erwartet in `tests/` ausschließlich diese Datei,
bis der erste Vertragstest im selben Pull Request die Prüfung anpasst.

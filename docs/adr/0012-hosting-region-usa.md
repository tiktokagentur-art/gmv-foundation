# ADR-0012: Hosting-Region USA (Railway sfo)

- Status: Accepted
- Datum: 2026-11-09
- Entscheider: CEO

## Kontext

Greenfield V1 betreibt seine Dienste auf Railway. Welche Region das ist, war in
[ADR-0005](0005-railway-environments.md) noch offen.

Die CEO-Entscheidung vom 09.11.2026 legt die Hosting-Region auf die USA fest,
Railway-Region `sfo`.

Im Arbeitsauftrag heißt diese Entscheidung ADR-0004. Die Nummer 0004 ist im
Repository bereits der offene Entscheid zu Branch Protection
([ADR-0004](0004-branch-protection-codeowners.md)). Nummern werden nicht
wiederverwendet. Diese Entscheidung trägt deshalb die nächste freie Nummer 0012.

Dieses ADR legt kein Railway-Projekt und keinen Dienst an.

## Entscheidung

Entschieden. Alle Dienste laufen in der Railway-Region sfo (USA), in derselben Region.

PostgreSQL und jeder weitere Dienst dieses Fundaments nutzen `sfo`. Ein Dienst
in einer anderen Region ist unzulässig. Umgebungen und Limits bleiben in
ADR-0005 offen. Die Region ist dort nicht mehr offen.

Ergänzung vom 10.11.2026: Dieser Entscheid gilt nur für Railway, nicht für
externe Anbieter. Quelle: CEO-Auswahl im Chat des Head of Engineering, 10.11.2026 05:49 MEZ.

## Konsequenzen

- Zwei Nachteile sind benannt und mit dem Entscheid akzeptiert: höherer Dokumentationsaufwand unter der DSGVO, sobald personenbezogene Daten verarbeitet werden, und höhere Latenz aus Deutschland.
- Dieses ADR ist keine Rechtsprüfung und legt keine Datenverarbeitung an. Der Dokumentationsaufwand ist eine Folge der Region, nicht ein Grund, die Region stillschweigend zu ändern.
- Alle Services laufen in derselben Region. Eine Aufteilung zwischen EU und USA widerspricht diesem Entscheid und würde zusätzlich eine zweite schreibende Instanz riskieren ([ADR-0003](0003-single-assignment-authority.md)).
- Es entsteht hier keine Railway-Ressource.

## Alternativen

Nicht in diesem ADR neu bewertet. Der Entscheid der CEO vom 09.11.2026 wird
dokumentiert. Eine andere Region braucht ein neues ADR, das dieses auf
`Superseded` setzt.

## Bezug

- [ADR-0001](0001-postgresql-on-railway.md)
- [ADR-0003](0003-single-assignment-authority.md)
- [ADR-0004](0004-branch-protection-codeowners.md)
- [ADR-0005](0005-railway-environments.md)

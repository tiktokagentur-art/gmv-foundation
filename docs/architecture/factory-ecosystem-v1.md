# GMVGANG Factory Ecosystem V1 — Offline contracts

Status: FE-003B mock-only; no production activation.

The existing Control Plane is the sole owner of WorkItems, assignments, claims, leases, fencing and worker registration (ADR-0003). Factory workers do not write those domains. Factory Registry is a planned operational projection in Railway PostgreSQL, not implemented in this package. Notion is the organizational source for personnel and mandates; a projection must validate identity, version, authority and conflicts before acceptance. No Notion or PostgreSQL connections are present.

Twelve factories share one Control Plane and one worker-runtime architecture. This pilot covers only offline contracts and mocks. New leadership profiles are Robin Keller (Research), Alex Winter (Data) and Kim Berger (Quality); no VE IDs, technical identities or permissions are assigned. Activation order is Research, then Data, then Quality, each after separate approval. Neither registration nor activation occurs here.

Pilot constraints: two concurrent mock workers at most, a 60-minute maximum test window, zero unauthorized actions, all security tests passing, and ceilings of EUR 25 total, EUR 10 per UTC day and EUR 5 per WorkItem. These are ceilings, not authorization to spend. No external APIs, network requests, database writes or actual costs.

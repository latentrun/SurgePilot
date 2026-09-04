# ADR-0006: Run Background Compensation in a Separate API Worker

- Status: Accepted

Timeout scans, Stop convergence, stale lease recovery, bounded remote cleanup, and lightweight artifact processing run in a separate `api-worker` process that shares API application code and coordinates through PostgreSQL. Running these loops inside every HTTP worker risks duplicate ownership, while Redis and an external task queue add infrastructure the initial milestone does not need. Jobs must therefore be idempotent and use database locking or claiming so accidental multiple worker instances remain safe.

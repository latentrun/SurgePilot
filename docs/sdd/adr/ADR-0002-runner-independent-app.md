# ADR-0002: Keep Runner as an Independent Application

- Status: Accepted

Runner is an independent application because remote, long-running load execution has a different process and security boundary from the HTTP API. It communicates with API through versioned, authenticated HTTP/JSON contracts and has no PostgreSQL, MinIO, session, or API-internal access. This costs explicit protocol and integration testing, but keeps business-state authority in API and prevents remote Load Nodes from inheriting control-plane credentials.

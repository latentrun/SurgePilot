# ADR-0003: Use MinIO as the Only Initial Object Store

- Status: Accepted

The initial milestone uses MinIO for Dependency Files and Run Artifacts, with all transfers proxied and authorized by API. A local filesystem would weaken container and multi-process behavior, while multiple providers or direct browser uploads would expand configuration, authorization, and test surfaces. Other storage backends, storage plugins, and browser-visible presigned flows require a later decision.

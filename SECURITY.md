# Security and trust boundaries

This public research API handles grid data and charging parameters. It does not accept file uploads, arbitrary URLs, account credentials or physical-device commands. Browser input and upstream JSON are untrusted and validated.

- Upstream hosts are fixed in application configuration. Clients cannot select URLs.
- Charging inputs reject non-finite values, unexpected fields, excessive horizons and infeasible energy targets.
- Native LightGBM text and JSON are loaded from a trusted bundled directory; no pickle or arbitrary uploaded model is deserialised. The model checksum is checked at startup. A checksum detects mismatch, not a maliciously replaced card and model together; trust the immutable image/source provenance.
- The image runs as a non-root user. Compose drops capabilities and uses a read-only root filesystem with a writable data volume.
- Dashboard content uses DOM text nodes, with no source-supplied HTML. The app sends a Content Security Policy. Swagger documentation has a separate CDN/inline policy because its standard UI requires it.
- Secrets, Terraform state, raw user configuration and cloud keys are excluded from Git. Azure CI uses OIDC. No Azure permissions or accounts are created by local startup.
- Public endpoints are read/compute APIs, with no model-promotion or destructive administrative route. A per-process API quota, 16 KiB body limit, five-second body deadline, upstream failure cooldown and bounded inputs limit work. A production gateway should enforce distributed quotas and abuse controls.
- Logs do not store charging request bodies. Metrics labels use route templates, avoiding user-controlled label cardinality.

The default public deployment is a small portfolio service, not a hardened multi-tenant system. MLflow is for local/restricted use and is not exposed by the public container. Security incident details should be shared privately with the repository owner, without posting secrets in an issue.

Third-party GitHub actions are pinned to verified commit SHAs. Image publication depends on the CI workflow; deployment accepts only the repository's GHCR content digest. Code and lock updates still require review. Dependency scans are point-in-time advisory checks and do not establish absence of vulnerabilities.

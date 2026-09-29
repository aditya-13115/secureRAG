# SecureRAG Admin Document Control

This feature adds an admin-only document control console without changing the existing chat, ACL, semantic retrieval, BM25, or RRF contracts.

## Admin roles

Only these roles can use the admin APIs:

- CEO
- CTO
- COFOUNDER

The backend enforces this with `require_policy_admin`. The frontend also shows an access-denied modal when another demo role opens the admin area.

## Workflow

```text
Admin uploads file
        |
        v
PENDING_POLICY
        |
        | admin approves classification + ACL
        v
READY_FOR_INGESTION
        |
        v
background worker
        |
        +--> loader
        +--> chunker
        +--> embeddings -> Chroma
        +--> text -> BM25
        |
        v
INDEXED
        |
        v
chat retrieval automatically sees it
```

A new upload is deliberately not indexed before policy approval. This keeps the existing pre-retrieval authorization boundary intact.

## Admin APIs

```text
GET    /api/documents
GET    /api/documents/{document_id}
GET    /api/documents/policy-options
GET    /api/documents/ingestion/status

POST   /api/documents/upload
PATCH  /api/documents/{document_id}/policy
POST   /api/documents/{document_id}/reindex
DELETE /api/documents/{document_id}
```

All admin endpoints use the existing `X-User-Email` identity mechanism and `require_policy_admin` dependency.

## What is tracked

Each document exposes:

- filesystem path and existence
- relative path
- file size
- SHA-256 checksum
- version
- owner department
- current classification and access scope
- current role/department/user grants
- who uploaded/registered it
- who last changed the policy
- when the policy changed
- who deleted it
- deletion time
- indexing time
- audit history

Audit events include actions such as:

```text
REGISTERED
UPLOADED
POLICY_UPDATED
REINDEX_REQUESTED
FILE_UPDATED
DELETE_REQUESTED
DELETE_FILE_FAILED
FILE_DELETED
RESTORED_PENDING_POLICY
```

## Background processing

The API does not wait for chunking or embeddings. A single in-process daemon worker consumes an internal queue, which keeps heavy indexing work out of FastAPI request/event-loop handling.

The indexer also checks document status/version before finalizing an index. If a file, policy, or deletion changed while indexing was running, the stale search output is removed instead of being published as the current `INDEXED` version.

If a stale index job is detected, the worker requeues the current `READY_FOR_INGESTION` version after the old job finishes.

## Delete semantics

Deletion is intentionally two-phase:

1. The SQL document status becomes `DELETED` first, immediately revoking retrieval access.
2. Physical file removal and Chroma/BM25 cleanup happen afterward.

If physical deletion fails, access remains revoked and an audit event records the failure.

## Direct filesystem changes

The watcher remains optional. It is still useful when someone changes files directly under `data/documents/`.

Uploads, policy approvals, re-indexes, and deletes through the admin console do not require the watcher because they enqueue background work directly.

## Production note

The prototype worker is intentionally local and in-process. A production deployment should move the same job contract to a durable queue/worker system so jobs survive process restarts and can scale independently.

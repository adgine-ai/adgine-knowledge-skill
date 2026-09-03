# Skill API contract

The configured API key is bound server-side to exactly one Skill knowledge base. Send `Authorization: Bearer <skkb-key>` to `<base-url>/api/v1/skills/kb`; never add user, project, or knowledge-base identifiers.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Bound knowledge-base information and snapshot status |
| GET | `/tree` | Nested directory tree |
| POST | `/dirs` | Create directory |
| PUT | `/dirs/{id}` | Rename directory |
| DELETE | `/dirs/{id}` | Delete an empty directory |
| POST | `/files` | Multipart upload; repeat field `files` |
| GET | `/files` | Paginated list; `keyword` searches filenames |
| GET | `/files/{id}` | File details and ingestion status |
| GET | `/files/{id}/download` | Original binary, not a JSON envelope |
| GET | `/files/{id}/content` | Canonical Markdown |
| GET | `/files/{id}/metadata` | Document and snapshot metadata |
| GET | `/files/{id}/processing-history` | Processing stages and history |
| PUT | `/files/{id}/content` | Replace canonical Markdown and reindex |
| POST | `/files/{id}/versions` | Multipart binary replacement, field `file` |
| DELETE | `/files/{id}` | Permanently delete a document |
| POST | `/queries` | Start a Pi Agent query |
| GET | `/queries/{query_id}` | Query status and result |

JSON success is normally `{ "code": 0, "data": ..., "message": "ok" }`. Clients must ignore unknown fields. Downloads are raw binary.

## Permissions

- `files:read`: knowledge-base, directory, file, content, metadata, history and download reads.
- `files:write`: directory writes, upload, canonical Markdown update and new version.
- `files:delete`: file and empty-directory deletion.
- `query:execute`: create and poll a query.

Every authorized request, including polling, may consume daily quota.

## Idempotency and retries

Send a stable `Idempotency-Key` of 1–128 characters for uploads, content updates, binary versions, and queries. Reuse it only when retrying the same logical operation. Query reuse with different parameters returns `409`.

Automatically retry only network errors and HTTP `500`, `502`, or `503`, at most three attempts with bounded exponential backoff. Preserve the same idempotency key. Do not automatically retry authentication, authorization, validation, quota, or ambiguous conflict errors.

## Asynchronous states

Document terminal states are `ready`, `error`, and `archived`; `pending` and `processing` require bounded polling. After documents are ready, the knowledge-base `snapshot_status` must also become `ready` before querying. `empty`, `building`, and `failed` are not query-ready.

Query terminal states are `succeeded`, `failed`, and `cancelled`. A succeeded query has a separate `answer_status`: `complete`, `insufficient_evidence`, or `not_found`. Only citations with `verified=true` should be treated as evidence.

## Limits and formats

Query text is 1–4000 characters; `max_sources` is 1–50 (default 12). File and total storage limits are environment-controlled; the current default maximum file size is 100 MB. Supported extensions are PDF, DOCX, XLSX, PPTX, TXT, MD, HTML/HTM, PNG, JPG/JPEG, WEBP, BMP, and TIF/TIFF.

Batch upload may return HTTP 200 while individual items contain `error`, `duplicate=true`, or `existing_id`. Inspect every item.


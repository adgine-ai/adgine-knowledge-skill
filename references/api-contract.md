# Skill API contract

The configured API key is bound server-side to exactly one Skill knowledge base. Send `Authorization: Bearer <skkb-key>` to `<base-url>/api/v1/skills/kb`; never add user, project, or knowledge-base identifiers.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Bound knowledge-base information and snapshot status |
| GET | `/tree` | Nested directory tree |
| GET | `/query-filters` | Snapshot-backed owner names, source IDs, directory paths and record types |
| POST | `/dirs` | Create directory |
| PUT | `/dirs/{id}` | Rename directory |
| DELETE | `/dirs/{id}` | Delete an empty directory |
| POST | `/files` | Multipart upload; repeat field `files` |
| GET | `/files` | Paginated list; `keyword` searches filenames |
| GET | `/files/{id}` | File details and ingestion status |
| GET | `/files/{id}/download` | Original binary, not a JSON envelope |
| GET | `/files/{id}/content` | Canonical Markdown |
| GET | `/files/{id}/metadata` | Document and snapshot metadata |
| PUT | `/files/{id}/query-metadata` | Replace explicit business metadata; `{}` restores inference |
| GET | `/files/{id}/processing-history` | Processing stages and history |
| PUT | `/files/{id}/content` | Replace canonical Markdown and reindex |
| POST | `/files/{id}/content/append` | Append Markdown server-side and reindex |
| POST | `/files/{id}/versions` | Multipart binary replacement, field `file` |
| DELETE | `/files/{id}` | Permanently delete a document |
| GET | `/queries/capabilities` | Query permission probe for filter support and metadata readiness |
| POST | `/queries` | Start a Pi Agent query |
| GET | `/queries/{query_id}` | Query status and result |

JSON success is normally `{ "code": 0, "data": ..., "message": "ok" }`. Clients must ignore unknown fields. Downloads are raw binary.

Original downloads use `Content-Disposition: attachment` and require `files:read`. The CLI saves those bytes without converting them; `/content` instead returns Canonical Markdown. HTML is downloaded as a file, not hosted as a public web page. Stored original bytes can be read while ingestion is pending; removed/missing originals return `404`. PDF compression, when successful, replaces the uploaded PDF before storage.

`files.py download --json` returns `ok`, `document_id`, absolute `output`, local `file_name`, `file_size` (bytes), and `sha256` calculated from the saved file. `--output` is required; `--force` permits an intentional local overwrite. Names and extensions come from the caller's output path, not from response headers. It does not open a viewer.

## Query images

Set `include_images=true` (`query.py ask --include-images`) to request related image assets. The server may return an empty `images` array even when the answer succeeds. A returned image has this shape:

```json
{
  "asset_id": "<image-asset-uuid>",
  "url": "https://<asset-host>/<image-path>",
  "caption": "Product diagram",
  "description": "Diagram description",
  "sources": []
}
```

The CLI's `ask --json` wrapper places the result under `query`, so use `query.images`. `status --json` returns the result directly, so use `images`. Plain text output lists the URLs and captions. Rendering an image requires the host's image capability; the CLI does not display pixels. Do not derive URLs from document IDs or assume a citation's `source_url` is an original-file download URL.

## Permissions

- `files:read`: knowledge-base, directory, file, content, metadata, history and download reads.
- `files:write`: directory writes, upload, canonical Markdown append/update and new version.
- `files:delete`: file and empty-directory deletion.
- `query:execute`: create and poll a query.

Every authorized request, including polling, may consume daily quota.

## Idempotency and retries

Send a stable `Idempotency-Key` of 1–128 characters for uploads, content appends/updates, binary versions, and queries. Reuse it only for the same logical operation. Query reuse with different parameters returns `409`.

Automatically retry only network errors and HTTP `500`, `502`, or `503`, at most three attempts with bounded exponential backoff. Preserve the same idempotency key. Do not automatically retry authentication, authorization, validation, quota, or ambiguous conflict errors.

Markdown append is the exception to automatic retry: an ambiguous response is not retried because append is non-idempotent. The server locks the document row, appends with one blank line between existing and new content, and coalesces appends received while Markdown processing is pending or running. Concurrent writer order is unspecified, but each accepted append is retained. The original uploaded binary is unchanged.

## Asynchronous states

Document terminal states are `ready`, `error`, and `archived`; `pending` and `processing` require bounded polling. After documents are ready, the knowledge-base `snapshot_status` must also become `ready` before querying. `empty`, `building`, and `failed` are not query-ready.

Query terminal states are `succeeded`, `failed`, and `cancelled`. A succeeded query has a separate `answer_status`: `complete`, `insufficient_evidence`, or `not_found`. Only citations with `verified=true` should be treated as evidence.

## Limits and formats

Query text is 1–4000 characters; `max_sources` is 1–50 (default 12). File and total storage limits are environment-controlled; the current default maximum file size is 100 MB. Supported extensions are PDF, DOCX, XLSX, PPTX, TXT, MD, HTML/HTM, PNG, JPG/JPEG, WEBP, BMP, and TIF/TIFF.

Batch upload may return HTTP 200 while individual items contain `error`, `duplicate=true`, or `existing_id`. Inspect every item.

## Filtered queries

See [query-filters.md](query-filters.md) for filter fields, business-date semantics, range enforcement and coverage. `POST /queries` accepts optional `filters` and `mode` (`search` or `summarize`). `GET /files` accepts the same filter object encoded as the `filters` query parameter, returning ready snapshot records. Unknown filter fields are rejected with HTTP 400. Existing queries without filters retain their original scope.

Person queries use exact `employee_names` across application identities. Same-name
records are included together; differing app_id/open_id values do not cause an
ambiguity error. `query-filters.employees[].ambiguous` remains false for response
compatibility. `employee_ids` is an optional legacy constraint; when supplied with
names it still applies as AND. Personal formal reports with `latest_only` are
grouped by name, scope, report type, variant and business period, not source ID
or directory. This query-policy update needs no new metadata schema or snapshot
rebuild when owner names already exist.

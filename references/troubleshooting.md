# Troubleshooting

## Authentication and authorization

- `401`: the key is missing, invalid, expired, disabled, or revoked. Stop retrying and ask the administrator for a valid key.
- `403`: the key is valid but lacks the endpoint's scope. Ask the administrator to add the precise required permission.
- `404`: the resource does not exist in the knowledge base bound to this key. Do not probe other IDs.

## Conflicts and readiness

- `409 project index is not ready`: wait for documents and then the knowledge-base snapshot; do not retry query creation in a tight loop.
- Other `409`: inspect document status, processing history, and the error message. Common causes are non-empty directories, busy documents, a pending replacement version, or idempotency misuse.
- A document stuck in `processing` or ending in `error`: read `metadata` and `history`, preserving the request/document ID when reporting to the administrator.

## Uploads

- HTTP 200 does not mean every file succeeded. Inspect each item for `error`, `duplicate`, `existing_id`, and `document_id`.
- `413` or an HTML error page normally comes from a gateway/body-size limit. Do not parse it as JSON.
- A duplicate content hash may reference an existing document even when filenames differ.

## Queries

- Poll no faster than the CLI defaults because each request may consume quota.
- `status=succeeded` plus `answer_status=not_found` is a successful execution with no supported knowledge answer.
- `429` is quota exhaustion. Stop polling and wait for reset or contact the administrator.

When escalating an issue, provide timestamp, endpoint and method, HTTP status, returned `code`, request/query/document ID, idempotency key, and operation stage. Never provide the API key or Authorization header.

# Scoped Skill KB queries

This capability is available only on Skill API knowledge bases. Filtering selects
an immutable document/line scope before exact search or BM25 ranking. Follow-up
search, reads, evidence validation and fallback answers cannot widen that scope.

## Agent workflow

1. Resolve the user's task: find an existing formal report, answer a topic, or
   produce a new complete work summary. These use different source selections.
2. Use the exact owner name with `--employee-name`; for “my” records, use the
   verified current user's name. Discover available names with
   `knowledge_base.py query-filters --json` when needed. Same-name records are
   queried together across applications, including different people who share a
   name. Different app_id/open_id values do not make a name query ambiguous.
   Do not replace the name with an ID or append an ID constraint to this workflow.
   Person ownership is different from author, uploader or a mention in the body.
3. Resolve relative dates from the host's actual clock in Asia/Shanghai. Weeks
   start Monday. On 2026-10-12, “this week” is [2026-10-12, 2026-10-19), “last
   week” is [2026-10-05, 2026-10-12). Do not hardcode these example dates.
4. Pass the explicit fields to `query.py ask` or use `files.py list` with the same
   filters to inspect the scope first. Keep all pages when enumerating files.
5. Inspect query_scope, answer_status and coverage. Empty scope means no matching
   ready material; never retry against the whole KB silently. Unknown dates and
   missing metadata are not proof that no work happened.

For a new work summary, prefer source records (`work_record`, `agent_history`,
`operation_record`) rather than reusing previous generated reports as independent
work events. For an existing report, use `formal_report`, `daily`/`weekly`, and
`manual`/`ai` as appropriate. Do not mix company/department contributions into a
personal summary.

## Parameters

| CLI flag | API filter field | Meaning |
|---|---|---|
| --employee-name | employee_names | Preferred person filter: exact ownership names across applications; repeat for OR |
| --employee-id | employee_ids | Optional legacy ID constraint; narrows results and is not required for name queries |
| --date-from | date_from | Inclusive business date |
| --date-to-exclusive | date_to_exclusive | Exclusive business date |
| --date-match | date_match | contained (default) or overlap |
| --directory-id | directory_ids | Stable directory IDs |
| --directory-path | directory_paths | Exact full path, e.g. /信息碎片/唐立兴 |
| --no-descendants | include_descendants=false | Direct folder membership only |
| --document-id | document_ids | Ready document IDs in the bound KB snapshot |
| --record-kind | record_kinds | work_record, formal_report, agent_history, operation_record, crm_history, attachment, document |
| --report-type | report_types | daily or weekly |
| --scope | scopes | person, department, company |
| --variant | variants | manual or ai |
| --origin | origins | Exact metadata origin |
| --mime-type | mime_types | Exact MIME type |
| --filename-keyword | filename_keyword | Filename substring |
| --include-test | exclude_test=false | Include designated test records |
| --all-revisions | latest_only=false | Include older formal report revisions |

Different dimensions are AND; values in one array are OR. Name and ID supplied
together are AND. `--filters-file` reads a JSON object containing these API fields;
explicit CLI flags override the corresponding fields. No flags means no new
filters and preserves the existing query behavior. `--mode summarize` enables
the default filter policy even if no other filter is supplied.

Use name-only person filters for both file discovery and queries:

```bash
python3 scripts/files.py list --employee-name "唐立兴" \
  --record-kind formal_report --report-type weekly --scope person \
  --date-from 2026-10-12 --date-to-exclusive 2026-10-19 --json
```

`query-filters` groups options by name. Its legacy `ambiguous` field is false;
source IDs are retained for compatibility, not a list of distinct people to
choose between. If an older server still rejects a name as ambiguous, report the
server limitation; do not silently retry with an ID or a wider scope.

For personal formal reports, `latest_only` groups by owner name, scope, report
type, variant and business period, regardless of source application or folder.
It chooses the latest source_cutoff, then revision, then document ID. Manual/AI
variants and different periods remain separate; `--all-revisions` retains all
versions. Non-personal reports retain their existing grouping.

Dates are business periods, not created_at/updated_at. Default `contained` avoids
including a whole weekly report in a daily query. `overlap` intentionally includes
intersecting document periods; it does not prove every event happened on the
requested day. Agent histories with exact date headings can be restricted to
those heading ranges. Partial scopes expose Markdown rather than undated
structured Excel/PDF regions. Unknown dates fail closed for a requested date range.

## Metadata and coverage

Existing adgine-work-report/adgine-report JSON comments and directory/date headings
are parsed as data. A name without application IDs is sufficient for name filtering.
Missing or incorrect owner names can be corrected explicitly:

```bash
python3 scripts/files.py set-query-metadata DOCUMENT_ID --metadata-file metadata.json --json
```

Example metadata.json:

```json
{
  "employee_name": "唐立兴",
  "period_start": "2026-10-10",
  "period_end_exclusive": "2026-10-11",
  "record_kind": "work_record",
  "scope": "person"
}
```

This replaces explicit metadata overrides and rebuilds the owning Skill snapshot;
it does not edit Markdown. An empty object restores inference. `source_cutoff`, if
supplied, must be an ISO datetime with timezone. Files with newer binary versions
inherit explicit metadata until it is replaced deliberately.

`mode=search` answers a topic within the scope. `mode=summarize` asks the runner to
enumerate all scope documents and read their allowed ranges, then summarize. If
the tool/token/time budget prevents full reading, answer_status is downgraded to
insufficient_evidence. Coverage includes matched/read/fully-read counts, unread
IDs/ranges and complete. Full reading proves scope coverage, not that every fact
was summarized or that the source system uploaded every expected record.

Query idempotency includes filters and mode. Reusing an operation ID with different
conditions returns 409. Unknown fields, invalid date ranges and invalid IDs/paths
are rejected rather than silently ignored. Old snapshots without filter metadata
must be rebuilt before using this feature; ordinary unfiltered queries remain
available during rollout.

Filtered ask probes `/queries/capabilities` before creating a query, and checks the returned scope against the requested fields before using results. This prevents an old server from silently ignoring filter fields during a staged rollout. The probe requires query:execute and is an additional quota-counted request. Filtered file lists also require scope confirmation.

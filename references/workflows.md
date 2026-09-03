# Workflows

## Save visible conversation content

1. Identify the user-visible content the user wants saved. Do not include system/developer instructions, hidden reasoning, tool traces, secrets, or unrelated conversation.
2. Produce clean Markdown with a specific title, brief context, headings, and the useful content. Do not invent claims absent from the conversation.
3. If the target directory is unclear, use the knowledge-base root unless choosing a directory changes the user's intended organization materially.
4. List files by the intended filename before writing. A filename match does not prove identical content.
5. Write the Markdown to a temporary `.md` file, then run:

   ```bash
   python3 <skill-root>/scripts/files.py upload --file '<temporary-file>' --wait --json
   ```

6. Inspect every returned upload item. Report the document ID, duplicate/error state, and final ingestion state. Remove the temporary local file after the operation if it was created only for this upload.

## Upload user files

Use one `--file` per attachment. Pass `--directory-id` only after resolving the intended directory with `knowledge_base.py tree`. Keep `--wait` for normal interactive tasks; for long OCR jobs use `--no-wait`, return the document IDs, and poll later with `files.py status`.

## Read and update

- Read searchable content with `files.py content <document-id>`.
- Use `update-markdown` only when the user intends to change canonical searchable text. It does not replace the original binary.
- Use `new-version` for a replacement PDF, Word document, spreadsheet, presentation, image, or other original. The API returns a new document ID and later archives the old ID.
- The API currently has no file rename or move operation. State that limitation instead of emulating it with an unsafe delete/reupload sequence.

## Search and answer

Use `files.py list --keyword` only to locate a filename. For knowledge/content search, run `query.py ask` with a complete question. Wait for the terminal result and distinguish:

- `complete`: answer supported by sufficient evidence;
- `insufficient_evidence`: related evidence exists but is incomplete;
- `not_found`: no verifiable answer in the bound knowledge base.

When presenting evidence, include only verified citations. A local PDF filename helps provenance but is not automatically a public link.

## Delete

Deleting a file is permanent. Confirm the exact document name and ID with the user, then pass `--yes`. Directory deletion is allowed only when it has no child directories or files; it is never recursive.

## Update this skill

Run `scripts/check_version.py --force`. If a newer release exists, explain that update behavior depends on installation method:

- Git installation: from the Skill repository, inspect local changes and run `git pull --ff-only` only after the user asks to update.
- Platform/package installation: use that platform's reinstall or update mechanism.
- Never silently update, discard local changes, or run destructive Git commands.


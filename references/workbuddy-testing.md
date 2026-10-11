# WorkBuddy installation and acceptance testing

## Install the exact package

1. In WorkBuddy, open Skills, then Add Skill → Upload Skill. Import the original `adgine-knowledge-v0.1.5.zip` from this release; do not wrap it in another ZIP. The archive root contains `SKILL.md`.
2. Confirm Adgine Knowledge is enabled. Ask WorkBuddy to locate the installed Skill directory, read its `VERSION` and report `0.1.5`. It should also read the installed `SKILL.md`, not a stale repository copy. Disable an older duplicate if it is still enabled.
3. Check that a Python 3 runtime is available. Prefer Python 3.9 or later; on Windows the command may be `python` or `py -3` rather than `python3`.
4. Configure the installed copy for a dedicated test Skill KB. Its key needs `files:read`, `files:write`, and `query:execute`; deletion tests additionally need `files:delete`. The default endpoint is production, so choose the test KB carefully. Use `setup.py` in a local interactive terminal to enter the key without putting it in chat, or provide it through the host's environment. Pass `--base-url` only for an administrator-provided alternative environment.

```bash
python3 <installed-skill-root>/setup.py
python3 <installed-skill-root>/scripts/check_auth.py
```

The Skill's `.env` is not included in the package. When importing an update, check whether the installed configuration was preserved; reconfigure if needed. Never copy a configured `.env` into a release archive. GitHub releases and WorkBuddy marketplace publication are separate: a GitHub release provides the ZIP for local installation; public WorkBuddy listing requires submission through its Open Platform.

Official references: [WorkBuddy local installation](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market), [WorkBuddy Skill format](https://open.workbuddy.cn/docs/skill).

## Prepare test files

Use a PNG with distinctive product information and an HTML file containing a unique Chinese sentence. For the first preview test, make the HTML self-contained with inline CSS and no external scripts or resources. Record their local SHA256 values before upload using the host's hashing tool (macOS: `shasum -a 256`; Windows PowerShell: `Get-FileHash -Algorithm SHA256`).

Use a fresh task workspace and output filenames for this test. Record returned document IDs; subsequent commands should use those IDs rather than guess based on filenames.

## Natural-language acceptance cases

| Request to WorkBuddy | Required observation |
|---|---|
| 把这张 PNG 上传到 Adgine 知识库，等待入库完成，记录文档 ID。 | `upload` succeeds and the document/snapshot become ready; report per-item errors honestly. |
| 从 Adgine 知识库下载刚才的图片到当前工作目录并展示。 | `download`, local path, byte count and SHA256; actual image display when the host supports it. |
| 把这个 HTML 上传到 Adgine 知识库，记录文档 ID。 | HTML is accepted; distinguish saved/pending from ready. |
| 下载刚才的 HTML 原文件，核对与上传前的 SHA256。 | Original HTML, same bytes/checksum, not Markdown renamed to `.html`. |
| 读取这个 HTML 的正文，找到其中的中文测试句。 | `content` returns Canonical Markdown containing the sentence. |
| 预览刚才下载的 HTML 页面。 | Host viewer/browser actually opens it, or reports preview unavailable separately from download success. |
| 查询图片中的产品信息，同时展示相关图片。 | `ask --include-images --json`; read `query.images`, display only returned URLs, report an empty array without fabricating assets. |
| 再次下载到刚才相同的路径，不覆盖。 | Existing file remains unchanged; no silent `--force`. |

An API may legitimately return no related images. First confirm the query asks about distinctive ingested image content; do not treat an empty `images` array as proof of a Skill bug. If images are returned, test both CLI plain text and `--json` output to ensure they are retained. A file path in text alone does not prove the host displayed the picture or HTML.

## CLI diagnosis

```bash
python3 <installed-skill-root>/scripts/files.py status '<document-id>' --json
python3 <installed-skill-root>/scripts/files.py download '<image-document-id>' --output './downloads/product.png' --json
python3 <installed-skill-root>/scripts/files.py download '<html-document-id>' --output './downloads/page.html' --json
python3 <installed-skill-root>/scripts/files.py content '<html-document-id>' --output './downloads/page.md' --json
python3 <installed-skill-root>/scripts/query.py ask --query '<question-about-the-test-product>' --include-images --json
```

If ingestion fails, use `files.py metadata` and `history`. If downloads fail, retain the previous output and inspect the reported status. Record WorkBuddy version, installed Skill version, endpoint, document/query IDs and preview outcome when reporting a problem. Exclude API keys and Authorization headers.

# Adgine Knowledge Skill

Adgine Knowledge 是面向 OpenClaw、WorkBuddy 及其他兼容 `SKILL.md` 的 Agent 的通用知识库 Skill。用户可以在自然语言对话中触发 Agent，把聊天内容或文件保存到指定的 Adgine 知识库，也可以浏览、读取、更新、删除和检索其中的数据。

常见触发方式：

- “把上面的聊天整理成文档存到 Adgine 知识库。”
- “上传这个 PDF 到 Adgine Wiki 的产品资料目录。”
- “Adgine KB 里有哪些文件？”
- “查询 Adgine 知识库：标准版适合哪些客户？”
- “用这个新版 PDF 替换知识库里的旧版本。”
- “从 Adgine 知识库下载这张图片并展示。”
- “下载知识库中的 HTML 原文件，并预览页面。”

## 能力范围

- 查看当前 API Key 绑定的 Skill 知识库
- 创建、重命名、删除空目录
- 上传单个或多个文件并等待异步入库
- 原样保留 UTF-8 中文及其他 Unicode 文件名
- 查询文件列表、状态、Markdown、元数据和处理历史
- 下载原文件、并发安全地追加或全量修改 Canonical Markdown、上传可审计的新版本
- 永久删除文件（强制显式确认）
- 发起并轮询 Pi Agent 知识查询
- 非阻断式版本检查和升级提示

知识库由 IndustryKB 管理后台预先创建。每个 `skkb_` API Key 只访问它绑定的知识库，因此调用时不传 `user-id`、`project-id` 或 `knowledge-base-id`。

## 安装

将本仓库以 Git 或本地目录方式安装到支持 Agent Skills 的客户端。仓库根目录就是 Skill 根目录，必须保留 `SKILL.md`、`scripts/` 和 `references/` 的相对结构。

可以直接把下面这句话发送给 WorkBuddy、OpenClaw、Codex 或其他支持 Git Skill 安装的 Agent：

```text
Install the skill from https://github.com/adgine-ai/adgine-knowledge-skill
```

也可以手动安装：

```bash
git clone https://github.com/adgine-ai/adgine-knowledge-skill.git
cd adgine-knowledge-skill
```

安装后配置：

```bash
python3 setup.py --key 'skkb_xxxxxxxxxxxxxxxxx'
```

当前默认地址是生产环境 `https://industry.adgine.ai`，因此只配置 API Key 即可：

```bash
python3 setup.py --key 'skkb_xxxxxxxxxxxxxxxxx'
```

只有管理员明确提供了其他环境地址时才需要额外传入 `--base-url`。

配置保存在仓库根目录的 `.env`，文件权限会设为仅当前用户可读写。也可以不创建文件，直接提供环境变量：

```text
ADGINE_KNOWLEDGE_API_KEY=skkb_...
ADGINE_KNOWLEDGE_BASE_URL=https://industry.adgine.ai
```

不要把 `.env`、API Key 或完整鉴权 Header 发到聊天、日志或 Git。

## 命令行快速验证

```bash
python3 scripts/check_auth.py
python3 scripts/knowledge_base.py info
python3 scripts/files.py list --page 1 --page-size 20
python3 scripts/files.py append-markdown '<document-id>' --file './addition.md' --wait
python3 scripts/query.py ask --query '知识库中有哪些产品事实？'
```

原件下载与正文读取示例：

```bash
python3 scripts/files.py download '<image-document-id>' --output './downloads/product.png' --json
python3 scripts/files.py download '<html-document-id>' --output './downloads/page.html' --json
python3 scripts/files.py content '<html-document-id>' --output './downloads/page.md' --json
python3 scripts/query.py ask --query '有哪些相关产品图片？' --include-images --json
```

`download` 保留服务端存储的文件字节，返回本地绝对路径、文件名、大小和 SHA256；`content` 返回用于检索的 Markdown。图片展示和 HTML 预览由宿主能力完成，下载脚本不会自动打开文件。图片查询的 `ask --json` 结果在 `query.images`，`status --json` 的结果在 `images`；普通输出也会列出返回的图片地址。下载接口需要鉴权，不能当作公开分享链接。

WorkBuddy 可通过“技能 → 添加技能 → 上传技能”导入发布的 ZIP。安装后应配置实际安装目录中的 Skill，并确认版本为 `0.1.5`。完整的配置、测试指令和验收标准见 [WorkBuddy 安装与验收](references/workbuddy-testing.md)。

查看命令帮助：

```bash
python3 scripts/files.py --help
python3 scripts/query.py --help
```

## 更新

Skill 会低频、非阻断地读取远程 `VERSION`。发现新版本时只提示，不会自行修改本地代码。Git 安装可在仓库目录执行 `git pull --ff-only`；平台包安装应使用平台的重新安装或更新能力。

可通过 `ADGINE_KNOWLEDGE_VERSION_URL` 指定实际发布仓库的远程 `VERSION` 地址。网络失败不会影响任何知识库操作。

维护者修改根目录的 `VERSION` 并推送到 `main` 后，GitHub Actions 会先运行测试，再创建 `v<version>` Release，同时附加以下两个内容相同、扩展名不同的安装包：

- `adgine-knowledge-v<version>.skill`：适合识别 Agent Skill 包的平台；
- `adgine-knowledge-v<version>.zip`：通用 ZIP 安装或人工检查。

`.skill` 本质也是 ZIP 文件。普通代码推送不会重复发版；只有 `VERSION` 变化，或者维护者手动运行 Release workflow 时才会触发。

当前版本 `0.1.5` 补齐图片/HTML 的使用流程、图片查询输出和原件下载校验。发布前运行全部测试并构建安装包，先在 WorkBuddy 导入本地 ZIP 验收，再将包含 `VERSION` 变更的提交推送到 `main`。打包时会校验 `SKILL.md` 的 WorkBuddy 发布字段及其版本与 `VERSION` 一致；包中不包含 `.env`、`.env.*`（保留 `.env.example`）或 `.DS_Store`。GitHub Release 不会自动上架 WorkBuddy 公共技能市场。

## 开发校验

本项目只依赖 Python 3 标准库，建议 Python 3.9 及以上：

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q scripts setup.py
```

## 人员、时间与目录过滤（0.1.6）

查看可用人员身份和目录：

```bash
python3 scripts/knowledge_base.py query-filters --json
```

完整汇总唐立兴 2026 年第 41 周的原始工作资料：

```bash
python3 scripts/query.py ask --query "按项目汇总已完成工作、问题和下一步计划" \
  --employee-name "唐立兴" --date-from 2026-10-05 --date-to-exclusive 2026-10-12 \
  --record-kind work_record --record-kind agent_history --record-kind operation_record \
  --mode summarize --max-sources 50 --json
```

也支持 `--employee-id`、`--directory-id`、`--directory-path`、`--document-id`、`--report-type`、`--scope`、`--variant`、`--origin`、`--mime-type`、`--filename-keyword` 和 `--filters-file`。
日期为业务日期，截止日期不包含；目录默认包含子目录。启用过滤时默认排除标明的测试资料、选择同类正式报告的最新修订。首次部署服务端需执行 SQL 迁移并重建 Skill KB 的派生快照，无须重跑 OCR。

请阅读 [过滤查询约定](references/query-filters.md)。

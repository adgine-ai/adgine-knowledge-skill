# Adgine Knowledge Skill

Adgine Knowledge 是面向 OpenClaw、WorkBuddy 及其他兼容 `SKILL.md` 的 Agent 的通用知识库 Skill。用户可以在自然语言对话中触发 Agent，把聊天内容或文件保存到指定的 Adgine 知识库，也可以浏览、读取、更新、删除和检索其中的数据。

常见触发方式：

- “把上面的聊天整理成文档存到 Adgine 知识库。”
- “上传这个 PDF 到 Adgine Wiki 的产品资料目录。”
- “Adgine KB 里有哪些文件？”
- “查询 Adgine 知识库：标准版适合哪些客户？”
- “用这个新版 PDF 替换知识库里的旧版本。”

## 能力范围

- 查看当前 API Key 绑定的 Skill 知识库
- 创建、重命名、删除空目录
- 上传单个或多个文件并等待异步入库
- 原样保留 UTF-8 中文及其他 Unicode 文件名
- 查询文件列表、状态、Markdown、元数据和处理历史
- 下载原文件、修改 Canonical Markdown、上传可审计的新版本
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

当前默认地址就是 Test 环境 `https://industry.afrgame.dev:31000`，因此只配置 API Key 即可：

```bash
python3 setup.py --key 'skkb_xxxxxxxxxxxxxxxxx'
```

只有管理员提供了其他环境地址时才需要额外传入 `--base-url`。

配置保存在仓库根目录的 `.env`，文件权限会设为仅当前用户可读写。也可以不创建文件，直接提供环境变量：

```text
ADGINE_KNOWLEDGE_API_KEY=skkb_...
ADGINE_KNOWLEDGE_BASE_URL=https://industry.afrgame.dev:31000
```

不要把 `.env`、API Key 或完整鉴权 Header 发到聊天、日志或 Git。

## 命令行快速验证

```bash
python3 scripts/check_auth.py
python3 scripts/knowledge_base.py info
python3 scripts/files.py list --page 1 --page-size 20
python3 scripts/query.py ask --query '知识库中有哪些产品事实？'
```

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

## 开发校验

本项目只依赖 Python 3 标准库，建议 Python 3.9 及以上：

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q scripts setup.py
```

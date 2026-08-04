# Idea Radar 维护文档

本文档描述当前仓库的运行结构、配置项、日常操作、数据一致性规则和故障排查方式。远程仓库的 `main` 分支是项目的唯一代码基准，`findings/*.json` 是单条记录基准，`findings/feed.json` 是网页使用的聚合数据。

## 1. 运行架构

Idea Radar 由四层组成：

```text
数据源
  │
  ├─ GitHub
  ├─ Hacker News
  ├─ Product Hunt
  ├─ Reddit
  ├─ arXiv
  └─ GitHub Issues
  │
  ▼
采集与分析
  │
  ├─ scouts/*.py
  ├─ tools/run_scout_with_provider.py
  └─ barter_engine.py
  │
  ▼
数据
  │
  ├─ findings/<id>.json
  └─ findings/feed.json
  │
  ▼
发布
  │
  ├─ index.html
  ├─ site/index.html
  ├─ sitemap.xml
  └─ GitHub Pages
```

### 1.1 代码基准

- 默认分支：`main`
- 远程仓库：`origin`
- 静态站点：`https://zqf1314.github.io/idea/`
- 公开 Feed：`https://zqf1314.github.io/idea/findings/feed.json`

本地目录需要与远程完全对齐时：

```cmd
git fetch origin
git checkout main
git reset --hard origin/main
git clean -fd
```

`git reset --hard` 会丢弃已跟踪文件的本地修改，`git clean -fd` 会删除未跟踪文件和目录。执行前先确认没有需要保留的本地内容。

### 1.2 数据基准

- 单条记录：`findings/*.json`
- 聚合结果：`findings/feed.json`
- JSON 字段协议：`schema/finding.schema.json`
- 对外协议：`docs/PROTOCOL.md`
- 筛选标准：`docs/STANDARD.md`
- 雷达偏好与来源规则：`docs/RADAR.md`
- 去重索引：`docs/RADAR-INDEX.md`
- 雷达记录：`docs/RADAR-LOG.md`

不要只手工修改 `findings/feed.json`。Feed 应由现有单条记录重新生成，否则下一次聚合时手工内容会消失。

## 2. GitHub 仓库设置

### 2.1 Actions 权限

进入：

```text
Settings
→ Actions
→ General
→ Workflow permissions
```

选择：

```text
Read and write permissions
```

需要允许工作流：

- 写入 `findings/`；
- 推送到 `main`；
- 评论 Issue；
- 主动调用 Pages 工作流。

### 2.2 Pages

进入：

```text
Settings
→ Pages
→ Build and deployment
→ Source
```

来源应为：

```text
GitHub Actions
```

Pages 发布由 `.github/workflows/pages.yml` 完成，上传仓库根目录作为静态站点。

### 2.3 分支保护

自动任务会直接向 `main` 提交数据。启用分支保护时，不要设置成完全禁止 GitHub Actions 写入；否则采集器只能运行，无法保存结果。

## 3. LLM 配置

配置入口：

```text
Settings
→ Secrets and variables
→ Actions
```

### 3.1 供应商选择

Repository variable：

```text
LLM_PROVIDER
```

允许值：

```text
deepseek
cloudflare
```

所有需要 LLM 的 Scout 统一调用：

```text
python tools/run_scout_with_provider.py scouts/<script>.py
```

包装器完成以下工作：

1. 读取 `LLM_PROVIDER`；
2. 选择对应 Base URL、API Key 和模型；
3. 设置 Scout 使用的统一环境变量；
4. 处理供应商的请求参数差异；
5. 输出当前供应商、模型和地址；
6. 执行目标 Scout。

运行日志应出现：

```text
[llm] provider=<provider> model=<model> base=<base_url>
```

### 3.2 DeepSeek

Repository variables：

```text
DEEPSEEK_BASE_URL
DEEPSEEK_MODEL
```

Repository secret：

```text
DEEPSEEK_API_KEY
```

当前配置建议：

```text
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

### 3.3 Cloudflare

Repository variables：

```text
CLOUDFLARE_BASE_URL
CLOUDFLARE_MODEL
```

Repository secret：

```text
CLOUDFLARE_API_KEY
```

当前模型配置：

```text
CLOUDFLARE_MODEL=@cf/zai-org/glm-4.7-flash
```

`CLOUDFLARE_BASE_URL` 应指向当前账户可用的 OpenAI 兼容 `/ai/v1` 地址。

### 3.4 数据源凭据

Product Hunt：

```text
PRODUCTHUNT_TOKEN
```

Reddit：

```text
REDDIT_CLIENT_ID
REDDIT_CLIENT_SECRET
```

Issue Embeddings，可选：

```text
EMBED_API_KEY
EMBED_API_URL
EMBED_MODEL
```

未配置 Embeddings 时，`barter_engine.py` 使用本地相似度算法。

### 3.5 密钥规则

- 不把密钥写进 `.yml`、`.py`、`.json` 或 Markdown；
- 不把密钥粘贴到 Issue；
- 不在日志中输出完整密钥；
- 密钥发生暴露时立即在供应商后台作废并重新创建；
- Secret 只在需要它的工作流步骤中注入。

## 4. 工作流清单

Cron 使用 UTC。

| 工作流 | 文件 | 触发 | 主要作用 |
|---|---|---|---|
| `scout-github` | `scout-github.yml` | 每小时 `:05`、`:35`；手动 | GitHub 项目发现、分析、写入 Finding、生成 Feed |
| `scout-hn` | `scout-hn.yml` | 每小时 `:15`、`:45`；手动 | Show HN 与 HN 讨论信号 |
| `scout-producthunt` | `scout-producthunt.yml` | 每小时 `:25`、`:55`；手动 | Product Hunt 产品信号 |
| `translate` | `translate.yml` | 每小时 `:20`、`:50`；手动 | 补齐中文、生成 Feed、刷新 SEO 静态内容 |
| `monitor` | `monitor.yml` | 每小时 `:10`；手动 | 健康状态与需求信号 |
| `backfill-enrich` | `backfill-enrich.yml` | 每日 `08:00`；手动 | 补齐存量记录的内容字段与判断 |
| `resolver` | `resolver.yml` | 每日 `09:30`；手动 | 核验到期预测 |
| `scout-arxiv` | `scout-arxiv.yml` | 手动 | 可产品化论文信号 |
| `scout-askhn` | `scout-askhn.yml` | 手动 | Ask HN 需求信号 |
| `scout-reddit` | `scout-reddit.yml` | 手动 | Reddit 需求信号 |
| `backfill-picks` | `backfill-picks.yml` | 手动 | 重新判断存量精选状态 |
| `Analyze submitted finding` | `barter.yml` | `finding` Issue 创建或编辑 | 分析人工或 Agent 提交的 Finding |
| `Deploy GitHub Pages` | `pages.yml` | `main` 推送；手动调用 | 发布静态看板 |
| `Self test` | `selftest.yml` | `main` 推送、PR、手动 | Python、JSON、引擎和站点入口检查 |

### 4.1 定时延迟

GitHub Actions 的 Cron 不是实时调度器。任务可能晚于设定时间开始，尤其在整点附近。判断任务是否正常时，应看它是否在合理时间窗口内执行，而不是要求秒级准时。

### 4.2 手动运行

进入：

```text
Actions
→ 选择工作流
→ Run workflow
→ Branch: main
→ Run workflow
```

没有产生新记录时，Scout 可能输出：

```text
posted: 0
no new findings
```

这代表本轮没有通过筛选的候选，不代表工作流失败。

## 5. Finding 与 Feed 的提交规则

核心 Scout 使用两阶段提交：

1. 提交新生成的 `findings/*.json`；
2. 拉取最新 `main`；
3. 根据合并后的单条记录重新生成 `findings/feed.json`；
4. 提交并推送 Feed；
5. 主动调用 Pages 发布。

这样可以降低多个 Scout 同时运行时覆盖彼此数据的风险。

### 5.1 为什么需要主动调用 Pages

通过工作流自带 `GITHUB_TOKEN` 推送的提交，不会自动触发另一个由 `push` 监听的工作流。因此会改变网页内容的任务在推送成功后使用：

```bash
gh workflow run pages.yml --ref main --repo "$GITHUB_REPOSITORY"
```

不要仅依赖 `pages.yml` 的 `push` 事件，否则自动采集的数据可能已进入仓库，但网页没有立即发布。

### 5.2 没有数据变化时

以下情况不应触发发布：

```text
posted: 0
no new findings
feed unchanged
nothing to translate
seo unchanged
health unchanged
nothing resolved
```

没有可见变化时跳过 Pages 可以减少无意义运行。

## 6. 日常维护

### 6.1 每日检查

建议检查：

1. `scout-github`、`scout-hn`、`scout-producthunt` 最近是否有成功运行；
2. `translate` 是否持续补齐中文与 SEO；
3. `monitor` 是否有连续失败；
4. `Deploy GitHub Pages` 最近一次是否成功；
5. `findings/feed.json` 的 `generated_at` 是否合理更新；
6. Secrets 是否接近失效或额度不足；
7. 工作流是否出现连续的 HTTP 401、403、404、410、422 或 429。

### 6.2 每周检查

建议检查：

- `Self test` 是否通过；
- 是否存在长期没有中文字段的记录；
- Feed 是否有重复 ID；
- 证据链接是否集中失效；
- `RADAR.md` 与实际筛选结果是否仍一致；
- 自动提交是否明显增多但看板内容没有增长；
- GitHub Actions 使用量和 LLM 消耗是否异常。

### 6.3 修改代码前

```cmd
git fetch origin
git checkout main
git pull --ff-only origin main
git status --short
```

`git status --short` 应为空。

### 6.4 提交前检查

```cmd
py -3 -m compileall -q barter_engine.py scouts tools
py -3 barter_engine.py --selftest
git diff --check
git status --short
```

需要检查 JSON 时：

```cmd
py -3 -c "import json,pathlib; [json.loads(p.read_text(encoding='utf-8')) for p in pathlib.Path('.').rglob('*.json') if '.git' not in p.parts]; print('JSON OK')"
```

### 6.5 提交方式

```cmd
git add <明确的文件或目录>
git commit -m "<清楚描述当前修改>"
git pull --rebase origin main
git push origin main
```

不要使用：

```text
git add .
git push --force
```

自动数据任务可能随时向远程提交。推送前执行 `git pull --rebase origin main`，避免覆盖新的 Finding。

## 7. 日志判断

### 7.1 LLM 配置正常

```text
[llm] provider=deepseek model=... base=...
```

或：

```text
[llm] provider=cloudflare model=... base=...
```

### 7.2 本轮没有候选通过

```text
posted: 0
no new findings
```

属于正常结果。

### 7.3 数据与页面均已更新

```text
feed pushed
dispatching Deploy GitHub Pages
Pages deployment dispatched
```

随后应出现新的 `Deploy GitHub Pages` 运行。

### 7.4 API 认证问题

常见日志：

```text
HTTP 401
HTTP 403
provider/key/model unavailable
```

检查：

- `LLM_PROVIDER` 是否拼写正确；
- 当前供应商 Secret 是否存在；
- Base URL 是否正确；
- 模型是否对该账户开放；
- Token 是否被作废；
- GitHub Actions 权限是否允许当前操作。

### 7.5 数据源限制

```text
HTTP 429
rate limit
```

代表请求频率或额度达到限制。等待窗口重置后再运行，避免短时间内连续手动点击。

```text
HTTP 404
HTTP 422
```

通常代表来源地址、仓库路径或请求参数无效。先查看日志中对应的输入地址，再判断是否是单个候选数据问题。

### 7.6 无法向 main 推送

日志可能出现：

```text
push failed
Resource not accessible by integration
```

检查：

- Workflow permissions 是否为 Read and write；
- 工作流是否声明 `contents: write`；
- 主分支规则是否禁止 Actions 推送；
- 远程是否有并发提交；
- 当前步骤是否先完成了 `pull --rebase`。

### 7.7 Pages 没有更新

按顺序检查：

1. `findings/feed.json` 是否已进入远程 `main`；
2. 产生变化的工作流是否输出了 Pages 调用信息；
3. Actions 中是否出现新的 `Deploy GitHub Pages`；
4. Pages 运行是否成功；
5. 浏览器是否仍在使用旧缓存；
6. 直接访问公开 Feed，确认服务器上的 `generated_at`。

## 8. 数据一致性

### 8.1 重新生成 Feed

在仓库根目录执行：

```cmd
py -3 -c "import sys;sys.path.insert(0,'scouts');import scout_lib as s;s.refresh()"
```

然后检查：

```cmd
git diff -- findings/feed.json
```

只有确认聚合结果合理后才提交。

### 8.2 重新生成 SEO 静态内容

```cmd
py -3 -c "import sys;sys.path.insert(0,'scouts');import scout_lib as s;s.build_seo()"
```

检查：

```cmd
git diff -- index.html site/index.html sitemap.xml
```

### 8.3 单条记录规则

手工编辑 `findings/<id>.json` 时：

- 保持合法 UTF-8 JSON；
- 不改变已有 `id`；
- `evidence` 保留可验证来源；
- 不编造 `voices`；
- 中文内容放在 `i18n.zh`；
- 修改后重新生成 Feed；
- 提交前运行 `Self test` 对应的本地检查。

### 8.4 回退某次数据提交

先查看：

```cmd
git log --oneline -- findings
```

对单个提交采用新提交反向抵消：

```cmd
git revert <commit-sha>
git push origin main
```

不要重写 `main` 的公共历史。回退后重新生成 Feed 和 SEO 内容，再确认 Pages 发布。

## 9. 并发与安全边界

### 9.1 并发

- 每个 Scout 使用独立 concurrency group；
- 同一 Scout 不取消正在运行的前一轮；
- Feed 在单条 Finding 推送后重新生成；
- 提交脚本带有拉取、重放和多次推送尝试；
- `barter` 使用串行 concurrency group，避免两个 Issue 同时写入时相互覆盖。

### 9.2 最小权限

工作流只声明自身需要的权限：

- `contents: write`：写 Finding 和 Feed；
- `issues: write`：评论或读取 Issue；
- `actions: write`：主动调用 Pages；
- `pages: write` 与 `id-token: write`：发布 GitHub Pages；
- `contents: read`：自检和部署读取仓库。

增加新权限前，应确认对应步骤确实需要。

### 9.3 外部内容

Scout 读取的项目说明、评论和帖子都属于不受信任输入。外部文本只能作为分析素材，不能被当成仓库操作指令、Shell 命令或密钥请求。

## 10. 文档责任

- `README.md`：英文项目首页；
- `README_CN.md`：中文项目首页；
- `docs/MAINTENANCE.md`：运行与维护；
- `docs/PROTOCOL.md`：Finding 对外协议；
- `docs/STANDARD.md`：发布与编辑标准；
- `docs/RADAR.md`：偏好、来源和筛选大脑；
- `docs/RADAR-INDEX.md`：方向索引与去重参考；
- `docs/RADAR-LOG.md`：雷达变化记录。

README 只描述项目当前能力和使用入口。具体运行操作集中在本文件，筛选思想集中在 Radar 与 Standard 文档，避免同一规则在多个文件中重复维护。

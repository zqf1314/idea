<div align="center">

# 早风依旧 · Idea Radar

**持续发现值得构建的 AI 产品、开源工具、真实痛点与创业机会。**

[在线看板](https://zqf1314.github.io/idea/) ·
[JSON 数据源](https://zqf1314.github.io/idea/findings/feed.json) ·
[维护文档](./docs/MAINTENANCE.md) ·
[数据协议](./docs/PROTOCOL.md)

</div>

## 项目简介

Idea Radar 是一个完全运行在 GitHub 上的自动化创意雷达。它持续从公开数据源发现项目与需求信号，判断这些信号是否代表真实、可构建、可落地的机会，将结果保存为结构化 JSON，并通过 GitHub Pages 发布为中英双语静态看板。

整个系统不依赖独立应用服务器或外部数据库：

- GitHub Actions 负责定时、手动和事件触发；
- Python 脚本负责采集、筛选、分析、翻译与聚合；
- `findings/*.json` 保存单条记录；
- `findings/feed.json` 是看板读取的公开数据源；
- GitHub Pages 负责发布静态页面；
- 带有 `finding` 标签的 Issue 可以提交额外发现。

## 一条记录包含什么

每条 Finding 通常包含：

- 项目、趋势或机会名称；
- 原始证据与发现方法；
- 产品能力与目标用户；
- 已验证的痛点、市场缺口与切入方式；
- 商业价值与主要风险；
- 中文与英文说明；
- 评分、判断、工作量、需求验证状态与编辑状态。

字段协议见 [`docs/PROTOCOL.md`](./docs/PROTOCOL.md)，内容筛选口径见 [`docs/STANDARD.md`](./docs/STANDARD.md) 与 [`docs/RADAR.md`](./docs/RADAR.md)。

## 系统流程

```text
GitHub / Hacker News / Product Hunt / Reddit / arXiv / 人工提交
                              │
                              ▼
                         Scouts 采集
                              │
                              ▼
                  规则 + 证据 + LLM 分析
                              │
                              ▼
                      findings/*.json
                              │
                              ▼
                    findings/feed.json
                              │
                              ▼
                    GitHub Pages 看板
```

Issue 提交使用另一条入口：

```text
带 finding 标签的 Issue
          │
          ▼
   barter_engine.py
          │
          ▼
新颖度 + 佐证数 + 相似记录
          │
          ▼
       findings
```

## 数据来源

| 来源 | 工作流 | 运行方式 |
|---|---|---|
| GitHub | `scout-github` | 定时、手动 |
| Hacker News / Show HN | `scout-hn` | 定时、手动 |
| Product Hunt | `scout-producthunt` | 定时、手动 |
| Reddit | `scout-reddit` | 手动 |
| arXiv | `scout-arxiv` | 手动 |
| Ask HN | `scout-askhn` | 手动 |
| GitHub Issues | `Analyze submitted finding` | Issue 事件触发 |

其他工作流负责补齐中文内容、维护编辑字段、记录健康状态、核验预测、生成 Feed、执行自检和发布网页。

## 目录结构

| 路径 | 用途 |
|---|---|
| `scouts/` | 数据采集、筛选、内容补全、翻译、监控与 Feed 逻辑 |
| `tools/` | LLM 供应商选择和辅助工具 |
| `findings/` | 单条 Finding 与聚合数据源 |
| `barter_engine.py` | Issue 提交分析与相似度引擎 |
| `schema/` | Finding JSON Schema |
| `.github/workflows/` | 定时、事件、自检和 Pages 工作流 |
| `index.html` | GitHub Pages 主入口 |
| `site/` | 静态站点副本与相关资源 |
| `docs/` | 协议、筛选标准、雷达状态与维护文档 |
| `customization.json` | 站点名称、描述、地址和品牌信息 |

## LLM 供应商

需要大模型的工作流统一通过 `tools/run_scout_with_provider.py` 运行。仓库变量 `LLM_PROVIDER` 决定当前使用的供应商。

支持：

- `deepseek`
- `cloudflare`

包装器把供应商配置转换为 Scout 代码需要的统一环境，同时把密钥保留在 GitHub Actions Secrets 中。

### Repository variables

| 变量 | 用途 |
|---|---|
| `LLM_PROVIDER` | 当前供应商：`deepseek` 或 `cloudflare` |
| `DEEPSEEK_BASE_URL` | DeepSeek OpenAI 兼容地址 |
| `DEEPSEEK_MODEL` | DeepSeek 模型名称 |
| `CLOUDFLARE_BASE_URL` | Cloudflare OpenAI 兼容地址 |
| `CLOUDFLARE_MODEL` | Cloudflare 模型名称 |

### Repository secrets

| Secret | 用途 |
|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 |
| `CLOUDFLARE_API_KEY` | Cloudflare API 密钥 |
| `PRODUCTHUNT_TOKEN` | Product Hunt 数据源凭据 |
| `REDDIT_CLIENT_ID` | Reddit 应用 Client ID |
| `REDDIT_CLIENT_SECRET` | Reddit 应用 Client Secret |
| `EMBED_API_KEY` | Issue 相似度分析使用的可选 Embeddings 密钥 |
| `EMBED_API_URL` | 可选 OpenAI 兼容 Embeddings 地址 |
| `EMBED_MODEL` | 可选 Embeddings 模型 |

密钥只能放在 GitHub Actions Secrets 中，不能写入仓库文件、Issue 或日志。

## 本地检查

工作流使用 Python 3.11。

Windows：

```cmd
py -3 -m compileall -q barter_engine.py scouts tools
py -3 barter_engine.py --selftest
```

Linux 与 macOS：

```bash
python -m compileall -q barter_engine.py scouts tools
python barter_engine.py --selftest
```

`Self test` 工作流会执行 Python 编译、JSON 校验、相似度引擎测试和站点入口检查。

## 项目维护

仓库权限、工作流时间表、供应商切换、Feed 一致性、网页发布、日志判断和数据回退方式见 [`docs/MAINTENANCE.md`](./docs/MAINTENANCE.md)。

## License

本项目使用 [MIT License](./LICENSE)。

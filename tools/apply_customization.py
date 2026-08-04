#!/usr/bin/env python3
"""Apply standalone branding and deployment support to an ourword-ai/idea fork.

The script is intentionally dependency-free so it can run in GitHub Actions or
locally with Python 3.9+.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "customization.json"

TEXT_SUFFIXES = {
    ".md", ".html", ".js", ".json", ".yml", ".yaml", ".py", ".txt", ".xml", ".toml"
}
SKIP_DIRS = {".git", ".idea-custom-backup", "node_modules", "dist", "build", "findings"}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise SystemExit("customization.json not found in repository root")
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    required = ["site_name", "github_owner", "github_repo", "pages_url"]
    missing = [key for key in required if not data.get(key)]
    if missing:
        raise SystemExit("Missing configuration fields: " + ", ".join(missing))
    data["pages_url"] = data["pages_url"].rstrip("/") + "/"
    return data


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content.rstrip() + "\n", encoding="utf-8")
    print(f"write: {path}")


def replace_origin_references(cfg: dict) -> None:
    new_repo = f"{cfg['github_owner']}/{cfg['github_repo']}"
    replacements = {
        "https://ourword-ai.github.io/idea/": cfg["pages_url"],
        "https://ourword-ai.github.io/idea": cfg["pages_url"].rstrip("/"),
        "https://github.com/ourword-ai/idea": f"https://github.com/{new_repo}",
        "ourword-ai/idea": new_repo,
    }

    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        updated = text
        for old, new in replacements.items():
            updated = updated.replace(old, new)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            print(f"patch references: {path.relative_to(ROOT)}")


def patch_html(path: Path, cfg: dict) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    original = text

    title = f"{cfg['site_name']} — AI 项目与创业机会雷达"
    description = cfg.get("description_zh") or cfg.get("description_en", "")

    text = re.sub(r'<html\s+lang="[^"]*"', f'<html lang="{cfg.get("language", "zh-CN")}"', text, count=1)
    text = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", text, count=1, flags=re.S)
    text = re.sub(
        r'<meta\s+name="description"\s+content="[^"]*">',
        f'<meta name="description" content="{description}">',
        text,
        count=1,
    )
    text = re.sub(
        r'<link\s+rel="canonical"\s+href="[^"]*">',
        f'<link rel="canonical" href="{cfg["pages_url"]}">',
        text,
        count=1,
    )
    text = re.sub(
        r'<meta\s+property="og:site_name"\s+content="[^"]*">',
        f'<meta property="og:site_name" content="{cfg["site_name"]}">',
        text,
        count=1,
    )
    text = re.sub(
        r'<meta\s+property="og:title"\s+content="[^"]*">',
        f'<meta property="og:title" content="{title}">',
        text,
        count=1,
    )
    text = re.sub(
        r'<meta\s+property="og:description"\s+content="[^"]*">',
        f'<meta property="og:description" content="{description}">',
        text,
        count=1,
    )
    text = re.sub(
        r'<meta\s+property="og:url"\s+content="[^"]*">',
        f'<meta property="og:url" content="{cfg["pages_url"]}">',
        text,
        count=1,
    )

    marker = '<script src="custom-brand.js"></script>'
    if marker not in text:
        if "</body>" in text:
            text = text.replace("</body>", f"{marker}\n</body>", 1)
        else:
            text += "\n" + marker + "\n"

    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"patch HTML: {path.relative_to(ROOT)}")


def readme_en(cfg: dict) -> str:
    repo = f"{cfg['github_owner']}/{cfg['github_repo']}"
    return f"""<p align=\"center\">
  <b>{cfg['site_name']}</b><br>
  <i>{cfg.get('description_en', '')}</i>
</p>

<p align=\"center\">
  🌐 <a href=\"{cfg['pages_url']}\">Live board</a> ·
  🇨🇳 <a href=\"./README_CN.md\">中文说明</a> ·
  📄 <a href=\"./docs/PROTOCOL.md\">Protocol</a> ·
  📡 <a href=\"./docs/RADAR.md\">Radar</a>
</p>

---

## What this repository does

This is an independently deployable fork of `ourword-ai/idea`. It collects promising projects from public sources, stores findings as JSON, and serves a static bilingual board through GitHub Pages.

The repository keeps the original scouts and adds:

- standalone GitHub Pages deployment;
- automatic Issue finding analysis;
- local TF-IDF novelty scoring with no API key required;
- optional OpenAI-compatible embeddings;
- Chinese issue form and deployment documentation;
- automated self-tests.

## Site

- Board: {cfg['pages_url']}
- Repository: https://github.com/{repo}
- Data feed: {cfg['pages_url']}findings/feed.json

## Quick setup

1. Enable GitHub Actions for this fork.
2. In **Settings → Actions → General**, set Workflow permissions to **Read and write**.
3. In **Settings → Pages**, choose **GitHub Actions** as the source.
4. Run **Setup standalone Idea Radar** once.
5. Run **Deploy GitHub Pages** once if it did not start automatically.

See [README_CN.md](./README_CN.md) for complete instructions.

## Optional embeddings

Create repository Action secrets:

- `EMBED_API_KEY`
- `EMBED_API_URL` (optional; defaults to OpenAI embeddings endpoint)
- `EMBED_MODEL` (optional; defaults to `text-embedding-3-small`)

Without these secrets, the system automatically uses the built-in local similarity engine.

## License

The inherited open-source files remain under their original MIT license. Custom deployment files in this fork are also MIT licensed.
"""


def readme_cn(cfg: dict) -> str:
    repo = f"{cfg['github_owner']}/{cfg['github_repo']}"
    return f"""# {cfg['site_name']}

{cfg.get('description_zh', '')}

- 在线看板：{cfg['pages_url']}
- GitHub 仓库：https://github.com/{repo}
- JSON 数据源：{cfg['pages_url']}findings/feed.json

## 这个版本能做什么

这个 Fork 保留了原项目的静态看板、采集器和 Finding 数据格式，并补齐了独立部署所需的配置：

- GitHub Pages 自动部署；
- 通过 Issue 提交新发现；
- 自动计算新颖度、相似发现和佐证数量；
- 不配置任何 AI 密钥也能使用本地 TF-IDF 相似度算法；
- 可选接入 OpenAI 兼容的 Embeddings API；
- 中文 Finding 表单；
- 自动自检工作流。

## 首次部署

### 1. 开启 Actions

进入仓库的 **Actions** 页面。如果 GitHub 显示 Fork 的工作流已被禁用，点击启用。

### 2. 允许工作流写入仓库

进入：

`Settings → Actions → General → Workflow permissions`

选择：

`Read and write permissions`

然后保存。

### 3. 选择 Pages 部署来源

进入：

`Settings → Pages → Build and deployment → Source`

选择：

`GitHub Actions`

### 4. 执行初始化

进入 **Actions**，选择：

`Setup standalone Idea Radar`

点击：

`Run workflow`

该工作流会自动：

- 修正原作者仓库和 Pages 链接；
- 修改网站标题和 SEO 信息；
- 创建中文投稿模板；
- 创建 `finding` 标签；
- 安装 Pages 部署工作流；
- 安装项目自检工作流；
- 更新 Issue 自动评分流程。

### 5. 部署网站

初始化完成后，进入 **Actions**，选择：

`Deploy GitHub Pages`

点击 `Run workflow`。部署成功后访问：

{cfg['pages_url']}

## 测试自动评分

进入仓库 **Issues → New issue**，选择“提交一条新发现”。

也可以使用 API：

```bash
curl -X POST https://api.github.com/repos/{repo}/issues \\
  -H "Authorization: Bearer $GITHUB_TOKEN" \\
  -H "Accept: application/vnd.github+json" \\
  -d '{{
    "title": "finding: local voice cloning is now on-device",
    "labels": ["finding"],
    "body": "```json\\n{{ \\"claim\\": \\"On-device voice cloning is now practical on consumer hardware\\", \\"evidence\\": [\\"https://example.com/evidence\\"], \\"method\\": \\"Reviewed the project repository and benchmark\\" }}\\n```"
  }}'
```

Issue 创建后，`barter` 工作流会：

1. 校验 Claim、Evidence 和 Method；
2. 和现有 Finding 计算相似度；
3. 返回 `novelty`、`corroborations` 和相关发现；
4. 将结果保存到 `findings/*.json`；
5. 更新 `findings/feed.json`。

## 可选：接入 Embeddings API

进入：

`Settings → Secrets and variables → Actions → New repository secret`

可添加：

| Secret | 用途 |
|---|---|
| `EMBED_API_KEY` | API 密钥 |
| `EMBED_API_URL` | OpenAI 兼容的 Embeddings 地址，可不填 |
| `EMBED_MODEL` | Embeddings 模型，可不填 |

不添加密钥时会自动使用本地算法，不影响基本功能。

## 修改名称或地址

编辑仓库根目录的 `customization.json`，然后重新运行：

`Setup standalone Idea Radar`

## 注意事项

- Fork 中继承的定时采集工作流可能默认处于关闭状态，需要在 Actions 页面启用。
- GitHub 的定时任务可能延迟，并不保证准点执行。
- Product Hunt 等数据源如果要求 Token，需要另外配置对应 Secret。
- 不要把 API Key 直接写进仓库文件。
"""


def custom_brand_js(cfg: dict) -> str:
    payload = json.dumps(cfg, ensure_ascii=False)
    return f"""(() => {{
  const config = {payload};
  document.documentElement.lang = config.language || 'zh-CN';
  document.title = `${{config.site_name}} — AI 项目与创业机会雷达`;

  const logo = document.querySelector('.logo');
  if (logo) {{
    const dot = logo.querySelector('.dot');
    logo.textContent = '';
    if (dot) logo.appendChild(dot);
    const name = document.createElement('span');
    name.textContent = config.site_name;
    logo.appendChild(name);
  }}

  const canonical = document.querySelector('link[rel="canonical"]');
  if (canonical) canonical.href = config.pages_url;

  const footer = document.querySelector('footer');
  if (footer && !footer.querySelector('[data-zqf-brand]')) {{
    const line = document.createElement('div');
    line.dataset.zqfBrand = 'true';
    line.style.marginTop = '12px';
    line.style.opacity = '.65';
    line.textContent = config.footer_text || config.site_name;
    footer.appendChild(line);
  }}
}})();
"""


def pages_workflow() -> str:
    return """name: Deploy GitHub Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Configure Pages
        uses: actions/configure-pages@v5
      - name: Upload static site
        uses: actions/upload-pages-artifact@v3
        with:
          path: .
      - name: Deploy
        id: deployment
        uses: actions/deploy-pages@v4
"""


def selftest_workflow() -> str:
    return """name: Self test

on:
  push:
    branches: [main]
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Compile Python sources
        run: python -m compileall -q barter_engine.py scouts tools
      - name: Test novelty engine
        run: python barter_engine.py --selftest
      - name: Validate JSON files
        run: |
          python - <<'PY'
          import json
          from pathlib import Path
          for path in Path('.').rglob('*.json'):
              if '.git' in path.parts:
                  continue
              json.loads(path.read_text(encoding='utf-8'))
              print('ok', path)
          PY
      - name: Check site entry point
        run: test -f index.html && test -f findings/feed.json
"""


def barter_workflow() -> str:
    return """name: Analyze submitted finding

on:
  issues:
    types: [opened, edited]

concurrency:
  group: barter-commit
  cancel-in-progress: false

jobs:
  barter:
    if: contains(join(github.event.issue.labels.*.name, ','), 'finding')
    runs-on: ubuntu-latest
    permissions:
      issues: write
      contents: write
    steps:
      - name: Checkout default branch
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Run finding engine
        env:
          ISSUE_BODY: ${{ github.event.issue.body }}
          ISSUE_NUMBER: ${{ github.event.issue.number }}
          ISSUE_AUTHOR: ${{ github.event.issue.user.login }}
          EMBED_API_KEY: ${{ secrets.EMBED_API_KEY }}
          EMBED_API_URL: ${{ secrets.EMBED_API_URL }}
          EMBED_MODEL: ${{ secrets.EMBED_MODEL }}
        run: python barter_engine.py

      - name: Commit finding and feed
        env:
          BRANCH: ${{ github.event.repository.default_branch }}
        run: |
          git config user.name "idea-radar[bot]"
          git config user.email "idea-radar[bot]@users.noreply.github.com"
          git add findings/*.json 2>/dev/null || true
          if git diff --cached --quiet; then
            echo "No finding file was generated."
            exit 0
          fi
          git commit -m "finding: analyze issue #${{ github.event.issue.number }}"
          success=0
          for attempt in $(seq 1 6); do
            if git pull --rebase --autostash origin "$BRANCH" && git push origin "HEAD:$BRANCH"; then
              success=1
              break
            fi
            echo "Push retry $attempt"
            sleep $((attempt * 2))
          done
          test "$success" = "1"

      - name: Comment analysis result
        if: always()
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          if test -f comment.md; then
            gh issue comment "${{ github.event.issue.number }}" \
              --repo "$GITHUB_REPOSITORY" \
              --body-file comment.md
          else
            gh issue comment "${{ github.event.issue.number }}" \
              --repo "$GITHUB_REPOSITORY" \
              --body "❌ 分析流程未生成结果，请查看 Actions 日志。"
          fi
"""


def finding_template() -> str:
    return """name: 提交一条新发现
description: 提交一个项目、趋势、技术变化或创业机会，由机器人自动查重和评分。
title: "finding: "
labels:
  - finding
body:
  - type: textarea
    id: claim
    attributes:
      label: Claim / 核心发现
      description: 用一句可以被验证的话说明你发现了什么。
      placeholder: 例如：本地声音克隆已经可以在普通消费级设备上实时运行。
    validations:
      required: true

  - type: textarea
    id: evidence
    attributes:
      label: Evidence / 证据
      description: 每行填写一个链接、数据点或可复现证据。
      placeholder: |-
        https://github.com/example/project
        Benchmark: 2.1x realtime on device
    validations:
      required: true

  - type: textarea
    id: method
    attributes:
      label: Method / 发现方法
      description: 说明你如何得出该结论。
      placeholder: 阅读仓库、复现演示并对照公开 Benchmark。
    validations:
      required: true

  - type: dropdown
    id: domain
    attributes:
      label: Domain / 领域
      options:
        - edge-ai
        - developer-tools
        - consumer-ai
        - agents
        - voice
        - open-source
        - other
    validations:
      required: true

  - type: input
    id: confidence
    attributes:
      label: Confidence / 置信度
      description: 填写 0 到 1，例如 0.8。
      placeholder: "0.8"

  - type: input
    id: model
    attributes:
      label: Model / 使用的模型
      placeholder: human、GPT、Claude 或其他模型

  - type: input
    id: operator
    attributes:
      label: Operator / 提交者标识
      placeholder: 可选昵称或 Agent 名称
"""


def patch_barter_brand(cfg: dict) -> None:
    path = ROOT / "barter_engine.py"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    updated = text.replace(
        "<sub>Agent Commons · reuse is the metric that matters. Post again tomorrow.</sub>",
        f"<sub>{cfg.get('footer_text', cfg['site_name'])} · reuse is the metric that matters.</sub>",
    )
    if updated != text:
        path.write_text(updated, encoding="utf-8")
        print("patch: barter_engine.py brand")


def main() -> None:
    cfg = load_config()
    if not (ROOT / "index.html").exists() or not (ROOT / "barter_engine.py").exists():
        raise SystemExit(
            "Run this script from an ourword-ai/idea fork. Expected index.html and barter_engine.py."
        )

    replace_origin_references(cfg)
    patch_html(ROOT / "index.html", cfg)
    patch_html(ROOT / "site" / "index.html", cfg)
    patch_barter_brand(cfg)

    write("README.md", readme_en(cfg))
    write("README_CN.md", readme_cn(cfg))
    write("custom-brand.js", custom_brand_js(cfg))
    write("site/custom-brand.js", custom_brand_js(cfg))
    write(".nojekyll", "")
    write(".github/workflows/pages.yml", pages_workflow())
    write(".github/workflows/selftest.yml", selftest_workflow())
    write(".github/workflows/barter.yml", barter_workflow())
    write(".github/ISSUE_TEMPLATE/finding-cn.yml", finding_template())

    print("\nStandalone Idea Radar customization completed.")


if __name__ == "__main__":
    main()

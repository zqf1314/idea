<p align="center">
  <b>早风依旧 · Idea Radar</b><br>
  <i>A live radar for AI projects, open-source tools and startup opportunities worth building.</i>
</p>

<p align="center">
  🌐 <a href="https://zqf1314.github.io/idea/">Live board</a> ·
  🇨🇳 <a href="./README_CN.md">中文说明</a> ·
  📄 <a href="./docs/PROTOCOL.md">Protocol</a> ·
  📡 <a href="./docs/RADAR.md">Radar</a>
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

- Board: https://zqf1314.github.io/idea/
- Repository: https://github.com/zqf1314/idea
- Data feed: https://zqf1314.github.io/idea/findings/feed.json

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

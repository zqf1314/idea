
## Overview

Idea Radar continuously discovers public product and demand signals, evaluates whether they represent a useful and buildable opportunity, stores the results as structured JSON, and publishes a bilingual static board through GitHub Pages.

The repository runs entirely on GitHub:

- GitHub Actions schedule and execute the scouts;
- Python scripts collect, filter, enrich, translate, and aggregate findings;
- `findings/*.json` acts as the record store;
- `findings/feed.json` is the board's public data source;
- GitHub Pages serves the static site;
- labeled GitHub Issues provide a second entry point for submitted findings.

No application server or external database is required.

## What a finding contains

A finding can include:

- the project, signal, or opportunity;
- source evidence and discovery method;
- product capability and target user;
- verified pain, market gap, and possible wedge;
- commercial value and key risk;
- bilingual English and Chinese copy;
- score, verdict, workload, demand validation, and editorial status.

The stable field contract is documented in [`docs/PROTOCOL.md`](./docs/PROTOCOL.md). Editorial rules are documented in [`docs/STANDARD.md`](./docs/STANDARD.md) and [`docs/RADAR.md`](./docs/RADAR.md).

## System flow

```text
GitHub / Hacker News / Product Hunt / Reddit / arXiv / submitted Issues
                              |
                              v
                         Scout scripts
                              |
                              v
                 Rules + evidence + LLM analysis
                              |
                              v
                      findings/*.json
                              |
                              v
                    findings/feed.json
                              |
                              v
                     GitHub Pages board
```

Submitted findings follow a separate entry path:

```text
Issue with label "finding"
          |
          v
   barter_engine.py
          |
          v
novelty + corroboration + related findings
          |
          v
       findings
```

## Data sources

| Source | Workflow | Mode |
|---|---|---|
| GitHub | `scout-github` | scheduled and manual |
| Hacker News / Show HN | `scout-hn` | scheduled and manual |
| Product Hunt | `scout-producthunt` | scheduled and manual |
| Reddit | `scout-reddit` | manual |
| arXiv | `scout-arxiv` | manual |
| Ask HN | `scout-askhn` | manual |
| GitHub Issues | `Analyze submitted finding` | event-driven |

Additional workflows maintain translations, editorial fields, health information, prediction results, feed generation, validation, and site publication.

## Repository layout

| Path | Purpose |
|---|---|
| `scouts/` | Collection, filtering, enrichment, translation, monitoring, and feed logic |
| `tools/` | Provider selection and supporting utilities |
| `findings/` | Individual finding records and the aggregated feed |
| `barter_engine.py` | Issue submission analysis and similarity engine |
| `schema/` | Finding JSON Schema |
| `.github/workflows/` | Scheduled, event-driven, test, and Pages workflows |
| `index.html` | Main GitHub Pages entry point |
| `site/` | Static site copy and related assets |
| `docs/` | Protocol, editorial rules, radar state, and operations documentation |
| `customization.json` | Site name, descriptions, URLs, and branding configuration |

## LLM providers

LLM-powered workflows run through `tools/run_scout_with_provider.py`. The selected provider is controlled by the repository variable `LLM_PROVIDER`.

Supported values:

- `deepseek`
- `cloudflare`

The wrapper exposes the selected provider through the environment contract expected by the scout code, while keeping provider keys in GitHub Actions Secrets.

### Repository variables

| Variable | Description |
|---|---|
| `LLM_PROVIDER` | Active provider: `deepseek` or `cloudflare` |
| `DEEPSEEK_BASE_URL` | DeepSeek OpenAI-compatible base URL |
| `DEEPSEEK_MODEL` | DeepSeek model name |
| `CLOUDFLARE_BASE_URL` | Cloudflare OpenAI-compatible base URL |
| `CLOUDFLARE_MODEL` | Cloudflare model name |

### Repository secrets

| Secret | Description |
|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API key |
| `CLOUDFLARE_API_KEY` | Cloudflare API key |
| `PRODUCTHUNT_TOKEN` | Product Hunt access token |
| `REDDIT_CLIENT_ID` | Reddit application client ID |
| `REDDIT_CLIENT_SECRET` | Reddit application client secret |
| `EMBED_API_KEY` | Optional embedding API key for submitted findings |
| `EMBED_API_URL` | Optional OpenAI-compatible embedding endpoint |
| `EMBED_MODEL` | Optional embedding model |

Secrets must remain in GitHub Actions Secrets and must not be written into repository files, Issues, or logs.

## Local validation

Python 3.11 is used by the workflows.

Linux and macOS:

```bash
python -m compileall -q barter_engine.py scouts tools
python barter_engine.py --selftest
```

Windows:

```cmd
py -3 -m compileall -q barter_engine.py scouts tools
py -3 barter_engine.py --selftest
```

The `Self test` workflow performs Python compilation, JSON validation, novelty-engine testing, and site-entry checks.

## Operations

Repository settings, workflow schedules, provider switching, feed consistency, publication behavior, log interpretation, and data rollback procedures are documented in [`docs/MAINTENANCE.md`](./docs/MAINTENANCE.md).

## License

This repository is licensed under the [MIT License](./LICENSE).

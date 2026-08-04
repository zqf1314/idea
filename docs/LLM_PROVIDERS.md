# LLM 供应商切换

本升级支持同时保存 DeepSeek 与 Cloudflare 两套配置，通过一个仓库变量切换。

## Secrets

在 `Settings -> Secrets and variables -> Actions -> Secrets` 添加：

- `DEEPSEEK_API_KEY`
- `CLOUDFLARE_API_KEY`

此前公开过的 Cloudflare Token 必须撤销后重新创建。

## Variables

在 `Settings -> Secrets and variables -> Actions -> Variables` 添加：

```text
LLM_PROVIDER=deepseek
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
CLOUDFLARE_BASE_URL=https://api.cloudflare.com/client/v4/accounts/<ACCOUNT_ID>/ai/v1
CLOUDFLARE_MODEL=@cf/zai-org/glm-4.7-flash
```

切换到 Cloudflare：

```text
LLM_PROVIDER=cloudflare
```

切回 DeepSeek：

```text
LLM_PROVIDER=deepseek
```

旧的 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL` 会作为兼容备用配置读取，确认新配置正常后可以删除。

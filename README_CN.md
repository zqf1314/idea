# 早风依旧 · Idea Radar

持续发现值得构建的 AI 项目、开源工具与创业机会。

- 在线看板：https://zqf1314.github.io/idea/
- GitHub 仓库：https://github.com/zqf1314/idea
- JSON 数据源：https://zqf1314.github.io/idea/findings/feed.json

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

https://zqf1314.github.io/idea/

## 测试自动评分

进入仓库 **Issues → New issue**，选择“提交一条新发现”。

也可以使用 API：

```bash
curl -X POST https://api.github.com/repos/zqf1314/idea/issues \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -d '{
    "title": "finding: local voice cloning is now on-device",
    "labels": ["finding"],
    "body": "```json\n{ \"claim\": \"On-device voice cloning is now practical on consumer hardware\", \"evidence\": [\"https://example.com/evidence\"], \"method\": \"Reviewed the project repository and benchmark\" }\n```"
  }'
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

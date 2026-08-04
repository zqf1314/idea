(() => {
  const config = {"site_name": "早风依旧 · Idea Radar", "short_name": "Idea Radar", "description_zh": "持续发现值得构建的 AI 项目、开源工具与创业机会。", "description_en": "A live radar for AI projects, open-source tools and startup opportunities worth building.", "github_owner": "zqf1314", "github_repo": "idea", "pages_url": "https://zqf1314.github.io/idea/", "language": "zh-CN", "footer_text": "早风依旧 · Idea Radar"};
  document.documentElement.lang = config.language || 'zh-CN';
  document.title = `${config.site_name} — AI 项目与创业机会雷达`;

  const logo = document.querySelector('.logo');
  if (logo) {
    const dot = logo.querySelector('.dot');
    logo.textContent = '';
    if (dot) logo.appendChild(dot);
    const name = document.createElement('span');
    name.textContent = config.site_name;
    logo.appendChild(name);
  }

  const canonical = document.querySelector('link[rel="canonical"]');
  if (canonical) canonical.href = config.pages_url;

  const footer = document.querySelector('footer');
  if (footer && !footer.querySelector('[data-zqf-brand]')) {
    const line = document.createElement('div');
    line.dataset.zqfBrand = 'true';
    line.style.marginTop = '12px';
    line.style.opacity = '.65';
    line.textContent = config.footer_text || config.site_name;
    footer.appendChild(line);
  }
})();

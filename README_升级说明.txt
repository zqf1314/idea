Idea Radar DeepSeek / Cloudflare 直接覆盖升级包

使用方法：
1. 打开本压缩包，进入最外层。
2. 将其中的 .github、tools、docs 和本说明文件复制到你的 idea 项目根目录。
3. Windows 询问是否替换文件时，选择“替换目标中的文件”。
4. 在项目根目录运行：

   py -3 -m py_compile tools\run_scout_with_provider.py
   git diff
   git status
   git add .
   git commit -m "feat: add switchable DeepSeek and Cloudflare providers"
   git push origin main

该包不会覆盖 scouts/scout_lib.py，而是通过独立包装器兼容两个供应商，减少与上游代码冲突。

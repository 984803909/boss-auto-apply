# Boss 直聘投递助手

基于 Python、CustomTkinter 和 Patchright 的 Windows 桌面工具，使用系统 Microsoft Edge。

支持关键词与城市组合搜索、岗位筛选、自定义招呼语、投递记录及停止控制。

> 自动化操作可能违反平台服务条款并导致账号限制。请先阅读平台条款，勿用于骚扰、绕过验证码或规避风控。检测到安全验证时应停止并手动处理。任何投递间隔或数量都不保证账号安全。

## 环境与安装

目标环境：Windows 10/11、Python 3.12、系统 Microsoft Edge。其他系统暂不支持；Edge 页面兼容性仍需按实际版本验证。

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item config.example.yaml config.yaml
.venv\Scripts\python.exe gui.py
```

也可以双击 `run_gui.bat`。无需下载 Chromium，程序直接连接系统 Edge。

## 首次使用

1. 在 `config.yaml` 设置关键词、城市和招呼语，或启动 GUI 后调整并保存配置。
2. 在 GUI 点击启动浏览器，手动打开 Boss 直聘、完成登录并确认搜索页面。
3. 按界面提示开始投递；点击停止后，等待当前操作结束。

程序首次找不到配置时会在程序目录生成默认配置：城市上海、关键词为空、每日上限 30、间隔 60 秒。关键词需要自己添加，否则没有岗位可搜。请先确认符合自己的需求，再开始操作。程序目录必须可写。

命令行用户可先运行 `python login.py` 完成登录，再运行 `python main.py`；也可使用对应的 `run_login.bat`、`run_main.bat`。命令行用 Ctrl+C 停止。

## 配置

完整字段见 [config.example.yaml](config.example.yaml)。

| 字段 | 用途 |
| --- | --- |
| keywords / cities | 搜索关键词列表 / 城市名称与编码 |
| daily_limit / interval_seconds | 每日成功投递上限 / 间隔秒数，均为正整数 |
| greeting | 自定义招呼语 |
| filters.min_salary / max_salary | 月薪上下限，0 表示不限制 |
| filters.skip_communicated | 跳过已沟通岗位 |
| filters.company_blacklist / title_blacklist / category_blacklist | 公司、标题、岗位类别排除 |
| filters.job_type | all、only_parttime、no_parttime |
| filters.activity_levels 等列表 | 招聘者活跃度、经验、学历、区域等筛选 |
| filters.auto_favorite | 投递后是否收藏 |

浏览器启动使用系统 Edge 的可见窗口；`browser.headless` 当前兼容字段不生效。浏览器调试端口使用本机 9222，请避免与其他调试程序冲突。

## 本地数据

- `config.yaml`：个人设置，不提交。
- `data/edge_user_data/`：独立 Edge 资料目录，包含敏感登录态，不提交、不分享。
- `data/applied.csv`：投递记录；`data/category_log.csv`：类别记录。

登录失效后重新手动登录；不使用 `data/state.json`。清除登录态前先停止程序并关闭该 Edge 窗口，然后删除 `data/edge_user_data/`。

## 常见问题

- 找不到 Edge：安装 Microsoft Edge；当前识别标准 Program Files 安装路径。
- 9222 端口未就绪：检查 Edge 安装和端口占用，关闭旧的本工具浏览器后重试。
- 配置格式错误：对照示例检查 YAML 缩进和数值。
- 找不到按钮：平台页面可能已变化，提交脱敏复现步骤，勿上传登录态或个人记录。

## 开发、测试与发布

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m compileall -q app_config.py browser_launcher.py gui.py login.py main.py utils.py tests
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\build.bat
```

离线测试不会连接真实账号或发送消息。GitHub Actions 在 Windows 和 Ubuntu 运行检查，版本标签 `v*` 触发 Windows 打包并创建草稿 Release，供维护者审核后发布。

EXE 首次运行会生成配置和数据目录。打包与发布验证见 [发布清单](OPEN_SOURCE_CHECKLIST.md)；历史检查见 [历史审查](docs/history-audit.md)。

## 作者

<a href="https://github.com/984803909">
  <img src="https://avatars.githubusercontent.com/u/47996740?v=4" width="96" height="96" alt="984803909 的 GitHub 头像">
</a>

由 [@984803909](https://github.com/984803909) 开发和维护。

## 反馈与贡献

欢迎通过下表参与项目：

| 事项 | 方式 | 说明 |
| --- | --- | --- |
| Bug、使用问题、功能建议 | [提交 Issue](https://github.com/984803909/boss-auto-apply/issues) | 请附上 Windows / Python / Edge 版本、复现步骤，以及脱敏后的日志或截图。 |
| 功能改进 | [提交 Pull Request](https://github.com/984803909/boss-auto-apply/pulls) | 请先阅读 [贡献指南](CONTRIBUTING.md)，并说明修改内容和验证方式。 |
| 安全漏洞 | [安全说明](SECURITY.md) | 请私密报告，不要在公开 Issue 中披露漏洞细节。 |

作者目前主要使用 Windows + Microsoft Edge 验证项目，暂时没有充分验证 Google Chrome 或 macOS 环境。如果你需要 Chrome、macOS 或其他平台支持，欢迎提交 Issue 说明需求，也欢迎直接提交 Pull Request 一起完善。请勿上传个人配置、登录态或投递记录。

本项目采用 [MIT License](LICENSE)。

## 赞助与支持

如果项目对你有帮助，欢迎点一个 Star。也可以通过下表支持项目维护：

| 名称 | 类型 | 链接 |
| --- | --- | --- |
| Dulays | AI API 中转服务 | [访问 chaeng.cn](https://www.chaeng.cn/) |

### 微信联系

如需交流项目、反馈问题或讨论合作，可以通过微信联系作者：

<img src="assets/wechat-qr.png" width="240" alt="作者微信二维码">

# 开源发布清单

## 已完成的本地准备

- [x] MIT、贡献指南、行为准则、安全说明和更新记录。
- [x] .gitignore 排除 config.yaml、data/ 与构建产物。config.yaml 仍被 Git 跟踪，忽略规则不会取消已跟踪的文件。
- [x] 首次启动自动创建配置，默认上限 30、间隔 60 秒。
- [x] README 对齐 Windows + 系统 Edge，补充 GUI 与命令行操作。
- [x] 离线配置、薪资、去重、每日计数回归测试。
- [x] Windows / Ubuntu CI，标签触发构建与草稿 Release。
- [x] 历史路径审查及不带历史的源码导出工具。

## 首次公开前的人工验证

- [ ] 用 `python tools/package_source.py` 导出的源码包在新目录初始化公开仓库。不要直接推送现有历史：唯一的提交 b35e2a7 里含 config.yaml 和 build/ 产物（见 docs/history-audit.md）。
- [ ] 本地仓库执行 `git rm --cached config.yaml`，让之后的提交不再跟踪它。这不改已有历史。
- [ ] GitHub 设置中开启 Private vulnerability reporting。
- [ ] 在干净 Windows 环境验证源码和 EXE 的首次启动、配置保存、Edge 启动和停止；当前离线测试不代表真实页面兼容。
- [ ] 补充不包含个人信息的 GUI 截图。
- [ ] 运行托管 CI，确认 Windows 构建成功。
- [ ] 按实际验证结果记录 Windows、Python、Edge 版本。
- [ ] 创建 vX.Y.Z 标签，检查草稿 Release 的 ZIP、SHA256 与版本信息后再公开。

首次导出：`python tools/package_source.py`。发布包为 dist/open-source-source.zip，不包含 .git、config.yaml、data/、旧 EXE 或本地诊断脚本。

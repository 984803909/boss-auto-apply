# 参与贡献

提交问题时附上 Python、Windows、Edge 版本、复现步骤与脱敏日志。较大改动请先通过 Issue 讨论。

安装依赖后运行：

```powershell
python -m unittest discover -s tests -v
python -m compileall -q app_config.py browser_launcher.py gui.py login.py main.py utils.py tests
```

测试使用临时目录，不连接真实账号、不发送真实消息。增加筛选或记录逻辑时补充离线回归测试。

禁止提交 config.yaml、data/、登录态、浏览器用户目录或构建产物。构建依赖见 requirements-dev.txt，发布步骤见 OPEN_SOURCE_CHECKLIST.md。

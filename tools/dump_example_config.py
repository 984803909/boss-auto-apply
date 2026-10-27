"""把 app_config.DEFAULT_CONFIG 写到 config.example.yaml。

默认配置只维护一处。改了 app_config.py 里的默认值后运行本脚本，
仓库里的示例和安装包的初始配置会一起更新。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_config

if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "config.example.yaml"
    target.write_text(app_config.example_config_text(), encoding="utf-8")
    print(target)

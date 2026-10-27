"""把版本号写进 installer.iss 和 version_info.py。

发版时由 CI 用标签名调用：python tools/set_version.py 1.2.3。
两个文件里的版本号只在这里改，不手写。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(version: str) -> None:
    parts = version.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise SystemExit(f"版本号必须是 x.y.z，收到的是 {version!r}")

    iss = ROOT / "installer.iss"
    iss.write_text(re.sub(r'#define AppVersion ".*"', f'#define AppVersion "{version}"',
                          iss.read_text(encoding="utf-8")), encoding="utf-8")

    info = ROOT / "version_info.py"
    text = re.sub(r"u'(FileVersion|ProductVersion)', u'[^']*'",
                  lambda m: f"u'{m.group(1)}', u'{version}.0'",
                  info.read_text(encoding="utf-8"))
    nums = ", ".join(parts + ["0"])
    text = re.sub(r"(file|prod)vers=\([^)]*\)", lambda m: f"{m.group(1)}vers=({nums})", text)
    info.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])

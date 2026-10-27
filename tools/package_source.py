"""Export a clean initial-publication snapshot without private files or Git history."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ".gitignore", "README.md", "LICENSE", "CHANGELOG.md", "SECURITY.md",
    "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "OPEN_SOURCE_CHECKLIST.md",
    "config.example.yaml", "city_data.json", "requirements.txt", "requirements-dev.txt",
    "app_config.py", "browser_launcher.py", "gui.py", "login.py", "main.py",
    "utils.py", "version_info.py", "BossAutoApply.spec", "installer.iss", "build.bat",
    "run_gui.bat", "run_login.bat", "run_main.bat", ".github/workflows/ci.yml",
    "docs/history-audit.md", "docs/boss-city-api.md", "tests/test_offline.py",
    "tools/package_source.py", "tools/dump_example_config.py", "tools/set_version.py",
    "assets/app-icon.ico", "assets/app-icon.png", "assets/app-icon.svg",
]

if __name__ == "__main__":
    output = ROOT / "dist" / "open-source-source.zip"
    output.parent.mkdir(exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(ROOT / name, name)
    print(output)

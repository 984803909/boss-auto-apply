"""Shared configuration loading for source installs and standalone executables."""
from copy import deepcopy
from pathlib import Path

import yaml

# 默认配置是唯一的一份。config.example.yaml 由它生成，不单独维护。
# 关键词是用户自己的搜索习惯，不预置；空列表表示还没选，界面保存时会拦下。
DEFAULT_CONFIG = {
    "keywords": [],
    "cities": {"上海": "101020100"},
    "daily_limit": 30,
    "interval_seconds": 60,
    "greeting": "可以聊聊吗",
    "browser": {"headless": False, "slow_mo": 100},
    "filters": {
        "company_blacklist": [],
        "title_blacklist": [],
        "category_blacklist": [],
        "min_salary": 0,
        "max_salary": 0,
        "job_type": "all",
        "skip_communicated": True,
        "activity_levels": [],
        "experience_levels": [],
        "degree_levels": [],
        "districts": [],
        "scale_levels": [],
        "stage_levels": [],
        "welfare_required": [],
        "tag_blacklist": [],
        "industry_blacklist": [],
        "recruiter_blacklist": [],
        "experience": "",
        "degree": "",
        "salary": "",
        "scale": "",
        "stage": "",
        "jobType": "",
        "auto_favorite": False,
    },
}


def validate_config(cfg: dict) -> dict:
    if not isinstance(cfg, dict):
        raise ValueError("配置内容必须是 YAML 映射")
    for key in ("daily_limit", "interval_seconds"):
        value = cfg.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{key} 必须是正整数")
    if not isinstance(cfg.get("keywords"), list) or any(
        not isinstance(v, str) or not v.strip() for v in cfg["keywords"]
    ):
        raise ValueError("keywords 必须是字符串列表")
    if not isinstance(cfg.get("cities"), dict) or not cfg["cities"] or any(
        not isinstance(k, str) or not k.strip() or not str(v).isdigit()
        for k, v in cfg["cities"].items()
    ):
        raise ValueError("cities 必须包含城市名称和数字编码")
    if not isinstance(cfg.get("filters", {}), dict):
        raise ValueError("filters 必须是 YAML 映射")
    return cfg


def load_config(path: str) -> dict:
    target = Path(path)
    if not target.exists():
        cfg = deepcopy(DEFAULT_CONFIG)
        save_config(path, cfg)
        return cfg
    try:
        cfg = yaml.safe_load(target.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"配置 YAML 格式错误：{exc}") from exc
    if not isinstance(cfg, dict):
        raise ValueError("配置不能为空，且必须是 YAML 映射")
    merged = deepcopy(DEFAULT_CONFIG)
    merged.update(cfg)
    return validate_config(merged)


def save_config(path: str, cfg: dict) -> None:
    validate_config(cfg)
    Path(path).write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")


def example_config_text() -> str:
    """仓库里的 config.example.yaml 和安装包的初始配置都从这里来。"""
    body = yaml.safe_dump(deepcopy(DEFAULT_CONFIG), allow_unicode=True, sort_keys=False)
    return "# 由 app_config.DEFAULT_CONFIG 生成，改默认值改那里，再运行 tools/dump_example_config.py。\n" + body

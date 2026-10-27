"""工具函数：薪资解析、投递记录、日志。"""
from __future__ import annotations

import csv
import json
import os
import sys
import re
from datetime import datetime
from typing import Optional

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(__file__)

APPLIED_CSV = os.path.join(APP_DIR, "data", "applied.csv")
CATEGORY_LOG_CSV = os.path.join(APP_DIR, "data", "category_log.csv")
CITY_JSON = os.path.join(APP_DIR, "data", "city.json")


def _city_json_paths() -> list[str]:
    """城市数据的查找顺序：exe 旁边的 data/，打包进去的副本，随源码发布的副本。

    data/ 整个目录在 gitignore 里，里面的文件不会进仓库也不会进打包，
    所以随代码发布的副本放在 data/ 外面，打包时以 city_data.json 这个名字进包。
    """
    paths = [CITY_JSON]
    bundle = getattr(sys, "_MEIPASS", "")
    if bundle:
        paths.append(os.path.join(bundle, "data", "city.json"))
        paths.append(os.path.join(bundle, "data", "city_data.json"))
    paths.append(os.path.join(os.path.dirname(__file__), "city_data.json"))
    return paths


def load_city_tree() -> list[dict]:
    """读 Boss 城市数据，返回 [{name, province, code, districts: [区名]}]。

    数据来自 zhipin 的 city.json，取城市层（省级节点的下一层），
    编码是搜索用的城市编码，不是行政区划编码。文件缺失或格式不对时返回空。
    """
    data = None
    for path in _city_json_paths():
        if not os.path.exists(path):
            continue
        try:
            data = json.load(open(path, encoding="utf-8"))
            break
        except (OSError, ValueError):
            continue
    if data is None:
        return []
    try:
        provinces = data["zpData"]["cityList"]
    except (KeyError, TypeError):
        return []
    cities = []
    for province in provinces:
        province_name = province.get("name", "")
        for city in province.get("subLevelModelList") or []:
            districts = [d.get("name", "") for d in (city.get("subLevelModelList") or [])
                         if d.get("name")]
            cities.append({"name": city.get("name", ""), "province": province_name,
                           "code": str(city.get("code", "")), "districts": districts})
    return [c for c in cities if c["name"] and c["code"]]


def _parse_salary_range(salary_text: str) -> tuple[Optional[int], Optional[int]]:
    """从 Boss 薪资字符串里提取 (下限, 上限)，单位：元/月。

    支持格式：
      "15-25K"          -> (15000, 25000)
      "15-25K·13薪"     -> (15000, 25000)
      "8-12K"           -> (8000, 12000)
      "4000-5000元/月"  -> (4000, 5000)
      "500-1000元/月"   -> (500, 1000)
      "200-400元/天"    -> None（日薪忽略）
      "面议"            -> (None, None)
    """
    if not salary_text:
        return None, None
    # 1. K 格式：12-15K、12-15K·15薪
    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*[kK]", salary_text)
    if m:
        return int(float(m.group(1)) * 1000), int(float(m.group(2)) * 1000)
    # 2. 元/月 格式：4000-5000元/月
    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*元/月", salary_text)
    if m:
        return int(float(m.group(1))), int(float(m.group(2)))
    return None, None


def parse_salary_lower(salary_text: str) -> Optional[int]:
    """从 Boss 薪资字符串里提取下限（元/月）。"""
    low, _ = _parse_salary_range(salary_text)
    return low


def parse_salary_upper(salary_text: str) -> Optional[int]:
    """从 Boss 薪资字符串里提取上限（元/月）。"""
    _, high = _parse_salary_range(salary_text)
    return high


def ensure_data_dir() -> None:
    os.makedirs(os.path.join(APP_DIR, "data"), exist_ok=True)


def job_key(href: str, company: str = "", title: str = "") -> str:
    """岗位去重键。优先用链接里的职位 ID，没有链接时退回公司名加岗位名。

    同一公司在不同城市、不同招聘者名下会挂同名职位，按名字去重会误伤；
    链接 /job_detail/<id>.html 里的 id 才是这个职位自己的。
    """
    m = re.search(r"/job_detail/([^.?/]+)", href or "")
    if m:
        return "id:" + m.group(1)
    return f"{company}|{title}"


def load_applied_keys() -> set[str]:
    """返回投递成功过的岗位 key 集合，用于跨天去重。

    只算 status 为 success 的记录。超时、验证码、找不到按钮这类失败
    也写在同一个文件里，但那是临时问题，不能因此再也不投这个岗位。
    """
    ensure_data_dir()
    keys: set[str] = set()
    if not os.path.exists(APPLIED_CSV):
        return keys
    with open(APPLIED_CSV, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("status") != "success":
                continue
            keys.add(job_key(row.get("url", ""), row.get("company", ""), row.get("title", "")))
    return keys


def record_applied(title: str, company: str, salary: str, city: str,
                   keyword: str, status: str, url: str = "") -> None:
    ensure_data_dir()
    new_file = not os.path.exists(APPLIED_CSV)
    with open(APPLIED_CSV, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["time", "city", "keyword", "title", "company",
                             "salary", "status", "url"])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                         city, keyword, title, company, salary, status, url])


def record_category(category: str, title: str, company: str, action: str) -> None:
    """记录一次投递时读到的岗位类别。

    每天的投递都会追加到 data/category_log.csv，action 为「已投」或「已排除」。
    之后可以按类别汇总，把混进来的非程序员类别补进排除名单。
    """
    if not category:
        return
    ensure_data_dir()
    new_file = not os.path.exists(CATEGORY_LOG_CSV)
    with open(CATEGORY_LOG_CSV, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["time", "category", "action", "title", "company"])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                         category, action, title, company])


def today_applied_count() -> int:
    """统计今天已投递成功的数量。"""
    if not os.path.exists(APPLIED_CSV):
        return 0
    today = datetime.now().strftime("%Y-%m-%d")
    n = 0
    with open(APPLIED_CSV, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("time", "").startswith(today) and row.get("status") == "success":
                n += 1
    return n


_log_callback = None


def set_log_callback(cb):
    global _log_callback
    _log_callback = cb


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    if _log_callback:
        try:
            _log_callback(line)
        except Exception:
            pass

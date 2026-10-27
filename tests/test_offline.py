import csv
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import app_config
import main
import utils


class ConfigTests(unittest.TestCase):
    def test_first_run_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "config.yaml")
            cfg = app_config.load_config(path)
            self.assertEqual(cfg["daily_limit"], 30)
            cfg["keywords"] = ["测试开发"]
            app_config.save_config(path, cfg)
            self.assertEqual(app_config.load_config(path)["keywords"], ["测试开发"])

    def test_invalid_config_does_not_overwrite(self):
        for text in ("[]", "", "daily_limit: -1", "interval_seconds: true", "keywords: abc", "cities: {}", "filters: []", "a: ["):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "config.yaml"
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    app_config.load_config(str(path))
                self.assertEqual(path.read_text(encoding="utf-8"), text)


class RecordTests(unittest.TestCase):
    def test_salary_units(self):
        for text, expected in (("15-25K·13薪", (15000, 25000)), ("4000-5000元/月", (4000, 5000)), ("200-400元/天", (None, None)), ("面议", (None, None))):
            with self.subTest(text=text):
                self.assertEqual((utils.parse_salary_lower(text), utils.parse_salary_upper(text)), expected)

    def test_records_count_only_success_today_and_dedupe_by_id(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(utils, "APP_DIR", tmp), patch.object(utils, "APPLIED_CSV", str(Path(tmp) / "data" / "applied.csv")):
            self.assertEqual(utils.today_applied_count(), 0)
            url = "https://www.zhipin.com/job_detail/abc.html?source=1"
            utils.record_applied("开发", "公司", "15-25K", "上海", "开发", "success", url)
            utils.record_applied("开发", "公司", "15-25K", "上海", "开发", "failed", "https://www.zhipin.com/job_detail/failed.html")
            with open(utils.APPLIED_CSV, "a", encoding="utf-8", newline="") as f:
                csv.writer(f).writerow(["2000-01-01 12:00:00", "上海", "开发", "开发", "公司", "15K", "success", "https://www.zhipin.com/job_detail/old.html"])
            self.assertEqual(utils.today_applied_count(), 1)
            self.assertEqual(utils.load_applied_keys(), {"id:abc", "id:old"})
            self.assertEqual(utils.job_key(url), utils.job_key(url.replace("source=1", "source=2")))


class FilterTests(unittest.TestCase):
    def test_district_match_requires_city_not_just_district_name(self):
        cfg = {"filters": {"districts": ["北京·朝阳区"]}}
        self.assertIsNone(main.should_skip(
            {"area": "北京·朝阳区·望京", "title": "开发", "company": "甲"}, cfg, set()))
        # 长春也有朝阳区，只比区名会被放进来。
        self.assertIsNotNone(main.should_skip(
            {"area": "长春·朝阳区·桂林路", "title": "开发", "company": "乙"}, cfg, set()))

    def test_blacklist_blocks_when_detail_unreadable(self):
        card = {"title": "开发", "company": "甲", "area": "北京·朝阳区",
                "href": "/job_detail/1.html"}

        class Locator:
            def first(self):
                return self

            def wait_for(self, **kwargs):
                raise main.PWTimeout("no button")

        class Page:
            url = "https://www.zhipin.com/job_detail/1.html"

            def goto(self, *args, **kwargs):
                pass

            def locator(self, selector):
                return Locator()

        context = type("Context", (), {"new_page": lambda self: Page()})()
        with patch.object(main, "extract_category", lambda page: ""), \
             patch.object(main, "extract_activity", lambda page: ""), \
             patch.object(main, "extract_detail", lambda page: {}), \
             patch.object(main, "detect_verify", lambda page: False):
            for key, reason in (("category_blacklist", "skip_category:未读到"),
                                ("industry_blacklist", "skip_industry:未读到"),
                                ("recruiter_blacklist", "skip_recruiter:未读到")):
                with self.subTest(key=key):
                    self.assertEqual(
                        main.apply_one(context, card, {"filters": {key: ["不想要的"]}}, "", ""),
                        reason)


if __name__ == "__main__":
    unittest.main()

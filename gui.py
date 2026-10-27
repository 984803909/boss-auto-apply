"""Boss 直聘自动投递 - 现代化 GUI 界面"""
from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox
import traceback
import yaml

import customtkinter as ctk
from PIL import Image as PILImage

# 获取真实运行目录（支持单文件 exe）
if getattr(sys, 'frozen', False):
    BASE = os.path.dirname(sys.executable)
else:
    BASE = os.path.dirname(os.path.abspath(__file__))

if BASE not in sys.path:
    sys.path.insert(0, BASE)

CONFIG_PATH = os.path.join(BASE, "config.yaml")

from app_config import load_config as read_config, save_config as write_config


def load_config() -> dict:
    return read_config(CONFIG_PATH)


def save_config(cfg: dict) -> None:
    write_config(CONFIG_PATH, cfg)


ctk.set_appearance_mode("System")  # 模式: "System", "Dark", "Light"
ctk.set_default_color_theme("blue")  # 主题: "blue", "green", "dark-blue"

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Boss 直聘自动投递助手")
        self.geometry("1120x800")
        self.minsize(1000, 680)

        # 网格布局权重配置
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._edge_ready_event = threading.Event()

        self._build_ui()
        self._load_config_to_ui()
        # Edge 可能是上次留下的，启动时直接读一次账号，不用等手动点启动。
        threading.Thread(target=self._refresh_account, daemon=True).start()

    def _build_ui(self):
        # Presentation only: variable names and existing commands are preserved.
        surface = ("#FFFFFF", "#17282C")
        muted = ("#63767A", "#A2B7BB")
        self._ink = ink = ("#18383D", "#E4EFF0")
        self._accent = accent = "#087F78"
        self.configure(fg_color=("#EDF3F3", "#102024"))
        self._body_font = body_font = ctk.CTkFont(family="Microsoft YaHei UI", size=13)
        self._select_menu_font = tkfont.Font(root=self, family="Microsoft YaHei UI", size=14)
        heading_font = ctk.CTkFont(family="Microsoft YaHei UI", size=17, weight="bold")
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 20))
        mark = ctk.CTkLabel(header, text="B", width=44, height=44, corner_radius=12,
                            fg_color=accent, text_color="white",
                            font=ctk.CTkFont(family="Segoe UI", size=25, weight="bold"))
        mark.pack(side="left", padx=(0, 14))
        title_group = ctk.CTkFrame(header, fg_color="transparent")
        title_group.pack(side="left")
        ctk.CTkLabel(title_group, text="投递工作台", text_color=ink,
                     font=ctk.CTkFont(family="Microsoft YaHei UI", size=24, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(title_group, text="Boss 直聘  /  自动投递助手", text_color=muted,
                     font=body_font).pack(anchor="w")
        # 登录的 Boss 账号。Edge 起来后从页面导航栏读名字和头像填进来。
        self.account_frame = ctk.CTkFrame(header, fg_color="transparent")
        self.account_frame.pack(side="right", padx=(0, 16))
        self.account_avatar = ctk.CTkLabel(self.account_frame, text="", width=36, height=36,
            corner_radius=18, fg_color=("#DCE8E8", "#294146"))
        self.account_avatar.pack(side="left", padx=(0, 8))
        account_text = ctk.CTkFrame(self.account_frame, fg_color="transparent")
        account_text.pack(side="left")
        self.account_name = ctk.CTkLabel(account_text, text="未登录", text_color=ink,
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=14, weight="bold"))
        self.account_name.pack(anchor="w")
        self.account_state = ctk.CTkLabel(account_text, text="启动浏览器后显示账号", text_color=muted,
            font=body_font)
        self.account_state.pack(anchor="w")

        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(
            header, values=["System", "Dark", "Light"], command=self.change_appearance_mode_event,
            width=112, height=34, fg_color=surface, text_color=ink,
            button_color=("#DCE8E8", "#294146"), button_hover_color=("#C9DCDC", "#36565B"),
            font=body_font, dropdown_font=body_font)
        self.appearance_mode_optionemenu.pack(side="right")
        self.appearance_mode_optionemenu.set("System")

        workspace = ctk.CTkFrame(self, fg_color="transparent")
        workspace.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 24))
        workspace.grid_rowconfigure(0, weight=1)
        workspace.grid_columnconfigure(0, weight=3, minsize=560)
        workspace.grid_columnconfigure(1, weight=2, minsize=360)

        settings = ctk.CTkFrame(workspace, fg_color=surface, corner_radius=16)
        settings.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        settings.grid_columnconfigure(0, weight=1)
        settings.grid_rowconfigure(1, weight=1)
        settings_header = ctk.CTkFrame(settings, fg_color="transparent")
        settings_header.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 8))
        ctk.CTkLabel(settings_header, text="投递偏好", font=heading_font, text_color=ink).pack(side="left")
        ctk.CTkLabel(settings_header, text="按条件找到合适的岗位", font=body_font, text_color=muted).pack(side="right")
        # 下拉面板展开时切走标签页，面板还挂在原处，切回来就是打开状态。
        # 每个下拉注册一个收起函数，切换标签时统一收起。
        self._dropdown_closers = []

        def on_tab_change():
            for close in self._dropdown_closers:
                close()

        tabs = ctk.CTkTabview(settings, fg_color=surface, corner_radius=10,
            command=on_tab_change,
            segmented_button_fg_color=("#EAF1F1", "#20373C"),
            segmented_button_selected_color=accent, segmented_button_selected_hover_color="#096E69",
            segmented_button_unselected_color=("#EAF1F1", "#20373C"),
            segmented_button_unselected_hover_color=("#D9E7E7", "#2B484E"),
            text_color=ink, text_color_disabled=muted)
        tabs.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        pages = {}
        for name in ("基础设置", "岗位筛选", "公司与招聘者", "搜索条件"):
            tab = tabs.add(name)
            tab.grid_rowconfigure(0, weight=1)
            tab.grid_columnconfigure(0, weight=1)
            scroll = ctk.CTkScrollableFrame(tab, fg_color=surface,
                scrollbar_button_color=("#C5D7D7", "#36565B"))
            scroll.grid(row=0, column=0, sticky="nsew")
            scroll.grid_columnconfigure(0, weight=1)
            pages[name] = scroll

        def section(parent, title, note):
            group = ctk.CTkFrame(parent, fg_color="transparent")
            group.pack(fill="x", padx=6, pady=(14, 8))
            ctk.CTkLabel(group, text=title, text_color=ink, font=heading_font).pack(anchor="w")
            ctk.CTkLabel(group, text=note, text_color=muted, font=body_font,
                         wraplength=440, justify="left").pack(anchor="w", pady=(2, 10))
            return group

        def input_surface():
            return "#F7FAFA" if ctk.get_appearance_mode() == "Light" else "#122327"

        def input_text():
            return "#18383D" if ctk.get_appearance_mode() == "Light" else "#E4EFF0"

        def field(parent, label, attr, value="", placeholder="", choices=None, multiple=False,
                  custom=False, on_change=None):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=(0, 13))
            ctk.CTkLabel(row, text=label.rstrip(":"), text_color=ink, font=body_font).pack(anchor="w", pady=(0, 5))
            var = tk.StringVar(value=value)
            setattr(self, attr, var)
            options = dict(height=36, corner_radius=7, font=body_font)
            if multiple:
                # 多选下拉：点一项切换勾选，按钮上显示已选数量。
                # custom=True 时菜单底部可以自己加减选项。
                selected = set()
                setattr(self, attr + "_selected", selected)
                option_list = list(choices or [])
                setattr(self, attr + "_options", option_list)

                def summary():
                    if not selected:
                        return "未选择"
                    names = [n for n in option_list if n in selected]
                    names += sorted(selected - set(option_list))
                    text = "、".join(names)
                    return text if len(text) <= 28 else f"已选 {len(selected)} 项"

                menu_panel = ctk.CTkFrame(row, fg_color=surface, corner_radius=7,
                    border_width=1, border_color=("#D6E3E3", "#345057"))
                menu_open = False

                def toggle(name, var=var):
                    if name in selected:
                        selected.discard(name)
                    else:
                        selected.add(name)
                    var.set(summary())
                    if menu_open:
                        rebuild()
                    if on_change:
                        on_change()

                def rebuild(var=var):
                    for child in menu_panel.winfo_children():
                        child.destroy()
                    light = ctk.get_appearance_mode() == "Light"

                    def add_item(label, command=None, disabled=False, separator=False):
                        if separator:
                            ctk.CTkFrame(menu_panel, height=1,
                                fg_color=("#D6E3E3", "#345057")).pack(fill="x", pady=3)
                            return
                        btn = ctk.CTkButton(menu_panel, text=label, anchor="w",
                            height=36, corner_radius=4, font=body_font,
                            fg_color="transparent", hover_color=("#E8F0F0", "#294146"),
                            text_color=muted if disabled else ink,
                            state="disabled" if disabled else "normal", command=command)
                        btn.pack(fill="x", padx=4, pady=2)
                    if not option_list:
                        add_item("（先选城市）", disabled=True)
                    for name in option_list:
                        mark = "✓  " if name in selected else "    "
                        add_item(mark + name, command=lambda n=name: toggle(n))
                    if custom:
                        add_item("", separator=True)
                        add_item("＋ 添加自定义…", command=add_custom)
                        if selected:
                            add_item("－ 去掉已选", command=remove_selected)
                    var.set(summary())

                def add_custom(var=var):
                    name = self._ask_custom_option()
                    if not name:
                        return
                    for part in name.replace("，", ",").split(","):
                        part = part.strip()
                        if part and part not in option_list:
                            option_list.append(part)
                        if part:
                            selected.add(part)
                    rebuild()
                    if on_change:
                        on_change()

                def remove_selected(var=var):
                    option_list[:] = [n for n in option_list if n not in selected]
                    selected.clear()
                    rebuild()
                    if on_change:
                        on_change()

                def close_menu():
                    nonlocal menu_open
                    menu_open = False
                    menu_panel.pack_forget()

                def open_menu():
                    nonlocal menu_open
                    menu_open = not menu_open
                    if menu_open:
                        rebuild()
                        menu_panel.pack(fill="x", pady=(4, 0))
                    else:
                        close_menu()

                self._dropdown_closers.append(close_menu)

                button = ctk.CTkButton(row, text=summary(), anchor="w",
                    fg_color=surface, hover_color=("#E8F0F0", "#1A3035"),
                    text_color=ink, border_width=1, border_color=("#D6E3E3", "#345057"),
                    **options, command=open_menu)
                var.trace_add("write", lambda *_: button.configure(text=var.get() or summary()))
                button.pack(fill="x")
                setattr(self, attr + "_rebuild", rebuild)
                return
            if choices is None:
                widget = ctk.CTkEntry(row, textvariable=var, placeholder_text=placeholder,
                    fg_color=surface, border_color=("#D6E3E3", "#345057"),
                    text_color=ink, border_width=1, **options)
            else:
                # 单选 Select：列表直接放在同一个字段容器中，宽度自然跟随输入框。
                select_panel = ctk.CTkFrame(row, fg_color=surface, corner_radius=7,
                    border_width=1, border_color=("#D6E3E3", "#345057"))
                select_open = False
                select_button = ctk.CTkButton(row, textvariable=var, anchor="w",
                    fg_color=surface, hover_color=("#E8F0F0", "#1A3035"),
                    text_color=ink, border_width=1, border_color=("#D6E3E3", "#345057"),
                    **options)

                def rebuild_select_menu():
                    for child in select_panel.winfo_children():
                        child.destroy()
                    light = ctk.get_appearance_mode() == "Light"
                    for option in choices:
                        ctk.CTkButton(select_panel, text=option, anchor="w",
                            height=36, corner_radius=4, font=body_font,
                            fg_color="transparent", hover_color=("#E8F0F0", "#294146"),
                            text_color=ink,
                            command=lambda value=option: choose_option(value)).pack(fill="x", padx=4, pady=2)

                def choose_option(value):
                    nonlocal select_open
                    var.set(value)
                    select_open = False
                    select_panel.pack_forget()

                def close_select_menu():
                    nonlocal select_open
                    select_open = False
                    select_panel.pack_forget()

                def open_select_menu():
                    nonlocal select_open
                    select_open = not select_open
                    if select_open:
                        rebuild_select_menu()
                        select_panel.pack(fill="x", pady=(4, 0))
                    else:
                        close_select_menu()

                self._dropdown_closers.append(close_select_menu)

                select_button.configure(command=open_select_menu)
                select_button.pack(fill="x")
                return
            widget.pack(fill="x")

        def checkbox(parent, text, var):
            widget = ctk.CTkCheckBox(parent, text=text, variable=var, font=body_font,
                text_color=ink, fg_color=accent, hover_color="#096E69", border_width=2,
                border_color=("#A1BABA", "#68888E"), checkbox_width=19, checkbox_height=19,
                corner_radius=5)
            return widget

        from utils import load_city_tree
        self._city_tree = load_city_tree()
        # 按编码索引。城市名在不同省可能重名，名字不能当唯一键。
        self._city_by_code = {c["code"]: c for c in self._city_tree}
        self._city_data_missing = not self._city_tree

        basic = section(pages["基础设置"], "投递节奏", "设置每日数量与投递间隔，按自己的节奏开始。")
        # 不预置关键词：搜什么是用户自己的事，列表只来自配置里已保存的。
        field(basic, "搜索关键词（每个词单独搜一遍）", "var_keywords", "", multiple=True, custom=True,
              choices=[])
        field(basic, "每日投递上限", "var_daily_limit", "30")
        field(basic, "投递间隔（秒）", "var_interval", "50")
        field(basic, "默认招呼语（投递时发给招聘者，留空用 Boss 账号默认）", "var_greeting", "你好")
        salary = section(pages["基础设置"], "薪资与岗位类型", "薪资单位为元 / 月，填写 0 表示不限。")
        field(salary, "薪资下限", "var_min_salary", "0", "如 4000")
        field(salary, "薪资上限", "var_max_salary", "0", "如 50000")
        field(salary, "岗位类型", "var_job_type", "全部", choices=["全部", "只看兼职", "排除兼职"])
        def city_label(city):
            # 带上省份，重名时也能分清，保存和城区都按这个标签认。
            if city["province"] and city["province"] != city["name"]:
                return f"{city['province']}·{city['name']}"
            return city["name"]

        self._city_label_of = {c["code"]: city_label(c) for c in self._city_tree}
        # 城区是城市选择器的第三级，选中项仍存 filters.districts，格式 "城市名·区名"。
        self.var_districts_selected = set()
        self._build_city_picker(salary, city_label)
        self.var_skip_communicated = tk.BooleanVar(value=True)
        checkbox(salary, "跳过已沟通岗位", self.var_skip_communicated).pack(anchor="w", pady=(6, 12))
        self.var_auto_favorite = tk.BooleanVar(value=False)
        checkbox(salary, "投递后自动收藏", self.var_auto_favorite).pack(anchor="w", pady=(0, 12))

        jobs = section(pages["岗位筛选"], "岗位排除", "点开下拉勾选，底部可以自己加减选项。")
        field(jobs, "标题关键词排除", "var_title_blacklist", "", multiple=True, custom=True,
              choices=["客服", "销售", "实习", "主播"])
        field(jobs, "岗位类别排除", "var_category_blacklist", "", multiple=True, custom=True,
              choices=["主播", "销售", "客服"])
        company = section(pages["公司与招聘者"], "公司偏好", "点开下拉勾选，底部可以自己加减选项，全不选不限制。")
        field(company, "公司黑名单", "var_blacklist", "", multiple=True, custom=True,
              choices=["外包", "劳务", "派遣"])
        # 选项固定的筛选用下拉多选，全不选等于不限制。
        field(jobs, "工作经验（只投勾选的，全不选不限）", "var_experience_levels", "", multiple=True,
              choices=["在校/应届", "1年以内", "1-3年", "3-5年", "5-10年", "经验不限"])
        field(jobs, "学历要求（只投勾选的，全不选不限）", "var_degree_levels", "", multiple=True,
              choices=["初中及以下", "中专/中技", "高中", "大专", "本科", "硕士", "博士", "学历不限"])
        field(company, "公司规模（只投勾选的，全不选不限）", "var_scale_levels", "", multiple=True,
              choices=["0-20人", "20-99人", "100-499人", "500-999人", "1000-9999人", "10000人以上"])
        field(company, "融资阶段（只投勾选的，全不选不限）", "var_stage_levels", "", multiple=True,
              choices=["未融资", "天使轮", "A轮", "B轮", "C轮", "D轮及以上", "已上市", "不需要融资"])
        field(jobs, "必须福利（没有的岗位跳过，全不选不限）", "var_welfare_required", "", multiple=True,
              custom=True,
              choices=["五险一金", "补充医疗保险", "定期体检", "年终奖", "带薪年假", "员工旅游", "餐补", "住房补贴"])
        # 城区不在这里选：它跟着城市走，放在「投递城市」的第三级里。
        field(jobs, "岗位标签排除", "var_tag_blacklist", "", multiple=True, custom=True,
              choices=["餐饮外卖", "自带电动车", "需要驾照", "需要电工证"])
        field(company, "公司行业排除", "var_industry_blacklist", "", multiple=True, custom=True,
              choices=["餐饮", "物流", "房地产", "教育培训", "人力资源"])
        field(company, "招聘者身份排除", "var_recruiter_blacklist", "", multiple=True, custom=True,
              choices=["人事", "人资专员", "猎头"])
        activity = section(pages["公司与招聘者"], "招聘者活跃度", "只投勾选的活跃档位。")
        from main import ACTIVITY_LEVELS
        self.activity_vars = {}
        for level in ACTIVITY_LEVELS:
            var = tk.BooleanVar(value=False)
            self.activity_vars[level] = var
            checkbox(activity, level, var).pack(anchor="w", pady=(0, 12))
        search = section(pages["搜索条件"], "搜索页筛选", "使用 Boss 搜索条件缩小岗位范围。")
        search_filters = [
            ("工作经验:", "var_experience",
             ["不限", "在校/应届", "1年以内", "1-3年", "3-5年", "5-10年"]),
            ("学历要求:", "var_degree",
             ["不限", "初中及以下", "中专/中技", "高中", "大专", "本科", "硕士", "博士"]),
            ("薪资待遇:", "var_salary",
             ["不限", "3K以下", "3-5K", "5-10K", "10-20K", "20-50K", "50K以上"]),
            ("公司规模:", "var_scale",
             ["不限", "0-20人", "20-99人", "100-499人", "500-999人", "1000-9999人", "10000人以上"]),
            ("融资阶段:", "var_stage",
             ["不限", "未融资", "天使轮", "A轮", "B轮", "C轮", "D轮及以上", "已上市", "不需要融资"]),
        ]
        for label, attr, values in search_filters:
            field(search, label, attr, "不限", choices=values)
        field(search, "求职类型", "var_job_type_search", "不限", choices=["不限", "兼职", "实习"])

        console = ctk.CTkFrame(workspace, fg_color=surface, corner_radius=16)
        console.grid(row=0, column=1, sticky="nsew")
        console.grid_columnconfigure(0, weight=1)
        console.grid_rowconfigure(5, weight=1)
        ctk.CTkLabel(console, text="运行控制", font=heading_font, text_color=ink).grid(
            row=0, column=0, sticky="w", padx=22, pady=(20, 2))
        ctk.CTkLabel(console, text="启动浏览器并登录，再开始投递。", font=body_font, text_color=muted).grid(
            row=1, column=0, sticky="w", padx=22, pady=(0, 18))
        controls = ctk.CTkFrame(console, fg_color="transparent")
        controls.grid(row=2, column=0, sticky="ew", padx=22)
        controls.grid_columnconfigure((0, 1), weight=1)
        self.btn_start = ctk.CTkButton(controls, text="启动 Edge", command=self._on_start,
            height=40, corner_radius=8, fg_color=("#E5EFEF", "#29434A"), text_color=ink,
            hover_color=("#D5E6E5", "#35565E"), font=body_font, width=100)
        self.btn_start.grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=(0, 10))
        self.btn_save = ctk.CTkButton(controls, text="保存配置", command=self._on_save_config,
            height=40, corner_radius=8, fg_color=("#E5EFEF", "#29434A"), text_color=ink,
            hover_color=("#D5E6E5", "#35565E"), font=body_font, width=100)
        self.btn_save.grid(row=0, column=1, sticky="ew", pady=(0, 10))
        self.btn_apply = ctk.CTkButton(controls, text="开始投递", command=self._on_apply, state="disabled",
            height=44, corner_radius=8, fg_color=accent, hover_color="#096E69", font=body_font, width=100)
        self.btn_apply.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self.btn_stop = ctk.CTkButton(controls, text="停止", command=self._on_stop, state="disabled",
            height=44, corner_radius=8, fg_color=("#F9EAEA", "#482E35"), text_color=("#A13D45", "#F1B2B8"),
            hover_color=("#F2D7D9", "#643D46"), font=body_font, width=100)
        self.btn_stop.grid(row=1, column=1, sticky="ew")
        self.var_status = tk.StringVar(value="就绪")
        self.status_label = ctk.CTkLabel(console, textvariable=self.var_status,
            font=body_font, text_color=accent, anchor="w", wraplength=310)
        self.status_label.grid(row=3, column=0, sticky="ew", padx=22, pady=(16, 12))
        stats = ctk.CTkFrame(console, fg_color=("#F0F6F6", "#20353A"), corner_radius=8)
        stats.grid(row=4, column=0, sticky="ew", padx=22, pady=(0, 18))
        self._count_success = self._count_skip = self._count_fail = 0
        self.var_stats = tk.StringVar(value="成功: 0  |  跳过: 0  |  失败: 0")
        self.stats_label = ctk.CTkLabel(stats, textvariable=self.var_stats, text_color=ink,
            font=body_font, height=42)
        self.stats_label.pack(padx=10)
        log_frame = ctk.CTkFrame(console, fg_color="transparent")
        log_frame.grid(row=5, column=0, sticky="nsew", padx=22, pady=(0, 22))
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(log_frame, text="运行日志", text_color=ink, font=heading_font).grid(
            row=0, column=0, sticky="w", pady=(0, 10))
        self.log_text = ctk.CTkTextbox(log_frame, state="disabled", wrap="word", corner_radius=10,
            fg_color=("#F7FAFA", "#102024"), text_color=ink, border_width=1,
            border_color=("#E2ECEC", "#2C464D"), border_spacing=12,
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12), height=220)
        self.log_text.grid(row=1, column=0, sticky="nsew")
        self.log_text.tag_config("success", foreground="#159477")
        self.log_text.tag_config("skip", foreground="#819397")
        self.log_text.tag_config("error", foreground="#D05D67")
        self.log_text.tag_config("info", foreground="#328EB1")

    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)

    def _load_config_to_ui(self):
        cfg = load_config()
        self.var_daily_limit.set(str(cfg.get("daily_limit", 30)))
        self.var_interval.set(str(cfg.get("interval_seconds", 60)))
        self.var_greeting.set(cfg.get("greeting") or "你好")
        filters = cfg.get("filters", {})
        self.var_min_salary.set(str(filters.get("min_salary", 0)))
        self.var_max_salary.set(str(filters.get("max_salary", 0)))
        # 岗位类型映射
        jt_map = {"all": "全部", "only_parttime": "只看兼职", "no_parttime": "排除兼职"}
        self.var_job_type.set(jt_map.get(filters.get("job_type", "all"), "全部"))
        self.var_skip_communicated.set(filters.get("skip_communicated", True))
        enabled = set(filters.get("activity_levels", []) or [])
        for level, var in self.activity_vars.items():
            var.set(level in enabled)
        self.var_keywords_selected.clear()
        for word in [w for w in (cfg.get("keywords") or []) if w]:
            if word not in self.var_keywords_options:
                self.var_keywords_options.append(word)
            self.var_keywords_selected.add(word)
        self.var_keywords_rebuild()
        cities = cfg.get("cities") or {}
        self.var_cities_selected.clear()
        # 城市数据里对不上的条目界面无法展示，单独留着，保存时原样写回，不丢。
        self._cities_unmatched = {}
        for name, code in cities.items():
            code = str(code)
            city = self._city_by_code.get(code)
            if city is None:
                matches = [c for c in self._city_tree if c["name"] == name]
                city = matches[0] if len(matches) == 1 else None
            if city is not None:
                self.var_cities_selected.add(self._city_label_of[city["code"]])
            else:
                self._cities_unmatched[name] = code
        self.var_cities_rebuild()
        # 只认 "城市名·区名"。旧配置里不带城市名的区名对不上城市，不再沿用。
        self.var_districts_selected.clear()
        self.var_districts_selected.update(
            s for s in (filters.get("districts") or []) if "·" in str(s))
        for key, attr in (("experience_levels", "var_experience_levels"),
                          ("degree_levels", "var_degree_levels"),
                          ("scale_levels", "var_scale_levels"),
                          ("stage_levels", "var_stage_levels"),
                          ("welfare_required", "var_welfare_required"),
                          ("tag_blacklist", "var_tag_blacklist"),
                          ("industry_blacklist", "var_industry_blacklist"),
                          ("recruiter_blacklist", "var_recruiter_blacklist"),
                          ("company_blacklist", "var_blacklist"),
                          ("title_blacklist", "var_title_blacklist"),
                          ("category_blacklist", "var_category_blacklist")):
            saved = [s for s in (filters.get(key, []) or []) if s]
            options = getattr(self, attr + "_options")
            selected = getattr(self, attr + "_selected")
            selected.clear()
            for item in saved:
                if item not in options:
                    options.append(item)
                selected.add(item)
            getattr(self, attr + "_rebuild")()
        code_to_label = {
            # 编码是对着搜索结果逐个实测的，不是猜的：101 是不限
            "experience": {"102": "在校/应届", "103": "1年以内", "104": "1-3年",
                           "105": "3-5年", "106": "5-10年"},
            "degree": {"209": "初中及以下", "208": "中专/中技", "206": "高中", "202": "大专",
                       "203": "本科", "204": "硕士", "205": "博士"},
            "salary": {"402": "3K以下", "403": "3-5K", "404": "5-10K", "405": "10-20K",
                       "406": "20-50K", "407": "50K以上"},
            "scale": {"301": "0-20人", "302": "20-99人", "303": "100-499人", "304": "500-999人",
                      "305": "1000-9999人", "306": "10000人以上"},
            "stage": {"801": "未融资", "802": "天使轮", "803": "A轮", "804": "B轮", "805": "C轮",
                      "806": "D轮及以上", "807": "已上市", "808": "不需要融资"},
        }
        for key, mapping in code_to_label.items():
            getattr(self, f"var_{key}").set(mapping.get(str(filters.get(key) or ""), "不限"))
        job_type_map = {"1901": "兼职", "1903": "实习"}
        self.var_job_type_search.set(job_type_map.get(str(filters.get("jobType") or ""), "不限"))
        self.var_auto_favorite.set(bool(filters.get("auto_favorite", False)))

    def _build_city_picker(self, parent, city_label):
        """省、市、区三级联动。省定城市列表，城市定城区列表，城市和区都可以多选。

        城区全不选表示该城市不限区。区名会重名，选中项存成 "城市名·区名"。
        """
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 13))
        self._city_picker_row = row
        ctk.CTkLabel(row, text="投递城市与城区（城市、城区都可多选，城区全不选不限）",
                     text_color=self._ink, font=self._body_font).pack(anchor="w", pady=(0, 5))

        by_province = {}
        for city in self._city_tree:
            by_province.setdefault(city["province"] or city["name"], []).append(city)
        provinces = list(by_province)

        self.var_cities = tk.StringVar(value="未选择")
        self.var_cities_selected = set()
        self.var_cities_options = [city_label(c) for c in self._city_tree]
        self._city_province = tk.StringVar(value="")

        surface = ("#FFFFFF", "#17282C")
        ink = self._ink
        font = self._body_font
        columns = ctk.CTkFrame(row, fg_color="transparent")
        columns.grid_columnconfigure((0, 1, 2), weight=1)

        def summary():
            labels = [self._city_label_of[c["code"]] for c in self._city_tree
                      if self._city_label_of[c["code"]] in self.var_cities_selected]
            if not labels:
                return "未选择"
            text = "、".join(labels)
            return text if len(text) <= 28 else f"已选 {len(labels)} 个城市"

        def make_panel(parent):
            panel = ctk.CTkFrame(parent, fg_color=surface, corner_radius=7,
                border_width=1, border_color=("#D6E3E3", "#345057"))
            box = ctk.CTkScrollableFrame(panel, fg_color="transparent", height=220,
                scrollbar_button_color=("#C5D7D7", "#36565B"))
            box.pack(fill="x", padx=2, pady=2)
            return panel, box

        province_panel, province_box = make_panel(columns)
        city_panel, city_box = make_panel(columns)
        district_panel, district_box = make_panel(columns)
        province_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        city_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 4))
        district_panel.grid(row=0, column=2, sticky="nsew")
        panels_open = False
        self._district_city = None

        def fill(box, items, command_of):
            for child in box.winfo_children():
                child.destroy()
            for item in items:
                ctk.CTkButton(box, text=item, anchor="w", height=34, corner_radius=4,
                    font=font, fg_color="transparent", hover_color=("#E8F0F0", "#294146"),
                    text_color=ink, command=command_of(item)).pack(fill="x", padx=2, pady=1)

        def district_key(city, district):
            return f"{city['name']}·{district}"

        def show_districts(city):
            """第三列列出这个城市的区。城市没勾选时区也列出来，但勾区会顺带勾上城市。"""
            self._district_city = city
            for child in district_box.winfo_children():
                child.destroy()
            if city is None:
                return
            for district in city["districts"]:
                mark = "✓  " if district_key(city, district) in self.var_districts_selected else "    "
                ctk.CTkButton(district_box, text=mark + district, anchor="w", height=34,
                    corner_radius=4, font=font, fg_color="transparent",
                    hover_color=("#E8F0F0", "#294146"), text_color=ink,
                    command=lambda d=district, c=city: toggle_district(c, d)).pack(fill="x", padx=2, pady=1)

        def toggle_district(city, district):
            key = district_key(city, district)
            if key in self.var_districts_selected:
                self.var_districts_selected.discard(key)
            else:
                self.var_districts_selected.add(key)
                # 勾了区就一定要投这个城市，否则区选了没有意义。
                self.var_cities_selected.add(city_label(city))
                self.var_cities.set(summary())
            show_districts(city)
            pick_province(city["province"] or city["name"])

        def pick_province(name, focus_city=None):
            self._city_province.set(name)
            cities = by_province.get(name, [])
            for child in city_box.winfo_children():
                child.destroy()
            for city in cities:
                current = city is focus_city or (focus_city is None and city is self._district_city)
                mark = "✓  " if city_label(city) in self.var_cities_selected else "    "
                prefix = "▸ " if current else "    "
                ctk.CTkButton(city_box, text=prefix + mark + city["name"], anchor="w", height=34,
                    corner_radius=4, font=font, fg_color="transparent",
                    hover_color=("#E8F0F0", "#294146"), text_color=ink,
                    command=lambda c=city: pick_city(c)).pack(fill="x", padx=2, pady=1)

        def pick_city(city):
            """点城市：已选的取消，没选的勾上，同时把第三列切到这个城市的区。"""
            label = city_label(city)
            if label in self.var_cities_selected and self._district_city is city:
                self.var_cities_selected.discard(label)
                # 城市不投了，它下面勾过的区一并去掉。
                for district in city["districts"]:
                    self.var_districts_selected.discard(district_key(city, district))
            else:
                self.var_cities_selected.add(label)
            self.var_cities.set(summary())
            show_districts(city)
            pick_province(city["province"] or city["name"], focus_city=city)

        def rebuild():
            self.var_cities.set(summary())
            if not panels_open:
                return
            if not provinces:
                return
            current = self._city_province.get()
            if current not in by_province:
                current = next((c["province"] or c["name"] for c in self._city_tree
                                if city_label(c) in self.var_cities_selected), provinces[0])
                self._city_province.set(current)
            fill(province_box,
                 [("▸ " if name == current else "    ") + name for name in provinces],
                 lambda name: (lambda n=name.lstrip("▸ ").strip(): pick_province(n)))
            focus = self._district_city if (self._district_city
                                             and (self._district_city["province"] or self._district_city["name"]) == current) else None
            pick_province(current, focus_city=focus)
            if focus is None:
                show_districts(None)

        def close_panels():
            nonlocal panels_open
            panels_open = False
            columns.pack_forget()

        def open_panels():
            nonlocal panels_open
            panels_open = not panels_open
            if panels_open:
                columns.pack(fill="x", pady=(4, 0))
                rebuild()
            else:
                close_panels()

        self._dropdown_closers.append(close_panels)

        button = ctk.CTkButton(row, text=summary(), anchor="w", height=36,
            corner_radius=7, font=font, fg_color=surface, hover_color=("#E8F0F0", "#1A3035"),
            text_color=ink, border_width=1, border_color=("#D6E3E3", "#345057"),
            command=open_panels)
        button.pack(fill="x")
        # CTkButton 不支持 textvariable，文字变化时手动更新。
        self.var_cities.trace_add("write", lambda *_: button.configure(text=self.var_cities.get()))

        def refresh_summary():
            rebuild()
        self.var_cities_rebuild = refresh_summary

    def _read_int(self, var, label: str, default: int) -> int:
        """读界面上的数字输入。留空用默认值，填了非数字就报错提示，不让程序崩。"""
        text = var.get().strip()
        if not text:
            return default
        try:
            return int(text)
        except ValueError:
            raise ValueError(f"「{label}」要填整数，当前填的是「{text}」")

    def _save_ui_to_config(self):
        cfg = load_config()
        # 关键词可以为空：没填也能保存配置、打开 Edge，只是开始投递时拦住。
        cfg["keywords"] = [item for item in self.var_keywords_options
                           if item in self.var_keywords_selected]
        cfg["daily_limit"] = self._read_int(self.var_daily_limit, "每日投递上限", 30)
        cfg["interval_seconds"] = self._read_int(self.var_interval, "投递间隔(秒)", 60)
        cfg["greeting"] = self.var_greeting.get().strip() or "你好"
        if "filters" not in cfg:
            cfg["filters"] = {}
        cfg["filters"]["min_salary"] = self._read_int(self.var_min_salary, "最低薪资", 0)
        cfg["filters"]["max_salary"] = self._read_int(self.var_max_salary, "最高薪资", 0)
        # 岗位类型映射
        jt_rmap = {"全部": "all", "只看兼职": "only_parttime", "排除兼职": "no_parttime"}
        cfg["filters"]["job_type"] = jt_rmap.get(self.var_job_type.get(), "all")
        cfg["filters"]["skip_communicated"] = self.var_skip_communicated.get()
        cfg["filters"]["activity_levels"] = [
            level for level, var in self.activity_vars.items() if var.get()
        ]
        if self._city_data_missing:
            # 城市数据没加载出来时，界面上一个城市都选不了，不能拿空选择覆盖已有配置。
            self._city_save_skipped = True
        else:
            self._city_save_skipped = False
            label_to_city = {self._city_label_of[c["code"]]: c for c in self._city_tree}
            cfg["cities"] = dict(getattr(self, "_cities_unmatched", {}))
            cfg["cities"].update({city["name"]: city["code"]
                                  for label in self.var_cities_selected
                                  if (city := label_to_city.get(label))})
        # 城区选中项就是 "城市名·区名" 的集合，不再经过下拉的选项列表。
        cfg["filters"]["districts"] = sorted(self.var_districts_selected)
        for key, attr in (("experience_levels", "var_experience_levels"),
                          ("degree_levels", "var_degree_levels"),
                          ("scale_levels", "var_scale_levels"),
                          ("stage_levels", "var_stage_levels"),
                          ("welfare_required", "var_welfare_required"),
                          ("tag_blacklist", "var_tag_blacklist"),
                          ("industry_blacklist", "var_industry_blacklist"),
                          ("recruiter_blacklist", "var_recruiter_blacklist"),
                          ("company_blacklist", "var_blacklist"),
                          ("title_blacklist", "var_title_blacklist"),
                          ("category_blacklist", "var_category_blacklist")):
            options = getattr(self, attr + "_options")
            selected = getattr(self, attr + "_selected")
            cfg["filters"][key] = [item for item in options if item in selected]
        label_to_code = {
            "experience": {"在校/应届": "102", "1年以内": "103", "1-3年": "104",
                           "3-5年": "105", "5-10年": "106"},
            "degree": {"初中及以下": "209", "中专/中技": "208", "高中": "206", "大专": "202",
                       "本科": "203", "硕士": "204", "博士": "205"},
            "salary": {"3K以下": "402", "3-5K": "403", "5-10K": "404", "10-20K": "405",
                       "20-50K": "406", "50K以上": "407"},
            "scale": {"0-20人": "301", "20-99人": "302", "100-499人": "303", "500-999人": "304",
                      "1000-9999人": "305", "10000人以上": "306"},
            "stage": {"未融资": "801", "天使轮": "802", "A轮": "803", "B轮": "804", "C轮": "805",
                      "D轮及以上": "806", "已上市": "807", "不需要融资": "808"},
        }
        for key, mapping in label_to_code.items():
            cfg["filters"][key] = mapping.get(getattr(self, f"var_{key}").get(), "")
        job_type_code = {"兼职": "1901", "实习": "1903"}
        cfg["filters"]["jobType"] = job_type_code.get(self.var_job_type_search.get(), "")
        # 工作区域改由「岗位筛选」里的城区下拉负责，旧配置里的编码不再保留。
        cfg["filters"].pop("multiBusinessDistrict", None)
        cfg["filters"]["auto_favorite"] = self.var_auto_favorite.get()
        save_config(cfg)

    def _on_save_config(self):
        try:
            self._save_ui_to_config()
            self._append_log("[配置已保存]", "success")
            if getattr(self, "_city_save_skipped", False):
                self._append_log("[城市数据缺失，本次保存没有改动城市列表]", "error")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def _append_log(self, text: str, tag: str = ""):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n", tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _log_callback(self, msg: str, tag: str = ""):
        if not tag:
            if "success" in msg or "投递 [" in msg:
                tag = "success"
            elif "跳过" in msg:
                tag = "skip"
            elif "!!" in msg or "error" in msg or "失败" in msg or "错误" in msg:
                tag = "error"
            elif "启动" in msg or "接管" in msg or "检测" in msg or "完成" in msg or "系统" in msg:
                tag = "info"
        # 更新进度计数
        if "-> success" in msg:
            self._count_success += 1
            self.after(0, self._update_stats)
        elif "跳过" in msg:
            self._count_skip += 1
            self.after(0, self._update_stats)
        elif "-> error" in msg or "-> timeout" in msg or "-> no_" in msg \
                or "-> greeting_failed" in msg or "-> send_unconfirmed" in msg:
            self._count_fail += 1
            self.after(0, self._update_stats)
        self.after(0, self._append_log, msg, tag)

    def _update_stats(self):
        self.var_stats.set(f"成功: {self._count_success}  |  跳过: {self._count_skip}  |  失败: {self._count_fail}")

    def _on_start(self):
        try:
            self._save_ui_to_config()
        except ValueError as e:
            messagebox.showerror("输入有误", str(e))
            return
        self.btn_start.configure(state="disabled")
        self.var_status.set("正在启动 Edge...")
        self._stop_event.clear()
        self._edge_ready_event.clear()

        from utils import set_log_callback
        set_log_callback(self._log_callback)
        self._log_callback("[系统] 开始执行 Edge 启动流程...", "info")

        def worker():
            try:
                import traceback
                self._log_callback("[系统] worker 线程已启动，导入模块中...", "info")
                from browser_launcher import start_edge, _port_open, _edge_owns_port, CDP_PORT
                self._log_callback("[系统] 模块导入完成，检查端口...", "info")

                if _port_open(CDP_PORT) and not _edge_owns_port():
                    raise RuntimeError(
                        f"端口 {CDP_PORT} 被别的调试浏览器占用，不是本工具启动的 Edge。"
                        "关掉那个浏览器，或停掉它的调试端口后再试")
                if _port_open(CDP_PORT):
                    self._log_callback("[Edge CDP 端口已开启] 复用已有 Edge", "info")
                else:
                    self._log_callback("[正在清理旧进程并启动 Edge...]", "info")
                    start_edge()
                self._open_search_page()
                self.after(0, self._refresh_account)
                self._log_callback("[Edge 已启动] 搜索页已打开，登录后点开始投递即可", "success")
                self.after(0, self._edge_started)
            except Exception as e:
                self._log_callback(f"[错误] 启动 Edge 失败: {e}\n{traceback.format_exc()}", "error")
                self.after(0, lambda: self.btn_start.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_account(self):
        """从已打开的 Edge 页面读登录账号的名字和头像，显示在头部。

        读不到就保持「未登录」。头像是网络图片，下不到就只显示名字。
        """
        import json
        import urllib.request
        from browser_launcher import CDP_PORT

        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/list", timeout=4) as r:
                tabs = json.loads(r.read().decode())
        except Exception:
            return
        ws_url = next((t.get("webSocketDebuggerUrl") for t in tabs
                       if "zhipin.com" in t.get("url", "") and t.get("type") == "page"), None)
        if not ws_url:
            return

        from patchright.sync_api import sync_playwright

        def read():
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
                page = next((pg for pg in browser.contexts[0].pages
                             if "zhipin.com" in pg.url), None)
                if page is None:
                    return None
                return page.evaluate(r"""() => {
                    const name = document.querySelector('.nav-figure .label-text');
                    const img = document.querySelector('.nav-figure img');
                    return {name: name ? name.innerText.trim() : '',
                            avatar: img ? img.src : ''};
                }""")

        try:
            info = read()
        except Exception:
            return
        if not info or not info.get("name"):
            return
        # 读取在后台线程里，改界面要回到主线程。
        self.after(0, lambda: self._show_account(info))

    def _show_account(self, info: dict):
        self.account_name.configure(text=info["name"])
        self.account_state.configure(text="已登录 Boss 直聘")
        self._set_avatar(info.get("avatar") or "")

    def _set_avatar(self, url: str):
        """把头像地址下载成图片放到头部。失败就留着空的色块。"""
        if not url:
            return
        import io
        import urllib.request
        try:
            with urllib.request.urlopen(url, timeout=6) as r:
                image = PILImage.open(io.BytesIO(r.read())).convert("RGBA")
        except Exception:
            return
        image = image.resize((72, 72))
        self._avatar_image = ctk.CTkImage(light_image=image, dark_image=image, size=(36, 36))
        self.account_avatar.configure(image=self._avatar_image, text="")

    def _open_search_page(self):
        """用 CDP 打开第一个关键词 × 第一个城市的搜索页，省掉手动搜索。"""
        import json
        import urllib.parse
        import urllib.request
        from browser_launcher import CDP_PORT
        cfg = load_config()
        keywords = [k for k in (cfg.get("keywords") or []) if k]
        cities = cfg.get("cities") or {}
        if not cities:
            self._log_callback("[提示] 没有选城市，无法自动打开搜索页，请手动打开 Boss 直聘", "error")
            return
        if not keywords:
            # 没填关键词照样打开 Edge，只是不带搜索词，打开城市首页让用户自己搜。
            keyword = ""
            self._log_callback("[提示] 没有搜索关键词，已打开城市首页，搜索词请自己填", "info")
        else:
            keyword = keywords[0]
        city_name, city_code = next(iter(cities.items()))
        url = (f"https://www.zhipin.com/web/geek/job?"
               f"query={urllib.parse.quote(keyword)}&city={city_code}")
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{CDP_PORT}/json/new?{url}", method="PUT")
            with urllib.request.urlopen(req, timeout=8) as r:
                json.loads(r.read().decode())
            self._log_callback(f"[已打开搜索页] {city_name} · {keyword}", "info")
        except Exception as e:
            self._log_callback(f"[提示] 自动打开搜索页失败: {type(e).__name__}，请手动搜索", "error")

    def _edge_started(self):
        self.var_status.set("Edge已启动 - 登录后点开始投递")
        self.btn_apply.configure(state="normal")
        self.btn_stop.configure(state="normal")

    def _on_apply(self):
        # 投递读的是磁盘上的配置，不保存就用的是上次的旧值。
        try:
            self._save_ui_to_config()
        except ValueError as e:
            messagebox.showerror("输入有误", str(e))
            return
        # 关键词为空也允许投递：main.run 会直接投当前浏览器里已打开的岗位列表。
        self.btn_apply.configure(state="disabled")
        self.var_status.set("投递中...")
        # 停止信号不能在这里清。停止后按钮恢复和线程真正退出之间有间隔，
        # 这段时间再点投递，会把旧线程的停止信号清掉，旧线程接着跑。
        # 等旧线程确认退出后再清，见 _wait_worker_exit。
        # 重置本轮计数
        self._count_success = 0
        self._count_skip = 0
        self._count_fail = 0
        self._update_stats()

        def worker():
            try:
                import traceback
                from main import run
                run(stop_event=self._stop_event, on_ready=lambda: None)
            except Exception as e:
                self._log_callback(f"[错误] {e}\n{traceback.format_exc()}", "error")
            finally:
                self.after(0, self._apply_done)

        self._worker = threading.Thread(target=worker, daemon=True)
        self._worker.start()

    def _apply_done(self):
        self.var_status.set("本轮投递完成/停止")
        self.btn_apply.configure(state="normal")
        self.btn_stop.configure(state="normal")

    def _on_stop(self):
        self._stop_event.set()
        self._append_log("[用户请求停止] 当前任务将在本次操作完成后终止", "error")
        # 按钮先不恢复。旧线程还没退出时就恢复，再点一次投递会清掉停止信号，
        # 旧线程接着跑，两个线程一起投。等线程真退出再恢复。
        self.var_status.set("正在停止...")
        self.btn_apply.configure(state="disabled")
        self._wait_worker_exit()

    def _wait_worker_exit(self):
        worker = getattr(self, "_worker", None)
        if worker is not None and worker.is_alive():
            self.after(300, self._wait_worker_exit)
            return
        # 旧线程已退出，这时清停止信号才安全，不会被还在跑的线程误读。
        self._stop_event.clear()
        self.var_status.set("已停止 - 可重新启动")
        self.btn_start.configure(state="normal")
        self.btn_apply.configure(state="normal")
        self.btn_stop.configure(state="normal")

    def _ask_custom_option(self) -> str | None:
        """弹一个跟主题同色的输入框，返回用户输入的文本，取消返回 None。

        不用 tkinter.simpledialog：那个框是系统原生样式，跟界面其余部分对不上。
        """
        dialog = ctk.CTkToplevel(self)
        dialog.title("添加选项")
        dialog.geometry("420x188")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color=("#F4F8F8", "#101C1F"))

        result = {"value": None}

        ctk.CTkLabel(dialog, text="添加选项",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=16, weight="bold"),
            text_color=self._ink, anchor="w").pack(fill="x", padx=24, pady=(20, 0))
        ctk.CTkLabel(dialog, text="多个用逗号分隔", font=self._body_font,
            text_color=("#63767A", "#A2B7BB"), anchor="w").pack(fill="x", padx=24, pady=(2, 10))

        entry = ctk.CTkEntry(dialog, font=self._body_font, height=38,
            fg_color=("#FFFFFF", "#17282C"), text_color=self._ink,
            border_color=("#D6E3E3", "#345057"), border_width=1,
            placeholder_text="例如：五险一金, 双休")
        entry.pack(fill="x", padx=24)
        entry.focus()

        def confirm(event=None):
            result["value"] = entry.get().strip()
            dialog.destroy()

        def cancel(event=None):
            dialog.destroy()

        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(fill="x", padx=24, pady=(16, 0))
        ctk.CTkButton(buttons, text="取消", width=88, height=34, font=self._body_font,
            fg_color="transparent", hover_color=("#E8F0F0", "#1A3035"),
            text_color=self._ink, border_width=1, border_color=("#D6E3E3", "#345057"),
            command=cancel).pack(side="right")
        ctk.CTkButton(buttons, text="添加", width=88, height=34, font=self._body_font,
            fg_color=self._accent, hover_color="#0A9990", text_color="#FFFFFF",
            command=confirm).pack(side="right", padx=(0, 8))

        dialog.bind("<Return>", confirm)
        dialog.bind("<Escape>", cancel)
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        self.wait_window(dialog)
        return result["value"] or None


def _acquire_single_instance() -> bool:
    """创建命名互斥体，保证同时只开一个窗口。

    名字必须和 installer.iss 里的 AppMutex 一致：安装和卸载前 Inno Setup
    靠这个判断程序是否在运行。句柄不关闭，进程退出时由系统回收。
    """
    import ctypes
    from ctypes import wintypes
    # use_last_error=True 才会在调用当下保存错误码，否则读到的是之后被
    # 别的 Win32 调用覆盖过的值，ERROR_ALREADY_EXISTS 永远读不到。
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel32.CreateMutexW(None, False, "BossAutoApply")
    ERROR_ALREADY_EXISTS = 183
    already_running = ctypes.get_last_error() == ERROR_ALREADY_EXISTS
    if not handle or already_running:
        if handle:
            kernel32.CloseHandle(handle)
        return False
    return True


def main():
    if not _acquire_single_instance():
        messagebox.showinfo("Boss直聘投递助手", "程序已经在运行。")
        return
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()

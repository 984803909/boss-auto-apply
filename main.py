"""Boss 直聘自动投递主脚本。

流程：
  1. 使用 data/edge_user_data 中的 Edge 登录态
  2. 按 config.yaml 中 keywords × cities 组合搜索
  3. 遍历岗位卡片，过滤：已沟通 / 薪资过低 / 公司黑名单 / 已投递
  4. 进入岗位详情，点击"立即沟通" -> 在聊天框发送自定义招呼语
  5. 每次投递间隔 interval_seconds（±30% 随机抖动）

风险提示：此类工具可能违反 Boss 直聘用户协议，使用请自行承担封号风险。
"""
from __future__ import annotations

import os
import random
import sys
import threading
import time
from typing import Callable, Optional
from urllib.parse import quote

import yaml
from patchright.sync_api import (BrowserContext, Page, TimeoutError as PWTimeout,
                                  sync_playwright)

from browser_launcher import (PROFILE_DIR, CDP_PORT, connect_to_edge, start_edge,
                              _port_open, _edge_owns_port)
from utils import (log, parse_salary_lower, parse_salary_upper,
                   load_applied_keys, record_applied, record_category,
                   today_applied_count, job_key)

if getattr(sys, 'frozen', False):
    BASE = os.path.dirname(sys.executable)
else:
    BASE = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE, "config.yaml")


from app_config import load_config as read_config


def load_config() -> dict:
    return read_config(CONFIG_PATH)


def human_sleep(seconds: float, jitter: float = 0.3,
               stop_event: threading.Event | None = None) -> bool:
    """带随机抖动的 sleep，模拟真人节奏。
    如果传入 stop_event 且被设置，会提前中断并返回 True。
    返回 False 表示正常睡完。
    """
    delta = seconds * jitter
    total = max(1.0, random.uniform(seconds - delta, seconds + delta))
    elapsed = 0.0
    step = 0.5
    while elapsed < total:
        if stop_event and stop_event.is_set():
            return True
        time.sleep(min(step, total - elapsed))
        elapsed += step
    return False


def build_search_url(keyword: str, city_code: str, filters: dict) -> str:
    """拼出带筛选条件的搜索地址。

    Boss 的筛选是 URL 参数，值为 Boss 自己的编码，0 或不填表示不限。
    experience 工作经验（实测：102 在校/应届、103 1年以内、104 1-3年、
    105 3-5年、106 5-10年，101 就是不限）、degree 学历、salary 薪资档、scale 公司规模、
    stage 融资阶段、jobType 求职类型（1901 兼职、1903 实习）、
    multiBusinessDistrict 工作区域（行政区划编码）。
    """
    url = (f"https://www.zhipin.com/web/geek/job?"
           f"query={quote(keyword)}&city={city_code}")
    for param in ("experience", "degree", "salary", "scale", "stage",
                  "jobType", "multiBusinessDistrict"):
        value = str((filters or {}).get(param) or "").strip()
        if value and value != "0":
            url += f"&{param}={quote(value)}"
    return url


def check_login(page: Page) -> bool:
    """粗略判断登录态：页面若出现登录按钮则视为未登录。

    页面超时或浏览器异常时无法确认登录态，按未登录处理。当成已登录会
    让程序继续跑，直到找不到岗位列表才失败，看不出是登录问题。
    """
    try:
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        # 登录状态下页面顶部一般有头像；未登录会看到 "登录/注册"
        login_link = page.locator("a:has-text('登录/注册')").first
        if login_link.count() > 0 and login_link.is_visible():
            return False
        return True
    except Exception:
        return False


def detect_verify(page: Page) -> bool:
    """检测是否出现滑块/验证码页面。"""
    url = page.url
    if "safe/verify" in url or "securityCheck" in url:
        return True
    try:
        if page.locator("text=请进行安全验证").first.count() > 0:
            return True
    except Exception:
        pass
    return False


def extract_cards(page: Page) -> list[dict]:
    """从搜索结果页提取岗位卡片数据。"""
    page.wait_for_selector("li.job-card-box, li.job-card-wrapper",
                           timeout=20000)
    cards = page.evaluate(
        r"""() => {
            const items = document.querySelectorAll('li.job-card-box, li.job-card-wrapper');
            // Boss 用加密字体渲染薪资数字，innerText 拿不到。
            // 尝试从 Vue 组件数据、aria-label、title 属性等拿到真实薪资。
            function getSalary(el) {
                const node = el.querySelector('.job-salary');
                if (!node) return '';
                // 1. 检查 aria-label / title 等辅助属性
                for (const attr of ['aria-label', 'title', 'data-salary']) {
                    const v = node.getAttribute(attr);
                    if (v && /\d/.test(v)) return v.trim();
                }
                // 2. 检查父/祖的 Vue 数据
                let vueEl = el;
                for (let i = 0; i < 5; i++) {
                    const vc = vueEl.__vue__ || vueEl.__vueParentComponent;
                    if (vc) {
                        // Vue2
                        const d = vc.$data || vc.data || vc.proxy || vc.props;
                        if (d) {
                            const s = d.salaryDesc || d.salary || d.showSalary;
                            if (s) return String(s);
                        }
                        // Vue3 proxy
                        if (vc.proxy) {
                            const s = vc.proxy.salaryDesc || vc.proxy.salary;
                            if (s) return String(s);
                        }
                    }
                    vueEl = vueEl.parentElement;
                    if (!vueEl) break;
                }
                // 3. 从 innerText 解码自定义字体字符（Unicode PUA 区域）
                const raw = node.innerText || '';
                let decoded = '';
                for (const ch of raw) {
                    const code = ch.charCodeAt(0);
                    if (code >= 0xE030 && code <= 0xE03A) {
                        decoded += String(code - 0xE031);
                    } else if (code >= 0xE000 && code <= 0xF8FF) {
                        decoded += String(code - 0xE031);
                    } else {
                        decoded += ch;
                    }
                }
                if (/\d/.test(decoded)) return decoded;
                return raw;
            }

            return Array.from(items).map((el, idx) => {
                const href = el.querySelector('a.job-name, a[href*="/job_detail/"]')?.getAttribute('href') || '';
                const title = el.querySelector('.job-name')?.innerText?.trim() || '';
                const salary = getSalary(el);
                const company = el.querySelector('.boss-name')?.innerText?.trim() || '';
                const area = el.querySelector('.company-location')?.innerText?.trim() || '';
                const tagCommunicated = !!el.querySelector('.start-chat-btn')
                    && /继续沟通|已沟通/.test(el.querySelector('.start-chat-btn')?.innerText || '');
                // 卡片标签前两项固定是工作经验和学历要求，后面是岗位关键词
                const tagTexts = Array.from(el.querySelectorAll('.tag-list li'))
                    .map(li => li.innerText.trim()).filter(Boolean);
                return { index: idx, title, salary, area, company, tagCommunicated, href,
                         experience: tagTexts[0] || '', degree: tagTexts[1] || '',
                         tags: tagTexts.slice(2) };
            });
        }"""
    )
    return cards


# 活跃程度从高到低。界面上勾选的档位允许投递，没勾的跳过。
ACTIVITY_LEVELS = ["在线", "刚刚活跃", "今日活跃", "3日内活跃", "本周活跃",
                   "本月活跃", "半年前活跃"]


def extract_activity(page: Page) -> str:
    """读取详情页招聘者的活跃状态，如 '在线'、'刚刚活跃'、'本周活跃'。"""
    try:
        tag = page.locator(".boss-online-tag").first
        if tag.count() > 0:
            text = (tag.inner_text() or "").strip()
            if text:
                return text
        tag = page.locator(".boss-active-time").first
        if tag.count() > 0:
            return (tag.inner_text() or "").strip()
    except Exception:
        pass
    return ""


def extract_detail(page: Page) -> dict:
    """从详情页读取公司行业、规模、融资阶段、福利和招聘者身份。

    这些字段列表卡片上没有，只能进详情页读。读不到时返回空字符串。
    """
    try:
        # 公司信息块是异步渲染的，不等待时经常读到空
        page.locator(".sider-company").first.wait_for(state="attached", timeout=6000)
    except Exception:
        pass
    try:
        return page.evaluate(r"""() => {
            const text = sel => (document.querySelector(sel)?.innerText || '').trim();
            const company = text('.sider-company');
            const lines = company.split('\n').map(s => s.trim()).filter(Boolean);
            // 形如: 公司基本信息 / 掌玩科技 / 不需要融资 / 1000-9999人 / 互联网 / 查看全部职位
            // 轮次写法是 A轮、B轮、C轮、D轮及以上、天使轮，不含"融资"二字，
            // 只匹配"融资"会读成空，行业也会被误判成轮次
            const stage = lines.find(s => /融资|已上市|轮/.test(s)) || '';
            const scale = lines.find(s => /^\d/.test(s) && s.includes('人')) || '';
            const industry = lines.find(s => s && s !== stage && s !== scale
                && !/公司基本信息|查看全部职位/.test(s) && !/^\S{0,4}科技$/.test(s)
                && lines.indexOf(s) > 1) || '';
            const welfare = [...new Set(
                Array.from(document.querySelectorAll('.job-tags > span'))
                    .map(e => e.innerText.trim()).filter(t => t && t.length < 16))];
            const bossAttr = text('.job-boss-info .boss-info-attr');
            const recruiterRole = bossAttr.split('·').pop().trim();
            return {industry, scale, stage, welfare, recruiterRole};
        }""")
    except Exception:
        return {}


def extract_category(page: Page) -> str:
    """从详情页面包屑读取 Boss 岗位类别，如 '主播'、'前端开发工程师'。

    Boss 详情页底部 .pos-bread 里有岗位分类链接，形如:
        <a href="/p170610/" ...>主播招聘</a>
    /p{code}/ 即 Boss 自身的岗位分类体系，返回去掉"招聘"后缀的类别名。
    """
    try:
        loc = page.locator(".pos-bread a[href^='/p']")
        loc.wait_for(state="attached", timeout=3000)
        texts = loc.all_inner_texts()
    except Exception:
        return ""
    for t in texts or []:
        t = (t or "").strip().replace("招聘", "").strip()
        if t:
            return t
    return ""


def should_skip(card: dict, cfg: dict, applied_keys: set[str]) -> Optional[str]:
    """判断是否跳过此岗位，返回跳过原因（None 表示不跳过）。"""
    filters = cfg.get("filters", {})
    if filters.get("skip_communicated", True) and card.get("tagCommunicated"):
        return "已沟通"

    # 兼职筛选: "all"=全部, "only_parttime"=只看兼职, "no_parttime"=排除兼职
    job_type_filter = filters.get("job_type", "all")
    title = card.get("title", "")
    is_parttime = "兼职" in title
    if job_type_filter == "only_parttime" and not is_parttime:
        return "非兼职岗位"
    if job_type_filter == "no_parttime" and is_parttime:
        return "兼职岗位(已排除)"

    # 薪资区间过滤
    min_salary = filters.get("min_salary", 0)
    max_salary = filters.get("max_salary", 0)
    salary_text = card.get("salary", "")

    if min_salary or max_salary:
        low = parse_salary_lower(salary_text)
        high = parse_salary_upper(salary_text)

        if min_salary:
            if high is None:
                return f"薪资无法解析({salary_text})"
            if high < min_salary:
                return f"薪资上限低于{min_salary}元({salary_text})"

        if max_salary:
            if low is None:
                return f"薪资无法解析({salary_text})"
            if low > max_salary:
                return f"薪资下限超过{max_salary}元({salary_text})"

    for bad in filters.get("company_blacklist", []) or []:
        if bad and bad in (card.get("company") or ""):
            return f"公司黑名单({bad})"

    # 岗位标题关键词排除
    for bad in filters.get("title_blacklist", []) or []:
        if bad and bad in (card.get("title") or ""):
            return f"标题关键词({bad})"

    # 工作经验、学历：卡片标签前两项，配置里填允许的值，空表示不限。
    # 配了白名单却没读到值，不能当符合放行，否则等于筛选失效。
    for field, label in (("experience", "工作经验"), ("degree", "学历")):
        allowed = [s for s in (filters.get(f"{field}_levels") or []) if s]
        if allowed and card.get(field) not in allowed:
            return f"{label}不符({card.get(field) or '未读到'})"

    # 城区：卡片地点形如 "杭州·拱墅区·拱宸桥"，界面存的是 "杭州·拱墅区"。
    # 区名会重名（北京、长春都有朝阳区），所以城市名和区名都要在地点里，
    # 只比区名会把别的城市的同名区放进来。
    districts = [s for s in (filters.get("districts") or []) if s]
    area = card.get("area") or ""
    if districts and not any(
        len(parts) >= 2 and parts[-2] in area and parts[-1] in area
        for parts in (d.split("·") for d in districts)
    ):
        return f"城区不符({card.get('area')})"

    # 岗位关键词标签排除：卡片上经验、学历之外的标签，如 "餐饮外卖"
    for bad in filters.get("tag_blacklist", []) or []:
        if bad and any(bad in t for t in (card.get("tags") or [])):
            return f"岗位标签({bad})"

    if job_key(card.get("href", ""), card.get("company", ""), card.get("title", "")) in applied_keys:
        return "本地已投递过"

    return None


def apply_one(context: BrowserContext, card: dict, cfg: dict,
              keyword: str, city: str) -> str | tuple:
    """打开岗位详情页并尝试投递。

    正常返回状态字符串。触发验证码时返回 (状态, 详情页)，页面留着等用户
    解验证，由调用方等完再关。
    """
    href = card.get("href") or ""
    if not href:
        return "no_href"
    if href.startswith("//"):
        url = "https:" + href
    elif href.startswith("/"):
        url = "https://www.zhipin.com" + href
    else:
        url = href

    page = context.new_page()
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=30000)

        if detect_verify(page):
            # 验证码出现在详情页上，页面必须留着等用户解，不能关。
            return "verify_required", page

        # 岗位类别排除：卡片上没有类别，只能读详情页面包屑（Boss 自己分类）。
        # 命中黑名单直接跳过，不点"立即沟通"。
        category = extract_category(page)
        card["category"] = category
        category_blacklist = [s for s in (cfg.get("filters", {}).get("category_blacklist", []) or []) if s]
        # 配了类别黑名单却没读到类别，无法确认不在黑名单里，跳过而不是放行。
        if category_blacklist and not category:
            return "skip_category:未读到"
        for bad in category_blacklist:
            if bad in category:
                return f"skip_category:{category}"

        # 招聘者活跃度：只投界面上勾选的档位。
        # 勾了却没读到状态，没法确认符合，跳过而不是放行。
        allowed = cfg.get("filters", {}).get("activity_levels") or []
        activity = extract_activity(page)
        card["activity"] = activity
        if allowed and activity not in allowed:
            return f"skip_activity:{activity or '未读到'}"

        # 公司行业、规模、融资阶段、福利、招聘者身份，都在详情页上。
        detail = extract_detail(page)
        card.update({k: v for k, v in detail.items() if v})
        filters = cfg.get("filters", {})

        industry_blacklist = [s for s in (filters.get("industry_blacklist", []) or []) if s]
        # 配了黑名单却没读到行业，无法确认不在黑名单里，跳过而不是放行。
        if industry_blacklist and not detail.get("industry"):
            return "skip_industry:未读到"
        for bad in industry_blacklist:
            if bad in detail.get("industry"):
                return f"skip_industry:{detail.get('industry')}"

        scale_levels = [s for s in (filters.get("scale_levels") or []) if s]
        if scale_levels and detail.get("scale") not in scale_levels:
            return f"skip_scale:{detail.get('scale') or '未读到'}"

        stage_levels = [s for s in (filters.get("stage_levels") or []) if s]
        if stage_levels and detail.get("stage") not in stage_levels:
            return f"skip_stage:{detail.get('stage') or '未读到'}"

        required = [s for s in (filters.get("welfare_required") or []) if s]
        welfare_text = " ".join(detail.get("welfare") or [])
        for word in required:
            if word not in welfare_text:
                return f"skip_welfare:缺少{word}"

        recruiter_blacklist = [s for s in (filters.get("recruiter_blacklist", []) or []) if s]
        # 配了黑名单却没读到招聘者身份，无法确认不在黑名单里，跳过而不是放行。
        if recruiter_blacklist and not detail.get("recruiterRole"):
            return "skip_recruiter:未读到"
        for bad in recruiter_blacklist:
            if bad in detail.get("recruiterRole"):
                return f"skip_recruiter:{detail.get('recruiterRole')}"

        # 点击 "立即沟通" / "继续沟通"
        btn = page.locator("a.btn-startchat").first
        try:
            btn.wait_for(state="visible", timeout=8000)
        except PWTimeout:
            return "no_chat_button"

        text = (btn.inner_text() or "").strip()
        if "继续沟通" in text:
            # 已经沟通过，跳过不重复打招呼
            return "already_chatted"

        btn.click()
        human_sleep(3, jitter=0.2)

        if detect_verify(page):
            return "verify_required", page

        # 每天沟通次数用完后 Boss 弹「今日沟通已达上限」，继续点也不会发出去。
        try:
            if page.locator("text=今日沟通已达上限").first.count() > 0:
                return "daily_chat_limit"
        except Exception:
            pass

        # 每天沟通满 120 次后，Boss 会弹「还剩30次沟通机会」的温馨提示，
        # 不点下面的「好」按钮，后续沟通都不会真正发出。
        try:
            sure = page.locator(".greet-pop .btn-sure").first
            sure.wait_for(state="visible", timeout=3000)
            sure.click()
            log("已关闭沟通次数提示弹窗")
            human_sleep(1, jitter=0.2)
        except PWTimeout:
            pass

        # 点「立即沟通」后弹出的是一条待发的招呼语，输入框里预填着账号的默认
        # 招呼，确认后只发这一条，不会自动先发一条再补一条。配置了招呼语就把
        # 输入框改成它再发送；输入框没出现说明这次没有可编辑的招呼，不额外发。
        greeting = (cfg.get("greeting") or "").strip()
        if greeting:
            try:
                chat_input = page.locator(
                    ".chat-input, textarea[class*=chat], textarea.input-area").first
                chat_input.wait_for(state="visible", timeout=4000)
                chat_input.fill(greeting)
                page.locator(".chat-op .btn-send, .startchat-content button:has-text('发送')").first.click()
                human_sleep(1, jitter=0.2)
            except PWTimeout:
                log("没有出现招呼语输入框，本次按页面默认处理")
            except Exception as e:
                log(f"填写招呼语失败({type(e).__name__})")

        # 勾了自动收藏就点详情页侧边的收藏按钮，失败不影响投递结果。
        if cfg.get("filters", {}).get("auto_favorite"):
            try:
                fav = page.locator("a[ka='side_interest']").first
                fav.wait_for(state="visible", timeout=3000)
                fav.click()
                log("已收藏该岗位")
            except Exception as e:
                log(f"收藏失败({type(e).__name__})，不影响本次投递")

        # 「已向BOSS发送消息」弹窗不是每次都出现，不能拿它当成功依据。
        # 两个可靠标志，出现任一即可：
        # 1. 详情页沟通按钮从「立即沟通」变成「继续沟通」。
        #    不能用 has-text('继续沟通')，弹窗里的「留在此页继续沟通」会抢先匹配。
        # 2. 页面跳进了聊天页 /web/geek/chat。每天沟通满 120 次后点掉
        #    「还剩30次」提示，Boss 会直接把页面导航到聊天页，按钮随之消失。
        try:
            page.wait_for_function(
                """() => location.pathname.startsWith('/web/geek/chat') ||
                       [...document.querySelectorAll('a.btn-startchat')].some(
                           el => el.offsetParent && el.innerText.includes('继续沟通'))""",
                timeout=8000)
        except PWTimeout:
            log("按钮没有变成继续沟通，也没有进入聊天页，本次不算成功")
            return "send_unconfirmed"

        # 弹窗出现了就关掉，没出现不影响结果。
        try:
            stay_btn = page.locator("a:has-text('留在此页'), button:has-text('留在此页')").first
            stay_btn.wait_for(state="visible", timeout=2000)
            stay_btn.click()
        except Exception:
            pass

        return "success"
    except PWTimeout:
        return "timeout"
    except Exception as e:
        return f"error:{type(e).__name__}"
    finally:
        # 触发验证码时页面要留给用户操作，由调用方等验证过后再关。
        try:
            if page and not page.is_closed() and not detect_verify(page):
                page.close()
        except Exception:
            pass


def _apply_list(active_page, context: BrowserContext, cfg: dict, keyword: str, city_name: str,
               applied_keys: set, counters: dict, stop_event, max_apply) -> bool:
    """在一个已经打开的岗位列表页上投递。返回 True 表示本轮该结束了。

    counters 里的 today_done、sent_this_run 由调用方读，sent_this_run 在这里累加。
    """
    daily_limit = int(cfg.get("daily_limit", 30))
    interval = float(cfg.get("interval_seconds", 50))
    seen_hrefs: set[str] = set()
    stale_rounds = 0
    while stale_rounds < 3:
        if counters["today_done"] + counters["sent_this_run"] >= daily_limit or (
                max_apply is not None and counters["sent_this_run"] >= max_apply):
            log("达到上限，结束本轮。")
            return True
        try:
            cards = extract_cards(active_page)
        except PWTimeout:
            log("列表未加载出卡片，换下一个搜索。")
            return False

        fresh = [c for c in cards if c.get("href") and c["href"] not in seen_hrefs]
        if not fresh:
            stale_rounds += 1
        else:
            stale_rounds = 0
        for c in fresh:
            seen_hrefs.add(c["href"])

        log(f"本屏 {len(cards)} 个卡片，新出现 {len(fresh)} 个")
        for card in fresh:
            if stop_event and stop_event.is_set():
                log("收到停止信号，结束本轮。")
                return True
            if counters["today_done"] + counters["sent_this_run"] >= daily_limit or (
                    max_apply is not None and counters["sent_this_run"] >= max_apply):
                log("达到上限，结束本轮。")
                return True

            reason = should_skip(card, cfg, applied_keys)
            if reason:
                log(f"  跳过 [{card.get('company')}] {card.get('title')} - {reason}")
                continue

            log(f"  投递 [{card.get('company')}] {card.get('title')} "
                f"{card.get('salary')} {card.get('area')}")
            result = apply_one(context, card, cfg, keyword, city_name)
            # 触发验证码时返回 (状态, 详情页)，页面留着等用户解验证。
            verify_page = None
            if isinstance(result, tuple):
                status, verify_page = result
            else:
                status = result
            log(f"    -> {status}")

            if status == "verify_required":
                log("!! 触发安全验证，请在弹出的详情页里手动完成验证...")
                log("   验证通过后将自动继续投递（等待中...）")
                # 验证码在详情页上，必须查这个页面，查搜索页会误判已通过。
                waited = 0
                while waited < 300:
                    if stop_event and stop_event.is_set():
                        log("收到停止信号，结束本轮。")
                        return True
                    time.sleep(3)
                    waited += 3
                    try:
                        if verify_page and not detect_verify(verify_page):
                            log("验证已通过，继续投递...")
                            break
                    except Exception:
                        pass
                else:
                    log("等待验证超时(5分钟)，结束本轮。")
                    try:
                        if verify_page:
                            verify_page.close()
                    except Exception:
                        pass
                    return True
                try:
                    if verify_page:
                        verify_page.close()
                except Exception:
                    pass
                # 验证期间这个岗位没有投出去，不能跳过，重投一次。
                # 重投结果覆盖本次状态，这样记录里记的是最终结果。
                log(f"  重新投递 [{card.get('company')}] {card.get('title')}")
                status = apply_one(context, card, cfg, keyword, city_name)
                if isinstance(status, tuple):
                    status = status[0]
                    log("验证后重投仍要求验证，本轮结束，请手动处理后再运行。")
                    log(f"    -> {status}")
                    return True
                log(f"    -> {status}")

            if status.startswith("skip_category:"):
                bad = status[len("skip_category:"):]
                log(f"  跳过 [{card.get('company')}] {card.get('title')} - 岗位类别({bad})")
                record_category(bad, card.get("title", ""), card.get("company", ""), "已排除")
                continue

            if status.startswith("skip_activity:"):
                activity = status[len("skip_activity:"):]
                log(f"  跳过 [{card.get('company')}] {card.get('title')} - 招聘者不活跃({activity})")
                continue

            skipped = False
            for prefix, label in (("skip_industry:", "公司行业"), ("skip_scale:", "公司规模"),
                                  ("skip_stage:", "融资阶段"), ("skip_welfare:", "福利"),
                                  ("skip_recruiter:", "招聘者身份")):
                if status.startswith(prefix):
                    log(f"  跳过 [{card.get('company')}] {card.get('title')} - "
                        f"{label}({status[len(prefix):]})")
                    skipped = True
                    break
            if skipped:
                continue

            # 失败（超时、验证码、找不到按钮）也记一笔，方便事后看，
            # 但不进去重集合，下次运行还能再试。
            record_applied(
                title=card.get("title", ""),
                company=card.get("company", ""),
                salary=card.get("salary", ""),
                city=city_name,
                keyword=keyword,
                status=status,
                url=card.get("href", ""),
            )
            if status == "success":
                record_category(card.get("category", ""), card.get("title", ""),
                                card.get("company", ""), "已投")
                applied_keys.add(job_key(card.get("href", ""), card.get("company", ""),
                                         card.get("title", "")))

            if status == "success":
                counters["sent_this_run"] += 1
                if max_apply is not None and counters["sent_this_run"] >= max_apply:
                    log(f"本次已投递 {counters['sent_this_run']} 个，达到试跑上限，结束。")
                    return True

            if status == "daily_chat_limit":
                log("今日沟通次数已用完，结束本轮。")
                return True

            if stop_event and stop_event.is_set():
                log("收到停止信号，结束本轮。")
                return True

            if human_sleep(interval, jitter=0.3, stop_event=stop_event):
                log("收到停止信号，结束本轮。")
                return True

        try:
            active_page.mouse.wheel(0, 2500)
        except Exception:
            return False
        human_sleep(2, jitter=0.3)
    return False


def run(stop_event: threading.Event | None = None,
       on_ready: Callable | None = None,
       max_apply: int | None = None) -> None:
    """主投递流程。stop_event 可用于外部中止，on_ready 在 Edge 启动后回调。

    max_apply 限制本次运行最多成功投递几个，不影响每日上限，给试跑用。
    """
    cfg = load_config()

    daily_limit = int(cfg.get("daily_limit", 30))
    interval = float(cfg.get("interval_seconds", 50))
    today_done = today_applied_count()
    log(f"今日已投递: {today_done} / {daily_limit}")

    if today_done >= daily_limit:
        log("今日已达上限，退出。")
        return

    applied_keys = load_applied_keys()
    browser_cfg = cfg.get("browser", {})

    # 先启动 Edge（不连接 patchright，避免干扰 target=_blank 等正常导航）
    if _port_open(CDP_PORT) and not _edge_owns_port():
        log(f"端口 {CDP_PORT} 被别的调试浏览器占用，不是本工具启动的 Edge，退出。")
        return
    if not _port_open(CDP_PORT):
        log("正在启动 Edge...")
        start_edge()
        log("Edge 已启动（当前未被 patchright 接管，浏览器正常可用）")
    else:
        log("Edge 已在运行，跳过启动。")

    if on_ready:
        on_ready()
    else:
        print("=" * 60)
        print("请你自己在当前 Edge 窗口里完成以下动作：")
        print("  1. 输入 www.zhipin.com 进入 Boss 直聘")
        print("  2. 登录自己的账号")
        print("  3. 搜索想投递的关键词和城市，打开职位列表页")
        print("  4. 确认已经可以看到岗位列表后，回到终端按回车开始投递。")
        print("=" * 60)
        input(">>> 识别到岗位列表后按回车开始：")

    with sync_playwright() as p:
        log("patchright 正在接管浏览器...")
        context = connect_to_edge(p, slow_mo=browser_cfg.get("slow_mo", 100))
        log("已接管")

        keywords = [k for k in (cfg.get("keywords") or []) if k]
        cities = cfg.get("cities") or {}

        counters = {"today_done": today_done, "sent_this_run": 0}
        stop = False

        # 没填关键词时不自己搜，直接投你在浏览器里已经打开的那个岗位列表。
        if not keywords:
            active_page = _pick_job_list_page(context)
            if active_page is None:
                log("没有搜索关键词，也没有找到已打开的 Boss 岗位列表页。")
                log("先在浏览器里搜索出岗位列表，再点开始投递。")
                return
            if detect_verify(active_page):
                log("当前页面是安全验证，请在浏览器里手动完成后再点开始投递。")
                return
            if not check_login(active_page):
                log("未登录 Boss，请先在浏览器里登录后再点开始投递。")
                return
            log(f"未设置搜索关键词，直接投递当前打开的列表页：{active_page.url}")
            _apply_list(active_page, context, cfg, "", "当前页面",
                        applied_keys, counters, stop_event, max_apply)
            log(f"本次运行投递成功 {counters['sent_this_run']} 个；今日累计 "
                f"{today_done + counters['sent_this_run']} / {daily_limit}")
            log("脚本执行完毕。Edge 窗口保持打开，你可以继续用或手动关闭。")
            return

        if not cities:
            log("config.yaml 里没有 cities，无法搜索，退出。")
            return

        for keyword in keywords:
            if stop:
                break
            for city_name, city_code in cities.items():
                if stop or counters["today_done"] + counters["sent_this_run"] >= daily_limit or (
                        max_apply is not None and counters["sent_this_run"] >= max_apply):
                    stop = True
                    break
                url = build_search_url(keyword, str(city_code), cfg.get("filters", {}))
                log(f"搜索 [{city_name}] {keyword}")
                active_page = context.new_page()
                try:
                    active_page.goto(url, wait_until="domcontentloaded", timeout=30000)
                except Exception as e:
                    log(f"打开搜索页失败: {type(e).__name__}")
                    try:
                        active_page.close()
                    except Exception:
                        pass
                    continue

                # 安全验证页上没有登录按钮，先看验证再看登录，
                # 否则验证页会被当成已登录，拖到列表超时才跳过。
                if detect_verify(active_page):
                    log("打开搜索页时遇到安全验证，请在浏览器里手动完成后再点开始投递。")
                    stop = True
                    break

                if not check_login(active_page):
                    log("未登录 Boss，请先在浏览器里登录后再点开始投递。")
                    stop = True
                    break

                stop = _apply_list(active_page, context, cfg, keyword, city_name,
                                   applied_keys, counters, stop_event, max_apply)
                try:
                    active_page.close()
                except Exception:
                    pass

        log(f"本次运行投递成功 {counters['sent_this_run']} 个；今日累计 "
            f"{today_done + counters['sent_this_run']} / {daily_limit}")
        log("脚本执行完毕。Edge 窗口保持打开，你可以继续用或手动关闭。")


def _pick_job_list_page(context: BrowserContext):
    """从已打开的标签页里挑出一个 Boss 列表页：
    优先包含 '/web/geek/job' 或 '/job/' 的页面；
    其次返回任意一个 zhipin.com 页面。
    """
    best = None
    for p in context.pages:
        try:
            u = p.url or ""
        except Exception:
            continue
        if "zhipin.com" not in u:
            continue
        if "/web/geek/job" in u or "/job/" in u:
            return p
        best = best or p
    return best


if __name__ == "__main__":
    run()
"""首次登录脚本：启动独立资料目录的 Edge，你手动登录 Boss 直聘。

登录态直接保存在data/edge_user_data 里，以后不用重复登录。
"""
from __future__ import annotations

from patchright.sync_api import sync_playwright

from browser_launcher import launch_context


def main() -> None:
    with sync_playwright() as p:
        context = launch_context(p, headless=False, slow_mo=50)
        page = context.pages[0] if context.pages else context.new_page()

        try:
            page.goto("about:blank", wait_until="domcontentloaded", timeout=10000)
            print("已打开普通 Edge 页面。请你手动搜索 Boss 直聘并完成登录。")
        except Exception:
            print("已启动 Edge。请你手动打开 Boss 直聘并完成登录。")

        print("=" * 60)
        print("请在浏览器里手动搜索 Boss 直聘并登录（扫码 / 手机号验证码均可）。")
        print("登录成功、看到首页后，回到这里按回车。")
        print("=" * 60)
        input(">>> 登录完成后按回车：")

        print("登录完成，可以关闭此窗口。")
        context.close()


if __name__ == "__main__":
    main()

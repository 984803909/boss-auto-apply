"""统一的浏览器启动器：手动启动系统 Edge，通过 CDP 连接。

说明：
  1. 用 subprocess 正常启动系统 Edge（保留系统代理、扩展等）
  2. 通过 --remote-debugging-port 让 patchright 连接
  3. 使用独立资料目录 data/edge_user_data，登录态会保存
"""
from __future__ import annotations

import os
import sys
import socket
import subprocess
import time
from patchright.sync_api import Browser, BrowserContext, Playwright

if getattr(sys, 'frozen', False):
    BASE = os.path.dirname(sys.executable)
else:
    BASE = os.path.dirname(__file__)

PROFILE_DIR = os.path.join(BASE, "data", "edge_user_data")
EDGE_PATH_X86 = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
EDGE_PATH_X64 = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
EDGE_PATH = EDGE_PATH_X86 if os.path.exists(EDGE_PATH_X86) else EDGE_PATH_X64
CDP_PORT = 9222


def _port_open(port: int, timeout: float = 1.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _port_owner_command() -> str:
    """返回占用 9222 的进程命令行，查不到返回空串。"""
    script = (
        "$conn = Get-NetTCPConnection -LocalPort 9222 -State Listen "
        "-ErrorAction SilentlyContinue | Select-Object -First 1; "
        "if (-not $conn) { exit 0 }; "
        "(Get-CimInstance Win32_Process -Filter \"ProcessId=$($conn.OwningProcess)\").CommandLine"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            timeout=8,
        )
    except Exception:
        return ""
    return result.stdout.decode("utf-8", "ignore")


def _edge_owns_port() -> bool:
    """9222 上是不是可以接管的 Edge。

    本工具自己启动的 Edge（命令行带资料目录）直接算。
    另外，之前手动开过调试端口、里面已经登录 Boss 直聘的 Edge 也算：
    资料目录可能不在本程序目录下（比如从别的目录跑过一次），
    只要是 Edge、开着调试端口、页面里有 zhipin.com，就复用，不重复开窗口。
    端口上是别的程序，或是 Edge 但没打开 Boss，不算。
    """
    command = _port_owner_command()
    if not command:
        return False
    if PROFILE_DIR.lower() in command.lower():
        return True
    if "msedge" not in command.lower() or "--remote-debugging-port" not in command.lower():
        return False
    try:
        import json
        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/list", timeout=4) as r:
            tabs = json.loads(r.read().decode("utf-8", "ignore"))
    except Exception:
        return False
    return any("zhipin.com" in (tab.get("url") or "") for tab in tabs)


def _cleanup_profile_processes() -> None:
    target = PROFILE_DIR.replace("'", "''")
    script = (
        f"$target = '{target}'; "
        "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | "
        "Where-Object { $_.CommandLine -like ('*' + $target + '*') } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            check=False,
            timeout=5
        )
    except Exception:
        pass
    time.sleep(1)
    for name in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
        path = os.path.join(PROFILE_DIR, name)
        try:
            os.remove(path)
        except OSError:
            pass


def start_edge() -> None:
    """启动系统 Edge，开启 CDP 端口，但不连接 patchright。"""
    os.makedirs(PROFILE_DIR, exist_ok=True)
    _cleanup_profile_processes()

    cmd = [
        EDGE_PATH,
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={PROFILE_DIR}",
    ]
    subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    )

    for _ in range(30):
        if _port_open(CDP_PORT):
            return
        time.sleep(1)
    raise RuntimeError(f"Edge CDP 端口 {CDP_PORT} 未就绪")


def connect_to_edge(p: Playwright, slow_mo: int = 50) -> BrowserContext:
    """用户完成登录+搜索后调用，patchright 此时才接管。"""
    browser: Browser = p.chromium.connect_over_cdp(
        f"http://127.0.0.1:{CDP_PORT}",
        slow_mo=slow_mo,
    )
    context = browser.contexts[0]
    return context


def launch_context(p: Playwright, headless: bool = False,
                   slow_mo: int = 50) -> BrowserContext:
    """兼容旧接口：一次性完成启动+连接（不推荐，会干扰 target=_blank）。"""
    start_edge()
    return connect_to_edge(p, slow_mo=slow_mo)

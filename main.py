"""Discord 車牌查詢機器人
====================================================
- 系統匣 (pystray) ➜ 可多次切換 Console 顯示 / 隱藏
- Selenium + HiNet 小額付費查詢車籍
  ├ (1) 汽車：!car  <車牌>
  └ (5) 機車：!moto <車牌>
- !shutdown 關閉機器人（限 config.json 指定使用者）

依賴：
    pip install discord.py selenium webdriver-manager pystray pillow
"""
from __future__ import annotations

import asyncio, base64, json, os, platform, sys, tempfile, threading
from pathlib import Path
from typing import Final, Tuple

import discord
from discord.ext import commands
from PIL import Image
import pystray                           # ✅ 型別註解用 pystray.Icon
from pystray import Menu, MenuItem
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# ============================================================
# 設定檔 (exe 與原始碼兩種情況都能找到)
# ============================================================
BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
CONFIG_PATH: Final = BASE_DIR / "config.json"

if not CONFIG_PATH.exists():
    CONFIG_PATH.write_text(json.dumps({
        "bot_token": "YOUR_DISCORD_BOT_TOKEN",
        "hinet_uid": "HINET_ID",
        "hinet_pwd": "HINET_PASSWORD",
        "owner_id": 123456789012345678
    }, ensure_ascii=False, indent=2))
    print(f"已產生範例 {CONFIG_PATH.name}，請填完再啟動！")
    sys.exit(1)

CFG = json.loads(CONFIG_PATH.read_text("utf-8"))
BOT_TOKEN: Final[str] = CFG["bot_token"]
OWNER_ID:  Final[int] = int(CFG["owner_id"])

# ============================================================
# Selenium 共用設定
# ============================================================
CHROME_OPTS = ChromeOptions()
CHROME_OPTS.add_argument("--headless=new")
CHROME_OPTS.add_argument("--disable-gpu")
CHROME_OPTS.add_argument("--no-sandbox")
CHROME_OPTS.add_experimental_option("excludeSwitches", ["enable-logging"])

# ============================================================
# Discord Bot
# ============================================================
import logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")

intents             = discord.Intents.default()
intents.message_content = True          # ⚠️ Developer Portal 也要勾
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    logging.info(f"✅ 已登入 Discord：{bot.user} (id={bot.user.id})")

@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    logging.error(f"指令錯誤：{error}")
    await ctx.send(f"❌ {error}")

# ============================================================
# Console 顯示 / 隱藏
# ============================================================
import ctypes
SW_HIDE, SW_SHOW, SW_RESTORE = 0, 5, 9

def _get_console_hwnd() -> int | None:
    return ctypes.windll.kernel32.GetConsoleWindow() if platform.system()=="Windows" else None

def hide_console():            # 啟動時先調用
    hwnd = _get_console_hwnd()
    if hwnd: ctypes.windll.user32.ShowWindow(hwnd, SW_HIDE)

def show_console(to_front: bool = True):
    hwnd = _get_console_hwnd()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
        if to_front:
            ctypes.windll.user32.SetForegroundWindow(hwnd)

def toggle_console(menu_item: MenuItem):
    hwnd = _get_console_hwnd()
    if not hwnd:
        return
    visible = ctypes.windll.user32.IsWindowVisible(hwnd)
    if visible:
        hide_console()
        menu_item.text = "顯示主控台"
    else:
        show_console()
        menu_item.text = "隱藏主控台"
    menu_item.icon.update_menu()     # 即時刷新

# -------------------- 系統匣 --------------------
import ctypes, platform
from pystray import Menu, MenuItem
from PIL import Image
import asyncio, os, sys

SW_HIDE, SW_SHOW, SW_RESTORE = 0, 5, 9

def _console_hwnd() -> int | None:
    """取得目前 Console 的視窗句柄 (HWND)；找不到回傳 None"""
    return ctypes.windll.kernel32.GetConsoleWindow() if platform.system() == "Windows" else None

def hide_console() -> None:
    if hwnd := _console_hwnd():
        ctypes.windll.user32.ShowWindow(hwnd, SW_HIDE)

def show_console() -> None:
    if hwnd := _console_hwnd():
        ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
        ctypes.windll.user32.SetForegroundWindow(hwnd)

def toggle_console() -> None:
    """若可見→隱藏；若隱藏→顯示"""
    if hwnd := _console_hwnd():
        is_visible = ctypes.windll.user32.IsWindowVisible(hwnd)
        if is_visible:
            hide_console()
        else:
            show_console()

async def shutdown() -> None:
    await bot.close()
    os._exit(0)

def create_tray_icon(loop: asyncio.AbstractEventLoop) -> pystray.Icon:  # type: ignore
    logo = Image.new("RGB", (64, 64), "#4C6EF5")
    return pystray.Icon(
        "CarCrawlerBot",
        logo,
        menu=Menu(
            MenuItem("顯示 / 隱藏主控台", lambda *_: toggle_console()),
            MenuItem(
                "離開",
                lambda *_: loop.call_soon_threadsafe(asyncio.create_task, shutdown()),
            ),
        ),
    )

# ============================================================
# Selenium 查詢核心
# ============================================================
def _decode_base64_image(src: str, plate: str) -> str | None:
    if not src.startswith("data:image"):
        return None
    header, b64 = src.split(",", 1)
    ext = ".png" if "png" in header else ".jpg"
    p = Path(tempfile.gettempdir())/f"{plate}{ext}"
    p.write_bytes(base64.b64decode(b64))
    return str(p)

def _query_plate(plate: str, qmode: str) -> Tuple[str, str|None]:
    uid, pwd = CFG["hinet_uid"], CFG["hinet_pwd"]
    driver   = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()),
                                options=CHROME_OPTS)
    wait = WebDriverWait(driver, 30)
    try:
        driver.get("https://mvdvan.mvdis.gov.tw/mvdvan/mvdvan")
        wait.until(EC.element_to_be_clickable((By.ID,"searchType"))).click()
        driver.find_element(By.CSS_SELECTOR, f"#searchType option[value='{qmode}']").click()
        driver.find_element(By.ID,"input_1").send_keys(plate)
        driver.find_element(By.ID,"notcgi_submit").click()

        # HiNet 認證
        wait.until(EC.url_contains("hinet.net"))
        driver.find_element(By.ID,"aa-uid").send_keys(uid)
        driver.find_element(By.ID,"aa-passwd").send_keys(pwd)
        driver.find_element(By.ID,"submit_hn").click()

        # 結果
        wait.until(EC.url_contains("mvdvan#anchor"))
        wait.until(EC.presence_of_element_located((By.CLASS_NAME,"pane_result")))
        container   = driver.find_element(By.CLASS_NAME,"pane_result")
        result_text = container.text.strip()

        img_path = None
        try:
            img = container.find_element(By.CSS_SELECTOR,"img[src^='data:image']")
            img_path = _decode_base64_image(img.get_attribute("src"), plate)
        except Exception:
            pass
        return result_text, img_path
    finally:
        driver.quit()

async def query_and_send(ctx: commands.Context, plate: str, qmode:str, label:str):
    async with ctx.typing():
        loop = asyncio.get_running_loop()
        text, img_path = await loop.run_in_executor(None, _query_plate, plate.upper(), qmode)
        embed = discord.Embed(title=f"{label} 查詢結果",
                              description=text or "（無結果）",
                              color=0x4C6EF5)
        files: list[discord.File] = []
        if img_path and Path(img_path).exists():
            files.append(discord.File(img_path, filename="result.png"))
            embed.set_image(url="attachment://result.png")
        await ctx.send(embed=embed, files=files)

# ------------------------------------------------------------
# Bot 指令
# ------------------------------------------------------------
@bot.command(name="car",  help="查詢汽車車籍")
async def car_cmd(ctx: commands.Context, plate:str):
    if not ctx.author.bot:
        await query_and_send(ctx, plate, "1", "汽車車籍")

@bot.command(name="moto", help="查詢機車車籍")
async def moto_cmd(ctx: commands.Context, plate:str):
    if not ctx.author.bot:
        await query_and_send(ctx, plate, "5", "機車車籍")

@bot.command(name="shutdown", aliases=["關閉"], help="關閉機器人（限擁有者）")
async def shutdown_cmd(ctx: commands.Context):
    if ctx.author.id != OWNER_ID:
        await ctx.send("❌ 你沒有權限使用此指令。"); return
    await ctx.send("🛑 機器人關閉中…")
    await shutdown()

# ============================================================
# 主程式
# ============================================================
def main():
    loop = asyncio.get_event_loop()
    tray = create_tray_icon(loop)
    threading.Thread(target=tray.run, daemon=True).start()

    hide_console()       # 一啟動就藏

    try:
        loop.run_until_complete(bot.start(BOT_TOKEN))
    except discord.PrivilegedIntentsRequired:
        print("❗ 請到 Developer Portal → Bot → Privileged Gateway Intents 勾選 Message Content Intent")
    finally:
        tray.stop()
        loop.run_until_complete(bot.close())

if __name__ == "__main__":
    main()

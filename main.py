"""Discord 車牌查詢機器人
====================================================
!car  <車牌>   汽車查詢
!moto <車牌>   機車查詢
!shutdown      關閉（限 owner）
依賴：pip install discord.py selenium webdriver-manager pystray pillow
"""
from __future__ import annotations
import asyncio, base64, json, os, platform, sys, tempfile, threading, logging, ctypes
from pathlib import Path
from typing import Final, Tuple

# ---------- Discord ----------
import discord
from discord.ext import commands
# ---------- 系統匣 ----------
import pystray
from pystray import Menu, MenuItem
from PIL import Image
# ---------- Selenium ----------
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
# ------------------------------------------------------------

# ==================== 設定檔 ====================
BASE_DIR    = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"

if not CONFIG_PATH.exists():
    CONFIG_PATH.write_text(json.dumps({
        "bot_token": "YOUR_DISCORD_BOT_TOKEN",
        "hinet_uid": "HINET_ID",
        "hinet_pwd": "HINET_PASSWORD",
        "owner_id": 123456789012345678
    }, ensure_ascii=False, indent=2))
    print("已產生範例 config.json，請填完再啟動！")
    sys.exit(1)

_cfg        = json.loads(CONFIG_PATH.read_text("utf-8"))
BOT_TOKEN   = _cfg["bot_token"]
OWNER_ID    = int(_cfg["owner_id"])

# ==================== Selenium 共用設定 ====================
CHROME_OPTS = ChromeOptions()
CHROME_OPTS.add_argument("--headless=new")  # ←需要背景執行再打開
CHROME_OPTS.add_argument("--disable-gpu")
CHROME_OPTS.add_argument("--no-sandbox")
CHROME_OPTS.add_experimental_option("excludeSwitches", ["enable-logging"])

# ==================== Discord Bot ====================
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
intents = discord.Intents.default(); intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready(): logging.info(f"✅ 已登入 Discord：{bot.user} (id={bot.user.id})")
@bot.event
async def on_command_error(ctx, err): logging.error(err); await ctx.send(f"❌ {err}")

# ==================== Console 顯示 / 隱藏 ====================
SW_HIDE, SW_RESTORE = 0, 9
def _hwnd(): return ctypes.windll.kernel32.GetConsoleWindow() if platform.system()=="Windows" else None
def hide_console():  h=_hwnd(); h and ctypes.windll.user32.ShowWindow(h, SW_HIDE)
def show_console():  h=_hwnd(); h and (ctypes.windll.user32.ShowWindow(h, SW_RESTORE), ctypes.windll.user32.SetForegroundWindow(h))
async def _shutdown(): await bot.close(); os._exit(0)
def _tray(loop) -> pystray.Icon:  # type: ignore
    ico = Image.new("RGB",(64,64),"#4C6EF5")
    return pystray.Icon("PlateBot", ico, menu=Menu(
        MenuItem("顯示 / 隱藏主控台", lambda *_: show_console() if not ctypes.windll.user32.IsWindowVisible(_hwnd()) else hide_console()),
        MenuItem("離開", lambda *_: loop.call_soon_threadsafe(asyncio.create_task,_shutdown()))))

# ==================== Selenium 核心 ====================
def _decode_img(src:str, plate:str)->str|None:
    if not src.startswith("data:image"): return None
    ext = ".png" if "png" in src.split(",",1)[0] else ".jpg"
    p = Path(tempfile.gettempdir())/f"{plate}{ext}"
    p.write_bytes(base64.b64decode(src.split(",",1)[1])); return str(p)

def _query_plate(plate:str, qmode:str)->Tuple[str,str|None]:
    uid,pwd = _cfg["hinet_uid"], _cfg["hinet_pwd"]
    drv = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=CHROME_OPTS)
    w   = WebDriverWait(drv,30)
    try:
        drv.get("https://mvdvan.mvdis.gov.tw/mvdvan/mvdvan")
        w.until(EC.element_to_be_clickable((By.ID,"searchType"))).click()
        drv.find_element(By.CSS_SELECTOR,f"#searchType option[value='{qmode}']").click()
        drv.find_element(By.ID,"input_1").send_keys(plate)
        drv.find_element(By.ID,"notcgi_submit").click()

        # ---------- HiNet 登入 ----------
        w.until(EC.url_contains("hinet.net"))
        drv.find_element(By.ID,"aa-uid").send_keys(uid)
        drv.find_element(By.ID,"aa-passwd").send_keys(pwd)
        drv.find_element(By.ID,"submit_hn").click()

        # ---------- 等成功頁 or 合約額度不足頁 ----------
        def _either(d):
            return (d.find_elements(By.CLASS_NAME,"pane_result") or
                    d.find_elements(By.CSS_SELECTOR,"table.contract"))
        try:
            w.until(_either)
        except TimeoutException:
            return "⚠️ 等待網站回應逾時，請稍後再試。", None

        # 若看到 table.contract => 餘額不足 / 額度用盡
        if drv.find_elements(By.CSS_SELECTOR,"table.contract"):
            return "⚠️ HiNet 點數不足或本月額度已用盡，請儲值後再試。", None

        # ---------- 正常結果 ----------
        cont = drv.find_element(By.CLASS_NAME,"pane_result")
        res  = cont.text.strip()
        img_path = None
        try:
            img = cont.find_element(By.CSS_SELECTOR,"img[src^='data:image']")
            img_path = _decode_img(img.get_attribute("src"), plate)
        except Exception: pass
        return res, img_path
    finally:
        threading.Thread(target=drv.quit, daemon=True).start()

async def _send(ctx,label,qmode,plate):
    async with ctx.typing():
        loop = asyncio.get_running_loop()
        txt, img = await loop.run_in_executor(None, _query_plate, plate.upper(), qmode)
        emb = discord.Embed(title=f"{label} 查詢結果", description=txt or "（無結果）", color=0x4C6EF5)
        files=[]
        if img and Path(img).exists():
            files.append(discord.File(img, filename="result.png"))
            emb.set_image(url="attachment://result.png")
        await ctx.send(embed=emb, files=files)

# ==================== Bot 指令 ====================
@bot.command(name="car", help="查詢汽車車籍")
async def _car(ctx: commands.Context, plate: str):
    if ctx.author.bot:
        return
    await _send(ctx, "汽車車籍", "1", plate)

@bot.command(name="moto", help="查詢機車車籍")
async def _moto(ctx: commands.Context, plate: str):
    if ctx.author.bot:
        return
    await _send(ctx, "機車車籍", "5", plate)

@bot.command(name="shutdown", aliases=["關閉"], help="關閉機器人（限擁有者）")
async def _bye(ctx: commands.Context):
    if ctx.author.id != OWNER_ID:
        await ctx.send("❌ 你沒有權限使用此指令。")
        return
    await ctx.send("🛑 機器人關閉中…")
    await _shutdown()


# ==================== 進入點 ====================
def main():
    loop = asyncio.get_event_loop()
    tray = _tray(loop); threading.Thread(target=tray.run, daemon=True).start()
    hide_console()
    try:    loop.run_until_complete(bot.start(BOT_TOKEN))
    finally: tray.stop(); loop.run_until_complete(bot.close())

if __name__ == "__main__":
    main()

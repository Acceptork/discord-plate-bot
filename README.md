# discord-plate-bot
一款基於 Discord 的自動化車牌查詢機器人，透過 Selenium 自動登入 HiNet 小額付費服務，支援汽車與機車車籍查詢，並內建系統匣最小化與隱藏主控台功能。


功能介紹
- 自動登入 公路監理資訊網（MVDVAN）並查詢車籍資料
- 支援以下查詢模式：
  - `!car <車牌>`：查詢汽車最新車牌
  - `!moto <車牌>`：查詢機車最新車牌
- 查詢結果以 Embed 形式回覆，並附上官方回傳之車籍示意圖（如有）
- 啟動時最小化至系統匣（Windows），可從托盤選單喚回或關閉程式
- 支援單一 config.json 設定檔，首次啟動時自動產生範本

## 快速上手

## 使用 .exe 檔（Windows）

如果你已經用 PyInstaller 將程式打包成單一 `.exe`，可以直接在沒有安裝 Python 環境的 Windows 電腦上執行：

1. **準備檔案**  
   - `CarCrawlerBot.exe`（或你命名的可執行檔）  
   - 同目錄下放入 `icon.ico`（選填，若編譯時有指定就不必）  
   - 同目錄下放入 `config.json`（若第一次執行尚未產生，exe 會自動建立範本）

2. **第一次啟動**  
   > 若目錄下不存在 `config.json`，程式會自動建立範本並退出  
   - 雙擊 `CarCrawlerBot.exe`  
   - 看到「已產生範本 config.json，請填完再啟動！」就代表建立成功  

3. **填寫設定**  
   - 用記事本（Notepad）或任何文字編輯器打開 `config.json`  
   - 填入你的設定：  
     ```jsonc
     {
       "bot_token":    "YOUR_DISCORD_BOT_TOKEN",
       "hinet_uid":    "你的 HiNet 帳號",
       "hinet_pwd":    "你的 HiNet 密碼",
       "owner_id":     123456789012345678
     }
     ```
     owner_id為自己Discord帳號的ID，Discord程式左下角點自己的資訊後，按下複製使用者ID即可取得
     >若沒有顯示"複製使用者ID"，請開啟Discord開發者模式
     
   - 存檔後關閉編輯器

4. **再次啟動**  
   - 雙擊 `CarCrawlerBot.exe`  
   - 程式會隱藏主控台並最小化到系統匣  
   - 托盤（Tray）圖示右鍵 → **顯示主控台** 可查看日誌，或選 **離開** 完全關閉

> **Tip.**  
> - 若要保留 Console 輸出，不要使用 `--noconsole` 參數重新打包；  
> - 托盤圖示只能在程式運行中用滑鼠操作，不會在按下❌後自動關閉；  
> - 如需重新顯示或關閉主控台，可從托盤選單呼叫。


## 使用原始碼
1. **Clone 本專案**
   ```bash
   git clone https://github.com/YourUsername/discord-plate-bot.git
   cd discord-plate-bot
   ```
2. 安裝相依套件
   ```bash
   pip install discord.py selenium webdriver-manager pystray pillow
   ```
3. 首次執行
   ```bash
   python main.py
   ```
   會在專案根目錄自動產生範本 `config.json`
4. 編輯 `config.json`，填入以下內容：
   ```jsonc
   {
     "bot_token": "YOUR_DISCORD_BOT_TOKEN",
     "hinet_uid": "HINET_ID",
     "hinet_pwd": "YOUR_HINET_PASSWORD",
     "owner_id": 123456789012345678
   }
   ```

5. 啟動機器人
   ```bash
   python main.py
   ```
6. 邀請 Bot 加入伺服器
   - 前往 Discord Developer Portal → OAuth2 → URL Generator
   - 勾選 Scope: `bot`
   - 在 Bot Permissions 中勾選：Send Messages、Embed Links、Attach Files
   - 複製邀請連結並貼到瀏覽器完成邀請

進階：打包為 Windows 執行檔
```bash
pyinstaller --onefile --noconsole --icon=icon.ico main.py
```

注意事項
- 每次查詢都需透過 HiNet 小額付費服務，請留意使用頻率
- Bot 需在 Developer Portal 開啟 Message Content Intent
- 請勿公開分享 `config.json` 中的敏感資訊

本 README 由 ChatGPT 協助生成，歡迎修改與擴充！

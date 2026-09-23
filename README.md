# 台灣二手 MX-5 車源

每 6 小時自動整理 PTT CarShop、8891、abc好車網上的二手 MX-5，放在一個可以篩選的網頁上。整套使用 GitHub 的免費服務，不需要主機，也不需要買網域。

## 架設步驟（約 15 分鐘，只需要瀏覽器）

1. **註冊 GitHub 帳號**：到 https://github.com 免費註冊。
2. **建立 repository**：右上角「+」選「New repository」，名稱例如 `mx5`，選 **Public**（免費帳號的 GitHub Pages 需要公開 repo），按「Create repository」。
3. **上傳檔案**：在新 repo 頁面點「uploading an existing file」，把這個資料夾裡的**所有內容**拖進去（包含 `.github` 這個隱藏資料夾，Mac 按 `Cmd+Shift+.` 可以顯示隱藏檔），按「Commit changes」。
   - 如果 `.github` 拖不進去：在 repo 裡按「Add file → Create new file」，檔名輸入 `.github/workflows/update.yml`，把本機那個檔案的內容貼上後儲存。
4. **允許自動更新寫入資料**：Settings → Actions → General → 最下面「Workflow permissions」選 **Read and write permissions** → Save。
5. **開啟網站**：Settings → Pages → Source 選「Deploy from a branch」，Branch 選 `main`、資料夾選 `/docs` → Save。約 1 分鐘後頁面上方會出現網址，形式是 `https://你的帳號.github.io/mx5/`。
6. **先手動跑一次**：到 Actions 分頁，左邊點「更新 MX-5 車源」，右邊按「Run workflow」。約 3–5 分鐘跑完，重新整理網站就會看到完整結果。之後每 6 小時會自動執行。

把第 5 步的網址傳給朋友就完成了。

## 日常維護

- **某個來源沒資料**：網頁上方會出現提示。到 Actions 分頁點最近一次執行，可以看到哪個來源出錯。最常見的原因是對方網站改版，需要調整 `scraper/` 裡對應的檔案。
- **手動加入一台車**（例如朋友在其他地方看到的）：編輯 `manual_listings.json`，格式如下，存檔後下一輪更新就會出現：

  ```json
  [
    {
      "url": "https://example.com/car/123",
      "title": "2008 Mazda MX-5 NC 手排",
      "price": 45,
      "year": 2008,
      "mileage_km": 98000,
      "location": "台中市",
      "description": "原廠軟頂，剛換離合器",
      "image": "https://example.com/photo.jpg"
    }
  ]
  ```
  `price` 以「萬」為單位，除了 `url` 以外都可以省略。
- **排程被暫停**：GitHub 對公開 repo 的排程，若 repo 長時間沒有活動可能會自動停用，Actions 頁面會出現提示，按一下重新啟用即可。

## 各來源說明

| 來源 | 做法 | 備註 |
|---|---|---|
| PTT CarShop | 用看板搜尋 MX-5、MX5、Miata、Roadster，只收標題含 [售車] 的文章 | 只看最近 120 天的文章；標題有「已售」「已收訂」會標為已售出 |
| 8891 | 讀取 Mazda MX-5 車款列表，再開每台車的頁面 | 最穩定 |
| abc好車網 | 搜尋頁需要用無頭瀏覽器開啟，再讀每台車的頁面 | 若只抓到第一頁，是因為網站用分頁或延遲載入 |

程式在每次請求之間會等 1.5–3 秒，整輪大約幾十個請求，對來源網站的負擔很小。資料僅供朋友間參考，請勿商業使用；各網站的使用條款請自行留意。

## 在自己電腦上測試（選用）

```bash
pip install -r requirements.txt
python -m playwright install chromium
python -m scraper.run          # 抓一輪資料
python -m pytest               # 測試解析功能
cd docs && python -m http.server 8000   # 打開 http://localhost:8000 預覽網站
```

直接雙擊 `docs/index.html` 會讀不到資料，一定要透過上面的本機伺服器或 GitHub Pages 開啟。

## 檔案結構

```
.github/workflows/update.yml   每 6 小時執行的排程
scraper/                       抓取程式（ptt.py、s8891.py、abccar.py 各自獨立）
scraper/run.py                 合併新舊資料：記錄降價、新上架、已下架
docs/index.html                網站
docs/data/listings.json        網站讀取的資料（自動產生）
manual_listings.json           手動加入的車
tests/                         解析功能測試
```

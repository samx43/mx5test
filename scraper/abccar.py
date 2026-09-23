"""abc好車網（車商聯盟平台）：搜尋頁是 JavaScript 產生的，所以用無頭瀏覽器
取得車輛連結；每台車的詳細頁則是一般 HTML，直接讀取。"""
import html as htmllib
import re

from bs4 import BeautifulSoup

from .common import UA, clean_text, is_mx5, log, parse_mileage_km, parse_price_wan, parse_year

SEARCH_URL = "https://www.abccar.com.tw/search?tab=1&brand=108&series=389"
DETAIL_URL = "https://www.abccar.com.tw/Car/{}"
_ID = re.compile(r"/car/(\d+)", re.I)


def collect_ids():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("沒有安裝 Playwright，略過 abc好車網")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=UA, locale="zh-TW")
        page.goto(SEARCH_URL, wait_until="networkidle", timeout=60000)
        for _ in range(6):  # 往下捲動，觸發延遲載入
            page.mouse.wheel(0, 4000)
            page.wait_for_timeout(1200)
        hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
        browser.close()
    ids = []
    for h in hrefs:
        m = _ID.search(h)
        if m and m.group(1) not in ids:
            ids.append(m.group(1))
    return ids


def parse_detail(html):
    soup = BeautifulSoup(html, "html.parser")

    def meta(prop):
        t = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
        return htmllib.unescape(htmllib.unescape(t["content"])).strip() if t and t.get("content") else ""

    # 'Mazda MX-5 2017年 中古車(二手車) 83.8萬 - 鴻揚汽車 - abc好車網'
    og_title = meta("og:title")
    if not is_mx5(og_title):
        return None
    parts = [p.strip() for p in og_title.split(" - ")]
    head = parts[0]
    title = re.split(r"\s*中古車", head)[0]
    pm = re.search(r"(\d+(?:\.\d+)?)\s*萬", head)
    text = soup.get_text(" ", strip=True)
    km = re.search(r"行駛里程\s*([\d,]+)\s*公里", text)
    loc = re.search(r"所在地\s*([\u4e00-\u9fff]{2}[市縣])", text)
    desc = re.sub(r"\s*\|\s*abc好車網.*$", "", meta("og:description"))
    return {
        "title": title,
        "price": parse_price_wan(pm.group(0)) if pm else None,
        "year": parse_year(head),
        "mileage_km": parse_mileage_km(km.group(1) + "公里") if km else None,
        "location": loc.group(1) if loc else None,
        "seller": parts[1] if len(parts) > 2 else None,
        "description": clean_text(desc),
        "image": meta("og:image") or None,
    }


def scrape(fetcher, known):
    items = []
    for cid in collect_ids():
        url = DETAIL_URL.format(cid)
        html = fetcher.get(url)
        if not html:
            continue
        d = parse_detail(html)
        if not d:
            continue  # 搜尋頁上的推薦車款不是 MX-5
        items.append({
            "id": f"abccar-{cid}",
            "url": url,
            "title": d["title"],
            "price": d["price"],
            "year": d["year"],
            "mileage_km": d["mileage_km"],
            "location": d["location"],
            "description": d["description"],
            "images": [d["image"]] if d["image"] and "favico" not in d["image"] else [],
            "seller": d["seller"],
            "posted_at": None,
            "sold": False,
        })
    log.info("abc好車網：%d 筆", len(items))
    return items

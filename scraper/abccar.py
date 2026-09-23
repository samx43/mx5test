"""abc好車網（車商聯盟平台）：搜尋頁是 JavaScript 產生的，所以用無頭瀏覽器
取得車輛連結；每台車的詳細頁則是一般 HTML，直接讀取。"""
import html as htmllib
import re

from bs4 import BeautifulSoup

from . import browser
from .common import clean_text, is_mx5, log, parse_mileage_km, parse_price_wan, parse_year

SEARCH_URL = "https://www.abccar.com.tw/search?tab=1&brand=108&series=389"
DETAIL_URL = "https://www.abccar.com.tw/Car/{}"
_ID = re.compile(r"/car/(\d+)", re.I)


MAX_DETAILS = 30


def collect_ids():
    """搜尋頁是 JavaScript 產生的，用瀏覽器開啟後再取出車輛連結。"""
    html = browser.get_html(SEARCH_URL, wait_selector='a[href*="/Car/"], a[href*="/car/"]', scroll=6)
    if html is None:
        raise RuntimeError("搜尋頁開不起來（瀏覽器讀取失敗）")
    ids = []
    for m in _ID.finditer(html):
        if m.group(1) not in ids:
            ids.append(m.group(1))
    if not ids:
        raise RuntimeError("搜尋頁沒有抓到任何車輛連結，版面可能改了")
    log.info("abc好車網：找到 %d 個車輛連結", len(ids))
    return ids[:MAX_DETAILS]


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
    ids = collect_ids()
    items, blocked, not_mx5 = [], 0, 0
    for cid in ids:
        url = DETAIL_URL.format(cid)
        # 這個網站會擋掉一般的程式請求，車輛頁面也要用瀏覽器開
        html = browser.get_html(url)
        if not html:
            blocked += 1
            continue
        d = parse_detail(html)
        if not d:
            not_mx5 += 1
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
    log.info("abc好車網：%d 筆（%d 頁讀不到、%d 頁不是 MX-5）", len(items), blocked, not_mx5)
    if not items:
        raise RuntimeError(f"{len(ids)} 個連結都沒有解析成功（讀不到 {blocked} 頁、非 MX-5 {not_mx5} 頁）")
    return items

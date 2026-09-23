"""abc好車網（車商聯盟平台）：搜尋頁是 JavaScript 產生的，所以用無頭瀏覽器
取得車輛連結；每台車的詳細頁則是一般 HTML，直接讀取。"""
import html as htmllib
import re

from bs4 import BeautifulSoup

from . import browser
from .common import clean_text, is_mx5, log, parse_mileage_km, parse_price_wan, parse_year

# 只給 series 參數時，網站會忽略車款篩選、回傳整個 Mazda 品牌的車，
# 所以要帶上 SeriesGroup。依序嘗試，哪一個先抓到 MX-5 就用哪一個。
SEARCH_URLS = [
    "https://www.abccar.com.tw/Search?tab=1&brand=108&SeriesGroup=338&series=389",
    "https://www.abccar.com.tw/Search?tab=1&SearchType=1&brand=108&SeriesGroup=338&OrderByField=0",
    "https://www.abccar.com.tw/search?tab=1&brand=108&series=389",
]
DETAIL_URL = "https://www.abccar.com.tw/Car/{}"
_ID = re.compile(r"/car/(\d+)", re.I)


MAX_DETAILS = 30


def cards(html):
    """回傳 [(車輛編號, 卡片上的文字)]。卡片文字用來先篩掉別款車。"""
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        m = _ID.search(a["href"])
        if not m or len(m.group(1)) < 5 or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        node, text = a, a.get_text(" ", strip=True)
        for _ in range(4):  # 車名有時放在外層，往上找到最近一層有文字的祖先就停
            if len(text) >= 10:
                break
            node = node.parent
            if node is None:
                break
            text = node.get_text(" ", strip=True)
        out.append((m.group(1), clean_text(text, 120)))
    return out


def collect_ids():
    """搜尋頁是 JavaScript 產生的，用瀏覽器開啟後再取出車輛連結。"""
    tried, best = [], []
    for url in SEARCH_URLS:
        html = browser.get_html(url, wait_selector='a[href*="/Car/"], a[href*="/car/"]', scroll=6)
        if not html:
            tried.append(f"{url} 開不起來")
            continue
        found = cards(html)
        hits = [cid for cid, text in found if is_mx5(text)]
        log.info("abc好車網：%s 找到 %d 個連結，其中 %d 個看起來是 MX-5",
                 url.split("?")[-1], len(found), len(hits))
        if hits:
            return hits[:MAX_DETAILS]
        if len(found) > len(best):
            best = found
        tried.append(f"{url} 只找到 {len(found)} 個連結、沒有 MX-5")
    if best:  # 卡片上看不出車款時，仍然開幾頁進去確認
        log.warning("abc好車網：卡片文字判斷不出車款，改開前 12 個連結確認")
        return [cid for cid, _ in best[:12]]
    raise RuntimeError("搜尋頁抓不到任何車輛連結（" + "；".join(tried) + "）")


def page_title(html):
    soup = BeautifulSoup(html, "html.parser")
    return clean_text(soup.title.get_text() if soup.title else "", 80)


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
    items, blocked, not_mx5, samples = [], 0, 0, []
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
            if len(samples) < 3:   # 記下實際讀到的頁面標題，方便判斷是被擋還是版面改了
                samples.append(f"{cid}：{page_title(html) or '（沒有標題）'}")
            continue
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
        raise RuntimeError(
            f"{len(ids)} 個連結都沒有解析成功（讀不到 {blocked} 頁、非 MX-5 {not_mx5} 頁）"
            + ("；實際讀到的頁面：" + "；".join(samples) if samples else ""))
    return items

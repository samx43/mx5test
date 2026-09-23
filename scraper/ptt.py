"""PTT CarShop：用看板搜尋找 [售車] 的 MX-5 文章，再逐篇讀取內文。"""
import datetime as dt
import re
import time
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from .common import (clean_text, is_mx5, log, parse_mileage_km, parse_price_wan,
                     parse_year)

BASE = "https://www.ptt.cc"
QUERIES = ["MX-5", "MX5", "MX 5", "Miata", "Roadster"]
MAX_PAGES = 3          # 每個關鍵字最多翻幾頁搜尋結果（由新到舊）
MAX_AGE_DAYS = 120     # 超過這個天數的文章不收
COOKIES = {"over18": "1"}

FIELDS = [
    ("price", re.compile(r"售價|價格|欲售|價錢|開價|售價")),
    ("year", re.compile(r"年份|年分|年式|出廠")),
    ("mileage", re.compile(r"里程|公里數|行駛")),
    ("location", re.compile(r"地點|地區|所在地|交易地|看車地")),
    ("desc", re.compile(r"其[他它]說明|車況說明|備註|說明|介紹")),
]
_FIELD_LINE = re.compile(r"^\s*([^：:\n]{1,10})[：:]\s*(.*)$")
_IMGUR = re.compile(r"https?://(?:i\.|m\.)?imgur\.com/([A-Za-z0-9]{5,8})(?:\.(?:jpe?g|png|webp|gif))?")
_DIRECT_IMG = re.compile(r"https?://[^\s\"'<>]+\.(?:jpe?g|png|webp)(?:\?[^\s\"'<>]*)?", re.I)


def search_titles(fetcher):
    found = {}
    for q in QUERIES:
        for page in range(1, MAX_PAGES + 1):
            url = f"{BASE}/bbs/CarShop/search?page={page}&q={quote(q)}"
            html = fetcher.get(url, cookies=COOKIES)
            if not html:
                break
            entries = BeautifulSoup(html, "html.parser").select("div.r-ent")
            if not entries:
                break
            for e in entries:
                a = e.select_one("div.title a")
                if not a or not a.get("href"):
                    continue
                title = a.get_text(strip=True)
                if title.startswith(("Re:", "Fw:")) or "[售車]" not in title:
                    continue
                if not is_mx5(title):
                    continue
                found[urljoin(BASE, a["href"])] = title
    return found


def parse_fields(body):
    fields, current = {}, None
    for line in body.splitlines():
        m = _FIELD_LINE.match(line)
        if m:
            key = next((k for k, rx in FIELDS if rx.search(m.group(1))), None)
            current = key
            if key and key not in fields:
                fields[key] = m.group(2).strip()
            continue
        if current == "desc" and line.strip():
            fields["desc"] = (fields.get("desc", "") + " " + line.strip()).strip()
    return fields


def extract_images(html):
    imgs = []
    for m in _IMGUR.finditer(html):
        u = f"https://i.imgur.com/{m.group(1)}.jpg"
        if u not in imgs:
            imgs.append(u)
    for m in _DIRECT_IMG.finditer(html):
        u = m.group(0)
        if "imgur.com" not in u and u not in imgs:
            imgs.append(u)
    return imgs[:4]


def parse_article(html, url, list_title):
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("#main-content")
    if not main:
        return None
    meta = [s.get_text(strip=True) for s in main.select("span.article-meta-value")]
    author = meta[0].split(" ")[0] if meta else ""
    title = meta[2] if len(meta) > 2 else list_title
    for tag in main.select("div.article-metaline, div.article-metaline-right, div.push, span.f2"):
        tag.decompose()
    text = main.get_text("\n")
    body = re.split(r"\n--\s*\n", text)[0]
    f = parse_fields(body)

    clean_title = re.sub(r"^\s*\[售車\]\s*", "", title).strip()
    price = parse_price_wan(f.get("price")) or parse_price_wan(
        (re.search(r"\d+(?:\.\d+)?\s*萬", clean_title) or [None])[0]
    )
    year = parse_year(f.get("year")) or parse_year(clean_title)
    desc = f.get("desc") or " ".join(
        l.strip() for l in body.splitlines() if l.strip() and not _FIELD_LINE.match(l)
    )

    pid = re.search(r"M\.(\d+)\.A\.\w+", url)
    posted = (
        dt.datetime.fromtimestamp(int(pid.group(1)), dt.timezone.utc).isoformat()
        if pid else None
    )
    return {
        "id": "ptt-" + (pid.group(0) if pid else url.rsplit("/", 1)[-1]),
        "url": url,
        "title": clean_title,
        "price": price,
        "year": year,
        "mileage_km": parse_mileage_km(f.get("mileage")),
        "location": clean_text(f.get("location"), 20) or None,
        "description": clean_text(desc),
        "images": extract_images(str(main)),
        "seller": author,
        "posted_at": posted,
        "sold": bool(re.search(r"已售|售出|已收訂|已出售", title)),
    }


def scrape(fetcher, known):
    items = []
    for url, title in search_titles(fetcher).items():
        pid = re.search(r"M\.(\d+)\.A", url)
        if pid and time.time() - int(pid.group(1)) > MAX_AGE_DAYS * 86400:
            continue
        html = fetcher.get(url, cookies=COOKIES)
        if not html:
            continue
        try:
            item = parse_article(html, url, title)
        except Exception:  # 單篇格式怪異不影響其他文章
            log.exception("PTT 文章解析失敗 %s", url)
            continue
        if item:
            items.append(item)
    log.info("PTT：%d 筆", len(items))
    return items

"""PTT 的備援管道：pttweb.cc。

ptt.cc 會擋掉機房 IP，但 pttweb.cc 這個第三方網頁版可以正常讀取，
文章內容也和原文一致。抓到的文章會附上原始 ptt.cc 連結，方便點過去看。
"""
import datetime as dt
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from . import browser
from .common import clean_text, log, parse_mileage_km, parse_price_wan, parse_year

BASE = "https://www.pttweb.cc"
LIST_URL = f"{BASE}/bbs/CarShop/page"
PAGE_STEP = 25          # 一頁 25 篇
LIST_PAGES = 10         # 往回翻幾頁（約兩個月）

_ARTICLE = re.compile(r"/bbs/CarShop/(M\.\d+\.A\.\w+)")
_PAGE_N = re.compile(r"/bbs/CarShop/page\?n=(\d+)")
_PTT_URL = re.compile(r"https://www\.ptt\.cc/bbs/CarShop/M\.\d+\.A\.\w+\.html")


def fetch(fetcher, url):
    """先用一般請求，被擋就改用瀏覽器。"""
    html = fetcher.get(url)
    if html and "/bbs/CarShop/" in html:
        return html
    return browser.get_html(url, wait_selector='a[href*="/bbs/CarShop/"]')


def _soup(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup


def _titles(soup):
    """文章連結 -> 標題。pttweb 的標題會重複兩次，取前半即可。"""
    out = {}
    for a in soup.find_all("a", href=_ARTICLE):
        aid = _ARTICLE.search(a["href"]).group(1)
        text = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
        if not text:
            continue
        half = len(text) // 2
        if text[:half].strip() and text[:half].strip() == text[half:].strip():
            text = text[:half].strip()
        out.setdefault(aid, text)
    return out


def collect(fetcher, pages=LIST_PAGES):
    """從最新往回翻，回傳 {文章代碼: 標題}。"""
    html = fetch(fetcher, LIST_URL)
    if not html:
        raise RuntimeError("pttweb.cc 的看板頁讀不到（一般請求和瀏覽器都失敗）")
    soup = _soup(html)
    found = _titles(soup)
    ns = sorted({int(m.group(1)) for m in _PAGE_N.finditer(html)})
    n = (ns[-1] - PAGE_STEP) if ns else None
    for _ in range(pages - 1):
        if not n or n < PAGE_STEP:
            break
        html = fetch(fetcher, f"{LIST_URL}?n={n}")
        if not html:
            break
        page_soup = _soup(html)
        before = len(found)
        found.update(_titles(page_soup))
        log.info("pttweb：n=%s，累積 %d 篇（新增 %d）", n, len(found), len(found) - before)
        n -= PAGE_STEP
    return found


def article_url(aid):
    return f"{BASE}/bbs/CarShop/{aid}"


def parse_article(html, aid, list_title=""):
    soup = _soup(html)
    og = soup.find("meta", attrs={"property": "og:title"})
    title = og["content"].strip() if og and og.get("content") else list_title
    title = re.sub(r"\s*-\s*看板\s*CarShop\s*$", "", title)

    author = ""
    a = soup.find("a", href=re.compile(r"/user/[^/]+$"))
    if a:
        author = re.sub(r"\s*\(.*\)\s*$", "", a.get_text(strip=True))

    text = soup.get_text("\n")
    body = re.split(r"※\s*發信站", text)[0]
    idx = body.find("車輛品牌")
    if idx > 0:
        body = body[idx:]

    # 原始 ptt.cc 連結；讀不到就退回 pttweb 的網址
    m = _PTT_URL.search(text)
    url = m.group(0) if m else article_url(aid)

    from .ptt import build_desc, extract_images, parse_fields, pick  # 共用解析邏輯
    pairs = parse_fields(body)
    clean_title = re.sub(r"^\s*\[售車\]\s*", "", title).strip()
    price = parse_price_wan(pick(pairs, "price"))
    if price is None:
        pm = re.search(r"\d+(?:\.\d+)?\s*萬", clean_title)
        price = parse_price_wan(pm.group(0)) if pm else None
    loc = pick(pairs, "location")
    if loc:
        loc = clean_text(re.split(r"[／/、,，\s(（]", loc.strip())[0], 12) or None

    ts = re.search(r"M\.(\d+)\.A", aid)
    posted = (dt.datetime.fromtimestamp(int(ts.group(1)), dt.timezone.utc).isoformat()
              if ts else None)
    return {
        "id": "ptt-" + aid,
        "url": url,
        "title": clean_title,
        "price": price,
        "year": parse_year(pick(pairs, "year")) or parse_year(clean_title),
        "mileage_km": parse_mileage_km(pick(pairs, "mileage")),
        "location": loc,
        "description": build_desc(pairs, body),
        "images": extract_images(str(soup)),
        "seller": author,
        "posted_at": posted,
        "sold": bool(re.search(r"已售|售出|已收訂|已出售|完售|已刪文", title)),
    }

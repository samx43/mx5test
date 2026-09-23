"""PTT CarShop：主要做法是直接翻看板的文章列表（最可靠），搜尋功能當作補充。"""
import datetime as dt
import re
import time
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from . import browser
from .common import (clean_text, is_mx5, log, parse_mileage_km, parse_price_wan,
                     parse_year)

BASE = "https://www.ptt.cc"
BOARD = "/bbs/CarShop"
INDEX_PAGES = 15       # 從最新往回翻幾頁（一頁約 20 篇）
SEARCH_PAGES = 2       # 每個關鍵字再翻幾頁搜尋結果
QUERIES = ["MX-5", "MX5", "Miata", "Roadster"]
MAX_AGE_DAYS = 180     # 超過這個天數的文章不收
COOKIES = {"over18": "1"}

FIELDS = [
    ("price", re.compile(r"售價|價格|欲售|價錢|開價")),
    ("year", re.compile(r"年份|年分|年式|出廠")),
    ("mileage", re.compile(r"里程|公里數")),
    ("location", re.compile(r"地點|地區|所在地|交易地|看車地")),
    ("desc", re.compile(r"其[他它]說明|車況說明|備註|說明|介紹")),
]
DESC_KEYS = re.compile(r"車款|型式|排氣|顏色|排檔|變速|原使用|車況|配備|保養|改裝|說明|備註")
SKIP_KEYS = re.compile(r"聯絡|電話|line|LINE|照片|圖片|價|地區|地點")
_FIELD_LINE = re.compile(r"^\s*([^：:\n]{1,24})[：:]\s*(.*)$")
_IMGUR = re.compile(r"https?://(?:i\.|m\.)?imgur\.com/([A-Za-z0-9]{5,8})(?:\.(?:jpe?g|png|webp|gif))?")
_DIRECT_IMG = re.compile(r"https?://[^\s\"'<>]+\.(?:jpe?g|png|webp)(?:\?[^\s\"'<>]*)?", re.I)


class Reader:
    """PTT 會擋掉一般的程式請求，被擋到就整個改用瀏覽器。"""

    def __init__(self, fetcher):
        self.fetcher = fetcher
        self.use_browser = False

    def get(self, url):
        if not self.use_browser:
            html = self.fetcher.get(url, cookies=COOKIES)
            if html and ("r-ent" in html or "main-content" in html):
                return html
            log.warning("PTT 一般請求拿不到內容，改用瀏覽器")
            self.use_browser = True
        return browser.get_html(url, wait_selector="div.r-ent, #main-content")


def _rows(html):
    soup = BeautifulSoup(html, "html.parser")
    out = {}
    for e in soup.select("div.r-ent"):
        a = e.select_one("div.title a")
        if a and a.get("href"):
            out[urljoin(BASE, a["href"])] = a.get_text(strip=True)
    return soup, out


def collect_from_index(reader):
    """從最新的看板頁往回翻，這是最穩定的來源。"""
    url = f"{BASE}{BOARD}/index.html"
    found, pages = {}, 0
    for _ in range(INDEX_PAGES):
        html = reader.get(url)
        if html is None:
            if pages == 0:
                raise RuntimeError("PTT 看板頁讀不到，一般請求和瀏覽器都失敗")
            break
        soup, rows = _rows(html)
        found.update(rows)
        pages += 1
        prev = next((a for a in soup.select("div.btn-group-paging a")
                     if "上頁" in a.get_text() and a.get("href")), None)
        if not prev:
            break
        url = urljoin(BASE, prev["href"])
    log.info("PTT：翻了 %d 頁看板，共 %d 篇文章", pages, len(found))
    if not found:
        raise RuntimeError("看板頁打得開，但裡面一篇文章都沒有，可能被擋或版面改了")
    return found


def collect_from_search(reader):
    found = {}
    for q in QUERIES:
        for page in range(1, SEARCH_PAGES + 1):
            html = reader.get(f"{BASE}{BOARD}/search?page={page}&q={quote(q)}")
            if not html:
                break
            _, rows = _rows(html)
            if not rows:
                break
            found.update(rows)
    log.info("PTT：搜尋另外找到 %d 篇文章", len(found))
    return found


def wanted(title):
    if not title or title.startswith(("Re:", "Fw:")):
        return False
    return "[售車]" in title and is_mx5(title)


def parse_fields(body):
    """回傳 [(欄位名, 值)]；跳過網址那種帶冒號的行，值可以跨行。"""
    pairs, last = [], None
    for line in body.splitlines():
        if re.match(r"^\s*https?://", line):
            continue
        m = _FIELD_LINE.match(line)
        if m and m.group(1).strip().lower() not in ("http", "https"):
            pairs.append([m.group(1).strip(), m.group(2).strip()])
            last = pairs[-1]
        elif last is not None and line.strip():
            last[1] = (last[1] + " " + line.strip()).strip()
    return pairs


def pick(pairs, key):
    rx = dict(FIELDS)[key]
    for k, v in pairs:
        if rx.search(k) and v:
            return v
    return None


def build_desc(pairs, fallback_body):
    explicit = pick(pairs, "desc")
    bits = [f"{k}：{v}" for k, v in pairs
            if v and DESC_KEYS.search(k) and not SKIP_KEYS.search(k)]
    if explicit:
        bits.insert(0, explicit)
    if bits:
        return clean_text("｜".join(bits))
    return clean_text(" ".join(l.strip() for l in fallback_body.splitlines() if l.strip()))


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
    images = extract_images(str(main))
    for tag in main.select("div.article-metaline, div.article-metaline-right, div.push, span.f2"):
        tag.decompose()
    body = re.split(r"\n--\s*\n", main.get_text("\n"))[0]
    pairs = parse_fields(body)

    clean_title = re.sub(r"^\s*\[售車\]\s*", "", title).strip()
    price = parse_price_wan(pick(pairs, "price"))
    if price is None:
        m = re.search(r"\d+(?:\.\d+)?\s*萬", clean_title)
        price = parse_price_wan(m.group(0)) if m else None
    loc = pick(pairs, "location")
    if loc:
        loc = clean_text(re.split(r"[／/、,，\s(（]", loc.strip())[0], 12) or None

    pid = re.search(r"M\.(\d+)\.A\.\w+", url)
    posted = (dt.datetime.fromtimestamp(int(pid.group(1)), dt.timezone.utc).isoformat()
              if pid else None)
    return {
        "id": "ptt-" + (pid.group(0) if pid else url.rsplit("/", 1)[-1]),
        "url": url,
        "title": clean_title,
        "price": price,
        "year": parse_year(pick(pairs, "year")) or parse_year(clean_title),
        "mileage_km": parse_mileage_km(pick(pairs, "mileage")),
        "location": loc,
        "description": build_desc(pairs, body),
        "images": images,
        "seller": author,
        "posted_at": posted,
        "sold": bool(re.search(r"已售|售出|已收訂|已出售|完售", title)),
    }


def scrape(fetcher, known):
    reader = Reader(fetcher)
    candidates = collect_from_index(reader)
    try:
        candidates.update(collect_from_search(reader))
    except Exception:
        log.warning("PTT 搜尋失敗，只用看板列表的結果", exc_info=True)

    hits = {u: t for u, t in candidates.items() if wanted(t)}
    log.info("PTT：%d 篇標題符合 MX-5 售車", len(hits))

    items = []
    for url, title in hits.items():
        pid = re.search(r"M\.(\d+)\.A", url)
        if pid and time.time() - int(pid.group(1)) > MAX_AGE_DAYS * 86400:
            continue
        html = reader.get(url)
        if not html:
            continue
        try:
            item = parse_article(html, url, title)
        except Exception:
            log.exception("PTT 文章解析失敗 %s", url)
            continue
        if item:
            items.append(item)
    log.info("PTT：收錄 %d 筆", len(items))
    return items

"""8891：讀取 MX-5 車款列表頁，再到每台車的頁面讀標題、價格與照片。"""
import html as htmllib
import re

from bs4 import BeautifulSoup

from .common import clean_text, is_mx5, log, parse_mileage_km, parse_price_wan, parse_year

LIST_URL = "https://auto.8891.com.tw/mazda/mx-5"
DETAIL_URL = "https://auto.8891.com.tw/usedauto-infos-{}.html"
MAX_PAGES = 5
_ID = re.compile(r"usedauto-infos-(\d+)\.html")
_CITY_AGE = re.compile(r"([\u4e00-\u9fff]{2}[市縣])\s*\d+\s*(?:天|小時|分鐘|個月)[內前]")
_YEAR_KM = re.compile(r"((?:19|20)\d{2})年\s*([\d.]+\s*萬?\s*公里)")


def parse_list_text(text):
    """列表卡片文字，例如：
    'Mazda MX-5 2021款 2.0L MT 百週年紀念版本 新北市7天內刊登 988次瀏覽 ... 98.0萬 2021年6.1萬公里'"""
    out = {}
    m = _CITY_AGE.search(text)
    if m:
        out["headline"] = text[: m.start()].strip()
        out["location"] = m.group(1)
    ym = _YEAR_KM.search(text)
    if ym:
        out["year"] = int(ym.group(1))
        out["mileage_km"] = parse_mileage_km(ym.group(2))
        rest = text[: ym.start()]
    else:
        rest = text
    prices = re.findall(r"(\d+(?:\.\d+)?)\s*萬(?!\s*公里)", rest[m.end():] if m else rest)
    if prices:
        out["price"] = parse_price_wan(prices[-1] + "萬")
    return out


def parse_detail(html):
    soup = BeautifulSoup(html, "html.parser")

    def meta(prop):
        t = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
        return htmllib.unescape(t["content"]).strip() if t and t.get("content") else ""

    og_title = meta("og:title")  # 'Mazda MX-5 2016年二手車 76.8萬 桃園市-冠豪汽車 |'
    out = {"og_title": og_title, "image": meta("og:image") or None}
    pm = re.search(r"(\d+(?:\.\d+)?)\s*萬", og_title)
    if pm:
        out["price"] = parse_price_wan(pm.group(0))
    y = parse_year(og_title)
    if y:
        out["year"] = y
    dm = re.search(r"萬\s+([\u4e00-\u9fff]{2}[市縣])-([^|]+)", og_title)
    if dm:
        out["location"], out["seller"] = dm.group(1), dm.group(2).strip()
    desc = meta("description").split("8891中古車")[0].strip(" 。")
    out["description"] = desc
    return out


def scrape(fetcher, known):
    cards = {}
    for page in range(1, MAX_PAGES + 1):
        url = LIST_URL if page == 1 else f"{LIST_URL}?page={page}"
        html = fetcher.get(url)
        if not html:
            break
        soup = BeautifulSoup(html, "html.parser")
        new = 0
        for a in soup.find_all("a", href=_ID):
            cid = _ID.search(a["href"]).group(1)
            text = a.get_text(" ", strip=True)
            if cid in cards or not is_mx5(text):
                continue
            img = a.find("img")
            src = None
            if img:
                for attr in ("data-original", "data-src", "src"):
                    v = img.get(attr) or ""
                    if v.startswith("http") and "photo" in v:
                        src = v
                        break
            cards[cid] = {"text": text, "img": src}
            new += 1
        if new == 0:
            break

    items = []
    for cid, card in cards.items():
        info = parse_list_text(card["text"])
        detail_url = DETAIL_URL.format(cid)
        html = fetcher.get(detail_url)
        d = parse_detail(html) if html else {}
        if html is None and not known.get(f"8891-{cid}"):
            continue  # 詳細頁打不開而且以前沒看過，可能已下架
        title = info.get("headline") or re.sub(r"\s*\|.*$", "", d.get("og_title", "")) or card["text"][:40]
        items.append({
            "id": f"8891-{cid}",
            "url": detail_url,
            "title": clean_text(title, 90),
            "price": d.get("price", info.get("price")),
            "year": info.get("year") or d.get("year"),
            "mileage_km": info.get("mileage_km"),
            "location": info.get("location") or d.get("location"),
            "description": clean_text(d.get("description", "")),
            "images": [u for u in [card["img"], d.get("image")] if u][:2],
            "seller": d.get("seller"),
            "posted_at": None,
            "sold": False,
        })
    log.info("8891：%d 筆", len(items))
    return items

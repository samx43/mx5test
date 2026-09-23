"""共用工具：禮貌抓取、價格/年份/里程解析、MX-5 判斷、代數判斷。"""
import datetime as dt
import logging
import random
import re
import time

import requests

log = logging.getLogger("mx5")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)

CURRENT_YEAR = dt.date.today().year


class Fetcher:
    """每次請求之間隨機等待，失敗時重試，避免對來源網站造成負擔。"""

    def __init__(self, delay=(1.5, 3.0)):
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": UA, "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.6"}
        )
        self.delay = delay
        self._last = 0.0

    def get(self, url, **kwargs):
        wait = random.uniform(*self.delay) - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        for attempt in range(3):
            try:
                r = self.session.get(url, timeout=25, **kwargs)
                self._last = time.time()
                if r.status_code == 200:
                    if not r.encoding or r.encoding.lower() == "iso-8859-1":
                        r.encoding = r.apparent_encoding
                    return r.text
                log.warning("HTTP %s  %s", r.status_code, url)
                if r.status_code in (403, 404, 410):
                    return None
            except requests.RequestException as e:
                log.warning("請求失敗 %s: %s", url, e)
            time.sleep(4 * (attempt + 1))
        return None


# ---------- MX-5 判斷 ----------
_MX5 = re.compile(r"(?i)(?<![a-z])mx[\s\-_]?5(?!\d)|miata|ロードスター")
_ROADSTER = re.compile(r"(?i)roadster")
_MAZDA = re.compile(r"(?i)mazda|馬自達")


def is_mx5(text):
    if not text:
        return False
    if _MX5.search(text):
        return True
    # Roadster 也可能是 BMW Z4 等，必須同時出現 Mazda
    return bool(_ROADSTER.search(text) and _MAZDA.search(text))


# ---------- 數值解析 ----------
def parse_price_wan(s):
    """回傳以「萬」為單位的價格，例如 '58.8萬' -> 58.8、'580000' -> 58.0。"""
    if not s:
        return None
    s = s.replace(",", "").replace("，", "").replace(" ", "")
    m = re.search(r"(\d+(?:\.\d+)?)(萬|w|W)", s)
    if m:
        v = float(m.group(1))
    else:
        m = re.search(r"(?<![\d.])(\d{5,7})(?![\d.])", s)
        if m:
            v = float(m.group(1)) / 10000
        else:
            m = re.search(r"(?<![\d.])(\d{1,3}(?:\.\d)?)(?![\d.])", s)
            if not m:
                return None
            v = float(m.group(1))
    return round(v, 1) if 1 <= v <= 500 else None


def parse_year(s):
    if not s:
        return None
    for m in re.finditer(r"(?<!\d)((?:19|20)\d{2})(?!\d)", s):
        y = int(m.group(1))
        if 1989 <= y <= CURRENT_YEAR + 1:
            return y
    m = re.search(r"(?<!\d)(\d{2})\s*年", s)
    if m:
        yy = int(m.group(1))
        y = 2000 + yy if yy <= CURRENT_YEAR % 100 + 1 else 1900 + yy
        if 1989 <= y <= CURRENT_YEAR + 1:
            return y
    return None


def parse_mileage_km(s):
    if not s:
        return None
    s = s.replace(",", "").replace("，", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*萬\s*(?:公里|km|KM|Km)?", s)
    if m:
        v = float(m.group(1)) * 10000
    else:
        m = re.search(r"(\d{2,7})\s*(?:公里|km|KM|Km)", s) or re.search(
            r"(?<![\d.])(\d{3,7})(?![\d.])", s
        )
        if not m:
            return None
        v = float(m.group(1))
    return int(v) if 0 < v < 600000 else None


# ---------- 代數 ----------
_GEN = re.compile(r"(?<![A-Za-z])(NA|NB|NC|ND)(?![A-Za-z])")


def generation(year, text=""):
    m = _GEN.search(text or "")
    if m:
        return m.group(1)
    if not year:
        return None
    if year <= 1997:
        return "NA"
    if year <= 2005:
        return "NB"
    if year <= 2015:
        return "NC"
    return "ND"


def clean_text(s, limit=160):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= limit else s[: limit - 1] + "…"


def utcnow():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

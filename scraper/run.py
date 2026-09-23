"""執行一輪抓取：python -m scraper.run

- 每個來源各自獨立，一個壞掉不影響其他來源
- 和上一輪資料合併：保留首次出現時間、記錄價格變化
- 連續兩輪都沒抓到的車標記為「已下架」，30 天後從資料中移除
"""
import datetime as dt
import hashlib
import json
import logging
import pathlib
import sys

from . import abccar, browser, ptt, s8891
from .common import Fetcher, generation, log, utcnow

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data" / "listings.json"
MANUAL = ROOT / "manual_listings.json"

SOURCES = [
    ("ptt", "PTT CarShop", ptt.scrape),
    ("8891", "8891", s8891.scrape),
    ("abccar", "abc好車網", abccar.scrape),
]
MISSES_BEFORE_GONE = 2
KEEP_GONE_DAYS = 30


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def days_since(iso):
    if not iso:
        return 0
    t = dt.datetime.fromisoformat(iso)
    return (dt.datetime.now(dt.timezone.utc) - t).total_seconds() / 86400


def load_manual():
    items = []
    for raw in load_json(MANUAL, []):
        if not raw.get("url"):
            continue
        items.append({
            "id": "manual-" + hashlib.sha1(raw["url"].encode()).hexdigest()[:10],
            "url": raw["url"],
            "title": raw.get("title", ""),
            "price": raw.get("price"),
            "year": raw.get("year"),
            "mileage_km": raw.get("mileage_km"),
            "location": raw.get("location"),
            "description": raw.get("description", ""),
            "images": [raw["image"]] if raw.get("image") else [],
            "seller": raw.get("seller"),
            "posted_at": None,
            "sold": bool(raw.get("sold")),
        })
    return items


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    now = utcnow()
    prev_data = load_json(OUT, {"items": []})
    old = {it["id"]: it for it in prev_data.get("items", [])}
    fetcher = Fetcher()

    status, fetched = {}, {}
    for key, name, fn in SOURCES:
        known = {k: v for k, v in old.items() if v.get("source") == key}
        try:
            items = fn(fetcher, known)
            active_before = sum(1 for v in known.values() if v.get("status") == "active")
            if not items and active_before >= 3:
                raise RuntimeError("這一輪抓到 0 筆，網站可能改版了")
            status[key] = {"name": name, "ok": True, "count": len(items)}
        except Exception as e:
            log.exception("%s 失敗", name)
            status[key] = {"name": name, "ok": False, "count": 0, "error": str(e)[:200]}
            continue
        for it in items:
            it["source"], it["source_name"] = key, name
            fetched[it["id"]] = it

    browser.close()  # 抓完就把無頭瀏覽器關掉

    for it in load_manual():
        it["source"], it["source_name"] = "manual", "手動新增"
        fetched[it["id"]] = it

    merged = []
    for iid, it in fetched.items():
        prev = old.get(iid, {})
        hist = list(prev.get("price_history", []))
        if it.get("price") is not None and (not hist or hist[-1]["price"] != it["price"]):
            hist.append({"date": now, "price": it["price"]})
        it.update({
            "generation": generation(it.get("year"), it.get("title", "")),
            "first_seen": prev.get("first_seen", now),
            "last_seen": now,
            "missed": 0,
            "price_history": hist[-10:],
            "status": "sold" if it.pop("sold", False) else "active",
        })
        merged.append(it)

    for iid, prev in old.items():
        if iid in fetched or prev.get("source") == "manual":
            continue
        if status.get(prev.get("source"), {}).get("ok"):
            prev["missed"] = prev.get("missed", 0) + 1
            if prev["missed"] >= MISSES_BEFORE_GONE and prev.get("status") != "gone":
                prev["status"], prev["gone_at"] = "gone", now
        if prev.get("status") == "gone" and days_since(prev.get("gone_at")) > KEEP_GONE_DAYS:
            continue
        merged.append(prev)

    merged.sort(key=lambda x: x.get("first_seen", ""), reverse=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({"updated_at": now, "sources": status, "items": merged},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    log.info("完成：共 %d 筆（%s）", len(merged),
             "、".join(f"{v['name']} {v['count']}" for v in status.values()))
    # 全部來源都失敗時讓 GitHub Actions 顯示紅燈，方便發現問題
    return 0 if any(v["ok"] for v in status.values()) else 1


if __name__ == "__main__":
    sys.exit(main())

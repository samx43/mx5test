"""共用的無頭瀏覽器。有些網站會擋掉一般的程式請求，只接受真正的瀏覽器。

整個流程共用一個瀏覽器，用完在 run.py 收尾時關掉。
"""
import random

from .common import UA, log

_pw = _browser = _ctx = None


def _context():
    global _pw, _browser, _ctx
    if _ctx is not None:
        return _ctx
    from playwright.sync_api import sync_playwright
    _pw = sync_playwright().start()
    _browser = _pw.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
    _ctx = _browser.new_context(
        user_agent=UA, locale="zh-TW", timezone_id="Asia/Taipei",
        viewport={"width": 1366, "height": 900},
    )
    _ctx.add_cookies([{"name": "over18", "value": "1", "domain": ".ptt.cc", "path": "/"}])
    log.info("已啟動無頭瀏覽器")
    return _ctx


def get_html(url, wait_selector=None, scroll=0, timeout=45000):
    """取得整頁 HTML；失敗時回傳 None。"""
    try:
        ctx = _context()
    except Exception as e:
        log.error("無法啟動瀏覽器：%s", e)
        return None
    page = ctx.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        if wait_selector:
            try:
                page.wait_for_selector(wait_selector, timeout=20000)
            except Exception:
                log.warning("等不到 %s（%s）", wait_selector, url)
        for _ in range(scroll):
            page.mouse.wheel(0, 4000)
            page.wait_for_timeout(1200)
        page.wait_for_timeout(random.randint(500, 1200))  # 放慢速度，降低對方負擔
        return page.content()
    except Exception as e:
        log.warning("瀏覽器讀取失敗 %s：%s", url, e)
        return None
    finally:
        try:
            page.close()
        except Exception:
            pass


def close():
    global _pw, _browser, _ctx
    for obj, fn in ((_ctx, "close"), (_browser, "close"), (_pw, "stop")):
        try:
            if obj:
                getattr(obj, fn)()
        except Exception:
            pass
    _pw = _browser = _ctx = None

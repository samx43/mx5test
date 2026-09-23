from scraper.common import is_mx5, parse_price_wan, parse_year, parse_mileage_km, generation
from scraper import ptt, s8891, abccar


def test_is_mx5():
    assert is_mx5("[售車] 2016 Mazda MX-5 ND 手排")
    assert is_mx5("MX5 RF 紅")
    assert is_mx5("Mazda Roadster 30週年")
    assert not is_mx5("BMW Z4 Roadster")
    assert not is_mx5("Mazda CX-5 2.0")
    assert not is_mx5("Mazda MX-30")


def test_numbers():
    assert parse_price_wan("58.8萬（可議）") == 58.8
    assert parse_price_wan("NT$580,000") == 58.0
    assert parse_price_wan("68") == 68
    assert parse_price_wan("私訊") is None
    assert parse_year("2016年式") == 2016
    assert parse_year("16年出廠") == 2016
    assert parse_year("97年") == 1997
    assert parse_mileage_km("8.2萬公里") == 82000
    assert parse_mileage_km("82,000 km") == 82000
    assert generation(2016) == "ND" and generation(1995) == "NA"
    assert generation(2016, "MX-5 NC2 2.0") == "NC"


PTT_HTML = """<div id="main-content"><div class="article-metaline"><span class="article-meta-tag">作者</span><span class="article-meta-value">roadlover (阿明)</span></div>
<div class="article-metaline-right"><span class="article-meta-tag">看板</span><span class="article-meta-value">CarShop</span></div>
<div class="article-metaline"><span class="article-meta-tag">標題</span><span class="article-meta-value">[售車] 2009 Mazda MX-5 NC 手排 已售出</span></div>
<div class="article-metaline"><span class="article-meta-tag">時間</span><span class="article-meta-value">Tue Sep 15 10:00:00 2026</span></div>
車輛品牌：Mazda
出廠年月：2009/05
行駛里程：9.5萬公里
欲售價格：42萬
交易地點：台北
其他說明：原廠保養，軟頂無漏水
新換輪胎
https://imgur.com/AbCdE12
https://i.imgur.com/XyZ9876.png
--
※ 發信站: 批踢踢實業坊(ptt.cc)
<div class="push">推 abc: 好車</div></div>"""


def test_ptt_article():
    it = ptt.parse_article(PTT_HTML, "https://www.ptt.cc/bbs/CarShop/M.1789000000.A.123.html", "")
    assert it["price"] == 42 and it["year"] == 2009 and it["mileage_km"] == 95000
    assert it["location"] == "台北" and it["sold"] is True
    assert "軟頂無漏水" in it["description"] and "新換輪胎" in it["description"]
    assert it["images"] == ["https://i.imgur.com/AbCdE12.jpg", "https://i.imgur.com/XyZ9876.jpg"]
    assert it["seller"] == "roadlover" and it["id"] == "ptt-M.1789000000.A.123"


def test_8891_list_text():
    t = ("Mazda MX-5 2021款 2.0L MT 2.0L百週年紀念版本 履約保證 新北市7天內刊登 988次瀏覽 "
         "里程實拍 真實車源 98.0 萬 2021年6.1萬公里")
    d = s8891.parse_list_text(t)
    assert d["location"] == "新北市" and d["price"] == 98.0
    assert d["year"] == 2021 and d["mileage_km"] == 61000
    d2 = s8891.parse_list_text("Mazda MX-5 2025款 ND3 RF 2.0L 台南市4天內刊登 585次瀏覽 電洽 2024年3000公里")
    assert d2.get("price") is None and d2["mileage_km"] == 3000


def test_8891_detail():
    html = ('<meta property="og:title" content="Mazda MX-5 2016年二手車 76.8萬 桃園市-冠豪汽車  |">'
            '<meta property="og:image" content="https://photo.8891.com.tw/a.jpg">'
            '<meta name="description" content="全程原廠保養 。8891中古車，為您提供">')
    d = s8891.parse_detail(html)
    assert d["price"] == 76.8 and d["year"] == 2016 and d["location"] == "桃園市"
    assert d["seller"] == "冠豪汽車" and d["description"] == "全程原廠保養"


def test_abccar_detail():
    html = ('<meta property="og:title" content="Mazda MX-5 2.0 (NC) 2013年 中古車(二手車) 20.8萬 - 好車行 - abc好車網">'
            '<meta property="og:image" content="https://image.abccar.com.tw/x.jpg">'
            '<meta property="og:description" content="車況佳&amp;nbsp;原鈑件 |abc好車網中古車(二手車)">'
            '<div>行駛里程 101,000公里 所在地 台中市</div>')
    d = abccar.parse_detail(html)
    assert d["title"] == "Mazda MX-5 2.0 (NC) 2013年" and d["price"] == 20.8
    assert d["mileage_km"] == 101000 and d["location"] == "台中市" and d["seller"] == "好車行"
    assert d["description"] == "車況佳 原鈑件"
    assert abccar.parse_detail(html.replace("MX-5", "CX-5")) is None


REAL_POST = """<div id="main-content"><div class="article-metaline"><span class="article-meta-tag">作者</span><span class="article-meta-value">jason731124 (jason)</span></div>
<div class="article-metaline-right"><span class="article-meta-tag">看板</span><span class="article-meta-value">CarShop</span></div>
<div class="article-metaline"><span class="article-meta-tag">標題</span><span class="article-meta-value">[售車] 2024MX5硬頂+recaro椅</span></div>
<div class="article-metaline"><span class="article-meta-tag">時間</span><span class="article-meta-value">Wed Jun  3 22:08:57 2026</span></div>
車輛品牌/產地/出廠年月：2024年7月

車款型式/排氣量：Mazda MX5硬頂+recaro座椅

顏色/排檔形式：原色天際灰，全車內外貼混動紅

有無調表/實際里程：無調表、8422KM增加中

欲售售價：130萬（誠可議）

原使用情形：自用一手

交易地區/聯絡方式：台中/站內信 + (電話/line/推文)

實際照片：

<a href="https://i.meee.com.tw/gNuKIt4.jpg">https://i.meee.com.tw/gNuKIt4.jpg</a>

--
※ 發信站: 批踢踢實業坊(ptt.cc)
</div>"""


def test_real_ptt_post():
    it = ptt.parse_article(REAL_POST, "https://www.ptt.cc/bbs/CarShop/M.1780000000.A.ABC.html", "")
    assert ptt.wanted("[售車] 2024MX5硬頂+recaro椅")
    assert it["price"] == 130
    assert it["year"] == 2024
    assert it["mileage_km"] == 8422
    assert it["location"] == "台中"
    assert it["images"] == ["https://i.meee.com.tw/gNuKIt4.jpg"]
    assert "天際灰" in it["description"] and "站內信" not in it["description"]
    assert it["seller"] == "jason731124"


def test_index_rows():
    html = """<div class="r-ent"><div class="title"><a href="/bbs/CarShop/M.1780000000.A.ABC.html">[售車] 2024MX5硬頂+recaro椅</a></div></div>
    <div class="r-ent"><div class="title">(本文已被刪除)</div></div>
    <div class="r-ent"><div class="title"><a href="/bbs/CarShop/M.1780000001.A.DEF.html">[購車] 徵 MX-5</a></div></div>
    <div class="btn-group btn-group-paging"><a class="btn wide" href="/bbs/CarShop/index2100.html">‹ 上頁</a></div>"""
    soup, rows = ptt._rows(html)
    assert len(rows) == 2
    assert [t for t in rows.values() if ptt.wanted(t)] == ["[售車] 2024MX5硬頂+recaro椅"]
    assert soup.select("div.btn-group-paging a")[0]["href"].endswith("index2100.html")

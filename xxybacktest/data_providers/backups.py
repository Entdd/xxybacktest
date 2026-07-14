"""
================================================================================
backups —— 备用源 & 降级策略（a-stock-data V3.4.0）
================================================================================
来源: D:\\dev\\a-stock-data-main\\SKILL.md — 备用源速查章节

东财被封时的独立备胎：交易所官方/新浪。不同域名、不同风控面。
================================================================================
"""
import json
import urllib.request
import ssl

from .core import UA

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE


def dragon_tiger_backup(trade_date: str) -> dict:
    """龙虎榜官方备用源（东财被封时用）：上交所+深交所官方，零鉴权权威一手，含营业部席位。"""
    out = {"date": trade_date, "sse_raw": "", "szse": []}
    # 深交所
    su = (f"https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON"
          f"&CATALOGID=1842_xxpl&TABKEY=tab1&txtStart={trade_date}&txtEnd={trade_date}&random=0.9")
    req = urllib.request.Request(su, headers={"User-Agent": UA,
          "Referer": "https://www.szse.cn/disclosure/supervision/dealinfo/index.html"})
    with urllib.request.urlopen(req, timeout=15, context=_ctx) as r:
        d = json.loads(r.read())
    for row in d[0].get("data", []):
        out["szse"].append({"code": row.get("zqdm"), "name": row.get("zqjc"),
                            "amount": row.get("cjje"), "reason": row.get("plyy")})
    # 上交所
    eu = (f"https://query.sse.com.cn/infodisplay/showTradePublicFile.do?"
          f"jsonCallBack=cb&isPagination=false&dateTx={trade_date}")
    req = urllib.request.Request(eu, headers={"User-Agent": UA,
          "Referer": "https://www.sse.com.cn/disclosure/diclosure/public/"})
    with urllib.request.urlopen(req, timeout=15) as r:
        t = r.read().decode("utf-8", "ignore")
    out["sse_raw"] = "\n".join(json.loads(t[t.index("(")+1:t.rindex(")")]).get("fileContents", []))
    return out


def fund_flow_backup(code: str, days: int = 60) -> list:
    """个股资金流备用源（东财被封时用）：新浪，日度四档单净额。"""
    pre = ("sh" if code.startswith(("6", "9")) else "bj" if code.startswith("8") else "sz") + code
    u = (f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
         f"MoneyFlow.ssl_qsfx_zjlrqs?page=1&num={days}&sort=opendate&asc=0&daima={pre}")
    req = urllib.request.Request(u, headers={"User-Agent": UA, "Referer": "https://finance.sina.com.cn/"})
    with urllib.request.urlopen(req, timeout=15) as r:
        t = r.read().decode("utf-8", "ignore")
    arr = json.loads(t[t.index("["):t.rindex("]")+1])
    return [{"date": x.get("opendate"), "close": x.get("trade"),
             "net_amount": x.get("netamount"), "turnover": x.get("turnover")} for x in arr]


def announcements_backup(code: str, page_size: int = 20) -> list:
    """公告备用源（巨潮被封时用）：深市走深交所官方+PDF，沪市走东财+PDF。"""
    if code.startswith(("0", "3")):
        body = json.dumps({"channelCode": ["listedNotice_disc"], "pageSize": page_size,
                           "pageNum": 1, "stock": [code]}).encode()
        req = urllib.request.Request("https://www.szse.cn/api/disc/announcement/annList", data=body,
              headers={"User-Agent": UA, "Content-Type": "application/json",
                       "Referer": "https://www.szse.cn/disclosure/listed/notice/index.html"})
        with urllib.request.urlopen(req, timeout=15, context=_ctx) as r:
            d = json.loads(r.read())
        return [{"title": a.get("title"), "time": a.get("publishTime", "")[:10],
                 "pdf": "https://disc.static.szse.cn/download" + a.get("attachPath", "")}
                for a in d.get("data", [])]
    u = (f"https://np-anotice-stock.eastmoney.com/api/security/ann?sr=-1&page_size={page_size}"
         f"&page_index=1&ann_type=A&client_source=web&stock_list={code}&f_node=0&s_node=0")
    req = urllib.request.Request(u, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
    return [{"title": a.get("title"), "time": a.get("notice_date", "")[:10],
             "pdf": f"https://pdf.dfcfw.com/pdf/H2_{a.get('art_code','')}_1.pdf"}
            for a in d.get("data", {}).get("list", [])]

"""
================================================================================
market —— Layer 1: 行情层（a-stock-data V3.4.0）
================================================================================
来源: D:\\dev\\a-stock-data-main\\SKILL.md §§1.1-1.3

实时行情，不封IP：mootdx(TCP) + 腾讯财经(HTTP) + 百度股市通(HTTP)
================================================================================
"""
import urllib.request
from .core import tdx_client, UA


# ══════════════════════════════════════════════════════════════════════════════
# 1.2 腾讯财经 API
# ══════════════════════════════════════════════════════════════════════════════

def tencent_quote(codes: list[str]) -> dict[str, dict]:
    """
    批量拉取腾讯财经实时行情。

    codes: ["688017", "300476", "002463"]
    也支持指数: ["000001", "000300", "399006"]
    也支持ETF: ["510050", "510300"]

    返回: {code: {name, price, pe_ttm, pb, mcap,...}}
    """
    prefixed = []
    for c in codes:
        if c.startswith(("6", "9")):
            prefixed.append(f"sh{c}")
        elif c.startswith("8"):
            prefixed.append(f"bj{c}")
        else:
            prefixed.append(f"sz{c}")

    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode("gbk")

    result = {}
    for line in data.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            continue
        code = key[2:]
        result[code] = {
            "name":         vals[1],
            "price":        float(vals[3]) if vals[3] else 0,
            "last_close":   float(vals[4]) if vals[4] else 0,
            "open":         float(vals[5]) if vals[5] else 0,
            "change_amt":   float(vals[31]) if vals[31] else 0,
            "change_pct":   float(vals[32]) if vals[32] else 0,
            "high":         float(vals[33]) if vals[33] else 0,
            "low":          float(vals[34]) if vals[34] else 0,
            "amount_wan":   float(vals[37]) if vals[37] else 0,
            "turnover_pct": float(vals[38]) if vals[38] else 0,
            "pe_ttm":       float(vals[39]) if vals[39] else 0,
            "amplitude_pct":float(vals[43]) if vals[43] else 0,
            "mcap_yi":      float(vals[44]) if vals[44] else 0,
            "float_mcap_yi":float(vals[45]) if vals[45] else 0,
            "pb":           float(vals[46]) if vals[46] else 0,
            "limit_up":     float(vals[47]) if vals[47] else 0,
            "limit_down":   float(vals[48]) if vals[48] else 0,
            "vol_ratio":    float(vals[49]) if vals[49] else 0,
            "pe_static":    float(vals[52]) if vals[52] else 0,
        }
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 1.3 百度股市通 K线（带 MA5/10/20）
# ══════════════════════════════════════════════════════════════════════════════

def baidu_kline_with_ma(code: str, start_time: str = "") -> dict:
    """百度股市通K线 — 返回时自带 ma5/ma10/ma20 均价"""
    import requests
    url = "https://finance.pae.baidu.com/selfselect/getstockquotation"
    params = {
        "all": "1", "isIndex": "false", "isBk": "false", "isBlock": "false",
        "isFutures": "false", "isStock": "true", "newFormat": "1",
        "group": "quotation_kline_ab", "finClientType": "pc",
        "code": code, "start_time": start_time, "ktype": "1",
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/vnd.finance-web.v1+json",
        "Origin": "https://gushitong.baidu.com",
        "Referer": "https://gushitong.baidu.com/",
    }
    r = requests.get(url, params=params, headers=headers, timeout=10)
    d = r.json()
    result = d.get("Result", {})
    if isinstance(result, list):
        return {"keys": [], "rows": []}
    md = result.get("newMarketData", {})
    keys = md.get("keys", [])
    rows = md.get("marketData", "").split(";")
    return {"keys": keys, "rows": rows}


# ══════════════════════════════════════════════════════════════════════════════
# 1.1 mootdx 包装
# ══════════════════════════════════════════════════════════════════════════════

def tdx_bars(symbol: str, frequency: int = 9, offset: int = 10):
    """
    K线数据 (mootdx)。

    frequency: 0=5分钟 1=15分钟 2=30分钟 3=60分钟 4=日线 5=周线
               6=月线 8=1分钟 9=日线(默认) 10=季线 11=年线
    返回: open, close, high, low, vol, amount, datetime
    注意: bars 返回不复权原始价。
    """
    client = tdx_client()
    return client.bars(symbol=symbol, frequency=frequency, offset=offset)


def tdx_quotes(symbols: list[str]):
    """实时报价（46字段含五档盘口）"""
    client = tdx_client()
    return client.quotes(symbol=symbols)


def tdx_transaction(symbol: str, date: str):
    """逐笔成交（非交易时间返回空）"""
    client = tdx_client()
    return client.transaction(symbol=symbol, date=date)


def tdx_finance(symbol: str):
    """财务快照（37字段季报：EPS/ROE/净利/每股净资产等）"""
    client = tdx_client()
    return client.finance(symbol=symbol)


def tdx_f10(symbol: str, name: str = "最新提示"):
    """F10公司资料（9大类：最新提示/公司概况/财务分析/股东研究/股本结构/资本运作/业内点评/行业分析/公司大事）"""
    client = tdx_client()
    return client.F10(symbol=symbol, name=name)

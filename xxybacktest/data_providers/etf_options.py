"""
================================================================================
etf_options —— Layer 9: ETF 期权层（a-stock-data V3.4.0）
================================================================================
来源: D:\\dev\\a-stock-data-main\\SKILL.md §9.1

新浪源 — T型报价 + 希腊字母 + 隐含波动率
================================================================================
"""
import requests
from .core import UA

SINA_OPT_HDR = {"Referer": "https://stock.finance.sina.com.cn/", "User-Agent": UA}


def _opt_f(x):
    try: return float(x)
    except Exception: return x


def _sina_opt_list(param: str) -> list:
    """新浪 hq.sinajs.cn 取值（GBK，逗号分隔）"""
    r = requests.get(f"https://hq.sinajs.cn/list={param}", headers=SINA_OPT_HDR, timeout=10)
    r.encoding = "gbk"
    t = r.text
    return t.split('"')[1].split(",") if '"' in t else []


def sina_option_codes(underlying: str = "510050", call: bool = True) -> dict:
    """
    ETF期权合约清单。
    underlying: 510050/510300/588000/510500
    返回 {月份YYMM: [合约代码,...]}，第一个 key 即近月
    """
    cate = {"510050": "50ETF", "510300": "300ETF",
            "588000": "科创50ETF", "510500": "500ETF"}.get(underlying, "50ETF")
    url = ("https://stock.finance.sina.com.cn/futures/api/openapi.php/"
           f"StockOptionService.getStockName?exchange=null&cate={cate}")
    try:
        months = requests.get(url, headers=SINA_OPT_HDR, timeout=10).json()["result"]["data"]["contractMonth"]
    except Exception as e:
        print(f"[WARN] 期权月份获取失败: {e}")
        return {}
    months = [m.replace("-", "")[2:] for m in months[1:]]
    flag = "OP_UP_" if call else "OP_DOWN_"
    out = {}
    for m in months:
        codes = [c.replace("CON_OP_", "") for c in _sina_opt_list(f"{flag}{underlying}{m}")
                 if c.startswith("CON_OP_")]
        if codes:
            out[m] = codes
    return out


def sina_option_tquote(code: str) -> dict:
    """期权T型报价"""
    v = _sina_opt_list(f"CON_OP_{code}")
    if len(v) < 43:
        return {}
    return {"bid_vol": _opt_f(v[0]), "bid": _opt_f(v[1]), "last": _opt_f(v[2]),
        "ask": _opt_f(v[3]), "ask_vol": _opt_f(v[4]), "open_interest": _opt_f(v[5]),
        "pct": _opt_f(v[6]), "strike": _opt_f(v[7]), "prev_close": _opt_f(v[8]),
        "open": _opt_f(v[9]), "limit_up": _opt_f(v[10]), "limit_down": _opt_f(v[11]),
        "name": v[37], "amplitude": _opt_f(v[38]), "high": _opt_f(v[39]),
        "low": _opt_f(v[40]), "volume": _opt_f(v[41]), "amount": _opt_f(v[42])}


def sina_option_greeks(code: str) -> dict:
    """期权希腊字母 + 隐含波动率"""
    raw = _sina_opt_list(f"CON_SO_{code}")
    if len(raw) < 16:
        return {}
    v = [raw[0]] + raw[4:]
    return {"name": v[0], "volume": _opt_f(v[1]), "delta": _opt_f(v[2]),
        "gamma": _opt_f(v[3]), "theta": _opt_f(v[4]), "vega": _opt_f(v[5]),
        "iv": _opt_f(v[6]), "high": _opt_f(v[7]), "low": _opt_f(v[8]),
        "trade_code": v[9], "strike": _opt_f(v[10]), "last": _opt_f(v[11]), "theory": _opt_f(v[12])}

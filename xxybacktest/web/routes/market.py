"""行情层 Blueprint — 指数/ETF/个股/K线/盘口 (mootdx + 腾讯 + 百度)"""
from datetime import datetime
from flask import Blueprint, render_template, request

from . import ok, err

market_bp = Blueprint("market", __name__)

INDEX_MAP = {
    "000001": "上证指数", "399001": "深证成指", "399006": "创业板指",
    "000300": "沪深300",  "000688": "科创50",   "000016": "上证50",
}
HOT_ETF = ["510050", "510300", "510500", "588000", "159915", "512880", "512100", "159919", "513100", "518880"]
FREQ_MAP = {
    "1m": (8, 240), "5m": (0, 240), "15m": (1, 240), "30m": (2, 240),
    "60m": (3, 240), "day": (9, 200), "week": (5, 100), "month": (6, 50),
}


# ═══════════════════════════════════════════════════════════════
# 页面路由
# ═══════════════════════════════════════════════════════════════

@market_bp.route("/market")
def market_dashboard():
    return render_template("market.html")


@market_bp.route("/live")
def live_dashboard():
    """向后兼容旧URL"""
    return render_template("live.html")


# ═══════════════════════════════════════════════════════════════
# 指数 + ETF
# ═══════════════════════════════════════════════════════════════

@market_bp.route("/api/market/index")
@market_bp.route("/api/live/index")  # 向后兼容
def api_market_index():
    try:
        from xxybacktest.data_providers import tencent_quote
        codes = list(INDEX_MAP.keys())
        q = tencent_quote(codes)
        indices = []
        for code in codes:
            item = q.get(code, {})
            indices.append({
                "code": code, "name": INDEX_MAP[code],
                "price": item.get("price", 0), "change_pct": item.get("change_pct", 0),
                "change_amt": item.get("change_amt", 0), "turnover_pct": item.get("turnover_pct", 0),
            })
        return ok(indices)
    except Exception as e:
        return err(str(e))


@market_bp.route("/api/market/etf")
@market_bp.route("/api/live/etf")  # 向后兼容
def api_market_etf():
    try:
        from xxybacktest.data_providers import tencent_quote
        q = tencent_quote(HOT_ETF)
        etfs = []
        for code in HOT_ETF:
            item = q.get(code, {})
            etfs.append({
                "code": code, "name": item.get("name", code),
                "price": item.get("price", 0), "change_pct": item.get("change_pct", 0),
                "pe_ttm": item.get("pe_ttm", 0), "pb": item.get("pb", 0),
                "mcap_yi": item.get("mcap_yi", 0),
            })
        return ok(etfs)
    except Exception as e:
        return err(str(e))


# ═══════════════════════════════════════════════════════════════
# 个股行情 (腾讯 88字段)
# ═══════════════════════════════════════════════════════════════

@market_bp.route("/api/market/quote")
@market_bp.route("/api/live/quote")  # 向后兼容
def api_market_quote():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import tencent_quote
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        q = tencent_quote([pure])
        item = q.get(pure, {})
        return ok({
            "code": pure,
            "name": item.get("name", ""),
            "price": item.get("price", 0),
            "last_close": item.get("last_close", 0),
            "open": item.get("open", 0),
            "high": item.get("high", 0),
            "low": item.get("low", 0),
            "change_amt": item.get("change_amt", 0),
            "change_pct": item.get("change_pct", 0),
            "pe_ttm": item.get("pe_ttm", 0),
            "pe_static": item.get("pe_static", 0),
            "pb": item.get("pb", 0),
            "mcap_yi": item.get("mcap_yi", 0),
            "float_mcap_yi": item.get("float_mcap_yi", 0),
            "turnover_pct": item.get("turnover_pct", 0),
            "amount_wan": item.get("amount_wan", 0),
            "amplitude_pct": item.get("amplitude_pct", 0),
            "vol_ratio": item.get("vol_ratio", 0),
            "limit_up": item.get("limit_up", 0),
            "limit_down": item.get("limit_down", 0),
        })
    except Exception as e:
        return err(str(e))


# ═══════════════════════════════════════════════════════════════
# K线 (本地 daily_bar + mootdx 全周期)
# ═══════════════════════════════════════════════════════════════

@market_bp.route("/api/market/kline")
@market_bp.route("/api/live/kline")  # 向后兼容
def api_market_kline():
    code = request.args.get("code", "000001").strip()
    limit = int(request.args.get("limit", 200))
    try:
        from xxydb import xxydb
        db = xxydb(path="./data")
        try:
            if "." not in code:
                found = None
                for sfx in [".SZ", ".SH", ".BJ"]:
                    try:
                        c = db.query(
                            f"SELECT COUNT(*) as n FROM daily_bar WHERE instrument = '{code}{sfx}'"
                        ).df()
                        if c["n"].iloc[0] > 0: found = code + sfx; break
                    except Exception: continue
                code = found or code + ".SZ"
            df = db.query(f"""
                SELECT date, open, high, low, close, volume, change_ratio
                FROM daily_bar WHERE instrument = '{code}'
                ORDER BY date DESC LIMIT {limit}
            """).df()
        finally:
            db.close()
        if df is None or df.empty:
            return err(f"No data for {code}")
        df = df.sort_values('date')
        klines = [{"date": str(r["date"])[:10], "open": float(r["open"]),
                    "close": float(r["close"]), "high": float(r["high"]),
                    "low": float(r["low"]), "volume": int(r["volume"])}
                  for _, r in df.iterrows()]
        closes = [k["close"] for k in klines]
        def _ma(arr, n):
            res = [None] * len(arr)
            for i in range(n-1, len(arr)):
                res[i] = round(sum(arr[i-n+1:i+1]) / n, 3)
            return res
        ma5, ma10, ma20, ma60 = _ma(closes, 5), _ma(closes, 10), _ma(closes, 20), _ma(closes, 60)
        for i, k in enumerate(klines):
            k["ma5"] = ma5[i]; k["ma10"] = ma10[i]; k["ma20"] = ma20[i]; k["ma60"] = ma60[i]
        return ok({"code": code, "klines": klines, "total": len(klines)})
    except Exception as e:
        return err(str(e))


@market_bp.route("/api/market/orderbook")
@market_bp.route("/api/live/orderbook")  # 向后兼容
def api_market_orderbook():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import tdx_quotes
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        df = tdx_quotes([pure])
        if df is None or (hasattr(df, 'empty') and df.empty):
            return ok(None, note="market_closed")
        row = df.iloc[0] if hasattr(df, 'iloc') else df
        book = {
            "price": float(row.get("price", 0)) if not isinstance(row, dict) else row.get("price", 0),
            "open": float(row.get("open", 0) or 0),
            "high": float(row.get("high", 0) or 0),
            "low": float(row.get("low", 0) or 0),
            "last_close": float(row.get("last_close", 0) or 0),
            "volume": int(row.get("vol", 0) or 0),
            "amount": float(row.get("amount", 0) or 0),
            "servertime": str(row.get("servertime", "")),
            "bids": [
                {"price": float(row.get(f"bid{i}", 0) or 0), "vol": int(row.get(f"bid_vol{i}", 0) or 0)}
                for i in range(1, 6)
            ],
            "asks": [
                {"price": float(row.get(f"ask{i}", 0) or 0), "vol": int(row.get(f"ask_vol{i}", 0) or 0)}
                for i in range(1, 6)
            ],
        }
        return ok(book)
    except Exception as e:
        return err(str(e))


@market_bp.route("/api/market/tdx_bars")
@market_bp.route("/api/live/tdx_bars")  # 向后兼容
def api_market_tdx_bars():
    code = request.args.get("code", "000001").strip()
    freq = request.args.get("freq", "day")
    try:
        from xxybacktest.data_providers import tdx_bars
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        freq_val, offset = FREQ_MAP.get(freq, (9, 200))
        df = tdx_bars(symbol=pure, frequency=freq_val, offset=offset)
        if df is None or (hasattr(df, 'empty') and df.empty):
            return ok(None, note="market_closed_or_no_data")
        bars = []
        for _, r in df.iterrows():
            bars.append({
                "date": str(r.get("datetime", "")) if "datetime" in df.columns else "",
                "open": float(r.get("open", 0)), "close": float(r.get("close", 0)),
                "high": float(r.get("high", 0)), "low": float(r.get("low", 0)),
                "volume": int(r.get("vol", 0) or r.get("volume", 0) or 0),
            })
        return ok({"code": pure, "freq": freq, "bars": bars, "total": len(bars)})
    except Exception as e:
        return err(str(e))

"""Live data dashboard — comprehensive real-time market data"""
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request

live_bp = Blueprint("live", __name__)

INDEX_MAP = {
    "000001": "上证指数", "399001": "深证成指", "399006": "创业板指",
    "000300": "沪深300",  "000688": "科创50",   "000016": "上证50",
}

HOT_ETF = ["510050", "510300", "510500", "588000", "159915", "512880", "512100", "159919", "513100", "518880"]

@live_bp.route("/live")
def live_dashboard():
    return render_template("live.html")


@live_bp.route("/signals")
def signals_dashboard():
    return render_template("signals.html")


@live_bp.route("/capital")
def capital_dashboard():
    return render_template("capital.html")


@live_bp.route("/fundamentals")
def fundamentals_dashboard():
    return render_template("fundamentals.html")


# ═══════════════════════════════════════════════════════════════
# 基本面 + 资讯 API
# ═══════════════════════════════════════════════════════════════

@live_bp.route("/api/live/finance")
def api_live_finance():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import tdx_finance
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        df = tdx_finance(pure)
        if df is None or (hasattr(df,'empty') and df.empty):
            return _ok(None, note="mootdx_finance_empty")
        fields = {}
        for _, row in df.iterrows():
            for col in df.columns:
                fields[col] = str(row[col]) if row[col] is not None else ""
        return _ok({"code": pure, "fields": fields, "total_fields": len(fields)})
    except Exception as e:
        return _err(str(e))


@live_bp.route("/api/live/f10")
def api_live_f10():
    code = request.args.get("code", "000001").strip()
    cat = request.args.get("cat", "最新提示")
    try:
        from xxybacktest.data_providers import tdx_f10
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        text = tdx_f10(pure, cat)
        return _ok({"code": pure, "category": cat, "text": str(text) if text else ""})
    except Exception as e:
        return _err(str(e))


@live_bp.route("/api/live/fin_report")
def api_live_fin_report():
    code = request.args.get("code", "000001").strip()
    rtype = request.args.get("type", "lrb")
    try:
        from xxybacktest.data_providers import sina_financial_report
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        data = sina_financial_report(pure, rtype, num=8)
        return _ok({"code": pure, "type": rtype, "reports": data, "total": len(data)})
    except Exception as e:
        return _err(str(e))


@live_bp.route("/api/live/stock_news")
def api_live_stock_news():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import eastmoney_stock_news, eastmoney_global_news
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        stock_news = eastmoney_stock_news(pure, 15)
        global_news = eastmoney_global_news(15)
        return _ok({"code": pure, "stock_news": stock_news, "global_news": global_news})
    except Exception as e:
        return _err(str(e))


@live_bp.route("/api/live/announcements")
def api_live_announcements():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import cninfo_announcements
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        data = cninfo_announcements(pure, 30)
        return _ok({"code": pure, "announcements": data, "total": len(data)})
    except Exception as e:
        return _err(str(e))

def _ok(data, **extra):
    return jsonify({"data": data, "time": datetime.now().strftime("%H:%M:%S"), **extra})

def _err(msg):
    return jsonify({"data": None, "error": msg, "time": datetime.now().strftime("%H:%M:%S")})


# ═══════════════════════════════════════════════════════════════
# 指数 + ETF 行情
# ═══════════════════════════════════════════════════════════════
@live_bp.route("/api/live/index")
def api_live_index():
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
        return _ok(indices)
    except Exception as e:
        return _err(str(e))


@live_bp.route("/api/live/etf")
def api_live_etf():
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
        return _ok(etfs)
    except Exception as e:
        return _err(str(e))


# ═══════════════════════════════════════════════════════════════
# 个股完整估值 (腾讯财经 88字段)
# ═══════════════════════════════════════════════════════════════
@live_bp.route("/api/live/quote")
def api_live_quote():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import tencent_quote, get_prefix
        # 腾讯用纯数字
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        q = tencent_quote([pure])
        item = q.get(pure, {})
        return _ok({
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
        return _err(str(e))


# ═══════════════════════════════════════════════════════════════
# K线 — 本地 daily_bar 全历史
# ═══════════════════════════════════════════════════════════════
@live_bp.route("/api/live/kline")
def api_live_kline():
    code = request.args.get("code", "000001").strip()
    limit = int(request.args.get("limit", 200))
    try:
        from xxydb import xxydb
        import pandas as pd

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
            return _err(f"No data for {code}")

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

        return _ok({"code": code, "klines": klines, "total": len(klines)})
    except Exception as e:
        return _err(str(e))


# ═══════════════════════════════════════════════════════════════
# mootdx 实时盘口 (五档买卖 + 46字段)
# ═══════════════════════════════════════════════════════════════
@live_bp.route("/api/live/orderbook")
def api_live_orderbook():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import tdx_quotes
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        df = tdx_quotes([pure])
        if df is None or (hasattr(df, 'empty') and df.empty):
            return _ok(None, note="market_closed")

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
        return _ok(book)
    except Exception as e:
        return _err(str(e))


# ═══════════════════════════════════════════════════════════════
# mootdx K线全周期
# ═══════════════════════════════════════════════════════════════
FREQ_MAP = {
    "1m": (8, 240), "5m": (0, 240), "15m": (1, 240), "30m": (2, 240),
    "60m": (3, 240), "day": (9, 200), "week": (5, 100), "month": (6, 50),
}

@live_bp.route("/api/live/tdx_bars")
def api_live_tdx_bars():
    code = request.args.get("code", "000001").strip()
    freq = request.args.get("freq", "day")
    try:
        from xxybacktest.data_providers import tdx_bars
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        freq_val, offset = FREQ_MAP.get(freq, (9, 200))
        df = tdx_bars(symbol=pure, frequency=freq_val, offset=offset)
        if df is None or (hasattr(df, 'empty') and df.empty):
            return _ok(None, note="market_closed_or_no_data")

        bars = []
        for _, r in df.iterrows():
            bars.append({
                "date": str(r.get("datetime", "")) if "datetime" in df.columns else "",
                "open": float(r.get("open", 0)), "close": float(r.get("close", 0)),
                "high": float(r.get("high", 0)), "low": float(r.get("low", 0)),
                "volume": int(r.get("vol", 0) or r.get("volume", 0) or 0),
            })
        return _ok({"code": pure, "freq": freq, "bars": bars, "total": len(bars)})
    except Exception as e:
        return _err(str(e))


# ═══════════════════════════════════════════════════════════════
# 以下保持不变
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# 信号层：同花顺热点 + 北向资金 + 龙虎榜 + 解禁 + 概念板块
# ═══════════════════════════════════════════════════════════════

@live_bp.route("/api/live/hot_stocks")
def api_live_hot_stocks():
    try:
        from xxybacktest.data_providers import ths_hot_reason
        df = ths_hot_reason()
        if df is None or df.empty:
            return _ok([], note="no_data")
        rows = []
        for _, r in df.iterrows():
            rows.append({
                "code": str(r.get("代码", r.get("code", ""))),
                "name": str(r.get("名称", r.get("name", ""))),
                "reason": str(r.get("题材归因", r.get("reason", ""))),
                "change_pct": float(r.get("涨幅%", r.get("zhangfu", 0) or 0)),
                "turnover": float(r.get("换手率%", r.get("huanshou", 0) or 0)),
                "amount": float(r.get("成交额", r.get("chengjiaoe", 0) or 0)),
            })
        return _ok(rows)
    except Exception as e:
        return _err(str(e))


@live_bp.route("/api/live/northbound")
def api_live_northbound():
    try:
        from xxybacktest.data_providers import hsgt_realtime, _load_northbound_history
        realtime = hsgt_realtime()
        history = _load_northbound_history(10)
        points = []
        if realtime is not None and not realtime.empty:
            for _, r in realtime.iterrows():
                points.append({
                    "time": str(r.get("time", "")),
                    "hgt": float(r.get("hgt_yi", 0) or 0),
                    "sgt": float(r.get("sgt_yi", 0) or 0),
                })
        hist_rows = []
        if history is not None and not history.empty:
            for _, r in history.iterrows():
                hist_rows.append({
                    "date": str(r.get("date", ""))[:10],
                    "hgt": float(r.get("hgt", 0) or 0),
                    "sgt": float(r.get("sgt", 0) or 0),
                })
        return _ok({"realtime": points, "history": hist_rows, "total_points": len(points)})
    except Exception as e:
        return _err(str(e))


@live_bp.route("/api/live/dragon_tiger")
def api_live_dragon_tiger():
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    try:
        from xxybacktest.data_providers import daily_dragon_tiger
        data = daily_dragon_tiger(date)
        return _ok(data)
    except Exception as e:
        return _err(str(e))


@live_bp.route("/api/live/lockup")
def api_live_lockup():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import lockup_expiry
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        today = datetime.now().strftime("%Y-%m-%d")
        data = lockup_expiry(pure, today, forward_days=90)
        return _ok(data)
    except Exception as e:
        return _err(str(e))


@live_bp.route("/api/live/concept")
def api_live_concept():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import eastmoney_concept_blocks
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        data = eastmoney_concept_blocks(pure)
        return _ok(data)
    except Exception as e:
        return _err(str(e))


# ═══════════════════════════════════════════════════════════════
# 主力筹码：资金流 + 融资融券 + 大宗交易 + 股东户数 + 分红
# ═══════════════════════════════════════════════════════════════

@live_bp.route("/api/live/fund_flow")
def api_live_fund_flow():
    code = request.args.get("code", "000001").strip()
    pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
    source = ""
    data = []
    # 主源：东财 120日资金流
    try:
        from xxybacktest.data_providers import stock_fund_flow_120d
        data = stock_fund_flow_120d(pure)
        if data and len(data) > 0:
            source = "东财 push2his"
    except Exception:
        pass
    # 降级：新浪日度资金流
    if not data:
        try:
            from xxybacktest.data_providers import fund_flow_backup
            raw = fund_flow_backup(pure, 60)
            if raw:
                data = [{
                    "date": r.get("date", ""),
                    "main_net": float(r.get("net_amount", 0) or 0),
                    "super_net": 0, "large_net": 0, "mid_net": 0, "small_net": 0,
                } for r in raw if r.get("date")]
                source = "新浪 (东财受限)"
        except Exception:
            pass
    return _ok({"code": pure, "flow": data, "total": len(data), "source": source})


@live_bp.route("/api/live/margin")
def api_live_margin():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import margin_trading
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        data = margin_trading(pure)
        return _ok(data)
    except Exception as e:
        return _err(str(e))


@live_bp.route("/api/live/block_trade")
def api_live_block_trade():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import block_trade
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        data = block_trade(pure)
        return _ok(data)
    except Exception as e:
        return _err(str(e))


@live_bp.route("/api/live/holder_num")
def api_live_holder_num():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import holder_num_change
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        data = holder_num_change(pure)
        return _ok(data)
    except Exception as e:
        return _err(str(e))


@live_bp.route("/api/live/dividend")
def api_live_dividend():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import dividend_history
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        data = dividend_history(pure)
        return _ok(data)
    except Exception as e:
        return _err(str(e))


@live_bp.route("/api/live/news")
def api_live_news():
    try:
        from xxybacktest.data_providers import cls_telegraph
        return _ok(cls_telegraph(15))
    except Exception as e:
        return _err(str(e))


@live_bp.route("/api/live/industry")
def api_live_industry():
    try:
        from xxybacktest.data_providers import industry_comparison
        data = industry_comparison(10)
        if data and data.get("total", 0) > 0:
            return _ok({**data, "source": "Eastmoney"})
    except Exception: pass
    try:
        from xxybacktest.data_providers import ths_hot_reason
        from collections import Counter
        df = ths_hot_reason()
        if df is not None and not df.empty:
            col = "题材归因" if "题材归因" in df.columns else ("reason" if "reason" in df.columns else None)
            tags = []
            if col:
                for r in df[col].dropna():
                    tags.extend([t.strip() for t in str(r).split("+") if t.strip()])
            cnt = Counter(tags)
            top = [{"rank": i+1, "name": tag, "count": n, "change_pct": 0}
                   for i, (tag, n) in enumerate(cnt.most_common(15))]
            return _ok({"top": top[:10], "bottom": [], "total": len(cnt), "source": "THS"})
    except Exception: pass
    return _err("Industry unavailable")


@live_bp.route("/api/live/limit-up")
def api_live_limit_up():
    try:
        from xxybacktest.data_providers import limit_up_sentiment, em_zt_pool
        today = datetime.now().strftime("%Y%m%d")
        return _ok({"sentiment": limit_up_sentiment(today), "top_stocks": em_zt_pool(today)[:20]})
    except Exception as e:
        return _err(str(e))


@live_bp.route("/api/live/hot")
def api_live_hot():
    try:
        from xxybacktest.data_providers import ths_hot_list
        return _ok(ths_hot_list("day")[:12])
    except Exception as e:
        return _err(str(e))

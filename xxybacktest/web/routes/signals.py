"""信号层 Blueprint — 强势股/北向资金/龙虎榜/解禁/概念/涨停池/人气榜"""
from datetime import datetime
from flask import Blueprint, render_template, request

from . import ok, err

signals_bp = Blueprint("signals", __name__)


# ═══════════════════════════════════════════════════════════════
# 页面路由
# ═══════════════════════════════════════════════════════════════

@signals_bp.route("/signals")
def signals_dashboard():
    return render_template("signals.html")


# ═══════════════════════════════════════════════════════════════
# 同花顺热点强势股
# ═══════════════════════════════════════════════════════════════

@signals_bp.route("/api/signals/hot_stocks")
@signals_bp.route("/api/live/hot_stocks")  # 向后兼容
def api_signals_hot_stocks():
    try:
        from xxybacktest.data_providers import ths_hot_reason
        df = ths_hot_reason()
        if df is None or df.empty:
            return ok([], note="no_data")
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
        return ok(rows)
    except Exception as e:
        return err(str(e))


# ═══════════════════════════════════════════════════════════════
# 北向资金
# ═══════════════════════════════════════════════════════════════

@signals_bp.route("/api/signals/northbound")
@signals_bp.route("/api/live/northbound")  # 向后兼容
def api_signals_northbound():
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
        return ok({"realtime": points, "history": hist_rows, "total_points": len(points)})
    except Exception as e:
        return err(str(e))


# ═══════════════════════════════════════════════════════════════
# 龙虎榜
# ═══════════════════════════════════════════════════════════════

@signals_bp.route("/api/signals/dragon_tiger")
@signals_bp.route("/api/live/dragon_tiger")  # 向后兼容
def api_signals_dragon_tiger():
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    try:
        from xxybacktest.data_providers import daily_dragon_tiger
        data = daily_dragon_tiger(date)
        return ok(data)
    except Exception as e:
        return err(str(e))


# ═══════════════════════════════════════════════════════════════
# 解禁
# ═══════════════════════════════════════════════════════════════

@signals_bp.route("/api/signals/lockup")
@signals_bp.route("/api/live/lockup")  # 向后兼容
def api_signals_lockup():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import lockup_expiry
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        today = datetime.now().strftime("%Y-%m-%d")
        data = lockup_expiry(pure, today, forward_days=90)
        return ok(data)
    except Exception as e:
        return err(str(e))


# ═══════════════════════════════════════════════════════════════
# 概念板块
# ═══════════════════════════════════════════════════════════════

@signals_bp.route("/api/signals/concept")
@signals_bp.route("/api/live/concept")  # 向后兼容
def api_signals_concept():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import eastmoney_concept_blocks
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        data = eastmoney_concept_blocks(pure)
        return ok(data)
    except Exception as e:
        return err(str(e))


# ═══════════════════════════════════════════════════════════════
# 涨停池 + 情绪
# ═══════════════════════════════════════════════════════════════

@signals_bp.route("/api/signals/limit-up")
@signals_bp.route("/api/live/limit-up")  # 向后兼容
def api_signals_limit_up():
    try:
        from xxybacktest.data_providers import limit_up_sentiment, em_zt_pool
        today = datetime.now().strftime("%Y%m%d")
        return ok({"sentiment": limit_up_sentiment(today), "top_stocks": em_zt_pool(today)[:20]})
    except Exception as e:
        return err(str(e))


# ═══════════════════════════════════════════════════════════════
# 人气榜
# ═══════════════════════════════════════════════════════════════

@signals_bp.route("/api/signals/hot")
@signals_bp.route("/api/live/hot")  # 向后兼容
def api_signals_hot():
    try:
        from xxybacktest.data_providers import ths_hot_list
        return ok(ths_hot_list("day")[:12])
    except Exception as e:
        return err(str(e))


# ═══════════════════════════════════════════════════════════════
# 行业排名
# ═══════════════════════════════════════════════════════════════

@signals_bp.route("/api/signals/industry")
@signals_bp.route("/api/live/industry")  # 向后兼容
def api_signals_industry():
    try:
        from xxybacktest.data_providers import industry_comparison
        data = industry_comparison(10)
        if data and data.get("total", 0) > 0:
            return ok({**data, "source": "Eastmoney"})
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
            return ok({"top": top[:10], "bottom": [], "total": len(cnt), "source": "THS"})
    except Exception: pass
    return err("Industry unavailable")

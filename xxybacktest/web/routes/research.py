"""研报层 Blueprint — 东财研报/同花顺EPS预期/问财搜索"""
from flask import Blueprint, render_template, request

from . import ok, err

research_bp = Blueprint("research", __name__)


# ═══════════════════════════════════════════════════════════════
# 页面路由
# ═══════════════════════════════════════════════════════════════

@research_bp.route("/research")
def research_dashboard():
    return render_template("research.html")


# ═══════════════════════════════════════════════════════════════
# 东财研报列表
# ═══════════════════════════════════════════════════════════════

@research_bp.route("/api/research/reports")
def api_research_reports():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import eastmoney_reports
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        data = eastmoney_reports(pure, max_pages=3)
        return ok({"code": pure, "reports": data, "total": len(data)})
    except Exception as e:
        return err(str(e))


# ═══════════════════════════════════════════════════════════════
# 同花顺一致预期EPS
# ═══════════════════════════════════════════════════════════════

@research_bp.route("/api/research/eps_forecast")
def api_research_eps_forecast():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import ths_eps_forecast
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        df = ths_eps_forecast(pure)
        if df is None or df.empty:
            return ok({"code": pure, "eps_forecast": [], "note": "no_data"})
        # DataFrame -> list of dicts for JSON
        data = df.to_dict(orient="records")
        return ok({"code": pure, "eps_forecast": data, "columns": list(df.columns), "total": len(data)})
    except Exception as e:
        return err(str(e))


# ═══════════════════════════════════════════════════════════════
# 问财语义搜索
# ═══════════════════════════════════════════════════════════════

@research_bp.route("/api/research/iwencai")
def api_research_iwencai():
    query = request.args.get("q", "").strip()
    if not query:
        return err("缺少参数 q")
    try:
        from xxybacktest.data_providers import iwencai_search, dedup_articles
        articles = iwencai_search(query)
        articles = dedup_articles(articles)
        return ok({"query": query, "articles": articles[:30], "total": len(articles)})
    except Exception as e:
        return err(str(e))

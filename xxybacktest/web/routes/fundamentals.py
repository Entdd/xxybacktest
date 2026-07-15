"""基础数据层 Blueprint — 财务快照(mootdx 37字段)/F10(9类)/新浪财报三表"""
from flask import Blueprint, render_template, request

from . import ok, err

fundamentals_bp = Blueprint("fundamentals", __name__)


# ═══════════════════════════════════════════════════════════════
# 页面路由
# ═══════════════════════════════════════════════════════════════

@fundamentals_bp.route("/fundamentals")
def fundamentals_dashboard():
    return render_template("fundamentals.html")


# ═══════════════════════════════════════════════════════════════
# 财务快照 (mootdx 37字段)
# ═══════════════════════════════════════════════════════════════

@fundamentals_bp.route("/api/fundamentals/finance")
@fundamentals_bp.route("/api/live/finance")  # 向后兼容
def api_fundamentals_finance():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import tdx_finance
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        df = tdx_finance(pure)
        if df is None or (hasattr(df,'empty') and df.empty):
            return ok(None, note="mootdx_finance_empty")
        fields = {}
        for _, row in df.iterrows():
            for col in df.columns:
                fields[col] = str(row[col]) if row[col] is not None else ""
        return ok({"code": pure, "fields": fields, "total_fields": len(fields)})
    except Exception as e:
        return err(str(e))


# ═══════════════════════════════════════════════════════════════
# F10 (9类)
# ═══════════════════════════════════════════════════════════════

@fundamentals_bp.route("/api/fundamentals/f10")
@fundamentals_bp.route("/api/live/f10")  # 向后兼容
def api_fundamentals_f10():
    code = request.args.get("code", "000001").strip()
    cat = request.args.get("cat", "最新提示")
    try:
        from xxybacktest.data_providers import tdx_f10
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        text = tdx_f10(pure, cat)
        return ok({"code": pure, "category": cat, "text": str(text) if text else ""})
    except Exception as e:
        return err(str(e))


# ═══════════════════════════════════════════════════════════════
# 新浪财报三表
# ═══════════════════════════════════════════════════════════════

@fundamentals_bp.route("/api/fundamentals/fin_report")
@fundamentals_bp.route("/api/live/fin_report")  # 向后兼容
def api_fundamentals_fin_report():
    code = request.args.get("code", "000001").strip()
    rtype = request.args.get("type", "lrb")
    try:
        from xxybacktest.data_providers import sina_financial_report
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        data = sina_financial_report(pure, rtype, num=8)
        return ok({"code": pure, "type": rtype, "reports": data, "total": len(data)})
    except Exception as e:
        return err(str(e))

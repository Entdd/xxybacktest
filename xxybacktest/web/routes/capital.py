"""资金层 Blueprint — 资金流/融资融券/大宗交易/股东户数/分红"""
from datetime import datetime
from flask import Blueprint, render_template, request

from . import ok, err

capital_bp = Blueprint("capital", __name__)


# ═══════════════════════════════════════════════════════════════
# 页面路由
# ═══════════════════════════════════════════════════════════════

@capital_bp.route("/capital")
def capital_dashboard():
    return render_template("capital.html")


# ═══════════════════════════════════════════════════════════════
# 资金流 (东财 push2his → 新浪降级)
# ═══════════════════════════════════════════════════════════════

@capital_bp.route("/api/capital/fund_flow")
@capital_bp.route("/api/live/fund_flow")  # 向后兼容
def api_capital_fund_flow():
    code = request.args.get("code", "000001").strip()
    pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
    source = ""
    data = []
    try:
        from xxybacktest.data_providers import stock_fund_flow_120d
        data = stock_fund_flow_120d(pure)
        if data and len(data) > 0:
            source = "东财 push2his"
    except Exception:
        pass
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
    return ok({"code": pure, "flow": data, "total": len(data), "source": source})


# ═══════════════════════════════════════════════════════════════
# 融资融券
# ═══════════════════════════════════════════════════════════════

@capital_bp.route("/api/capital/margin")
@capital_bp.route("/api/live/margin")  # 向后兼容
def api_capital_margin():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import margin_trading
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        data = margin_trading(pure)
        return ok(data)
    except Exception as e:
        return err(str(e))


# ═══════════════════════════════════════════════════════════════
# 大宗交易
# ═══════════════════════════════════════════════════════════════

@capital_bp.route("/api/capital/block_trade")
@capital_bp.route("/api/live/block_trade")  # 向后兼容
def api_capital_block_trade():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import block_trade
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        data = block_trade(pure)
        return ok(data)
    except Exception as e:
        return err(str(e))


# ═══════════════════════════════════════════════════════════════
# 股东户数
# ═══════════════════════════════════════════════════════════════

@capital_bp.route("/api/capital/holder_num")
@capital_bp.route("/api/live/holder_num")  # 向后兼容
def api_capital_holder_num():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import holder_num_change
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        data = holder_num_change(pure)
        return ok(data)
    except Exception as e:
        return err(str(e))


# ═══════════════════════════════════════════════════════════════
# 分红送转
# ═══════════════════════════════════════════════════════════════

@capital_bp.route("/api/capital/dividend")
@capital_bp.route("/api/live/dividend")  # 向后兼容
def api_capital_dividend():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import dividend_history
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        data = dividend_history(pure)
        return ok(data)
    except Exception as e:
        return err(str(e))

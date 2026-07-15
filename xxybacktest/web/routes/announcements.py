"""公告层 Blueprint — 巨潮公告/财联社快讯/东财新闻"""
from flask import Blueprint, render_template, request

from . import ok, err

announcements_bp = Blueprint("announcements", __name__)


# ═══════════════════════════════════════════════════════════════
# 页面路由
# ═══════════════════════════════════════════════════════════════

@announcements_bp.route("/announcements")
def announcements_dashboard():
    return render_template("announcements.html")


# ═══════════════════════════════════════════════════════════════
# 巨潮全量公告
# ═══════════════════════════════════════════════════════════════

@announcements_bp.route("/api/announcements/cninfo")
@announcements_bp.route("/api/live/announcements")  # 向后兼容
def api_announcements_cninfo():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import cninfo_announcements
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        data = cninfo_announcements(pure, 30)
        return ok({"code": pure, "announcements": data, "total": len(data)})
    except Exception as e:
        return err(str(e))


# ═══════════════════════════════════════════════════════════════
# 个股新闻 + 全球资讯
# ═══════════════════════════════════════════════════════════════

@announcements_bp.route("/api/announcements/stock_news")
@announcements_bp.route("/api/live/stock_news")  # 向后兼容
def api_announcements_stock_news():
    code = request.args.get("code", "000001").strip()
    try:
        from xxybacktest.data_providers import eastmoney_stock_news, eastmoney_global_news
        pure = code.replace(".SZ","").replace(".SH","").replace(".BJ","")
        stock_news = eastmoney_stock_news(pure, 15)
        global_news = eastmoney_global_news(15)
        return ok({"code": pure, "stock_news": stock_news, "global_news": global_news})
    except Exception as e:
        return err(str(e))


# ═══════════════════════════════════════════════════════════════
# 财联社快讯
# ═══════════════════════════════════════════════════════════════

@announcements_bp.route("/api/announcements/telegraph")
@announcements_bp.route("/api/live/news")  # 向后兼容
def api_announcements_telegraph():
    try:
        from xxybacktest.data_providers import cls_telegraph
        return ok(cls_telegraph(15))
    except Exception as e:
        return err(str(e))

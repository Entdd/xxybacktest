"""用户层 Blueprint — 账户管理/策略参数/偏好设置"""
import os
from flask import Blueprint, render_template, jsonify, request

from . import ok, err

user_bp = Blueprint("user", __name__)
DEFAULT_DATA_PATH = os.environ.get('XXY_DATA_PATH', './data')


# ═══════════════════════════════════════════════════════════════
# 页面路由
# ═══════════════════════════════════════════════════════════════

@user_bp.route("/user")
def user_dashboard():
    return render_template("user.html")


# ═══════════════════════════════════════════════════════════════
# 用户概览 API
# ═══════════════════════════════════════════════════════════════

@user_bp.route("/api/user/overview")
def api_user_overview():
    """返回所有账户汇总 + 分类统计"""
    try:
        from xxybacktest.simulation.submitter import list_accounts
        accounts = list_accounts(data_path=DEFAULT_DATA_PATH)
        total = len(accounts)
        running = sum(1 for a in accounts if a.get('status') == 'running')
        sim_count = sum(1 for a in accounts if a.get('account_type') == 'sim')
        live_count = sum(1 for a in accounts if a.get('account_type') == 'live')
        return ok({
            "total_accounts": total,
            "running": running,
            "sim_count": sim_count,
            "live_count": live_count,
            "accounts": [{
                "account_id": a.get("account_id"),
                "name": a.get("name"),
                "status": a.get("status"),
                "account_type": a.get("account_type", "sim"),
                "created_at": str(a.get("created_at", ""))[:10],
            } for a in accounts],
        })
    except Exception as e:
        return err(str(e))

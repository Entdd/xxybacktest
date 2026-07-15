"""Flask 应用入口 —— 9层架构 Blueprint 注册"""
from flask import Flask
from pathlib import Path


def create_app():
    app = Flask(__name__, template_folder=str(Path(__file__).parent / 'templates'))

    # ── Layer 1-6: 数据看板层 ──
    from .routes.market import market_bp
    from .routes.research import research_bp
    from .routes.signals import signals_bp
    from .routes.capital import capital_bp
    from .routes.fundamentals import fundamentals_bp
    from .routes.announcements import announcements_bp

    # ── Layer 7-9: 因子 / 用户 / 任务 ──
    from .routes.factor import factor_bp
    from .routes.user import user_bp
    from .routes.tasks import tasks_bp

    # ── 基础路由 ──
    from .routes.dashboard import dashboard_bp
    from .routes.account import account_bp
    from .routes.api import api_bp

    # ── 注册 (顺序无关，URL前缀不冲突) ──
    app.register_blueprint(dashboard_bp)          # /
    app.register_blueprint(account_bp)            # /account/<id>
    app.register_blueprint(api_bp, url_prefix='/api')  # /api/accounts/...
    app.register_blueprint(tasks_bp)              # /tasks + /tasks/api/...

    app.register_blueprint(market_bp)             # /market + /api/market/* + 旧 /live + /api/live/*
    app.register_blueprint(research_bp)           # /research + /api/research/*
    app.register_blueprint(signals_bp)            # /signals + /api/signals/* + 旧 /api/live/*
    app.register_blueprint(capital_bp)            # /capital + /api/capital/* + 旧 /api/live/*
    app.register_blueprint(fundamentals_bp)       # /fundamentals + /api/fundamentals/* + 旧 /api/live/*
    app.register_blueprint(announcements_bp)      # /announcements + /api/announcements/* + 旧 /api/live/*
    app.register_blueprint(factor_bp)             # /factors + /api/factors
    app.register_blueprint(user_bp)               # /user + /api/user/*

    return app

"""路由包 — 公共工具和 Blueprint 注册"""
from datetime import datetime
from flask import jsonify


def ok(data, **extra):
    """统一成功响应"""
    return jsonify({"data": data, "time": datetime.now().strftime("%H:%M:%S"), **extra})


def err(msg):
    """统一错误响应"""
    return jsonify({"data": None, "error": msg, "time": datetime.now().strftime("%H:%M:%S")})

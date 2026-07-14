"""
================================================================================
core —— 共享基础设施（a-stock-data V3.4.0）
================================================================================
来源: D:\\dev\\a-stock-data-main\\SKILL.md — Prerequisites 章节

提供:
  1. tdx_client()            — mootdx TCP 客户端（多级 fallback 规避 0.11.x BESTIP bug）
  2. get_prefix(code)        — 6位代码 → sh/sz/bj 市场前缀
  3. em_get()                — 东财统一节流 HTTP 入口（防封IP）
  4. eastmoney_datacenter()  — 东财 datacenter 通用查询 wrapper
  5. _cninfo_orgid()         — 巨潮 orgId 动态查询（6198只股票缓存）
  6. EM_SESSION / EM_MIN_INTERVAL — 东财全局 Session + 限流间隔
================================================================================
"""
import socket
import time
import random
import json as _json

import requests
import pandas as pd

# ══════════════════════════════════════════════════════════════════════════════
# 全局常量
# ══════════════════════════════════════════════════════════════════════════════

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"

# ── 东财防封：全局节流 + 会话复用 ──
EM_SESSION = requests.Session()
EM_SESSION.headers.update({"User-Agent": UA})
try:
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    _em_adapter = HTTPAdapter(max_retries=Retry(
        total=3, connect=3, backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"]))
    EM_SESSION.mount("https://", _em_adapter)
    EM_SESSION.mount("http://", _em_adapter)
except Exception:
    pass

EM_MIN_INTERVAL = 1.0          # 两次东财请求最小间隔(秒)；批量筛选建议调大到 1.5~2
_em_last_call = [0.0]          # 模块级上次请求时间戳

# ── mootdx 服务器列表（2026-06 实测可用）──
_TDX_SERVERS = [
    ('119.97.185.59', 7709), ('124.70.133.119', 7709), ('116.205.183.150', 7709),
    ('123.60.73.44', 7709),  ('116.205.163.254', 7709), ('121.36.225.169', 7709),
    ('123.60.70.228', 7709), ('124.71.9.153', 7709),    ('110.41.147.114', 7709),
    ('124.71.187.122', 7709),
]

# ── 巨潮 orgId 映射缓存 ──
_cninfo_orgid_cache = None


# ══════════════════════════════════════════════════════════════════════════════
# mootdx 客户端
# ══════════════════════════════════════════════════════════════════════════════

def _probe(ip, port, timeout=2.0):
    """TCP 握手探测，判断服务器是否可达"""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False


def tdx_client(market='std'):
    """
    创建 mootdx 客户端，规避 0.11.x BESTIP.HQ 空串 bug。

    顺序兜底：
      1) 顺序探测 _TDX_SERVERS，用第一个 TCP 可达的显式 server；
      2) 全部不可达 → 回退 mootdx 自带 bestip 测速选优；
      3) 再不行 → 回退裸 factory（老用户 config 已有可用 BESTIP 时成立）；
      4) 仍失败 → 抛 RuntimeError，明确报错而非死等。
    """
    from mootdx.quotes import Quotes

    for ip, port in _TDX_SERVERS:
        if _probe(ip, port):
            return Quotes.factory(market=market, server=(ip, port))
    try:
        return Quotes.factory(market=market, bestip=True)
    except Exception:
        pass
    try:
        return Quotes.factory(market=market)
    except Exception as e:
        raise RuntimeError(
            "所有 mootdx 服务器均不可达。海外网络通常全部超时（TCP 7709），"
            "请走国内代理或更新 _TDX_SERVERS 列表。原始错误：%s" % e
        )


# ══════════════════════════════════════════════════════════════════════════════
# 市场前缀 & Ticker 归一化
# ══════════════════════════════════════════════════════════════════════════════

def get_prefix(code: str) -> str:
    """6位代码 → 市场前缀 (sh/sz/bj)"""
    code = _normalize_code(code)
    if code.startswith(("6", "9")):
        return "sh"
    elif code.startswith("8"):
        return "bj"
    else:
        return "sz"


def _normalize_code(code: str) -> str:
    """归一化股票代码为纯6位数字。

    支持: SH688017 / sh688017 / 688017.SH / 688017.sh / SZ000001 / BJ832000
    """
    code = code.strip().upper()
    # 去掉 .SH / .SZ / .BJ 后缀
    for sfx in ('.SH', '.SZ', '.BJ'):
        if code.endswith(sfx):
            code = code[:-3]
            break
    # 去掉 SH/SZ/BJ 前缀
    for pfx in ('SH', 'SZ', 'BJ'):
        if code.startswith(pfx) and len(code) == 8:
            code = code[2:]
            break
    return code


# ══════════════════════════════════════════════════════════════════════════════
# 东财防封：统一节流 HTTP 入口
# ══════════════════════════════════════════════════════════════════════════════

def em_get(url: str, params: dict | None = None, headers: dict | None = None,
           timeout: int = 15, **kwargs):
    """东财统一请求入口：自动节流 + 复用 session + 默认 UA。

    所有 eastmoney.com 接口都应通过它请求，避免高频被封 IP。
    """
    wait = EM_MIN_INTERVAL - (time.time() - _em_last_call[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.5))
    try:
        return EM_SESSION.get(url, params=params, headers=headers, timeout=timeout, **kwargs)
    finally:
        _em_last_call[0] = time.time()


def eastmoney_datacenter(report_name: str, columns: str = "ALL",
                          filter_str: str = "", page_size: int = 50,
                          sort_columns: str = "", sort_types: str = "-1") -> list[dict]:
    """东财数据中心统一查询 — 龙虎榜/解禁/融资融券/大宗交易/股东户数/分红 共用（已内置限流）"""
    params = {
        "reportName": report_name, "columns": columns,
        "filter": filter_str, "pageNumber": "1", "pageSize": str(page_size),
        "sortColumns": sort_columns, "sortTypes": sort_types,
        "source": "WEB", "client": "WEB",
    }
    r = em_get(DATACENTER_URL, params=params, timeout=15)
    d = r.json()
    if d.get("result") and d["result"].get("data"):
        return d["result"]["data"]
    return []


def set_em_interval(seconds: float):
    """调整东财请求间隔（批量筛选时调大到 1.5~2 秒可进一步降低封禁风险）"""
    global EM_MIN_INTERVAL
    EM_MIN_INTERVAL = seconds


# ══════════════════════════════════════════════════════════════════════════════
# 巨潮 orgId 查询
# ══════════════════════════════════════════════════════════════════════════════

def _cninfo_orgid():
    """动态查询巨潮 orgId 映射表（6198只股票，模块级缓存）。

    返回: dict[str, str] — {6位代码: orgId}
    """
    global _cninfo_orgid_cache
    if _cninfo_orgid_cache is not None:
        return _cninfo_orgid_cache

    url = "https://www.cninfo.com.cn/new/index/getStockMeta"
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
        data = r.json()
        org_map = {}
        for item in data.get("stockList", []):
            code = item.get("stockCode", "")
            org_id = item.get("orgId", "")
            if code and org_id:
                org_map[code] = org_id
        _cninfo_orgid_cache = org_map
        return org_map
    except Exception:
        _cninfo_orgid_cache = {}
        return {}

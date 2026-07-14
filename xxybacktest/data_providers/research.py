"""
================================================================================
research —— Layer 2: 研报层（a-stock-data V3.4.0）
================================================================================
来源: D:\\dev\\a-stock-data-main\\SKILL.md §§2.1-2.3

东财研报 + 同花顺一致预期EPS + iwencai语义搜索
================================================================================
"""
import os
import re
import json
import secrets
from pathlib import Path
from io import StringIO
import requests
import pandas as pd

from .core import em_get, UA

# ══════════════════════════════════════════════════════════════════════════════
# 2.1 东财研报
# ══════════════════════════════════════════════════════════════════════════════

REPORT_API = "https://reportapi.eastmoney.com/report/list"
PDF_TPL = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"


def eastmoney_reports(code: str, max_pages: int = 5) -> list[dict]:
    """拉取指定股票的研报列表"""
    all_records = []
    for page in range(1, max_pages + 1):
        params = {
            "industryCode": "*", "pageSize": "100", "industry": "*",
            "rating": "*", "ratingChange": "*",
            "beginTime": "2000-01-01", "endTime": "2030-01-01",
            "pageNo": str(page), "fields": "", "qType": "0",
            "orgCode": "", "code": code, "rcode": "",
            "p": str(page), "pageNum": str(page), "pageNumber": str(page),
        }
        r = em_get(REPORT_API, params=params,
                   headers={"Referer": "https://data.eastmoney.com/"}, timeout=30)
        d = r.json()
        rows = d.get("data") or []
        if not rows:
            break
        all_records.extend(rows)
        if page >= (d.get("TotalPage", 1) or 1):
            break
    return all_records


def download_pdf(record: dict, target_dir: str = "./reports") -> str | None:
    """下载单份研报PDF，返回保存路径或None"""
    info_code = record.get("infoCode", "")
    if not info_code:
        return None
    date = (record.get("publishDate") or "")[:10]
    org = re.sub(r'[\\/:*?"<>|]', "_", record.get("orgSName") or "未知")[:40]
    title = re.sub(r'[\\/:*?"<>|]', "_", record.get("title", ""))[:80]
    fname = f"{date}_{org}_{title}.pdf"
    target = Path(target_dir) / fname
    if target.exists():
        return str(target)
    url = PDF_TPL.format(info_code=info_code)
    r = em_get(url, headers={"Referer": "https://data.eastmoney.com/"}, timeout=60)
    if r.status_code == 200 and len(r.content) >= 1024:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(r.content)
        return str(target)
    return None


def eastmoney_industry_reports(industry_code: str = "*", max_pages: int = 5,
                               begin: str = "2024-01-01") -> list[dict]:
    """拉取行业研报列表（qType=1）。industry_code="*" = 全行业"""
    all_records = []
    for page in range(1, max_pages + 1):
        params = {
            "industryCode": industry_code, "pageSize": "100", "industry": "*",
            "rating": "*", "ratingChange": "*",
            "beginTime": begin, "endTime": "2030-01-01",
            "pageNo": str(page), "fields": "", "qType": "1",
        }
        r = em_get(REPORT_API, params=params,
                   headers={"Referer": "https://data.eastmoney.com/"}, timeout=30)
        d = r.json()
        rows = d.get("data") or []
        if not rows:
            break
        all_records.extend(rows)
        if page >= (d.get("TotalPage", 1) or 1):
            break
    return all_records


# ══════════════════════════════════════════════════════════════════════════════
# 2.2 同花顺一致预期EPS
# ══════════════════════════════════════════════════════════════════════════════

def ths_eps_forecast(code: str) -> pd.DataFrame:
    """
    同花顺机构一致预期EPS。
    返回 DataFrame: 年度, 预测机构数, 最小值, 均值, 最大值
    """
    url = f"https://basic.10jqka.com.cn/new/{code}/worth.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://basic.10jqka.com.cn/",
    }
    r = requests.get(url, headers=headers, timeout=15)
    r.encoding = "gbk"
    dfs = pd.read_html(StringIO(r.text))
    for df in dfs:
        cols = [str(c) for c in df.columns]
        if any("每股收益" in c or "均值" in c for c in cols):
            return df
    return dfs[0] if dfs else pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
# 2.3 iwencai 语义搜索（需 API Key）
# ══════════════════════════════════════════════════════════════════════════════

IWENCAI_BASE = os.environ.get("IWENCAI_BASE_URL", "https://openapi.iwencai.com")
IWENCAI_KEY = os.environ.get("IWENCAI_API_KEY", "")


def _claw_headers(call_type: str = "normal") -> dict:
    return {
        "X-Claw-Call-Type": call_type,
        "X-Claw-Skill-Id": "report-search",
        "X-Claw-Skill-Version": "2.0.0",
        "X-Claw-Plugin-Id": "none",
        "X-Claw-Plugin-Version": "none",
        "X-Claw-Trace-Id": secrets.token_hex(32),
    }


def iwencai_search(query: str, channel: str = "report", size: int = 50) -> list[dict]:
    """iwencai 语义搜索（需 IWENCAI_API_KEY 环境变量）。channel: report/announcement/news"""
    headers = {
        "Authorization": f"Bearer {IWENCAI_KEY}",
        "Content-Type": "application/json",
        **_claw_headers(),
    }
    payload = {"channels": [channel], "app_id": "AIME_SKILL", "query": query, "size": size}
    r = requests.post(f"{IWENCAI_BASE}/v1/comprehensive/search",
                      json=payload, headers=headers, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"iwencai HTTP {r.status_code}: {r.text[:200]}")
    data = r.json()
    if data.get("status_code", 0) != 0:
        raise RuntimeError(f"iwencai error: {data.get('status_msg', '')}")
    return data.get("data") or []


def iwencai_query(query: str, page: int = 1, limit: int = 50) -> list[dict]:
    """iwencai NL数据查询（结构化字段）"""
    headers = {
        "Authorization": f"Bearer {IWENCAI_KEY}",
        "Content-Type": "application/json",
        **_claw_headers(),
    }
    payload = {"query": query, "page": str(page), "limit": str(limit),
               "is_cache": "1", "expand_index": "true"}
    r = requests.post(f"{IWENCAI_BASE}/v1/query2data",
                      json=payload, headers=headers, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"iwencai HTTP {r.status_code}: {r.text[:200]}")
    data = r.json()
    if data.get("status_code", 0) != 0:
        raise RuntimeError(f"iwencai error: {data.get('status_msg', '')}")
    return data.get("datas") or []


def dedup_articles(articles: list[dict]) -> list[dict]:
    """同一uid仅保留score最高的段落"""
    best = {}
    for a in articles:
        uid = a.get("uid", "") or f"{a.get('title','')}|{a.get('publish_date','')}"
        score = float(a.get("score", 0))
        if uid not in best or score > float(best[uid].get("score", 0)):
            best[uid] = a
    return sorted(best.values(), key=lambda x: x.get("publish_date", ""), reverse=True)

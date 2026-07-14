"""
================================================================================
valuation —— 估值计算公式（a-stock-data V3.4.0）
================================================================================
来源: D:\\dev\\a-stock-data-main\\SKILL.md — 估值计算公式章节
================================================================================
"""
import math
import urllib.request
import pandas as pd


def forward_pe(price: float, eps_forecast: float) -> float:
    """前向PE = 当前股价 / 未来年度一致预期EPS"""
    if eps_forecast <= 0:
        return float("inf")
    return price / eps_forecast


def pe_digestion(current_pe: float, cagr: float, target_pe: float = 30) -> float:
    """
    当前PE消化到目标PE需要多少年。
    target_pe 固定30x（A股成长股合理估值锚点）。
    """
    if current_pe <= target_pe:
        return 0.0
    if cagr <= 0:
        return float("inf")
    return math.log(current_pe / target_pe) / math.log(1 + cagr)


def calc_peg(pe: float, cagr: float) -> float:
    """
    PEG = 前向PE / (CAGR * 100)
    PEG < 1   → 便宜
    PEG 1-1.5 → 合理
    PEG > 1.5 → 贵
    """
    if cagr <= 0:
        return float("inf")
    return pe / (cagr * 100)


def full_valuation(code: str) -> dict:
    """单票完整估值分析（腾讯行情 + 同花顺一致预期EPS）"""
    from .market import tencent_quote
    from .research import ths_eps_forecast

    q = tencent_quote([code]).get(code, {})
    price = q.get("price", 0)
    mcap = q.get("mcap_yi", 0)
    pe_ttm = q.get("pe_ttm", 0)
    pb = q.get("pb", 0)

    df = ths_eps_forecast(code)
    eps_cur = eps_next = None
    analyst_count = 0
    if not df.empty and len(df.columns) >= 3:
        def _pick(row, name):
            for c in df.columns:
                if name in str(c):
                    return row.get(c)
            return None
        try:
            r0 = df.iloc[0]
            v = _pick(r0, "均值");          eps_cur = float(v) if pd.notna(v) else None
            cnt = _pick(r0, "预测机构数");  analyst_count = int(cnt) if pd.notna(cnt) else 0
            if len(df) >= 2:
                vn = _pick(df.iloc[1], "均值"); eps_next = float(vn) if pd.notna(vn) else None
        except (ValueError, TypeError):
            pass

    pe_fwd = price / eps_cur if eps_cur else float("inf")
    cagr = (eps_next / eps_cur - 1) if (eps_cur and eps_next) else 0
    peg = pe_fwd / (cagr * 100) if cagr > 0 else float("inf")
    digest = (
        math.log(pe_fwd / 30) / math.log(1 + cagr)
        if pe_fwd > 30 and cagr > 0 else 0
    )

    return {
        "name": q.get("name", ""),
        "price": price,
        "mcap_yi": mcap,
        "pe_ttm": pe_ttm,
        "pb": pb,
        "eps_cur": eps_cur,
        "eps_next": eps_next,
        "pe_fwd": round(pe_fwd, 1) if eps_cur else None,
        "cagr_pct": round(cagr * 100, 0) if cagr else None,
        "peg": round(peg, 2) if peg != float("inf") else None,
        "digest_years": round(digest, 1),
        "analyst_count": analyst_count,
    }

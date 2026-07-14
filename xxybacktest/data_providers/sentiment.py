"""
================================================================================
sentiment —— Layer 10: 舆情互动层（a-stock-data V3.4.0）
================================================================================
来源: D:\\dev\\a-stock-data-main\\SKILL.md §§10.1-10.4

互动易问答 + 同花顺热榜 + 东财人气榜 + 概念命中
================================================================================
"""
from datetime import datetime
import requests

from .core import UA

EM_HOT_BODY = {"appId": "appId01", "globalId": "786e4c21-70dc-435a-93bb-38"}


# ══════════════════════════════════════════════════════════════════════════════
# 10.1 互动易问答
# ══════════════════════════════════════════════════════════════════════════════

def cninfo_irm(code: str, page_size: int = 30, page_num: int = 1) -> list[dict]:
    """互动易问答（深沪统一走巨潮）"""
    try:
        r1 = requests.post("https://irm.cninfo.com.cn/newircs/index/queryKeyboardInfo",
            data={"keyWord": code}, headers={"User-Agent": UA}, timeout=10)
        d1 = r1.json().get("data") or []
        if not d1:
            return []
        org_id = d1[0].get("secid")
        params = {"_t": 1, "stockcode": code, "orgId": org_id, "pageSize": page_size,
                  "pageNum": page_num, "keyWord": "", "startDay": "", "endDay": ""}
        r2 = requests.post("https://irm.cninfo.com.cn/newircs/company/question",
            params=params, headers={"User-Agent": UA}, timeout=10)
        rows = r2.json().get("rows") or []
    except Exception as e:
        print(f"[WARN] 互动易请求失败: {e}")
        return []
    out = []
    for it in rows:
        pd_ts = it.get("pubDate")
        out.append({"code": it.get("stockCode"), "company": it.get("companyShortName"),
            "question": it.get("mainContent"), "answer": it.get("attachedContent"),
            "answerer": it.get("attachedAuthor"),
            "ask_time": datetime.fromtimestamp(pd_ts / 1000).strftime("%Y-%m-%d %H:%M") if pd_ts else ""})
    return out


# ══════════════════════════════════════════════════════════════════════════════
# 10.2 同花顺热榜
# ══════════════════════════════════════════════════════════════════════════════

def ths_hot_list(period: str = "hour") -> list[dict]:
    """同花顺热榜。period: hour/day"""
    try:
        r = requests.get("https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/stock",
            params={"stock_type": "a", "type": period, "list_type": "normal"},
            headers={"User-Agent": UA}, timeout=10)
        lst = (r.json().get("data") or {}).get("stock_list") or []
    except Exception as e:
        print(f"[WARN] 同花顺热榜失败: {e}")
        return []
    out = []
    for it in lst:
        tag = it.get("tag") or {}
        out.append({"rank": it.get("order"), "code": it.get("code"), "name": it.get("name"),
            "heat": it.get("rate"), "pct": it.get("rise_and_fall"), "rank_chg": it.get("hot_rank_chg"),
            "concepts": tag.get("concept_tag") or [], "tag": tag.get("popularity_tag", "")})
    return out


# ══════════════════════════════════════════════════════════════════════════════
# 10.3 东财人气榜 + 概念命中
# ══════════════════════════════════════════════════════════════════════════════

def em_hot_rank(top: int = 50) -> list[dict]:
    """东财人气榜（排名 + 排名变化 + 名称/价格）"""
    try:
        r = requests.post("https://emappdata.eastmoney.com/stockrank/getAllCurrentList",
            json={**EM_HOT_BODY, "marketType": "", "pageNo": 1, "pageSize": top},
            headers={"User-Agent": UA}, timeout=10)
        data = r.json().get("data") or []
        if not data:
            return []
        secids = [("0." if it["sc"].startswith("SZ") else "1.") + it["sc"][2:] for it in data]
        u = requests.get("https://push2.eastmoney.com/api/qt/ulist.np/get",
            params={"ut": "f057cbcbce2a86e2866ab8877db1d059", "fltt": 2, "invt": 2,
                    "fields": "f14,f3,f12,f2", "secids": ",".join(secids)},
            headers={"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"}, timeout=10)
        diff = (u.json().get("data") or {}).get("diff") or []
        if isinstance(diff, dict):
            diff = list(diff.values())
        nm = {x["f12"]: (x.get("f14"), x.get("f2"), x.get("f3")) for x in diff}
    except Exception as e:
        print(f"[WARN] 东财人气榜失败: {e}")
        return []
    out = []
    for it in data:
        code = it["sc"][2:]
        name, price, pct = nm.get(code, ("", None, None))
        out.append({"rank": it["rk"], "code": code, "name": name,
            "price": price, "pct": pct, "rank_chg": it.get("hisRc")})
    return out


def em_hot_concept(code: str) -> list[dict]:
    """东财个股热门概念命中"""
    try:
        prefix = "SH" if code.startswith("6") else "SZ"
        r = requests.post("https://emappdata.eastmoney.com/stockrank/getHotStockRankList",
            json={**EM_HOT_BODY, "srcSecurityCode": prefix + code},
            headers={"User-Agent": UA}, timeout=10)
        data = r.json().get("data") or []
    except Exception as e:
        print(f"[WARN] 东财个股概念失败: {e}")
        return []
    return [{"concept": x.get("conceptName"), "bk": x.get("conceptId"),
             "hit": x.get("hitCount")} for x in data]

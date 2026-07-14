"""
================================================================================
test_data_providers.py —— smoke test 各数据端点在当前网络下能否正常返回
================================================================================
用法: python scripts/test_data_providers.py
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, "d:/xxybacktest-master")

from xxybacktest.data_providers import (
    tencent_quote,
    baidu_kline_with_ma,
    cls_telegraph,
    eastmoney_global_news,
    ths_hot_reason,
    industry_comparison,
    eastmoney_concept_blocks,
    eastmoney_stock_info,
    daily_dragon_tiger,
    lockup_expiry,
    ths_hot_list,
    em_hot_rank,
    limit_up_sentiment,
)

PASS, FAIL, SKIP = 0, 0, 0


def test(name, fn, *args, **kwargs):
    global PASS, FAIL, SKIP
    try:
        result = fn(*args, **kwargs)
        if result is None:
            print(f"  ⚠ SKIP {name}: 返回 None")
            SKIP += 1
        elif isinstance(result, (list, dict)) and len(result) == 0:
            print(f"  ⚠ SKIP {name}: 返回空（非交易日或网络问题）")
            SKIP += 1
        else:
            if isinstance(result, list):
                print(f"  ✓ {name}: {len(result)} 条")
            elif isinstance(result, dict):
                ks = list(result.keys())[:3]
                print(f"  ✓ {name}: keys={ks}")
            else:
                print(f"  ✓ {name}: ok")
            PASS += 1
    except Exception as e:
        msg = str(e)[:80]
        print(f"  ✗ FAIL {name}: {msg}")
        FAIL += 1


print("=" * 60)
print("data_providers Smoke Test")
print("=" * 60)

# Layer 1: 行情层
print("\n[Layer 1] 行情层")
test("腾讯实时行情(000001.SZ)", tencent_quote, ["000001"])
test("百度K线(600519)", baidu_kline_with_ma, "600519")

# Layer 3: 信号层
print("\n[Layer 3] 信号层")
test("同花顺热点", ths_hot_reason)
test("行业板块排名", industry_comparison, 5)
test("概念板块(600519)", eastmoney_concept_blocks, "600519")
test("全市场龙虎榜(2026-07-10)", daily_dragon_tiger, "2026-07-10")
test("限售解禁(600519)", lockup_expiry, "600519", "2026-07-10")
test("东财个股信息(000001)", eastmoney_stock_info, "000001")

# Layer 5: 新闻层
print("\n[Layer 5] 新闻层")
test("财联社快讯", cls_telegraph, 10)
test("东财全球资讯", eastmoney_global_news, 10)

# Layer 8: 打板层
print("\n[Layer 8] 打板层")
test("打板情绪(20260710)", limit_up_sentiment, "20260710")

# Layer 10: 舆情层
print("\n[Layer 10] 舆情层")
test("同花顺热榜", ths_hot_list, "day")
test("东财人气榜", em_hot_rank, 10)

# 估值
print("\n[估值]")
try:
    from xxybacktest.data_providers import full_valuation
    test("完整估值(000001)", full_valuation, "000001")
except Exception as e:
    test("完整估值错误", lambda: (_ for _ in ()).throw(Exception(str(e))))

# ── 结果 ──
print("\n" + "=" * 60)
total = PASS + FAIL + SKIP
print(f"总计 {total}:  ✓ {PASS} 通过  ✗ {FAIL} 失败  ⚠ {SKIP} 跳过")
print("=" * 60)

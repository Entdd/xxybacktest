"""
因子教程 — 从单因子验证到多因子合成策略
========================================

核心概念:
    IC (信息系数): 因子值和未来收益的相关性。正数=因子有效，负数=反向有效。
                  通常 |IC| > 0.02 就算有用，> 0.05 算好因子。
    ICIR: IC的均值/标准差，越高说明因子越稳定。> 0.5 算合格。

工作流:
    1. 写因子 SQL（返回 date, instrument, value 三列）
    2. 用 analyze_factor() 看 IC 好不好
    3. 好因子留下来合成多因子策略
    4. 回测验证
"""

import pandas as pd


# ═══════════════════════════════════════════════════════════════════════════════
# 第一部分：因子 SQL 定义
# ═══════════════════════════════════════════════════════════════════════════════

# 因子1: 动量因子（过去20天收益率，越高越好）
MOMENTUM_20_SQL = """
SELECT
    date,
    instrument,
    (close - LAG(close, 20) OVER w) / NULLIF(LAG(close, 20) OVER w, 0) AS value
FROM daily_bar
WINDOW w AS (PARTITION BY instrument ORDER BY date)
"""

# 因子2: 短期反转（过去5天收益率，越低越好 → 均值回归）
REVERSAL_5_SQL = """
SELECT
    date,
    instrument,
    (close - LAG(close, 5) OVER w) / NULLIF(LAG(close, 5) OVER w, 0) AS value
FROM daily_bar
WINDOW w AS (PARTITION BY instrument ORDER BY date)
"""

# 因子3: 换手率因子（高换手可能意味着关注度高）
TURNOVER_SQL = """
SELECT
    date,
    instrument,
    turn AS value
FROM daily_bar
WHERE turn > 0
"""

# 因子4: 波动率因子（过去20天日收益率标准差，越高=风险越大）
VOLATILITY_SQL = """
SELECT
    date,
    instrument,
    STDDEV_SAMP((close - LAG(close, 1) OVER w) / NULLIF(LAG(close, 1) OVER w, 0))
        OVER (PARTITION BY instrument ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS value
FROM daily_bar
WINDOW w AS (PARTITION BY instrument ORDER BY date)
"""

# 因子5: 价量背离（价跌量缩 → 可能见底）
# 价格跌 but 成交量相对萎缩 → 卖压减弱
PRICE_VOLUME_SQL = """
SELECT
    date,
    instrument,
    (close - LAG(close, 10) OVER w) / NULLIF(LAG(close, 10) OVER w, 0) * -1
    * (volume / NULLIF(AVG(volume) OVER (PARTITION BY instrument ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW), 0) - 1) * -1
    AS value
FROM daily_bar
WINDOW w AS (PARTITION BY instrument ORDER BY date)
"""

# 因子6: 涨跌幅（当日涨跌幅本身，ADHD效应）
DAILY_CHANGE_SQL = """
SELECT
    date,
    instrument,
    change_ratio AS value
FROM daily_bar
WHERE change_ratio IS NOT NULL
"""


# ═══════════════════════════════════════════════════════════════════════════════
# 第二部分: 因子验证
# ═══════════════════════════════════════════════════════════════════════════════

FACTORS = {
    "动量20日":      {"sql": MOMENTUM_20_SQL,   "direction": "positive"},
    "反转5日":       {"sql": REVERSAL_5_SQL,     "direction": "negative"},
    "换手率":        {"sql": TURNOVER_SQL,       "direction": "unknown"},
    "波动率20日":    {"sql": VOLATILITY_SQL,      "direction": "negative"},
    "价量背离":      {"sql": PRICE_VOLUME_SQL,    "direction": "positive"},
    "当日涨跌幅":    {"sql": DAILY_CHANGE_SQL,    "direction": "positive"},
}


def validate_all_factors(data_path="./data", periods=(1, 5, 20)):
    """
    逐个验证所有因子，打印 IC 表格。

    参数:
        data_path: xxydb 数据路径
        periods: 未来收益周期

    返回:
        DataFrame: 各因子在各周期上的 IC 表现
    """
    from xxybacktest.factor import analyze_factor
    from xxydb import xxydb

    db = xxydb(path=data_path)
    results = []

    for name, config in FACTORS.items():
        print(f"\n--- 验证: {name} ---")
        try:
            res = analyze_factor(
                sql=config["sql"],
                db=db,
                name=name,
                periods=periods,
                n_groups=5,
                ic_method="rank",
            )
            ic_dict = res.to_dict()
            metrics = ic_dict.get("metrics", {})

            # 取 base_period 的 IC 指标
            bp = periods[0]
            ic_mean_key = f"IC_period{bp}_mean"
            icir_key = f"IC_period{bp}_ICIR"

            row = {
                "因子名称": name,
                f"IC_{bp}天_均值": metrics.get(ic_mean_key, 0),
                f"ICIR_{bp}天": metrics.get(icir_key, 0),
            }
            for p in periods:
                row[f"IC_{p}天_mean"] = metrics.get(f"IC_period{p}_mean", 0)

            results.append(row)
            print(f"  IC_{bp}d = {row[f'IC_{bp}天_均值']:.4f}, ICIR = {row[f'ICIR_{bp}天']:.3f}")

        except Exception as e:
            print(f"  失败: {e}")
            results.append({
                "因子名称": name,
                f"IC_{periods[0]}天_均值": 0,
                f"ICIR_{periods[0]}天": 0,
            })

    db.close()

    # 汇总
    df = pd.DataFrame(results)
    print(f"\n{'='*70}")
    print("因子验证汇总")
    print(f"{'='*70}")
    print(df.to_string(index=False))

    # 推荐
    good = df[abs(df.iloc[:, 1]) > 0.01] if len(df.columns) > 1 else pd.DataFrame()
    print(f"\n推荐使用 (|IC| > 0.01): {len(good)} 个因子")
    if len(good) > 0:
        for _, r in good.iterrows():
            print(f"  ✓ {r['因子名称']}")

    return df


if __name__ == "__main__":
    validate_all_factors()

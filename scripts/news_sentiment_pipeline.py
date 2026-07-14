"""
================================================================================
news_sentiment_pipeline.py —— 新闻情绪因子全链路 Demo
================================================================================
无 LLM 版本: 用关键词规则做情绪评分 → 生成 date/instrument/value → 跑因子分析。
LLM 版本只需把 _score_by_keyword 替换为 NewsSentimentAgent.analyze()。
================================================================================
"""
import os
import sys
import re
import pandas as pd
import numpy as np
from datetime import datetime

# ====== 配置 ======
NEWS_PATH = "d:/News_Agent-main/news.csv"
DATA_PATH = "d:/xxybacktest-master/data"
OUTPUT_DIR = os.path.join(DATA_PATH, "news_sentiment_cache")

# ====== 情绪词典 ======
BULLISH_PATTERNS = [
    (r'(涨停|拉升|走高|走强|冲高|大涨|暴涨|涨超?\d|领涨|异动拉升)', 1),
    (r'(扭亏|预增|预盈|超预期|利好|签约|中标|合作|突破)', 1),
    (r'(净买入|融资净买入|机构调研|回购|增持)', 1),
    (r'(量产|交付|订单|开工|投产|获批|上市)', 1),
    (r'(新能源|光伏|锂电|芯片|AI|人工智能|机器人)', 0.5),  # 赛道加分
]

BEARISH_PATTERNS = [
    (r'(跌停|下挫|走弱|跳水|大跌|暴跌|跌超?\d|领跌|震荡下挫)', -1),
    (r'(预亏|预降|亏损|处罚|减持|清盘|终止|退市|警告)', -1),
    (r'(净卖出|融资净卖出|流拍|破产|违约|暴雷)', -1),
    (r'(停产|召回|诉讼|调查|处罚|限售|解禁)', -1),
    (r'(ST|\*ST|退市风险)', -1),  # 风险警示
]

NEUTRAL_PATTERNS = [
    (r'(震荡|波动|盘整|横盘|窄幅|整理)', 0),
    (r'(回应|辟谣|澄清|否认|不属实|尚不确定)', 0),
    (r'(人事|任命|辞职|换届|调整)', 0),
]


def score_news(title: str) -> float:
    """
    基于关键词规则的情绪评分，返回 -1 到 1 之间的连续值。

    规则:
    - 先匹配强信号（涨跌停、预增预亏等），权重 ±1
    - 再匹配弱信号（赛道加分、行业趋势），权重 ±0.5
    - 中性信号覆盖前面匹配的结果
    - 混合信号取加权平均
    """
    scores = []
    weights = []

    # 强看涨信号
    for pattern, score in BULLISH_PATTERNS:
        if re.search(pattern, title):
            scores.append(score)
            weights.append(abs(score))  # 权重 = 信号强度

    # 强看跌信号
    for pattern, score in BEARISH_PATTERNS:
        if re.search(pattern, title):
            scores.append(score)
            weights.append(abs(score))

    # 中性信号
    for pattern, score in NEUTRAL_PATTERNS:
        if re.search(pattern, title):
            scores.append(score)
            weights.append(0.3)

    if not scores:
        return 0.0

    # 加权平均
    total_weight = sum(weights)
    weighted_score = sum(s * w for s, w in zip(scores, weights))
    return round(weighted_score / total_weight, 2)


def process_news_to_factor(news_path: str) -> pd.DataFrame:
    """
    主流程: 读取新闻 CSV → 按标的展开 → 评分 → 产出因子格式 DataFrame
    """
    print(f"[1/4] 读取新闻数据: {news_path}")
    news = pd.read_csv(news_path)
    print(f"      共 {len(news)} 条新闻")

    # 拆分多标的行
    print("[2/4] 拆分多标的关联...")
    rows = []
    skipped = 0
    for _, row in news.iterrows():
        codes_str = str(row.get('related_instruments', ''))
        if not codes_str or codes_str == 'nan':
            skipped += 1
            continue

        codes = [c.strip() for c in codes_str.split(',') if c.strip()]

        # 只保留 A 股（有 daily_bar 数据）
        a_codes = [c for c in codes if c.endswith('.SZ') or c.endswith('.SH')]

        for code in a_codes:
            rows.append({
                'date': str(row['publish_time'])[:10],
                'instrument': code,
                'title': str(row['title']),
                'source': str(row.get('source', '')),
            })

    df = pd.DataFrame(rows)
    print(f"      展开为 {len(df)} 行 ({skipped} 行无标的), {df['instrument'].nunique()} 个 A 股标的")

    # 评分
    print("[3/4] 关键词情绪评分...")
    df['value'] = df['title'].apply(score_news)

    # 按日期+标的聚合（同一天同一标的多条新闻取平均）
    grouped = df.groupby(['date', 'instrument'])['value'].mean().reset_index()
    grouped['value'] = grouped['value'].round(3)

    print(f"      聚合后 {len(grouped)} 条因子记录")
    print(f"      情绪分布: 利好 {(grouped['value'] > 0).sum()} ({(grouped['value'] > 0).sum()/len(grouped)*100:.0f}%), "
          f"利空 {(grouped['value'] < 0).sum()} ({(grouped['value'] < 0).sum()/len(grouped)*100:.0f}%), "
          f"中性 {(grouped['value'] == 0).sum()} ({(grouped['value'] == 0).sum()/len(grouped)*100:.0f}%)")

    return grouped


def save_for_analysis(df: pd.DataFrame, output_dir: str):
    """保存为 Parquet 供 factor 引擎读取。"""
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "sentiment_factor.parquet")
    df.to_parquet(out_path, index=False)
    print(f"[4/4] 已保存: {out_path}")
    return out_path


def run_factor_analysis(parquet_path: str, data_path: str, factor_df: pd.DataFrame):
    """用 xxybacktest factor 引擎分析情绪因子。"""
    from xxydb import xxydb

    # 构建 SQL：直接从 parquet 读
    # DuckDB 可以直接查询 parquet 文件
    sql = (
        f"SELECT date::DATE AS date, instrument, value "
        f"FROM read_parquet('{parquet_path.replace(chr(92), '/')}')"
    )

    print(f"\n{'='*60}")
    print(f" 新闻情绪因子分析")
    print(f"{'='*60}")

    # 先检查数据覆盖
    db = xxydb(path=data_path)
    try:
        # 有多少标的在 daily_bar 中有数据
        instruments_str = "', '".join(factor_df['instrument'].unique()[:1000])
        check_sql = f"""
        SELECT COUNT(DISTINCT instrument) AS n_avail,
               MIN(date) AS min_date, MAX(date) AS max_date
        FROM daily_bar
        WHERE date >= '2023-07-01' AND date <= '2023-08-05'
          AND instrument IN ('{instruments_str}')
        """
        avail = db.query(check_sql).df()
        print(f"\n行情覆盖: {avail['n_avail'].iloc[0]} 个标的有 daily_bar 数据")
        print(f"日期范围: {avail['min_date'].iloc[0]} ~ {avail['max_date'].iloc[0]}")
    finally:
        db.close()

    # 跑因子分析
    from xxybacktest.factor import analyze_factor

    try:
        res = analyze_factor(
            sql=sql,
            data_path=data_path,
            name="新闻情绪因子 (关键词版)",
            periods=(1, 5, 10),
            n_groups=5,
        )
        return res
    except Exception as e:
        print(f"\n因子分析失败: {e}")
        print("可能原因: 1) 标的在 daily_bar 中不存在  2) 日期格式不匹配")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # Step 1: 处理新闻
    factor_df = process_news_to_factor(NEWS_PATH)
    parquet_path = save_for_analysis(factor_df, OUTPUT_DIR)

    # Step 2: 因子分析
    result = run_factor_analysis(parquet_path, DATA_PATH, factor_df)

    if result is not None:
        print("\n" + "="*60)
        result.summary()
        print("="*60)

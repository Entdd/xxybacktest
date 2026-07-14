"""
================================================================================
run_sentiment_analysis.py —— 新闻情绪因子完整分析
================================================================================
前提: 已运行 download_data.py 获取完整 daily_bar 数据。
用法: python scripts/run_sentiment_analysis.py
================================================================================
"""
import os
import sys
import pandas as pd
import numpy as np

DATA_PATH = "d:/xxybacktest-master/data"
PARQUET_PATH = os.path.join(DATA_PATH, "news_sentiment_cache", "sentiment_factor.parquet")

def main():
    # 1. 检查数据就绪
    if not os.path.exists(PARQUET_PATH):
        print("[错误] 情绪因子文件不存在, 请先运行 news_sentiment_pipeline.py")
        return

    from xxydb import xxydb
    db = xxydb(path=DATA_PATH)
    try:
        n_stocks = db.query("SELECT COUNT(DISTINCT instrument) FROM daily_bar").df().iloc[0, 0]
        print(f"[信息] daily_bar 共 {n_stocks} 只股票")

        if n_stocks < 50:
            print("[错误] 股票数量太少 ({n_stocks}), 请先运行 download_data.py 获取完整数据")
            return
    finally:
        db.close()

    # 2. 因子分析
    print(f"\n{'='*60}")
    print(f"  新闻情绪因子分析")
    print(f"{'='*60}")

    from xxybacktest.factor import analyze_factor

    # 构建 SQL
    parquet_path_fwd = PARQUET_PATH.replace('\\', '/')
    sql = f"SELECT date::DATE AS date, instrument, value FROM read_parquet('{parquet_path_fwd}')"

    res = analyze_factor(
        sql=sql,
        data_path=DATA_PATH,
        name="新闻情绪因子 (关键词版)",
        periods=(1, 5, 10),
        n_groups=5,
    )

    # 3. 输出
    print()
    res.summary()

    # 4. 保存图
    try:
        res.plot()
        import matplotlib.pyplot as plt
        fig_dir = os.path.join(DATA_PATH, "news_sentiment_cache")
        os.makedirs(fig_dir, exist_ok=True)
        plt.savefig(os.path.join(fig_dir, "sentiment_factor_analysis.png"), dpi=150, bbox_inches='tight')
        print(f"\n[OK] 分析图已保存至: {fig_dir}/sentiment_factor_analysis.png")
    except Exception as e:
        print(f"[提示] 无法保存图片: {e}")

    # 5. 与 LLM 版做对比 (如果有)
    print(f"\n{'='*60}")
    print(f"  Next: 将关键词评分替换为 LLM 评分")
    print(f"  from xxybacktest.agents import NewsSentimentAgent")
    print(f"  agent = NewsSentimentAgent(deepseek_api_key='sk-xxx')")
    print(f"  df = agent.analyze(pd.read_csv('news.csv'))")
    print(f"  # -> 提交为正式因子, 纳入每日监控")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

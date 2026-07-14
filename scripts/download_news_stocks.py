"""
================================================================================
download_news_stocks.py —— 下载新闻数据中出现的 A 股的日线数据
================================================================================
轻量版: 只下载 sentiment_factor.parquet 中出现过的股票
"""
import os, sys, time, pandas as pd, numpy as np
import baostock as bs

DATA_PATH = "d:/xxybacktest-master/data"
START = "2023-07-01"
END = "2023-09-30"
DELAY = 0.3
BATCH_SIZE = 50  # 每50只重新连接一次

def main():
    bs.login()

    # 1. 获取目标股票
    sf_path = os.path.join(DATA_PATH, "news_sentiment_cache", "sentiment_factor.parquet")
    if not os.path.exists(sf_path):
        print("sentiment_factor.parquet not found, run news_sentiment_pipeline.py first")
        bs.logout()
        return

    sf = pd.read_parquet(sf_path)
    codes = sorted(sf['instrument'].unique())
    print(f"Target: {len(codes)} stocks from news sentiment data")

    # 2. 分批下载
    all_rows = []
    success, failed = 0, 0
    total = len(codes)

    for i, code in enumerate(codes):
        # 每 BATCH_SIZE 个重新连接
        if i > 0 and i % BATCH_SIZE == 0:
            bs.logout()
            time.sleep(1)
            bs.login()
            print(f"  [{i}/{total}] reconnected, {success} ok, {failed} fail, {len(all_rows)} rows")

        try:
            bs_code = f"sh.{code[:6]}" if code.endswith('.SH') else f"sz.{code[:6]}"
            rs = bs.query_history_k_data_plus(
                bs_code,
                'date,open,high,low,close,preclose,volume,amount,turn,tradestatus',
                start_date=START, end_date=END, frequency='d', adjustflag='2'
            )

            if rs is None or rs.error_code != '0':
                failed += 1
                continue

            rows = []
            while rs.next():
                rows.append(rs.get_row_data())

            for r in rows:
                if r[9] == '1':  # tradestatus=1 (交易)
                    all_rows.append({
                        'date': r[0], 'instrument': code,
                        'open': float(r[1]), 'high': float(r[2]), 'low': float(r[3]),
                        'close': float(r[4]), 'pre_close': float(r[5]),
                        'volume': int(float(r[6])), 'amount': float(r[7]), 'turn': float(r[8]),
                        'change_ratio': 0.0, 'adjust_factor': 1.0,
                        'name': '', 'deal_number': 0,
                        'upper_limit': 0.0, 'lower_limit': 0.0
                    })
            success += 1

        except Exception as e:
            failed += 1
            if failed <= 3:
                print(f"  Error {code}: {e}")

        time.sleep(DELAY)

    bs.logout()

    # 3. 构建 DataFrame
    print(f"\nDownload done: {success} ok, {failed} fail, {len(all_rows)} rows")

    if not all_rows:
        print("No data downloaded!")
        return

    df = pd.DataFrame(all_rows)
    df['date'] = pd.to_datetime(df['date'])

    # 计算涨跌幅
    df['change_ratio'] = (df['close'] / df['pre_close'] - 1).fillna(0)
    df['upper_limit'] = (df['pre_close'] * 1.1).round(2)
    df['lower_limit'] = (df['pre_close'] * 0.9).round(2)

    print(f"Processed: {df['instrument'].nunique()} stocks, {len(df)} rows")
    print(f"Date range: {df['date'].min().date()} ~ {df['date'].max().date()}")

    # 4. 写入 parquet (合并到 daily_bar)
    for year, group in df.groupby(df['date'].dt.year):
        year_dir = os.path.join(DATA_PATH, "daily_bar", f"year={year}")
        os.makedirs(year_dir, exist_ok=True)

        # 合并已有数据
        fpath = os.path.join(year_dir, "data.parquet")
        if os.path.exists(fpath):
            existing = pd.read_parquet(fpath)
            # 去重: 删掉同 date+instrument 的旧行
            existing = existing[~existing.set_index(['date','instrument']).index.isin(
                group.set_index(['date','instrument']).index)]
            group = pd.concat([existing, group], ignore_index=True)

        cols = ['date','instrument','name','adjust_factor','pre_close','open','close',
                'high','low','volume','deal_number','amount','change_ratio','turn',
                'upper_limit','lower_limit']
        group = group[[c for c in cols if c in group.columns]]
        group.to_parquet(fpath, index=False)
        print(f"  Wrote year={year}: {len(group)} rows ({group['instrument'].nunique()} stocks)")

    print(f"\nDone! Data saved to {DATA_PATH}/daily_bar/")

if __name__ == "__main__":
    main()

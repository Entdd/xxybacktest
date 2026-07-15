"""
fast_download.py — baostock 前复权日线下载（快速版）

单进程批量下载，不设延迟，HTTP 往返作为自然间隔。
~5500 只 A 股，预计 10-15 分钟完成。

数据直接写入 xxydb Parquet，覆盖通达信不复权数据。

用法:
    python scripts/fast_download.py
"""

import os
import sys
import time
import pandas as pd
import baostock as bs

DATA_PATH = "d:/xxybacktest-master/data"
START_DATE = "2023-01-01"
END_DATE = "2026-07-15"

KEEP_COLS = [
    'date', 'instrument', 'name', 'adjust_factor', 'pre_close',
    'open', 'close', 'high', 'low', 'volume', 'deal_number',
    'amount', 'change_ratio', 'turn', 'upper_limit', 'lower_limit'
]


def get_stock_list():
    rs = bs.query_stock_basic()
    codes = []
    while True:
        row = rs.get_row_data()
        if row is None:
            break
        if len(row) >= 6 and row[4] == '1':
            code = row[0]
            if code.startswith('sh.'):
                codes.append(code.replace('sh.', '') + '.SH')
            elif code.startswith('sz.'):
                codes.append(code.replace('sz.', '') + '.SZ')
    return codes


def download_one(code):
    pure = code[:6]
    bs_code = f"sh.{pure}" if code.endswith('.SH') else f"sz.{pure}"

    try:
        rs = bs.query_history_k_data_plus(
            bs_code,
            'date,code_name,open,high,low,close,preclose,volume,amount,turn,tradestatus',
            start_date=START_DATE, end_date=END_DATE,
            frequency='d', adjustflag='2'
        )
        if rs is None or rs.error_code != '0':
            return None

        rows = []
        while rs.next():
            rows.append(rs.get_row_data())
        if not rows:
            return None

        df = pd.DataFrame(rows, columns=[
            'date', 'name', 'open', 'high', 'low', 'close',
            'preclose', 'volume', 'amount', 'turn', 'tradestatus'
        ])
        df = df[df['tradestatus'] == '1']
        if df.empty:
            return None

        df['date'] = pd.to_datetime(df['date'])
        for col in ['open', 'high', 'low', 'close', 'preclose', 'volume', 'amount', 'turn']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        df['instrument'] = code
        df['adjust_factor'] = 1.0
        df['change_ratio'] = (df['close'] / df['preclose'] - 1).fillna(0)
        df['deal_number'] = 0
        df['upper_limit'] = (df['preclose'] * 1.1).round(2)
        df['lower_limit'] = (df['preclose'] * 0.9).round(2)
        df = df.rename(columns={'preclose': 'pre_close'})
        return df[[c for c in KEEP_COLS if c in df.columns]]

    except Exception:
        return None


def main():
    # 强制实时输出（后台运行时防止缓冲）
    sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

    print("=" * 60, flush=True)
    print("  baostock 前复权日线下载", flush=True)
    print("=" * 60, flush=True)
    print(f"  日期: {START_DATE} ~ {END_DATE}", flush=True)
    print(flush=True)

    # 登录
    lg = bs.login()
    if lg.error_code != '0':
        print(f"登录失败: {lg.error_msg}")
        return

    # 从已有数据库获取股票列表（比 baostock query_stock_basic 快得多）
    print("[1/3] 从数据库获取股票列表...")
    from xxydb import xxydb
    db = xxydb(path=DATA_PATH)
    try:
        r = db.query("SELECT DISTINCT instrument FROM daily_bar ORDER BY instrument").df()
        codes = sorted(r["instrument"].tolist())
    except Exception:
        codes = get_stock_list()
    db.close()
    print(f"      全量 A 股: {len(codes)} 只")

    # 预读已有年数据
    year_data = {}
    for year in [2023, 2024, 2025, 2026]:
        path = os.path.join(DATA_PATH, "daily_bar", f"year={year}", "data.parquet")
        if os.path.exists(path):
            year_data[year] = pd.read_parquet(path)

    # 下载
    print(f"\n[2/3] 逐只下载 (无延迟)...")
    success, failed = 0, 0
    new_by_year = {y: [] for y in [2023, 2024, 2025, 2026]}
    start_time = time.time()

    for i, code in enumerate(codes):
        df = download_one(code)
        if df is not None and not df.empty:
            for year, group in df.groupby(df['date'].dt.year):
                if year in new_by_year:
                    new_by_year[year].append(group)
            success += 1
        else:
            failed += 1

        # 每 500 只报告进度
        if (i + 1) % 200 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (len(codes) - i - 1) / rate if rate > 0 else 0
            print(f"  进度: {i+1}/{len(codes)} 成功 {success} 失败 {failed} "
                  f"速度 {rate:.0f}只/秒 预计剩余 {eta:.0f}s", flush=True)

    bs.logout()

    # 写入
    print(f"\n[3/3] 合并写入...")
    for year, dfs in new_by_year.items():
        if not dfs:
            continue
        new_df = pd.concat(dfs, ignore_index=True)
        if year in year_data:
            combined = pd.concat([year_data[year], new_df], ignore_index=True)
            combined = combined.drop_duplicates(subset=["instrument", "date"], keep="last")
        else:
            combined = new_df

        year_dir = os.path.join(DATA_PATH, "daily_bar", f"year={year}")
        os.makedirs(year_dir, exist_ok=True)
        out_path = os.path.join(year_dir, "data.parquet")
        combined.to_parquet(out_path, index=False)
        print(f"  year={year}: {len(combined):,} 行 ({combined['instrument'].nunique():,} 只)")

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"  完成! 耗时 {elapsed/60:.1f} 分钟")
    print(f"  成功: {success}, 失败: {failed}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

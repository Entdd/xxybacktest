"""
download_tencent.py — 腾讯 K 线 API 前复权日线下载

腾讯 API: web.ifzq.gtimg.cn/appstock/app/fqkline/get
- 返回前复权(qfq)日线数据
- 多线程并行下载到内存，最后一次性写入 Parquet
- 覆盖 TDX 不复权数据

用法:
    python scripts/download_tencent.py
"""

import os
import sys
import time
import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

DATA_PATH = "d:/xxybacktest-master/data"
MAX_WORKERS = 20

KEEP_COLS = [
    'date', 'instrument', 'name', 'adjust_factor', 'pre_close',
    'open', 'close', 'high', 'low', 'volume', 'deal_number',
    'amount', 'change_ratio', 'turn', 'upper_limit', 'lower_limit'
]

_session = None

def _get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
            'Referer': 'https://gu.qq.com/',
        })
    return _session


def download_stock(code):
    """下载单只股票全部前复权日线，返回 DataFrame 或 None"""
    market = 'sz' if code.endswith('.SZ') else 'sh'
    symbol = f'{market}{code[:6]}'
    all_rows = []
    session = _get_session()
    base_url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'

    chunks = [('2023-01-01', '2024-06-30'), ('2024-07-01', '2026-07-16')]

    for start, end in chunks:
        param = f'{symbol},day,{start},{end},800,qfq'
        try:
            r = session.get(base_url, params={'param': param}, timeout=10)
            if r.status_code != 200:
                continue
            d = r.json()
            if d.get('code') != 0:
                continue
            klines = d.get('data', {}).get(symbol, {}).get('qfqday', [])
            for row in klines:
                try:
                    date_str, op, cl, hi, lo, vol = row
                    all_rows.append({
                        'date': date_str,
                        'open': float(op),
                        'close': float(cl),
                        'high': float(hi),
                        'low': float(lo),
                        'volume': float(vol),
                    })
                except (ValueError, IndexError):
                    continue
        except Exception:
            continue

    if not all_rows:
        return None

    df = pd.DataFrame(all_rows)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').drop_duplicates(subset=['date'], keep='last')
    df['instrument'] = code
    return df


def build_standard_df(df, code):
    """将原始数据转为标准 daily_bar 格式"""
    df = df.copy()
    df['name'] = ''
    df['adjust_factor'] = 1.0
    df['pre_close'] = df['close'].shift(1)
    df['change_ratio'] = (df['close'] / df['pre_close'] - 1).fillna(0)
    df['deal_number'] = 0
    df['amount'] = 0.0
    df['turn'] = 0.0
    df['upper_limit'] = (df['pre_close'] * 1.1).round(2)
    df['lower_limit'] = (df['pre_close'] * 0.9).round(2)
    return df[[c for c in KEEP_COLS if c in df.columns]]


def main():
    print("=" * 60)
    print("  腾讯 K 线 API — 前复权日线下载")
    print("=" * 60)
    print(f"  线程数: {MAX_WORKERS}")

    # 股票列表
    print("\n[1/3] 获取股票列表...")
    from xxydb import xxydb
    db = xxydb(path=DATA_PATH)
    try:
        r = db.query("SELECT DISTINCT instrument FROM daily_bar ORDER BY instrument").df()
        codes = sorted(r["instrument"].tolist())
    except Exception:
        codes = []
    db.close()

    codes = [c for c in codes if (
        (c.endswith('.SZ') and c[:1] in '0123') or
        (c.endswith('.SH') and c[:1] == '6')
    )]
    print(f"      可交易 A 股: {len(codes)} 只")

    # 并行下载
    print(f"\n[2/3] 并行下载 (不写盘, 无锁竞争)...")
    all_dfs = []
    success, failed = 0, 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(download_stock, code): code for code in codes}
        for i, future in enumerate(as_completed(futures)):
            code = futures[future]
            try:
                df = future.result()
                if df is not None and not df.empty:
                    df = build_standard_df(df, code)
                    all_dfs.append(df)
                    success += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

            if (i + 1) % 500 == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (len(codes) - i - 1) / rate if rate > 0 else 0
                print(f"  进度: {i+1}/{len(codes)} 成功 {success} 速度 {rate:.0f}只/秒 ETA {eta:.0f}s", flush=True)

    elapsed = time.time() - start_time
    print(f"  下载完成! 成功 {success} 失败 {failed} 耗时 {elapsed:.0f}s")

    if not all_dfs:
        print("[错误] 没有下载到数据!")
        return

    # 合并 + 写入
    print(f"\n[3/3] 合并写入 Parquet...")
    combined = pd.concat(all_dfs, ignore_index=True)
    combined['year'] = combined['date'].dt.year

    for year, group in combined.groupby('year'):
        group_w = group.drop(columns=['year'])
        year_dir = os.path.join(DATA_PATH, "daily_bar", f"year={year}")
        os.makedirs(year_dir, exist_ok=True)
        out_path = os.path.join(year_dir, "data.parquet")

        # 直接覆盖 (用前复权数据替换不复权数据)
        group_w.to_parquet(out_path, index=False)
        print(f"  year={year}: {len(group_w):,} 行, {group_w['instrument'].nunique():,} 只")

    print(f"\n{'='*60}")
    print(f"  完成! 总行数: {len(combined):,}, 总股票: {success}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

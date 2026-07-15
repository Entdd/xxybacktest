"""
download_mootdx.py — 从通达信 mootdx 下载全量 A 股日线数据

原理:
    - mootdx 连接通达信行情服务器 (TCP 7709)，逐只下载日K线
    - 每次调用 offset=800 可获得约 3 年的日线数据
    - 下载后写入 xxydb Parquet 格式 (和现有数据兼容)

用法:
    python scripts/download_mootdx.py

注意:
    - 约 5000 只 A 股，每只 0.3 秒延迟，预计 25-30 分钟
    - 非交易时间下载速度更快（服务器负载低）
    - mootdx 返回的是不复权原始价，但 xxydb backtest 引擎支持
"""

import os
import sys
import time
import pandas as pd
import numpy as np
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xxydb import xxydb

DATA_PATH = "d:/xxybacktest-master/data"
START_DATE = "2023-01-01"
BATCH_DELAY = 0.15  # 每只股票间隔(秒)，太快会被服务器限流
OFFSET = 800        # 取最近800根日K线（约3年）


def get_stock_list_from_db(db):
    """从现有数据中获取所有股票代码"""
    try:
        df = db.query("SELECT DISTINCT instrument FROM daily_bar ORDER BY instrument").df()
        codes = sorted(df["instrument"].tolist())
        print(f"[信息] 从 daily_bar 读取到 {len(codes)} 只股票")
        return codes
    except Exception:
        return []


def get_stock_list_from_tdx():
    """从通达信服务器获取沪深A股列表 (备用方案)"""
    try:
        from mootdx.quotes import Quotes
        client = Quotes.factory(market="std")
        # 获取深圳A股
        sz = client.stocks(market=0)  # 0=深圳
        sh = client.stocks(market=1)  # 1=上海

        codes = []
        for row in sz:
            code = str(row.get("code", "")).zfill(6)
            if code and not code.startswith("3"):  # 主板+中小板
                codes.append(f"{code}.SZ")
        for row in sh:
            code = str(row.get("code", "")).zfill(6)
            if code:
                codes.append(f"{code}.SH")

        print(f"[信息] 从通达信获取到 {len(codes)} 只A股")
        return sorted(codes)
    except Exception as e:
        print(f"[错误] 获取股票列表失败: {e}")
        return []


def download_one_stock(code, max_retries=3):
    """
    下载单只股票的日线数据。
    返回 DataFrame 或 None。
    """
    from xxybacktest.data_providers.market import tdx_bars

    pure_code = code.replace(".SZ", "").replace(".SH", "").replace(".BJ", "")

    for attempt in range(max_retries):
        try:
            df = tdx_bars(pure_code, frequency=9, offset=OFFSET)
            if df is None or df.empty:
                return None

            # mootdx 返回的列: open, close, high, low, vol, amount, datetime
            df = df.copy()
            df["instrument"] = code
            df["date"] = pd.to_datetime(df["datetime"])

            # 只保留日期范围内的数据
            df = df[df["date"] >= START_DATE]

            if df.empty:
                return None

            # 重命名和补充字段以匹配 daily_bar 表结构
            df = df.rename(columns={"vol": "volume"})

            # 计算衍生字段
            df = df.sort_values("date")
            df["pre_close"] = df["close"].shift(1)
            df["change_ratio"] = (df["close"] / df["pre_close"] - 1).fillna(0)
            df["adjust_factor"] = 1.0  # 原始价，adjust_factor=1
            df["name"] = ""
            df["deal_number"] = 0
            df["turn"] = 0.0
            df["upper_limit"] = (df["pre_close"] * 1.1).round(2)
            df["lower_limit"] = (df["pre_close"] * 0.9).round(2)

            # 只保留需要的列
            keep_cols = [
                "date", "instrument", "name", "adjust_factor", "pre_close",
                "open", "close", "high", "low", "volume", "deal_number",
                "amount", "change_ratio", "turn", "upper_limit", "lower_limit"
            ]
            df = df[[c for c in keep_cols if c in df.columns]]
            return df

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                # 静默失败，一个股票下载失败不影响整体
                pass

    return None


def main():
    print("=" * 60)
    print("  A 股日线数据下载 (mootdx 通达信)")
    print("=" * 60)
    print(f"  数据路径: {DATA_PATH}")
    print(f"  日期范围: {START_DATE} ~ 今天")
    print(f"  每只股票: {OFFSET} 根K线")
    print()

    # ── 初始化数据库 ──
    db = xxydb(path=DATA_PATH)

    # ── 获取股票列表 ──
    codes = get_stock_list_from_db(db)
    if not codes:
        print("[信息] 数据库无股票，从通达信获取列表...")
        codes = get_stock_list_from_tdx()

    if not codes:
        print("[错误] 无法获取股票列表，退出")
        db.close()
        return

    print(f"[信息] 目标: {len(codes)} 只股票")
    print(f"[信息] 预计耗时: {len(codes) * BATCH_DELAY / 60:.1f} 分钟")
    print()

    # ── 只下载已有数据不足的股票 ──
    try:
        existing = db.query("""
            SELECT instrument, COUNT(*) as n, MAX(date) as last_date
            FROM daily_bar
            GROUP BY instrument
        """).df()
        existing_map = {}
        for _, r in existing.iterrows():
            existing_map[r["instrument"]] = {"count": r["n"], "last_date": r["last_date"]}
    except Exception:
        existing_map = {}

    # 筛选需要更新的股票: 数据少于100天 或 最新日期早于30天前
    from datetime import timedelta
    cutoff_date = datetime.now() - timedelta(days=30)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d")

    to_download = []
    skip_count = 0
    for code in codes:
        info = existing_map.get(code)
        if info and info["count"] >= 100 and str(info["last_date"])[:10] >= cutoff_str:
            skip_count += 1
        else:
            to_download.append(code)

    print(f"[信息] 数据充足跳过: {skip_count} 只")
    print(f"[信息] 需要下载: {len(to_download)} 只")

    if not to_download:
        print("[信息] 无需下载，退出")
        db.close()
        return

    # ── 逐只下载 ──
    all_data = []
    success = 0
    failed = 0

    start_time = time.time()

    for i, code in enumerate(to_download):
        try:
            df = download_one_stock(code)
            if df is not None and len(df) > 0:
                all_data.append(df)
                success += 1
            else:
                failed += 1
        except Exception:
            failed += 1

        # 进度显示
        if (i + 1) % 100 == 0:
            elapsed = time.time() - start_time
            eta = elapsed / (i + 1) * len(to_download) - elapsed
            print(f"  进度: {i+1}/{len(to_download)} "
                  f"(成功 {success}, 失败 {failed}) "
                  f"耗时 {elapsed:.0f}s, 预计剩余 {eta:.0f}s")

        time.sleep(BATCH_DELAY)

    # ── 写入数据 ──
    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        print(f"\n[写入] 总行数: {len(combined)}, {combined['instrument'].nunique()} 只股票")

        # 按年分区写入 Parquet
        combined["year"] = combined["date"].dt.year
        for year, group in combined.groupby("year"):
            year_dir = os.path.join(DATA_PATH, "daily_bar", f"year={year}")
            os.makedirs(year_dir, exist_ok=True)
            out_path = os.path.join(year_dir, "data.parquet")

            # 如果已有数据，读取并合并
            if os.path.exists(out_path):
                existing = pd.read_parquet(out_path)
                # 按 instrument+date 去重
                group = pd.concat([existing, group], ignore_index=True)
                group = group.drop_duplicates(subset=["instrument", "date"], keep="last")

            group.drop(columns=["year"]).to_parquet(out_path, index=False)
            print(f"  写入 year={year}: {len(group)} 行")

        print(f"\n[完成] 成功: {success}, 失败: {failed}")
        print(f"[注意] mootdx 返回不复权原始价。如需复权数据，")
        print(f"       可运行 scripts/download_data.py (baostock 前复权)")
    else:
        print("\n[错误] 没有下载到任何数据!")

    db.close()


if __name__ == "__main__":
    main()

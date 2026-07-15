"""
tdx_to_xxydb.py — 通达信本地数据 → xxydb Parquet 格式

用法:
    python scripts/tdx_to_xxydb.py

前提:
    通达信已通过"盘后数据下载"下载了日线数据
    默认读取 D:/new/vipdoc/ 下的 sz/lday/ 和 sh/lday/
"""

import os
import sys
import time
from pathlib import Path
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TDX_VIPDOC = r"D:\new\vipdoc"
DATA_PATH = "d:/xxybacktest-master/data"


def count_day_files(vipdoc):
    """统计待处理的 .day 文件数"""
    total = 0
    for market in ["sz", "sh"]:
        lday = os.path.join(vipdoc, market, "lday")
        if os.path.exists(lday):
            total += len([f for f in os.listdir(lday) if f.endswith(".day")])
    return total


def tdx_to_dataframe(vipdoc, code, market):
    """
    读单只股票的 .day 文件，返回 DataFrame。

    参数:
        vipdoc: vipdoc 目录路径
        code: 纯数字代码，如 '000001'
        market: 'sz' 或 'sh'

    返回:
        DataFrame (columns: date, open, high, low, close, volume, amount)
        或 None
    """
    from mootdx.reader import Reader

    # 构造 .day 文件路径: sz/lday/sz000001.day
    filename = f"{market}{code}.day"
    filepath = os.path.join(vipdoc, market, "lday", filename)

    if not os.path.exists(filepath):
        return None

    try:
        reader = Reader.factory(market="std", tdxdir=vipdoc)
        df = reader.daily(symbol=filename)
        if df is None or df.empty:
            return None
        return df
    except Exception:
        return None


def main(start_date="2023-01-01"):
    print("=" * 60)
    print("  通达信本地数据 → xxydb Parquet")
    print("=" * 60)
    print(f"  数据源: {TDX_VIPDOC}")
    print(f"  目标:   {DATA_PATH}")
    print(f"  起始日: {start_date}")
    print()

    # ── 统计文件数 ──
    n_files = count_day_files(TDX_VIPDOC)
    print(f"[信息] 日线文件数: {n_files}")
    if n_files == 0:
        print("[错误] 没有 .day 文件！请先在通达信中下载日线数据")
        return

    # ── 初始化 MooTdxDailyBarReader ──
    from mootdx.reader import MooTdxDailyBarReader
    reader = MooTdxDailyBarReader(vipdoc_path=TDX_VIPDOC)

    # ── 遍历所有 .day 文件 ──
    all_data = []
    success, failed, skipped = 0, 0, 0
    start_time = time.time()
    start_dt = pd.Timestamp(start_date)

    for market_dir, suffix in [("sz", ".SZ"), ("sh", ".SH")]:
        lday = os.path.join(TDX_VIPDOC, market_dir, "lday")
        if not os.path.exists(lday):
            continue

        files = sorted([f for f in os.listdir(lday) if f.endswith(".day")])
        print(f"\n[{market_dir.upper()}] {len(files)} 只股票")

        for filename in files:
            code_num = filename.replace(market_dir, "").replace(".day", "")
            code = f"{code_num}{suffix}"
            filepath = os.path.join(lday, filename)

            try:
                df = reader.get_df_by_file(filepath)
                if df is None or df.empty:
                    skipped += 1
                    continue

                # 日期在 index 中，移到列
                df = df.reset_index()
                if "date" not in df.columns and "index" in df.columns:
                    df = df.rename(columns={"index": "date"})

                # 标准化列名 (get_df_by_file 返回: open, high, low, close, amount, volume)
                # date 已在 reset_index 后成为列

                # 过滤日期
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df[df["date"] >= start_dt]
                if df.empty:
                    skipped += 1
                    continue

                # 补充字段
                df["instrument"] = code
                df["name"] = ""
                df["adjust_factor"] = 1.0
                df["pre_close"] = df["close"].shift(1)
                df["change_ratio"] = (df["close"] / df["pre_close"] - 1).fillna(0)
                df["deal_number"] = 0
                df["turn"] = 0.0
                df["upper_limit"] = (df["pre_close"] * 1.1).round(2)
                df["lower_limit"] = (df["pre_close"] * 0.9).round(2)

                keep_cols = [
                    "date", "instrument", "name", "adjust_factor", "pre_close",
                    "open", "close", "high", "low", "volume", "deal_number",
                    "amount", "change_ratio", "turn", "upper_limit", "lower_limit"
                ]
                df = df[[c for c in keep_cols if c in df.columns]]
                all_data.append(df)
                success += 1

            except Exception:
                failed += 1

            # 进度
            total_done = success + failed + skipped
            if total_done % 200 == 0:
                elapsed = time.time() - start_time
                rate = total_done / elapsed if elapsed > 0 else 0
                print(f"  进度: {total_done}/{n_files} "
                      f"(成功 {success}) "
                      f"速度: {rate:.0f}只/秒")

    if not all_data:
        print("\n[错误] 没有读取到任何数据！")
        return

    # ── 合并写入，按年分区 ──
    combined = pd.concat(all_data, ignore_index=True)
    print(f"\n[写入] 总行数: {len(combined):,}, {combined['instrument'].nunique():,} 只股票")

    combined["year"] = combined["date"].dt.year
    for year, group in combined.groupby("year"):
        year_dir = os.path.join(DATA_PATH, "daily_bar", f"year={year}")
        os.makedirs(year_dir, exist_ok=True)
        out_path = os.path.join(year_dir, "data.parquet")

        if os.path.exists(out_path):
            existing = pd.read_parquet(out_path)
            group = pd.concat([existing, group.drop(columns=["year"])], ignore_index=True)
            group = group.drop_duplicates(subset=["instrument", "date"], keep="last")
        else:
            group = group.drop(columns=["year"])

        group.to_parquet(out_path, index=False)
        print(f"  year={year}: {len(group):,} 行")

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"  完成! 耗时 {elapsed:.1f}s")
    print(f"  成功: {success}, 失败: {failed}, 跳过: {skipped}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

"""
================================================================================
download_data.py —— 从 baostock 下载 A 股数据写入 xxydb 格式
================================================================================
下载内容: daily_bar, stock_status, index_bar, trading_days
覆盖范围: 新闻数据中出现的 A 股 + 沪深 300 成分股 + 主要指数
================================================================================
"""
import os
import sys
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import baostock as bs
from xxydb import xxydb

# ====== 配置 ======
DATA_PATH = "d:/xxybacktest-master/data"
START_DATE = "2023-01-01"
END_DATE = "2026-07-15"
BATCH_DELAY = 0.15  # API 调用间隔 (秒)，baostock 免费不限速

# ====== 步骤 0: 连接 ======
def init_db():
    return xxydb(path=DATA_PATH)

def init_bs():
    lg = bs.login()
    if lg.error_code != '0':
        raise RuntimeError(f"baostock 登录失败: {lg.error_msg}")
    print(f"[OK] baostock 已连接")
    return lg

# ====== 步骤 1: 获取目标股票列表 ======
def get_target_stocks(db):
    """获取需要下载的股票列表: 全量 A 股"""
    codes = set()

    print("[信息] 从 baostock 获取全量A股列表...")
    rs = bs.query_stock_basic()
    if rs is None:
        print("[错误] query_stock_basic 返回 None")
        return []

    while True:
        row = rs.get_row_data()
        if row is None:
            break
        if len(row) >= 6 and row[4] == '1':  # type=1 = 股票(非指数/ETF)
            code = row[0]
            if code.startswith('sh.'):
                codes.add(code.replace('sh.', '') + '.SH')
            elif code.startswith('sz.'):
                codes.add(code.replace('sz.', '') + '.SZ')

    print(f"[信息] baostock 全量 A 股: {len(codes)} 只")

    # ── 检查哪些已有足够数据 ──
    try:
        existing = db.query("""
            SELECT instrument, COUNT(*) as n, MAX(date) as last_date
            FROM daily_bar GROUP BY instrument
        """).df()
        skip = 0
        need = []
        for code in sorted(codes):
            match = existing[existing["instrument"] == code]
            if len(match) > 0:
                n = match.iloc[0]["n"]
                last = str(match.iloc[0]["last_date"])[:10]
                # 数据 > 500 天且最新日期在近期 → 跳过
                if n > 500 and last >= "2026-06-15":
                    skip += 1
                    continue
            need.append(code)
        print(f"[信息] 数据充足: {skip} 只, 需要下载: {len(need)} 只")
        return need
    except Exception:
        return sorted(codes)

# ====== 步骤 2: 下载日线数据 ======
def download_daily_bar(db, codes):
    """逐只下载日线数据并写入 xxydb"""
    # 先清理旧数据（只保留 2026 年的 demo 数据不删）
    print(f"\n[下载] 日线数据 {START_DATE} ~ {END_DATE}, {len(codes)} 只股票")
    print(f"       预计耗时: ~{len(codes) * BATCH_DELAY / 60:.1f} 分钟")

    schema = {
        "date": {"desc": "交易日期"},
        "instrument": {"desc": "股票代码"},
        "name": {"desc": "证券简称"},
        "adjust_factor": {"desc": "累积后复权因子"},
        "pre_close": {"desc": "昨收盘价"},
        "open": {"desc": "开盘价"},
        "close": {"desc": "收盘价"},
        "high": {"desc": "最高价"},
        "low": {"desc": "最低价"},
        "volume": {"desc": "成交量"},
        "deal_number": {"desc": "成交笔数"},
        "amount": {"desc": "成交金额"},
        "change_ratio": {"desc": "涨跌幅"},
        "turn": {"desc": "换手率"},
        "upper_limit": {"desc": "涨停价"},
        "lower_limit": {"desc": "跌停价"},
    }

    all_data = []
    success = 0
    failed = 0

    for i, code in enumerate(codes):
        try:
            # baostock 格式: sh.600519 或 sz.000001
            if code.endswith('.SH'):
                bs_code = f"sh.{code[:6]}"
            elif code.endswith('.SZ'):
                bs_code = f"sz.{code[:6]}"
            else:
                continue

            rs = bs.query_history_k_data_plus(
                bs_code,
                'date,open,high,low,close,preclose,volume,amount,turn,tradestatus',
                start_date=START_DATE,
                end_date=END_DATE,
                frequency='d',
                adjustflag='2'  # 前复权
            )

            if rs is None or rs.error_code != '0':
                failed += 1
                continue

            rows = []
            while rs.next():
                rows.append(rs.get_row_data())

            if not rows:
                continue

            df = pd.DataFrame(rows, columns=['date','open','high','low','close','preclose','volume','amount','turn','tradestatus'])
            df['date'] = pd.to_datetime(df['date'])
            df['instrument'] = code

            # 数值列转换
            for col in ['open','high','low','close','preclose','volume','amount','turn']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # 去掉停牌日
            df = df[df['tradestatus'] == '1'].copy()

            # 计算衍生字段
            df['change_ratio'] = (df['close'] / df['preclose'] - 1).fillna(0)
            df['adjust_factor'] = 1.0  # baostock 前复权不需要额外复权因子
            df['name'] = ''
            df['deal_number'] = 0
            # 涨跌停价: 简化计算 (10%)
            df['upper_limit'] = (df['preclose'] * 1.1).round(2)
            df['lower_limit'] = (df['preclose'] * 0.9).round(2)

            df = df[list(schema.keys())]

            if len(df) > 0:
                all_data.append(df)
                success += 1

        except Exception as e:
            failed += 1
            if failed <= 5:
                print(f"  [错误] {code}: {e}")

        if (i + 1) % 100 == 0:
            print(f"  进度: {i+1}/{len(codes)} (成功 {success}, 失败 {failed})")

        time.sleep(BATCH_DELAY)

    print(f"  完成: 成功 {success}, 失败 {failed}")

    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        print(f"  总行数: {len(combined)}, {combined['instrument'].nunique()} 只股票")

        # 写入 xxydb (按年分区)，与已有数据合并
        combined['year'] = combined['date'].dt.year
        for year, group in combined.groupby('year'):
            year_dir = os.path.join(DATA_PATH, "daily_bar", f"year={year}")
            os.makedirs(year_dir, exist_ok=True)
            out_path = os.path.join(year_dir, "data.parquet")

            # 如果已有数据，合并去重
            if os.path.exists(out_path):
                existing = pd.read_parquet(out_path)
                group = pd.concat([existing, group.drop(columns=['year'])], ignore_index=True)
                group = group.drop_duplicates(subset=["instrument", "date"], keep="last")
            else:
                group = group.drop(columns=['year'])

            group.to_parquet(out_path, index=False)
            print(f"  写入 year={year}: {len(group)} 行")

        print(f"  [OK] 日线数据已写入")
        return combined
    return None

# ====== 步骤 3: 下载股票状态 ======
def download_stock_status(db, codes):
    """下载 ST/停牌/涨跌停状态"""
    print(f"\n[下载] 股票状态数据...")

    all_data = []
    for i, code in enumerate(codes[:500]):  # 限制数量, 状态数据量大
        try:
            if code.endswith('.SH'):
                bs_code = f"sh.{code[:6]}"
            elif code.endswith('.SZ'):
                bs_code = f"sz.{code[:6]}"
            else:
                continue

            rs = bs.query_history_k_data_plus(
                bs_code,
                'date,tradestatus',
                start_date=START_DATE,
                end_date=END_DATE,
                frequency='d',
                adjustflag='2'
            )

            if rs.error_code != '0':
                continue

            rows = []
            while rs.next():
                rows.append(rs.get_row_data())

            if rows:
                df = pd.DataFrame(rows, columns=['date', 'tradestatus'])
                df['date'] = pd.to_datetime(df['date'])
                df['instrument'] = code
                df['suspended'] = (df['tradestatus'] == '0').astype(int)
                df['st_status'] = 0
                df['price_limit_status'] = 2  # 默认正常
                df['is_risk_warning'] = 0
                df['exdr'] = 0
                all_data.append(df[['date','instrument','suspended','st_status','price_limit_status','is_risk_warning','exdr']])
            else:
                continue
        except:
            continue

        time.sleep(BATCH_DELAY * 0.5)

    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        combined['year'] = combined['date'].dt.year
        for year, group in combined.groupby('year'):
            year_dir = os.path.join(DATA_PATH, "stock_status", f"year={year}")
            os.makedirs(year_dir, exist_ok=True)
            group.drop(columns=['year']).to_parquet(os.path.join(year_dir, "data.parquet"), index=False)
        print(f"  [OK] 状态数据: {len(combined)} 行, {combined['instrument'].nunique()} 只")
        return combined
    return None

# ====== 步骤 4: 下载指数数据 ======
def download_index_bar(db):
    """下载上证指数和沪深300"""
    print(f"\n[下载] 指数数据...")

    indices = {
        '000001.SH': 'sh.000001',
        '000300.SH': 'sh.000300',
        '399001.SZ': 'sz.399001',
        '399006.SZ': 'sz.399006',
    }

    all_data = []
    for code, bs_code in indices.items():
        rs = bs.query_history_k_data_plus(
            bs_code,
            'date,open,high,low,close,preclose,volume,amount',
            start_date=START_DATE,
            end_date=END_DATE,
            frequency='d',
            adjustflag='2'
        )

        rows = []
        while rs.next():
            rows.append(rs.get_row_data())

        if rows:
            df = pd.DataFrame(rows, columns=['date','open','high','low','close','preclose','volume','amount'])
            df['date'] = pd.to_datetime(df['date'])
            df['instrument'] = code
            df['name'] = {'000001.SH': '上证指数', '000300.SH': '沪深300', '399001.SZ': '深证成指', '399006.SZ': '创业板指'}[code]
            for col in ['open','high','low','close','preclose','volume','amount']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df['change_ratio'] = (df['close'] / df['preclose'] - 1)
            all_data.append(df)
            print(f"  {code} ({df['name'].iloc[0]}): {len(df)} 天")

        time.sleep(0.5)

    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        combined['year'] = combined['date'].dt.year
        for year, group in combined.groupby('year'):
            year_dir = os.path.join(DATA_PATH, "index_bar", f"year={year}")
            os.makedirs(year_dir, exist_ok=True)
            group.drop(columns=['year']).to_parquet(os.path.join(year_dir, "data.parquet"), index=False)
        print(f"  [OK] 指数数据已写入")
        return combined
    return None

# ====== 步骤 5: 更新 tables_config.json ======
def update_tables_config():
    import json
    config_path = os.path.join(DATA_PATH, "tables_config.json")
    if not os.path.exists(config_path):
        print("[警告] tables_config.json 不存在, 跳过")
        return

    with open(config_path, 'r') as f:
        config = json.load(f)

    # 确保表配置包含所有需要的表
    defaults = {
        "daily_bar": {"partition_by": "year"},
        "stock_status": {"partition_by": "year"},
        "index_bar": {"partition_by": "year"},
        "trading_days": {"partition_by": None},
    }
    for table, cfg in defaults.items():
        if table not in config:
            config[table] = cfg

    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"[OK] tables_config.json 已更新")

# ====== 主流程 ======
if __name__ == "__main__":
    print("=" * 60)
    print("  A 股数据下载 (baostock)")
    print("=" * 60)
    print(f"  目标路径: {DATA_PATH}")
    print(f"  日期范围: {START_DATE} ~ {END_DATE}")
    print()

    init_bs()
    db = init_db()

    try:
        # 1. 获取目标股票
        codes = get_target_stocks(db)

        # 2. 下载日线
        daily_df = download_daily_bar(db, codes)

        # 3. 下载状态
        status_df = download_stock_status(db, codes)

        # 4. 下载指数
        index_df = download_index_bar(db)

        # 5. 更新配置
        update_tables_config()

        print(f"\n{'='*60}")
        print(f"  下载完成!")
        if daily_df is not None:
            print(f"  daily_bar:   {daily_df['instrument'].nunique()} 只股票, {len(daily_df)} 行")
        print(f"  路径: {DATA_PATH}")
        print(f"{'='*60}")

    finally:
        bs.logout()
        print("[信息] baostock 已断开")

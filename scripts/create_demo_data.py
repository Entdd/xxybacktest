"""
一键生成演示数据：3只股票 + 上证指数的全年模拟行情
运行后即可正常使用回测和模拟交易功能
"""
import os
import pandas as pd
import numpy as np

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA_PATH, exist_ok=True)

# ============================================================
# 1. 生成交易日历（2024年所有交易日，排除周末）
# ============================================================
dates = pd.date_range("2024-01-01", "2024-12-31", freq="B")  # 工作日
dates = dates[dates.dayofweek < 5]  # 排除周六日
# 简化：去掉几个长假
holidays = [
    "2024-02-09", "2024-02-12", "2024-02-13", "2024-02-14", "2024-02-15", "2024-02-16",
    "2024-04-04", "2024-04-05",
    "2024-05-01", "2024-05-02", "2024-05-03",
    "2024-06-10",
    "2024-09-16", "2024-09-17",
    "2024-10-01", "2024-10-02", "2024-10-03", "2024-10-04", "2024-10-07",
]
dates = [d for d in dates if d.strftime("%Y-%m-%d") not in holidays]
print(f"生成 {len(dates)} 个交易日")

# 保存 trading_days
td_dir = os.path.join(DATA_PATH, "trading_days")
os.makedirs(td_dir, exist_ok=True)
df_td = pd.DataFrame({"date": dates, "market_code": "CN"})
df_td.to_parquet(os.path.join(td_dir, "data.parquet"), index=False)

# ============================================================
# 2. 生成 3 只股票的日线数据
# ============================================================
stocks = [
    {"code": "600519.SH", "name": "贵州茅台"},
    {"code": "000001.SZ", "name": "平安银行"},
    {"code": "000858.SZ", "name": "五粮液"},
]

np.random.seed(42)

rows = []
for stock in stocks:
    # 给每只股票不同起点
    if stock["code"] == "600519.SH":
        base_price = 1700.0
        trend = 0.0003  # 茅台微涨
    elif stock["code"] == "000001.SZ":
        base_price = 10.0
        trend = 0.0001
    else:
        base_price = 150.0
        trend = -0.0001  # 五粮液微跌

    price = base_price
    for d in dates:
        date_str = d.strftime("%Y-%m-%d")
        # 随机日收益率（均值回归 + 趋势）
        ret = np.random.normal(trend, 0.02)
        price = price * (1 + ret)
        if price < 1:
            price = 1

        open_p = price * (1 + np.random.normal(0, 0.005))
        high_p = max(open_p, price) * (1 + abs(np.random.normal(0, 0.01)))
        low_p = min(open_p, price) * (1 - abs(np.random.normal(0, 0.01)))
        pre_close = price / (1 + ret)
        vol = int(abs(np.random.normal(5000000, 2000000)))
        amount = vol * price
        change_ratio = ret

        upper_limit = round(pre_close * 1.10, 2)
        lower_limit = round(pre_close * 0.90, 2)

        rows.append({
            "instrument": stock["code"],
            "name": stock["name"],
            "date": pd.Timestamp(date_str),
            "open": round(open_p, 2),
            "high": round(high_p, 2),
            "low": round(low_p, 2),
            "close": round(price, 2),
            "pre_close": round(pre_close, 2),
            "volume": vol,
            "amount": round(amount, 2),
            "change_ratio": round(change_ratio, 4),
            "upper_limit": upper_limit,
            "lower_limit": lower_limit,
            "turn": round(np.random.uniform(0.001, 0.03), 4),
            "adjust_factor": 1.0,
            "deal_number": int(abs(np.random.normal(50000, 20000))),
        })

df_daily = pd.DataFrame(rows)
df_daily["year"] = df_daily["date"].dt.year

daily_dir = os.path.join(DATA_PATH, "daily_bar")
os.makedirs(daily_dir, exist_ok=True)
for year, group in df_daily.groupby("year"):
    year_dir = os.path.join(daily_dir, f"year={year}")
    os.makedirs(year_dir, exist_ok=True)
    group.drop(columns=["year"]).to_parquet(os.path.join(year_dir, "data.parquet"), index=False)

print(f"生成 {len(df_daily)} 条日线数据")

# ============================================================
# 3. 生成指数数据（上证指数）
# ============================================================
idx_rows = []
idx_price = 3000.0
for d in dates:
    date_str = d.strftime("%Y-%m-%d")
    ret = np.random.normal(0.0002, 0.012)
    idx_price = idx_price * (1 + ret)

    idx_rows.append({
        "instrument": "000001.SH",
        "name": "上证指数",
        "date": pd.Timestamp(date_str),
        "open": round(idx_price * (1 + np.random.normal(0, 0.003)), 2),
        "high": round(idx_price * 1.01, 2),
        "low": round(idx_price * 0.99, 2),
        "close": round(idx_price, 2),
        "pre_close": round(idx_price / (1 + ret), 2),
        "volume": int(abs(np.random.normal(100000000, 30000000))),
        "amount": round(idx_price * 100000000, 2),
        "change_ratio": round(ret, 4),
    })

df_idx = pd.DataFrame(idx_rows)
df_idx["year"] = df_idx["date"].dt.year

idx_dir = os.path.join(DATA_PATH, "index_bar")
os.makedirs(idx_dir, exist_ok=True)
for year, group in df_idx.groupby("year"):
    year_dir = os.path.join(idx_dir, f"year={year}")
    os.makedirs(year_dir, exist_ok=True)
    group.drop(columns=["year"]).to_parquet(os.path.join(year_dir, "data.parquet"), index=False)

print(f"生成 {len(df_idx)} 条指数数据")

# ============================================================
# 4. 生成股票状态数据
# ============================================================
ss_rows = []
for stock in stocks:
    for d in dates:
        ss_rows.append({
            "instrument": stock["code"],
            "date": pd.Timestamp(d.strftime("%Y-%m-%d")),
            "suspended": 0,
            "st_status": 0,
            "price_limit_status": 2,
            "exdr": 0,
            "is_risk_warning": 0,
            "name": stock["name"],
            "list_days": 1000,
            "list_sector": 1,
        })

df_ss = pd.DataFrame(ss_rows)
df_ss["year"] = df_ss["date"].dt.year

ss_dir = os.path.join(DATA_PATH, "stock_status")
os.makedirs(ss_dir, exist_ok=True)
for year, group in df_ss.groupby("year"):
    year_dir = os.path.join(ss_dir, f"year={year}")
    os.makedirs(year_dir, exist_ok=True)
    group.drop(columns=["year"]).to_parquet(os.path.join(year_dir, "data.parquet"), index=False)

# ============================================================
# 5. 生成 basic_info 数据
# ============================================================
bi_rows = []
for stock in stocks:
    for d in dates:
        bi_rows.append({
            "instrument": stock["code"],
            "name": stock["name"],
            "date": pd.Timestamp(d.strftime("%Y-%m-%d")),
            "list_days": 1000,
            "list_sector": 1,
            "st_status": 0,
        })

df_bi = pd.DataFrame(bi_rows)
df_bi["year"] = df_bi["date"].dt.year

bi_dir = os.path.join(DATA_PATH, "basic_info")
os.makedirs(bi_dir, exist_ok=True)
for year, group in df_bi.groupby("year"):
    year_dir = os.path.join(bi_dir, f"year={year}")
    os.makedirs(year_dir, exist_ok=True)
    group.drop(columns=["year"]).to_parquet(os.path.join(year_dir, "data.parquet"), index=False)

# ============================================================
# 6. 生成 valuation 估值数据
# ============================================================
val_rows = []
for stock in stocks:
    for d in dates:
        val_rows.append({
            "instrument": stock["code"],
            "date": pd.Timestamp(d.strftime("%Y-%m-%d")),
            "total_market_cap": np.random.uniform(5e10, 2e12),
            "float_market_cap": np.random.uniform(3e10, 1.5e12),
            "pe_ttm": np.random.uniform(5, 50),
            "pb": np.random.uniform(0.5, 10),
        })

df_val = pd.DataFrame(val_rows)
df_val["year"] = df_val["date"].dt.year

val_dir = os.path.join(DATA_PATH, "valuation")
os.makedirs(val_dir, exist_ok=True)
for year, group in df_val.groupby("year"):
    year_dir = os.path.join(val_dir, f"year={year}")
    os.makedirs(year_dir, exist_ok=True)
    group.drop(columns=["year"]).to_parquet(os.path.join(year_dir, "data.parquet"), index=False)

# ============================================================
# 7. 生成 tables_config.json
# ============================================================
config = {
    "trading_days": {
        "partition_by": None,
        "schema": {"date": "TIMESTAMP", "market_code": "VARCHAR"},
    },
    "daily_bar": {
        "partition_by": "year",
        "schema": {
            "instrument": "VARCHAR", "name": "VARCHAR", "date": "TIMESTAMP",
            "open": "DOUBLE", "high": "DOUBLE", "low": "DOUBLE", "close": "DOUBLE",
            "pre_close": "DOUBLE", "volume": "BIGINT", "amount": "DOUBLE",
            "change_ratio": "DOUBLE", "upper_limit": "DOUBLE", "lower_limit": "DOUBLE",
            "turn": "DOUBLE", "adjust_factor": "DOUBLE", "deal_number": "INTEGER",
        },
    },
    "index_bar": {
        "partition_by": "year",
        "schema": {
            "instrument": "VARCHAR", "name": "VARCHAR", "date": "TIMESTAMP",
            "open": "DOUBLE", "high": "DOUBLE", "low": "DOUBLE", "close": "DOUBLE",
            "pre_close": "DOUBLE", "volume": "BIGINT", "amount": "DOUBLE",
            "change_ratio": "DOUBLE",
        },
    },
    "stock_status": {
        "partition_by": "year",
        "schema": {
            "instrument": "VARCHAR", "date": "TIMESTAMP",
            "suspended": "TINYINT", "st_status": "TINYINT",
            "price_limit_status": "TINYINT", "exdr": "TINYINT",
            "is_risk_warning": "TINYINT", "name": "VARCHAR",
            "list_days": "INTEGER", "list_sector": "INTEGER",
        },
    },
    "basic_info": {
        "partition_by": "year",
        "schema": {
            "instrument": "VARCHAR", "name": "VARCHAR", "date": "TIMESTAMP",
            "list_days": "INTEGER", "list_sector": "INTEGER",
            "st_status": "INTEGER",
        },
    },
    "valuation": {
        "partition_by": "year",
        "schema": {
            "instrument": "VARCHAR", "date": "TIMESTAMP",
            "total_market_cap": "DOUBLE", "float_market_cap": "DOUBLE",
            "pe_ttm": "DOUBLE", "pb": "DOUBLE",
        },
    },
}

import json
with open(os.path.join(DATA_PATH, "tables_config.json"), "w", encoding="utf-8") as f:
    json.dump(config, f, ensure_ascii=False, indent=2)

print(f"\n✅ 演示数据生成完成！")
print(f"   路径: {DATA_PATH}")
print(f"   股票: 600519.SH(茅台), 000001.SZ(平安银行), 000858.SZ(五粮液)")
print(f"   基准: 000001.SH(上证指数)")
print(f"   区间: 2024-01-01 ~ 2024-12-31")
print(f"   交易日: {len(dates)} 天")

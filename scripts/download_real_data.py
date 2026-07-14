"""
用 AKShare 下载 A 股真实行情数据，存入 xxydb 格式
"""
import os, sys, json, time
import pandas as pd
import akshare as ak
from xxydb import xxydb

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA_PATH, exist_ok=True)

# --- 要下载的股票 ---
STOCKS = [
    "600519",  # 贵州茅台
    "000001",  # 平安银行
    "000858",  # 五粮液
    "300750",  # 宁德时代
    "600036",  # 招商银行
    "601318",  # 中国平安
    "600900",  # 长江电力
    "000333",  # 美的集团
    "600276",  # 恒瑞医药
    "002415",  # 海康威视
]

# 判断交易所后缀
def get_code(stock):
    if stock.startswith(("600", "601", "603", "605")):
        return f"{stock}.SH"
    else:
        return f"{stock}.SZ"

print("=" * 60)
print("下载 A 股真实行情数据")
print("=" * 60)

# ============================================================
# 1. 交易日历
# ============================================================
print("\n[1/5] 下载交易日历...")
df_td = ak.tool_trade_date_hist_sina()
df_td = df_td.rename(columns={"trade_date": "date"})
df_td["date"] = pd.to_datetime(df_td["date"])
df_td["market_code"] = "CN"

td_dir = os.path.join(DATA_PATH, "trading_days")
os.makedirs(td_dir, exist_ok=True)
df_td[["date", "market_code"]].to_parquet(
    os.path.join(td_dir, "data.parquet"), index=False
)
print(f"  -> {len(df_td)} 个交易日")

# ============================================================
# 2. 股票日线数据
# ============================================================
print("\n[2/5] 下载股票日线数据...")

def download_stock(symbol, max_retries=3):
    """带重试的下载"""
    for attempt in range(max_retries):
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date="20230101",
                end_date="20260714",
                adjust="qfq",
            )
            return df
        except Exception as e:
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 5
                print(f"(重试 {attempt+1}/{max_retries}, 等{wait}秒) ", end="", flush=True)
                time.sleep(wait)
            else:
                raise e

df_daily = None
for i, stock in enumerate(STOCKS):
    code = get_code(stock)
    name = code
    print(f"  [{i+1}/{len(STOCKS)}] {code} ...", end=" ", flush=True)
    try:
        df = download_stock(stock)
        if df is not None and len(df) > 0:
            df = df.rename(columns={
                "日期": "date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "成交额": "amount",
                "涨跌幅": "change_ratio",
                "换手率": "turn",
                "股票代码": "instrument",
            })
            df["date"] = pd.to_datetime(df["date"])
            df["instrument"] = code
            # 从涨跌幅推算前收盘价
            df["pre_close"] = round(df["close"] / (1 + df["change_ratio"] / 100), 2)
            df["upper_limit"] = round(df["pre_close"] * 1.10, 2)
            df["lower_limit"] = round(df["pre_close"] * 0.90, 2)
            df["adjust_factor"] = 1.0
            df["deal_number"] = 0
            if "名称" in df.columns:
                df["name"] = df["名称"]
            else:
                df["name"] = code

            keep_cols = [
                "instrument", "name", "date", "open", "high", "low", "close",
                "pre_close", "volume", "amount", "change_ratio", "upper_limit",
                "lower_limit", "turn", "adjust_factor", "deal_number",
            ]
            df = df[[c for c in keep_cols if c in df.columns]]

            if df_daily is None:
                df_daily = df
            else:
                df_daily = pd.concat([df_daily, df], ignore_index=True)
            print(f"{len(df)} 条")
        else:
            print("无数据")
    except Exception as e:
        print(f"失败: {e}")
    time.sleep(2)  # 防止请求太快被封

if df_daily is not None:
    df_daily["year"] = df_daily["date"].dt.year
    daily_dir = os.path.join(DATA_PATH, "daily_bar")
    # 清除旧数据
    import shutil
    if os.path.exists(daily_dir):
        shutil.rmtree(daily_dir)
    os.makedirs(daily_dir, exist_ok=True)
    for year, group in df_daily.groupby("year"):
        year_dir = os.path.join(daily_dir, f"year={year}")
        os.makedirs(year_dir, exist_ok=True)
        group.drop(columns=["year"]).to_parquet(
            os.path.join(year_dir, "data.parquet"), index=False
        )
    print(f"  总计 {len(df_daily)} 条日线数据")

# ============================================================
# 3. 指数数据
# ============================================================
print("\n[3/5] 下载指数数据...")
try:
    df_idx = ak.stock_zh_index_daily(symbol="sh000001")
    df_idx = df_idx.rename(columns={
        "date": "date",
        "open": "open",
        "close": "close",
        "high": "high",
        "low": "low",
        "volume": "volume",
        "amount": "amount",
    })
    df_idx["date"] = pd.to_datetime(df_idx["date"])
    df_idx = df_idx[df_idx["date"] >= pd.Timestamp("2023-01-01")]
    df_idx["instrument"] = "000001.SH"
    df_idx["name"] = "上证指数"
    df_idx["pre_close"] = df_idx["close"].shift(1)
    df_idx["change_ratio"] = (
        (df_idx["close"] - df_idx["pre_close"]) / df_idx["pre_close"]
    ).fillna(0)
    df_idx["year"] = df_idx["date"].dt.year

    idx_dir = os.path.join(DATA_PATH, "index_bar")
    if os.path.exists(idx_dir):
        shutil.rmtree(idx_dir)
    os.makedirs(idx_dir, exist_ok=True)
    for year, group in df_idx.groupby("year"):
        year_dir = os.path.join(idx_dir, f"year={year}")
        os.makedirs(year_dir, exist_ok=True)
        group.drop(columns=["year"]).to_parquet(
            os.path.join(year_dir, "data.parquet"), index=False
        )
    print(f"  -> {len(df_idx)} 条指数数据")
except Exception as e:
    print(f"  失败: {e}")

# ============================================================
# 4. 辅助表（stock_status、basic_info）
# ============================================================
print("\n[4/5] 生成辅助表...")

if df_daily is not None:
    # stock_status: 从日线数据推导
    df_ss = df_daily[["instrument", "date", "name", "year"]].copy()
    df_ss["suspended"] = 0
    df_ss["st_status"] = 0
    df_ss["price_limit_status"] = 2
    df_ss["exdr"] = 0
    df_ss["is_risk_warning"] = 0
    df_ss["list_days"] = 1000
    df_ss["list_sector"] = 1

    ss_dir = os.path.join(DATA_PATH, "stock_status")
    if os.path.exists(ss_dir):
        shutil.rmtree(ss_dir)
    os.makedirs(ss_dir, exist_ok=True)
    for year, group in df_ss.groupby("year"):
        year_dir = os.path.join(ss_dir, f"year={year}")
        os.makedirs(year_dir, exist_ok=True)
        group.drop(columns=["year"]).to_parquet(
            os.path.join(year_dir, "data.parquet"), index=False
        )

    # basic_info
    df_bi = df_daily[["instrument", "name", "date", "year"]].copy()
    df_bi["list_days"] = 1000
    df_bi["list_sector"] = 1
    df_bi["st_status"] = 0

    bi_dir = os.path.join(DATA_PATH, "basic_info")
    if os.path.exists(bi_dir):
        shutil.rmtree(bi_dir)
    os.makedirs(bi_dir, exist_ok=True)
    for year, group in df_bi.groupby("year"):
        year_dir = os.path.join(bi_dir, f"year={year}")
        os.makedirs(year_dir, exist_ok=True)
        group.drop(columns=["year"]).to_parquet(
            os.path.join(year_dir, "data.parquet"), index=False
        )

    # valuation（简化版）
    df_val = df_daily[["instrument", "date", "year"]].copy()
    df_val["total_market_cap"] = 1e11
    df_val["float_market_cap"] = 8e10
    df_val["pe_ttm"] = 20.0
    df_val["pb"] = 3.0

    val_dir = os.path.join(DATA_PATH, "valuation")
    if os.path.exists(val_dir):
        shutil.rmtree(val_dir)
    os.makedirs(val_dir, exist_ok=True)
    for year, group in df_val.groupby("year"):
        year_dir = os.path.join(val_dir, f"year={year}")
        os.makedirs(year_dir, exist_ok=True)
        group.drop(columns=["year"]).to_parquet(
            os.path.join(year_dir, "data.parquet"), index=False
        )

    print("  -> stock_status、basic_info、valuation 已生成")

# ============================================================
# 5. 空分红表 + 配置文件
# ============================================================
print("\n[5/5] 生成配置和分红表...")

div_dir = os.path.join(DATA_PATH, "dividend")
if not os.path.exists(div_dir):
    os.makedirs(div_dir, exist_ok=True)
    df_div = pd.DataFrame(columns=[
        "instrument", "name", "date", "register_date", "ex_date",
        "bonus_rate", "conversed_rate", "cash_before_tax", "cash_after_tax",
    ])
    df_div.to_parquet(os.path.join(div_dir, "data.parquet"), index=False)

# tables_config.json
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
    "dividend": {
        "partition_by": None,
        "schema": {
            "instrument": "VARCHAR", "name": "VARCHAR", "date": "TIMESTAMP",
            "register_date": "TIMESTAMP", "ex_date": "TIMESTAMP",
            "bonus_rate": "DOUBLE", "conversed_rate": "DOUBLE",
            "cash_before_tax": "DOUBLE", "cash_after_tax": "DOUBLE",
        },
    },
}

with open(os.path.join(DATA_PATH, "tables_config.json"), "w", encoding="utf-8") as f:
    json.dump(config, f, ensure_ascii=False, indent=2)

print("\n" + "=" * 60)
print("真实数据下载完成!")
if df_daily is not None:
    codes = df_daily["instrument"].unique()
    print(f"股票: {', '.join(codes)}")
    print(f"日期范围: {df_daily['date'].min().date()} ~ {df_daily['date'].max().date()}")
print("=" * 60)

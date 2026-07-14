"""
================================================================================
alphalens_bridge/bridge —— FactorResult ↔ AlphaLens 格式转换
================================================================================
将 xxybacktest FactorResult 转换为 AlphaLens 兼容的 MultiIndex DataFrame,
以便使用 AlphaLens 的 tear sheet 功能进行额外可视化。

用法:
    from xxybacktest.agents import factor_to_alphalens, alphalens_tear_sheet

    # 方式1: 从 FactorResult 转换并画 tear sheet
    res = analyze_factor(sql="...", data_path="./data")
    alphalens_tear_sheet(res, data_path="./data")

    # 方式2: 只转换, 自己调 AlphaLens
    factor_data, prices = factor_to_alphalens(res, data_path="./data")
    from alphalens_modify.tears import create_summary_tear_sheet
    create_summary_tear_sheet(factor_data)

注意: alphalens_modify 为可选依赖, 未安装时会给友好提示。
================================================================================
"""
import pandas as pd
import numpy as np

# 检查 alphalens_modify 是否可用
try:
    import alphalens_modify as al  # noqa: F401
    ALPHALENS_AVAILABLE = True
except ImportError:
    ALPHALENS_AVAILABLE = False


def factor_to_alphalens(factor_result, data_path: str = "./data") -> tuple:
    """
    将 FactorResult 转换为 AlphaLens 需要的 (factor_data, prices) 格式。

    参数:
        factor_result: xxybacktest.factor.FactorResult 对象
        data_path:     数据目录路径, 用于读取行情数据

    返回:
        (factor_data, prices) 元组, 其中:
        - factor_data: MultiIndex (date, asset) DataFrame, 含 factor 列和 forward returns
        - prices: 宽表 DataFrame (dates 行, assets 列)

    使用方法:
        from alphalens_modify.tears import create_summary_tear_sheet
        factor_data, prices = factor_to_alphalens(res)
        create_summary_tear_sheet(factor_data, prices=prices)
    """
    # 1. 从 FactorResult 的 groups 中重建因子值
    # groups 包含每期的分组信息, 我们需要原始因子值
    # 从 group_summary 和 group 明细反向获取
    if hasattr(factor_result, "groups"):
        groups_df = factor_result.groups
    elif isinstance(factor_result, dict) and "groups" in factor_result:
        groups_df = factor_result["groups"]
    else:
        raise ValueError(
            "factor_result 必须是 FactorResult 对象 或 包含 'groups' 键的 dict, "
            f"实际类型: {type(factor_result)}"
        )

    # groups 包含: date, instrument, group, ret_1, ret_5, ret_10, ret_20 (等)
    if groups_df is None or groups_df.empty:
        raise ValueError("FactorResult 中没有 groups 数据。请确保因子已成功分析。")

    # 从 groups 重建 factor 值 (用 group 编号作为因子代理, AlphaLens 在内部重新分组)
    # 更好的做法是从原始数据读取因子值
    factor_cols = ["date", "instrument"]
    # 找到 group 列和 ret 列
    group_col = [c for c in groups_df.columns if c == "group" or c.startswith("group")]
    ret_cols = [c for c in groups_df.columns if c.startswith("ret_")]

    if not group_col:
        raise ValueError(f"groups 数据中找不到 group 列。可用列: {list(groups_df.columns)}")

    # 用 group 编号作为因子值 (越小越好=多头组)
    factor_df = groups_df[factor_cols + [group_col[0]]].copy()
    factor_df.rename(columns={group_col[0]: "factor"}, inplace=True)

    # 构建前向收益 MultiIndex
    factor_df["date"] = pd.to_datetime(factor_df["date"])

    # 获取收益数据
    rets = groups_df[factor_cols + ret_cols].copy()
    rets["date"] = pd.to_datetime(rets["date"])

    # 2. 构建 AlphaLens 格式
    # factor: MultiIndex (date, asset) Series
    factor_series = factor_df.set_index(["date", "instrument"])["factor"]

    # 构建 factor_data: MultiIndex DataFrame
    factor_data = factor_series.to_frame("factor")
    factor_data.index.names = ["date", "asset"]

    # 添加前向收益列
    for rc in ret_cols:
        ret_series = rets.set_index(["date", "instrument"])[rc]
        # AlphaLens 期望收益是小数形式 (不是百分比)
        factor_data[rc] = ret_series

    # 3. 构建 prices (从 data_path 读取)
    prices = None
    try:
        prices = _build_prices(data_path, factor_data.index)
    except Exception:
        pass  # prices 为 None 时部分 tear sheet 功能受限

    return factor_data, prices


def _build_prices(data_path: str, factor_index: pd.MultiIndex) -> pd.DataFrame:
    """从 xxydb 读取价格数据并构建 AlphaLens 兼容的宽表。"""
    from xxydb import xxydb

    dates = factor_index.get_level_values("date").unique()
    assets = factor_index.get_level_values("asset").unique()

    if len(dates) == 0 or len(assets) == 0:
        return None

    min_date = dates.min().strftime("%Y-%m-%d") if hasattr(dates.min(), "strftime") else str(dates.min())[:10]
    max_date = dates.max().strftime("%Y-%m-%d") if hasattr(dates.max(), "strftime") else str(dates.max())[:10]
    asset_list = "', '".join(assets[:500])  # 限制数量避免 SQL 过长

    db = xxydb(path=data_path)
    try:
        sql = (
            f"SELECT date, instrument, close "
            f"FROM daily_bar "
            f"WHERE date >= '{min_date}' AND date <= '{max_date}' "
            f"AND instrument IN ('{asset_list}')"
        )
        df = db.query(sql).df()
    finally:
        db.close()

    if df.empty:
        return None

    df["date"] = pd.to_datetime(df["date"])
    prices = df.pivot(index="date", columns="instrument", values="close")
    return prices


def alphalens_tear_sheet(factor_result, data_path: str = "./data",
                         long_short: bool = True, group_neutral: bool = False):
    """
    用 AlphaLens 为 FactorResult 生成完整的 Summary Tear Sheet。

    参数:
        factor_result: FactorResult 对象
        data_path:     数据目录路径
        long_short:    是否显示多空组合
        group_neutral:  是否做行业中性 (需要 groupby 参数, 暂未实现)

    注意: 需要 pip install alphalens-modify
    """
    if not ALPHALENS_AVAILABLE:
        raise ImportError(
            "AlphaLens 未安装。请执行: pip install alphalens-modify\n"
            "注意: alphalens-modify 需要 Python >= 3.12"
        )

    from alphalens_modify.tears import create_summary_tear_sheet

    factor_data, prices = factor_to_alphalens(factor_result, data_path=data_path)

    if prices is not None:
        create_summary_tear_sheet(
            factor_data,
            prices=prices,
            long_short=long_short,
            group_neutral=group_neutral,
        )
    else:
        # 没有 prices 时, 只能用部分功能
        print("[提示] 无法读取 price 数据, 部分 tear sheet 功能受限。")
        create_summary_tear_sheet(
            factor_data,
            long_short=long_short,
            group_neutral=group_neutral,
        )

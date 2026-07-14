"""
================================================================================
factor_mining/tools —— 因子构建工具集
================================================================================
每个工具返回一个 SQL 片段 (字符串), 可在 daily_bar 的 SELECT 子句中组合使用。

工具分三类:
  - 时序操作: m_avg, m_lag, m_std, m_max, m_min, m_delta, m_roc
  - 代数操作: sub, divide, add, multiply
  - 截面操作: cs_rank, cs_zscore

所有时序工具通过窗口函数实现, 自动 PARTITION BY instrument ORDER BY date。
所有截面工具通过窗口函数实现, 自动 PARTITION BY date。
================================================================================
"""

# daily_bar 表可用字段（供 LLM 参考）
DAILY_BAR_FIELDS = [
    "date", "instrument", "name",
    "open", "high", "low", "close", "pre_close",
    "volume", "amount", "change_ratio", "turn",
    "upper_limit", "lower_limit", "adjust_factor",
    "deal_number",
]

# ====== 时序操作工具 ======

def m_avg(expr: str, N: int) -> str:
    """N 日移动平均: AVG(expr) OVER (PARTITION BY instrument ORDER BY date ROWS N-1 PRECEDING)"""
    return f"(AVG({expr}) OVER (PARTITION BY instrument ORDER BY date ROWS BETWEEN {N-1} PRECEDING AND CURRENT ROW))"


def m_lag(expr: str, N: int) -> str:
    """N 期滞后: LAG(expr, N) OVER (PARTITION BY instrument ORDER BY date)"""
    return f"(LAG({expr}, {N}) OVER (PARTITION BY instrument ORDER BY date))"


def m_std(expr: str, N: int) -> str:
    """N 日标准差: STDDEV_SAMP(expr) OVER (PARTITION BY instrument ORDER BY date ROWS N-1 PRECEDING)"""
    return f"(STDDEV_SAMP({expr}) OVER (PARTITION BY instrument ORDER BY date ROWS BETWEEN {N-1} PRECEDING AND CURRENT ROW))"


def m_max(expr: str, N: int) -> str:
    """N 日最大值: MAX(expr) OVER (PARTITION BY instrument ORDER BY date ROWS N-1 PRECEDING)"""
    return f"(MAX({expr}) OVER (PARTITION BY instrument ORDER BY date ROWS BETWEEN {N-1} PRECEDING AND CURRENT ROW))"


def m_min(expr: str, N: int) -> str:
    """N 日最小值: MIN(expr) OVER (PARTITION BY instrument ORDER BY date ROWS N-1 PRECEDING)"""
    return f"(MIN({expr}) OVER (PARTITION BY instrument ORDER BY date ROWS BETWEEN {N-1} PRECEDING AND CURRENT ROW))"


def m_delta(expr: str, N: int) -> str:
    """N 日变化量: expr - LAG(expr, N) OVER (PARTITION BY instrument ORDER BY date)"""
    return f"({expr} - LAG({expr}, {N}) OVER (PARTITION BY instrument ORDER BY date))"


def m_roc(expr: str, N: int) -> str:
    """N 日变化率: (expr - LAG(expr, N)) / LAG(expr, N)"""
    _lag = f"LAG({expr}, {N}) OVER (PARTITION BY instrument ORDER BY date)"
    return f"(({expr} - {_lag}) / NULLIF({_lag}, 0))"


def m_corr(x: str, y: str, N: int) -> str:
    """N 日相关系数: CORR(x, y) OVER (PARTITION BY instrument ORDER BY date ROWS N-1 PRECEDING)"""
    return f"(CORR({x}, {y}) OVER (PARTITION BY instrument ORDER BY date ROWS BETWEEN {N-1} PRECEDING AND CURRENT ROW))"


def m_sum(expr: str, N: int) -> str:
    """N 日累计和: SUM(expr) OVER (PARTITION BY instrument ORDER BY date ROWS N-1 PRECEDING)"""
    return f"(SUM({expr}) OVER (PARTITION BY instrument ORDER BY date ROWS BETWEEN {N-1} PRECEDING AND CURRENT ROW))"


# ====== 代数操作工具 ======

def sub(a: str, b: str) -> str:
    """因子减法: a - b"""
    return f"({a} - ({b}))"


def divide(a: str, b: str) -> str:
    """因子除法: a / b (安全除零)"""
    return f"(({a}) / NULLIF({b}, 0))"


def add(a: str, b: str) -> str:
    """因子加法: a + b"""
    return f"({a} + ({b}))"


def multiply(a: str, b: str) -> str:
    """因子乘法: a * b"""
    return f"(({a}) * ({b}))"


# ====== 截面操作工具 ======

def cs_rank(expr: str) -> str:
    """截面排名 (从小到大): RANK() OVER (PARTITION BY date ORDER BY expr)"""
    return f"(RANK() OVER (PARTITION BY date ORDER BY {expr}))"


def cs_zscore(expr: str) -> str:
    """截面 z-score: (expr - AVG(expr) OVER date) / STDDEV(expr) OVER date"""
    return (
        f"(({expr} - AVG({expr}) OVER (PARTITION BY date)) "
        f"/ NULLIF(STDDEV_SAMP({expr}) OVER (PARTITION BY date), 0))"
    )


# ====== 工具注册表 (供 LLM 选择) ======

TOOL_REGISTRY = {
    # 时序操作
    "m_avg": {
        "func": m_avg,
        "description": "计算某字段/表达式的 N 日移动平均值",
        "args": {"expr": "字段名或 SQL 表达式 (如 close, volume, open*adj)", "N": "N 日窗口"},
        "example": """m_avg("close", 5) → 5 日均价""",
    },
    "m_lag": {
        "func": m_lag,
        "description": "计算某字段/表达式的 N 期滞后值",
        "args": {"expr": "字段名或 SQL 表达式", "N": "滞后 N 期"},
        "example": """m_lag("close", 1) → 昨日收盘价""",
    },
    "m_std": {
        "func": m_std,
        "description": "计算某字段/表达式的 N 日标准差 (波动率)",
        "args": {"expr": "字段名或 SQL 表达式", "N": "N 日窗口"},
        "example": """m_std("change_ratio", 20) → 20 日涨跌幅波动率""",
    },
    "m_max": {
        "func": m_max,
        "description": "计算某字段/表达式的 N 日最大值",
        "args": {"expr": "字段名或 SQL 表达式", "N": "N 日窗口"},
        "example": """m_max("high", 20) → 20 日最高价""",
    },
    "m_min": {
        "func": m_min,
        "description": "计算某字段/表达式的 N 日最小值",
        "args": {"expr": "字段名或 SQL 表达式", "N": "N 日窗口"},
        "example": """m_min("low", 20) → 20 日最低价""",
    },
    "m_delta": {
        "func": m_delta,
        "description": "计算某字段 N 日的变化量 (当日 - N 日前)",
        "args": {"expr": "字段名或 SQL 表达式", "N": "间隔 N 日"},
        "example": """m_delta("close", 5) → 5 日涨跌额""",
    },
    "m_roc": {
        "func": m_roc,
        "description": "计算某字段 N 日的变化率/收益率",
        "args": {"expr": "字段名或 SQL 表达式", "N": "间隔 N 日"},
        "example": """m_roc("close", 5) → 5 日收益率""",
    },
    "m_corr": {
        "func": m_corr,
        "description": "计算两个字段的 N 日滚动相关系数",
        "args": {"x": "第一个字段", "y": "第二个字段", "N": "N 日窗口"},
        "example": """m_corr("close", "volume", 20) → 量价 20 日相关性""",
    },
    "m_sum": {
        "func": m_sum,
        "description": "计算某字段的 N 日累计和",
        "args": {"expr": "字段名或 SQL 表达式", "N": "N 日窗口"},
        "example": """m_sum("volume", 5) → 5 日累计成交量""",
    },
    # 代数操作
    "sub": {
        "func": sub,
        "description": "两个因子相减",
        "args": {"a": "被减数 (因子/表达式)", "b": "减数 (因子/表达式)"},
        "example": """sub("close", m_lag("close", 1)) → 当日涨跌额""",
    },
    "divide": {
        "func": divide,
        "description": "两个因子相除 (安全除零, 分母为 0 时返回 NULL)",
        "args": {"a": "分子 (因子/表达式)", "b": "分母 (因子/表达式)"},
        "example": """divide(sub("close", m_lag("close", 1)), m_lag("close", 1)) → 日收益率""",
    },
    "add": {
        "func": add,
        "description": "两个因子相加",
        "args": {"a": "因子/表达式", "b": "因子/表达式"},
        "example": """add(m_roc("close", 5), m_roc("close", 10)) → 两周期动量之和""",
    },
    "multiply": {
        "func": multiply,
        "description": "两个因子相乘",
        "args": {"a": "因子/表达式", "b": "因子/表达式"},
        "example": """multiply(m_roc("close", 20), "turn") → 动量 × 换手率""",
    },
    # 截面操作
    "cs_rank": {
        "func": cs_rank,
        "description": "在截面上(同一天所有股票间)对因子值排名, 从小到大",
        "args": {"expr": "因子/表达式"},
        "example": """cs_rank(m_roc("close", 20)) → 20 日收益率截面排名""",
    },
    "cs_zscore": {
        "func": cs_zscore,
        "description": "在截面上(同一天所有股票间)对因子值做 z-score 标准化",
        "args": {"expr": "因子/表达式"},
        "example": """cs_zscore("turn") → 换手率截面 z-score""",
    },
}


def get_tool_description() -> str:
    """生成供 LLM 使用的工具描述列表。"""
    lines = ["可用的因子构建工具 (每个工具返回 SQL 表达式片段):\n"]
    for name, info in TOOL_REGISTRY.items():
        args_desc = ", ".join(f"{k}: {v}" for k, v in info["args"].items())
        lines.append(f"  {name}: {info['description']}")
        lines.append(f"    参数: {args_desc}")
        lines.append(f"    示例: {info['example']}\n")
    return "\n".join(lines)

"""初始化演示因子——将因子提交并跑一次分析，供 Web 看板展示"""
import sys
sys.path.insert(0, "d:/xxybacktest-master")

from xxybacktest.factor.submitter import submit_factor
from xxybacktest.factor.runner import run_single

DATA_PATH = "d:/xxybacktest-master/data"

factors = [
    {
        "name": "5日动量",
        "category": "动量",
        "description": "(close - close_5d_ago) / close_5d_ago",
        "sql": """
SELECT date, instrument, (close - LAG(close, 5) OVER (PARTITION BY instrument ORDER BY date)) / NULLIF(LAG(close, 5) OVER (PARTITION BY instrument ORDER BY date), 0) AS value
FROM daily_bar
""",
    },
    {
        "name": "20日波动率",
        "category": "波动",
        "description": "20日收益率标准差",
        "sql": """
SELECT date, instrument, STDDEV_SAMP(change_ratio) OVER (PARTITION BY instrument ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS value
FROM daily_bar
""",
    },
    {
        "name": "成交量比",
        "category": "量价",
        "description": "5日均量 / 20日均量",
        "sql": """
SELECT date, instrument, AVG(volume) OVER (PARTITION BY instrument ORDER BY date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) / NULLIF(AVG(volume) OVER (PARTITION BY instrument ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW), 0) AS value
FROM daily_bar
""",
    },
    {
        "name": "换手率因子",
        "category": "量价",
        "description": "20日平均换手率",
        "sql": """
SELECT date, instrument, AVG(turn) OVER (PARTITION BY instrument ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS value
FROM daily_bar
""",
    },
]

for f in factors:
    fid = submit_factor(
        name=f["name"], sql=f["sql"], category=f["category"],
        description=f.get("description", ""), data_path=DATA_PATH,
        periods=[1, 5, 10], n_groups=10, run_now=False,
    )
    print(f"[提交] {f['name']}  →  {fid}")
    result = run_single(fid, data_path=DATA_PATH)
    status = result.get("status", "?")
    print(f"  运行结果: {status}")

print("\n全部完成！可启动 Web 查看。")

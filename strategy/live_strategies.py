"""
实盘策略定义 — 注册为模拟账户后每日自动重跑

每个策略是一对 (initialize, handle_data) 函数，
通过 submit() 注册后自动存入数据库，每日定时执行。
"""


# ═══════════════════════════════════════════════════════════
# 策略: 反转+低波选股
# ═══════════════════════════════════════════════════════════

def reversal_init(context):
    """
    反转策略初始化

    核心逻辑:
    - 从全市场选成交最活跃的 500 只作为候选池
    - 每月调仓，买过去 20 天跌得最多的 30 只（反转）
    - 等权重配置
    """
    from xxydb import xxydb

    db = xxydb(path=context.data.data_path)
    # 排除 ETF (159xxx)、可转债、B股，只保留真正的 A 股
    r = db.query("""
        SELECT instrument FROM daily_bar
        WHERE date >= '2026-06-01'
          AND NOT (instrument LIKE '159%' OR instrument LIKE '5%' OR instrument LIKE '9%' OR instrument LIKE '8%')
        GROUP BY instrument
        ORDER BY AVG(volume) DESC
        LIMIT 500
    """).df()
    db.close()

    context.g["pool"] = sorted(r["instrument"].tolist())
    context.g["lookback"] = 20       # 回看天数
    context.g["top_n"] = 30          # 持仓数量
    context.g["rebalance"] = 20      # 调仓周期（交易日）
    context.g["day_count"] = 0

    print(f"[反转策略] 初始化完成，候选池 {len(context.g['pool'])} 只")


def reversal_handle(context):
    """
    每日执行:
    1. 每 20 个交易日调仓一次
    2. 计算每只股票过去 20 天涨跌幅
    3. 选跌幅最大的 30 只买入（反转逻辑）
    4. 卖出不在目标列表的持仓
    """
    context.g["day_count"] += 1

    # 非调仓日跳过
    if context.g["day_count"] % context.g["rebalance"] != 0:
        return

    pool = context.g["pool"]
    lb = context.g["lookback"]
    date_str = context.current_dt.strftime("%Y-%m-%d")

    # 批量获取历史收盘价
    data = context.history(pool, fields=["close"], bar_count=lb + 1)

    # 计算每只股票的动量得分（负动量 = 反转得分高）
    scores = {}
    for code in pool:
        if code not in data or len(data[code]) < lb:
            continue
        closes = [float(row["close"]) for row in data[code]]
        if closes[0] <= 0:
            continue
        momentum = (closes[-1] - closes[0]) / closes[0]
        scores[code] = -momentum  # 跌越多分越高

    if not scores:
        return

    # 排名，取前 top_n
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    target = set(code for code, _ in ranked[: context.g["top_n"]])

    # 打印调仓信息
    top3 = ", ".join(f"{c}({s*100:+.1f}%)" for c, s in ranked[:3])
    print(f"[反转策略] {date_str} 调仓 Top3: {top3}")

    # 卖出不在目标的
    positions = context.get_account_positions()
    for code in list(positions.keys()):
        if code not in target:
            context.order_target_percent(code, 0)

    # 等权重买入目标
    if target:
        weight = 0.95 / len(target)
        for code in target:
            context.order_target_percent(code, weight)


# ═══════════════════════════════════════════════════════════
# 注册入口
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    from xxybacktest.simulation import submit

    account_id = submit(
        name="反转选股策略 v1",
        initialize=reversal_init,
        handle_data=reversal_handle,
        capital=1000000,
        start_date="2023-06-01",
        data_path="./data",
        asset_type="stock",
        benchmark="000001.SH",
        run_now=True,
    )

    if account_id:
        print(f"\n账户已创建: {account_id}")
        print(f"Web 看板: http://localhost:5000/account 可查看净值曲线和持仓")

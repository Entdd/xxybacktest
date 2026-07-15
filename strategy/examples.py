"""
策略示例库 — 从入门到实战
========================

每个策略都是一个独立的函数对 (initialize, handle_data)，
可以直接导入后用于回测或提交为模拟账户。

使用方法:
    # 方法1: 直接回测 (在脚本中)
    from xxybacktest import run_backtest
    from strategy.examples import dca_init, dca_handle

    context = run_backtest(
        initialize=dca_init,
        handle_data=dca_handle,
        start_date="2023-01-03",
        end_date="2026-07-14",
        capital=100000,
        data_path="./data",
        benchmark="000333.SZ",
        plot=False,
    )
    print(f"最终净值: {context.performance.returns[-1][1]:.4f}")

    # 方法2: 注册为模拟账户 (自动每日重跑)
    from xxybacktest.simulation import submit
    account_id = submit(
        name="定投策略",
        initialize=dca_init,
        handle_data=dca_handle,
        capital=100000,
        start_date="2023-01-03",
        run_now=True,
    )
"""

import math

# ═══════════════════════════════════════════════════════════════════════════════
# 策略 #1: 定投策略 (Dollar Cost Averaging)
# 难度: ⭐ | 核心概念: initialize + order_value + context.g
# ═══════════════════════════════════════════════════════════════════════════════

def dca_init(context):
    """
    定投设置：
    - 每月投入 fund_per_month 元
    - 买入目标股票 target_stock
    - 当天是否已定投通过 context.g 记录
    """
    context.g["fund_per_month"] = 10000        # 每月投 1 万元
    context.g["target_stock"] = "000333.SZ"    # 美的集团
    context.g["last_month"] = None             # 记录上次定投的月份


def dca_handle(context):
    """
    每天检查：如果进入了新的月份，就买入固定金额。

    核心 API:
        context.order_value(code, 金额) — 按金额买入
        正数 = 买入，负数 = 卖出
    """
    # 获取当前日期的月份
    current_month = context.current_dt.strftime("%Y-%m")

    # 如果本月已经投过，跳过
    if current_month == context.g["last_month"]:
        return

    # 标记本月已投
    context.g["last_month"] = current_month

    # 买入
    code = context.g["target_stock"]
    amount = context.g["fund_per_month"]
    print(f"[定投] {context.current_dt.strftime('%Y-%m-%d')} 买入 {code} {amount:.0f} 元")
    context.order_value(code, amount)


# ═══════════════════════════════════════════════════════════════════════════════
# 策略 #2: 双均线金叉死叉
# 难度: ⭐⭐ | 核心概念: context.history 取K线 + 技术信号
# ═══════════════════════════════════════════════════════════════════════════════

def ma_cross_init(context):
    """
    双均线设置：
    - 短均线 5 日
    - 长均线 20 日
    - 金叉全仓买入，死叉全仓卖出
    """
    context.g["short_window"] = 5
    context.g["long_window"] = 20
    context.g["target_stock"] = "000333.SZ"
    context.g["position"] = False       # 是否有持仓


def ma_cross_handle(context):
    """
    每5天检查一次：
    1. 用 context.history 取过去 20+ 天的收盘价
    2. 计算 5 日均线和 20 日均线
    3. 金叉买入，死叉卖出

    核心 API:
        context.history(codes, fields, bar_count)
        返回: dict[str -> recarray]，recarray 字段名即 fields 参数
    """
    code = context.g["target_stock"]
    short = context.g["short_window"]
    long = context.g["long_window"]

    # context.history 返回过去 N 天的数据（不含当天）
    # 需要 long+2 条，因为要算均线 + 判断前一天的状态
    data = context.history([code], fields=["close"], bar_count=long + 2)

    if code not in data or len(data[code]) < long + 1:
        return

    closes = [float(row["close"]) for row in data[code]]

    # 5日均线（含昨天）
    ma_short_today = sum(closes[-(short):]) / short
    ma_long_today = sum(closes[-(long):]) / long
    # 5日均线（前天）
    ma_short_yesterday = sum(closes[-(short+1):-1]) / short
    ma_long_yesterday = sum(closes[-(long+1):-1]) / long

    has_position = context.g["position"]
    date_str = context.current_dt.strftime("%Y-%m-%d")

    # 金叉：短线上穿长线 + 没持仓 → 全仓买入
    if ma_short_yesterday <= ma_long_yesterday and ma_short_today > ma_long_today:
        if not has_position:
            print(f"[金叉] {date_str} MA{short}={ma_short_today:.2f} 上穿 MA{long}={ma_long_today:.2f} → 全仓买入")
            context.order_target_percent(code, 0.95)  # 95% 仓位
            context.g["position"] = True

    # 死叉：短线下穿长线 + 有持仓 → 全部卖出
    elif ma_short_yesterday >= ma_long_yesterday and ma_short_today < ma_long_today:
        if has_position:
            print(f"[死叉] {date_str} MA{short}={ma_short_today:.2f} 下穿 MA{long}={ma_long_today:.2f} → 清仓")
            context.order_target_percent(code, 0)
            context.g["position"] = False


# ═══════════════════════════════════════════════════════════════════════════════
# 策略 #3: 动量选股轮动
# 难度: ⭐⭐⭐ | 核心概念: 多股票排序 + 定期调仓 + 持仓管理
# ═══════════════════════════════════════════════════════════════════════════════

# 股票池（你的数据库里数据较全的几只）
MOMENTUM_POOL = [
    "000333.SZ",   # 美的集团
]


def momentum_init(context):
    """动量轮动设置"""
    context.g["pool"] = MOMENTUM_POOL
    context.g["lookback"] = 20           # 回看 20 天
    context.g["top_n"] = 1               # 持有前 N 名（当前只有1只有数据）
    context.g["rebalance_days"] = 5      # 每 5 个交易日调仓一次
    context.g["day_count"] = 0


def momentum_handle(context):
    """
    每 5 天调仓一次：
    1. 计算股票池中每只股票过去 20 天的涨跌幅
    2. 选最强的 top_n 只
    3. 卖掉不在池子里的，买入新入选的

    核心 API:
        context.order_target_percent(code, pct) — 调到目标仓位百分比
        context.get_account_positions() — 当前持仓
    """
    context.g["day_count"] += 1

    # 只在调仓日执行
    if context.g["day_count"] % context.g["rebalance_days"] != 0:
        return

    pool = context.g["pool"]
    lookback = context.g["lookback"]
    top_n = context.g["top_n"]

    # 批量取所有候选股的历史行情
    data = context.history(pool, fields=["close"], bar_count=lookback + 1)

    # 计算每只股票的动量（过去N天涨跌幅）
    momentum_scores = {}
    for code in pool:
        if code not in data or len(data[code]) < lookback:
            continue
        old_close = float(data[code][0]["close"])
        new_close = float(data[code][-1]["close"])
        if old_close > 0:
            momentum_scores[code] = (new_close - old_close) / old_close

    # 按动量排序，取前 top_n
    ranked = sorted(momentum_scores.items(), key=lambda x: x[1], reverse=True)
    target_stocks = set(code for code, _ in ranked[:top_n])

    date_str = context.current_dt.strftime("%Y-%m-%d")
    if target_stocks:
        momentum_scores_str = ", ".join(f"{c}({s*100:.1f}%)" for c, s in ranked[:top_n])
        print(f"[动量轮动] {date_str} 最强股: {momentum_scores_str}")
    else:
        print(f"[动量轮动] {date_str} 无信号，跳过")
        return

    # 卖出不在目标列表的持仓
    positions = context.get_account_positions()
    for code in positions:
        if code not in target_stocks:
            print(f"  卖出 {code}")
            context.order_target_percent(code, 0)

    # 买入目标股票，等权重分配
    if target_stocks:
        weight = 0.95 / len(target_stocks)  # 留 5% 现金
        for code in target_stocks:
            context.order_target_percent(code, weight)


# ═══════════════════════════════════════════════════════════════════════════════
# 策略 #4: 涨停板打板策略
# 难度: ⭐⭐⭐⭐ | 核心概念: 信号数据 + 次日卖出 + 止损
# ═══════════════════════════════════════════════════════════════════════════════

def limit_up_init(context):
    """
    打板策略设置：
    - 每天从涨停池选首板股票
    - 次日开盘买入，持有 3 天卖出
    - 单只最大仓位 10%
    """
    context.g["hold_days"] = 3            # 持有天数
    context.g["max_position_pct"] = 0.10  # 单只最大仓位
    context.g["max_stocks"] = 5           # 最多持有5只
    context.g["stop_loss"] = -0.05        # 止损线 -5%
    # 买入队列: {code: buy_date}
    context.g["buy_queue"] = {}


def limit_up_handle(context):
    """
    （高级策略，需要接入涨停池数据，当前为框架演示）

    流程:
    1. 检查持仓是否需要卖出（到期或止损）
    2. 获取当日涨停池
    3. 筛选首板 + 封板早的股票
    4. 买入
    """
    date_str = context.current_dt.strftime("%Y-%m-%d")
    positions = context.get_account_positions()

    # ── 检查卖出的股票 ──
    to_sell = []
    for code, pos in positions.items():
        # 止损检查：当前价 vs 成本价
        if pos.get("cost_price") and pos.get("last_price"):
            pnl_pct = pos["last_price"] / pos["cost_price"] - 1
            if pnl_pct <= context.g["stop_loss"]:
                to_sell.append((code, f"止损({pnl_pct*100:.1f}%)"))

        # 到期检查：持有天数到了 → 卖出
        if code in context.g["buy_queue"]:
            buy_dt = context.g["buy_queue"][code]
            from datetime import datetime
            buy_date = datetime.strptime(buy_dt, "%Y-%m-%d")
            hold_days = (context.current_dt - buy_date).days
            if hold_days >= context.g["hold_days"]:
                to_sell.append((code, f"到期({hold_days}天)"))

    for code, reason in to_sell:
        print(f"[打板] {date_str} 卖出 {code} 原因: {reason}")
        context.order_target_percent(code, 0)
        context.g["buy_queue"].pop(code, None)

    # ── 检查是否需要加仓 ──
    current_count = len(positions) - len(to_sell)
    if current_count >= context.g["max_stocks"]:
        return  # 满仓了

    # ⚠️ 以下为伪代码：实际需要接入涨停池 API
    # from xxybacktest.data_providers import em_zt_pool
    # zt_pool = em_zt_pool(date_str.replace("-", ""))
    # first_seal = [s for s in zt_pool if s["limit_days"] == 1 and s["break_times"] == 0]
    # candidates = sorted(first_seal, key=lambda s: s["first_seal"])[:3]
    #
    # for c in candidates:
    #     code = c["code"]
    #     pct = context.g["max_position_pct"]
    #     print(f"[打板] {date_str} 打板买入 {code} {c['name']} 首封{c['first_seal']}")
    #     context.order_target_percent(code, pct)
    #     context.g["buy_queue"][code] = date_str

    print(f"[打板] {date_str} 策略就绪（持仓{current_count}只，仓位上限{context.g['max_stocks']}只）")


# ═══════════════════════════════════════════════════════════════════════════════
# 策略 #5: 多因子打分选股
# 难度: ⭐⭐⭐⭐⭐ | 核心概念: 基本面因子 + 加权打分 + 行业中性
# ═══════════════════════════════════════════════════════════════════════════════

def multifactor_init(context):
    """
    多因子打分设置：
    - 价值因子: 低PE（市盈率越低越好）
    - 动量因子: 过去20天涨幅（越高越好）
    - 质量因子: 高ROE（净资产收益率越高越好）

    每个因子标准化后加权求和，选总分最高的股票。
    """
    context.g["pool"] = MOMENTUM_POOL      # 候选池
    context.g["top_n"] = 1
    context.g["rebalance_days"] = 20       # 每月调仓
    context.g["day_count"] = 0

    # 因子权重（总和=1）
    context.g["weights"] = {
        "value": 0.35,      # 低PE
        "momentum": 0.35,   # 动量
        "quality": 0.30,    # 高ROE
    }


def multifactor_handle(context):
    """每月调仓一次，基于多因子打分选股"""
    context.g["day_count"] += 1

    if context.g["day_count"] % context.g["rebalance_days"] != 0:
        return

    pool = context.g["pool"]
    date_str = context.current_dt.strftime("%Y-%m-%d")

    # ── 1. 获取因子数据 ──
    # 动量因子：直接用行情数据算
    price_data = context.history(pool, fields=["close"], bar_count=21)
    momentum_scores = {}
    for code in pool:
        if code not in price_data or len(price_data[code]) < 20:
            continue
        old = float(price_data[code][0]["close"])
        new = float(price_data[code][-1]["close"])
        if old > 0:
            momentum_scores[code] = (new - old) / old

    # 价值因子和质量因子：需要基本面数据
    # ⚠️ 以下为伪代码框架，实际需要从 Data 层或数据库取 PE/ROE
    # from xxybacktest import Data
    # finance = Data.get_finance(code)  # 取最新财务数据
    # pe_scores[code] = -finance["pe"]   # 负号：PE越低分越高
    # roe_scores[code] = finance["roe"]

    # 演示：只用动量因子选股
    if not momentum_scores:
        print(f"[多因子] {date_str} 无有效数据")
        return

    # ── 2. 标准化（Z-score）──
    def zscore(scores_dict):
        values = list(scores_dict.values())
        if len(values) < 2:
            return {k: 0.0 for k in scores_dict}
        avg = sum(values) / len(values)
        std = math.sqrt(sum((v - avg)**2 for v in values) / len(values))
        if std == 0:
            return {k: 0.0 for k in scores_dict}
        return {k: (v - avg) / std for k, v in scores_dict.items()}

    momentum_z = zscore(momentum_scores)
    # pe_z = zscore(pe_scores)     # 需要的数据暂缺
    # roe_z = zscore(roe_scores)

    # ── 3. 加权计算总分 ──
    w = context.g["weights"]
    composite = {}
    for code in momentum_z:
        score = w["momentum"] * momentum_z[code]
        # score += w["value"] * pe_z.get(code, 0)
        # score += w["quality"] * roe_z.get(code, 0)
        composite[code] = score

    # ── 4. 选股 + 调仓 ──
    ranked = sorted(composite.items(), key=lambda x: x[1], reverse=True)
    target_stocks = set(code for code, _ in ranked[:context.g["top_n"]])

    print(f"[多因子] {date_str} 综合得分 TOP{context.g['top_n']}: "
          + ", ".join(f"{c}({s:.2f})" for c, s in ranked[:context.g["top_n"]]))

    # 卖出不在目标列表的
    positions = context.get_account_positions()
    for code in positions:
        if code not in target_stocks:
            context.order_target_percent(code, 0)

    # 买入目标
    if target_stocks:
        weight = 0.95 / len(target_stocks)
        for code in target_stocks:
            context.order_target_percent(code, weight)


# ═══════════════════════════════════════════════════════════════════════════════
# 工具函数：快速测试
# ═══════════════════════════════════════════════════════════════════════════════

def quick_test(strategy_name="dca"):
    """
    快速运行一个策略回测并打印结果。

    参数:
        strategy_name: "dca" | "ma_cross" | "momentum" | "limit_up" | "multifactor"
    """
    from xxybacktest import run_backtest

    strategies = {
        "dca":        (dca_init, dca_handle),
        "ma_cross":   (ma_cross_init, ma_cross_handle),
        "momentum":   (momentum_init, momentum_handle),
        "limit_up":   (limit_up_init, limit_up_handle),
        "multifactor":(multifactor_init, multifactor_handle),
        "live_factor":(live_factor_init, live_factor_handle),
    }

    if strategy_name not in strategies:
        print(f"未知策略: {strategy_name}，可选: {list(strategies.keys())}")
        return

    init, handle = strategies[strategy_name]
    print(f"\n{'='*60}")
    print(f"回测策略: {strategy_name}")
    print(f"{'='*60}")

    context = run_backtest(
        initialize=init,
        handle_data=handle,
        start_date="2023-01-03",
        end_date="2026-07-14",
        capital=100000,
        data_path="./data",
        plot=False,
    )

    # ── 分析结果 ──
    returns = getattr(context.performance, 'returns', None)
    if returns is not None and len(returns) > 0:
        if hasattr(returns, 'iloc'):
            final_nav = (1 + returns).cumprod().iloc[-1]
            total_return = float((final_nav - 1) * 100)
            # 年化收益率
            days = len(returns)
            annual_return = (final_nav ** (252 / days) - 1) * 100 if days > 0 else 0
        else:
            # 原始列表格式
            final_nav = returns[-1][1] if isinstance(returns[-1], (list, tuple)) else returns[-1]
            total_return = (final_nav - 1) * 100
            # 近似年化
            from datetime import datetime
            start = datetime.strptime("2023-01-03", "%Y-%m-%d")
            end = datetime.strptime("2026-07-14", "%Y-%m-%d")
            years = (end - start).days / 365.0
            annual_return = (final_nav ** (1 / years) - 1) * 100 if years > 0 else 0
    else:
        final_nav = 1.0
        total_return = 0
        annual_return = 0

    # ── 订单统计 ──
    n_orders = len(context.order) if hasattr(context, 'order') and context.order is not None else 0
    n_positions = len(getattr(context.performance, 'position_snapshots', []))

    print(f"\n{'='*60}")
    print(f"回测结果")
    print(f"{'='*60}")
    print(f"  初始资金:    100,000")
    print(f"  最终净值:    {final_nav:.4f}")
    print(f"  总收益率:    {total_return:.2f}%")
    print(f"  年化收益率:  {annual_return:.2f}%")
    print(f"  总订单数:    {n_orders}")
    print(f"  持仓快照:    {n_positions}")

    return context


# ═══════════════════════════════════════════════════════════════════════════════
# 策略 #6: 实战多因子策略（基于验证过的因子）
# ═══════════════════════════════════════════════════════════════════════════════

# 你的数据库中 7 只有完整数据的股票
FULL_DATA_POOL = [
    "000333.SZ",  # 美的集团
    "300750.SZ",  # 宁德时代
    "000858.SZ",  # 五粮液
    "600036.SH",  # 招商银行
    "002415.SZ",  # 海康威视
    "601318.SH",  # 中国平安
    "600900.SH",  # 长江电力
]


def live_factor_init(context):
    """
    实战多因子策略 v2 — 加入大盘择时 + 趋势过滤

    改进点（v1 只有 2.4% 收益的教训）:
    1. 大盘择时: 只有当至少一半候选股在上涨时才开仓，否则空仓
    2. 绝对动量过滤: 只买收益率 > 0 的股票（不买下跌中的）
    3. 放宽止损: -12%（给波动留空间）
    4. 保留现金: 没机会时空仓不动
    """
    context.g["pool"] = FULL_DATA_POOL
    context.g["momentum_window"] = 20
    context.g["top_n"] = 3
    context.g["rebalance_freq"] = 20
    context.g["stop_loss"] = -0.12     # 放宽到 -12%
    context.g["day_counter"] = 0
    context.g["entry_prices"] = {}


def live_factor_handle(context):
    """
    每日执行（改进版）:
    1. 止损检查
    2. 调仓日: 动量排序 → 绝对动量过滤 → 大盘择时 → 换仓
    """
    context.g["day_counter"] += 1
    date_str = context.current_dt.strftime("%Y-%m-%d")
    pool = context.g["pool"]
    positions = context.get_account_positions()

    # ── 止损 ──
    for code in list(positions.keys()):
        pos = positions[code]
        cost = pos.get("cost_price", 0)
        last = pos.get("last_price", 0)
        if cost > 0 and last > 0:
            pnl = last / cost - 1
            if pnl <= context.g["stop_loss"]:
                print(f"[止损] {date_str} {code} {pnl*100:.1f}% → 清仓")
                context.order_target_percent(code, 0)
                context.g["entry_prices"].pop(code, None)

    # ── 非调仓日跳过 ──
    if context.g["day_counter"] % context.g["rebalance_freq"] != 0:
        return

    print(f"\n[调仓] {date_str} {'='*40}")

    # ── 计算动量 ──
    window = context.g["momentum_window"]
    data = context.history(pool, fields=["close"], bar_count=window + 1)

    scores = {}
    for code in pool:
        if code not in data or len(data[code]) < window:
            continue
        old_close = float(data[code][0]["close"])
        new_close = float(data[code][-1]["close"])
        if old_close > 0:
            scores[code] = (new_close - old_close) / old_close

    if not scores:
        return

    # ── 大盘择时: 至少一半股票动量为正才开仓 ──
    positive_count = sum(1 for v in scores.values() if v > 0)
    total_count = len(scores)
    market_ok = positive_count >= total_count / 2

    if not market_ok:
        print(f"  [大盘择时] 上涨股 {positive_count}/{total_count} (< 50%) → 空仓避险")
        for code in list(positions.keys()):
            print(f"  [卖出] {code}")
            context.order_target_percent(code, 0)
        return

    # ── 绝对动量过滤: 只保留动量为正的股票 ──
    filtered = {code: s for code, s in scores.items() if s > 0}
    if not filtered:
        print(f"  [过滤] 无正动量股票 → 空仓")
        for code in list(positions.keys()):
            context.order_target_percent(code, 0)
        return

    ranked = sorted(filtered.items(), key=lambda x: x[1], reverse=True)
    target = set(code for code, _ in ranked[:context.g["top_n"]])

    for i, (code, score) in enumerate(ranked):
        tag = " ★" if code in target else ""
        print(f"  {i+1}. {code}  {score*100:+.2f}%{tag}")

    # 卖出不在目标的
    for code in list(positions.keys()):
        if code not in target:
            print(f"  [卖出] {code}")
            context.order_target_percent(code, 0)

    # 等权重买入
    if target:
        weight = 0.95 / len(target)
        for code in target:
            price = context.get_price(code)
            if price and price > 0:
                context.g["entry_prices"][code] = price
            context.order_target_percent(code, weight)


if __name__ == "__main__":
    # 直接运行本文件时，测试定投策略
    quick_test("dca")

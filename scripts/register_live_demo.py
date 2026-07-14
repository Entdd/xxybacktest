"""
注册真实数据演示策略并运行回测
"""
import sys, os

STOCKS = ["000858.SZ", "300750.SZ", "600036.SH", "601318.SH",
          "600900.SH", "000333.SZ", "002415.SZ"]  # 仅用于打印，不在策略函数中引用

def initialize(context):
    context.g.setdefault("day_count", 0)
    # 把股票列表写在函数内部，因为 exec() 加载时看不到外部变量
    context.universe = ["000858.SZ", "300750.SZ", "600036.SH", "601318.SH",
                        "600900.SH", "000333.SZ", "002415.SZ"]

def handle_data(context):
    context.g["day_count"] += 1
    # 每 22 个交易日调仓一次（约每月）
    if context.g["day_count"] % 22 != 1:
        return
    stocks = ["000858.SZ", "300750.SZ", "600036.SH", "601318.SH",
              "600900.SH", "000333.SZ", "002415.SZ"]
    n = len(stocks)
    for code in stocks:
        context.order_target_percent(code, 1.0 / n)

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")

    from xxybacktest.simulation import submit, run_single, list_accounts
    import shutil

    # 清理旧数据
    sim_dir = os.path.join("data", "simulation_results")
    if os.path.exists(sim_dir):
        shutil.rmtree(sim_dir)
        os.makedirs(sim_dir, exist_ok=True)

    print("=" * 60)
    print("注册演示策略")
    print("=" * 60)
    print(f"股票池: {', '.join(STOCKS)}")
    print(f"策略: 每月等权调仓，初始资金 10 万")
    print()

    # 提交
    account_id = submit(
        name="等权持有7只蓝筹",
        initialize=initialize,
        handle_data=handle_data,
        capital=100000,
        start_date="2024-01-01",
        data_path="./data",
        asset_type="stock",
        benchmark="000001.SH",
        run_now=False,
    )
    print(f"账户创建: {account_id}")

    # 跑回测
    print("\n正在运行回测...")
    result = run_single(account_id, data_path="./data")
    print(f"状态: {result['status']}")
    if result["status"] == "success":
        print(f"  最终净值: {result.get('final_nav', 'N/A')}")
        print(f"  累计收益: {result.get('total_return', 'N/A')}")
        print(f"  最大回撤: {result.get('max_drawdown', 'N/A')}")
    else:
        print(f"  原因: {result.get('reason', 'N/A')}")

    # 验证
    print(f"\n当前账户数: {len(list_accounts(data_path='./data'))}")
    print("完成!")

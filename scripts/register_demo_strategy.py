"""
注册演示策略并运行回测
"""
from xxybacktest.simulation import submit, run_single, list_accounts

# 1. 注册一个简单策略：每月初等权买入茅台+平安银行+五粮液
def initialize(context):
    context.g.setdefault('day_count', 0)
    context.universe = ["600519.SH", "000001.SZ", "000858.SZ"]

def handle_data(context):
    context.g['day_count'] += 1
    # 每 22 个交易日调仓一次（约一个月）
    if context.g['day_count'] % 22 != 1:
        return
    # 三只股票各买 1/3
    for code in context.universe:
        context.order_target_percent(code, 1.0 / 3)

account_id = submit(
    name="均配三只股票",
    initialize=initialize,
    handle_data=handle_data,
    capital=100000,
    start_date="2024-01-01",
    data_path="./data",
    asset_type="stock",
    benchmark="000001.SH",
    run_now=False,  # 先不跑，手动触发
)

print(f"策略注册成功: {account_id}")

# 2. 手动运行回测
result = run_single(account_id, data_path="./data")
print(f"回测结果: {result['status']}")
if result['status'] == 'success':
    print(f"  交易天数: {result['days']}")
    print(f"  最终净值: {result.get('final_nav', 'N/A')}")

# 3. 列出所有账户
accounts = list_accounts(data_path="./data")
print(f"\n当前账户数: {len(accounts)}")
for a in accounts:
    print(f"  {a['account_id'][:20]}... | {a['name']} | {a['status']}")

"""
================================================================================
data_providers —— A股全栈数据工具包（源自 a-stock-data V3.4.0）
================================================================================

十层数据架构，43 个端点（40 主端点 + 3 官方备胎），15 个数据源。
覆盖：行情 / 研报 / 信号 / 资金面 / 新闻 / 财务 / 公告 / 打板 / ETF期权 / 舆情互动

用法:
    from xxybacktest.data_providers import tencent_quote, cls_telegraph
    from xxybacktest.data_providers import em_zt_pool, full_valuation

依赖: pip install mootdx stockstats (可选，mootdx 不上也能用腾讯/东财系)
================================================================================
"""
# ── 共享基础设施 ──
from .core import (
    tdx_client, get_prefix, em_get, eastmoney_datacenter, set_em_interval,
)

# ── Layer 1: 行情层 ──
from .market import (
    tencent_quote, baidu_kline_with_ma,
    tdx_bars, tdx_quotes, tdx_transaction, tdx_finance, tdx_f10,
)

# ── Layer 2: 研报层 ──
from .research import (
    eastmoney_reports, eastmoney_industry_reports, download_pdf,
    ths_eps_forecast,
    iwencai_search, iwencai_query, dedup_articles,
)

# ── Layer 3: 信号层 ──
from .signals import (
    ths_hot_reason,
    hsgt_realtime, _save_northbound_snapshot, _load_northbound_history,
    eastmoney_concept_blocks,
    eastmoney_fund_flow_minute,
    dragon_tiger_board, daily_dragon_tiger,
    lockup_expiry,
    industry_comparison,
)

# ── Layer 4: 资金面 / 筹码层 ──
from .capital_flow import (
    margin_trading, block_trade, holder_num_change,
    dividend_history, stock_fund_flow_120d,
)

# ── Layer 5: 新闻层 ──
from .news import (
    eastmoney_stock_news, cls_telegraph, eastmoney_global_news,
)

# ── Layer 6+7: 基础数据 + 公告层 ──
from .fundamentals import (
    eastmoney_stock_info, sina_financial_report,
    cninfo_announcements,
)

# ── Layer 8: 打板层 ──
from .limit_pools import (
    em_zt_pool, em_zb_pool, em_dt_pool, em_yzt_pool,
    ths_limit_up_pool, limit_up_sentiment,
)

# ── Layer 9: ETF 期权层 ──
from .etf_options import (
    sina_option_codes, sina_option_tquote, sina_option_greeks,
)

# ── Layer 10: 舆情互动层 ──
from .sentiment import (
    cninfo_irm, ths_hot_list, em_hot_rank, em_hot_concept,
)

# ── 估值公式 ──
from .valuation import (
    forward_pe, pe_digestion, calc_peg, full_valuation,
)

# ── 备用源 ──
from .backups import (
    dragon_tiger_backup, fund_flow_backup, announcements_backup,
)

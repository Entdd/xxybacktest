"""
================================================================================
agents —— LLM Agent 辅助投研模块
================================================================================
提供三个 Agent，辅助量化投研工作流：

  ① FactorMiningAgent —— 自然语言 → 因子 SQL
      from xxybacktest.agents import FactorMiningAgent
      agent = FactorMiningAgent(api_key="sk-xxx")
      sql = agent.mine("计算5日动量因子")

  ② NewsSentimentAgent —— 新闻情绪 → 因子值 (date/instrument/value)
      from xxybacktest.agents import NewsSentimentAgent
      agent = NewsSentimentAgent(deepseek_api_key="sk-xxx", tavily_api_key="tvly-xxx")
      df = agent.analyze(news_df)  # 返回因子格式 DataFrame

  ③ AlphaLens Bridge —— FactorResult ↔ AlphaLens 格式转换
      from xxybacktest.agents import factor_to_alphalens, alphalens_tear_sheet
      alphalens_tear_sheet(factor_result)

依赖方向: agents → factor（单向），不反向依赖。
API key 通过初始化参数传入，不硬编码。
================================================================================
"""
from .factor_mining.agent import FactorMiningAgent
from .news_sentiment.agent import NewsSentimentAgent
from .alphalens_bridge.bridge import (
    factor_to_alphalens,
    alphalens_tear_sheet,
    ALPHALENS_AVAILABLE,
)

__all__ = [
    "FactorMiningAgent",
    "NewsSentimentAgent",
    "factor_to_alphalens",
    "alphalens_tear_sheet",
    "ALPHALENS_AVAILABLE",
]

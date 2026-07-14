"""
================================================================================
test_agent_news_sentiment —— 新闻情绪 Agent 测试
================================================================================
"""
import pytest
import pandas as pd
from datetime import datetime

from xxybacktest.agents.news_sentiment.agent import (
    _split_news_securities,
    _news_to_query,
    _dict_to_factor_df,
    NewsSentimentAgent,
)
from xxybacktest.agents.news_sentiment.prompts import build_prompt


class TestSplitNewsSecurities:
    """测试新闻标的分割函数。"""

    def test_single_instrument(self):
        df = pd.DataFrame([{
            "title": "测试新闻",
            "publish_time": "2023-07-01 10:00:00",
            "source": "新华社",
            "related_instruments": "000001.SZ",
        }])
        result = _split_news_securities(df)
        assert len(result) == 1
        assert result.iloc[0]["title"] == "测试新闻"

    def test_multiple_instruments_split(self):
        df = pd.DataFrame([{
            "title": "行业新闻",
            "publish_time": "2023-07-01 10:00:00",
            "source": "新华社",
            "related_instruments": "000001.SZ,600519.SH,000002.SZ",
        }])
        result = _split_news_securities(df)
        assert len(result) == 3
        assert result.iloc[0]["related_instruments"] == "000001.SZ"
        assert result.iloc[1]["related_instruments"] == "600519.SH"
        assert result.iloc[2]["related_instruments"] == "000002.SZ"

    def test_multiple_rows(self):
        df = pd.DataFrame([
            {"title": "新闻A", "publish_time": "2023-07-01", "source": "源A", "related_instruments": "000001.SZ"},
            {"title": "新闻B", "publish_time": "2023-07-02", "source": "源B", "related_instruments": "600519.SH"},
        ])
        result = _split_news_securities(df)
        assert len(result) == 2


class TestNewsToQuery:
    """测试 DataFrame → 查询字典转换。"""

    def test_basic_conversion(self):
        df = pd.DataFrame([{
            "title": "某公司业绩超预期",
            "publish_time": datetime(2023, 7, 1, 10, 0, 0),
            "source": "财联社",
            "related_instruments": "000001.SZ",
        }])
        query = _news_to_query(df)
        assert "000001.SZ" in query
        assert len(query["000001.SZ"]) == 1
        assert "业绩超预期" in query["000001.SZ"][0]
        assert "财联社" in query["000001.SZ"][0]
        assert "2023-07-01" in query["000001.SZ"][0]

    def test_multi_instrument_query(self):
        df = pd.DataFrame([{
            "title": "行业利好",
            "publish_time": datetime(2023, 7, 1),
            "source": "快兰斯",
            "related_instruments": "000001.SZ,600519.SH",
        }])
        query = _news_to_query(df)
        assert "000001.SZ" in query
        assert "600519.SH" in query


class TestDictToFactorDf:
    """测试 LLM 返回字典 → DataFrame 转换。"""

    def test_basic_conversion(self):
        data = {
            "600519.SH": {
                "respone": {
                    "date": "2023-07-01",
                    "value": 1,
                    "reason": "业绩超预期, 利好",
                }
            },
            "000001.SZ": {
                "respone": {
                    "date": "2023-07-02",
                    "value": -1,
                    "reason": "监管处罚, 利空",
                }
            },
        }
        df = _dict_to_factor_df(data)
        assert len(df) == 2
        assert list(df.columns) == ["date", "instrument", "value", "reason"]
        assert df.iloc[0]["instrument"] == "600519.SH"
        assert df.iloc[0]["value"] == 1
        assert df.iloc[1]["instrument"] == "000001.SZ"
        assert df.iloc[1]["value"] == -1

    def test_with_search_content_key_ignored(self):
        data = {
            "search_content": "some search content",
            "000001.SZ": {"respone": {"date": "2023-07-01", "value": 0, "reason": "中性"}},
        }
        df = _dict_to_factor_df(data)
        assert len(df) == 1
        assert df.iloc[0]["instrument"] == "000001.SZ"

    def test_empty_data(self):
        df = _dict_to_factor_df({"search_content": "无"})
        assert df.empty


class TestPrompts:
    """测试提示词生成。"""

    def test_build_prompt(self):
        query = {"000001.SZ": ["新闻1"]}
        scratch = {"search_content": "无"}
        prompt = build_prompt(query, agent_scratch=scratch)
        assert isinstance(prompt, str)
        assert "财经新闻分析师" in prompt
        assert "000001.SZ" in prompt

    def test_build_prompt_no_scratch(self):
        query = {"600519.SH": ["新闻"]}
        prompt = build_prompt(query)  # 不传 agent_scratch
        assert "600519.SH" in prompt
        assert "无" in prompt  # 默认值


class TestNewsSentimentAgentConfig:
    """测试 Agent 初始化。"""

    def test_init_basic(self):
        agent = NewsSentimentAgent(
            deepseek_api_key="sk-test",
            tavily_api_key="tvly-test",
        )
        assert agent.deepseek_api_key == "sk-test"
        assert agent.tavily_api_key == "tvly-test"
        assert agent.model == "deepseek-chat"

    def test_init_without_tavily(self):
        agent = NewsSentimentAgent(deepseek_api_key="sk-test")
        assert agent.tavily_api_key is None

    def test_init_custom_params(self):
        agent = NewsSentimentAgent(
            deepseek_api_key="sk-xxx",
            base_url="https://custom.api.com",
            model="deepseek-reasoner",
        )
        assert agent.model == "deepseek-reasoner"

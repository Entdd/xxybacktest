"""
================================================================================
test_agent_factor_mining —— 因子挖掘 Agent 测试
================================================================================
"""
import pytest
from xxybacktest.agents.factor_mining.tools import (
    m_avg, m_lag, m_std, m_max, m_min,
    m_delta, m_roc, m_corr, m_sum,
    sub, divide, add, multiply,
    cs_rank, cs_zscore,
    TOOL_REGISTRY, get_tool_description,
)
from xxybacktest.agents.factor_mining.agent import (
    FactorMiningAgent, _parse_action,
)
from xxybacktest.agents.factor_mining.prompts import build_prompt


class TestToolsSQL:
    """测试工具是否生成正确的 SQL 语法片段。"""

    def test_m_avg_generates_window_function(self):
        result = m_avg("close", 5)
        assert "AVG(close)" in result
        assert "PARTITION BY instrument" in result
        assert "ORDER BY date" in result
        assert "ROWS BETWEEN 4 PRECEDING" in result

    def test_m_lag_generates_lag_function(self):
        result = m_lag("close", 1)
        assert "LAG(close, 1)" in result
        assert "PARTITION BY instrument" in result

    def test_m_std(self):
        result = m_std("change_ratio", 20)
        assert "STDDEV_SAMP" in result
        assert "PARTITION BY instrument" in result

    def test_m_max_min(self):
        assert "MAX(high)" in m_max("high", 20)
        assert "MIN(low)" in m_min("low", 20)

    def test_m_delta(self):
        result = m_delta("close", 5)
        assert "LAG(close, 5)" in result
        assert result.startswith("(close -")

    def test_m_roc_safe_division(self):
        result = m_roc("close", 5)
        assert "NULLIF" in result  # 安全除零
        assert "LAG(close, 5)" in result

    def test_m_corr(self):
        result = m_corr("close", "volume", 20)
        assert "CORR(close, volume)" in result

    def test_m_sum(self):
        result = m_sum("volume", 5)
        assert "SUM(volume)" in result

    def test_sub_and_divide(self):
        result = sub("a", "b")
        assert result == "(a - (b))"

        result = divide("a", "b")
        assert "NULLIF(b, 0)" in result

    def test_add_and_multiply(self):
        assert add("a", "b") == "(a + (b))"
        assert multiply("a", "b") == "((a) * (b))"

    def test_cs_rank(self):
        result = cs_rank("close")
        assert "RANK()" in result
        assert "PARTITION BY date" in result

    def test_cs_zscore(self):
        result = cs_zscore("close")
        assert "AVG" in result
        assert "STDDEV_SAMP" in result
        assert "PARTITION BY date" in result

    def test_nested_tools_combine(self):
        """模拟工具嵌套: 5日动量 = (close - LAG(close,5)) / LAG(close,5)"""
        lag_close = m_lag("close", 5)
        delta = sub("close", lag_close)
        momentum = divide(delta, m_lag("close", 5))
        assert "close" in momentum
        assert "LAG(close, 5)" in momentum
        assert "NULLIF" in momentum

    def test_rolling_zscore_combine(self):
        """模拟: 20日滚动标准化动量 = (动量 - AVG(动量,20)) / STD(动量,20)"""
        momentum = m_roc("close", 5)
        avg_mom = m_avg(momentum, 20)
        std_mom = m_std(momentum, 20)
        zscore = divide(sub(momentum, avg_mom), std_mom)
        assert "AVG" in zscore
        assert "STDDEV_SAMP" in zscore
        assert "NULLIF" in zscore


class TestToolRegistry:
    """测试工具注册表的完整性。"""

    def test_all_tools_have_required_keys(self):
        for name, info in TOOL_REGISTRY.items():
            assert "func" in info, f"{name}: 缺少 func"
            assert "description" in info, f"{name}: 缺少 description"
            assert "args" in info, f"{name}: 缺少 args"
            assert callable(info["func"]), f"{name}: func 不可调用"

    def test_get_tool_description(self):
        desc = get_tool_description()
        assert "m_avg" in desc
        assert "m_lag" in desc
        assert "cs_rank" in desc
        assert "sub" in desc
        assert "divide" in desc

    def test_tool_count(self):
        """确认有 15 个工具。"""
        assert len(TOOL_REGISTRY) == 15


class TestPrompts:
    """测试提示词生成。"""

    def test_build_prompt_returns_tuple(self):
        system, user = build_prompt("计算5日动量因子")
        assert isinstance(system, str)
        assert isinstance(user, str)
        assert len(system) > 0
        assert "量化投研" in system

    def test_user_prompt_contains_query(self):
        _, user = build_prompt("20日波动率因子")
        assert "20日波动率因子" in user

    def test_history_chat_in_prompt(self):
        _, user = build_prompt("因子", history_chat="第1轮: 使用了 m_lag")
        assert "第1轮" in user


class TestParseAction:
    """测试 LLM 输出解析。"""

    def test_parse_action_basic(self):
        result = """Thoughts: 需要先计算滞后价格
Action: m_lag
Action_input: {"expr": "close", "N": 5}
Observation: SQL 片段: ..."""
        name, params = _parse_action(result)
        assert name == "m_lag"
        assert params == {"expr": "close", "N": 5}

    def test_parse_action_json_format(self):
        result = '''Thoughts: 计算移动平均
Action: m_avg
Action_input: {"expr": "close", "N": 20}
Observation: SQL 片段'''
        name, params = _parse_action(result)
        assert name == "m_avg"
        assert params == {"expr": "close", "N": 20}


class TestFactorMiningAgentConfig:
    """测试 Agent 初始化 (不实际调用 API)。"""

    def test_init(self):
        agent = FactorMiningAgent(api_key="sk-test-key")
        assert agent.api_key == "sk-test-key"
        assert agent.model == "deepseek-chat"
        assert agent.base_url == "https://api.deepseek.com"

    def test_init_custom_params(self):
        agent = FactorMiningAgent(
            api_key="sk-xxx",
            base_url="https://custom.api.com",
            model="deepseek-reasoner",
        )
        assert agent.base_url == "https://custom.api.com"
        assert agent.model == "deepseek-reasoner"

    def test_validate_sql_valid(self):
        sql = "SELECT date, instrument, close/pre_close-1 AS value FROM daily_bar"
        FactorMiningAgent._validate_sql(sql)  # 不抛异常

    def test_validate_sql_missing_date(self):
        sql = "SELECT instrument, close AS value FROM daily_bar"
        with pytest.raises(ValueError, match="date"):
            FactorMiningAgent._validate_sql(sql)

    def test_validate_sql_missing_instrument(self):
        sql = "SELECT date, close AS value FROM daily_bar"
        with pytest.raises(ValueError, match="instrument"):
            FactorMiningAgent._validate_sql(sql)

    def test_validate_sql_missing_value(self):
        sql = "SELECT date, instrument, close FROM daily_bar"
        with pytest.raises(ValueError, match="value"):
            FactorMiningAgent._validate_sql(sql)

    def test_validate_sql_missing_from_daily_bar(self):
        sql = "SELECT date, instrument, 1 AS value FROM other_table"
        with pytest.raises(ValueError, match="daily_bar"):
            FactorMiningAgent._validate_sql(sql)

    def test_extract_final_answer_basic(self):
        result = """Thoughts: 完成
Final_answer: SELECT date, instrument, close - LAG(close,1) OVER (...) AS value FROM daily_bar"""
        sql = FactorMiningAgent._extract_final_answer(result)
        assert sql.startswith("SELECT")
        assert "daily_bar" in sql
        assert "value" in sql

    def test_extract_final_answer_with_code_block(self):
        result = """Final_answer: ```sql
SELECT date, instrument, close AS value FROM daily_bar
```"""
        sql = FactorMiningAgent._extract_final_answer(result)
        assert "```" not in sql
        assert "SELECT date, instrument" in sql

"""
================================================================================
test_agent_alphalens_bridge —— AlphaLens Bridge 测试
================================================================================
"""
import pytest
import pandas as pd
import numpy as np

from xxybacktest.agents.alphalens_bridge.bridge import (
    ALPHALENS_AVAILABLE,
    factor_to_alphalens,
)


class TestAlphalensAvailability:
    """测试 alphalens 可用性检测。"""

    def test_alphalens_flag_is_bool(self):
        assert isinstance(ALPHALENS_AVAILABLE, bool)


class TestFactorToAlphalens:
    """测试格式转换。"""

    @pytest.fixture
    def mock_result_dict(self):
        """构造一个模拟的引擎输出 dict (模拟 FactorResult 的内部数据)。"""
        dates = pd.date_range("2023-01-03", "2023-01-10", freq="B")
        instruments = ["000001.SZ", "600519.SH", "000002.SZ"]
        np.random.seed(42)

        rows = []
        for d in dates:
            for ins in instruments:
                rows.append({
                    "date": d,
                    "instrument": ins,
                    "group": np.random.randint(1, 11),
                    "ret_1": np.random.normal(0.001, 0.02),
                    "ret_5": np.random.normal(0.005, 0.04),
                    "ret_10": np.random.normal(0.01, 0.06),
                })
        return {"groups": pd.DataFrame(rows)}

    def test_basic_conversion(self, mock_result_dict):
        factor_data, prices = factor_to_alphalens(mock_result_dict)
        assert factor_data is not None
        assert "factor" in factor_data.columns
        assert factor_data.index.names == ["date", "asset"]

    def test_output_is_multiindex(self, mock_result_dict):
        factor_data, _ = factor_to_alphalens(mock_result_dict)
        assert isinstance(factor_data.index, pd.MultiIndex)
        assert factor_data.index.nlevels == 2

    def test_contains_forward_returns(self, mock_result_dict):
        factor_data, _ = factor_to_alphalens(mock_result_dict)
        # 应该有 ret 列
        ret_cols = [c for c in factor_data.columns if c.startswith("ret_")]
        assert len(ret_cols) > 0

    def test_factor_values_are_group_numbers(self, mock_result_dict):
        factor_data, _ = factor_to_alphalens(mock_result_dict)
        # group 编号在 1-10 之间
        assert factor_data["factor"].between(1, 10).all()

    def test_empty_groups_raises(self):
        with pytest.raises(ValueError):
            factor_to_alphalens({"groups": pd.DataFrame()})

    def test_no_groups_raises(self):
        with pytest.raises(ValueError):
            factor_to_alphalens({"wrong_key": None})

    def test_none_groups_raises(self):
        with pytest.raises(ValueError):
            factor_to_alphalens({"groups": None})

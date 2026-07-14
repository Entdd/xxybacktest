"""
================================================================================
factor_mining/agent —— FactorMiningAgent (ReAct 循环)
================================================================================
将自然语言因子描述转化为可执行的完整 SQL。

用法:
    agent = FactorMiningAgent(api_key="sk-xxx")
    sql = agent.mine("计算5日动量因子")
    # 返回: SELECT date, instrument, (close - LAG(close,5)...)/...AS value FROM daily_bar

    可直接将结果传给因子分析系统:
    from xxybacktest.factor import analyze_factor
    res = analyze_factor(sql=sql, data_path="./data")
    res.summary()
================================================================================
"""
import re
import json

from .tools import TOOL_REGISTRY
from .prompts import build_prompt


def _parse_action(result: str) -> tuple:
    """从 LLM 输出中提取 Action 和 Action_input。"""
    # 提取 Action
    action_match = re.search(
        r"Action:\s*(.+?)(?=\n\s*(?:Action_input:|Observation:|Thoughts:|Final_answer:)|$)",
        result, re.DOTALL | re.IGNORECASE,
    )
    action_name = action_match.group(1).strip() if action_match else None

    # 提取 Action_input
    input_match = re.search(
        r"Action_input:\s*(.+?)(?=\n\s*(?:Observation:|Thoughts:|Action:|$)|$)",
        result, re.DOTALL | re.IGNORECASE,
    )
    if input_match:
        raw = input_match.group(1).strip()
        try:
            # 尝试解析为 JSON/dict
            # 先尝试 JSON 格式
            action_params = json.loads(raw)
        except json.JSONDecodeError:
            try:
                # 再尝试 Python dict 字面量
                action_params = eval(raw)
            except Exception:
                action_params = raw
    else:
        action_params = None

    return action_name, action_params


class FactorMiningAgent:
    """基于 ReAct 提示词工程的因子挖掘 Agent。

    通过 DeepSeek API 驱动 LLM 逐步推理, 组合 SQL 工具生成完整的因子表达式。

    参数:
        api_key:  DeepSeek API key
        base_url: API 地址, 默认 https://api.deepseek.com
        model:    模型名, 默认 deepseek-chat
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self._client = None  # lazy init on first API call

    def _get_client(self):
        """延迟初始化 OpenAI client (避免 openai 未安装时导入报错)。"""
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def mine(self, description: str, max_iterations: int = 10) -> str:
        """输入因子自然语言描述, 返回可直接提交的完整 SQL。

        参数:
            description:    因子的自然语言描述, 如 "20日动量: 当日收盘除以20日前收盘减1"
            max_iterations: 最大推理轮次, 默认 10

        返回:
            完整的 SQL 字符串, 形如:
            SELECT date, instrument, <表达式> AS value FROM daily_bar

        异常:
            RuntimeError: 达到最大迭代次数仍未得到 Final_answer
            ValueError:   返回的 SQL 不包含 date/instrument/value
        """
        system_prompt, _ = build_prompt(description)
        history_chat = "暂无推理记录"

        client = self._get_client()

        for step in range(1, max_iterations + 1):
            # 每轮重建 user_prompt，把最新历史嵌入
            _, user_prompt = build_prompt(description, history_chat=history_chat)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=False,
            )
            result = response.choices[0].message.content

            # 检查是否完成
            if "Final_answer" in result or "final_answer" in result.lower():
                final_sql = self._extract_final_answer(result)
                self._validate_sql(final_sql)
                return final_sql

            # 解析 Action
            action_name, action_params = self._parse_action_with_fallback(result)

            if action_name is None:
                # LLM 没输出有效 Action → 把原始输出当 observation 继续
                history_chat += (
                    f"\n\n{result}\n"
                    f"Observation: 未检测到有效的 Action 格式。"
                    f"请严格按照 Action: <工具名> 和 Action_input: <参数> 的格式输出。"
                )
                continue

            # 执行工具
            observation = self._execute_tool(action_name, action_params)

            # 更新历史 (LLM 输出 + 工具返回的 SQL 片段)
            if "Observation:" in result:
                updated_result = re.sub(
                    r"(Observation:\s*)(.*?)(?=\n|$)",
                    r"\1" + observation,
                    result,
                    flags=re.DOTALL,
                )
            else:
                updated_result = result + f"\nObservation: {observation}"

            history_chat += f"\n\n--- 第 {step} 轮 ---\n{updated_result}"

        raise RuntimeError(
            f"在 {max_iterations} 轮内未得到 Final_answer。"
            f"请尝试简化因子描述或增加 max_iterations。"
        )

    def _parse_action_with_fallback(self, result: str) -> tuple:
        """解析 Action, 带友好错误处理。"""
        action_name, action_params = _parse_action(result)
        if action_name is None:
            return None, None
        # 清理 action_name (去掉可能的引号、空格)
        action_name = action_name.strip().strip("'").strip('"')
        return action_name, action_params

    def _execute_tool(self, action_name: str, action_params) -> str:
        """执行工具并返回 SQL 片段作为 observation。"""
        if action_name not in TOOL_REGISTRY:
            available = ", ".join(TOOL_REGISTRY.keys())
            return (
                f"错误: 工具 '{action_name}' 不存在。"
                f"可用工具: {available}"
            )

        tool_info = TOOL_REGISTRY[action_name]
        func = tool_info["func"]

        try:
            if isinstance(action_params, dict):
                result = func(**action_params)
            elif isinstance(action_params, (list, tuple)):
                result = func(*action_params)
            else:
                result = func(action_params)
        except Exception as e:
            return f"工具执行错误: {e}"

        return f"SQL 片段: {result}"

    @staticmethod
    def _extract_final_answer(result: str) -> str:
        """从 LLM 输出中提取 Final_answer 后面的 SQL。"""
        # 匹配 Final_answer: 之后的内容 (到文本结束)
        match = re.search(
            r"Final_answer:\s*(.+)$",
            result, re.DOTALL | re.IGNORECASE,
        )
        if not match:
            raise ValueError(f"无法从 LLM 输出中提取 Final_answer: {result[:200]}...")

        sql = match.group(1).strip()
        # 去掉可能的 markdown 代码块标记
        sql = re.sub(r"^```(?:sql)?\s*\n?", "", sql)
        sql = re.sub(r"\n?\s*```$", "", sql)
        # 去掉加粗标记 **
        sql = sql.strip("*").strip()
        return sql

    @staticmethod
    def _validate_sql(sql: str) -> None:
        """基本检查: SQL 必须包含 date/instrument/value 和 FROM daily_bar。
        同时检查不包含 Python 工具函数名 (表示 LLM 没正确展开工具输出)。"""
        sql_upper = sql.upper()
        if "DATE" not in sql_upper:
            raise ValueError(f"因子 SQL 必须包含 date 列。SQL: {sql[:100]}")
        if "INSTRUMENT" not in sql_upper:
            raise ValueError(f"因子 SQL 必须包含 instrument 列。SQL: {sql[:100]}")
        if "VALUE" not in sql_upper:
            raise ValueError(f"因子 SQL 必须包含 AS value。SQL: {sql[:100]}")
        if "DAILY_BAR" not in sql_upper:
            raise ValueError(f"因子 SQL 必须 FROM daily_bar。SQL: {sql[:100]}")

        # 禁止包含工具函数名 (LLM 有时把 Python 函数名写进 SQL)
        _forbidden = ["divide(", "sub(", "add(", "multiply(",
                      "m_avg(", "m_lag(", "m_std(", "m_max(", "m_min(",
                      "m_delta(", "m_roc(", "m_corr(", "m_sum(",
                      "cs_rank(", "cs_zscore("]
        for fn in _forbidden:
            if fn in sql.lower():
                raise ValueError(
                    f"因子 SQL 中包含工具函数名 '{fn}'。"
                    f"Final_answer 必须是纯 SQL, 不能包含 Python 函数调用。"
                    f"请把工具返回的 SQL 片段直接代入表达式。"
                    f"当前 SQL: {sql[:200]}")


def mine_factor(api_key: str, description: str, **kwargs) -> str:
    """便捷函数: 一行调用因子挖掘。"""
    agent = FactorMiningAgent(api_key=api_key)
    return agent.mine(description, **kwargs)

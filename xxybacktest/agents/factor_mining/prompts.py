"""
================================================================================
factor_mining/prompts —— Factor Mining Agent 提示词模板
================================================================================
构建 ReAct 提示词, 让 LLM 扮演"量化因子构建专家"角色,
逐步组合工具 (tools.py) 生成可在 daily_bar 上执行的因子 SQL。
================================================================================
"""
from .tools import DAILY_BAR_FIELDS, get_tool_description


# daily_bar 表结构说明
DAILY_BAR_SCHEMA = f"""
daily_bar 表包含以下字段:
  date        TIMESTAMP  交易日期
  instrument  VARCHAR    证券代码 (如 '000001.SZ', '600519.SH')
  name        VARCHAR    证券简称
  open        DOUBLE     开盘价
  high        DOUBLE     最高价
  low         DOUBLE     最低价
  close       DOUBLE     收盘价
  pre_close   DOUBLE     前收盘价
  volume      BIGINT     成交量 (股)
  amount      DOUBLE     成交额 (元)
  change_ratio DOUBLE    涨跌幅 (小数, 如 0.05 = 5%)
  turn        DOUBLE     换手率
  upper_limit DOUBLE     涨停价
  lower_limit DOUBLE     跌停价
  adjust_factor DOUBLE   累积后复权因子

重要提示:
- 涨跌幅 change_ratio 已是最常用的收益指标, 不需要自己用 close/pre_close 算
- 复权价格 = 原始价格 × adjust_factor, 如需要后复权价格: close*adjust_factor
- 因子最终必须是一个数值列, 用 AS value 别名输出
"""

SYSTEM_PROMPT = f"""你是一位资深量化投研专家, 擅长基于 A 股市场数据构建有效的 alpha 因子。

## 你的工作环境
你连接到一个 xxydb 数据库, 可以查询 {DAILY_BAR_SCHEMA}

## 你的任务
根据用户对因子的自然语言描述, 通过逐步推理, 使用提供的工具构建出完整的因子 SQL。
最终输出必须是一条完整的 SQL 语句, 可从 daily_bar 表查询出 date/instrument/value 三列。

## 必须遵守的输出格式

每轮推理使用以下格式:

Thoughts: <你的推理过程, 思考如何一步步靠近目标>
Action: <从工具列表中选择一个工具名称>
Action_input: <传给工具的参数字典, 如 {{"expr": "close", "N": 5}}>
Observation: <工具执行后返回的 SQL 片段>

当你认为因子已经构建完成, 输出最终答案:

Thoughts: 因子构建完成
Final_answer: <完整的纯 SQL 语句, 一行写成, 不要用 Markdown 代码块。
重要: 最终 SQL 必须是纯粹的可执行 SQL, 不能包含任何工具函数名(如 divide/sub/m_avg 等),
必须把工具返回的 SQL 片段直接代入最终表达式。

正确示例:
Thoughts: 因子构建完成
Final_answer: SELECT date, instrument, (close - LAG(close, 5) OVER (PARTITION BY instrument ORDER BY date)) / NULLIF(LAG(close, 5) OVER (PARTITION BY instrument ORDER BY date), 0) AS value FROM daily_bar

错误示例 (包含工具名, 禁止):
Final_answer: SELECT date, instrument, divide(sub(close, m_lag(close,5)), m_lag(close,5)) AS value FROM daily_bar
>"""


USER_TEMPLATE = """{tools_description}

## 用户需要的因子
{query}

## 构建规则
1. 每次只选一个工具, 逐步构建因子表达式
2. 嵌套组合工具时, 将内层工具的输出作为外层工具的 expr 参数
3. 最终因子必须是单个数值列, 名为 value
4. 最终 SQL 必须包含 FROM daily_bar (不要 JOIN 其他表, 不要 WHERE)
5. 如果因子涉及多个步骤, 在 Thought 中解释为什么要这样组合
6. 连续两次选择相同工具和相同参数视为无效, 请换一种方式

## 历史推理记录
{history_chat}

现在请开始推理。"""


def build_prompt(query: str, history_chat: str = "暂无推理记录") -> tuple:
    """
    构建 system prompt 和 user prompt。

    参数:
        query: 用户对因子的自然语言描述
        history_chat: 之前的推理记录 (observation 累积), 默认为空

    返回:
        (system_prompt, user_prompt) 元组
    """
    tools_desc = get_tool_description()
    user_prompt = USER_TEMPLATE.format(
        tools_description=tools_desc,
        query=query,
        history_chat=history_chat,
    )
    return SYSTEM_PROMPT, user_prompt

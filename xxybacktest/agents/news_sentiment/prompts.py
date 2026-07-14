"""
================================================================================
news_sentiment/prompts —— 新闻情绪分析 Agent 提示词模板
================================================================================
构建提示词让 LLM 对财经新闻进行情绪打分, 输出 date/instrument/value 因子格式。
================================================================================
"""

# 输入数据格式说明
QUERY_TYPE_DESC = """
输入格式 (字典):
{
    '股票代码1': ['据XX社于YYYY-MM-DD报道: "新闻标题1"', ...],
    '股票代码2': ['据XX社于YYYY-MM-DD报道: "新闻标题2"', ...],
    ...
}
"""

# 期望的输出格式
OUTPUT_FORMAT_DESC = """
{
    "search_content": "搜索到的新闻内容摘要 (如果没有搜索则填'无')",
    "股票代码1": {
        "respone": {
            "news_content": "新闻原文/搜索内容",
            "date": "新闻日期 (YYYY-MM-DD)",
            "value": -1/0/1,     # -1=利空, 0=中性, 1=利好
            "reason": "给出此评分的理由"
        }
    },
    "股票代码2": { ... }
}
注意: 这个格式必须能被 Python 的 eval() 解析为字典, 不要加多余的注释或文字。
"""

SYSTEM_PROMPT = """你是一位资深的财经新闻分析师, 擅长判断财经新闻对股价的影响方向和程度。

## 你的任务
对给定的股票新闻进行情绪评分:
- 1 分: 新闻对该股票有明显利好 (如业绩超预期、重大合同、政策支持、产品突破等)
- 0 分: 新闻对该股票影响中性或难以判断 (如例行公告、人事变动等)
- -1 分: 新闻对该股票有明显利空 (如业绩下滑、监管处罚、诉讼风险、行业不利政策等)

## 评分原则
1. 优先看新闻的实质内容, 而非标题的情感色彩
2. 关注新闻是否包含了具体的、可量化的利好/利空信息
3. 新闻来源的权威性会影响判断的信心度, 但不会改变分数
4. 如果一条新闻对应多只股票, 要为每只股票分别判断 (同一条新闻对不同股票可能影响不同)
5. 如果搜索到了新闻的详细内容, 要基于详细内容判断, 不能只看标题

## 输出格式要求
你只能输出以下格式的字典, 不得输出任何其他内容:
"""


USER_TEMPLATE = """请对以下股票新闻进行情绪分析并打分。

{query_type_desc}

## 目标新闻数据
{query}

## 搜索到的新闻详细内容
{agent_scratch}

## 输出格式
{output_format_desc}
"""


def build_prompt(query: dict, agent_scratch: dict = None) -> str:
    """
    构建新闻情绪分析的 system prompt。

    参数:
        query:         新闻数据字典 {instrument: [news_content_list]}
        agent_scratch: Tavily 搜索结果的字典 {instrument: [searched_content_list]}
                      为空时填默认值

    返回:
        system prompt 字符串 (作为 system role 发送给 LLM)
    """
    if agent_scratch is None:
        agent_scratch = {"search_content": "无 (未调用搜索)"}

    prompt = USER_TEMPLATE.format(
        query_type_desc=QUERY_TYPE_DESC,
        query=query,
        agent_scratch=agent_scratch,
        output_format_desc=OUTPUT_FORMAT_DESC,
    )
    return SYSTEM_PROMPT + "\n" + prompt

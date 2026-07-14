"""
================================================================================
news_sentiment/agent —— NewsSentimentAgent (搜索 + LLM 评分)
================================================================================
将财经新闻数据转化为情绪因子值 (date/instrument/value), 可直接提交到因子分析系统。

用法:
    agent = NewsSentimentAgent(deepseek_api_key="sk-xxx", tavily_api_key="tvly-xxx")
    df = agent.analyze(news_df)         # 返回因子格式 DataFrame
    df = agent.score(news_df)           # 同上 (不搜索, 只用标题评分)

    可直接提交:
    fid = agent.analyze_and_submit(news_df, name="新闻情绪因子", category="舆情",
                                   data_path="./data")
================================================================================
"""
import os
import re
import pandas as pd

from .prompts import build_prompt


def _split_news_securities(df: pd.DataFrame,
                           news_col: str = "title",
                           securities_col: str = "related_instruments") -> pd.DataFrame:
    """将一条新闻对应多个标的的行拆分为多行 (每行一个标的)。"""
    other_cols = [c for c in df.columns if c not in [news_col, securities_col]]

    def split_row(row):
        securities = row[securities_col].split(",")
        return [
            (row[news_col], security.strip(), *[row[c] for c in other_cols])
            for security in securities
        ]

    exploded = df.apply(split_row, axis=1).explode()
    return pd.DataFrame(
        exploded.tolist(),
        columns=[news_col, securities_col] + other_cols,
    )


def _news_to_query(df: pd.DataFrame) -> dict:
    """将新闻 DataFrame 转化为 {instrument: [news_strings]} 字典。"""
    df = _split_news_securities(df)
    df["content"] = (
        df["source"].fillna("未知来源")
        + "于"
        + df["publish_time"].apply(
            lambda x: x.strftime("%Y-%m-%d") if hasattr(x, "strftime") else str(x)[:10]
        )
        + '发表了一篇关于: "'
        + df["title"]
        + '"的报道'
    )
    grouped = df.groupby("related_instruments")["content"].apply(list).to_dict()
    return grouped


def _dict_to_factor_df(data: dict) -> pd.DataFrame:
    """
    将 LLM 返回的评分字典转为因子格式 DataFrame (date/instrument/value/reason)。
    """
    rows = []
    for instrument, details in data.items():
        if instrument == "search_content":
            continue
        if isinstance(details, dict) and "respone" in details:
            resp = details["respone"]
            rows.append({
                "date": resp.get("date", ""),
                "instrument": instrument,
                "value": resp.get("value", resp.get("score", 0)),
                "reason": resp.get("reason", ""),
            })
        elif isinstance(details, list):
            for item in details:
                if isinstance(item, dict) and "respone" in item:
                    resp = item["respone"]
                    rows.append({
                        "date": resp.get("date", ""),
                        "instrument": instrument,
                        "value": resp.get("value", resp.get("score", 0)),
                        "reason": resp.get("reason", ""),
                    })
    return pd.DataFrame(rows, columns=["date", "instrument", "value", "reason"])


class NewsSentimentAgent:
    """财经新闻情绪分析 Agent。

    组合 Tavily 搜索 + DeepSeek LLM, 对新闻标题/内容进行情绪评分,
    输出 date/instrument/value 格式的因子数据。

    参数:
        deepseek_api_key: DeepSeek API key
        tavily_api_key:   Tavily 搜索 API key (可选, 不传则跳过搜索)
        base_url:         DeepSeek API 地址, 默认 https://api.deepseek.com
        model:            模型名, 默认 deepseek-chat
    """

    def __init__(
        self,
        deepseek_api_key: str,
        tavily_api_key: str = None,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
    ):
        self.deepseek_api_key = deepseek_api_key
        self.tavily_api_key = tavily_api_key
        self.model = model
        self.base_url = base_url
        self._client = None  # lazy init

        if tavily_api_key:
            os.environ.setdefault("TAVILY_API_KEY", tavily_api_key)

    def _get_client(self):
        """延迟初始化 OpenAI client。"""
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.deepseek_api_key, base_url=self.base_url)
        return self._client

    def score(self, news_df: pd.DataFrame, max_retries: int = 3) -> pd.DataFrame:
        """
        仅用新闻标题进行情绪评分 (不搜索新闻正文, 速度更快)。

        参数:
            news_df: 新闻 DataFrame, 须包含列:
                     title, publish_time, source, related_instruments
            max_retries: LLM 调用失败时的最大重试次数

        返回:
            DataFrame with columns: date, instrument, value, reason
        """
        return self._analyze_inner(news_df, search_first=False, max_retries=max_retries)

    def analyze(self, news_df: pd.DataFrame, max_retries: int = 3) -> pd.DataFrame:
        """
        先搜索新闻正文, 再进行情绪评分 (更准确, 但较慢)。

        参数:
            news_df: 新闻 DataFrame, 须包含列:
                     title, publish_time, source, related_instruments
            max_retries: LLM 调用失败时的最大重试次数

        返回:
            DataFrame with columns: date, instrument, value, reason
        """
        return self._analyze_inner(news_df, search_first=True, max_retries=max_retries)

    def _analyze_inner(self, news_df: pd.DataFrame, search_first: bool,
                       max_retries: int = 3) -> pd.DataFrame:
        """内部分析流程。"""
        query = _news_to_query(news_df)
        news_content = {}

        if search_first and self.tavily_api_key:
            news_content = self._search_news(query)

        prompt = build_prompt(query, agent_scratch=news_content)
        client = self._get_client()

        for attempt in range(max_retries):
            try:
                messages = [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "请为以上新闻完成情绪评分。"},
                ]
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    stream=False,
                )
                raw = response.choices[0].message.content
                # 清理可能的 markdown 标记
                raw = raw.replace("json", "").replace("```", "").strip()
                data = eval(raw)
                return _dict_to_factor_df(data)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise RuntimeError(
                        f"LLM 评分失败 ({max_retries} 次尝试): {e}"
                    ) from e
                continue

        return pd.DataFrame(columns=["date", "instrument", "value", "reason"])

    def _search_news(self, query: dict) -> dict:
        """用 Tavily 搜索新闻正文。"""
        try:
            from langchain_community.tools.tavily_search import TavilySearchResults
        except ImportError:
            print("[提示] langchain_community 未安装, 跳过新闻搜索。pip install langchain-community")
            return {}

        contents = {}
        instruments = list(query.keys())
        tavily = TavilySearchResults(max_results=2)

        for ins in instruments:
            titles = query[ins]
            content = []
            for t in titles:
                try:
                    # 提取标题文本 (去掉来源前缀)
                    match = re.search(r'"(.+?)"', t)
                    search_query = match.group(1) if match else t
                    ret = tavily.invoke(input=search_query)
                    if ret:
                        content.append(ret[0].get("content", ""))
                    else:
                        content.append("未搜索到内容")
                except Exception as e:
                    content.append(f"搜索失败: {e}")
            contents[ins] = content

        return contents

    def analyze_and_submit(
        self,
        news_df: pd.DataFrame,
        factor_name: str,
        category: str = "舆情",
        data_path: str = "./data",
        search_first: bool = True,
        **submit_kwargs,
    ) -> str:
        """
        分析新闻情绪并直接提交为因子, 纳入每日监控看板。

        参数:
            news_df:     新闻 DataFrame
            factor_name: 因子名称
            category:    因子分类, 默认 "舆情"
            data_path:   数据路径
            search_first: 是否先搜索新闻正文
            **submit_kwargs: 传给 submit_factor() 的额外参数

        返回:
            factor_id 字符串
        """
        try:
            from xxybacktest.factor import submit_factor
        except ImportError:
            raise ImportError("需要 xxybacktest.factor 模块, 请确认已安装 xxybacktest")

        # 1. 分析新闻 → 得到因子值 DataFrame
        sentiment_df = self._analyze_inner(news_df, search_first=search_first)
        if sentiment_df.empty:
            raise RuntimeError("新闻情绪分析未产生任何结果")

        # 2. 将因子值 DataFrame 转为一个临时表, 生成查询 SQL
        # 由于 submit_factor 需要 SQL, 我们构造一个简单的查询
        # 实际做法: 把 sentiment_df 写入 xxydb 的临时路径
        import tempfile
        import os as _os

        tmp_dir = _os.path.join(data_path, "news_sentiment_cache")
        _os.makedirs(tmp_dir, exist_ok=True)
        parquet_path = _os.path.join(tmp_dir, "latest_sentiment.parquet")
        sentiment_df.to_parquet(parquet_path, index=False)

        # 构建 SQL: 直接从 parquet 读取 (DuckDB 支持 parquet 直接查询)
        sql = (
            f"SELECT date, instrument, value "
            f"FROM read_parquet('{parquet_path.replace(chr(92), '/')}')"
        )

        # 3. 提交因子
        factor_id = submit_factor(
            name=factor_name,
            sql=sql,
            category=category,
            data_path=data_path,
            description=f"新闻情绪自动评分因子 (基于 {len(news_df)} 条新闻, {len(sentiment_df)} 个标的)",
            run_now=True,
            **submit_kwargs,
        )
        return factor_id

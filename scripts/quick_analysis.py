"""Factor analysis on news_sentiment table (now in xxydb)"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from xxybacktest.factor import analyze_factor

sql = "SELECT date, instrument, value FROM news_sentiment"

res = analyze_factor(
    sql=sql,
    data_path="d:/xxybacktest-master/data",
    name="News Sentiment (Keyword)",
    periods=(1, 5, 10),
    n_groups=5,
    exclude_suspended=False,
    exclude_st=False,
    exclude_limit=False,
)

res.summary()

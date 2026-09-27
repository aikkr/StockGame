import json

import yfinance as yf

from server.config import get_stock_symbols


def _article_content(article: dict) -> dict:
    if not isinstance(article, dict):
        return {}
    content = article.get('content')
    return content if isinstance(content, dict) else article


def _article_date(content: dict) -> str:
    published = content.get('pubDate') or content.get('providerPublishTime') or ''
    return str(published)[:10]


def getNews(tick: str, fromDate: str, toDate: str) -> dict:
    news = {}
    for article in yf.Ticker(tick).news or []:
        content = _article_content(article)
        title = content.get('title')
        date = _article_date(content)
        if title and fromDate <= date <= toDate:
            news[title] = {'summary': content.get('summary', ''), 'date': date}
    return news


def getLatestNews(tick: str) -> dict | None:
    for article in yf.Ticker(tick).news or []:
        content = _article_content(article)
        title = content.get('title')
        if title:
            return {
                'headline': title,
                'summary': content.get('summary', ''),
                'date': _article_date(content),
            }
    return None


def getNewsAsJSON(startDate: str, endDate: str) -> None:
    """Write filtered news for all configured stocks to ``news.json``.

    Dependencies: getNews, configured STOCKS, and a writable working directory.
    Side effects: performs network requests and replaces ``news.json``.
    Failure impact: callers receive the provider or filesystem exception.
    """
    all_news = {
        ticker: getNews(ticker, startDate, endDate)
        for ticker in get_stock_symbols()
    }
    with open('news.json', 'w', encoding='utf-8') as json_file:
        json.dump(all_news, json_file)

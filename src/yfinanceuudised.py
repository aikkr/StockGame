import json
from urllib.parse import urlparse

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


def _clean_text(value: object, maximum_length: int) -> str:
    return value.strip()[:maximum_length] if isinstance(value, str) else ''


def _article_text(content: dict) -> str:
    for field in ('body', 'fullText', 'description', 'summary'):
        value = content.get(field)
        cleaned = _clean_text(value, 20_000)
        if cleaned:
            return cleaned
    return ''


def _article_provider(content: dict) -> str:
    provider = content.get('provider')
    if isinstance(provider, dict):
        name = provider.get('displayName') or provider.get('name')
        if isinstance(name, str):
            return _clean_text(name, 200)
    publisher = content.get('publisher')
    return _clean_text(publisher, 200)


def _article_url(content: dict) -> str:
    for field in ('canonicalUrl', 'clickThroughUrl'):
        value = content.get(field)
        candidate = value.get('url') if isinstance(value, dict) else value
        if isinstance(candidate, str) and len(candidate) <= 2_048:
            parsed = urlparse(candidate)
            if parsed.scheme in {'http', 'https'} and parsed.netloc:
                return candidate
    link = content.get('link')
    if isinstance(link, str) and len(link) <= 2_048:
        parsed = urlparse(link)
        if parsed.scheme in {'http', 'https'} and parsed.netloc:
            return link
    return ''


def getNews(tick: str, fromDate: str, toDate: str) -> dict:
    news = {}
    for article in yf.Ticker(tick).news or []:
        content = _article_content(article)
        title = _clean_text(content.get('title'), 500)
        date = _article_date(content)
        if title and fromDate <= date <= toDate:
            news[title] = {'summary': _article_text(content), 'date': date}
    return news


def getLatestNews(tick: str) -> dict | None:
    for article in yf.Ticker(tick).news or []:
        content = _article_content(article)
        title = _clean_text(content.get('title'), 500)
        if title:
            return {
                'headline': title,
                'body': _article_text(content),
                'date': _article_date(content),
                'provider': _article_provider(content),
                'url': _article_url(content),
            }
    return None


def getNewsAsJSON(startDate: str, endDate: str) -> None:
    all_news = {
        ticker: getNews(ticker, startDate, endDate)
        for ticker in get_stock_symbols()
    }
    with open('news.json', 'w', encoding='utf-8') as json_file:
        json.dump(all_news, json_file)

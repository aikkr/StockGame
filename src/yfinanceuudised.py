import json
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from xml.etree import ElementTree
from urllib.parse import urlparse

import httpx
import yfinance as yf

from server.config import get_stock_symbols


def _article_content(article: dict) -> dict:
    if not isinstance(article, dict):
        return {}
    content = article.get('content')
    return content if isinstance(content, dict) else article


def _article_date(content: dict) -> str:
    published = content.get('pubDate') or content.get('providerPublishTime') or ''
    if isinstance(published, (int, float)):
        return datetime.fromtimestamp(published, timezone.utc).date().isoformat()
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


def get_recent_news(symbol):
    articles = []
    try:
        articles = yf.Ticker(symbol).news or []
    except Exception:
        logging.getLogger(__name__).warning('Yahoo ticker news failed for %s; trying RSS.', symbol)
    news = []
    for article in articles:
        content = _article_content(article)
        title = _clean_text(content.get('title'), 500)
        if title:
            news.append({
                'headline': title,
                'body': _article_text(content),
                'date': _article_date(content),
                'provider': _article_provider(content),
                'url': _article_url(content),
            })
    if not news:
        news = get_rss_news(symbol)
    return sorted(news, key=lambda article: article['date'], reverse=True)[:10]


def get_rss_news(symbol):
    response = httpx.get(
        'https://feeds.finance.yahoo.com/rss/2.0/headline',
        params={'s': symbol, 'region': 'US', 'lang': 'en-US'},
        headers={'User-Agent': 'Mozilla/5.0'},
        timeout=20,
        follow_redirects=True,
    )
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    news = []
    for item in root.findall('./channel/item'):
        title = _clean_text(item.findtext('title'), 500)
        if not title:
            continue
        published = item.findtext('pubDate', '')
        try:
            date = parsedate_to_datetime(published).date().isoformat()
        except (ValueError, TypeError, OverflowError):
            date = ''
        news.append({
            'headline': unescape(title),
            'body': unescape(_clean_text(item.findtext('description'), 20_000)),
            'date': date,
            'provider': item.findtext('source') or 'Yahoo Finance',
            'url': _article_url({'link': item.findtext('link')}),
        })
    return news


def getNews(tick: str, fromDate: str, toDate: str) -> dict:
    return {
        article['headline']: {'summary': article['body'], 'date': article['date']}
        for article in get_recent_news(tick)
        if fromDate <= article['date'] <= toDate
    }


def getLatestNews(tick: str) -> dict | None:
    news = get_recent_news(tick)
    return news[0] if news else None


def getNewsAsJSON(startDate: str, endDate: str) -> None:
    all_news = {
        ticker: getNews(ticker, startDate, endDate)
        for ticker in get_stock_symbols()
    }
    with open('news.json', 'w', encoding='utf-8') as json_file:
        json.dump(all_news, json_file)

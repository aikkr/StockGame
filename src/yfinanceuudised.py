import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from xml.etree import ElementTree

import httpx
import yfinance as yf


def article_date(article):
    return article['date']


def get_article_url(content):
    for field in ('canonicalUrl', 'clickThroughUrl', 'link'):
        link = content.get(field, '')
        if isinstance(link, dict):
            link = link.get('url', '')
        if link and link.startswith(('https://', 'http://')):
            return link
    return ''


def get_recent_news(symbol):
    try:
        articles = yf.Ticker(symbol).news or []
    except Exception:
        logging.getLogger(__name__).debug('Yahoo news failed for %s; trying RSS.', symbol, exc_info=True)
        articles = []

    news = []
    for article in articles:

        content = article.get('content', article)
        title = content.get('title', '').strip()
        if not title:
            continue

        body = ''
        for field in ('body', 'fullText', 'description', 'summary'):
            text = content.get(field)
            if text:
                body = text.strip()
                break

        published = content.get('pubDate') or content.get('providerPublishTime', '')
        if isinstance(published, (int, float)):
            date = datetime.fromtimestamp(published, timezone.utc).date().isoformat()
        else:
            date = published[:10]

        provider = content.get('provider') or content.get('publisher', '')
        if isinstance(provider, dict):
            provider = provider.get('displayName') or provider.get('name', '')

        news.append({
            'headline': title,
            'body': body,
            'date': date,
            'provider': provider,
            'url': get_article_url(content),
        })

    if not news:
        news = get_rss_news(symbol)


    news.sort(key=article_date, reverse=True)
    latest_news = news[:10]
    return latest_news


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
        title = item.findtext('title', '').strip()
        if not title:
            continue
        published = item.findtext('pubDate')
        date = ''
        if published:
            date = parsedate_to_datetime(published).date().isoformat()
        news.append({
            'headline': unescape(title),
            'body': unescape(item.findtext('description', '')),
            'date': date,
            'provider': item.findtext('source') or 'Yahoo Finance',
            'url': get_article_url({'link': item.findtext('link', '')}),
        })
    return news

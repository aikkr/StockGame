import asyncio
import random
from collections import deque
from datetime import datetime, timezone

from nicegui import app, background_tasks

from server.config import get_stock_symbols
from yfinanceuudised import getLatestNews


_items = deque(maxlen=5)
_last_symbol = None
_task = None


def get_news() -> list[dict]:
    return list(_items)


def _choose_symbol() -> str:
    symbols = get_stock_symbols()
    choices = [symbol for symbol in symbols if symbol != _last_symbol]
    return random.choice(choices or list(symbols))


def _fetch_item(symbol: str) -> dict:
    try:
        article = getLatestNews(symbol)
    except Exception:
        article = None
    if article:
        return {
            'symbol': symbol,
            'age': 'just now',
            'headline': article['headline'],
            'body': article.get('body', ''),
            'date': article.get('date', ''),
            'provider': article.get('provider', ''),
            'url': article.get('url', ''),
        }
    timestamp = datetime.now(timezone.utc).strftime('%H:%M:%S UTC')
    return {
        'symbol': symbol,
        'age': 'just now',
        'headline': f'No recent Yahoo Finance headline for {symbol} ({timestamp})',
        'body': 'Yahoo Finance did not return an article for this ticker.',
        'date': datetime.now(timezone.utc).date().isoformat(),
        'provider': 'Yahoo Finance',
        'url': '',
    }


async def update_news() -> None:
    global _last_symbol
    while True:
        symbol = _choose_symbol()
        _last_symbol = symbol
        item = await asyncio.to_thread(_fetch_item, symbol)
        _items.appendleft(item)
        await asyncio.sleep(10)


def start_news_updates() -> None:
    global _task
    if _task is None or _task.done():
        _task = background_tasks.create(update_news(), name='stock-news-updater')


async def stop_news_updates() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        await asyncio.gather(_task, return_exceptions=True)
        _task = None


app.on_startup(start_news_updates)
app.on_shutdown(stop_news_updates)

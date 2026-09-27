"""Fetch rotating stock news and expose the latest server-side items."""

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
    """Return a copy of the newest generated news items.

    Dependencies: the in-process news updater.
    Side effects: none.
    Failure impact: callers receive an empty list before the first update.
    """
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
            'summary': article.get('summary', ''),
            'date': article.get('date', ''),
        }
    timestamp = datetime.now(timezone.utc).strftime('%H:%M:%S UTC')
    return {
        'symbol': symbol,
        'age': 'just now',
        'headline': f'No recent Yahoo Finance headline for {symbol} ({timestamp})',
        'summary': '',
        'date': datetime.now(timezone.utc).date().isoformat(),
    }


async def update_news() -> None:
    """Continuously fetch news for alternating random configured stocks.

    Dependencies: configured STOCKS and the yfinance news adapter.
    Side effects: performs network reads and updates the in-memory news feed.
    Failure impact: a failed request produces a timestamped fallback item.
    """
    global _last_symbol
    while True:
        symbol = _choose_symbol()
        _last_symbol = symbol
        item = await asyncio.to_thread(_fetch_item, symbol)
        _items.appendleft(item)
        await asyncio.sleep(10)


def start_news_updates() -> None:
    """Start the single application-wide news update task.

    Dependencies: NiceGUI's running event loop.
    Side effects: creates one background task that performs periodic network reads.
    Failure impact: live news remains at its last successfully generated state.
    """
    global _task
    if _task is None or _task.done():
        _task = background_tasks.create(update_news(), name='stock-news-updater')


async def stop_news_updates() -> None:
    """Cancel the news update task during application shutdown.

    Dependencies: a previously started news task.
    Side effects: cancels pending periodic work.
    Failure impact: none; shutdown continues if no task exists.
    """
    global _task
    if _task is not None:
        _task.cancel()
        await asyncio.gather(_task, return_exceptions=True)
        _task = None


app.on_startup(start_news_updates)
app.on_shutdown(stop_news_updates)

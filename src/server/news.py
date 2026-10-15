import asyncio
import hashlib
import logging
from collections import deque
from datetime import datetime
from time import monotonic

from nicegui import app, background_tasks

from server.config import get_stock_symbols
from server.market_data import market_service
from server.price_ai import get_news_goal
from yfinanceuudised import get_recent_news


_news_items = deque(maxlen=20)
_pending_articles = asyncio.Queue()
_queued_article_ids = set()
_update_tasks = []
_feed_status = 'Waiting for Yahoo Finance.'
_ai_status = 'Up to date. Waiting for new headlines.'
logger = logging.getLogger(__name__)


def get_news():
    return list(_news_items)[:5]


def get_news_status():
    if market_service.get_event()['active']:
        return {
            'feed': 'News paused: Trump has woken up.',
            'ai': 'AI goals paused until the event ends.',
            'pending': len(_queued_article_ids),
        }
    return {'feed': _feed_status, 'ai': _ai_status, 'pending': len(_queued_article_ids)}


def get_article_id(symbol, article):
    headline = article['headline'].strip().casefold()
    identity = headline + ':' + article.get('date', '')
    return hashlib.sha256(f'{symbol}:{identity}'.encode()).hexdigest()


def queue_articles(symbol, articles):
    if market_service.get_event()['active']:
        return 0
    items = [dict(article, id=get_article_id(symbol, article)) for article in articles]
    market_service.initialize_news(symbol, items)
    stock = next(stock for stock in market_service.get_snapshot()['stocks'] if stock['symbol'] == symbol)
    reports = {report['id']: report for report in stock['news_reports']}
    queued = 0
    for article in reversed(items):
        article_id = get_article_id(symbol, article)
        item = dict(article, symbol=symbol, age=article.get('date', ''), id=article_id)
        if article_id in reports:
            item['ai_reason'] = reports[article_id]['reason']
            item['goal_price'] = reports[article_id].get('goal_price')
        if not any(current['id'] == article_id for current in _news_items):
            _news_items.appendleft(item)
        if article_id in _queued_article_ids or market_service.has_processed_news(symbol, article_id):
            continue
        if len(_queued_article_ids) >= 200:
            break
        _queued_article_ids.add(article_id)
        _pending_articles.put_nowait(item)
        queued += 1
    return queued


async def fetch_stock_news(symbol, limit):
    async with limit:
        if market_service.get_event()['active']:
            return 0, False
        try:
            articles = await asyncio.to_thread(get_recent_news, symbol)
            queued = queue_articles(symbol, articles)
            return queued, bool(articles)
        except Exception:
            logger.exception('Could not fetch Yahoo Finance news for %s', symbol)
            return 0, False


async def update_news():
    global _feed_status
    while True:
        if market_service.get_event()['active']:
            await asyncio.sleep(1)
            continue
        started = monotonic()
        symbols = get_stock_symbols()
        if not symbols:
            _feed_status = 'No stocks are configured.'
            await asyncio.sleep(10)
            continue
        limit = asyncio.Semaphore(4)
        results = await asyncio.gather(*(fetch_stock_news(symbol, limit) for symbol in symbols))
        count = sum(result[0] for result in results)
        available = sum(result[1] for result in results)
        checked = datetime.now().strftime('%H:%M:%S')
        _feed_status = f'Checked {checked}: {available}/{len(symbols)} feeds, {count} new articles. Checks every minute.'
        await asyncio.sleep(max(1, 60 - (monotonic() - started)))


async def update_market_prices():
    while True:
        try:
            await asyncio.to_thread(market_service.get_snapshot)
        except Exception:
            logger.exception('Could not update market prices')
        await asyncio.sleep(1)


async def process_article(item):
    if market_service.get_event()['active']:
        return False
    symbol = item['symbol']
    article_id = item['id']
    if market_service.has_processed_news(symbol, article_id):
        return True
    snapshot = market_service.get_snapshot()
    stock = next(stock for stock in snapshot['stocks'] if stock['symbol'] == symbol)
    previous_goal = stock['goal_price']
    recent_news = [
        {'headline': report['headline'], 'reason': report['reason']}
        for report in stock['news_reports'][:10]
    ]
    goal, reason = await get_news_goal(
        symbol, previous_goal, item,
        company_name=stock['name'], recent_news=recent_news,
    )
    event = market_service.get_event()
    if event['active'] or event['id'] != snapshot['event']['id']:
        return False
    report = {
        'id': article_id, 'headline': item['headline'], 'reason': reason,
        'checked_at': datetime.now().strftime('%H:%M:%S'),
    }
    market_service.apply_news_goal(
        symbol, article_id, previous_goal, goal,
        expected_revision=stock['goal_revision'], report=report,
    )
    updated = next(stock for stock in market_service.get_snapshot()['stocks'] if stock['symbol'] == symbol)
    applied = next(report for report in updated['news_reports'] if report['id'] == article_id)
    item['ai_reason'] = reason
    item['goal_price'] = applied['goal_price']
    for displayed in _news_items:
        if displayed['id'] == article_id:
            displayed.update(item)
    return True


async def update_goals():
    global _ai_status
    while True:
        if market_service.get_event()['active']:
            await asyncio.sleep(1)
            continue
        item = await _pending_articles.get()
        try:
            _ai_status = f'Reading news for {item["symbol"]}.'
            if not await process_article(item):
                _pending_articles.put_nowait(item)
                await asyncio.sleep(1)
                continue
            _ai_status = f'News processed for {item["symbol"]}.'
            _queued_article_ids.discard(item['id'])
            if _pending_articles.empty():
                _ai_status = 'Up to date. Waiting for new headlines.'
        except Exception:
            logger.exception('Could not apply AI news goal for %s', item['symbol'])
            _ai_status = 'AI unavailable; goals unchanged. Check Ollama and the model. Retrying.'
            await asyncio.sleep(30)
            _pending_articles.put_nowait(item)
        finally:
            _pending_articles.task_done()


def start_news_updates():
    if not _update_tasks:
        _update_tasks.append(background_tasks.create(update_news(), name='stock-news-updater'))
        _update_tasks.append(background_tasks.create(update_goals(), name='stock-goal-updater'))
        _update_tasks.append(background_tasks.create(update_market_prices(), name='stock-price-updater'))


async def stop_news_updates():
    for task in _update_tasks:
        task.cancel()
    await asyncio.gather(*_update_tasks, return_exceptions=True)
    _update_tasks.clear()


app.on_startup(start_news_updates)
app.on_shutdown(stop_news_updates)

import asyncio
import logging
from collections import deque
from datetime import datetime
from time import monotonic

from nicegui import app, background_tasks

from server.config import get_stock_symbols
from server.market_data import market_service
from server.news_identity import get_publication_id
from server.price_ai import get_news_goal
from yfinanceuudised import get_recent_news


_news_items = deque(maxlen=20)
_unpublished_articles = deque()
_staged_publication_ids = set()
NEWS_INTERVAL_SECONDS = 5
_next_publication_at = monotonic() + NEWS_INTERVAL_SECONDS
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
    return symbol + ':' + headline + ':' + article.get('date', '')


def queue_articles(symbol, articles):
    if market_service.get_event()['active']:
        return 0
    items = []
    for article in articles:
        item = dict(article)
        item['id'] = get_article_id(symbol, article)
        items.append(item)
    market_service.initialize_news(symbol, items)
    for stock in market_service.get_snapshot()['stocks']:
        if stock['symbol'] == symbol:
            break
    reports = {}
    for report in stock['news_reports']:
        reports[report['id']] = report
    queued = 0
    for article in reversed(items):
        article_id = article['id']
        publication_id = get_publication_id(article)
        if market_service.has_published_news(publication_id):
            if (
                market_service.has_published_news(publication_id, symbol)
                and article_id not in _queued_article_ids
                and not market_service.has_processed_news(symbol, article_id)
            ):
                _queued_article_ids.add(article_id)
                _pending_articles.put_nowait(dict(article, symbol=symbol))
            continue
        if publication_id in _staged_publication_ids:
            continue
        if len(_unpublished_articles) >= 200:
            break
        item = dict(article, symbol=symbol, age=article.get('date', ''), id=article_id)
        if article_id in reports:
            item['ai_reason'] = reports[article_id]['reason']
            item['goal_price'] = reports[article_id].get('goal_price')
        _staged_publication_ids.add(publication_id)
        _unpublished_articles.append(item)
        queued += 1
    return queued


def publish_next_article():
    global _next_publication_at
    now = monotonic()
    if market_service.get_event()['active']:
        _next_publication_at = now + NEWS_INTERVAL_SECONDS
        return False
    if now < _next_publication_at:
        return False
    while _unpublished_articles:
        item = _unpublished_articles[0]
        publication_id = get_publication_id(item)
        if market_service.has_published_news(publication_id):
            _unpublished_articles.popleft()
            _staged_publication_ids.discard(publication_id)
            continue
        if not market_service.publish_news(item['symbol'], publication_id):
            return False
        _unpublished_articles.popleft()
        _staged_publication_ids.discard(publication_id)
        _news_items.appendleft(item)
        _next_publication_at = now + NEWS_INTERVAL_SECONDS
        article_id = item['id']
        if article_id not in _queued_article_ids and not market_service.has_processed_news(item['symbol'], article_id):
            _queued_article_ids.add(article_id)
            _pending_articles.put_nowait(item)
        return True
    return False


async def release_news():
    while True:
        publish_next_article()
        await asyncio.sleep(0.1)


async def fetch_stock_news(symbol, limit):
    async with limit:
        event = market_service.get_event()
        if event['active']:
            return 0, False
        try:
            articles = await asyncio.to_thread(get_recent_news, symbol)
            current = market_service.get_event()
            if current['active'] or current['id'] != event['id']:
                return 0, False
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
        tasks = []
        for symbol in symbols:
            tasks.append(fetch_stock_news(symbol, limit))

        results = await asyncio.gather(*tasks)
        count = 0
        available = 0
        for queued, has_articles in results:
            count += queued
            if has_articles:
                available += 1
        checked = datetime.now().strftime('%H:%M:%S')
        _feed_status = (
            f'Checked {checked}: {available}/{len(symbols)} feeds, {count} unused articles. '
            'One headline every 5 seconds while available.'
        )
        await asyncio.sleep(max(1, 60 - (monotonic() - started)))


async def update_market_prices():
    while True:
        await asyncio.to_thread(market_service.get_snapshot)
        await asyncio.sleep(1)


async def process_article(item):
    if market_service.get_event()['active']:
        return False
    symbol = item['symbol']
    article_id = item['id']
    if market_service.has_processed_news(symbol, article_id):
        return True
    snapshot = market_service.get_snapshot()
    for stock in snapshot['stocks']:
        if stock['symbol'] == symbol:
            break
    previous_goal = stock['goal_price']
    recent_news = []
    for report in stock['news_reports'][:10]:
        recent_news.append({'headline': report['headline'], 'reason': report['reason']})
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
    for updated in market_service.get_snapshot()['stocks']:
        if updated['symbol'] == symbol:
            break
    for applied in updated['news_reports']:
        if applied['id'] == article_id:
            break
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
        _update_tasks.append(background_tasks.create(release_news(), name='stock-news-publisher'))
        _update_tasks.append(background_tasks.create(update_goals(), name='stock-goal-updater'))
        _update_tasks.append(background_tasks.create(update_market_prices(), name='stock-price-updater'))


async def stop_news_updates():
    for task in _update_tasks:
        task.cancel()
    await asyncio.gather(*_update_tasks, return_exceptions=True)
    _update_tasks.clear()


app.on_startup(start_news_updates)
app.on_shutdown(stop_news_updates)

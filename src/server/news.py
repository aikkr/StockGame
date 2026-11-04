import asyncio
import logging
from collections import deque
from datetime import datetime
from time import monotonic
from uuid import uuid4

from nicegui import app, background_tasks

from server.config import get_stock_symbols
from server.market_data import market_service
from server.news_identity import get_publication_id
from server.price_ai import get_news_goal
from yfinanceuudised import get_recent_news


_news_items = deque(maxlen=20)
_released_publication_ids = set()
_unpublished_articles = deque()
_staged_publication_ids = set()
_cached_articles = {}
_last_shown_at = {}
NEWS_INTERVAL_SECONDS = 5
MAX_PENDING_EVALUATIONS = 200
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
            'publication': 'News paused during the market event.',
            'ai': 'AI goals paused until the event ends.',
            'pending': len(_queued_article_ids),
        }
    if len(_queued_article_ids) >= MAX_PENDING_EVALUATIONS:
        publication = 'AI is catching up. Headlines resume when evaluations finish.'
    elif _unpublished_articles:
        publication = f'One headline every {NEWS_INTERVAL_SECONDS} seconds. {len(_unpublished_articles)} waiting.'
    elif _feed_status.startswith('News feeds unavailable.'):
        publication = (
            'Showing saved headlines. News feeds temporarily unavailable.'
            if _cached_articles else 'News temporarily unavailable. Retrying every minute.'
        )
    elif _cached_articles:
        publication = 'Showing recent headlines. Waiting for new stories.'
    elif _feed_status == 'Waiting for Yahoo Finance.':
        publication = _feed_status
    else:
        publication = 'No new headlines. Checking for updates every minute.'
    return {
        'feed': _feed_status, 'publication': publication,
        'ai': _ai_status, 'pending': len(_queued_article_ids),
    }


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
    stock = next(stock for stock in market_service.get_snapshot()['stocks'] if stock['symbol'] == symbol)
    reports = {report.get('article_id', report['id']): report for report in reversed(stock['news_reports'])}
    cached = []
    queued = 0
    for article in reversed(items):
        article_id = article['id']
        publication_id = get_publication_id(article)
        if (
            market_service.has_published_news(publication_id)
            and not market_service.has_published_news(publication_id, symbol)
        ):
            continue
        item = dict(article, symbol=symbol, age=article.get('date', ''), id=article_id)
        if article_id in reports:
            item['ai_reason'] = reports[article_id]['reason']
            item['goal_price'] = reports[article_id].get('goal_price')
        cached.append(item)
        if market_service.has_processed_news(symbol, article_id):
            continue
        if publication_id in _released_publication_ids or publication_id in _staged_publication_ids:
            continue
        if len(_unpublished_articles) >= 200:
            continue
        _staged_publication_ids.add(publication_id)
        _unpublished_articles.append(item)
        queued += 1
    if cached:
        _cached_articles[symbol] = cached
        active_ids = {
            get_publication_id(item)
            for batch in _cached_articles.values() for item in batch
        }
        for publication_id in _last_shown_at.keys() - active_ids:
            del _last_shown_at[publication_id]
    return queued


def _next_article_index():
    recent_symbols = list(dict.fromkeys(item['symbol'] for item in _news_items))
    priority = {symbol: index for index, symbol in enumerate(recent_symbols)}
    return max(
        range(len(_unpublished_articles)),
        key=lambda index: priority.get(_unpublished_articles[index]['symbol'], len(priority)),
    )


def _release_article(article, now, previously_processed=False):
    item = dict(article, evaluation_id=uuid4().hex, previously_processed=previously_processed)
    for field in ('ai_reason', 'goal_price', 'previous_goal'):
        item.pop(field, None)
    item['ai_status'] = 'queued'
    _news_items.appendleft(item)
    _last_shown_at[get_publication_id(item)] = now
    _queued_article_ids.add(item['evaluation_id'])
    _pending_articles.put_nowait(item)


def _publish_cached_article(now):
    recent_symbols = list(dict.fromkeys(item['symbol'] for item in _news_items))
    priority = {symbol: index for index, symbol in enumerate(recent_symbols)}
    visible_ids = {get_publication_id(item) for item in get_news()}
    candidates = [
        item for symbol in get_stock_symbols()
        for item in _cached_articles.get(symbol, [])
        if get_publication_id(item) not in visible_ids
        and market_service.has_processed_news(symbol, item['id'])
    ]
    if not candidates:
        return False
    item = max(candidates, key=lambda article: (
        priority.get(article['symbol'], len(priority)),
        -_last_shown_at.get(get_publication_id(article), float('-inf')),
    ))
    _release_article(item, now, previously_processed=True)
    return True


def publish_next_article():
    global _next_publication_at
    now = monotonic()
    if market_service.get_event()['active']:
        _next_publication_at = now + NEWS_INTERVAL_SECONDS
        return False
    if now < _next_publication_at:
        return False
    if len(_queued_article_ids) >= MAX_PENDING_EVALUATIONS:
        return False
    while _unpublished_articles:
        index = _next_article_index()
        item = _unpublished_articles[index]
        publication_id = get_publication_id(item)
        if publication_id in _released_publication_ids:
            del _unpublished_articles[index]
            _staged_publication_ids.discard(publication_id)
            continue
        if (
            not market_service.has_published_news(publication_id)
            and not market_service.publish_news(item['symbol'], publication_id)
        ):
            return False
        del _unpublished_articles[index]
        _staged_publication_ids.discard(publication_id)
        _released_publication_ids.add(publication_id)
        _release_article(item, now)
        _next_publication_at = now + NEWS_INTERVAL_SECONDS
        return True
    if _publish_cached_article(now):
        _next_publication_at = now + NEWS_INTERVAL_SECONDS
        return True
    return False


async def release_news():
    unavailable = False
    while True:
        try:
            published = publish_next_article()
            if published and unavailable:
                logger.info('News publication recovered.')
                unavailable = False
        except Exception:
            if not unavailable:
                logger.warning('Could not publish news; retrying in the background.', exc_info=True)
            unavailable = True
            await asyncio.sleep(1)
            continue
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
            logger.debug('Could not fetch Yahoo Finance news for %s', symbol, exc_info=True)
            return 0, False


async def update_news():
    global _feed_status
    feed_unavailable = False
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
        if not available and not feed_unavailable:
            logger.warning('No news feeds are available. Retrying quietly in the background.')
        elif available and feed_unavailable:
            logger.info('News feeds recovered.')
        feed_unavailable = not available
        checked = datetime.now().strftime('%H:%M:%S')
        _feed_status = (
            f'Checked {checked}: {available}/{len(symbols)} feeds, {count} headlines queued.'
            if available else f'News feeds unavailable. Last checked {checked}.'
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
    evaluation_id = item.get('evaluation_id')
    report_id = evaluation_id or article_id
    if market_service.has_processed_news(symbol, report_id):
        return True
    snapshot = market_service.get_snapshot()
    for stock in snapshot['stocks']:
        if stock['symbol'] == symbol:
            break
    previous_goal = stock['goal_price']
    recent_news = []
    if not evaluation_id:
        for report in stock['news_reports'][:10]:
            recent_news.append({'headline': report['headline'], 'reason': report['reason']})
    item['ai_status'] = 'reading'
    goal, reason = await get_news_goal(
        symbol, previous_goal, item,
        company_name=stock['name'], recent_news=recent_news,
    )
    event = market_service.get_event()
    if event['active'] or event['id'] != snapshot['event']['id']:
        return False
    report = {
        'id': report_id, 'article_id': article_id,
        'headline': item['headline'], 'reason': reason, 'requested_goal': goal,
        'checked_at': datetime.now().strftime('%H:%M:%S'),
    }
    market_service.apply_news_goal(
        symbol, article_id, previous_goal, goal,
        expected_revision=stock['goal_revision'], report=report,
        evaluation_id=evaluation_id,
    )
    for updated in market_service.get_snapshot()['stocks']:
        if updated['symbol'] == symbol:
            break
    for applied in updated['news_reports']:
        if applied['id'] == report_id:
            break
    item['ai_reason'] = reason
    item['goal_price'] = applied['goal_price']
    item['previous_goal'] = applied['previous_goal']
    item['ai_status'] = 'processed'
    for displayed in _news_items:
        if displayed.get('evaluation_id', displayed['id']) == report_id:
            displayed.update(item)
    return True


async def update_goals():
    global _ai_status
    ai_unavailable = False
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
            if ai_unavailable:
                logger.info('AI news processing recovered.')
            ai_unavailable = False
            _ai_status = f'News processed for {item["symbol"]}.'
            _queued_article_ids.discard(item.get('evaluation_id', item['id']))
            if _pending_articles.empty():
                _ai_status = 'Up to date. Waiting for new headlines.'
        except Exception as error:
            item['ai_status'] = 'retrying'
            if not ai_unavailable:
                logger.warning(
                    'AI news processing unavailable (%s). Check Ollama and the model; retrying quietly.',
                    type(error).__name__,
                )
            ai_unavailable = True
            logger.debug('Could not apply AI news goal for %s', item['symbol'], exc_info=True)
            _ai_status = 'AI unavailable; goals unchanged. Check Ollama and the model. Retrying.'
            await asyncio.sleep(30)
            _pending_articles.put_nowait(item)
        finally:
            _pending_articles.task_done()


def start_news_updates():
    global _next_publication_at
    if not _update_tasks:
        _next_publication_at = monotonic() + NEWS_INTERVAL_SECONDS
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

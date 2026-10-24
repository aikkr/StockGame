"""Regress news cadence and automatic events; uses unittest mocks and temporary SQLite only.

Run with PYTHONPATH=src and python -m unittest test_news_events.
"""

import asyncio
from collections import deque
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch

from DB import UserDatabase
from server import news
from server.market_data import MarketService, MockMarketDataSource


class NewsEventTests(unittest.IsolatedAsyncioTestCase):
    """Test market/news coordination with mocked clocks; failures flag timing or repeat regressions."""

    def setUp(self):
        """Isolate queues, clocks and market via unittest patches; no network or durable writes."""
        clock = patch('server.market_data.monotonic', return_value=100)
        self.clock = clock.start()
        self.addCleanup(clock.stop)
        news_clock = patch.object(news, 'monotonic', side_effect=lambda: self.clock())
        news_clock.start()
        self.addCleanup(news_clock.stop)
        self.source = MockMarketDataSource()
        self.source._next_event_at = 220
        self.market = MarketService(self.source, lambda: ('AAPL', 'MSFT'))
        self.market.get_snapshot()
        patches = patch.multiple(
            news, market_service=self.market, _news_items=deque(maxlen=20),
            _unpublished_articles=deque(), _staged_publication_ids=set(),
            _pending_articles=asyncio.Queue(), _queued_article_ids=set(),
            _next_publication_at=105,
        )
        patches.start()
        self.addCleanup(patches.stop)

    def test_release_one_every_five_seconds_without_catching_up_in_bursts(self):
        """Advance mocked time to verify the feed cadence; only isolated state is changed."""
        articles = [{'headline': f'Story {i}'} for i in range(4)]
        self.assertEqual(news.queue_articles('AAPL', articles), 4)
        self.assertEqual(news.get_news(), [])
        self.assertFalse(news.publish_next_article())
        for now, count in ((105, 1), (109.99, 1), (110, 2), (180, 3)):
            self.clock.return_value = now
            news.publish_next_article()
            self.assertEqual(len(news.get_news()), count)
            self.assertFalse(news.publish_next_article())

    def test_dedup_across_symbols_dates_whitespace_and_queue_refills(self):
        """Refill overlapping feeds using saved identities; no external side effects."""
        first = {'headline': 'A new story', 'date': '2026-10-22'}
        duplicate = {'headline': ' A  NEW story ', 'date': '2026-10-23'}
        self.assertEqual(news.queue_articles('AAPL', [first]), 1)
        self.assertEqual(news.queue_articles('MSFT', [duplicate]), 0)
        self.clock.return_value = 105
        self.assertTrue(news.publish_next_article())
        self.assertEqual(news.queue_articles('AAPL', [first]), 0)
        self.assertEqual(news.queue_articles('MSFT', [duplicate]), 0)
        self.clock.return_value = 110
        self.assertFalse(news.publish_next_article())

    def test_event_pauses_releases_and_resumes_without_burst(self):
        """Toggle the event and advance clocks; queued stories survive and no network is used."""
        news.queue_articles('AAPL', [{'headline': 'One'}, {'headline': 'Two'}])
        self.market.set_event_active(True)
        self.clock.return_value = 110
        self.assertFalse(news.publish_next_article())
        self.assertEqual(news.queue_articles('MSFT', [{'headline': 'Paused'}]), 0)
        self.assertEqual(news.get_news(), [])
        self.market.set_event_active(False)
        self.clock.return_value = 115
        self.assertTrue(news.publish_next_article())
        self.assertFalse(news.publish_next_article())
        self.assertEqual(len(news._unpublished_articles), 1)

    def test_natural_start_and_exact_timeout_restore_goals(self):
        """Verify server-driven lifecycle with mocked monotonic time; no debug API dependency."""
        self.market.set_goal_price('AAPL', 200)
        self.clock.return_value = 219.99
        self.assertFalse(self.market.get_snapshot()['event']['active'])
        self.clock.return_value = 220
        started = self.market.get_snapshot()['event']
        self.assertTrue(started['active'])
        self.clock.return_value = 269.99
        self.assertTrue(self.market.get_event()['active'])
        self.clock.return_value = 270
        ended = self.market.get_event()
        self.assertFalse(ended['active'])
        self.assertEqual(ended['id'], started['id'])
        self.assertEqual(ended['title'], 'Trump went sleep.')
        self.assertEqual(self.market.get_snapshot()['stocks'][0]['goal_price'], 200)
        self.assertGreaterEqual(self.source._next_event_at, 570)
        self.assertLessEqual(self.source._next_event_at, 870)

    def test_manual_event_expires_and_repeated_start_does_not_extend_it(self):
        """Verify debug events share the fixed deadline using mocked time; no external writes."""
        self.market.set_event_active(True)
        self.clock.return_value = 149
        self.market.set_event_active(True)
        self.clock.return_value = 150
        self.assertFalse(self.market.get_event()['active'])

    def test_durable_history_survives_restart_and_migrates_old_reports(self):
        """Use temporary SQLite to verify persistence and migration; writes are removed afterward."""
        article = {'headline': 'Already displayed'}
        identity = news.get_publication_id(article)
        with TemporaryDirectory() as directory:
            database = UserDatabase(Path(directory) / 'game.db')
            source = MockMarketDataSource(database)
            source.get_snapshot(('AAPL',))
            self.assertTrue(source.publish_news('AAPL', identity))
            restored = MockMarketDataSource(database)
            self.assertTrue(restored.has_published_news(identity))
            self.assertFalse(restored.publish_news('AAPL', identity))
            state = database.load_market()
            state['AAPL'].pop('published_news')
            state['AAPL']['news_reports'] = [article]
            database.save_market(state)
            migrated = MockMarketDataSource(database)
            migrated.get_snapshot(('AAPL',))
            self.assertTrue(migrated.has_published_news(identity))

    def test_failed_save_keeps_headline_available_for_retry(self):
        """Inject a storage failure via mock; isolated queue and durable reservation roll back."""
        news.queue_articles('AAPL', [{'headline': 'Retry'}])
        self.clock.return_value = 105
        with patch.object(self.source, '_save_stocks', side_effect=OSError('Disk full')):
            with self.assertRaises(OSError):
                news.publish_next_article()
        self.assertEqual(news.get_news(), [])
        self.assertEqual(len(news._unpublished_articles), 1)
        self.assertTrue(news.publish_next_article())

    def test_published_unprocessed_article_recovers_ai_without_republication(self):
        """Simulate interrupted AI work using memory queues; refill retries AI without another release."""
        news.queue_articles('AAPL', [{'headline': 'Background'}])
        article = {'headline': 'Published before restart'}
        self.market.publish_news('AAPL', news.get_publication_id(article))
        self.assertEqual(news.queue_articles('AAPL', [article]), 0)
        self.assertEqual(news._pending_articles.qsize(), 1)
        news.queue_articles('AAPL', [article])
        self.assertEqual(news._pending_articles.qsize(), 1)

    async def test_fetch_crossing_a_whole_event_is_discarded(self):
        """Mock a slow Yahoo call crossing event boundaries; stale results never enter the feed."""
        async def fetch(*args):
            self.market.set_event_active(True)
            self.market.set_event_active(False)
            return [{'headline': 'Stale response'}]

        with patch.object(news.asyncio, 'to_thread', AsyncMock(side_effect=fetch)):
            self.assertEqual(await news.fetch_stock_news('AAPL', asyncio.Semaphore(1)), (0, False))
        self.assertEqual(len(news._unpublished_articles), 0)


if __name__ == '__main__':
    unittest.main()

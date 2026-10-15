"""Provide market snapshots through a replaceable server-side data source."""

from copy import deepcopy
import math
import random
from threading import Lock
from time import time
from typing import Protocol

from server.config import get_stock_symbols
from server.state import database


PERIOD_PATTERNS = {
    '1D': (0.91, 0.94, 0.92, 0.98, 0.96, 1.02, 1.00),
    '1W': (0.82, 0.87, 0.81, 0.98, 0.935, 1.075, 0.99),
    '1M': (0.72, 0.82, 0.78, 0.89, 0.85, 0.94, 1.00),
    '1Y': (0.50, 0.64, 0.61, 0.80, 0.75, 0.92, 1.00),
}

_COMPANY_NAMES = {
    'MSFT': 'Microsoft', 'MU': 'Micron Technology', 'TSLA': 'Tesla',
    'MCD': "McDonald's", 'AZN': 'AstraZeneca', 'PFE': 'Pfizer',
    'SLS': 'SELLAS Life Sciences', 'KO': 'Coca-Cola', 'AAPL': 'Apple',
    'GOOGL': 'Alphabet', 'NVDA': 'NVIDIA', 'TSM': 'Taiwan Semiconductor',
    'ASML': 'ASML Holding', 'LMT': 'Lockheed Martin', 'SHEL': 'Shell',
    'EQNR': 'Equinor', 'PYPL': 'PayPal', 'HOOD': 'Robinhood Markets',
    'CAT': 'Caterpillar',
}

_SAMPLE_QUOTES = {
    'MSFT': (342.15, 4.12), 'MU': (84.92, -2.84), 'TSLA': (210.40, 2.45),
    'MCD': (292.30, 0.15), 'AZN': (65.65, -1.30), 'PFE': (28.14, 0.62),
    'SLS': (1.21, -3.20), 'KO': (61.12, 0.35), 'AAPL': (189.84, 1.14),
    'GOOGL': (142.65, 0.88), 'NVDA': (495.22, 3.08), 'TSM': (101.44, -0.42),
    'ASML': (692.18, 1.56), 'LMT': (448.92, -0.76), 'SHEL': (64.31, 0.29),
    'EQNR': (31.75, -1.04), 'PYPL': (61.90, 1.09), 'HOOD': (11.24, -2.12),
    'CAT': (257.73, 0.94),
}


class MarketDataSource(Protocol):
    def get_snapshot(self, symbols: tuple[str, ...]) -> dict:
        """Build one complete market snapshot for the requested symbols."""
        ...


class MockMarketDataSource:
    def __init__(self, database=None):
        self._database = database
        self._stocks = database.load_market() if database else {}
        self._last_update = time()
        self._lock = Lock()
        self._event_active = False
        self._event_id = 0
        self._saved_goals = {}

    def get_event(self):
        with self._lock:
            return self._event_status()

    def _event_status(self):
        return {
            'active': self._event_active,
            'id': self._event_id,
            'title': 'Trump has woken up',
            'update_seconds': 1 if self._event_active else 15,
        }

    def set_event_active(self, active, symbols):
        if not isinstance(active, bool):
            raise ValueError('Event active must be true or false.')
        with self._lock:
            if active == self._event_active:
                return self._event_status()
            self._load_stocks(symbols)
            if active and not symbols:
                raise ValueError('No stocks are configured.')
            previous = deepcopy(self._stocks)
            saved_goals = {}
            if active:
                saved_goals = {symbol: self._stocks[symbol]['goal_price'] for symbol in symbols}
            else:
                for symbol, goal in self._saved_goals.items():
                    self._stocks[symbol]['goal_price'] = goal
            for stock in self._stocks.values():
                stock['goal_revision'] = stock.get('goal_revision', 0) + 1
            try:
                self._save_stocks()
            except Exception:
                self._stocks = previous
                raise
            self._saved_goals = saved_goals
            self._event_active = active
            if active:
                self._event_id += 1
            self._last_update = time()
            return self._event_status()

    def _event_goal(self, price, change):
        return round(max(0.01, min(1_000_000, price * (1 + change / 100))), 2)

    def _update_event_goals(self):
        changed = False
        for symbol in self._saved_goals:
            stock = self._stocks[symbol]
            roll = random.random()
            change = 0
            if roll < 0.01:
                change = random.choice((-1, 1)) * random.uniform(20, 40)
            elif roll < 0.25:
                change = random.choice((-1, 1)) * random.uniform(3, 7)
            stock['goal_price'] = self._event_goal(stock['price'], change)
            changed |= stock['goal_price'] != stock['price']
        if not changed:
            stock = self._stocks[random.choice(tuple(self._saved_goals))]
            change = random.choice((-5, 5))
            goal = self._event_goal(stock['price'], change)
            if goal == stock['price']:
                goal = self._event_goal(stock['price'], -change)
            if goal == stock['price']:
                goal = round(stock['price'] + 0.01, 2)
            stock['goal_price'] = goal

    def _save_stocks(self):
        if self._database:
            stocks = self._stocks
            if self._event_active:
                stocks = deepcopy(stocks)
                for symbol, goal in self._saved_goals.items():
                    stocks[symbol]['goal_price'] = goal
            self._database.save_market(stocks)

    def _load_stocks(self, symbols):
        now = time()
        changed = False
        for index, symbol in enumerate(symbols):
            if symbol in self._stocks:
                stock = self._stocks[symbol]
                if 'base_price' not in stock:
                    stock['base_price'] = stock['price']
                    stock['goal_price'] = self._limit_news_goal(stock, stock['goal_price'])
                    changed = True
                if not stock.get('history_times') or now - stock['history_times'][-1] > 600:
                    stock['history'] = [stock['price']]
                    stock['history_times'] = [now]
                    stock['chart_start'] = now
                continue
            price, _ = _SAMPLE_QUOTES.get(symbol, (round(40 + index * 13.17, 2), 0))
            self._stocks[symbol] = {
                'price': price,
                'base_price': price,
                'goal_price': price,
                'start_price': price,
                'history': [price],
                'history_times': [now],
                'chart_start': now,
                'processed_news': [],
            }
            changed = True
        if changed:
            self._save_stocks()

    def _limit_news_goal(self, stock, goal):
        base = stock['base_price']
        return round(max(0.01, min(1_000_000, max(base * 0.85, min(base * 1.15, goal)))), 2)

    def _update_prices(self):
        now = time()
        interval = 1 if self._event_active else 15
        elapsed_updates = int((now - self._last_update) / interval)
        updates = min(elapsed_updates, 40)
        if updates <= 0:
            return
        if elapsed_updates > 40:
            self._last_update = now - updates * interval
        for _ in range(updates):
            self._last_update += interval
            if self._event_active:
                self._update_event_goals()
            for symbol, stock in self._stocks.items():
                if self._event_active and symbol not in self._saved_goals:
                    continue
                if not stock.get('history_times') or self._last_update <= stock['history_times'][-1]:
                    continue
                price = stock['price']
                goal = stock['goal_price']
                base = stock['base_price']
                if self._event_active:
                    movement = (goal - price) * 0.25
                    if goal != price and abs(movement) < 0.01:
                        movement = goal - price
                else:
                    stock['goal_price'] = round(base + (goal - base) * 0.98, 4)
                    movement = (stock['goal_price'] - price) * 0.02
                    movement += random.uniform(-price * 0.006, price * 0.006)
                    movement = max(-price * 0.01, min(price * 0.01, movement))
                stock['price'] = round(max(0.01, min(1_000_000, price + movement)), 2)
                stock['history'].append(stock['price'])
                stock['history_times'].append(self._last_update)
                while stock['history_times'][0] < self._last_update - 600:
                    stock['history_times'].pop(0)
                    stock['history'].pop(0)
        self._save_stocks()

    def set_goal_price(self, symbol, goal_price):
        if isinstance(goal_price, bool) or not isinstance(goal_price, (int, float)):
            raise ValueError('Goal price must be a number.')
        if not math.isfinite(goal_price) or not 0.01 <= goal_price <= 1_000_000:
            raise ValueError('Goal price must be between 0.01 and 1,000,000.')
        with self._lock:
            if self._event_active:
                raise ValueError('Manual goals are paused during the market event.')
            if symbol not in self._stocks:
                raise ValueError('Unknown stock symbol.')
            previous = self._stocks[symbol]['goal_price']
            revision = self._stocks[symbol].get('goal_revision', 0)
            self._stocks[symbol]['goal_price'] = round(float(goal_price), 2)
            self._stocks[symbol]['goal_revision'] = revision + 1
            try:
                self._save_stocks()
            except Exception:
                self._stocks[symbol]['goal_price'] = previous
                self._stocks[symbol]['goal_revision'] = revision
                raise
            return self._stocks[symbol]['goal_price']

    def has_processed_news(self, symbol, article_id):
        with self._lock:
            stock = self._stocks.get(symbol, {})
            return article_id in stock.get('processed_news', [])

    def initialize_news(self, symbol, articles):
        with self._lock:
            stock = self._stocks[symbol]
            if stock.get('news_initialized') or not articles:
                return False
            previous = deepcopy(stock)
            stock['news_initialized'] = True
            processed = stock.setdefault('processed_news', [])
            for article in articles:
                if article['id'] not in processed:
                    processed.append(article['id'])
            stock['news_reports'] = [
                dict(article, reason='Existing headline: used as background, no price change.')
                for article in articles[:10]
            ]
            try:
                self._save_stocks()
            except Exception:
                self._stocks[symbol] = previous
                raise
            return True

    def apply_news_goal(self, symbol, article_id, previous_goal, new_goal,
                        expected_revision=None, report=None):
        with self._lock:
            stock = self._stocks[symbol]
            if self._event_active:
                raise ValueError('News is paused during the market event.')
            if article_id in stock.get('processed_news', []):
                return False
            changed = stock['goal_price'] != previous_goal
            if expected_revision is not None:
                changed = stock.get('goal_revision', 0) != expected_revision
            if changed:
                raise ValueError('Goal changed while AI was reading the news; retrying.')
            if not math.isfinite(new_goal) or not 0.01 <= new_goal <= 1_000_000:
                raise ValueError('Invalid AI goal price.')
            previous = deepcopy(stock)
            adjusted_goal = stock['goal_price'] * new_goal / previous_goal
            if new_goal != previous_goal:
                stock['goal_price'] = self._limit_news_goal(stock, adjusted_goal)
            stock['goal_revision'] = stock.get('goal_revision', 0) + 1
            stock.setdefault('processed_news', []).append(article_id)
            if report:
                report = dict(report, previous_goal=previous['goal_price'], goal_price=stock['goal_price'])
                reports = stock.setdefault('news_reports', [])
                reports.insert(0, report)
                stock['news_reports'] = reports[:20]
            try:
                self._save_stocks()
            except Exception:
                self._stocks[symbol] = previous
                raise
            return True

    def get_snapshot(self, symbols: tuple[str, ...]) -> dict:
        """Return quotes, histories, news, account data, and positions."""
        with self._lock:
            self._load_stocks(symbols)
            self._update_prices()
            states = deepcopy(self._stocks)
            event = self._event_status()
        stocks = []
        for symbol in symbols:
            state = states[symbol]
            price = state['price']
            change = (price / state['history'][0] - 1) * 100
            stocks.append({
                'symbol': symbol,
                'name': _COMPANY_NAMES.get(symbol, symbol),
                'price': price,
                'goal_price': state['goal_price'],
                'goal_revision': state.get('goal_revision', 0),
                'news_reports': state.get('news_reports', []),
                'change': round(change, 2),
                'history_times': state['history_times'],
                'chart_start': max(state['chart_start'], state['history_times'][-1] - 600),
                'chart_end': max(state['chart_start'] + 600, state['history_times'][-1]),
                'history': {
                    period: state['history'] for period in PERIOD_PATTERNS
                },
            })

        positions = {}
        if 'MSFT' in symbols:
            positions['MSFT'] = {
                'shares': 250,
                'average_entry_price': 290.10,
                'total_investment': 72525.00,
                'total_return': 13012.50,
                'return_percent': 17.9,
            }

        return {
            'event': event,
            'stocks': stocks,
            'news': [
                {'symbol': 'TTT_CORP', 'age': '3m ago', 'headline': 'Triple T did a backflip!!!'},
                {'symbol': 'HAR_VIN', 'age': '18m ago', 'headline': 'Põlva tellis 10000 uut passatit.'},
                {'symbol': 'COL_INC', 'age': '42m ago', 'headline': 'Columbus avastas Ameerika!!!'},
            ],
            'account': {
                'portfolio_value': 142405.12,
                'available_cash': 24812.50,
                'handling_fee': 2.30,
            },
            'positions': positions,
        }


class MarketService:

    def __init__(self, data_source: MarketDataSource, symbol_loader):
        self._data_source = data_source
        self._symbol_loader = symbol_loader

    def get_snapshot(self) -> dict:
        return deepcopy(self._data_source.get_snapshot(self._symbol_loader()))

    def get_event(self):
        """Read shared event status. Dependencies: data source. Side effects: none."""
        return self._data_source.get_event()

    def set_event_active(self, active):
        """Toggle the shared event via the data source; invalid requests raise ValueError.

        Dependencies: symbol loader. Side effects: changes market timing and goals.
        """
        return self._data_source.set_event_active(active, self._symbol_loader())

    def set_goal_price(self, symbol, goal_price):
        symbols = self._symbol_loader()
        if symbol not in symbols:
            raise ValueError('Unknown stock symbol.')
        self._data_source.get_snapshot(symbols)
        return self._data_source.set_goal_price(symbol, goal_price)

    def has_processed_news(self, symbol, article_id):
        return self._data_source.has_processed_news(symbol, article_id)

    def initialize_news(self, symbol, articles):
        self.get_snapshot()
        return self._data_source.initialize_news(symbol, articles)

    def apply_news_goal(self, symbol, article_id, previous_goal, new_goal, **details):
        return self._data_source.apply_news_goal(symbol, article_id, previous_goal, new_goal, **details)


market_service = MarketService(MockMarketDataSource(database), get_stock_symbols)

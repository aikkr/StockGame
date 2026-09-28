"""Provide market snapshots through a replaceable server-side data source."""

from copy import deepcopy
import math
import random
from threading import Lock
from time import monotonic
from typing import Protocol


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
    """Define the provider contract used by the market API.

    Dependencies: none beyond configured stock symbols.
    Side effects: implementation-specific; providers may call external services.
    Failure impact: a provider failure makes market snapshots unavailable.
    """

    def get_snapshot(self, symbols: tuple[str, ...]) -> dict:
        """Build one complete market snapshot for the requested symbols."""
        ...


class MockMarketDataSource:
    def __init__(self):
        self._stocks = {}
        self._last_update = monotonic()
        self._lock = Lock()

    def _load_stocks(self, symbols):
        for index, symbol in enumerate(symbols):
            if symbol in self._stocks:
                continue
            price, _ = _SAMPLE_QUOTES.get(symbol, (round(40 + index * 13.17, 2), 0))
            self._stocks[symbol] = {
                'price': price,
                'goal_price': price,
                'start_price': price,
                'history': [price],
            }

    def _update_prices(self):
        now = monotonic()
        elapsed_updates = int((now - self._last_update) / 15)
        updates = min(elapsed_updates, 240)
        if not updates:
            return
        self._last_update = now if elapsed_updates > 240 else self._last_update + updates * 15
        for _ in range(updates):
            for stock in self._stocks.values():
                price = stock['price']
                goal = stock['goal_price']
                movement = (goal - price) * 0.12 + random.uniform(-goal * 0.003, goal * 0.003)
                movement = max(-goal * 0.01, min(goal * 0.01, movement))
                stock['price'] = round(max(0.01, price + movement), 2)
                stock['history'].append(stock['price'])
                stock['history'] = stock['history'][-240:]

    def set_goal_price(self, symbol, goal_price):
        if isinstance(goal_price, bool) or not isinstance(goal_price, (int, float)):
            raise ValueError('Goal price must be a number.')
        if not math.isfinite(goal_price) or not 0.01 <= goal_price <= 1_000_000:
            raise ValueError('Goal price must be between 0.01 and 1,000,000.')
        with self._lock:
            if symbol not in self._stocks:
                raise ValueError('Unknown stock symbol.')
            self._stocks[symbol]['goal_price'] = round(float(goal_price), 2)
            return self._stocks[symbol]['goal_price']

    def get_snapshot(self, symbols: tuple[str, ...]) -> dict:
        """Return quotes, histories, news, account data, and positions."""
        with self._lock:
            self._load_stocks(symbols)
            self._update_prices()
            states = deepcopy(self._stocks)
        stocks = []
        for symbol in symbols:
            state = states[symbol]
            price = state['price']
            change = (price / state['start_price'] - 1) * 100
            stocks.append({
                'symbol': symbol,
                'name': _COMPANY_NAMES.get(symbol, symbol),
                'price': price,
                'goal_price': state['goal_price'],
                'change': round(change, 2),
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

    def set_goal_price(self, symbol, goal_price):
        symbols = self._symbol_loader()
        if symbol not in symbols:
            raise ValueError('Unknown stock symbol.')
        self._data_source.get_snapshot(symbols)
        return self._data_source.set_goal_price(symbol, goal_price)

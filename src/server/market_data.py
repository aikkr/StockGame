"""Provide market snapshots through a replaceable server-side data source."""

from copy import deepcopy
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
    """Serve deterministic temporary data until a live provider is available.

    Dependencies: configured symbols and module-level sample values.
    Side effects: none.
    Failure impact: none; unknown valid symbols receive generated sample values.
    """

    def get_snapshot(self, symbols: tuple[str, ...]) -> dict:
        """Return quotes, histories, news, account data, and positions."""
        stocks = []
        for index, symbol in enumerate(symbols):
            price, change = _SAMPLE_QUOTES.get(
                symbol,
                (round(40.0 + index * 13.17, 2), round(((index % 7) - 3) * 0.61, 2)),
            )
            stocks.append({
                'symbol': symbol,
                'name': _COMPANY_NAMES.get(symbol, symbol),
                'price': price,
                'change': change,
                'history': {
                    period: [round(price * factor, 2) for factor in pattern]
                    for period, pattern in PERIOD_PATTERNS.items()
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
    """Coordinate configured symbols with the active market data provider.

    Dependencies: a MarketDataSource and a callable symbol loader.
    Side effects: delegates to the configured provider.
    Failure impact: provider errors propagate to the API for explicit handling.
    """

    def __init__(self, data_source: MarketDataSource, symbol_loader):
        """Create the service with replaceable data and configuration sources."""
        self._data_source = data_source
        self._symbol_loader = symbol_loader

    def get_snapshot(self) -> dict:
        """Return a defensive copy of the current provider snapshot."""
        return deepcopy(self._data_source.get_snapshot(self._symbol_loader()))

    def submit_order(self, symbol: str, side: str, quantity: int) -> str:
        """Validate an order against configured symbols and return a demo result."""
        if symbol not in self._symbol_loader():
            raise ValueError('Unknown stock symbol.')
        if side not in {'BUY', 'SELL'}:
            raise ValueError('Order side must be BUY or SELL.')
        if isinstance(quantity, bool) or not isinstance(quantity, int) or not 1 <= quantity <= 1_000_000:
            raise ValueError('Quantity must be a whole number from 1 to 1,000,000.')
        return f'Demo only: {side} {quantity} shares of {symbol}. No order was placed.'

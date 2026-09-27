"""Load and validate server-owned stock configuration from the environment."""

import json
import os
import re

from dotenv import load_dotenv


# These are the symbols currently configured for the project. Keeping the
# fallback in server code makes a fresh checkout usable without a local .env.
DEFAULT_STOCK_SYMBOLS = (
    'MSFT', 'MU', 'TSLA', 'MCD', 'AZN', 'PFE', 'SLS', 'KO', 'AAPL', 'GOOGL',
    'NVDA', 'TSM', 'ASML', 'LMT', 'SHEL', 'EQNR', 'PYPL', 'HOOD', 'CAT',
)

_SYMBOL_PATTERN = re.compile(r'^[A-Z0-9][A-Z0-9.-]{0,14}$')


def get_stock_symbols() -> tuple[str, ...]:
    """Return validated symbols from STOCKS or the server default.

    Dependencies: process environment and an optional local .env file.
    Side effects: loads missing process variables from .env.
    Failure impact: malformed or empty configuration safely uses the default.
    """
    load_dotenv()
    raw_stocks = os.getenv('STOCKS', '').strip()
    if not raw_stocks:
        return DEFAULT_STOCK_SYMBOLS

    try:
        parsed = json.loads(raw_stocks)
    except json.JSONDecodeError:
        parsed = [symbol.strip() for symbol in raw_stocks.split(',')]

    if not isinstance(parsed, list):
        return DEFAULT_STOCK_SYMBOLS

    symbols = []
    for value in parsed:
        if not isinstance(value, str):
            continue
        symbol = value.strip().upper()
        if _SYMBOL_PATTERN.fullmatch(symbol) and symbol not in symbols:
            symbols.append(symbol)
    return tuple(symbols) or DEFAULT_STOCK_SYMBOLS

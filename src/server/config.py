import json
import os
import re
import secrets
from pathlib import Path

from dotenv import load_dotenv, set_key

_SYMBOL_PATTERN = re.compile(r'^[A-Z0-9][A-Z0-9.-]{0,14}$')
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / '.env'
load_dotenv(ENV_PATH)
DEBUG = os.getenv('DEBUG', 'false').strip().lower() == 'true'


def get_storage_secret():
    secret = os.getenv('STOCKGAME_STORAGE_SECRET')
    if not secret or secret == 'replace-with-a-long-random-value':
        secret = secrets.token_urlsafe(32)
        set_key(ENV_PATH, 'STOCKGAME_STORAGE_SECRET', secret)
        os.environ['STOCKGAME_STORAGE_SECRET'] = secret
    return secret


def get_stock_symbols() -> tuple[str, ...]:
    raw_stocks = os.getenv('STOCKS', 'MSFT,AAPL,NVDA').strip()
    try:
        parsed = json.loads(raw_stocks)
    except json.JSONDecodeError:
        parsed = [symbol.strip() for symbol in raw_stocks.split(',')]

    if isinstance(parsed, str):
        parsed = [parsed]
    if not isinstance(parsed, list):
        return ()

    symbols = []
    for value in parsed:
        if not isinstance(value, str):
            continue
        symbol = value.strip().upper()
        if _SYMBOL_PATTERN.fullmatch(symbol) and symbol not in symbols:
            symbols.append(symbol)
    return tuple(symbols)

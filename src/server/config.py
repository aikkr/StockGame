import json
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv, set_key


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / '.env'
load_dotenv(ENV_PATH)
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'


def get_storage_secret():
    secret = os.getenv('STOCKGAME_STORAGE_SECRET')
    if not secret or secret == 'replace-with-a-long-random-value':
        secret = secrets.token_urlsafe(32)
        set_key(ENV_PATH, 'STOCKGAME_STORAGE_SECRET', secret)
        os.environ['STOCKGAME_STORAGE_SECRET'] = secret
    return secret


def get_stock_symbols():
    text = os.getenv('STOCKS', 'MSFT,AAPL,NVDA').strip()
    if text.startswith('['):
        names = json.loads(text)
    else:
        names = text.split(',')

    symbols = []
    for name in names:
        symbol = name.strip().upper()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return tuple(symbols)

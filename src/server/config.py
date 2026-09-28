import json
import os
import re

from dotenv import load_dotenv

_SYMBOL_PATTERN = re.compile(r'^[A-Z0-9][A-Z0-9.-]{0,14}$')

def get_stock_symbols() -> tuple[str, ...]:
    load_dotenv()
    raw_stocks = os.getenv('STOCKS', '').strip()
    try:
        parsed = json.loads(raw_stocks)
    except json.JSONDecodeError:
        parsed = [symbol.strip() for symbol in raw_stocks.split(',')]

    symbols = []
    for value in parsed:
        if not isinstance(value, str):
            continue
        symbol = value.strip().upper()
        if _SYMBOL_PATTERN.fullmatch(symbol) and symbol not in symbols:
            symbols.append(symbol)
    return tuple(symbols)

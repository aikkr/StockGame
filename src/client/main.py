import os
import secrets
import sys
from pathlib import Path

from dotenv import load_dotenv
from nicegui import ui

SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

import server.api 
from pages.home import home_page
from pages.market import market_page

CSS = Path(__file__).with_name('styles.css').read_text()


def _storage_secret() -> str:
    load_dotenv()
    configured = os.getenv('STOCKGAME_STORAGE_SECRET')
    if configured:
        return configured
    print('Warning: STOCKGAME_STORAGE_SECRET is unset; browser sessions reset on server restart.')
    return secrets.token_urlsafe(32)


def setup():
    ui.dark_mode().enable()
    ui.add_css(CSS)


@ui.page('/')
def home():
    setup()
    home_page()


@ui.page('/market')
async def market():
    setup()
    await market_page()


if __name__ in {'__main__', '__mp_main__'}:
    ui.run(
        title='Stockgame', favicon='📈', host='127.0.0.1', port=8080,
        reload=False, show=False, storage_secret=_storage_secret(),
    )

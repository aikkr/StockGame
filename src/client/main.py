import sys
from pathlib import Path

from nicegui import ui

SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

import server.api 
from server.config import get_storage_secret
from pages.home import home_page
from pages.market import market_page

CSS = Path(__file__).with_name('styles.css').read_text()


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
        reload=False, show=False, storage_secret=get_storage_secret(),
    )

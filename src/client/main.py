"""Start the NiceGUI application and register its server API routes."""
import sys
from pathlib import Path

from nicegui import ui

SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

import server.api 
from pages.home import home_page
from pages.market import market_page

CSS = Path(__file__).with_name('styles.css').read_text()


def setup():
    """Apply shared UI settings and CSS to the current page."""
    ui.dark_mode().enable()
    ui.add_css(CSS)


@ui.page('/')
def home():
    """Render the application landing page."""
    setup()
    home_page()


@ui.page('/market')
async def market():
    """Load server-owned market data and render the trading page."""
    setup()
    await market_page()


if __name__ in {'__main__', '__mp_main__'}:
    ui.run(title='Stockgame', favicon='📈', host='127.0.0.1', port=8080, reload=False, show=False)

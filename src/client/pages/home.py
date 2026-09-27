"""Render the Stockgame landing page."""

from nicegui import ui

from charts import integrity_chart
from components import header, metric, plot

def menu_item(number, title, subtitle, action, highlighted=False):
    """Render a landing-page navigation action."""
    with ui.element('button').classes('menu-item' + (' highlighted' if highlighted else '')).on('click', action):
        with ui.column().classes('menu-copy'):
            ui.label(f'{number}. {title}').classes('mono menu-title')
            ui.label(subtitle).classes('muted')
        ui.icon('arrow_forward').classes('menu-arrow')


def home_page():
    """Render the complete landing page without loading market data."""
    header()
    with ui.element('main').classes('home-layout'):
        with ui.column().classes('home-intro'):
            ui.label('INDEX_ZERO PROTOCOL v2.4.1').classes('protocol mono')
            ui.label('Master the messy, high-stakes simulated market').classes('hero-title mono')
            ui.label('Describe your strategy or execute manual orders in an adversarial trading sandbox. '
                     'Backtest logic, watch breaking news tickers, and gain complete sovereignty over simulated wealth.').classes('hero-description muted')
            with ui.column().classes('home-menu'):
                menu_item(1, 'START NEW SIMULATION', 'Reset sandbox and launch index_zero universe', lambda: ui.navigate.to('/market'), True)
                menu_item(2, 'CONTINUE CURRENT SESSION', 'Resume simulated portfolio with active holdings', lambda: ui.navigate.to('/market'))
        with ui.column().classes('panel engine-panel'):
            with ui.row().classes('engine-status'):
                ui.label('● ALL ENGINE SIMULATORS ONLINE').classes('green mono')
                ui.label('MATCH_LATENCY: 12ms').classes('muted mono')
            with ui.element('div').classes('engine-metrics'):
                metric('SIMULATIONS BOOTED', '1,249,012')
                metric('SANDBOX DISCORDS', '24.1K')
                metric('HIGHEST INDEX LIQ', '$4.9M', 'yellow')
            with ui.column().classes('integrity-panel'):
                ui.label('INDEX_ZERO_CORE INTEGRITY HISTORY (7D)').classes('caption mono')
                plot(integrity_chart(), 'integrity-chart')

"""Render small shared UI components without owning market data."""
from nicegui import ui


def header(active=False, portfolio_value=None, available_cash=None):
    """Render the navigation header with optional API-provided account values."""
    with ui.element('header').classes('topbar'):
        with ui.link(target='/').classes('brand'):
            with ui.element('span').classes('brand-icon'):
                ui.icon('trending_up', size='19px')
            ui.label('Stockgame')
        with ui.row().classes('header-stats'):
            for title, value, color in [
                ('PORTFOLIO VALUE', portfolio_value, 'green'),
                ('AVAILABLE CASH', available_cash, 'yellow'),
            ]:
                with ui.column().classes('header-stat'):
                    ui.label(title).classes('caption')
                    ui.label(f'${value:,.2f}' if active else '-- --').classes(f'mono {color}')
            ui.label('◈').classes('avatar').tooltip('Demo player')


def metric(title, value, color=''):
    """Render one title/value metric tile."""
    with ui.column().classes('metric'):
        ui.label(title).classes('caption')
        ui.label(value).classes(f'mono metric-value {color}')


def change_badge(value):
    """Render a signed percentage with direction-aware styling."""
    ui.label(f'{value:+.2f}%').classes('change ' + ('positive' if value >= 0 else 'negative'))


def plot(figure, css_class):
    """Render a Plotly figure with the application's shared configuration."""
    options = figure.to_plotly_json()
    options['config'] = dict(displayModeBar=False, responsive=True)
    return ui.plotly(options).classes(css_class)

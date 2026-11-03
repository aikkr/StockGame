from nicegui import ui


def header(active=False, portfolio_value=None, available_cash=None):
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
                    value_text = '-- --'
                    if active:
                        value_text = f'${value:,.2f}'
                    ui.label(value_text).classes(f'mono {color}')
            ui.label('◈').classes('avatar').tooltip('Demo player')


def metric(title, value, color=''):
    with ui.column().classes('metric'):
        ui.label(title).classes('caption')
        ui.label(value).classes(f'mono metric-value {color}')


def change_badge(value):
    color = 'positive'
    if value < 0:
        color = 'negative'
    ui.label(f'{value:+.2f}%').classes('change ' + color)


def plot(figure, css_class):
    options = figure.to_plotly_json()
    options['config'] = dict(displayModeBar=False, responsive=True)
    return ui.plotly(options).classes(css_class)

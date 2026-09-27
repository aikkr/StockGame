"""Render the trading screen from server API data and local interaction state."""

from nicegui import ui

from api import MarketApiError, get_market, get_news, submit_order
from charts import stock_chart
from components import change_badge, header, metric, plot
from server.sessions import load_user, save_progress


async def market_page():
    user, saved = load_user()
    try:
        market = await get_market()
    except MarketApiError:
        header()
        with ui.column().classes('panel settings-card'):
            ui.label('Market data is unavailable.').classes('section-title')
            ui.label('Refresh the page to try again.').classes('muted')
        return

    stocks = market['stocks']
    if not stocks:
        header()
        with ui.column().classes('panel settings-card'):
            ui.label('No stocks are configured.').classes('section-title')
        return

    account = market['account']
    positions = market['positions']
    stock_by_symbol = {stock['symbol']: stock for stock in stocks}
    selected = stock_by_symbol.get(saved.get('selected_symbol'), stocks[0])
    period = saved.get('period') if saved.get('period') in {'1D', '1W', '1M', '1Y'} else '1W'
    side = saved.get('side') if saved.get('side') in {'BUY', 'SELL'} else 'BUY'
    quantity = saved.get('quantity', 50)
    if isinstance(quantity, bool) or not isinstance(quantity, (int, float)) or quantity <= 0:
        quantity = 50
    state = dict(stock=selected, period=period, search='', side=side, quantity=quantity)
    saved_watchlist = saved.get('watchlist', [])
    if not isinstance(saved_watchlist, list):
        saved_watchlist = []
    watchlist = {
        symbol for symbol in saved_watchlist
        if isinstance(symbol, str) and symbol in stock_by_symbol
    }
    news_items = list(market['news'])

    def persist_progress():
        if user['id'] == 0:
            return
        save_progress(user['id'], {
            'selected_symbol': state['stock']['symbol'],
            'period': state['period'],
            'side': state['side'],
            'quantity': state['quantity'],
            'watchlist': sorted(watchlist),
        })

    async def refresh_news():
        try:
            latest = await get_news()
        except MarketApiError:
            return
        if latest != news_items:
            news_items[:] = latest
            news_panel.refresh()

    def select_stock(stock):
        state['stock'] = stock
        stock_list.refresh()
        chart_panel.refresh()
        order_panel.refresh()
        position_panel.refresh()

    def filter_stocks(value):
        state['search'] = value or ''
        stock_list.refresh()

    @ui.refreshable
    def stock_list():
        search_text = state['search'].lower()
        matches = [
            stock for stock in stocks
            if search_text in (stock['symbol'] + stock['name']).lower()
        ]
        with ui.column().classes('stock-list'):
            for stock in matches:
                with ui.element('button').classes(
                    'stock-row ' + ('active' if stock == state['stock'] else '')
                ).on('click', lambda s=stock: select_stock(s)):
                    with ui.column().classes('stock-name'):
                        ui.label(stock['symbol']).classes('mono')
                        ui.label(stock['name']).classes('muted stock-subtitle')
                    ui.label(f"${stock['price']:,.2f}").classes('mono stock-price')
                    change_badge(stock['change'])
            if not matches:
                ui.label('No matching assets.').classes('muted empty-state')

    def set_period(period):
        state['period'] = period
        chart_panel.refresh()

    @ui.refreshable
    def chart_panel():
        stock = state['stock']
        with ui.column().classes('panel chart-panel'):
            with ui.row().classes('chart-heading'):
                ui.label(stock['symbol'][:2]).classes('ticker-icon mono')
                with ui.column().classes('company-heading'):
                    with ui.row().classes('company-title'):
                        ui.label(stock['symbol']).classes('mono')
                        ui.label('SIM MARKET / INDEX_ZERO').classes('caption')
                    ui.label(stock['name']).classes('muted')
                with ui.column().classes('quote'):
                    ui.label(f"${stock['price']:,.2f}").classes('quote-price mono green')
                    change = stock['price'] - stock['price'] / (1 + stock['change'] / 100)
                    ui.label(f"{change:+.2f} ({stock['change']:+.2f}%)").classes(
                        'mono ' + ('green' if change >= 0 else 'red')
                    )
                with ui.row().classes('period-tabs'):
                    for period in ['1D', '1W', '1M', '1Y']:
                        ui.button(period, color=None, on_click=lambda p=period: set_period(p)).props(
                            'flat dense'
                        ).classes('tiny-tab ' + ('selected' if period == state['period'] else ''))
            plot(stock_chart(stock, state['period']), 'market-chart')

    def set_side(side):
        state['side'] = side
        order_panel.refresh()

    def toggle_watchlist():
        symbol = state['stock']['symbol']
        if symbol in watchlist:
            watchlist.remove(symbol)
        else:
            watchlist.add(symbol)
        watch_panel.refresh()
        order_panel.refresh()

    async def execute():
        quantity = state['quantity']
        if quantity is None or quantity <= 0 or quantity != int(quantity):
            ui.notify('Enter a positive whole number of shares.', type='warning')
            return
        try:
            message = await submit_order(state['stock']['symbol'], state['side'], int(quantity))
            ui.notify(message, type='info')
        except MarketApiError:
            ui.notify('The order could not be submitted.', type='negative')

    @ui.refreshable
    def order_panel():
        stock = state['stock']
        available_cash = account['available_cash']
        handling_fee = account['handling_fee']
        with ui.column().classes('panel order-panel'):
            with ui.row().classes('side-tabs'):
                for side in ['BUY', 'SELL']:
                    ui.button(side, color=None, on_click=lambda s=side: set_side(s)).props('flat').classes(
                        'side-tab ' + ('side-active' if state['side'] == side else '')
                    )
            with ui.row().classes('spread quantity-label'):
                ui.label('QUANTITY (SHARES)').classes('caption')
                max_shares = int((available_cash - handling_fee) / stock['price'])
                ui.label(f'MAX ({max_shares} Shares)').classes('yellow mono')

            def update_quantity(event):
                """Update estimated order value after quantity input changes."""
                state['quantity'] = event.value
                total = (event.value or 0) * stock['price']
                total += handling_fee if state['side'] == 'BUY' else -handling_fee
                cost.set_text(f'${max(0, total):,.2f}')

            quantity = ui.number(
                value=state['quantity'], min=1, step=1, on_change=update_quantity
            ).props(f'outlined dense hide-bottom-space suffix={stock["symbol"]}').classes(
                'quantity-input mono'
            )
            quantity.props('aria-label="Quantity in shares"')
            with ui.column().classes('order-summary'):
                with ui.row().classes('spread'):
                    ui.label('Current Stock Price').classes('muted')
                    ui.label(f"${stock['price']:,.2f}").classes('mono')
                with ui.row().classes('spread estimated yellow'):
                    ui.label('COST' if state['side'] == 'BUY' else 'PROCEEDS')
                    fee = handling_fee if state['side'] == 'BUY' else -handling_fee
                    estimated = max(0, (state['quantity'] or 0) * stock['price'] + fee)
                    cost = ui.label(f'${estimated:,.2f}').classes('mono')
            ui.button('EXECUTE SIMULATED ORDER', color=None, on_click=execute).classes(
                'primary-button execute-button'
            )
            button_text = 'REMOVE FROM WATCHLIST' if stock['symbol'] in watchlist else 'ADD TO WATCHLIST'
            ui.button(button_text, icon='star_border', color=None, on_click=toggle_watchlist).props(
                'flat'
            ).classes('watch-button')

    @ui.refreshable
    def watch_panel():
        with ui.column().classes('panel watch-panel'):
            with ui.row().classes('spread'):
                ui.label('WATCHLIST').classes('section-title')
                ui.label(f'{len(watchlist)} ITEMS').classes('caption mono')
            with ui.column().classes('watch-items'):
                for stock in stocks:
                    if stock['symbol'] not in watchlist:
                        continue
                    with ui.element('button').classes('stock-row').on(
                        'click', lambda s=stock: select_stock(s)
                    ):
                        with ui.column().classes('stock-name'):
                            ui.label(stock['symbol']).classes('mono')
                            ui.label(stock['name']).classes('muted stock-subtitle')
                        ui.label(f"${stock['price']:,.2f}").classes('mono stock-price')
                        change_badge(stock['change'])
                if not watchlist:
                    ui.label('Add an asset to watch it here.').classes('muted empty-state')

    @ui.refreshable
    def position_panel():
        symbol = state['stock']['symbol']
        position = positions.get(symbol)
        with ui.column().classes('panel position-panel'):
            with ui.row().classes('spread'):
                with ui.row().classes('position-title'):
                    ui.icon('work', size='12px').classes('yellow')
                    ui.label('YOUR POSITION DETAILS').classes('section-title')
                ui.label('HOLDING ACTIVE' if position else 'NO POSITION').classes('holding mono')
            with ui.element('div').classes('position-metrics'):
                if position:
                    values = [
                        ('SHARES OWNED', f"{position['shares']} Units", ''),
                        ('AVG ENTRY PRICE', f"${position['average_entry_price']:,.2f}", ''),
                        ('TOTAL INVESTMENT', f"${position['total_investment']:,.2f}", ''),
                        ('TOTAL RETURN', (
                            f"${position['total_return']:+,.2f} "
                            f"({position['return_percent']:+.1f}%)"
                        ), 'green'),
                    ]
                    for title, value, color in values:
                        metric(title, value, color)
                else:
                    for title, value in [
                        ('SHARES OWNED', '0 Units'), ('AVG ENTRY PRICE', '—'),
                        ('TOTAL INVESTMENT', '$0.00'), ('TOTAL RETURN', '—'),
                    ]:
                        metric(title, value)

    @ui.refreshable
    def news_panel():
        with ui.column().classes('panel news-panel'):
            ui.label('Market Wire (Live)').classes('section-title')
            for article in news_items:
                with ui.column().classes('news-item'):
                    with ui.row().classes('news-meta'):
                        ui.label(article['symbol']).classes('yellow mono')
                        ui.label('• ' + article['age']).classes('muted')
                    ui.label(article['headline'])
            if not news_items:
                ui.label('Waiting for the first market update...').classes('muted empty-state')

    header(
        active=True,
        portfolio_value=account['portfolio_value'],
        available_cash=account['available_cash'],
    )
    with ui.element('main').classes('market-layout'):
        with ui.column().classes('left-column'):
            news_panel()
            with ui.column().classes('panel stocks-panel'):
                ui.label('Stocks').classes('section-title')
                search = ui.input(
                    placeholder='Search assets...', on_change=lambda e: filter_stocks(e.value)
                ).props('dense borderless').classes('search-input')
                with search.add_slot('prepend'):
                    ui.icon('search', size='14px')
                stock_list()
        with ui.column().classes('center-column'):
            chart_panel()
            position_panel()
        with ui.column().classes('right-column'):
            order_panel()
            watch_panel()

    ui.timer(10, refresh_news)
    ui.timer(20, persist_progress)

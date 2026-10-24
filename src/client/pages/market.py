import logging
import math
import sqlite3

from nicegui import ui

from api import MarketApiError, get_market, get_news, set_goal_price, set_market_event
from charts import stock_chart
from components import change_badge, header, metric, plot
from portfolio import TradeError, apply_trade, load_cash, load_portfolio, portfolio_value
from server import config
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
    stock_by_symbol = {stock['symbol']: stock for stock in stocks}
    prices = {symbol: stock['price'] for symbol, stock in stock_by_symbol.items()}
    selected = stock_by_symbol.get(saved.get('selected_symbol'), stocks[0])
    period = saved.get('period') if saved.get('period') in {'1D', '1W', '1M', '1Y'} else '1W'
    side = saved.get('side') if saved.get('side') in {'BUY', 'SELL'} else 'BUY'
    quantity = saved.get('quantity', 50)
    if (
        isinstance(quantity, bool)
        or not isinstance(quantity, (int, float))
        or not math.isfinite(quantity)
        or not 0 < quantity <= 1_000_000
    ):
        quantity = 50
    state = dict(
        stock=selected,
        period=period,
        search='',
        side=side,
        quantity=quantity,
        cash=load_cash(saved.get('cash'), account['available_cash']),
    )
    portfolio = load_portfolio(saved.get('portfolio'), set(stock_by_symbol))
    saved_watchlist = saved.get('watchlist', [])
    if not isinstance(saved_watchlist, list):
        saved_watchlist = []
    watchlist = {
        symbol for symbol in saved_watchlist
        if isinstance(symbol, str) and symbol in stock_by_symbol
    }
    news_items = list(market['news'])
    selected_news = {'article': None}
    event = dict(market['event'])
    seen_event = {'id': event['id'] if not event['active'] else 0, 'active': False}

    def show_event_popup():
        if event['id'] != seen_event['id'] or event['active'] != seen_event['active']:
            seen_event.update(id=event['id'], active=event['active'])
            event_dialog_content.refresh()
            event_dialog.open()

    async def toggle_event():
        try:
            await set_market_event(not event['active'])
        except MarketApiError:
            ui.notify('Could not change the market event. Try again.', type='negative')
            return
        await refresh_market()

    def persist_progress():
        if user['id'] == 0:
            return True
        progress = {
            '_generation': saved.get('_generation'),
            'selected_symbol': state['stock']['symbol'],
            'period': state['period'],
            'side': state['side'],
            'quantity': state['quantity'],
            'watchlist': sorted(watchlist),
            'portfolio': dict(portfolio),
            'cash': state['cash'],
        }
        try:
            save_progress(user['id'], progress, saved)
        except ValueError as error:
            ui.notify(str(error), type='negative')
            return False
        except sqlite3.Error:
            logging.getLogger(__name__).exception('Could not save player progress')
            ui.notify('Progress could not be saved. Check database access and disk space.', type='negative')
            return False
        saved.clear()
        saved.update(progress)
        return True

    async def refresh_news():
        try:
            latest = await get_news()
        except MarketApiError:
            return
        if latest['news'] != news_items:
            news_items[:] = latest['news']
            news_panel.refresh()

    async def refresh_market():
        try:
            latest = await get_market()
        except MarketApiError:
            return
        event_changed = latest['event'] != event
        event.clear()
        event.update(latest['event'])
        show_event_popup()
        if latest['news'] != news_items:
            news_items[:] = latest['news']
            news_panel.refresh()
        if config.DEBUG and event_changed:
            event_panel.refresh()
        prices_changed = any(
            stock_by_symbol.get(stock['symbol']) != stock for stock in latest['stocks']
        )
        if not prices_changed and not event_changed:
            return
        for updated in latest['stocks']:
            stock = stock_by_symbol.get(updated['symbol'])
            if stock:
                stock.update(updated)
                prices[updated['symbol']] = updated['price']
        stock_list.refresh()
        chart_panel.refresh()
        order_panel.refresh()
        watch_panel.refresh()
        position_panel.refresh()
        if config.DEBUG:
            debug_panel.refresh()
        account_header.refresh()

    def select_stock(stock):
        state['stock'] = stock
        persist_progress()
        stock_list.refresh()
        chart_panel.refresh()
        order_panel.refresh()
        position_panel.refresh()
        if config.DEBUG:
            debug_panel.refresh()

    def filter_stocks(value):
        state['search'] = value or ''
        stock_list.refresh()

    def open_news(article):
        selected_news['article'] = article
        news_dialog_content.refresh()
        news_dialog.open()

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
            plot(stock_chart(stock, state['period']), 'market-chart')

    def set_side(side):
        state['side'] = side
        persist_progress()
        order_panel.refresh()

    def toggle_watchlist():
        previous = set(watchlist)
        symbol = state['stock']['symbol']
        if symbol in watchlist:
            watchlist.remove(symbol)
        else:
            watchlist.add(symbol)
        if not persist_progress():
            watchlist.clear()
            watchlist.update(previous)
        watch_panel.refresh()
        order_panel.refresh()

    async def execute():
        quantity = state['quantity']
        if (
            isinstance(quantity, bool)
            or not isinstance(quantity, (int, float))
            or quantity <= 0
            or quantity > 1_000_000
            or not float(quantity).is_integer()
        ):
            ui.notify('Enter a positive whole number of shares.', type='warning')
            return
        stock = state['stock']
        previous_cash = state['cash']
        previous_portfolio = dict(portfolio)
        try:
            state['cash'] = apply_trade(
                portfolio,
                state['cash'],
                stock['symbol'],
                state['side'],
                int(quantity),
                stock['price'],
                account['handling_fee'],
            )
        except TradeError as error:
            ui.notify(str(error), type='warning')
            return
        if not persist_progress():
            state['cash'] = previous_cash
            portfolio.clear()
            portfolio.update(previous_portfolio)
            return
        ui.notify(
            f'{state["side"]} order completed: {int(quantity)} shares of {stock["symbol"]}.',
            type='positive',
        )
        account_header.refresh()
        order_panel.refresh()
        position_panel.refresh()

    @ui.refreshable
    def order_panel():
        stock = state['stock']
        available_cash = state['cash']
        handling_fee = account['handling_fee']
        with ui.column().classes('panel order-panel'):
            with ui.row().classes('side-tabs'):
                for side in ['BUY', 'SELL']:
                    ui.button(side, color=None, on_click=lambda s=side: set_side(s)).props('flat').classes(
                        'side-tab ' + ('side-active' if state['side'] == side else '')
                    )
            with ui.row().classes('spread quantity-label'):
                ui.label('QUANTITY (SHARES)').classes('caption')
                if state['side'] == 'BUY':
                    max_shares = max(0, int((available_cash - handling_fee) / stock['price']))
                else:
                    max_shares = portfolio.get(stock['symbol'], 0)
                ui.label(f'MAX ({max_shares} Shares)').classes('yellow mono')

            def update_quantity(event):
                """Update estimated order value after quantity input changes."""
                if event.value is None or not math.isfinite(event.value):
                    return
                state['quantity'] = event.value
                persist_progress()
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
    def debug_panel():
        stock = state['stock']

        async def save_goal():
            try:
                goal = await set_goal_price(stock['symbol'], target.value)
            except MarketApiError:
                ui.notify('Enter a goal price from 0.01 to 1,000,000.', type='warning')
                return
            stock['goal_price'] = goal
            ui.notify(f'{stock["symbol"]} goal changed to ${goal:,.2f}.', type='positive')
            debug_panel.refresh()

        with ui.column().classes('panel debug-panel'):
            target = ui.number(
                label=f'{stock["symbol"]} goal price',
                value=round(stock['goal_price'], 2),
                min=0.01,
                max=1_000_000,
                step=0.01,
            ).props('outlined dense hide-bottom-space').classes('quantity-input mono')
            goal_button = ui.button('SET GOAL PRICE', on_click=save_goal).classes('primary-button debug-button')
            if event['active']:
                target.disable()
                goal_button.disable()

    @ui.refreshable
    def position_panel():
        symbol = state['stock']['symbol']
        shares = portfolio.get(symbol, 0)
        with ui.column().classes('panel position-panel'):
            with ui.row().classes('spread'):
                with ui.row().classes('position-title'):
                    ui.icon('work', size='12px').classes('yellow')
                    ui.label('YOUR POSITION DETAILS').classes('section-title')
                ui.label('HOLDING ACTIVE' if shares else 'NO POSITION').classes('holding mono')
            with ui.element('div').classes('position-metrics'):
                if shares:
                    market_value = shares * state['stock']['price']
                    holdings_value = sum(prices[ticker] * amount for ticker, amount in portfolio.items())
                    values = [
                        ('SHARES OWNED', f'{shares} Units', ''),
                        ('CURRENT PRICE', f"${state['stock']['price']:,.2f}", ''),
                        ('MARKET VALUE', f'${market_value:,.2f}', ''),
                        ('PORTFOLIO SHARE', f'{market_value / holdings_value:.1%}', 'green'),
                    ]
                    for title, value, color in values:
                        metric(title, value, color)
                else:
                    for title, value in [
                        ('SHARES OWNED', '0 Units'), ('CURRENT PRICE', '—'),
                        ('MARKET VALUE', '$0.00'), ('PORTFOLIO SHARE', '—'),
                    ]:
                        metric(title, value)

    @ui.refreshable
    def news_panel():
        with ui.column().classes('panel news-panel'):
            ui.label('Market Wire (Live)').classes('section-title')
            for article in news_items:
                with ui.element('button').classes('news-item').on(
                    'click', lambda current=article: open_news(current)
                ):
                    with ui.row().classes('news-meta'):
                        ui.label(article.get('symbol', '')).classes('yellow mono')
                        ui.label('• ' + article.get('age', '')).classes('muted')
                    ui.label(article.get('headline', 'Untitled article'))
            if not news_items:
                ui.label('Waiting for the first market update...').classes('muted empty-state')

    @ui.refreshable
    def news_dialog_content():
        article = selected_news['article'] or {}
        with ui.row().classes('news-dialog-heading'):
            with ui.column().classes('news-dialog-title'):
                ui.label(article.get('symbol', '')).classes('yellow mono')
                ui.label(article.get('headline', 'Untitled article')).classes('news-dialog-headline')
            ui.button(icon='close', on_click=news_dialog.close).props(
                'flat round dense aria-label="Close article"'
            ).classes('news-dialog-close')
        metadata = ' • '.join(
            value for value in (article.get('provider', ''), article.get('date', '')) if value
        )
        if metadata:
            ui.label(metadata).classes('muted news-dialog-meta')
        ui.separator().classes('news-dialog-separator')
        ui.label(
            article.get('body') or 'No article text was provided by Yahoo Finance.'
        ).classes('news-dialog-body')
        if article.get('url'):
            ui.link('READ ORIGINAL ARTICLE', article['url'], new_tab=True).classes(
                'primary-button news-dialog-link'
            )

    with ui.dialog() as news_dialog:
        with ui.card().classes('news-dialog-card'):
            news_dialog_content()

    @ui.refreshable
    def event_dialog_content():
        phase = 'awake' if event['active'] else 'asleep'
        with ui.card().classes(f'event-popup-card event-popup-{phase}'):
            ui.button(icon='close', on_click=event_dialog.close).props(
                'flat round dense aria-label="Close event popup"'
            ).classes('event-popup-close')
            ui.icon('campaign' if event['active'] else 'bedtime').classes('event-popup-icon')
            ui.label(
                'TRUMP HAS WAKEN UP!!!!' if event['active'] else 'Trump went sleep.'
            ).classes('event-popup-title')

    with ui.dialog().classes('event-popup') as event_dialog:
        event_dialog_content()

    @ui.refreshable
    def event_panel():
        with ui.column().classes('panel debug-panel'):
            ui.label('Trump has woken up').classes('yellow')
            ui.button(
                'END EVENT' if event['active'] else 'TRIGGER EVENT', on_click=toggle_event,
            ).classes('primary-button')

    @ui.refreshable
    def account_header():
        """Render account totals calculated from client-side portfolio state."""
        header(
            active=True,
            portfolio_value=portfolio_value(portfolio, prices, state['cash']),
            available_cash=state['cash'],
        )

    account_header()
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
            if config.DEBUG:
                event_panel()
                debug_panel()

    ui.timer(10, refresh_news)
    ui.timer(1, refresh_market)
    show_event_popup()

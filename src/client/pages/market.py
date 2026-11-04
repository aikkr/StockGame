from nicegui import ui

from api import MarketApiError, get_market, set_goal_price, set_market_event
from charts import stock_chart
from components import change_badge, header, metric, plot
from server.portfolio import TradeError, apply_trade, portfolio_value
from server import config
from server.sessions import load_user, save_progress


async def market_page():
    """Build the NiceGUI market from the API and saved session; polls quotes and news.

    Side effects: renders UI and persists player actions. API failures show an unavailable state.
    """
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
    stock_by_symbol = {}
    prices = {}
    for stock in stocks:
        symbol = stock['symbol']
        stock_by_symbol[symbol] = stock
        prices[symbol] = stock['price']
    selected = stock_by_symbol.get(saved.get('selected_symbol'), stocks[0])
    period = saved.get('period', '1W')
    side = saved.get('side', 'BUY')
    quantity = saved.get('quantity', 50)
    state = dict(
        stock=selected,
        period=period,
        search='',
        side=side,
        quantity=quantity,
        cash=saved.get('cash', account['available_cash']),
    )

    portfolio = dict(saved.get('portfolio', {}))
    watchlist = set(saved.get('watchlist', []))
    news_items = list(market['news'])
    news_status = dict(market.get('news_status', {}))
    selected_news = {'article': None}
    stock_rows = {}
    no_matching_assets = None
    event = dict(market['event'])
    seen_event = {'id': 0, 'active': False}
    if not event['active']:
        seen_event['id'] = event['id']

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
        saved.clear()
        saved.update(progress)
        return True

    async def refresh_market():
        try:
            latest = await get_market()
        except MarketApiError:
            return
        event_changed = latest['event'] != event
        event.clear()
        event.update(latest['event'])
        show_event_popup()
        latest_news_status = latest.get('news_status', {})
        ai_status_changed = latest_news_status != news_status
        news_status.clear()
        news_status.update(latest_news_status)
        if latest['news'] != news_items:
            news_items[:] = latest['news']
            news_panel.refresh()
            selected_article = selected_news['article']
            if selected_article:
                for article in news_items:
                    if article.get('evaluation_id', article['id']) == selected_article.get('evaluation_id', selected_article['id']):
                        selected_news['article'] = article
                        news_dialog_content.refresh()
                        break
        if config.DEBUG and event_changed:
            event_panel.refresh()
        prices_changed = False
        for stock in latest['stocks']:
            if stock_by_symbol[stock['symbol']] != stock:
                prices_changed = True
                break
        if not prices_changed and not event_changed:
            if config.DEBUG and ai_status_changed:
                debug_panel.refresh()
            return
        for updated in latest['stocks']:
            stock = stock_by_symbol.get(updated['symbol'])
            if stock:
                stock.update(updated)
                prices[updated['symbol']] = updated['price']
        update_stock_list()
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
        update_stock_list()
        chart_panel.refresh()
        order_panel.refresh()
        position_panel.refresh()
        if config.DEBUG:
            debug_panel.refresh()

    def filter_stocks(value):
        state['search'] = value or ''
        update_stock_list()

    def open_news(article):
        selected_news['article'] = article
        news_dialog_content.refresh()
        news_dialog.open()

    def update_stock_list():
        """Update existing NiceGUI rows from page state; preserves the list element and scroll position."""
        search_text = state['search'].lower()
        visible_count = 0
        for stock in stocks:
            row, price_label, change_label = stock_rows[stock['symbol']]
            company_text = (stock['symbol'] + stock['name']).lower()
            visible = search_text in company_text
            row.set_visibility(visible)
            visible_count += visible
            row.classes(add='active' if stock is state['stock'] else '',
                        remove='' if stock is state['stock'] else 'active')
            price_label.set_text(f"${stock['price']:,.2f}")
            change_label.set_text(f"{stock['change']:+.2f}%")
            positive = stock['change'] >= 0
            change_label.classes(add='positive' if positive else 'negative',
                                 remove='negative' if positive else 'positive')
        no_matching_assets.set_visibility(visible_count == 0)

    def stock_list():
        """Build persistent NiceGUI stock rows once; stores references for later updates without rebuilding."""
        nonlocal no_matching_assets
        with ui.column().classes('stock-list'):
            for stock in stocks:
                def choose_stock(stock=stock):
                    select_stock(stock)

                row_class = 'stock-row'
                if stock == state['stock']:
                    row_class += ' active'
                with ui.element('button').classes(row_class).on('click', choose_stock) as row:
                    with ui.column().classes('stock-name'):
                        ui.label(stock['symbol']).classes('mono')
                        ui.label(stock['name']).classes('muted stock-subtitle')
                    price_label = ui.label(f"${stock['price']:,.2f}").classes('mono stock-price')
                    color = 'positive' if stock['change'] >= 0 else 'negative'
                    change_label = ui.label(f"{stock['change']:+.2f}%").classes('change ' + color)
                stock_rows[stock['symbol']] = (row, price_label, change_label)
            no_matching_assets = ui.label('No matching assets.').classes('muted empty-state')
        update_stock_list()

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
                    color = 'green'
                    if change < 0:
                        color = 'red'
                    ui.label(f"{change:+.2f} ({stock['change']:+.2f}%)").classes('mono ' + color)
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
        stock = state['stock']
        previous_cash = state['cash']
        previous_portfolio = dict(portfolio)
        try:
            state['cash'] = apply_trade(
                portfolio,
                state['cash'],
                stock['symbol'],
                state['side'],
                quantity,
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
                    def choose_side(side=side):
                        set_side(side)

                    button_class = 'side-tab'
                    if state['side'] == side:
                        button_class += ' side-active'
                    ui.button(side, color=None, on_click=choose_side).props('flat').classes(button_class)
            with ui.row().classes('spread quantity-label'):
                ui.label('QUANTITY (SHARES)').classes('caption')
                if state['side'] == 'BUY':
                    max_shares = max(0, int((available_cash - handling_fee) / stock['price']))
                else:
                    max_shares = portfolio.get(stock['symbol'], 0)
                ui.label(f'MAX ({max_shares} Shares)').classes('yellow mono')

            def update_quantity(event):
                if event.value is None:
                    return
                state['quantity'] = event.value
                persist_progress()
                total = (event.value or 0) * stock['price']
                if state['side'] == 'BUY':
                    total += handling_fee
                else:
                    total -= handling_fee
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
                    if state['side'] == 'BUY':
                        ui.label('COST')
                        fee = handling_fee
                    else:
                        ui.label('PROCEEDS')
                        fee = -handling_fee
                    estimated = max(0, (state['quantity'] or 0) * stock['price'] + fee)
                    cost = ui.label(f'${estimated:,.2f}').classes('mono')
            ui.button('EXECUTE SIMULATED ORDER', color=None, on_click=execute).classes(
                'primary-button execute-button'
            )
            button_text = 'ADD TO WATCHLIST'
            if stock['symbol'] in watchlist:
                button_text = 'REMOVE FROM WATCHLIST'
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
                    def choose_watched_stock(stock=stock):
                        select_stock(stock)

                    with ui.element('button').classes('stock-row').on('click', choose_watched_stock):
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
            ui.label(f'Current {stock["symbol"]} goal: ${stock["goal_price"]:,.2f}').classes('mono yellow')
            ui.label(news_status.get('ai', 'Waiting for news.')).classes('muted text-xs')
            ui.label(f'Pending AI evaluations: {news_status.get("pending", 0)}').classes('muted text-xs')
            reports = stock.get('news_reports', [])
            if reports:
                report = reports[0]
                ui.label(f'Last AI evaluation: {report.get("checked_at", "Earlier")}').classes('caption')
                ui.label(report['headline']).classes('text-xs')
                if report.get('previous_goal') is not None and report.get('goal_price') is not None:
                    ui.label(
                        f'${report["previous_goal"]:,.2f} → ${report["goal_price"]:,.2f}'
                    ).classes('mono')
                ui.label(report['reason']).classes('muted text-xs')
                if report.get('requested_goal') is not None and report['requested_goal'] != report.get('goal_price'):
                    ui.label('Applied goal limited to ±15% of the base price.').classes('muted text-xs')
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
                holding_text = 'NO POSITION'
                if shares:
                    holding_text = 'HOLDING ACTIVE'
                ui.label(holding_text).classes('holding mono')
            with ui.element('div').classes('position-metrics'):
                if shares:
                    market_value = shares * state['stock']['price']
                    holdings_value = portfolio_value(portfolio, prices, 0)
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
                def read_article(article=article):
                    open_news(article)

                with ui.element('button').classes('news-item').on(
                    'click', read_article
                ):
                    with ui.row().classes('news-meta'):
                        ui.label(article.get('symbol', '')).classes('yellow mono')
                        ui.label('• ' + article.get('age', '')).classes('muted')
                        if article.get('previously_processed'):
                            ui.label('• Previously read').classes('muted')
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
        metadata_parts = []
        for value in (article.get('provider', ''), article.get('date', '')):
            if value:
                metadata_parts.append(value)
        metadata = ' • '.join(metadata_parts)
        if metadata:
            ui.label(metadata).classes('muted news-dialog-meta')
        ui.separator().classes('news-dialog-separator')
        ui.label(
            article.get('body') or 'No article text was provided by Yahoo Finance.'
        ).classes('news-dialog-body')
        ui.label('AI evaluation').classes('caption')
        ui.label(article.get('ai_reason') or f'AI {article.get("ai_status", "queued")}.').classes('muted text-xs')
        if article.get('previous_goal') is not None and article.get('goal_price') is not None:
            ui.label(f'Goal: ${article["previous_goal"]:,.2f} → ${article["goal_price"]:,.2f}').classes('mono')
        if article.get('url'):
            ui.link('READ ORIGINAL ARTICLE', article['url'], new_tab=True).classes(
                'primary-button news-dialog-link'
            )

    with ui.dialog() as news_dialog:
        with ui.card().classes('news-dialog-card'):
            news_dialog_content()

    @ui.refreshable
    def event_dialog_content():
        if event['active']:
            phase = 'awake'
            icon = 'campaign'
            title = 'TRUMP HAS WAKEN UP!!!!'
        else:
            phase = 'asleep'
            icon = 'bedtime'
            title = 'Trump went sleep.'
        with ui.card().classes(f'event-popup-card event-popup-{phase}'):
            ui.button(icon='close', on_click=event_dialog.close).props(
                'flat round dense aria-label="Close event popup"'
            ).classes('event-popup-close')
            ui.icon(icon).classes('event-popup-icon')
            ui.label(title).classes('event-popup-title')

    with ui.dialog().classes('event-popup') as event_dialog:
        event_dialog_content()

    @ui.refreshable
    def event_panel():
        with ui.column().classes('panel debug-panel'):
            ui.label('Trump has woken up').classes('yellow')
            button_text = 'TRIGGER EVENT'
            if event['active']:
                button_text = 'END EVENT'
            ui.button(button_text, on_click=toggle_event).classes('primary-button')

    @ui.refreshable
    def account_header():
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
                def search_changed(event):
                    filter_stocks(event.value)

                search = ui.input(
                    placeholder='Search assets...', on_change=search_changed
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

    ui.timer(1, refresh_market)
    show_event_popup()

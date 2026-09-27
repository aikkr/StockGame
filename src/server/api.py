from fastapi import HTTPException
from nicegui import app

from server.config import get_stock_symbols
from server.market_data import MarketService, MockMarketDataSource
from server.news import get_news


market_service = MarketService(MockMarketDataSource(), get_stock_symbols)


@app.get('/api/market')
def get_market() -> dict:
    snapshot = market_service.get_snapshot()
    snapshot['news'] = get_news()
    return snapshot


@app.get('/api/news')
def get_latest_news() -> dict:
    return {'news': get_news()}


@app.post('/api/orders')
def post_order(order: dict) -> dict:
    try:
        message = market_service.submit_order(
            symbol=order.get('symbol'),
            side=order.get('side'),
            quantity=order.get('quantity'),
        )
    except (AttributeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {'message': message}

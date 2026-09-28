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


@app.post('/api/market/goal')
def set_goal_price(data: dict) -> dict:
    try:
        goal_price = market_service.set_goal_price(data.get('symbol'), data.get('goal_price'))
    except (AttributeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {'goal_price': goal_price}

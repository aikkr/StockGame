from fastapi import HTTPException
from nicegui import app

from server import config
from server.market_data import market_service
from server.news import get_news, get_news_status


@app.post('/api/market/event')
def set_market_event(data: dict) -> dict:
    """Change the shared event via the market service; disabled debug tools return 403."""
    if not config.DEBUG:
        raise HTTPException(status_code=403, detail='Debug tools are disabled.')
    try:
        return market_service.set_event_active(data.get('active'))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get('/api/market')
def get_market() -> dict:
    snapshot = market_service.get_snapshot()
    snapshot['news'] = get_news()
    snapshot['news_status'] = get_news_status()
    return snapshot


@app.get('/api/news')
def get_latest_news() -> dict:
    return {'news': get_news(), 'status': get_news_status()}


@app.post('/api/market/goal')
def set_goal_price(data: dict) -> dict:
    """Set a shared goal via the market service; disabled debug tools return 403."""
    if not config.DEBUG:
        raise HTTPException(status_code=403, detail='Debug tools are disabled.')
    try:
        goal_price = market_service.set_goal_price(data.get('symbol'), data.get('goal_price'))
    except (AttributeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {'goal_price': goal_price}

"""Expose the server-owned market data contract over HTTP."""

from fastapi import HTTPException
from nicegui import app

from server.config import get_stock_symbols
from server.market_data import MarketService, MockMarketDataSource


market_service = MarketService(MockMarketDataSource(), get_stock_symbols)


@app.get('/api/market')
def get_market() -> dict:
    """Return stocks and all market-screen data in one consistent snapshot.

    Dependencies: configured MarketService provider.
    Side effects: provider-specific reads.
    Failure impact: HTTP 500 if the provider cannot create a snapshot.
    """
    return market_service.get_snapshot()


@app.post('/api/orders')
def post_order(order: dict) -> dict:
    """Validate a simulated order and return its server-side result.

    Dependencies: configured MarketService and JSON request data.
    Side effects: currently none; a future order provider may persist changes.
    Failure impact: invalid input returns HTTP 400 without placing an order.
    """
    try:
        message = market_service.submit_order(
            symbol=order.get('symbol'),
            side=order.get('side'),
            quantity=order.get('quantity'),
        )
    except (AttributeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {'message': message}

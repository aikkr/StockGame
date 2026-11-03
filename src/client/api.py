import httpx
from nicegui import app


class MarketApiError(RuntimeError):
    pass


async def get_market():
    return await _request('GET', '/api/market')


async def set_goal_price(symbol, goal_price):
    result = await _request('POST', '/api/market/goal', {
        'symbol': symbol,
        'goal_price': goal_price,
    })
    return result['goal_price']


async def set_market_event(active):
    return await _request('POST', '/api/market/event', {'active': active})


async def _request(method, path, data=None):
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url='http://stockgame.local') as client:
            response = await client.request(method, path, json=data)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as error:
        raise MarketApiError('The market service is currently unavailable.') from error

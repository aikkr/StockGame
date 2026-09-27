import httpx
from nicegui import app


class MarketApiError(RuntimeError):
    """Represent a server API failure that the UI can display safely.

    Dependencies: an unsuccessful API response or transport exception.
    Side effects: none.
    Failure impact: callers should show a non-sensitive error state.
    """


async def get_market() -> dict:
    return await _request('GET', '/api/market')


async def submit_order(symbol: str, side: str, quantity: int) -> str:
    result = await _request('POST', '/api/orders', json={
        'symbol': symbol,
        'side': side,
        'quantity': quantity,
    })
    return result['message']


async def _request(method: str, path: str, **kwargs) -> dict:
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url='http://stockgame.local') as client:
            response = await client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError, KeyError) as error:
        raise MarketApiError('The market service is currently unavailable.') from error

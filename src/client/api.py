import httpx
from nicegui import app


class MarketApiError(RuntimeError):
    """Represent a server API failure that the UI can display safely.

    Dependencies: an unsuccessful API response or transport exception.
    Side effects: none.
    Failure impact: callers should show a non-sensitive error state.
    """


async def get_market() -> dict:
    """Load the current server-owned market snapshot."""
    return await _request('GET', '/api/market')


async def get_news() -> list[dict]:
    """Load the latest news feed without refreshing the page."""
    result = await _request('GET', '/api/news')
    return result['news']


async def set_goal_price(symbol: str, goal_price: float) -> float:
    result = await _request('POST', '/api/market/goal', json={
        'symbol': symbol,
        'goal_price': goal_price,
    })
    return result['goal_price']


async def _request(method: str, path: str, **kwargs) -> dict:
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url='http://stockgame.local') as client:
            response = await client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError, KeyError) as error:
        raise MarketApiError('The market service is currently unavailable.') from error

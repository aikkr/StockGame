"""Validate client portfolio state and apply simulated trades.

Dependencies: only Python's standard library.
Side effects: trade operations mutate the explicitly supplied portfolio mapping.
Failure impact: invalid orders are rejected without changing any holdings.
"""

from math import isfinite


class TradeError(ValueError):
    """Report an invalid or unaffordable simulated trade.

    Dependencies: none.
    Side effects: none.
    Failure impact: the requested trade is not applied.
    """


def load_portfolio(value: object, valid_symbols: set[str]) -> dict[str, int]:
    """Return valid positive whole-share holdings from saved client data.

    Dependencies: the currently configured ticker symbols.
    Side effects: none.
    Failure impact: invalid holdings are omitted instead of entering the game state.
    """
    if not isinstance(value, dict):
        return {}

    portfolio = {}
    for symbol, amount in value.items():
        if (
            isinstance(symbol, str)
            and symbol in valid_symbols
            and isinstance(amount, int)
            and not isinstance(amount, bool)
            and amount > 0
        ):
            portfolio[symbol] = amount
    return portfolio


def load_cash(value: object, default: float) -> float:
    """Return a valid saved cash balance or a safe default.

    Dependencies: a non-negative default balance supplied by the market snapshot.
    Side effects: none.
    Failure impact: corrupt saved cash is replaced by the default balance.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        cash = float(value)
        if isfinite(cash) and cash >= 0:
            return cash
    return float(default)


def apply_trade(
    portfolio: dict[str, int],
    cash: float,
    symbol: str,
    side: str,
    quantity: int,
    price: float,
    handling_fee: float,
) -> float:
    """Apply a validated buy or sell to a client-owned portfolio.

    Dependencies: a mutable ticker-to-share mapping and current market pricing.
    Side effects: mutates ``portfolio`` only after every validation succeeds.
    Failure impact: raises TradeError and leaves the portfolio unchanged.
    """
    if not symbol or side not in {'BUY', 'SELL'}:
        raise TradeError('Invalid order.')
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        raise TradeError('Enter a positive whole number of shares.')
    if quantity > 1_000_000:
        raise TradeError('An order cannot exceed 1,000,000 shares.')
    if not all(
        isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)
        for value in (cash, price, handling_fee)
    ) or cash < 0 or price <= 0 or handling_fee < 0:
        raise TradeError('Invalid account or market data.')
    held = portfolio.get(symbol, 0)
    if isinstance(held, bool) or not isinstance(held, int) or held < 0:
        raise TradeError('Invalid portfolio data.')

    if side == 'BUY':
        cost = price * quantity + handling_fee
        if cost > cash:
            raise TradeError('Not enough available cash for this order.')
        portfolio[symbol] = held + quantity
        return cash - cost

    if quantity > held:
        raise TradeError(f'You only own {held} shares of {symbol}.')
    proceeds = price * quantity - handling_fee
    if proceeds < 0:
        raise TradeError('The sale value does not cover the handling fee.')
    remaining = held - quantity
    if remaining:
        portfolio[symbol] = remaining
    else:
        portfolio.pop(symbol, None)
    return cash + proceeds


def portfolio_value(portfolio: dict[str, int], prices: dict[str, float], cash: float) -> float:
    """Calculate total account equity from cash and current holding prices.

    Dependencies: current prices keyed by ticker.
    Side effects: none.
    Failure impact: missing tickers contribute no holding value.
    """
    return cash + sum(prices.get(symbol, 0.0) * amount for symbol, amount in portfolio.items())

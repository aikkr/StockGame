class TradeError(ValueError):
    pass


def apply_trade(portfolio, cash, symbol, side, quantity, price, handling_fee):
    if quantity is None or quantity <= 0 or quantity != int(quantity):
        raise TradeError('Enter a positive whole number of shares.')
    if quantity > 1_000_000:
        raise TradeError('An order cannot exceed 1,000,000 shares.')
    quantity = int(quantity)
    owned = portfolio.get(symbol, 0)

    if side == 'BUY':
        cost = price * quantity + handling_fee
        if cost > cash:
            raise TradeError('Not enough available cash for this order.')
        portfolio[symbol] = owned + quantity
        return cash - cost

    if quantity > owned:
        raise TradeError(f'You only own {owned} shares of {symbol}.')
    payment = price * quantity - handling_fee
    if payment < 0:
        raise TradeError('The sale value does not cover the handling fee.')
    remaining = owned - quantity
    if remaining == 0:
        del portfolio[symbol]
    else:
        portfolio[symbol] = remaining
    return cash + payment


def portfolio_value(portfolio, prices, cash):
    total = cash
    for symbol, amount in portfolio.items():
        total = total + prices[symbol] * amount
    return total

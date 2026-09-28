"""Test portfolio restoration, valuation, and trading rules."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from client.portfolio import TradeError, apply_trade, load_cash, load_portfolio, portfolio_value
from DB import UserDatabase


class PortfolioTests(unittest.TestCase):
    """Verify restored state and simulated order behavior.

    Dependencies: client.portfolio and unittest.
    Side effects: none outside temporary in-memory dictionaries.
    Failure impact: test failures identify broken trading or restoration rules.
    """

    def test_load_portfolio_accepts_only_known_positive_whole_holdings(self):
        saved = {'AAPL': 3, 'MSFT': 0, 'BAD': 4, 'TSLA': -1, 'NVDA': 1.5, 'KO': True}

        self.assertEqual(
            load_portfolio(saved, {'AAPL', 'MSFT', 'TSLA', 'NVDA', 'KO'}),
            {'AAPL': 3},
        )

    def test_buy_and_sell_update_portfolio_and_cash(self):
        portfolio = {}

        cash = apply_trade(portfolio, 1_000.0, 'AAPL', 'BUY', 3, 100.0, 2.0)
        self.assertEqual(portfolio, {'AAPL': 3})
        self.assertEqual(cash, 698.0)

        cash = apply_trade(portfolio, cash, 'AAPL', 'SELL', 3, 110.0, 2.0)
        self.assertEqual(portfolio, {})
        self.assertEqual(cash, 1_026.0)

    def test_failed_trade_does_not_change_portfolio(self):
        portfolio = {'AAPL': 2}

        with self.assertRaisesRegex(TradeError, 'only own 2'):
            apply_trade(portfolio, 50.0, 'AAPL', 'SELL', 3, 100.0, 2.0)

        self.assertEqual(portfolio, {'AAPL': 2})

    def test_saved_cash_and_total_portfolio_value(self):
        self.assertEqual(load_cash(float('nan'), 500.0), 500.0)
        self.assertEqual(portfolio_value({'AAPL': 2}, {'AAPL': 125.0}, 500.0), 750.0)

    def test_server_save_round_trip_returns_portfolio(self):
        with TemporaryDirectory() as directory:
            database = UserDatabase(Path(directory) / 'test.db')
            user = database.addUser('Player')
            progress = {'portfolio': {'AAPL': 4}, 'cash': 500.0}

            database.addSave(user['id'], 'current', progress)

            self.assertEqual(database.getSave(user['id'], 'current'), progress)


if __name__ == '__main__':
    unittest.main()

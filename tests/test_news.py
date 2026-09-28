"""Test extraction of displayable Yahoo Finance article details.

Dependencies: unittest and yfinanceuudised.
Side effects: temporarily mocks yfinance ticker construction.
Failure impact: failures identify incomplete or unsafe dialog article data.
"""

import unittest
from unittest.mock import patch

from yfinanceuudised import getLatestNews


class NewsExtractionTests(unittest.TestCase):
    """Verify that rich and legacy Yahoo article formats are normalized.

    Dependencies: yfinanceuudised and unittest.mock.
    Side effects: replaces network-backed ticker construction during each test.
    Failure impact: failures identify news fields missing from the article dialog.
    """

    @patch('yfinanceuudised.yf.Ticker')
    def test_latest_news_extracts_full_article_fields(self, ticker):
        ticker.return_value.news = [{
            'content': {
                'title': 'Market update',
                'description': 'The longer article description.',
                'summary': 'Short summary.',
                'pubDate': '2026-09-28T10:30:00Z',
                'provider': {'displayName': 'Example News'},
                'canonicalUrl': {'url': 'https://example.com/article'},
            },
        }]

        self.assertEqual(getLatestNews('AAPL'), {
            'headline': 'Market update',
            'body': 'The longer article description.',
            'date': '2026-09-28',
            'provider': 'Example News',
            'url': 'https://example.com/article',
        })

    @patch('yfinanceuudised.yf.Ticker')
    def test_latest_news_rejects_unsafe_article_url(self, ticker):
        ticker.return_value.news = [{
            'title': 'Legacy update',
            'summary': 'Legacy summary.',
            'publisher': 'Legacy News',
            'link': 'javascript:alert(1)',
        }]

        article = getLatestNews('MSFT')

        self.assertEqual(article['body'], 'Legacy summary.')
        self.assertEqual(article['provider'], 'Legacy News')
        self.assertEqual(article['url'], '')


if __name__ == '__main__':
    unittest.main()

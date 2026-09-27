"""Fetch stock news for the centrally configured server-side symbol list."""

import datetime
import json

import yfinance as yf

from server.config import get_stock_symbols


todayDate = datetime.date.today()


def getNews(tick, fromDate, toDate):
    """Fetch and filter Yahoo Finance news for one stock and date range."""
    stock = yf.Ticker(tick)
    uudis = stock.news
    dic = {}
    for article in uudis:
        content = article.get("content")
        title = content.get("title")
        summary = content.get("summary")
        date = content.get("pubDate")[0:10]
        if fromDate <= date <= toDate:
            dic[title] = {"summary": summary, "date": date}
    return dic


def getNewsAsJSON(startDate: str, endDate: str):
    """Write filtered news for all configured stocks to news.json."""
    all_news = {}

    for ticker in get_stock_symbols():
        uudis = getNews(ticker, startDate, endDate)
        all_news[ticker] = uudis

    with open("news.json", "w", encoding="utf-8") as json_file:
        json.dump(all_news, json_file)

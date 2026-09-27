import os
from dotenv import load_dotenv
import yfinance as yf
import json
import datetime

load_dotenv()
stocks = json.loads(os.getenv("STOCKS"))
todayDate = datetime.date.today()

def getNews(tick, fromDate, toDate):
    stock = yf.Ticker(tick)
    uudis = stock.news
    dic = {
    }
    for article in uudis:
        content = article.get("content")
        title = content.get("title")
        summary = content.get("summary")
        date = content.get("pubDate")[0:10]
        if fromDate <= date <= toDate:
            dic[title] = {"summary": summary, "date": date}
    return dic


def getNewsAsJSON(startDate: str, endDate: str):
    all_news = {}

    for ticker in stocks:
        uudis = getNews(ticker, startDate, endDate)
        all_news[ticker] = uudis

    json_file = open("news.json", "w")
    json.dump(all_news, json_file)
    json_file.close()
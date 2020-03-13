import logging
import threading
from time import sleep

import requests
from alpha_vantage.timeseries import TimeSeries

from stock_project import settings

logging.basicConfig(filename=settings.LOG_FILE_PATH, level=logging.DEBUG)

def startStockMonitorThread():
    stockMonitorThread = threading.Thread(target=runStockMonitor, daemon=True, name='stockMonitor_thread')
    stockMonitorThread.start()


def runStockMonitor():
    while True:
        pass
        logging.debug('thread started and running')
        checkStockData()
        sleep(1)


def checkStockData(current):
    key = settings.ALPHA_VANTAGE_API_KEY
    ts = TimeSeries(key)
    #aapl, meta = ts.get_daily(symbol=['NSE:ONGC', 'NSE:VEDL'])
    # aapl, meta = ts.get_batch_stock_quotes(symbols=['NSE:ONGC', 'NSE:VEDL'])
    # logging.debug(aapl['2020-03-09'])
    keys={
        1:settings.ALPHA_VANTAGE_API_KEY,
        2:settings.ALPHA_VANTAGE_API_KEY1,
    }
    params = {
        'function':'GLOBAL_QUOTE',
        'symbols':['NSE:VEDL','NSE:ONGC'],
        'apikey':keys[current],
        'datatype':'json',
    }
    url = settings.ALPHA_VANTAGE_URL #+ '?' + 'function=GLOBAL_QUOTE&symbol=NSE:VEDL&apikey=QJXWDFNT4EYCUOKG&datatype=json'
    aapl= requests.get(url=url, params=params)
    logging.debug(aapl.json())

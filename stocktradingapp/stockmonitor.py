import logging
import queue
import threading
from queue import Queue

from django.contrib.auth.models import User
from kiteconnect import KiteTicker

from stock_project import settings
from stocktradingapp import stocktrader
from stocktradingapp.models import Stock

logging.basicConfig(filename=settings.LOG_FILE_PATH, level=logging.DEBUG)

def runStockMonitor():
    kws = createWebSocketTicker()
    if kws:
        tick_queue = Queue(maxsize=5)
        startTickAnalyser(tick_queue)
        startWebSocketTicker(kws, tick_queue)

def createWebSocketTicker():
    user = User.objects.get_by_natural_key(settings.PRIMARY_USERNAME)
    user_zerodha = user.user_zerodha.first()
    if user_zerodha is None:
        return None
    return KiteTicker(user_zerodha.api_key, user_zerodha.access_token)

def startTickAnalyser(tick_queue):
    traderThread = threading.Thread(target=stocktrader.analyzeTicks, args=(tick_queue,), daemon=True,
                                    name='stockTrader_thread')
    traderThread.start()

def startWebSocketTicker(kws, tick_queue):
    def on_ticks(ws, tick):
        # Callback to receive ticks.
        try:
            tick_queue.put_nowait(tick)
        except queue.Full:
            try:
                dump = tick_queue.get_nowait()
                dump = tick_queue.get_nowait()
            except queue.Empty:
                pass

    def on_connect(ws, response):
        # Callback on successful connect.
        # Subscribe to a list of instrument_tokens (RELIANCE and ACC here).
        instrument_tokens = getInstrumentTokens()
        ws.subscribe(instrument_tokens)

        # Set RELIANCE to tick in `full` mode.
        ws.set_mode(ws.MODE_LTP, instrument_tokens=instrument_tokens)

    def on_close(ws, code, reason):
        # On connection close stop the main loop
        # Reconnection will not happen after executing `ws.stop()`
        ws.stop()

    # Assign the callbacks.
    kws.on_ticks = on_ticks
    kws.on_connect = on_connect
    kws.on_close = on_close

    # Infinite loop on the main thread. Nothing after this will run.
    # You have to use the pre-defined callbacks to manage subscriptions.
    kws.connect()

def getInstrumentTokens():
    stocks = Stock.objects.filter(active=True)
    return [stock.instrument_token for stock in stocks]

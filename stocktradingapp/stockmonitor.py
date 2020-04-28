import logging
import queue
import threading
from queue import Queue
from time import sleep

from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.utils.timezone import now
from kiteconnect import KiteTicker

from stock_project import settings
from stocktradingapp import stocktradershort
from stocktradingapp.models import Stock, Controls

logging.basicConfig(filename=settings.LOG_FILE_PATH, level=logging.DEBUG)

SHORT_SIDE = 1
LONG_SIDE = 2
TRADING_SIDE = settings.TRADING_SIDE

def runStockMonitor():
    # try:
    #     x=send_mail(subject='Server restarted', message='server restarted successfully at ' + str(now()),
    #                 from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=['felixsundar07@gmail.com'], fail_silently=False)
    # except Exception as e:
    #     logging.debug('\n\n\n\nemail sending exception:\n\n{}\n\n\n\n\n'.format(e))
    logging.debug('\n\n\n\nstock monitor thread started.\n\n\n\n')
    tick_queue = Queue(maxsize=5)
    kws = createWebSocketTicker()
    if not kws or not startStockTrader(tick_queue):
        return
    sleep(5)
    startWebSocketTicker(kws, tick_queue)

def createWebSocketTicker():
    user = User.objects.get_by_natural_key(settings.PRIMARY_USERNAME)
    user_zerodha = user.user_zerodha.first()
    if user_zerodha is None:
        return None
    return KiteTicker(user_zerodha.api_key, user_zerodha.access_token)

def startStockTrader(tick_queue):
    global TRADING_SIDE
    try:
        controls = Controls.objects.get(control_id=settings.CONTROLS_RECORD_ID)
        TRADING_SIDE = controls.trading_side
    except Exception as e:
        pass
    if TRADING_SIDE == SHORT_SIDE:
        traderThread = threading.Thread(target=stocktradershort.analyzeTicks, args=(tick_queue,), daemon=True,
                                    name='stockTrader_thread')
        traderThread.start()
    elif TRADING_SIDE == LONG_SIDE:
        traderThread = threading.Thread(target=stocktradershort.analyzeTicks, args=(tick_queue,), daemon=True,
                                        name='stockTrader_thread')
        traderThread.start()
    else:
        return False # Don't do any trading
    return True

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

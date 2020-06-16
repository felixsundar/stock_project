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
from stocktradingapp import stockTraderShortStoploss, stockTraderLongStoploss, mockTraderShortStoploss, \
    mockTraderLongStoploss, stockTraderShortStopprofit, stockTraderLongStopprofit, mockTraderShortStopprofit, \
    mockTraderLongStopprofit, stockTraderShortFixed, stockTraderLongFixed, mockTraderShortFixed, mockTraderLongFixed
from stocktradingapp.models import Stock, Controls

logging.basicConfig(filename=settings.LOG_FILE_PATH, level=logging.DEBUG)

SHORT_STOPPROFIT = 1
LONG_STOPPROFIT = 2
SHORT_STOPLOSS = 3
LONG_STOPLOSS = 4
MOCK_SHORT_STOPPROFIT = 5
MOCK_LONG_STOPPROFIT = 6
MOCK_SHORT_STOPLOSS = 7
MOCK_LONG_STOPLOSS = 8
SHORT_FIXED = 9
LONG_FIXED = 10
MOCK_SHORT_FIXED = 11
MOCK_LONG_FIXED = 12
TRADING_SIDE = settings.TRADING_SIDE

tick_overflow_mail_sent = False

def runStockMonitor():
    try:
        x=send_mail(subject='Stock Project App Started', message='Stock Project App started successfully at ' + str(now()),
                    from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=['felixsundar07@gmail.com'], fail_silently=False)
    except Exception as e:
        logging.debug('\n\n\n\nemail sending exception:\n\n{}\n\n\n\n\n'.format(e))
    logging.debug('\n\n\n\nstock monitor thread started at time - {}\n\n\n\n'.format(now()))
    tick_queue = Queue(maxsize=3)
    kws = createWebSocketTicker()
    if not kws or not startStockTrader(tick_queue):
        return
    sleep(5)
    startWebSocketTicker(kws, tick_queue)

def createWebSocketTicker():
    try:
        user = User.objects.get_by_natural_key(settings.PRIMARY_USERNAME)
        user_zerodha = user.user_zerodha.first()
        return KiteTicker(user_zerodha.api_key, user_zerodha.access_token)
    except Exception as e:
        return None

def startStockTrader(tick_queue):
    global TRADING_SIDE
    try:
        controls = Controls.objects.get(control_id=settings.CONTROLS_RECORD_ID)
        TRADING_SIDE = controls.trading_side
    except Exception as e:
        pass

    if TRADING_SIDE == SHORT_STOPPROFIT:
        traderThread = threading.Thread(target=stockTraderShortStopprofit.analyzeTicks, args=(tick_queue,), daemon=True,
                                        name='stockTraderShortStopprofit_thread')
        traderThread.start()
    elif TRADING_SIDE == LONG_STOPPROFIT:
        traderThread = threading.Thread(target=stockTraderLongStopprofit.analyzeTicks, args=(tick_queue,), daemon=True,
                                        name='stockTraderLongStopprofit_thread')
        traderThread.start()
    elif TRADING_SIDE == SHORT_STOPLOSS:
        traderThread = threading.Thread(target=stockTraderShortStoploss.analyzeTicks, args=(tick_queue,), daemon=True,
                                        name='stockTraderShortStoploss_thread')
        traderThread.start()
    elif TRADING_SIDE == LONG_STOPLOSS:
        traderThread = threading.Thread(target=stockTraderLongStoploss.analyzeTicks, args=(tick_queue,), daemon=True,
                                        name='stockTraderLongStoploss_thread')
        traderThread.start()
    elif TRADING_SIDE == MOCK_SHORT_STOPPROFIT:
        traderThread = threading.Thread(target=mockTraderShortStopprofit.analyzeTicks, args=(tick_queue,), daemon=True,
                                        name='mockTraderShortStopprofit_thread')
        traderThread.start()
    elif TRADING_SIDE == MOCK_LONG_STOPPROFIT:
        traderThread = threading.Thread(target=mockTraderLongStopprofit.analyzeTicks, args=(tick_queue,), daemon=True,
                                        name='mockTraderLongStopprofit_thread')
        traderThread.start()
    elif TRADING_SIDE == MOCK_SHORT_STOPLOSS:
        traderThread = threading.Thread(target=mockTraderShortStoploss.analyzeTicks, args=(tick_queue,), daemon=True,
                                        name='mockTraderShortStoploss_thread')
        traderThread.start()
    elif TRADING_SIDE == MOCK_LONG_STOPLOSS:
        traderThread = threading.Thread(target=mockTraderLongStoploss.analyzeTicks, args=(tick_queue,), daemon=True,
                                        name='mockTraderLongStoploss_thread')
        traderThread.start()
    elif TRADING_SIDE == SHORT_FIXED:
        traderThread = threading.Thread(target=stockTraderShortFixed.analyzeTicks, args=(tick_queue,), daemon=True,
                                        name='stockTraderShortFixed_thread')
        traderThread.start()
    elif TRADING_SIDE == LONG_FIXED:
        traderThread = threading.Thread(target=stockTraderLongFixed.analyzeTicks, args=(tick_queue,), daemon=True,
                                        name='stockTraderLongFixed_thread')
        traderThread.start()
    elif TRADING_SIDE == MOCK_SHORT_FIXED:
        traderThread = threading.Thread(target=mockTraderShortFixed.analyzeTicks, args=(tick_queue,), daemon=True,
                                        name='mockTraderShortFixed_thread')
        traderThread.start()
    elif TRADING_SIDE == MOCK_LONG_FIXED:
        traderThread = threading.Thread(target=mockTraderLongFixed.analyzeTicks, args=(tick_queue,), daemon=True,
                                        name='mockTraderLongFixed_thread')
        traderThread.start()
    else:
        logging.debug('Not starting any trading threads.')
        return False # Don't do any trading
    return True

def startWebSocketTicker(kws, tick_queue):
    def on_ticks(ws, tick):
        # Callback to receive ticks.
        try:
            tick_queue.put_nowait(tick)
        except queue.Full:
            try:
                sendTickOverflowMail()
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
        current_time = now()
        if current_time > now().replace(hour=15, minute=29, second=30):
            ws.stop()

    # Assign the callbacks.
    kws.on_ticks = on_ticks
    kws.on_connect = on_connect
    kws.on_close = on_close

    # Infinite loop on the main thread. Nothing after this will run.
    # You have to use the pre-defined callbacks to manage subscriptions.
    kws.connect()

def sendTickOverflowMail():
    global tick_overflow_mail_sent
    if not tick_overflow_mail_sent:
        mail_thread = threading.Thread(target=sendEmail, daemon=True, name='mail_thread')
        mail_thread.start()
        tick_overflow_mail_sent = True

def sendEmail():
    logging.debug('\n\nTick overflow occured at time - {}'.format(now()))
    try:
        x = send_mail(subject='Tick Overflow', message='Tick overflow occured at time - ' + str(now()),
                      from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=['felixsundar07@gmail.com'], fail_silently=False)
    except Exception as e:
        logging.debug('\n\nemail sending exception while sending tick overflow email:\n\n{}\n\n'.format(e))

def getInstrumentTokens():
    stocks = Stock.objects.filter(active=True)
    return [stock.instrument_token for stock in stocks]

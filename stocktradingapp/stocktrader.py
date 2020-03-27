import logging
import queue
import threading
from queue import PriorityQueue

from django.contrib.auth.models import User
from kiteconnect import KiteConnect

from stock_project import settings
from stocktradingapp.models import Stock

logging.basicConfig(filename=settings.LOG_FILE_PATH, level=logging.DEBUG)

current_positions = {} # {'instrument_token': {'entry_price': entry_price,
                       #                       'stoploss': stoploss,
                       #                       'users': [(zerodha_user_id, number_of_stocks)]
                       #                      }
                       # }
pending_orders = {}
funds_available = {} # for each user
signal_queues = {} # for each user
token_symbols = {} # for each token
token_trigger_prices = {} # for each token
token_mis_margins = {} # for each token
token_co_margins = {} # for each token

def analyzeTicks(tick_queue):
    if not setupTradingThreads():
        return
    setupTokenInfoMap()
    while True:
        try:
            tick = tick_queue.get(True)
            if isinstance(tick, (list,)):
                for instrument in tick:
                    instrument_token = instrument['instrument_token']
                    current_price = instrument['last_price']
                    checkEntryTrigger(instrument_token, current_price)
                    checkStoploss(instrument_token, current_price)
            else:
                processMessage(tick)
        except Exception as e:
            pass

def checkEntryTrigger(instrument_token, current_price):
    trigger_price = token_trigger_prices[instrument_token]
    if current_price < trigger_price:  # entry trigger breached
        token_trigger_prices[instrument_token] = 0.995 * current_price
        sendSignal(1, instrument_token)
    else:  # update entry trigger
        token_trigger_prices[instrument_token] = max(trigger_price, 0.995 * current_price)

def checkStoploss(instrument_token, current_price):
    current_position = current_positions.get(instrument_token)
    if current_position is None:
        return
    if current_price >= current_position['stoploss']:  # stoploss breached
        sendSignal(0, instrument_token)
    else:  # update stoploss
        current_position['stoploss'] = min(current_position['stoploss'], 1.005 * current_price)

def setupTradingThreads():
    users = User.objects.filter(is_active=True)
    if not users.exists():
        return False
    for user in users:
        user_zerodha = user.user_zerodha.first()
        if user_zerodha is None:
            continue
        kite = KiteConnect(settings.KITE_API_KEY)
        kite.set_access_token(user_zerodha.access_token)
        margin = kite.margins()
        fund_available = margin['data']['equity']['available']['cash']
        funds_available[user_zerodha.user_id] = fund_available
        signal_queues[user_zerodha.user_id] = PriorityQueue(maxsize=5)
        trading_thread = threading.Thread(target=tradeExecutor, daemon=True, args=(user_zerodha.user_id, kite,),
                                          name=user_zerodha.user_id+'_trader')
        trading_thread.start()
    return True

def setupTokenInfoMap():
    stocks = Stock.objects.filter(active=True)
    for stock in stocks:
        token_symbols[stock.instrument_token] = stock.trading_symbol
        token_trigger_prices[stock.instrument_token] = 0.0 # initial trigger price
        token_mis_margins[stock.instrument_token] = stock.mis_margin
        token_co_margins[stock.instrument_token] = stock.co_margin

def processMessage(tick):
    pass

def sendSignal(enter_or_exit, instrument_token): # 0 for exit, 1 for enter
    if enter_or_exit == 1:
        for signal_queue in signal_queues.values():
            try:
                signal_queue.put_nowait((enter_or_exit, instrument_token))
            except queue.Full:
                pass
    else:
        current_position = current_positions[instrument_token]
        for user in current_position['users']:
            signal_queues[user[0]].put((enter_or_exit, instrument_token, user[1]), block=True)

def tradeExecutor(zerodha_user_id, kite):
    updateFundAvailable(zerodha_user_id, kite)
    signal_queue = signal_queues[zerodha_user_id]
    while True:
        signal = signal_queue.get(True)
        # if signal[0] == 1:
        #     kite.place_order(variety='CO', exchange='NSE', tradingsymbol='d', transaction_type='d', quantity='d',
        #                      product='d', order_type='df', price='d', validity='df', disclosed_quantity='d',
        #                      trigger_price='d', squareoff='df', stoploss='dfe', trailing_stoploss='df', tag='j')

def updateFundAvailable(zerodha_user_id, kite):
    pass

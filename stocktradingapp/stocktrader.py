import logging
import queue
import threading
from datetime import datetime
from queue import PriorityQueue
from time import sleep

import pytz
import requests
import schedule
from django.contrib.auth.models import User
from kiteconnect import KiteConnect

from stock_project import settings
from stocktradingapp.models import Stock

logging.basicConfig(filename=settings.LOG_FILE_PATH, level=logging.DEBUG)

# CONSTANTS
# enter_or_exit: 1 - enter, 0 - exit
STATUS_COMPLETE = 'COMPLETE'
STATUS_CANCELLED = 'CANCELLED'
STATUS_REJECTED = 'REJECTED'
CO_ORDER = 'co'
REGULAR_ORDER = 'regular'

current_positions = {} # {'instrument_token1': [],
                       #  'instrument_token2': [],
                       #  'instrument_token3': [{position1},
                       #                        {position2},
                       #                        {'user_id', 'number_of_stocks', 'variety', 'entry_price':45.8, 'stoploss':47.4}
                       #                       ]
                       # } for each token
user_kites = {} # for each user
pending_orders = {} # for each user {userid1:[], userid2:[], userid3:[{enter_or_exit:1, orderid:32435, instrument_token:xx}]}
funds_available = {} # for each user
signal_queues = {} # for each user
token_symbols = {} # for each token
token_trigger_prices = {} # for each token
token_mis_margins = {} # for each token
token_co_margins = {} # for each token
token_co_upper_trigger = {} # for each token
order_variety = 'co'
entry_time_limit = datetime.now().time().replace(hour=15, minute=17, second=0, microsecond=0)

def analyzeTicks(tick_queue):
    if not setupTradingThreads():
        return
    updateTriggerRangesInDB()
    setupTokenInfoMap()
    printInitialValues()
    schedule.every().day.at('15:18').do(exitAllPositions)
    while True:
        try:
            tick = tick_queue.get(True)
            for instrument in tick:
                instrument_token = instrument['instrument_token']
                current_price = instrument['last_price']
                checkEntryTrigger(instrument_token, current_price)
                checkStoploss(instrument_token, current_price)
            # logging.debug('tick - {}'.format(tick))
            schedule.run_pending()
        except Exception as e:
            pass

def setupTradingThreads():
    users = User.objects.filter(is_active=True)
    if not users.exists():
        return False
    zerodha_present = False
    for user in users:
        user_zerodha = user.user_zerodha.first()
        if user_zerodha is None:
            continue
        zerodha_present = True

        kite = KiteConnect(user_zerodha.api_key)
        kite.set_access_token(user_zerodha.access_token)
        user_kites[user_zerodha.user_id] = kite
        kite.cancel_order()

        fund_available = updateFundAvailable(user_zerodha.user_id)
        user_zerodha.fund_available = fund_available
        user_zerodha.save()

        signal_queues[user_zerodha.user_id] = PriorityQueue(maxsize=5)
        pending_orders[user_zerodha.user_id] = []

        trading_thread = threading.Thread(target=tradeExecutor, daemon=True, args=(user_zerodha.user_id,),
                                          name=user_zerodha.user_id+'_trader')
        trading_thread.start()

    return zerodha_present

def updateFundAvailable(zerodha_user_id):
    margin = user_kites[zerodha_user_id].margins()
    fund_available = margin['equity']['available']['live_balance']
    funds_available[zerodha_user_id] = fund_available
    return fund_available

def updateTriggerRangesInDB():
    trigger_ranges_response = requests.get(url=settings.TRIGGER_RANGE_URL)
    trigger_ranges = trigger_ranges_response.json()
    stocks = Stock.objects.filter(active=True)
    symbol_stock = {}
    for stock in stocks:
        symbol_stock[stock.trading_symbol] = stock
    for instrument in trigger_ranges:
        stock = symbol_stock.get(instrument['tradingsymbol'])
        if stock is not None:
            stock.co_trigger_percent_lower = instrument['co_lower']
            stock.co_trigger_percent_upper = instrument['co_upper']
            stock.mis_margin = instrument['mis_multiplier']
            stock.save()

def setupTokenInfoMap():
    stocks = Stock.objects.filter(active=True)
    for stock in stocks:
        current_positions[stock.instrument_token] = []
        token_symbols[stock.instrument_token] = stock.trading_symbol
        token_trigger_prices[stock.instrument_token] = 0.0 # initial trigger price
        token_mis_margins[stock.instrument_token] = stock.mis_margin
        token_co_margins[stock.instrument_token] = stock.co_margin
        token_co_upper_trigger[stock.instrument_token] = stock.co_trigger_percent_upper

def printInitialValues():
    logging.debug('\n\ncurrent Positions - {}\n\n'.format(current_positions))
    logging.debug('\n\npending orders - {}\n\n'.format(pending_orders))
    logging.debug('\n\nfunds available - {}\n\n'.format(funds_available))
    logging.debug('\n\nsignal queues - {}\n\n'.format(signal_queues))
    logging.debug('\n\ntoken symbols - {}\n\n'.format(token_symbols))
    logging.debug('\n\ntoken trigger prices - {}\n\n'.format(token_trigger_prices))
    logging.debug('\n\ntoken mis margins - {}\n\n'.format(token_mis_margins))
    logging.debug('\n\ntoken co margins - {}\n\n'.format(token_co_margins))
    logging.debug('\n\ntoken co upper trigger - {}\n\n'.format(token_co_upper_trigger))

def checkEntryTrigger(instrument_token, current_price):
    trigger_price = token_trigger_prices[instrument_token]
    if current_price < trigger_price:  # entry trigger breached
        token_trigger_prices[instrument_token] = 0.995 * current_price
        sendSignal(1, instrument_token, current_price)
    else:  # update entry trigger
        token_trigger_prices[instrument_token] = max(trigger_price, 0.995 * current_price)

def checkStoploss(instrument_token, current_price):
    current_positions_for_token = current_positions[instrument_token]
    for position in current_positions_for_token:
        if current_price >= position['stoploss']: # stoploss breached
            sendSignal(0, instrument_token, position)
        else:  # update stoploss
            position['stoploss'] = min(position['stoploss'], 1.005 * current_price)

def sendSignal(enter_or_exit, instrument_token, currentPrice_or_currentPosition): # 0 for exit, 1 for enter
    if enter_or_exit == 1:
        for signal_queue in signal_queues.values():
            try:
                signal_queue.put_nowait((enter_or_exit, instrument_token, currentPrice_or_currentPosition))
            except queue.Full:
                pass
    else:
        signal_queue = signal_queues[currentPrice_or_currentPosition['user_id']]
        signal_queue.put((enter_or_exit, instrument_token, currentPrice_or_currentPosition), block=True)

def tradeExecutor(zerodha_user_id):
    signal_queue = signal_queues[zerodha_user_id]
    kite = user_kites[zerodha_user_id]
    place = True
    while True:
        signal = signal_queue.get(True)
        try:
            if signal[0] == 1 and verifyEntryCondition(zerodha_user_id, signal[1]) and place == True:
                place = False
                placeEntryOrder(zerodha_user_id, kite, signal)
            elif signal[0] == 0  and verifyExitCondition(signal[1], signal[2]):
                placeExitOrder(kite, signal[1], signal[2])
        except Exception as e:
            logging.debug('Exception while placing order for user - {}\n'
                          'Instrument Token - {}\n\n{}'.format(zerodha_user_id, signal[1], e))

            # variety = regular, amo, bo, co
            # exchange = NSE, BSE
            # tradingsymbol = IRCTC, SBICARD, etc..
            # transaction_type = BUY, SELL
            # quantity = number of stocks
            # product = CNC, MIS
            # order_type = MARKET, LIMIT, SL, SL-M
            # price = limit price
            # validity = DAY, IOC # use day always
            # disclosed quantity = within 10 to 100 % of quantity. # set this same as quantity
            # trigger price = entry trigger price
            # squareoff = target profit to exit. Profit amount in Rupees
            # stoploss = loss amount in Rupees to exit
            # trailing_stoploss = moving stoploss
            # tag = random alphanumeric id attached to the order

def verifyEntryCondition(zerodha_user_id, instrument_token):
    current_positions_for_token = current_positions[instrument_token]
    for position in current_positions_for_token:
        if position['user_id'] == zerodha_user_id:
            return False
    if datetime.now(tz=pytz.timezone(settings.TIME_ZONE)).time() > entry_time_limit:
        return False
    return False if pending_orders[zerodha_user_id] else True

def placeEntryOrder(zerodha_user_id, kite, signal):
    quantity, variety = calculateNumberOfStocksToTrade(zerodha_user_id, signal[1], signal[2])
    if variety == 'co': #place co order
        trigger_price = calculateCOtriggerPrice(token_co_upper_trigger[signal[1]], signal[2])
        order_id = kite.place_order(variety=variety, exchange='NSE', tradingsymbol=token_symbols[signal[1]],
                                    transaction_type='SELL', quantity=quantity, product='MIS', order_type='MARKET',
                                    validity='DAY', disclosed_quantity=quantity, trigger_price=trigger_price)
        logging.debug('CO ENTRY ORDER PLACED for zerodha user - {}\nInstrument token for entry - {}'
                      '\nTrigger price for co order exit - {}'
                      '\norder quantity - {}'.format(zerodha_user_id, signal[1], trigger_price, quantity))
    else: #place regular order(mis)
        order_id = kite.place_order(variety=variety, exchange='NSE', tradingsymbol=token_symbols[signal[1]],
                                    transaction_type='SELL', quantity=quantity, product='MIS',
                                    order_type='MARKET', validity='DAY', disclosed_quantity=quantity)
        logging.debug('REGULAR ENTRY ORDER PLACED for zerodha user - {}\nInstrument token for entry - {}'
                      '\norder quantity - {}'.format(zerodha_user_id, signal[1], quantity))
    pending_orders[zerodha_user_id].append({'enter_or_exit':1, 'order_id':order_id, 'instrument_token':signal[1]})

def verifyExitCondition(instrument_token, position):
    pending_orders_for_user = pending_orders[position['user_id']]
    for pending_order in pending_orders_for_user:
        if pending_order['instrument_token'] == instrument_token and pending_order['enter_or_exit'] == 0:
            return False
    return True

def placeExitOrder(kite, instrument_token, position):
    if position['variety'] == 'co':
        order_id = kite.cancel_order(variety='co', order_id=position['order_id'], parent_order_id=position['parent_order_id'])
    else:
        order_id = kite.place_order(variety=position['variety'], exchange='NSE', tradingsymbol=token_symbols[instrument_token],
                                    transaction_type='BUY', quantity=position['number_of_stocks'], product='MIS',
                                    order_type='MARKET', validity='DAY', disclosed_quantity=position['number_of_stocks'])
    pending_orders[position['user_id']].append({'enter_or_exit':0, 'order_id':order_id, 'instrument_token':instrument_token})

def calculateNumberOfStocksToTrade(zerodha_user_id, instrument_token, current_price):
    order_variety_local = order_variety
    if order_variety_local == 'co':
        margin = token_co_margins[instrument_token]
    else:
        margin = token_mis_margins[instrument_token]
    total_fund = margin * funds_available[zerodha_user_id]
    quantity = total_fund//(current_price + 1) # 1 added to match the anticipated price increase in the time gap
    return (int(quantity), order_variety_local)

def calculateCOtriggerPrice(co_upper_trigger_percent, current_price):
    trigger_price = current_price + (current_price * (min(co_upper_trigger_percent - 1.0, 1.5) / 100.0))
    return float('{:.1f}'.format(trigger_price))

def updateOrderFromPostback(order_details):
    sleep(0.5) # postback may be received instantly after placing order. wait till order id is entered in the pending orders list
    pending_order = getPendingOrder(order_details)
    if pending_order is None:
        return
    if order_details['status'] == STATUS_CANCELLED:
        pending_orders[order_details['user_id']].remove(pending_order)
    elif order_details['status'] == STATUS_REJECTED:
        pending_orders[order_details['user_id']].remove(pending_order)
        global order_variety
        order_variety = 'regular'
    elif order_details['status'] == STATUS_COMPLETE:
        updateFundAvailable(order_details['user_id'])
        if pending_order['enter_or_exit'] == 1:
            updateEntryOrderComplete(order_details)
        else:
            updateExitOrderComplete(order_details)
        pending_orders[order_details['user_id']].remove(pending_order)

def getPendingOrder(order_details):
    user_pending_orders = pending_orders[order_details['user_id']]
    for order in user_pending_orders:
        if order['order_id'] == order_details['order_id']:
            return order
    return None

def updateEntryOrderComplete(order_details):
    if order_details['variety'] == CO_ORDER:
        second_leg_order_details = getSecondLegOrder(order_details)
        new_position = constructNewPosition(order_details, second_leg_order_details)
    else:
        new_position = constructNewPosition(order_details)
    current_positions[order_details['instrument_token']].append(new_position)

def updateExitOrderComplete(order_details):
    current_positions_for_instrument = current_positions[order_details['instrument_token']]
    for position in current_positions_for_instrument:
        if position['user_id'] == order_details['user_id']:
            current_positions_for_instrument.remove(position)
            return

def getSecondLegOrder(order_details):
    kite = user_kites[order_details['user_id']]
    orders = kite.orders()
    for order in orders:
        if order['parent_order_id'] == order_details['order_id']:
            return order
    raise Exception

def constructNewPosition(order_details, second_leg_order_details=None):
    new_position = {}
    new_position['user_id'] = order_details['user_id']
    new_position['variety'] = order_details['variety']
    new_position['number_of_stocks'] = order_details['filled_quantity']
    new_position['entry_price'] = order_details['average_price']
    new_position['stoploss'] = order_details['average_price'] + order_details['average_price'] * 0.005
    if second_leg_order_details:
        new_position['order_id'] = second_leg_order_details['order_id']
        new_position['parent_order_id'] = second_leg_order_details['parent_order_id']
    return new_position

def exitAllPositions():
    for instrument_token in current_positions.keys():
        for position in current_positions[instrument_token]:
            sendSignal(0, instrument_token, position)
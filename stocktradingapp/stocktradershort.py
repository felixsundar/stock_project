import logging
import queue
import threading
from queue import PriorityQueue, Queue
from time import sleep

import requests
import schedule
from django.utils.timezone import now
from kiteconnect import KiteConnect

from stock_project import settings
from stocktradingapp.models import Stock, ZerodhaAccount, Controls

logging.basicConfig(filename=settings.LOG_FILE_PATH, level=logging.DEBUG)

# CONSTANTS
ENTER = 1
EXIT = 0
STATUS_COMPLETE = 'COMPLETE'
STATUS_CANCELLED = 'CANCELLED'
STATUS_REJECTED = 'REJECTED'
CO_ORDER = 'co'
REGULAR_ORDER = 'regular'

# PARAMETERS
ENTRY_TRIGGER_TIMES = (100.0 - settings.ENTRY_TRIGGER_PERCENT) / 100.0

MAX_RISK_PERCENT_PER_TRADE = settings.MAX_RISK_PERCENT_PER_TRADE
MAX_INVESTMENT_PER_POSITION = settings.MAX_INVESTMENT_PER_POSITION
MIN_INVESTMENT_PER_POSITION = settings.MIN_INVESTMENT_PER_POSITION

POSITION_STOPLOSS_PERCENT = settings.POSITION_STOPLOSS_PERCENT
POSITION_TARGET_STOPLOSS = settings.POSITION_TARGET_STOPLOSS
POSITION_STOPLOSS_RANGE = POSITION_STOPLOSS_PERCENT - POSITION_TARGET_STOPLOSS
POSITION_TARGET_PERCENT = settings.POSITION_TARGET_PERCENT

USER_STOPLOSS_PERCENT = settings.USER_STOPLOSS_PERCENT
USER_TARGET_STOPLOSS = settings.USER_TARGET_STOPLOSS
USER_STOPLOSS_RANGE = USER_STOPLOSS_PERCENT - USER_TARGET_STOPLOSS
USER_TARGET_PERCENT = settings.USER_TARGET_PERCENT

ENTRY_TIME_START = now().time().replace(hour=settings.ENTRY_TIME_START[0], minute=settings.ENTRY_TIME_START[1],
                                        second=settings.ENTRY_TIME_START[2])
ENTRY_TIME_END = now().time().replace(hour=settings.ENTRY_TIME_END[0], minute=settings.ENTRY_TIME_END[1],
                                      second=settings.ENTRY_TIME_END[2])

# FOR EACH TOKEN
token_symbols = {}
token_trigger_prices = {}
token_mis_margins = {}
token_co_margins = {}
token_co_upper_trigger = {}
current_positions = {}

# FOR EACH USER
user_kites = {}
pending_orders = {} # {userid1:[], userid2:[], userid3:[{enter_or_exit:1, orderid:32435, instrument_token:xx}]}
user_initial_value = {}
live_funds_available = {}
user_net_value = {}
user_target_value = {}
user_stoploss = {}
user_amount_at_risk = {}
signal_queues = {}

# OTHER GLOBALS
postback_queue = Queue(maxsize=500)
order_variety = CO_ORDER

def analyzeTicks(tick_queue):
    if not setupTradingThreads():
        return
    updateTriggerRangesInDB()
    setupTokenMaps()
    setupParameters()
    startPostbackProcessingThread()
    logging.debug('short stocktrader thread started')
    schedule.every().day.at('15:08').do(scheduleExit)
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
    user_zerodhas = ZerodhaAccount.objects.filter(is_active=True)
    zerodha_present = False
    for user_zerodha in user_zerodhas:
        zerodha_present = True
        if not validateAccessToken(user_zerodha.access_token_time):
            continue
        setupUserMaps(user_zerodha)
        trading_thread = threading.Thread(target=tradeExecutor, daemon=True, args=(user_zerodha.user_id,),
                                          name=user_zerodha.user_id + '_trader_thread')
        trading_thread.start()
    return zerodha_present

def setupUserMaps(user_zerodha):
    kite = KiteConnect(user_zerodha.api_key)
    kite.set_access_token(user_zerodha.access_token)
    updateFundAvailable(user_zerodha.user_id)
    user_zerodha.fund_available = live_funds_available[user_zerodha.user_id]
    user_zerodha.save()

    user_kites[user_zerodha.user_id] = kite
    user_initial_value[user_zerodha.user_id] = live_funds_available[user_zerodha.user_id]
    user_target_value[user_zerodha.user_id] = live_funds_available[user_zerodha.user_id] * (100.0 + USER_TARGET_PERCENT) / 100.0
    user_net_value[user_zerodha.user_id] = live_funds_available[user_zerodha.user_id]
    user_stoploss[user_zerodha.user_id] = (100.0 - USER_STOPLOSS_PERCENT) / 100.0 * live_funds_available[user_zerodha.user_id]
    user_amount_at_risk[user_zerodha.user_id] = 0.0
    signal_queues[user_zerodha.user_id] = PriorityQueue(maxsize=100)
    pending_orders[user_zerodha.user_id] = []

def validateAccessToken(access_token_time):
    expiry_time = now().replace(hour=8, minute=30, second=0, microsecond=0)
    if now() > expiry_time and access_token_time < expiry_time:
        return False
    return True

def updateFundAvailable(zerodha_user_id):
    margin = user_kites[zerodha_user_id].margins()
    live_funds_available[zerodha_user_id] = margin['equity']['available']['live_balance']

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

def setupTokenMaps():
    stocks = Stock.objects.filter(active=True)
    for stock in stocks:
        current_positions[stock.instrument_token] = []
        token_symbols[stock.instrument_token] = stock.trading_symbol
        token_trigger_prices[stock.instrument_token] = 0.0 # initial trigger price
        token_mis_margins[stock.instrument_token] = stock.mis_margin
        token_co_margins[stock.instrument_token] = stock.co_margin
        token_co_upper_trigger[stock.instrument_token] = stock.co_trigger_percent_upper

def setupParameters():
    global ENTRY_TRIGGER_TIMES, MAX_RISK_PERCENT_PER_TRADE, MAX_INVESTMENT_PER_POSITION, MIN_INVESTMENT_PER_POSITION,\
        POSITION_STOPLOSS_PERCENT, POSITION_TARGET_STOPLOSS, POSITION_STOPLOSS_RANGE, POSITION_TARGET_PERCENT,\
        USER_STOPLOSS_PERCENT, USER_TARGET_STOPLOSS, USER_STOPLOSS_RANGE, USER_TARGET_PERCENT, ENTRY_TIME_START, ENTRY_TIME_END
    try:
        controls = Controls.objects.get(control_id=settings.CONTROLS_RECORD_ID)
        ENTRY_TRIGGER_TIMES = (100.0 - controls.entry_trigger_percent) / 100.0

        MAX_RISK_PERCENT_PER_TRADE = controls.max_risk_percent_per_trade
        MAX_INVESTMENT_PER_POSITION = controls.max_investment_per_position
        MIN_INVESTMENT_PER_POSITION = controls.min_investment_per_position

        POSITION_STOPLOSS_PERCENT = controls.position_stoploss_percent
        POSITION_TARGET_STOPLOSS = controls.position_target_stoploss
        POSITION_STOPLOSS_RANGE = POSITION_STOPLOSS_PERCENT - POSITION_TARGET_STOPLOSS
        POSITION_TARGET_PERCENT = controls.position_target_percent

        USER_STOPLOSS_PERCENT = controls.user_stoploss_percent
        USER_TARGET_STOPLOSS = controls.user_target_stoploss
        USER_STOPLOSS_RANGE = USER_STOPLOSS_PERCENT - USER_TARGET_STOPLOSS
        USER_TARGET_PERCENT = controls.user_target_percent
        ENTRY_TIME_START = controls.entry_time_start.time()
        ENTRY_TIME_END = controls.entry_time_end.time()
    except Exception as e:
        pass

def startPostbackProcessingThread():
    postback_processing_thread = threading.Thread(target=updateOrderFromPostback, daemon=True, name='postback_processing_thread')
    postback_processing_thread.start()

def checkEntryTrigger(instrument_token, current_price):
    if current_price <= token_trigger_prices[instrument_token]: # entry trigger breached
        token_trigger_prices[instrument_token] = current_price * ENTRY_TRIGGER_TIMES
        sendSignal(ENTER, instrument_token, current_price)
    else: # update entry trigger
        token_trigger_prices[instrument_token] = max(token_trigger_prices[instrument_token], current_price * ENTRY_TRIGGER_TIMES)

def checkStoploss(instrument_token, current_price):
    for position in current_positions[instrument_token]:
        if current_price >= position['stoploss']: # stoploss breached
            sendSignal(EXIT, instrument_token, position)
        else: # update stoploss
            position['stoploss'] = min(position['stoploss'], updatePositionStoploss(position, current_price))

def updatePositionStoploss(position, current_price):
    remaining_target = current_price - position['target_price'] if current_price > position['target_price'] else 0
    return current_price + \
           (remaining_target * position['slrange_tprofit_ratio'] + POSITION_TARGET_STOPLOSS) * position['one_percent_entry_price']

def sendSignal(enter_or_exit, instrument_token, currentPrice_or_currentPosition): # 0 for exit, 1 for enter
    if enter_or_exit == ENTER:
        for signal_queue in signal_queues.values():
            try:
                signal_queue.put_nowait((ENTER, instrument_token, currentPrice_or_currentPosition))
            except queue.Full:
                pass
    else:
        signal_queue = signal_queues[currentPrice_or_currentPosition['user_id']]
        signal_queue.put((EXIT, instrument_token, currentPrice_or_currentPosition), block=True)

def tradeExecutor(zerodha_user_id):
    signal_queue = signal_queues[zerodha_user_id]
    kite = user_kites[zerodha_user_id]
    place = True
    while True:
        signal = signal_queue.get(True)
        try:
            if signal[0] == ENTER and verifyEntryCondition(zerodha_user_id, signal[1]) and place == True:
                place = False
                placeEntryOrder(zerodha_user_id, kite, signal)
            elif signal[0] == EXIT and verifyExitCondition(signal[1], signal[2]):
                placeExitOrder(kite, signal[1], signal[2])
        except Exception as e:
            logging.debug('Exception while placing order for user - {}\n'
                          'Instrument Token - {}\n\n{}'.format(zerodha_user_id, signal[1], e))

def verifyEntryCondition(zerodha_user_id, instrument_token):
    for position in current_positions[instrument_token]:
        if position['user_id'] == zerodha_user_id:
            return False
    current_time = now().time()
    if current_time > ENTRY_TIME_END or current_time < ENTRY_TIME_START or \
            user_net_value[zerodha_user_id] <= user_stoploss[zerodha_user_id] or pending_orders[zerodha_user_id]:
        return False
    return True

def placeEntryOrder(zerodha_user_id, kite, signal):
    quantity, variety = calculateNumberOfStocksToTrade(zerodha_user_id, signal[1], signal[2])
    if quantity == 0:
        return
    if variety == CO_ORDER: #place co order
        trigger_price = calculateCOtriggerPrice(token_co_upper_trigger[signal[1]], signal[2])
        order_id = kite.place_order(variety=variety, exchange='NSE', tradingsymbol=token_symbols[signal[1]],
                                    transaction_type='SELL', quantity=quantity, product='MIS', order_type='MARKET',
                                    validity='DAY', disclosed_quantity=quantity, trigger_price=trigger_price)
    else: #place regular order(mis)
        order_id = kite.place_order(variety=variety, exchange='NSE', tradingsymbol=token_symbols[signal[1]],
                                    transaction_type='SELL', quantity=quantity, product='MIS',
                                    order_type='MARKET', validity='DAY', disclosed_quantity=quantity)
    pending_orders[zerodha_user_id].append({'enter_or_exit':ENTER, 'order_id':order_id, 'instrument_token':signal[1]})

def verifyExitCondition(instrument_token, position):
    for pending_order in pending_orders[position['user_id']]:
        if pending_order['instrument_token'] == instrument_token and pending_order['enter_or_exit'] == EXIT:
            return False
    return True

def placeExitOrder(kite, instrument_token, position):
    if position['variety'] == CO_ORDER:
        order_id = kite.cancel_order(variety=CO_ORDER, order_id=position['order_id'], parent_order_id=position['parent_order_id'])
    else:
        order_id = kite.place_order(variety=position['variety'], exchange='NSE', tradingsymbol=token_symbols[instrument_token],
                                    transaction_type='BUY', quantity=position['number_of_stocks'], order_type='MARKET',
                                    product='MIS', validity='DAY', disclosed_quantity=position['number_of_stocks'])
    pending_orders[position['user_id']].append({'enter_or_exit':EXIT, 'order_id':order_id, 'instrument_token':instrument_token})

def calculateNumberOfStocksToTrade(zerodha_user_id, instrument_token, current_price):
    order_variety_local = order_variety
    if order_variety_local == CO_ORDER:
        margin = token_co_margins[instrument_token]
    else:
        margin = token_mis_margins[instrument_token]
    riskable_amount = min(MAX_RISK_PERCENT_PER_TRADE * user_net_value[zerodha_user_id] / 100.0,
                          user_net_value[zerodha_user_id] - user_amount_at_risk[zerodha_user_id] - user_stoploss[zerodha_user_id])
    if riskable_amount <= 0:
        return (0, order_variety_local)
    investment_for_riskable_amount = riskable_amount * 100.0 / POSITION_STOPLOSS_PERCENT # riskable_amount = 0.5% then ? = 100%...
    amount_to_invest = min(investment_for_riskable_amount, live_funds_available[zerodha_user_id] * margin, MAX_INVESTMENT_PER_POSITION)
    quantity = amount_to_invest // (current_price + 1) if amount_to_invest > MIN_INVESTMENT_PER_POSITION else 0 # 1 added to match the anticipated price increase in the time gap
    return (int(quantity), order_variety_local)

def calculateCOtriggerPrice(co_upper_trigger_percent, current_price):
    trigger_price = current_price + (current_price * (min(co_upper_trigger_percent - 1.0, 2.5) / 100.0))
    return float('{:.1f}'.format(trigger_price))

def updateOrderFromPostback():
    while True:
        order_details = postback_queue.get(block=True)
        sleep(0.3) # postback maybe received instantly after placing order. so wait till order id is added to pending orders list
        pending_order = getPendingOrder(order_details)
        if pending_order is None:
            continue
        if order_details['status'] == STATUS_CANCELLED:
            pending_orders[order_details['user_id']].remove(pending_order)
        elif order_details['status'] == STATUS_REJECTED:
            pending_orders[order_details['user_id']].remove(pending_order)
            global order_variety
            order_variety = REGULAR_ORDER
        elif order_details['status'] == STATUS_COMPLETE:
            updateFundAvailable(order_details['user_id'])
            if pending_order['enter_or_exit'] == ENTER:
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
        updateAmountAtRisk(ENTER, order_details['user_id'], order_details['average_price'], order_details['filled_quantity'])
    else:
        new_position = constructNewPosition(order_details)
    current_positions[order_details['instrument_token']].append(new_position)

def updateAmountAtRisk(enter_or_exit, zerodha_user_id, price, number_of_stocks):
    if enter_or_exit == ENTER:
        user_amount_at_risk[zerodha_user_id] = user_amount_at_risk[zerodha_user_id] + (price * number_of_stocks * POSITION_STOPLOSS_PERCENT / 100.0)
    else:
        user_amount_at_risk[zerodha_user_id] = user_amount_at_risk[zerodha_user_id] - (price * number_of_stocks * POSITION_STOPLOSS_PERCENT / 100.0)

def updateExitOrderComplete(order_details):
    current_positions_for_instrument = current_positions[order_details['instrument_token']]
    for position in current_positions_for_instrument:
        if position['user_id'] == order_details['user_id']:
            updateUserNetValue(position['user_id'], position, order_details['average_price'])
            updateAmountAtRisk(EXIT, position['user_id'], position['entry_price'], position['number_of_stocks'])
            current_positions_for_instrument.remove(position)
            return

def updateUserNetValue(user_id, position, exit_price):
    trade_profit = (position['entry_price'] - exit_price) * position['number_of_stocks']
    user_net_value[user_id] += trade_profit
    user_stoploss[user_id] = max(user_stoploss[user_id], updateUserStoploss(user_id))

def updateUserStoploss(user_id):
    remaining_target = user_target_value[user_id] - user_net_value[user_id] if user_target_value[user_id] > user_net_value[user_id] else 0
    return user_net_value[user_id] - (remaining_target * USER_STOPLOSS_RANGE / (user_target_value[user_id] - user_initial_value[user_id]) + USER_TARGET_STOPLOSS) * user_initial_value[user_id] / 100.0

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
    new_position['stoploss'] = order_details['average_price'] * (100.0 + POSITION_STOPLOSS_PERCENT) / 100.0
    new_position['target_price'] = order_details['average_price'] * (100.0 - POSITION_TARGET_PERCENT) / 100.0
    new_position['slrange_tprofit_ratio'] = POSITION_STOPLOSS_RANGE / (new_position['entry_price'] - new_position['target_price'])
    new_position['one_percent_entry_price'] = new_position['entry_price'] / 100.0
    if second_leg_order_details:
        new_position['order_id'] = second_leg_order_details['order_id']
        new_position['parent_order_id'] = second_leg_order_details['parent_order_id']
    return new_position

def scheduleExit():
    global ENTRY_TIME_END
    try:
        controls = Controls.objects.get(control_id=settings.CONTROLS_RECORD_ID)
        ENTRY_TIME_END = controls.entry_time_end.time()
        exit_time = controls.exit_time.time()
    except Exception as e:
        ENTRY_TIME_END = now().time().replace(hour=settings.ENTRY_TIME_END[0], minute=settings.ENTRY_TIME_END[1],
                                              second=settings.ENTRY_TIME_END[2])
        exit_time =  now().time().replace(hour=settings.EXIT_TIME[0], minute=settings.EXIT_TIME[1])
    exit_time_str = str(exit_time.hour) + ':' + str(exit_time.minute)
    schedule.every().day.at(exit_time_str).do(exitAllPositions)

def exitAllPositions():
    for instrument_token in current_positions.keys():
        for position in current_positions[instrument_token]:
            sendSignal(EXIT, instrument_token, position)

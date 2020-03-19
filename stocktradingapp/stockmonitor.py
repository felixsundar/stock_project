import logging
import threading
from datetime import datetime, time

import pytz
from django.contrib.auth.models import User
from kiteconnect import KiteTicker, KiteConnect

from stock_project import settings

logging.basicConfig(filename=settings.LOG_FILE_PATH, level=logging.DEBUG)

def startStockMonitorThread():
    stockMonitorThread = threading.Thread(target=runStockMonitor, daemon=True, name='stockMonitor_thread')
    stockMonitorThread.start()

def runStockMonitor():
    user = User.objects.get_by_natural_key('felixsundar')
    user_zerodha = user.user_zerodha.first()
    if user_zerodha is None:
        return

    kws = KiteTicker(user_zerodha.api_key, user_zerodha.access_token)

    def on_ticks(ws, ticks):
        # Callback to receive ticks.
        logging.debug("Ticks: {}".format(ticks))

    def on_connect(ws, response):
        # Callback on successful connect.
        # Subscribe to a list of instrument_tokens (RELIANCE and ACC here).
        ws.subscribe([738561, 5633])

        # Set RELIANCE to tick in `full` mode.
        ws.set_mode(ws.MODE_FULL, [738561])

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
    ist = pytz.timezone(settings.TIME_ZONE)
    start_time = time(hour=settings.START_HOUR, minute=settings.START_MINUTE, tzinfo=ist)
    end_time = time(hour=settings.END_HOUR, minute=settings.END_MINUTE, tzinfo=ist)
    while True:
        current_datetime = datetime.now(ist)
        current_day = current_datetime.isoweekday()
        current_time = current_datetime.time()
        if current_day != 6 and current_day != 7 and current_time >= start_time and current_time < end_time:
            if not kws.is_connected():
                kws.connect(threaded=True)
        elif kws.is_connected():
            kws.close()

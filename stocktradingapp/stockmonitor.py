import logging
from django.contrib.auth.models import User
from kiteconnect import KiteTicker

from stock_project import settings

logging.basicConfig(filename=settings.LOG_FILE_PATH, level=logging.DEBUG)

def runStockMonitor():
    user = User.objects.get_by_natural_key(settings.PRIMARY_USERNAME)
    user_zerodha = user.user_zerodha.first()
    if user_zerodha is None:
        return
    kws = KiteTicker(user_zerodha.api_key, user_zerodha.access_token)

    def on_ticks(ws, ticks):
        # Callback to receive ticks.
        print('ticks: ',ticks)

    def on_connect(ws, response):
        # Callback on successful connect.
        # Subscribe to a list of instrument_tokens (RELIANCE and ACC here).
        ws.subscribe([738561])

        # Set RELIANCE to tick in `full` mode.
        ws.set_mode(ws.MODE_LTP, [738561])

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
    kws.connect(threaded=True)

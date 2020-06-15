import threading

from django.apps import AppConfig


class StocktradingappConfig(AppConfig):
    name = 'stocktradingapp'

    def ready(self):
        from stocktradingapp import stockmonitor
        stockMonitorThread = threading.Thread(target=stockmonitor.runStockMonitor, daemon=True, name='stockMonitor_thread')
        stockMonitorThread.start()
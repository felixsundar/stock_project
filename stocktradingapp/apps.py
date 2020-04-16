import threading

from django.apps import AppConfig


class StocktradingappConfig(AppConfig):
    name = 'stocktradingapp'

    def ready(self):
        # from stocktradingapp import stockmonitor
        from stocktradingapp import pythontest
        stockMonitorThread = threading.Thread(target=pythontest.runTests, daemon=True, name='stockMonitor_thread')
        stockMonitorThread.start()
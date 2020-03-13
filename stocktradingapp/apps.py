from django.apps import AppConfig


class StocktradingappConfig(AppConfig):
    name = 'stocktradingapp'

    def ready(self):
        from stocktradingapp import stockmonitor
        #stockmonitor.startStockMonitorThread()
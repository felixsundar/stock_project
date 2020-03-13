from django.apps import AppConfig


class StocktradingappConfig(AppConfig):
    name = 'stocktradingapp'

    def ready(self):
        pass
        #from stocktradingapp import stockmonitor
        #stockmonitor.startStockMonitorThread()
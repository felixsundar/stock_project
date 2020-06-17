from django.contrib import admin

# Register your models here.
from stocktradingapp.models import ZerodhaAccount, Stock, KiteConnectApp, Controls, LiveMonitor


class StockAdmin(admin.ModelAdmin):
    list_filter = ('active',)
    list_display = ('stock_id', 'trading_symbol', 'stock_name', 'instrument_token', 'mis_margin', 'co_margin', 'active')

class ZerodhaAccountAdmin(admin.ModelAdmin):
    list_display = ('hstock_user', 'user_id', 'user_name', 'email')

class KiteConnectAppAdmin(admin.ModelAdmin):
    list_display = ('hstock_user', 'api_key', 'api_secret')

class LiveMonitorAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'initial_value', 'value_at_risk', 'stoploss', 'current_value', 'profit', 'commission', 'net_profit_percent')

admin.site.register(Stock, StockAdmin)
admin.site.register(ZerodhaAccount, ZerodhaAccountAdmin)
admin.site.register(KiteConnectApp, KiteConnectAppAdmin)
admin.site.register(Controls)
admin.site.register(LiveMonitor, LiveMonitorAdmin)
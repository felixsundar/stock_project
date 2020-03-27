from django.contrib import admin

# Register your models here.
from stocktradingapp.models import ZerodhaAccount, Stock

class StockAdmin(admin.ModelAdmin):
    list_filter = ('active',)
    list_display = ('stock_id', 'trading_symbol', 'stock_name', 'instrument_token', 'mis_margin', 'co_margin', 'active')

admin.site.register(ZerodhaAccount)
admin.site.register(Stock, StockAdmin)
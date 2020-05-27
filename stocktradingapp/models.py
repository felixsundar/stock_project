from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField
from django.db import models

# Create your models here.

class KiteConnectApp(models.Model):
    hstock_user = models.ForeignKey(User, related_name='user_kite_app', on_delete=models.CASCADE, primary_key=True)
    api_key = models.CharField(max_length=100, unique=True)
    api_secret = models.CharField(max_length=100, unique=True)

class ZerodhaAccount(models.Model):
    hstock_user = models.ForeignKey(User, related_name='user_zerodha', on_delete=models.CASCADE, primary_key=True)
    access_token = models.CharField(max_length=100)
    access_token_time = models.DateTimeField()
    refresh_token = models.CharField(max_length=100, null=True, blank=True)
    public_token = models.CharField(max_length=100, null=True, blank=True)
    api_key = models.CharField(max_length=100)
    user_id = models.CharField(max_length=100, unique=True)
    user_name = models.CharField(max_length=100)
    user_shortname = models.CharField(max_length=100)
    email = models.CharField(max_length=100)
    user_type = models.CharField(max_length=100, null=True, blank=True)
    broker = models.CharField(max_length=100, null=True, blank=True)
    exchanges = JSONField(null=True, blank=True)
    products = JSONField(null=True, blank=True)
    order_types = JSONField(null=True, blank=True)
    fund_available = models.FloatField(default=0.0)
    is_active = models.BooleanField(default=True)

class Stock(models.Model):
    stock_id = models.AutoField(primary_key=True)
    instrument_token = models.BigIntegerField(unique=True)
    trading_symbol = models.CharField(max_length=20, unique=True)
    stock_name = models.CharField(max_length=100, unique=True)
    mis_margin = models.FloatField()
    co_margin = models.FloatField()
    co_trigger_percent_lower = models.FloatField()
    co_trigger_percent_upper = models.FloatField()
    active = models.BooleanField()

class Controls(models.Model):
    control_id = models.CharField(max_length=40, primary_key=True)
    entry_trigger_percent = models.FloatField(help_text='default: 0.5')
    max_risk_percent_per_trade = models.FloatField(help_text='default: 0.5')
    max_investment_per_position = models.FloatField(help_text='default: 300000.0')
    min_investment_per_position = models.FloatField(help_text='default: 1000.0')
    position_stoploss_percent = models.FloatField(help_text='default: 0.5')
    position_target_stoploss = models.FloatField(help_text='default: 0.1')
    position_target_percent = models.FloatField(help_text='default: 1.0')
    user_stoploss_percent = models.FloatField(help_text='default: 5.0')
    user_target_stoploss = models.FloatField(help_text='default: 1.0')
    user_target_percent = models.FloatField(help_text='default: 10.0')
    commission_percent = models.FloatField(help_text='default: 0.06')
    entry_time_start = models.DateTimeField(help_text='default: 9:15:04')
    entry_time_end = models.DateTimeField(help_text='default: 15:18:00')
    exit_time = models.DateTimeField(help_text='default: 15:19:00')
    trading_side = models.IntegerField(choices=[(1, 'Short Side'), (2, 'Long Side'), (3, 'Mock Short Side'),
                                                (4, 'Mock Long Side'), (5, 'Don\'t Trade')], default=1)
    order_variety = models.CharField(max_length=20, choices=[('co', 'CO ORDER'), ('regular', 'REGULAR ORDER')])
    mock_trading_initial_value = models.FloatField(help_text='default:100000.0')

class LiveMonitor(models.Model):
    hstock_user = models.ForeignKey(User, related_name='user_live_monitor', on_delete=models.CASCADE, unique=True)
    user_id = models.CharField(max_length=100, primary_key=True)
    initial_value = models.FloatField()
    current_value = models.FloatField()
    stoploss = models.FloatField()
    value_at_risk = models.FloatField()
    profit_percent = models.FloatField()
    do_trading = models.BooleanField(default=True)
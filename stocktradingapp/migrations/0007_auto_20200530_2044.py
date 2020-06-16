# Generated by Django 3.0.4 on 2020-05-30 20:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stocktradingapp', '0006_auto_20200529_0848'),
    ]

    operations = [
        migrations.RenameField(
            model_name='livemonitor',
            old_name='profit_percent',
            new_name='net_profit_percent',
        ),
        migrations.RemoveField(
            model_name='controls',
            name='commission_percent',
        ),
        migrations.AddField(
            model_name='livemonitor',
            name='commission',
            field=models.FloatField(default=0.0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='livemonitor',
            name='profit',
            field=models.FloatField(default=0.0),
            preserve_default=False,
        ),
    ]
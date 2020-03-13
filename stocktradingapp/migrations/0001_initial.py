# Generated by Django 3.0.4 on 2020-03-13 11:10

from django.conf import settings
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0011_update_proxy_permissions'),
    ]

    operations = [
        migrations.CreateModel(
            name='ZerodhaAccount',
            fields=[
                ('hstock_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='user_zerodha', serialize=False, to=settings.AUTH_USER_MODEL)),
                ('access_token', models.CharField(max_length=100)),
                ('refresh_token', models.CharField(max_length=100)),
                ('public_token', models.CharField(max_length=100)),
                ('api_key', models.CharField(max_length=100)),
                ('user_id', models.CharField(max_length=100)),
                ('user_name', models.CharField(max_length=100)),
                ('user_shortname', models.CharField(max_length=100)),
                ('email', models.CharField(max_length=100)),
                ('user_type', models.CharField(max_length=100)),
                ('broker', models.CharField(max_length=100)),
                ('exchanges', django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True)),
                ('products', django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True)),
                ('order_types', django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True)),
            ],
        ),
    ]

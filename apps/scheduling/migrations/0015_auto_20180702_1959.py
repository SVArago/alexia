# -*- coding: utf-8 -*-
# Generated by Django 1.10.8 on 2018-07-02 17:59
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0014_auto_20180702_1610'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bartenderavailability',
            name='availability',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='scheduling.Availability', verbose_name='availability'),
        ),
    ]

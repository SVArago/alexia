# -*- coding: utf-8 -*-
# Generated by Django 1.10.8 on 2018-07-02 14:10
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0013_merge'),
    ]

    operations = [
        migrations.AddField(
            model_name='bartenderavailability',
            name='comment',
            field=models.TextField(blank=True, default=''),
        ),
    ]
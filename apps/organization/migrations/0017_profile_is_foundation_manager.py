# -*- coding: utf-8 -*-
# Generated by Django 1.9.11 on 2016-12-06 10:42
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0016_merge'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='is_foundation_manager',
            field=models.BooleanField(default=False, help_text='Designates that this user is manager of the purchasing foundation.', verbose_name='is foundation manager'),
        ),
    ]
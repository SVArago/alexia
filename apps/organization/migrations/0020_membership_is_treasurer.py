# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0019_merge'),
    ]

    operations = [
        migrations.AddField(
            model_name='membership',
            name='is_treasurer',
            field=models.BooleanField(default=False, verbose_name='may see and manage finances'),
        ),
    ]

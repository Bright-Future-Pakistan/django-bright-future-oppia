# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('oppia', '0010_move_userprofile'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='cohort',
            name='course',
        ),
        migrations.RemoveField(
            model_name='points',
            name='cohort',
        ),
    ]

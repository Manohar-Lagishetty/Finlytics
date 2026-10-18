# Reverts the mobile-sync scaffolding added in 0005/0006 now that the
# Flutter mobile app (and its local-first sync endpoint) has been removed:
# drops the uuid/updated_at columns added to the syncable models and the
# SyncTombstone table.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('expenses', '0006_alter_synctombstone_user'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='budget',
            name='uuid',
        ),
        migrations.RemoveField(
            model_name='budget',
            name='updated_at',
        ),
        migrations.RemoveField(
            model_name='category',
            name='uuid',
        ),
        migrations.RemoveField(
            model_name='category',
            name='updated_at',
        ),
        migrations.RemoveField(
            model_name='expense',
            name='uuid',
        ),
        migrations.RemoveField(
            model_name='expense',
            name='updated_at',
        ),
        migrations.RemoveField(
            model_name='income',
            name='uuid',
        ),
        migrations.RemoveField(
            model_name='income',
            name='updated_at',
        ),
        migrations.RemoveField(
            model_name='recurringincome',
            name='uuid',
        ),
        migrations.RemoveField(
            model_name='recurringincome',
            name='updated_at',
        ),
        migrations.DeleteModel(
            name='SyncTombstone',
        ),
    ]

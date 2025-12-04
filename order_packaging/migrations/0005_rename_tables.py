# Generated migration to handle app rename from packaging to order_packaging
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('order_packaging', '0004_packagingrecord_height_packagingrecord_length_and_more'),
    ]

    operations = [
        # No database changes needed - we use db_table in Meta to keep existing table names
        # This migration just marks the transition
    ]

# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0003_add_device_model"),
    ]

    operations = [
        migrations.AddField(
            model_name="device",
            name="mac_address",
            field=models.CharField(blank=True, max_length=17, verbose_name="MAC-адрес"),
        ),
    ]

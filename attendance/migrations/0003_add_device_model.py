# Generated manually for Device model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0002_dailyattendancesummary"),
    ]

    operations = [
        migrations.CreateModel(
            name="Device",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=128, verbose_name="Название")),
                ("address", models.CharField(blank=True, max_length=255, verbose_name="Адрес (IP или URL)")),
                (
                    "device_id",
                    models.CharField(
                        help_text="Строка из событий (ipAddress, deviceName и т.п.)",
                        max_length=64,
                        unique=True,
                        verbose_name="ID устройства в событиях",
                    ),
                ),
                (
                    "direction",
                    models.CharField(
                        choices=[
                            ("entrance", "Вход"),
                            ("exit", "Выход"),
                            ("both", "Вход и выход"),
                        ],
                        default="both",
                        max_length=16,
                        verbose_name="Направление",
                    ),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="Активно")),
                ("last_seen", models.DateTimeField(blank=True, null=True, verbose_name="Последнее событие")),
                ("notes", models.TextField(blank=True, verbose_name="Примечание")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Устройство",
                "verbose_name_plural": "Устройства",
                "ordering": ["name"],
            },
        ),
    ]

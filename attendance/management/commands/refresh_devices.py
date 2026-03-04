"""
Короткая команда для обновления устройств в нашей сети.

После настройки под текущую подсеть/интерфейс можно просто вызывать:

    python manage.py refresh_devices

и она будет работать как:

    python manage.py discover_devices --subnet 192.168.68.0/24 --interface enp2s0
"""

from django.core.management.base import BaseCommand

from attendance.management.commands.discover_devices import Command as DiscoverCommand


class Command(BaseCommand):
    help = "Обновить список устройств в локальной сети (фиксированные subnet/interface)."

    def handle(self, *args, **options):
        discover_cmd = DiscoverCommand()
        # Жёстко используем нужную вам подсеть и интерфейс.
        return discover_cmd.handle(
            subnet="192.168.68.0/24",
            interface="enp2s0",
            arp_only=False,
        )


"""
Обнаружение устройств в сети по ARP и обновление Device (IP, MAC).
Запускать на хосте в той же подсети, что и терминалы (или с сервера, если он в той же LAN).

Примеры:
  python manage.py discover_devices
  python manage.py discover_devices --subnet 192.168.1.0/24
  python manage.py discover_devices --interface eth0
"""
import re
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.db.models import Q
from django.core.management.base import BaseCommand

from attendance.models import Device


def parse_arp_scan(output: str) -> list[tuple[str, str]]:
    """Парсим вывод arp-scan: строки вида '192.168.1.10\t00:11:22:33:44:55\t...'"""
    mac_ip_pairs = []
    # arp-scan: IP \t MAC \t Vendor
    for line in output.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2:
            ip = parts[0]
            mac = parts[1]
            if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip) and re.match(
                r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$", mac
            ):
                mac_ip_pairs.append((ip, mac))
    return mac_ip_pairs


def read_arp_table_linux() -> list[tuple[str, str]]:
    """Читаем /proc/net/arp (Linux): IP и MAC для недавно виденных хостов."""
    pairs = []
    path = Path("/proc/net/arp")
    if not path.exists():
        return pairs
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    # skip header
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 6 and parts[3] != "00:00:00:00:00:00":
            ip = parts[0]
            mac = parts[3]
            pairs.append((ip, mac))
    return pairs


class Command(BaseCommand):
    help = "Обнаружить устройства в подсети (ARP) и обновить Device: address, mac_address."

    def add_arguments(self, parser):
        parser.add_argument(
            "--subnet",
            default="192.168.1.0/24",
            help="Подсеть для сканирования (по умолчанию 192.168.1.0/24)",
        )
        parser.add_argument(
            "--interface",
            default="",
            help="Сетевой интерфейс для arp-scan (например eth0)",
        )
        parser.add_argument(
            "--arp-only",
            action="store_true",
            help="Только прочитать ARP-таблицу (/proc/net/arp), не вызывать arp-scan",
        )

    def handle(self, *args, **options):
        subnet = options["subnet"]
        interface = options["interface"]
        arp_only = options["arp_only"]

        pairs: list[tuple[str, str]] = []

        if not arp_only:
            cmd = ["arp-scan", "-q", "-l"]
            if interface:
                cmd.extend(["-I", interface])
            else:
                cmd.append(subnet)
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.stdout:
                    # Даже если arp-scan вернул код != 0, но вывел что-то в stdout — пробуем это распарсить.
                    pairs = parse_arp_scan(result.stdout)
                    self.stdout.write(
                        f"arp-scan (rc={result.returncode}): найдено {len(pairs)} записей по выводу команды."
                    )
                elif result.returncode != 0:
                    self.stdout.write(self.style.WARNING(
                        f"arp-scan завершился с кодом {result.returncode} без вывода, используем ARP-таблицу."
                    ))
            except FileNotFoundError:
                self.stdout.write(self.style.WARNING(
                    "arp-scan не найден. Установите: sudo apt install arp-scan. Используем /proc/net/arp."
                ))
            except subprocess.TimeoutExpired:
                self.stdout.write(self.style.WARNING("arp-scan таймаут, используем ARP-таблицу."))

        if not pairs and Path("/proc/net/arp").exists():
            pairs = read_arp_table_linux()
            self.stdout.write(f"ARP-таблица: найдено {len(pairs)} записей.")

        if not pairs:
            self.stdout.write(
                self.style.WARNING(
                    "Нет данных об устройствах. Запустите на хосте в той же подсети."
                )
            )
            return

        # Фильтрация только по MAC-адресам:
        # по умолчанию используем старое поведение (только Hikvision 88:de:39),
        # но даём возможность переопределить список префиксов через settings.DISCOVER_DEVICE_MAC_PREFIXES.
        default_prefixes = ("88:de:39", "88:DE:39")
        allowed_prefixes = getattr(
            settings, "DISCOVER_DEVICE_MAC_PREFIXES", default_prefixes
        )
        # Если в настройках явно указано пустое значение ([], ()), то не фильтруем по префиксам вообще.
        if allowed_prefixes:
            prefixes_lower = tuple(p.lower() for p in allowed_prefixes)
            filtered_pairs = [
                (ip, mac)
                for ip, mac in pairs
                if mac.lower().startswith(prefixes_lower)
            ]
            skipped = len(pairs) - len(filtered_pairs)
            if skipped:
                self.stdout.write(
                    self.style.WARNING(
                        f"Пропущено устройств с MAC не из списка {allowed_prefixes}: {skipped}"
                    )
                )
            if not filtered_pairs:
                self.stdout.write(
                    self.style.WARNING(
                        f"Не найдено устройств с MAC, начинающимся на один из {allowed_prefixes}."
                    )
                )
                return
        else:
            filtered_pairs = pairs

        updated = 0
        for ip, mac in filtered_pairs:
            # Сначала ищем устройство по MAC — это устойчивый идентификатор,
            # даже если IP меняется (динамический адрес по DHCP).
            dev = Device.objects.filter(mac_address__iexact=mac).first()
            if dev:
                dev.address = ip
                dev.device_id = ip
                dev.save(update_fields=["address", "device_id"])
                updated += 1
                continue

            # Если MAC ещё не знаем, пробуем найти по текущему IP (address или device_id)
            qs = Device.objects.filter(Q(address=ip) | Q(device_id=ip))
            if qs.exists():
                qs.update(mac_address=mac, address=ip)
                updated += 1
            else:
                # Авто-создаём запись по IP/MAC (device_id = IP)
                Device.objects.get_or_create(
                    device_id=ip,
                    defaults={"name": ip, "address": ip, "mac_address": mac, "is_active": True},
                )
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Обновлено/создано устройств: {updated}."))

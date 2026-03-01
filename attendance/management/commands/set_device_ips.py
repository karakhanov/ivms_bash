"""
Задать правильные IP устройств: по имени или по текущему device_id.
Удобно, когда записи в базе получились с неверными IP (discover/события), а реальные адреса известны.

Примеры:
  python manage.py set_device_ips --csv devices.csv
  python manage.py set_device_ips --set "Терминал 1:192.168.1.100" "Терминал 2:192.168.1.101"
  python manage.py set_device_ips --by-id --set "192.168.1.50:192.168.1.100"

CSV: две колонки без заголовка или с заголовком name,address (или device_id,address при --by-id).
Разделитель — запятая. Кодировка UTF-8.
"""
import csv
import io
from pathlib import Path

from django.core.management.base import BaseCommand

from attendance.models import Device


class Command(BaseCommand):
    help = "Задать правильные IP устройств по имени или по текущему device_id (из CSV или --set)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            type=str,
            help="Путь к CSV: колонки name,address (или device_id,address при --by-id).",
        )
        parser.add_argument(
            "--set",
            nargs="+",
            type=str,
            help='Пары "имя:IP" или "device_id:IP" при --by-id.',
        )
        parser.add_argument(
            "--by-id",
            action="store_true",
            help="Искать устройство по device_id, а не по name (для --set и CSV).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать, что будет изменено, не сохранять.",
        )

    def handle(self, *args, **options):
        csv_path = options.get("csv")
        set_pairs = options.get("set")
        by_id = options.get("by_id")
        dry_run = options.get("dry_run", False)

        updates = []

        if csv_path:
            path = Path(csv_path)
            if not path.exists():
                self.stderr.write(self.style.ERROR(f"Файл не найден: {csv_path}"))
                return
            with open(path, encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)
            if not rows:
                self.stderr.write(self.style.WARNING("CSV пуст."))
                return
            # Пропуск заголовка, если похож на name,address
            start = 0
            if len(rows[0]) >= 2 and rows[0][0].lower() in ("name", "device_id") and rows[0][1].lower() == "address":
                start = 1
            for row in rows[start:]:
                if len(row) < 2:
                    continue
                key = row[0].strip()
                ip = row[1].strip()
                if key and ip:
                    updates.append((key, ip))
        elif set_pairs:
            for part in set_pairs:
                if ":" in part:
                    key, ip = part.split(":", 1)
                    updates.append((key.strip(), ip.strip()))
                else:
                    self.stderr.write(self.style.WARNING(f"Пропуск (ожидается 'имя:IP'): {part}"))
        else:
            self.stderr.write(self.style.ERROR("Укажите --csv путь или --set \"имя:IP\" ..."))
            return

        if not updates:
            self.stderr.write(self.style.WARNING("Нет пар для обновления."))
            return

        field = "device_id" if by_id else "name"
        updated = 0
        for key, ip in updates:
            qs = Device.objects.filter(**{field: key})
            dev = qs.first()
            if not dev:
                self.stdout.write(self.style.WARNING(f"Устройство не найдено ({field}={key!r})"))
                continue
            if dry_run:
                self.stdout.write(f"Будет: {dev.name} (id={dev.device_id}) -> address={ip}, device_id={ip}")
                updated += 1
                continue
            dev.address = ip
            # device_id делаем равным IP только если не занят другим устройством
            if not Device.objects.filter(device_id=ip).exclude(pk=dev.pk).exists():
                dev.device_id = ip
                dev.save(update_fields=["address", "device_id"])
            else:
                dev.save(update_fields=["address"])
            self.stdout.write(self.style.SUCCESS(f"Обновлено: {dev.name} -> {ip}"))
            updated += 1

        if not dry_run and updated:
            self.stdout.write(self.style.SUCCESS(f"Обновлено устройств: {updated}"))
        elif dry_run:
            self.stdout.write(f"Будет обновлено: {updated} (запустите без --dry-run).")

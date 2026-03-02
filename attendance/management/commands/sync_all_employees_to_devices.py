"""
Синхронизировать всех сотрудников на все настроенные терминалы Hikvision.

Удобно использовать по расписанию (cron/systemd timer), чтобы новые сотрудники
и обновлённые фото автоматически попадали на устройства.

Примеры:
  python manage.py sync_all_employees_to_devices
  python manage.py sync_all_employees_to_devices --only-active --only-with-photo
"""

from django.core.management.base import BaseCommand

from employees.models import Employee
from hikvision.client import sync_employee_to_devices


class Command(BaseCommand):
    help = "Отправить всех (или отфильтрованных) сотрудников на все терминалы Hikvision."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only-active",
            action="store_true",
            help="Только активные сотрудники (is_active=True).",
        )
        parser.add_argument(
            "--only-with-photo",
            action="store_true",
            help="Только сотрудники с загруженным фото.",
        )
        parser.add_argument(
            "--external-id",
            type=str,
            help="Синхронизировать только одного сотрудника по external_id (ПИНФЛ).",
        )
        parser.add_argument(
            "--employee-id",
            type=int,
            help="Синхронизировать только одного сотрудника по ID.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Ограничить количество сотрудников (0 = без ограничения).",
        )

    def handle(self, *args, **options):
        only_active: bool = options["only_active"]
        only_with_photo: bool = options["only_with_photo"]
        external_id: str | None = options.get("external_id")
        employee_id: int | None = options.get("employee_id")
        limit: int = options["limit"]

        qs = Employee.objects.all().order_by("id")
        if external_id:
            qs = qs.filter(external_id=external_id)
        if employee_id:
            qs = qs.filter(pk=employee_id)
        if only_active:
            qs = qs.filter(is_active=True)
        if only_with_photo:
            qs = qs.exclude(photo__isnull=True).exclude(photo="")
        if limit and limit > 0:
            qs = qs[:limit]

        total = qs.count()
        if not total:
            self.stdout.write(self.style.WARNING("Нет сотрудников, подходящих под фильтр."))
            return

        self.stdout.write(f"Синхронизация сотрудников: всего {total}.")

        ok_users = 0
        ok_photos = 0
        errors = 0

        for emp in qs:
            results = sync_employee_to_devices(emp)
            if not results:
                self.stdout.write(
                    self.style.WARNING(
                        f"{emp} → нет настроенных устройств (HIKVISION_DEVICES / HIKVISION_DEVICE_URL)."
                    )
                )
                errors += 1
                continue
            for r in results:
                if r["user_ok"]:
                    ok_users += 1
                else:
                    errors += 1
                    self.stdout.write(
                        self.style.WARNING(f"{emp} → {r['base_url']}: user error: {r['user_message']}")
                    )
                if r["photo_ok"]:
                    ok_photos += 1
                elif r["photo_message"] not in {"no_photo", "skipped"}:
                    errors += 1
                    self.stdout.write(
                        self.style.WARNING(f"{emp} → {r['base_url']}: photo error: {r['photo_message']}")
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Готово. Успешно отправлено пользователей: {ok_users}, фото: {ok_photos}, ошибок: {errors}."
            )
        )


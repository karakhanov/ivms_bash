import csv
import os

from django.db import transaction
from django.utils.text import slugify

from employees.models import Department, Position, WorkSchedule, Employee


# Путь к CSV с сотрудниками (руйхат.csv / руйхатutf.csv и т.п.)
CSV_PATH = r"c:\bashkent\руйхатutf.csv"


def make_code(name: str) -> str:
    """
    Строим код из имени.
    Для кириллицы используем allow_unicode=True, чтобы slugify не возвращал пустую строку,
    а при необходимости добавляем хэш, чтобы коды были уникальными.
    """
    raw = (name or "").strip()
    base = slugify(raw, allow_unicode=True).replace("-", "_")
    if not base:
        base = "item"
    # добавим короткий хэш, чтобы разные имена не схлопывались в один код
    suffix = abs(hash(raw)) % 10_000
    code = f"{base}_{suffix}"
    return code[:30]


def collect_from_csv():
    if not os.path.exists(CSV_PATH):
        raise SystemExit(f"CSV not found: {CSV_PATH}")

    departments = {}
    positions = {}
    schedules = {}

    # Файл сохранён в Excel → обычно кодировка cp1251
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";")
        for row in reader:
            if not row:
                continue
            first_col = (row[0] or "").strip()
            # пропускаем заголовки/пустые
            if not first_col or first_col.startswith("№"):
                continue
            if len(row) < 7:
                continue

            # №;Фамилия;Исми;Шариф;Лавозим;Бўлим;Иш графиги;...
            (
                _,
                last_name,
                first_name,
                middle_name,
                pos_name,
                dept_name,
                schedule_name,
                *rest,
            ) = row

            dept_name = (dept_name or "").strip()
            pos_name = (pos_name or "").strip()
            schedule_name = (schedule_name or "").strip()

            if dept_name:
                departments[dept_name] = True
            if dept_name and pos_name:
                positions[(dept_name, pos_name)] = True
            if schedule_name:
                schedules[schedule_name] = True

    print(f"Найдено отделов в CSV: {len(departments)}")
    print(f"Найдено должностей (dept+position) в CSV: {len(positions)}")
    print(f"Найдено графиков в CSV: {len(schedules)}")

    return departments, positions, schedules


@transaction.atomic
def seed():
    departments, positions, schedules = collect_from_csv()

    # Отделы: короткие латинские коды dep01, dep02, ...
    dept_map = {}
    for idx, name in enumerate(sorted(departments.keys()), start=1):
        code = f"dep{idx:02d}"
        obj, _ = Department.objects.get_or_create(
            name=name,
            defaults={"code": code},
        )
        if not obj.code:
            obj.code = code
            obj.save(update_fields=["code"])
        dept_map[name] = obj
    print(f"Создано/найдено отделов: {Department.objects.count()}")

    # Графики работы (время заглушкой, можно поменять руками в админке)
    for name in sorted(schedules.keys()):
        WorkSchedule.objects.get_or_create(
            name=name,
            defaults={
                "start_time": "09:00",
                "end_time": "18:00",
                "is_default": False,
                "is_active": True,
            },
        )
    print(f"Создано/найдено графиков: {WorkSchedule.objects.count()}")

    # Должности: коды pos001, pos002, ...
    for idx, (dept_name, pos_name) in enumerate(sorted(positions.keys()), start=1):
        dept = dept_map.get(dept_name)
        code = f"pos{idx:03d}"
        Position.objects.get_or_create(
            code=code,
            defaults={
                "name": pos_name,
                "department": dept,
                "is_active": True,
            },
        )
    print(f"Создано/найдено должностей: {Position.objects.count()}")

    # Сотрудники (external_id = ПИНФЛ)
    created = 0
    updated = 0
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";")
        for row in reader:
            if not row:
                continue
            first_col = (row[0] or "").strip()
            if not first_col or first_col.startswith("№"):
                continue
            if len(row) < 8:
                continue

            (
                _,
                last_name,
                first_name,
                middle_name,
                pos_name,
                dept_name,
                schedule_name,
                pinfl,
                *rest,
            ) = row

            pinfl = (pinfl or "").strip()
            if not pinfl:
                continue

            first_name = (first_name or "").strip()
            last_name = (last_name or "").strip()
            middle_name = (middle_name or "").strip()
            pos_name = (pos_name or "").strip()
            dept_name = (dept_name or "").strip()
            schedule_name = (schedule_name or "").strip()
            phone = (rest[0] if rest else "").strip()

            dept_obj = Department.objects.filter(name=dept_name).first()
            pos_obj = None
            if dept_obj:
                pos_obj = Position.objects.filter(name=pos_name, department=dept_obj).first()
            if not pos_obj:
                pos_obj = Position.objects.filter(name=pos_name).first()
            ws_obj = WorkSchedule.objects.filter(name=schedule_name).first()

            obj, created_flag = Employee.objects.update_or_create(
                external_id=pinfl,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "middle_name": middle_name,
                    "position": pos_name,
                    "department": dept_name,
                    "type_of_work": schedule_name,
                    "pinfl": pinfl,
                    "phone_number": phone,
                    "department_ref": dept_obj,
                    "position_ref": pos_obj,
                    "work_schedule_ref": ws_obj,
                    "is_active": True,
                },
            )
            if created_flag:
                created += 1
            else:
                updated += 1

    print(f"Создано сотрудников: {created}, обновлено: {updated}")


if __name__ == "__main__":
    seed()


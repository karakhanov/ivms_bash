from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from django.db.models import QuerySet
from django.utils import timezone

from .models import AttendanceLog


def _normalize_to_datetime(value: date | datetime) -> datetime:
    """
    Convert a date or datetime to an aware datetime in the current timezone.
    - date -> start of day
    - naive datetime -> make_aware
    - aware datetime -> converted to current timezone
    """
    if isinstance(value, date) and not isinstance(value, datetime):
        dt = datetime.combine(value, datetime.min.time())
    else:
        dt = value  # type: ignore[assignment]

    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt.astimezone(timezone.get_current_timezone())


def get_logs_for_employee_in_range(
    employee_id: int,
    start: date | datetime,
    end: date | datetime,
) -> QuerySet[AttendanceLog]:
    """
    Fetch attendance logs for a specific employee in a given datetime range.

    Uses select_related to avoid N+1 queries on employee.
    """
    start_dt = _normalize_to_datetime(start)
    end_dt = _normalize_to_datetime(end)

    # Ensure end is inclusive to the end of the day when a date is passed
    if isinstance(end, date) and not isinstance(end, datetime):
        end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)

    return (
        AttendanceLog.objects.select_related("employee")
        .filter(
            employee_id=employee_id,
            event_time__range=(start_dt, end_dt),
        )
        .order_by("event_time")
    )


def get_logs_in_range(
    start: date | datetime,
    end: date | datetime,
    employee_id: Optional[int] = None,
) -> QuerySet[AttendanceLog]:
    """
    Fetch attendance logs for all employees (or a single employee if provided)
    in a given datetime range, optimized with select_related.
    """
    start_dt = _normalize_to_datetime(start)
    end_dt = _normalize_to_datetime(end)

    if isinstance(end, date) and not isinstance(end, datetime):
        end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)

    qs: QuerySet[AttendanceLog] = AttendanceLog.objects.select_related("employee").filter(
        event_time__range=(start_dt, end_dt),
    )

    if employee_id is not None:
        qs = qs.filter(employee_id=employee_id)

    return qs.order_by("employee_id", "event_time")


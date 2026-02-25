from datetime import datetime, timedelta

import pytest
from django.utils import timezone

from employees.models import Employee
from .models import AttendanceLog
from .services import AttendanceCalculationService


@pytest.mark.django_db
def test_normal_workday():
    tz = timezone.get_current_timezone()
    employee = Employee.objects.create(
        external_id="E1",
        first_name="Normal",
        last_name="Worker",
        department="IT",
        is_active=True,
    )

    day = datetime(2026, 2, 23, tzinfo=tz).date()
    first_in = datetime(2026, 2, 23, 9, 0, tzinfo=tz)
    last_out = datetime(2026, 2, 23, 18, 0, tzinfo=tz)

    AttendanceLog.objects.create(
        employee=employee,
        device_id="D1",
        event_type=AttendanceLog.EventType.IN,
        event_time=first_in,
        confidence_score=0.99,
    )
    AttendanceLog.objects.create(
        employee=employee,
        device_id="D1",
        event_type=AttendanceLog.EventType.OUT,
        event_time=last_out,
        confidence_score=0.99,
    )

    logs = AttendanceLog.objects.all()
    result = AttendanceCalculationService.calculate_daily_attendance(logs)

    summary = result[employee.id][day]
    assert pytest.approx(summary["worked_hours"], rel=1e-3) == 9.0
    assert summary["lateness_minutes"] == 0
    assert summary["overtime_minutes"] == 0


@pytest.mark.django_db
def test_late_arrival():
    tz = timezone.get_current_timezone()
    employee = Employee.objects.create(
        external_id="E2",
        first_name="Late",
        last_name="Worker",
        department="IT",
        is_active=True,
    )

    day = datetime(2026, 2, 23, tzinfo=tz).date()
    first_in = datetime(2026, 2, 23, 9, 30, tzinfo=tz)
    last_out = datetime(2026, 2, 23, 18, 0, tzinfo=tz)

    AttendanceLog.objects.create(
        employee=employee,
        device_id="D1",
        event_type=AttendanceLog.EventType.IN,
        event_time=first_in,
        confidence_score=0.99,
    )
    AttendanceLog.objects.create(
        employee=employee,
        device_id="D1",
        event_type=AttendanceLog.EventType.OUT,
        event_time=last_out,
        confidence_score=0.99,
    )

    logs = AttendanceLog.objects.all()
    result = AttendanceCalculationService.calculate_daily_attendance(logs)

    summary = result[employee.id][day]
    # 8.5 hours from 09:30 to 18:00
    assert pytest.approx(summary["worked_hours"], rel=1e-3) == 8.5
    assert summary["lateness_minutes"] == 30
    assert summary["overtime_minutes"] == 0


@pytest.mark.django_db
def test_missing_out_event():
    tz = timezone.get_current_timezone()
    employee = Employee.objects.create(
        external_id="E3",
        first_name="Forgot",
        last_name="To Exit",
        department="IT",
        is_active=True,
    )

    day = datetime(2026, 2, 23, tzinfo=tz).date()
    first_in = datetime(2026, 2, 23, 9, 0, tzinfo=tz)

    AttendanceLog.objects.create(
        employee=employee,
        device_id="D1",
        event_type=AttendanceLog.EventType.IN,
        event_time=first_in,
        confidence_score=0.99,
    )

    logs = AttendanceLog.objects.all()
    result = AttendanceCalculationService.calculate_daily_attendance(logs)

    summary = result[employee.id][day]
    # No OUT event -> 0 worked hours, no overtime
    assert pytest.approx(summary["worked_hours"], rel=1e-3) == 0.0
    assert summary["lateness_minutes"] == 0
    assert summary["overtime_minutes"] == 0


@pytest.mark.django_db
def test_overtime_case():
    tz = timezone.get_current_timezone()
    employee = Employee.objects.create(
        external_id="E4",
        first_name="Overtime",
        last_name="Worker",
        department="IT",
        is_active=True,
    )

    day = datetime(2026, 2, 23, tzinfo=tz).date()
    first_in = datetime(2026, 2, 23, 9, 0, tzinfo=tz)
    last_out = datetime(2026, 2, 23, 20, 0, tzinfo=tz)  # 2 hours overtime after 18:00

    AttendanceLog.objects.create(
        employee=employee,
        device_id="D1",
        event_type=AttendanceLog.EventType.IN,
        event_time=first_in,
        confidence_score=0.99,
    )
    AttendanceLog.objects.create(
        employee=employee,
        device_id="D1",
        event_type=AttendanceLog.EventType.OUT,
        event_time=last_out,
        confidence_score=0.99,
    )

    logs = AttendanceLog.objects.all()
    result = AttendanceCalculationService.calculate_daily_attendance(logs)

    summary = result[employee.id][day]
    assert pytest.approx(summary["worked_hours"], rel=1e-3) == 11.0
    assert summary["lateness_minutes"] == 0
    # 120 minutes overtime from 18:00 to 20:00
    assert summary["overtime_minutes"] == 120


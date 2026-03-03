from datetime import datetime, time

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from employees.models import Department, Employee
from .models import AttendanceLog, DailyAttendanceSummary

User = get_user_model()


def _api_client_with_token():
    """Client authenticated with a token (for protected API)."""
    user = User.objects.create_user(username="apiuser", password="testpass")
    token, _ = Token.objects.get_or_create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


def _make_access_event_payload(
    external_id: str = "EXT-1",
    full_name: str = "Webhook User",
    attendance_status: str = "checkIn",
    device_ip: str = "192.168.1.10",
    event_time: str | None = None,
):
    """
    Helper to build JSON body similar to real Hikvision AccessControllerEvent.
    """
    if event_time is None:
        # use fixed time in UTC for deterministic tests
        event_time = "2026-02-23T09:00:00+00:00"

    return {
        "eventType": "AccessControllerEvent",
        "ipAddress": device_ip,
        "dateTime": event_time,
        "AccessControllerEvent": {
            "employeeNoString": external_id,
            "name": full_name,
            "attendanceStatus": attendance_status,
        },
    }


@pytest.mark.django_db
def test_ivms_access_controller_event_creates_log_for_existing_employee():
    """
    If employee with given external_id already exists, webhook must create
    AttendanceLog and DailyAttendanceSummary, but must NOT auto-create employees.
    """
    client = APIClient()
    url = reverse("ivms-events")

    # Employee must be pre-created (no auto-creation from webhook)
    employee = Employee.objects.create(
        external_id="EXT-1",
        first_name="Existing",
        last_name="Employee",
        is_active=True,
    )

    payload = _make_access_event_payload(
        external_id="EXT-1",
        full_name="Webhook User",
        attendance_status="checkIn",
        event_time="2026-02-23T09:00:00+00:00",
    )

    response = client.post(url, data=payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    data = response.data
    assert "id" in data
    assert data["event_type"] == "IN"
    assert data["employee_id"] == employee.id

    # Employee name must not be overwritten from webhook payload
    employee.refresh_from_db()
    assert employee.first_name == "Existing"
    assert employee.last_name == "Employee"

    log = AttendanceLog.objects.get(employee=employee)
    assert log.device_id == payload["ipAddress"]

    # DailyAttendanceSummary should be created for that date
    local_day = timezone.localdate(timezone.make_aware(datetime(2026, 2, 23)))
    assert DailyAttendanceSummary.objects.filter(
        employee=employee, date=local_day
    ).exists()


@pytest.mark.django_db
def test_ivms_duplicate_event_is_ignored_with_200():
    client = APIClient()
    url = reverse("ivms-events")

    payload = _make_access_event_payload(
        external_id="EXT-2",
        full_name="Duplicate User",
        attendance_status="checkIn",
        event_time="2026-02-23T09:00:00+00:00",
    )

    first_response = client.post(url, data=payload, format="json")
    assert first_response.status_code == status.HTTP_201_CREATED
    assert AttendanceLog.objects.count() == 1

    second_response = client.post(url, data=payload, format="json")
    assert second_response.status_code == status.HTTP_200_OK
    assert second_response.data.get("status") == "ignored"
    assert second_response.data.get("reason") == "duplicate"
    assert AttendanceLog.objects.count() == 1


@pytest.mark.django_db
def test_ivms_event_with_unknown_employee_is_ignored():
    """
    If there is no employee with given external_id, webhook must ignore the event
    (no log created, status 200 with status='ignored').
    """
    client = APIClient()
    url = reverse("ivms-events")

    payload = _make_access_event_payload(
        external_id="NON-EXISTENT",
        full_name="Unknown User",
        attendance_status="checkIn",
        event_time="2026-02-23T09:00:00+00:00",
    )

    response = client.post(url, data=payload, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert response.data.get("status") == "ignored"
    # No logs should be created
    assert AttendanceLog.objects.count() == 0


@pytest.mark.django_db
def test_ivms_heartbeat_returns_ok():
    client = APIClient()
    url = reverse("ivms-events")

    payload = {"eventType": "heartBeat"}

    response = client.post(url, data=payload, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"status": "ok"}


@pytest.mark.django_db
def test_ivms_unknown_event_is_ignored():
    client = APIClient()
    url = reverse("ivms-events")

    payload = {"eventType": "SomeOtherEvent"}

    response = client.post(url, data=payload, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"status": "ignored"}


@pytest.mark.django_db
def test_dashboard_requires_auth():
    client = APIClient()
    url = reverse("dashboard-summary")
    response = client.get(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_dashboard_summary_counts_and_recent_activity():
    client = _api_client_with_token()
    today = timezone.localdate()
    tz = timezone.get_current_timezone()

    employee = Employee.objects.create(
        external_id="E-DASH",
        first_name="Dash",
        last_name="User",
        is_active=True,
    )

    first_entry = timezone.make_aware(
        datetime.combine(today, time(9, 5)), tz
    )  # немного позже графика
    AttendanceLog.objects.create(
        employee=employee,
        device_id="door-1",
        event_type=AttendanceLog.EventType.IN,
        event_time=first_entry,
        confidence_score=0.99,
    )

    # Создаём summary напрямую, чтобы не зависеть от сервиса
    DailyAttendanceSummary.objects.create(
        employee=employee,
        date=today,
        first_entry=first_entry,
        last_exit=None,
        worked_hours=0.0,
        lateness_minutes=5,
        overtime_minutes=0,
    )

    url = reverse("dashboard-summary")
    response = client.get(url)

    assert response.status_code == status.HTTP_200_OK
    data = response.data

    summary = data["summary"]
    assert summary["total"] == 1
    assert summary["present"] == 1
    assert summary["late"] == 1
    assert summary["absent"] == 0
    assert "devices_online" in summary

    recent = data["recent_activity"]
    assert len(recent) >= 1
    first_row = recent[0]
    assert first_row["employee_id"] == employee.id
    assert first_row["event_type"] == "IN"
    assert first_row["event_type_display"] == "Вход"
    assert "time_display" in first_row


@pytest.mark.django_db
def test_daily_attendance_summaries_filter_by_date_and_department_ref():
    client = _api_client_with_token()
    today = timezone.localdate()
    tz = timezone.get_current_timezone()

    dep = Department.objects.create(name="IT Department", code="it-dep")

    employee = Employee.objects.create(
        external_id="E-ATT",
        first_name="Att",
        last_name="User",
        department_ref=dep,
        is_active=True,
    )

    first_entry = timezone.make_aware(
        datetime.combine(today, time(9, 0)), tz
    )
    DailyAttendanceSummary.objects.create(
        employee=employee,
        date=today,
        first_entry=first_entry,
        last_exit=None,
        worked_hours=8.0,
        lateness_minutes=0,
        overtime_minutes=0,
    )

    url = reverse("daily-attendance-summary-list")
    response = client.get(
        url,
        {
            "date": today.isoformat(),
            "department_ref_id": dep.id,
        },
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.data
    assert data["count"] == 1
    result = data["results"][0]
    assert result["employee"] == employee.id
    assert result["employee_department"] == dep.name
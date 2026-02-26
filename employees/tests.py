from datetime import datetime

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from attendance.models import AttendanceLog
from .models import Department, Employee, Position


@pytest.mark.django_db
def test_employee_list_returns_last_entry_and_status_and_department():
    client = APIClient()
    url = reverse("employee-list")

    tz = timezone.get_current_timezone()

    dep = Department.objects.create(name="IT Department", code="it-dep")
    pos = Position.objects.create(
        name="Engineer",
        code="eng",
        department=dep,
    )

    employee = Employee.objects.create(
        external_id="EMP-1",
        first_name="Ivan",
        last_name="Ivanov",
        department_ref=dep,
        position_ref=pos,
        phone_number="+99890...",
        is_active=True,
    )

    # два IN-события, должно взять последнее
    first_in = timezone.make_aware(datetime(2026, 2, 23, 9, 0), tz)
    last_in = timezone.make_aware(datetime(2026, 2, 23, 10, 0), tz)

    AttendanceLog.objects.create(
        employee=employee,
        device_id="door-1",
        event_type=AttendanceLog.EventType.IN,
        event_time=first_in,
        confidence_score=0.9,
    )
    AttendanceLog.objects.create(
        employee=employee,
        device_id="door-1",
        event_type=AttendanceLog.EventType.IN,
        event_time=last_in,
        confidence_score=0.95,
    )

    response = client.get(url)
    assert response.status_code == status.HTTP_200_OK

    data = response.data
    assert data["count"] == 1
    result = data["results"][0]

    assert result["id"] == employee.id
    assert result["external_id"] == "EMP-1"
    assert result["full_name"] == "Ivanov Ivan"
    assert result["department"] == dep.name
    assert result["position"] == pos.name
    assert result["phone_number"] == "+99890..."
    assert result["is_active"] is True
    assert result["status"] == "Активен"

    # last_entry должен совпадать с последним IN-событием
    assert result["last_entry"] is not None
    last_entry_dt = datetime.fromisoformat(result["last_entry"].replace("Z", "+00:00"))
    assert last_entry_dt == last_in.astimezone(last_entry_dt.tzinfo)


@pytest.mark.django_db
def test_employee_list_filters_by_department_and_active_and_search():
    client = APIClient()
    url = reverse("employee-list")

    dep1 = Department.objects.create(name="IT", code="it")
    dep2 = Department.objects.create(name="HR", code="hr")

    emp_it_active = Employee.objects.create(
        external_id="IT-ACTIVE",
        first_name="Alice",
        last_name="Smith",
        department_ref=dep1,
        is_active=True,
    )
    emp_it_inactive = Employee.objects.create(
        external_id="IT-INACTIVE",
        first_name="Bob",
        last_name="Brown",
        department_ref=dep1,
        is_active=False,
    )
    Employee.objects.create(
        external_id="HR-ACTIVE",
        first_name="Charlie",
        last_name="Johnson",
        department_ref=dep2,
        is_active=True,
    )

    # фильтр по department_ref_id
    resp_dep = client.get(url, {"department_ref_id": dep1.id})
    assert resp_dep.status_code == status.HTTP_200_OK
    ids_dep = {item["id"] for item in resp_dep.data["results"]}
    assert emp_it_active.id in ids_dep
    assert emp_it_inactive.id in ids_dep
    # сотрудник из другого отдела не должен попасть
    assert all(item["department"] == dep1.name for item in resp_dep.data["results"])

    # фильтр по is_active=true
    resp_active = client.get(url, {"is_active": "true"})
    assert resp_active.status_code == status.HTTP_200_OK
    assert all(item["is_active"] is True for item in resp_active.data["results"])

    # фильтр по is_active=false
    resp_inactive = client.get(url, {"is_active": "false"})
    assert resp_inactive.status_code == status.HTTP_200_OK
    assert all(item["is_active"] is False for item in resp_inactive.data["results"])

    # поиск по части имени / external_id
    resp_search = client.get(url, {"search": "IT-ACT"})
    assert resp_search.status_code == status.HTTP_200_OK
    results = resp_search.data["results"]
    assert len(results) == 1
    assert results[0]["external_id"] == "IT-ACTIVE"


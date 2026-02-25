from datetime import datetime

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from employees.models import Employee
from .models import AttendanceLog


@pytest.mark.django_db
def test_webhook_creates_employee_and_log():
    client = APIClient()
    url = reverse("ivms-events")

    payload = {
        "external_id": "EXT-1",
        "full_name": "Webhook User",
        "device_id": "D1",
        "event_type": "IN",
        "event_time": "2026-02-23T09:00:00Z",
        "confidence_score": 0.95,
    }

    response = client.post(url, data=payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED

    employee = Employee.objects.get(external_id="EXT-1")
    assert employee.first_name == "User"
    assert employee.last_name == "Webhook"

    log = AttendanceLog.objects.get(employee=employee)
    assert log.device_id == "D1"
    assert log.event_type == "IN"
    assert pytest.approx(float(log.confidence_score), rel=1e-6) == 0.95


@pytest.mark.django_db
def test_webhook_duplicate_event_rejected():
    client = APIClient()
    url = reverse("ivms-events")

    payload = {
        "external_id": "EXT-2",
        "full_name": "Duplicate User",
        "device_id": "D1",
        "event_type": "IN",
        "event_time": "2026-02-23T09:00:00Z",
        "confidence_score": 0.9,
    }

    # First call creates employee and log
    first_response = client.post(url, data=payload, format="json")
    assert first_response.status_code == status.HTTP_201_CREATED
    assert AttendanceLog.objects.count() == 1

    # Second identical call should be treated as duplicate
    second_response = client.post(url, data=payload, format="json")
    assert second_response.status_code == status.HTTP_400_BAD_REQUEST
    assert "non_field_errors" in second_response.data
    assert AttendanceLog.objects.count() == 1


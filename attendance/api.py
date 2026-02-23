from __future__ import annotations

from typing import Any, Dict

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from employees.models import Employee
from .models import AttendanceLog, DailyAttendanceSummary


class IvmsEventSerializer(serializers.Serializer):
    external_id = serializers.CharField(max_length=64)
    full_name = serializers.CharField(max_length=255)
    device_id = serializers.CharField(max_length=64)
    event_type = serializers.ChoiceField(
        choices=[AttendanceLog.EventType.IN, AttendanceLog.EventType.OUT]
    )
    event_time = serializers.DateTimeField()
    confidence_score = serializers.FloatField()

    def validate_event_time(self, value):
        # Normalize to current timezone
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.get_current_timezone())
        return value

    @transaction.atomic
    def create(self, validated_data: Dict[str, Any]) -> AttendanceLog:
        external_id = validated_data.pop("external_id")
        full_name = validated_data.pop("full_name")

        employee, _ = Employee.objects.update_or_create(
            external_id=external_id,
            defaults={"full_name": full_name, "is_active": True},
        )

        # Prevent duplicates: same employee, device, event_type and exact event_time
        if AttendanceLog.objects.filter(
            employee=employee,
            device_id=validated_data["device_id"],
            event_type=validated_data["event_type"],
            event_time=validated_data["event_time"],
        ).exists():
            raise serializers.ValidationError(
                {"non_field_errors": ["Duplicate attendance event detected."]}
            )

        return AttendanceLog.objects.create(employee=employee, **validated_data)


class IvmsEventAPIView(APIView):
    """
    API endpoint to receive raw events from iVMS.
    """

    def post(self, request, *args, **kwargs) -> Response:
        serializer = IvmsEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        log = serializer.save()

        return Response(
            {
                "id": log.id,
                "employee_id": log.employee_id,
                "event_type": log.event_type,
                "event_time": log.event_time,
            },
            status=status.HTTP_201_CREATED,
        )


class DailyAttendanceSummarySerializer(serializers.ModelSerializer):
    employee_external_id = serializers.CharField(
        source="employee.external_id", read_only=True
    )
    employee_full_name = serializers.CharField(
        source="employee.full_name", read_only=True
    )

    class Meta:
        model = DailyAttendanceSummary
        fields = [
            "id",
            "employee",
            "employee_external_id",
            "employee_full_name",
            "date",
            "first_entry",
            "last_exit",
            "worked_hours",
            "lateness_minutes",
            "overtime_minutes",
        ]
        read_only_fields = [
            "id",
            "first_entry",
            "last_exit",
            "worked_hours",
            "lateness_minutes",
            "overtime_minutes",
        ]


class DailyAttendanceSummaryPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class DailyAttendanceSummaryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only API for daily attendance summaries with:
    - filtering by employee (employee_id)
    - filtering by date range (date_from, date_to; ISO dates)
    - ordering by allowed fields via `ordering` query param
    - pagination
    """

    serializer_class = DailyAttendanceSummarySerializer
    pagination_class = DailyAttendanceSummaryPagination

    ordering_fields = ("date", "worked_hours", "lateness_minutes", "overtime_minutes")
    default_ordering = ("-date", "employee_id")

    def get_queryset(self):
        qs = DailyAttendanceSummary.objects.select_related("employee")

        params = self.request.query_params

        employee_id = params.get("employee_id")
        if employee_id:
            qs = qs.filter(employee_id=employee_id)

        date_from = params.get("date_from")
        if date_from:
            qs = qs.filter(date__gte=date_from)

        date_to = params.get("date_to")
        if date_to:
            qs = qs.filter(date__lte=date_to)

        ordering_param = params.get("ordering")
        if ordering_param:
            requested = []
            for field in ordering_param.split(","):
                field = field.strip()
                if not field:
                    continue
                raw = field.lstrip("-")
                if raw in self.ordering_fields:
                    requested.append(field)
            if requested:
                qs = qs.order_by(*requested)
                return qs

        return qs.order_by(*self.default_ordering)



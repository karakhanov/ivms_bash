from __future__ import annotations

from typing import Any, Dict, List
import json

from email.parser import BytesParser
from email.policy import default as email_default_policy
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from employees.models import Employee
from .models import AttendanceLog, DailyAttendanceSummary
from .services import AttendanceCalculationService


def _normalize_hikvision_event(json_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a single Hikvision JSON event (AccessControllerEvent)
    to the schema expected by IvmsEventSerializer.
    """
    access_event = json_payload.get("AccessControllerEvent") or {}

    external_id = (
        access_event.get("employeeNoString")
        or access_event.get("employeeNo")
        or access_event.get("cardNo")
        or access_event.get("verifyNo")
        or access_event.get("serialNo")
    )
    if external_id is None:
        external_id = str(access_event.get("serialNo", "unknown"))

    device_id = json_payload.get("ipAddress") or access_event.get("deviceName") or "unknown"
    event_time = json_payload.get("dateTime")

    attendance_status = access_event.get("attendanceStatus")
    if attendance_status in {"checkIn", "onDuty", "signIn"}:
        event_type = AttendanceLog.EventType.IN
    elif attendance_status in {"checkOut", "offDuty", "signOut"}:
        event_type = AttendanceLog.EventType.OUT
    else:
        event_type = AttendanceLog.EventType.IN

    full_name = access_event.get("name", "") or ""

    return {
        "external_id": str(external_id),
        "full_name": full_name,
        "device_id": device_id,
        "event_type": event_type,
        "event_time": event_time,
        "confidence_score": 1.0,
    }


def parse_hikvision_multipart(body: bytes, content_type: str) -> Dict[str, Any]:
    """
    Parse multipart payload from Hikvision terminal and normalize it
    to the schema expected by IvmsEventSerializer.
    """
    header = f"Content-Type: {content_type}\r\n\r\n".encode("utf-8")
    message = BytesParser(policy=email_default_policy).parsebytes(header + body)

    json_payload: Dict[str, Any] | None = None

    for part in message.iter_parts():
        if part.get_content_type() == "application/json":
            json_payload = json.loads(part.get_content())
            break

    if not json_payload:
        raise ValueError("JSON part not found in multipart payload.")

    return _normalize_hikvision_event(json_payload)


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

    def _update_daily_summary(self, employee: Employee, log: AttendanceLog) -> None:
        """
        Recalculate and upsert DailyAttendanceSummary for the log's day.
        """
        local_dt = timezone.localtime(log.event_time)
        day = local_dt.date()

        day_logs = AttendanceLog.objects.filter(
            employee=employee, event_time__date=day
        ).order_by("event_time")

        summaries = AttendanceCalculationService.calculate_daily_attendance(day_logs)
        employee_data = summaries.get(employee.id, {})
        summary_data = employee_data.get(day)

        if not summary_data:
            return

        DailyAttendanceSummary.objects.update_or_create(
            employee=employee,
            date=day,
            defaults={
                "first_entry": summary_data["first_in"],
                "last_exit": summary_data["last_out"],
                "worked_hours": summary_data["worked_hours"],
                "lateness_minutes": summary_data["lateness_minutes"],
                "overtime_minutes": summary_data["overtime_minutes"],
            },
        )

    @transaction.atomic
    def create(self, validated_data: Dict[str, Any]) -> AttendanceLog:
        external_id = validated_data.pop("external_id")
        full_name = validated_data.pop("full_name")

        # Roughly split full name into last / first / middle
        name_parts = full_name.split()
        first_name = ""
        last_name = ""
        middle_name = ""
        if len(name_parts) == 1:
            first_name = name_parts[0]
        elif len(name_parts) >= 2:
            last_name = name_parts[0]
            first_name = name_parts[1]
            if len(name_parts) > 2:
                middle_name = " ".join(name_parts[2:])

        employee, _ = Employee.objects.update_or_create(
            external_id=external_id,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "middle_name": middle_name,
                "is_active": True,
            },
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

        log = AttendanceLog.objects.create(employee=employee, **validated_data)
        self._update_daily_summary(employee, log)
        return log


class IvmsEventAPIView(APIView):
    """
    API endpoint to receive raw events from iVMS.
    No auth: terminals cannot send Token; protect by firewall / webhook secret if needed.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs) -> Response:
        content_type = request.META.get("CONTENT_TYPE", "")
        # print("IVMS RAW BODY:", request.body[:500])
        if content_type.startswith("multipart/"):
            try:
                payload = parse_hikvision_multipart(request.body, content_type)
            except ValueError as exc:
                return Response(
                    {"status": "ignored", "reason": str(exc)},
                    status=status.HTTP_200_OK,
                )
            serializer = IvmsEventSerializer(data=payload)
        else:
            try:
                raw_body = request.body.decode("utf-8") if request.body else ""
                raw_json = json.loads(raw_body or "{}")
            except json.JSONDecodeError:
                return Response(
                    {"status": "ignored", "reason": "invalid json"},
                    status=status.HTTP_200_OK,
                )

            event_type = raw_json.get("eventType")

            if event_type == "heartBeat":
                return Response({"status": "ok"}, status=status.HTTP_200_OK)

            if event_type == "AccessControllerEvent":
                payload = _normalize_hikvision_event(raw_json)
                serializer = IvmsEventSerializer(data=payload)
            else:
                return Response({"status": "ignored"}, status=status.HTTP_200_OK)

        if not serializer.is_valid():
            return Response(
                {"status": "ignored", "errors": serializer.errors},
                status=status.HTTP_200_OK,
            )

        try:
            log = serializer.save()
        except serializers.ValidationError:
            return Response(
                {"status": "ignored", "reason": "duplicate"},
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "id": log.id,
                "employee_id": log.employee_id,
                "event_type": log.event_type,
                "event_time": log.event_time,
            },
            status=status.HTTP_201_CREATED,
        )


class DashboardSummaryAPIView(APIView):
    """
    Lightweight aggregate endpoint for the main dashboard.
    """

    def get(self, request, *args, **kwargs) -> Response:
        today = timezone.localdate()

        employees_qs = Employee.objects.filter(is_active=True)
        total_employees = employees_qs.count()

        today_summaries = DailyAttendanceSummary.objects.filter(
            date=today
        ).select_related("employee")

        present_count = today_summaries.count()
        late_count = today_summaries.filter(lateness_minutes__gt=0).count()

        # Placeholder: no vacation model yet
        on_leave_count = 0

        absent_count = max(total_employees - present_count - on_leave_count, 0)

        # Recent activity (today's logs)
        logs: List[AttendanceLog] = list(
            AttendanceLog.objects.filter(event_time__date=today)
            .select_related("employee")
            .order_by("-event_time")[:20]
        )

        recent_activity = []
        work_start = AttendanceCalculationService.WORK_START

        for log in logs:
            local_dt = timezone.localtime(log.event_time)
            scheduled_start = timezone.make_aware(
                timezone.datetime.combine(today, work_start),
                timezone.get_current_timezone(),
            )
            is_late = log.event_type == AttendanceLog.EventType.IN and local_dt > scheduled_start

            employee = log.employee
            full_name = " ".join(
                p
                for p in [
                    getattr(employee, "last_name", ""),
                    getattr(employee, "first_name", ""),
                    getattr(employee, "middle_name", ""),
                ]
                if p
            )

            event_type_display = "Выход" if log.event_type == AttendanceLog.EventType.OUT else "Вход"
            status_display = "Завершено" if log.event_type == AttendanceLog.EventType.OUT else ("Опоздал" if is_late else "Вовремя")

            photo_url = None
            photo = getattr(employee, "photo", None)
            if photo:
                try:
                    photo_url = photo.url
                except ValueError:
                    photo_url = None

            recent_activity.append(
                {
                    "employee_id": employee.id,
                    "employee_external_id": employee.external_id,
                    "employee_full_name": full_name,
                    "employee_photo_url": photo_url,
                    "device_id": log.device_id,
                    "event_type": log.event_type,
                    "event_type_display": event_type_display,
                    "event_time": local_dt.isoformat(),
                    "time_display": local_dt.strftime("%H:%M"),
                    "status": status_display,
                }
            )

        data = {
            "summary": {
                "total": total_employees,
                "present": present_count,
                "absent": absent_count,
                "late": late_count,
                "on_leave": on_leave_count,
                "devices_online": {"online": 0, "total": 0},
            },
            "recent_activity": recent_activity,
        }

        return Response(data, status=status.HTTP_200_OK)

class DailyAttendanceSummarySerializer(serializers.ModelSerializer):
    employee_external_id = serializers.CharField(
        source="employee.external_id", read_only=True
    )
    employee_full_name = serializers.SerializerMethodField(read_only=True)
    employee_department = serializers.SerializerMethodField(read_only=True)
    employee_position = serializers.SerializerMethodField(read_only=True)
    employee_photo_url = serializers.SerializerMethodField(read_only=True)
    status = serializers.SerializerMethodField(read_only=True)

    def get_employee_department(self, obj: DailyAttendanceSummary) -> str:
        emp = obj.employee
        if getattr(emp, "department_ref", None):
            return emp.department_ref.name or ""
        return getattr(emp, "department", "") or ""

    def get_employee_position(self, obj: DailyAttendanceSummary) -> str:
        emp = obj.employee
        if getattr(emp, "position_ref", None):
            return emp.position_ref.name or ""
        return getattr(emp, "position", "") or ""

    def get_employee_photo_url(self, obj: DailyAttendanceSummary) -> str | None:
        emp = obj.employee
        photo = getattr(emp, "photo", None)
        if photo:
            try:
                return photo.url
            except ValueError:
                return None
        return None

    def get_employee_full_name(self, obj: DailyAttendanceSummary) -> str:
        parts = [
            getattr(obj.employee, "last_name", ""),
            getattr(obj.employee, "first_name", ""),
            getattr(obj.employee, "middle_name", ""),
        ]
        return " ".join(p for p in parts if p)

    def get_status(self, obj: DailyAttendanceSummary) -> str:
        """
        Human readable daily status for the employee.
        """
        today = timezone.localdate()

        if not obj.first_entry:
            return "Отсутствует"

        if obj.date == today:
            now = timezone.now()
            if not obj.last_exit or obj.last_exit > now:
                return "Присутствует"

        if obj.lateness_minutes > 0:
            return "Опоздал"

        return "Присутствовал"

    class Meta:
        model = DailyAttendanceSummary
        fields = [
            "id",
            "employee",
            "employee_external_id",
            "employee_full_name",
            "employee_department",
            "employee_position",
            "employee_photo_url",
            "date",
            "first_entry",
            "last_exit",
            "worked_hours",
            "lateness_minutes",
            "overtime_minutes",
            "status",
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
        qs = DailyAttendanceSummary.objects.select_related(
            "employee", "employee__department_ref", "employee__position_ref"
        )

        params = self.request.query_params

        date = params.get("date")
        if date:
            qs = qs.filter(date=date)
        else:
            date_from = params.get("date_from")
            if date_from:
                qs = qs.filter(date__gte=date_from)
            date_to = params.get("date_to")
            if date_to:
                qs = qs.filter(date__lte=date_to)

        department = params.get("department")
        if department:
            qs = qs.filter(employee__department=department)

        department_ref_id = params.get("department_ref_id")
        if department_ref_id:
            qs = qs.filter(employee__department_ref_id=department_ref_id)

        employee_id = params.get("employee_id")
        if employee_id:
            qs = qs.filter(employee_id=employee_id)

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



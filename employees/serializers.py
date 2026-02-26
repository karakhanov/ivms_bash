from datetime import date

from django.utils import timezone
from rest_framework import serializers

from attendance.models import DailyAttendanceSummary
from attendance.api import DailyAttendanceSummarySerializer
from .models import Employee


class EmployeeListSerializer(serializers.ModelSerializer):
    """For list API: id, name, department, position, contact, photo, last_entry, status."""

    full_name = serializers.SerializerMethodField(read_only=True)
    department = serializers.SerializerMethodField(read_only=True)
    position = serializers.SerializerMethodField(read_only=True)
    photo_url = serializers.SerializerMethodField(read_only=True)
    last_entry = serializers.DateTimeField(read_only=True, allow_null=True)
    status = serializers.SerializerMethodField(read_only=True)

    def get_full_name(self, obj: Employee) -> str:
        parts = [
            getattr(obj, "last_name", ""),
            getattr(obj, "first_name", ""),
            getattr(obj, "middle_name", ""),
        ]
        return " ".join(p for p in parts if p).strip() or str(obj)

    def get_department(self, obj: Employee) -> str:
        if getattr(obj, "department_ref", None):
            return obj.department_ref.name or ""
        return getattr(obj, "department", "") or ""

    def get_position(self, obj: Employee) -> str:
        if getattr(obj, "position_ref", None):
            return obj.position_ref.name or ""
        return getattr(obj, "position", "") or ""

    def get_photo_url(self, obj: Employee) -> str | None:
        photo = getattr(obj, "photo", None)
        if photo:
            try:
                return photo.url
            except ValueError:
                return None
        return None

    def get_status(self, obj: Employee) -> str:
        return "Активен" if obj.is_active else "Неактивен"

    class Meta:
        model = Employee
        fields = [
            "id",
            "external_id",
            "first_name",
            "last_name",
            "middle_name",
            "full_name",
            "department",
            "position",
            "phone_number",
            "photo_url",
            "last_entry",
            "is_active",
            "status",
        ]
        read_only_fields = fields


class EmployeeDetailSerializer(EmployeeListSerializer):
    """
    Detail view for employee page: base info + attendance history and current-month stats.
    """

    month_stats = serializers.SerializerMethodField(read_only=True)
    attendance_history = serializers.SerializerMethodField(read_only=True)

    def _get_month_bounds(self, month_str: str | None):
        today = timezone.localdate()
        if month_str:
            try:
                year, month = map(int, month_str.split("-"))
                start = date(year, month, 1)
            except Exception:
                start = date(today.year, today.month, 1)
        else:
            start = date(today.year, today.month, 1)
        if start.month == 12:
            end = date(start.year + 1, 1, 1)
        else:
            end = date(start.year, start.month + 1, 1)
        # end is exclusive
        return start, end

    def get_month_stats(self, obj: Employee) -> dict:
        request = self.context.get("request")
        month_param = request.query_params.get("month") if request else None
        start, end_exclusive = self._get_month_bounds(month_param)

        qs = DailyAttendanceSummary.objects.filter(
            employee=obj,
            date__gte=start,
            date__lt=end_exclusive,
        )

        total_days = qs.count()
        if not total_days:
            return {
                "month": start.strftime("%Y-%m"),
                "total_days_with_records": 0,
                "present_days": 0,
                "late_days": 0,
                "overtime_days": 0,
                "total_worked_hours": 0.0,
                "attendance_percent": 0.0,
            }

        present_days = qs.exclude(first_entry__isnull=True).count()
        late_days = qs.filter(lateness_minutes__gt=0).count()
        overtime_days = qs.filter(overtime_minutes__gt=0).count()
        total_worked_hours = sum(s.worked_hours for s in qs)

        attendance_percent = round(100.0 * present_days / total_days, 1)

        return {
            "month": start.strftime("%Y-%m"),
            "total_days_with_records": total_days,
            "present_days": present_days,
            "late_days": late_days,
            "overtime_days": overtime_days,
            "total_worked_hours": total_worked_hours,
            "attendance_percent": attendance_percent,
        }

    def get_attendance_history(self, obj: Employee):
        """
        Daily attendance history for this employee for given month (or current month).
        """
        request = self.context.get("request")
        month_param = request.query_params.get("month") if request else None
        start, end_exclusive = self._get_month_bounds(month_param)

        qs = DailyAttendanceSummary.objects.filter(
            employee=obj,
            date__gte=start,
            date__lt=end_exclusive,
        ).order_by("-date")

        serializer = DailyAttendanceSummarySerializer(
            qs, many=True, context=self.context
        )
        return serializer.data

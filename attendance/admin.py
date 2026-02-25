from django.contrib import admin

from .models import AttendanceLog, DailyAttendanceSummary


@admin.register(AttendanceLog)
class AttendanceLogAdmin(admin.ModelAdmin):
    list_display = ("employee", "device_id", "event_type", "event_time", "confidence_score")
    list_filter = ("event_type", "device_id", "event_time")
    search_fields = (
        "employee__external_id",
        "employee__first_name",
        "employee__last_name",
        "employee__middle_name",
        "device_id",
    )
    date_hierarchy = "event_time"


@admin.register(DailyAttendanceSummary)
class DailyAttendanceSummaryAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "date",
        "worked_hours",
        "lateness_minutes",
        "overtime_minutes",
    )
    list_filter = ("date",)
    search_fields = (
        "employee__external_id",
        "employee__first_name",
        "employee__last_name",
        "employee__middle_name",
    )

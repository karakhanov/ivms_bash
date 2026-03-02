from django.contrib import admin
from django.utils.html import format_html

from .models import AttendanceLog, DailyAttendanceSummary, Device


def _employee_photo_thumb(obj):
    """Миниатюра фото сотрудника для списка (obj — запись с полем employee)."""
    emp = getattr(obj, "employee", None)
    if not emp or not emp.photo:
        return "—"
    return format_html(
        '<img src="{}" alt="" style="max-width: 40px; max-height: 40px; object-fit: cover; border-radius: 4px;">',
        emp.photo.url,
    )


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("name", "device_id", "address", "mac_address", "direction", "is_active", "last_seen")
    list_editable = ("address",)  # быстрая правка реального IP в списке
    list_filter = ("direction", "is_active")
    search_fields = ("name", "device_id", "address", "mac_address")
    readonly_fields = ("last_seen", "created_at", "updated_at")


@admin.register(AttendanceLog)
class AttendanceLogAdmin(admin.ModelAdmin):
    list_display = ("photo_thumb", "employee", "device_id", "event_type", "event_time", "confidence_score")

    @admin.display(description="Фото")
    def photo_thumb(self, obj):
        return _employee_photo_thumb(obj)

    list_select_related = ("employee",)
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
        "photo_thumb",
        "employee",
        "date",
        "worked_hours",
        "lateness_minutes",
        "overtime_minutes",
    )

    @admin.display(description="Фото")
    def photo_thumb(self, obj):
        return _employee_photo_thumb(obj)

    list_select_related = ("employee",)
    list_filter = ("date",)
    search_fields = (
        "employee__external_id",
        "employee__first_name",
        "employee__last_name",
        "employee__middle_name",
    )

from django.contrib import admin, messages
from django.utils.html import format_html

from hikvision.client import sync_employee_to_devices

from .models import (
    Department,
    Position,
    WorkSchedule,
    EmployeeStatus,
    EmployeeRole,
    Employee,
)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "photo_thumb",
        "external_id",
        "first_name",
        "last_name",
        "department_ref",
        "position_ref",
        "work_schedule_ref",
        "is_active",
    )

    @admin.display(description="Фото")
    def photo_thumb(self, obj):
        if not obj.photo:
            return "—"
        url = obj.photo.url
        return format_html(
            '<img src="{}" alt="" style="max-width: 48px; max-height: 48px; object-fit: cover; border-radius: 4px;">',
            url,
        )
    list_filter = (
        "department_ref",
        "position_ref",
        "work_schedule_ref",
        "is_active",
        "gender",
    )
    search_fields = ("external_id", "first_name", "last_name")
    actions = ["sync_selected_to_devices"]

    # старые текстовые поля не показываем в форме
    exclude = ("department", "position", "type_of_work")

    @admin.action(description="Отправить на терминал(ы)")
    def sync_selected_to_devices(self, request, queryset):
        total = 0
        errors = []
        for employee in queryset:
            results = sync_employee_to_devices(employee)
            if not results:
                errors.append(f"{employee}: устройств не настроено (HIKVISION_DEVICE_URL / HIKVISION_DEVICES)")
                continue
            for r in results:
                if r["user_ok"]:
                    total += 1
                else:
                    errors.append(f"{employee} → {r['base_url']}: {r['user_message']}")
        if total:
            self.message_user(
                request,
                f"Отправлено на устройств: {total}. Фото загружено там, где было у сотрудника.",
                messages.SUCCESS,
            )
        if errors:
            self.message_user(
                request,
                "Ошибки: " + "; ".join(errors[:5]) + (" …" if len(errors) > 5 else ""),
                messages.WARNING,
            )
        if not total and not errors:
            self.message_user(
                request,
                "Устройства не настроены. Задайте HIKVISION_DEVICE_URL и HIKVISION_USERNAME (или HIKVISION_DEVICES) в окружении.",
                messages.WARNING,
            )

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "department", "is_active")
    list_filter = ("department", "is_active")
    search_fields = ("name", "code")


@admin.register(WorkSchedule)
class WorkScheduleAdmin(admin.ModelAdmin):
    list_display = ("name", "start_time", "end_time", "is_default", "is_active")
    list_filter = ("is_default", "is_active")
    search_fields = ("name",)


@admin.register(EmployeeStatus)
class EmployeeStatusAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")


@admin.register(EmployeeRole)
class EmployeeRoleAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")

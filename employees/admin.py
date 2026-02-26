from django.contrib import admin

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
        "external_id",
        "first_name",
        "last_name",
        "department_ref",
        "position_ref",
        "work_schedule_ref",
        "is_active",
    )
    list_filter = (
        "department_ref",
        "position_ref",
        "work_schedule_ref",
        "is_active",
        "gender",
    )
    search_fields = ("external_id", "first_name", "last_name")

    # старые текстовые поля не показываем в форме
    exclude = ("department", "position", "type_of_work")

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

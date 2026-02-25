from django.contrib import admin

from .models import Employee


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("external_id", "first_name", "last_name", "department", "is_active")
    list_filter = ("department", "is_active")
    search_fields = ("external_id", "first_name", "department")

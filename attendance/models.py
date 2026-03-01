from django.db import models

from employees.models import Employee


class Device(models.Model):
    """
    Терминал/устройство контроля доступа (например Hikvision).
    device_id совпадает с тем, что приходит в событиях (AttendanceLog.device_id).
    """

    class Direction(models.TextChoices):
        ENTRANCE = "entrance", "Вход"
        EXIT = "exit", "Выход"
        BOTH = "both", "Вход и выход"

    name = models.CharField("Название", max_length=128)
    address = models.CharField(
        "Адрес (IP или URL)",
        max_length=255,
        blank=True,
        help_text="Реальный IP устройства. По нему устройство сопоставляется с запросом при приходе событий.",
    )
    mac_address = models.CharField("MAC-адрес", max_length=17, blank=True)
    device_id = models.CharField(
        "ID устройства в событиях",
        max_length=64,
        unique=True,
        help_text="Строка из событий (ipAddress, deviceName и т.п.)",
    )
    direction = models.CharField(
        "Направление",
        max_length=16,
        choices=Direction.choices,
        default=Direction.BOTH,
    )
    is_active = models.BooleanField("Активно", default=True)
    last_seen = models.DateTimeField("Последнее событие", null=True, blank=True)
    notes = models.TextField("Примечание", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Устройство"
        verbose_name_plural = "Устройства"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.device_id})"


class AttendanceLog(models.Model):
    class EventType(models.TextChoices):
        IN = "IN", "IN"
        OUT = "OUT", "OUT"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="attendance_logs")
    device_id = models.CharField(max_length=64)
    event_type = models.CharField(max_length=3, choices=EventType.choices)
    event_time = models.DateTimeField(db_index=True)
    confidence_score = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["employee"]),
            models.Index(fields=["event_time"]),
        ]

    def __str__(self) -> str:
        return f"{self.employee} {self.event_type} @ {self.event_time.isoformat()}"


class DailyAttendanceSummary(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="daily_summaries")
    date = models.DateField()
    first_entry = models.DateTimeField(null=True, blank=True)
    last_exit = models.DateTimeField(null=True, blank=True)
    worked_hours = models.FloatField()
    lateness_minutes = models.PositiveIntegerField()
    overtime_minutes = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "date"],
                name="unique_employee_date_daily_summary",
            )
        ]

    def __str__(self) -> str:
        return f"{self.employee} {self.date}"

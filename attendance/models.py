from django.db import models

from employees.models import Employee


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

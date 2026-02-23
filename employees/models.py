from django.db import models


class Employee(models.Model):
    external_id = models.CharField(max_length=64, unique=True)
    full_name = models.CharField(max_length=255)
    department = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["external_id"]),
            models.Index(fields=["department", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.external_id})"

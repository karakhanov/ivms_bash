from django.db import models


class Employee(models.Model):
    external_id = models.CharField(max_length=64, unique=True)
    first_name = models.CharField(max_length=128)
    last_name = models.CharField(max_length=128)
    middle_name = models.CharField(max_length=128)
    position = models.CharField(max_length=128)
    department = models.CharField(max_length=128)
    type_of_work = models.CharField(max_length=128)
    pinfl = models.CharField(max_length=128)
    phone_number = models.CharField(max_length=128)
    department = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["external_id"]),
            models.Index(fields=["department", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name} {self.middle_name} ({self.external_id})"

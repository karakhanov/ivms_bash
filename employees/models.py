from django.db import models


class Department(models.Model):
    """
    Справочник подразделений.
    """

    name = models.CharField(max_length=128, unique=True)
    code = models.CharField(max_length=32, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Position(models.Model):
    """
    Справочник должностей.
    """

    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32, unique=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="positions",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("name", "department")

    def __str__(self) -> str:
        return self.name


class WorkSchedule(models.Model):
    """
    Справочник графиков работы (смен).
    """

    name = models.CharField(max_length=128, unique=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    break_start = models.TimeField(null=True, blank=True)
    break_end = models.TimeField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class EmployeeStatus(models.Model):
    """
    Справочник статусов сотрудника (Активен, В отпуске, Уволен и т.д.).
    """

    name = models.CharField(max_length=64, unique=True)
    code = models.CharField(max_length=32, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class EmployeeRole(models.Model):
    """
    Справочник ролей (например: Сотрудник, Руководитель, Администратор).
    """

    name = models.CharField(max_length=64, unique=True)
    code = models.CharField(max_length=32, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Employee(models.Model):
    class Gender(models.TextChoices):
        MALE = "male", "Мужской"
        FEMALE = "female", "Женский"
        OTHER = "other", "Другое"

    external_id = models.CharField(max_length=64, unique=True)
    first_name = models.CharField(max_length=128)
    last_name = models.CharField(max_length=128)
    middle_name = models.CharField(max_length=128, blank=True)

    # Исторические строковые поля, которые уже есть в БД
    position = models.CharField(max_length=128, blank=True)
    department = models.CharField(max_length=128, blank=True)
    type_of_work = models.CharField(max_length=128, blank=True)

    # Новые связи на справочники (можно использовать на фронте)
    department_ref = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
    )
    position_ref = models.ForeignKey(
        Position,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
    )
    work_schedule_ref = models.ForeignKey(
        WorkSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
    )

    pinfl = models.CharField(max_length=128, blank=True)
    phone_number = models.CharField(max_length=128, blank=True)

    photo = models.ImageField(
        upload_to="employees/photos/",
        blank=True,
        null=True,
    )

    gender = models.CharField(
        max_length=16, choices=Gender.choices, blank=True, default=""
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["external_id"]),
            models.Index(fields=["department", "is_active"]),
        ]

    def __str__(self) -> str:
        parts = [self.first_name, self.last_name, self.middle_name]
        full_name = " ".join(p for p in parts if p)
        return f"{full_name} ({self.external_id})"

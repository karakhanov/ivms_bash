from __future__ import annotations

from django.conf import settings
from django.db import models


class BaseModel(models.Model):
    """
    Общие поля аудита и статуса для бизнес-моделей.

    Поля:
    - created_at: дата/время создания (автоматически заполняется)
    - updated_at: дата/время последнего обновления (автоматически обновляется)
    - created_by: пользователь, создавший запись
    - updated_by: пользователь, изменивший запись
    - state: целочисленный статус (по умолчанию 1)
    - attributes: произвольные дополнительные атрибуты (JSON)
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_%(class)ss",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_%(class)ss",
    )

    state = models.IntegerField(default=1)
    attributes = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True


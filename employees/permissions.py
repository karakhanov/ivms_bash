from __future__ import annotations

from rest_framework.permissions import BasePermission
from rest_framework.views import View
from rest_framework.request import Request


class EmployeePermission(BasePermission):
    """
    Права доступа к API сотрудников.

    - Админы / персонал (is_staff или is_superuser): полный доступ.
    - Обычные пользователи:
      - могут только создавать сотрудников (POST /employees/ -> action == "create");
      - не могут просматривать список, детали или изменять/удалять записи.
    """

    def has_permission(self, request: Request, view: View) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False

        # Админы и staff имеют полный доступ
        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            return True

        # Для обычных пользователей разрешаем только создание сотрудников
        action = getattr(view, "action", None)
        if action == "create":
            return True

        return False


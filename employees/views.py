from django.db.models import OuterRef, Q, Subquery
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from attendance.models import AttendanceLog
from hikvision.client import sync_employee_to_devices

from .models import Employee
from .permissions import EmployeePermission
from .serializers import (
    EmployeeListSerializer,
    EmployeeDetailSerializer,
    EmployeeWriteSerializer,
)


class EmployeePagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class EmployeeViewSet(viewsets.ModelViewSet):
    """
    Read-only list of employees for the frontend: id, name, department, position,
    contact, last_entry (last IN event time), status.
    Filter: department_ref_id, is_active, search (by name/external_id).
    """

    serializer_class = EmployeeListSerializer
    pagination_class = EmployeePagination
    permission_classes = [EmployeePermission]

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return EmployeeWriteSerializer
        if self.action == "retrieve":
            return EmployeeDetailSerializer
        return EmployeeListSerializer

    def get_queryset(self):
        last_in_subquery = (
            AttendanceLog.objects.filter(
                employee=OuterRef("pk"),
                event_type=AttendanceLog.EventType.IN,
            )
            .order_by("-event_time")
            .values("event_time")[:1]
        )
        qs = (
            Employee.objects.select_related("department_ref", "position_ref")
            .annotate(last_entry=Subquery(last_in_subquery))
            .order_by("last_name", "first_name")
        )

        params = self.request.query_params
        department_ref_id = params.get("department_ref_id")
        if department_ref_id:
            qs = qs.filter(department_ref_id=department_ref_id)
        is_active = params.get("is_active")
        if is_active is not None:
            if is_active in ("1", "true", "True"):
                qs = qs.filter(is_active=True)
            elif is_active in ("0", "false", "False"):
                qs = qs.filter(is_active=False)
        search = params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(middle_name__icontains=search)
                | Q(external_id__icontains=search)
            )
        return qs

    @action(detail=True, methods=["post"], url_path="sync-to-devices")
    def sync_to_devices(self, request, pk=None):
        """
        Push this employee to configured Hikvision device(s): create/update user, upload photo.
        Requires HIKVISION_DEVICE_URL + HIKVISION_USERNAME (+ HIKVISION_PASSWORD) in env,
        or HIKVISION_DEVICES JSON array.
        """
        employee = self.get_object()
        results = sync_employee_to_devices(employee)
        if not results:
            return Response(
                {"detail": "No Hikvision devices configured.", "results": []},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"results": results}, status=status.HTTP_200_OK)

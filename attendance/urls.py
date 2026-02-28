from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api import (
    DailyAttendanceSummaryViewSet,
    DeviceViewSet,
    IvmsEventAPIView,
    DashboardSummaryAPIView,
)

router = DefaultRouter()
router.register(r"devices", DeviceViewSet, basename="device")
router.register(
    r"daily-attendance-summaries",
    DailyAttendanceSummaryViewSet,
    basename="daily-attendance-summary",
)

urlpatterns = [
    path("ivms/events/", IvmsEventAPIView.as_view(), name="ivms-events"),
    path("dashboard/summary/", DashboardSummaryAPIView.as_view(), name="dashboard-summary"),
    path("", include(router.urls)),
    path("ivms/webhook/", IvmsEventAPIView.as_view(), name="ivms-webhook"),
]


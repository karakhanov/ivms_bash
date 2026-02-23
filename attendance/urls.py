from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api import DailyAttendanceSummaryViewSet, IvmsEventAPIView

router = DefaultRouter()
router.register(
    r"daily-attendance-summaries",
    DailyAttendanceSummaryViewSet,
    basename="daily-attendance-summary",
)

urlpatterns = [
    path("ivms/events/", IvmsEventAPIView.as_view(), name="ivms-events"),
    path("", include(router.urls)),
    path("ivms/webhook/", IvmsEventAPIView.as_view(), name="ivms-webhook"),
]


from django.urls import path

from apps.notifications.views import (
    NotificationListApiView,
    NotificationDeleteApiView,
    NotificationPageView,
    NotificationReadAllApiView,
    NotificationReadApiView,
    NotificationTestApiView,
    NotificationUnreadCountApiView,
)

app_name = "notifications"

urlpatterns = [
    path("profile/notifications/", NotificationPageView.as_view(), name="page"),
    path("api/notifications/", NotificationListApiView.as_view(), name="list"),
    path("api/notifications/unread-count/", NotificationUnreadCountApiView.as_view(), name="unread-count"),
    path("api/notifications/<int:notification_id>/read/", NotificationReadApiView.as_view(), name="read"),
    path("api/notifications/<int:notification_id>/delete/", NotificationDeleteApiView.as_view(), name="delete"),
    path("api/notifications/read-all/", NotificationReadAllApiView.as_view(), name="read-all"),
    path("api/notifications/test/", NotificationTestApiView.as_view(), name="test"),
]

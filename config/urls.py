from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve as static_serve
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from apps.complaints.views import ComplaintViewSet
from apps.content.views import ContentItemViewSet
from apps.donations.views import DonationViewSet
from apps.mosques.views import MosqueViewSet
from apps.notifications.views import NotificationViewSet
from apps.projects.views import ProjectViewSet
from apps.reports.views import ReportViewSet
from apps.subscriptions.views import SubscriptionViewSet
from apps.users.views import AuthViewSet, MaxWebhookView, UserViewSet
from common.api.views import HealthcheckView, PlatformAdminViewSet

router = DefaultRouter()
router.register("auth", AuthViewSet, basename="auth")
router.register("users", UserViewSet, basename="users")
router.register("mosques", MosqueViewSet, basename="mosques")
router.register("projects", ProjectViewSet, basename="projects")
router.register("donations", DonationViewSet, basename="donations")
router.register("subscriptions", SubscriptionViewSet, basename="subscriptions")
router.register("complaints", ComplaintViewSet, basename="complaints")
router.register("reports", ReportViewSet, basename="reports")
router.register("notifications", NotificationViewSet, basename="notifications")
router.register("content", ContentItemViewSet, basename="content")
router.register("admin", PlatformAdminViewSet, basename="platform-admin")


def media_serve_view(request, path):
    return static_serve(request, path, document_root=settings.MEDIA_ROOT)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", HealthcheckView.as_view(), name="healthcheck"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/docs/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("api/max/webhook/", MaxWebhookView.as_view(), name="max-webhook"),
    path("api/v1/", include(router.urls)),
    path("", include("apps.platform.urls")),
    re_path(r"^media/(?P<path>.*)$", media_serve_view, name="media"),
]

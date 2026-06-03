from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.generic import TemplateView, View
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.notifications.filters import NotificationFilterSet
from apps.notifications.models import Notification
from apps.notifications.permissions import NotificationAccessPermission
from apps.notifications.selectors import get_notifications_for_actor
from apps.notifications.serializers import NotificationSerializer
from apps.notifications.services import NotificationService
from apps.platform.selectors import get_landing_page_context


class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = NotificationSerializer
    permission_classes = [NotificationAccessPermission]
    filterset_class = NotificationFilterSet
    search_fields = ["title", "message"]
    ordering_fields = ["created_at", "read_at"]

    def get_queryset(self):
        return get_notifications_for_actor(actor=self.request.user)

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = NotificationService.mark_as_read(notification=self.get_object(), user=request.user)
        return Response(self.get_serializer(notification).data)


class NotificationPageView(LoginRequiredMixin, TemplateView):
    template_name = "landing/notifications.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_landing_page_context())
        filter_value = (self.request.GET.get("filter") or "all").strip()
        queryset = NotificationService.get_user_notifications(user=self.request.user)
        if filter_value == "unread":
            queryset = queryset.filter(is_read=False)
        elif filter_value == "read":
            queryset = queryset.filter(is_read=True)
        elif filter_value == "important":
            queryset = queryset.filter(notification_type__in=[Notification.NotificationType.WARNING, Notification.NotificationType.ERROR])

        base_queryset = NotificationService.get_user_notifications(user=self.request.user)
        notifications_unread_count = base_queryset.filter(is_read=False).count()
        notifications_read_count = base_queryset.filter(is_read=True).count()
        notifications_important_count = base_queryset.filter(
            notification_type__in=[Notification.NotificationType.WARNING, Notification.NotificationType.ERROR]
        ).count()
        notifications_total_count = base_queryset.count()

        context.update(
            {
                "page_title": "Уведомления",
                "current_page": "profile",
                "profile_section": "notifications",
                "notifications_filter": filter_value,
                "notifications_list": queryset[:50],
                "notifications_unread_count": notifications_unread_count,
                "notifications_read_count": notifications_read_count,
                "notifications_total_count": notifications_total_count,
                "notifications_important_count": notifications_important_count,
            }
        )
        return context


class NotificationListApiView(LoginRequiredMixin, View):
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        limit = min(max(int(request.GET.get("limit", 8) or 8), 1), 50)
        queryset = NotificationService.get_user_notifications(user=request.user)
        filter_value = (request.GET.get("filter") or "all").strip()
        if filter_value == "unread":
            queryset = queryset.filter(is_read=False)
        elif filter_value == "read":
            queryset = queryset.filter(is_read=True)
        elif filter_value == "important":
            queryset = queryset.filter(notification_type__in=[Notification.NotificationType.WARNING, Notification.NotificationType.ERROR])
        payload = NotificationSerializer(queryset[:limit], many=True).data
        return JsonResponse({"success": True, "results": payload})


class NotificationUnreadCountApiView(LoginRequiredMixin, View):
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        return JsonResponse({"count": NotificationService.get_unread_count(user=request.user)})


class NotificationReadApiView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, notification_id, *args, **kwargs):
        notification = get_object_or_404(Notification, pk=notification_id, is_deleted=False)
        if notification.user_id is None and not request.user.is_platform_admin:
            raise Http404
        if notification.user_id not in {request.user.id, None} and not request.user.is_platform_admin:
            raise Http404
        notification = NotificationService.mark_as_read(notification=notification, user=request.user)
        return JsonResponse({"success": True, "notification": NotificationSerializer(notification).data})


class NotificationDeleteApiView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, notification_id, *args, **kwargs):
        notification = get_object_or_404(Notification, pk=notification_id, is_deleted=False)
        if notification.user_id is None and not request.user.is_platform_admin:
            raise Http404
        if notification.user_id not in {request.user.id, None} and not request.user.is_platform_admin:
            raise Http404
        NotificationService.delete_notification(notification=notification, user=request.user)
        return JsonResponse({"success": True, "deleted": True})


class NotificationReadAllApiView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        count = NotificationService.mark_all_as_read(user=request.user)
        return JsonResponse({"success": True, "updated": count, "count": 0})


class NotificationTestApiView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        if not request.user.is_staff and not request.user.is_platform_admin:
            return JsonResponse({"success": False, "message": "Недостаточно прав."}, status=403)
        notification = NotificationService.create_notification(
            user=request.user,
            title="Тестовое уведомление",
            message=f"Проверка звука и интерфейса {timezone.localtime().strftime('%d.%m.%Y %H:%M:%S')}",
            event=Notification.Event.TEST,
            notification_type=Notification.NotificationType.INFO,
            link="/profile/notifications/",
        )
        return JsonResponse({"success": True, "notification": NotificationSerializer(notification).data if notification else None})

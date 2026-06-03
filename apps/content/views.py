from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.content.filters import ContentFilterSet
from apps.content.permissions import ContentAccessPermission
from apps.content.selectors import get_content_for_actor
from apps.content.serializers import ContentItemSerializer
from apps.content.services import ContentService
from common.permissions import CanModerateObject
from common.utils.auth import get_actor_or_anonymous


class ContentItemViewSet(viewsets.ModelViewSet):
    serializer_class = ContentItemSerializer
    filterset_class = ContentFilterSet
    search_fields = ["title", "body"]
    ordering_fields = ["created_at", "published_at", "title"]

    def get_permissions(self):
        if self.action in {"approve", "reject"}:
            return [CanModerateObject()]
        return [ContentAccessPermission()]

    def get_queryset(self):
        return get_content_for_actor(actor=get_actor_or_anonymous(self.request.user))

    def perform_create(self, serializer):
        serializer.instance = ContentService.create_content(actor=self.request.user, **serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = ContentService.update_content(
            item=self.get_object(), actor=self.request.user, **serializer.validated_data
        )

    def perform_destroy(self, instance):
        instance.soft_delete()

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        item = ContentService.approve(item=self.get_object(), actor=request.user)
        return Response(self.get_serializer(item).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        item = ContentService.reject(item=self.get_object(), actor=request.user)
        return Response(self.get_serializer(item).data)

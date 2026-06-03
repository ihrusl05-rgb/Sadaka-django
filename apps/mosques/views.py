from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.mosques.filters import MosqueFilterSet
from apps.mosques.models import Mosque
from apps.mosques.permissions import MosqueAccessPermission
from apps.mosques.selectors import get_mosques_for_actor
from apps.mosques.serializers import MosqueSerializer
from apps.mosques.services import MosqueService
from common.permissions import CanModerateObject, IsMosqueAdmin
from common.utils.auth import get_actor_or_anonymous


class MosqueViewSet(viewsets.ModelViewSet):
    serializer_class = MosqueSerializer
    filterset_class = MosqueFilterSet
    search_fields = ["name", "city", "description", "address"]
    ordering_fields = ["created_at", "name", "published_at"]

    def get_permissions(self):
        if self.action in {"verify", "approve", "reject", "block", "unblock"}:
            return [CanModerateObject()]
        if self.action == "create":
            return [IsMosqueAdmin()]
        return [MosqueAccessPermission()]

    def get_queryset(self):
        return get_mosques_for_actor(actor=get_actor_or_anonymous(self.request.user))

    def perform_create(self, serializer):
        serializer.instance = MosqueService.create_mosque(actor=self.request.user, **serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = MosqueService.update_mosque(
            mosque=self.get_object(), actor=self.request.user, **serializer.validated_data
        )

    def perform_destroy(self, instance):
        instance.soft_delete()

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        mosque = MosqueService.verify(mosque=self.get_object(), actor=request.user)
        return Response(self.get_serializer(mosque).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        mosque = MosqueService.approve(mosque=self.get_object(), actor=request.user)
        return Response(self.get_serializer(mosque).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        mosque = MosqueService.reject(mosque=self.get_object(), actor=request.user)
        return Response(self.get_serializer(mosque).data)

    @action(detail=True, methods=["post"])
    def block(self, request, pk=None):
        mosque = MosqueService.block(mosque=self.get_object(), actor=request.user, reason=request.data.get("reason", ""))
        return Response(self.get_serializer(mosque).data)

    @action(detail=True, methods=["post"])
    def unblock(self, request, pk=None):
        mosque = MosqueService.unblock(mosque=self.get_object(), actor=request.user)
        return Response(self.get_serializer(mosque).data)

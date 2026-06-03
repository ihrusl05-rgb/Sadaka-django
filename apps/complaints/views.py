from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.complaints.filters import ComplaintFilterSet
from apps.complaints.permissions import ComplaintAccessPermission
from apps.complaints.selectors import get_complaints_for_actor
from apps.complaints.serializers import ComplaintHandleSerializer, ComplaintSerializer
from apps.complaints.services import ComplaintService
from common.permissions import IsPlatformAdmin


class ComplaintViewSet(viewsets.ModelViewSet):
    serializer_class = ComplaintSerializer
    permission_classes = [ComplaintAccessPermission]
    filterset_class = ComplaintFilterSet
    search_fields = ["description", "user__email"]
    ordering_fields = ["created_at", "handled_at"]

    def get_queryset(self):
        return get_complaints_for_actor(actor=self.request.user)

    def perform_create(self, serializer):
        serializer.instance = ComplaintService.create_complaint(actor=self.request.user, **serializer.validated_data)

    @action(detail=True, methods=["post"], permission_classes=[IsPlatformAdmin])
    def handle(self, request, pk=None):
        serializer = ComplaintHandleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        complaint = ComplaintService.handle_complaint(
            complaint=self.get_object(), actor=request.user, **serializer.validated_data
        )
        return Response(self.get_serializer(complaint).data)

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.donations.filters import DonationFilterSet
from apps.donations.permissions import DonationAccessPermission
from apps.donations.selectors import get_donations_for_actor
from apps.donations.serializers import DonationSerializer
from apps.donations.services import DonationService
from common.permissions import IsPlatformAdmin


class DonationViewSet(viewsets.ModelViewSet):
    serializer_class = DonationSerializer
    permission_classes = [DonationAccessPermission]
    filterset_class = DonationFilterSet
    search_fields = ["receipt_number", "provider_payment_id", "user__email"]
    ordering_fields = ["created_at", "paid_at", "amount"]

    def get_queryset(self):
        return get_donations_for_actor(actor=self.request.user)

    def perform_create(self, serializer):
        serializer.instance = DonationService.create_donation(actor=self.request.user, **serializer.validated_data)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        donation = DonationService.confirm_payment(donation=self.get_object(), actor=request.user)
        return Response(self.get_serializer(donation).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        donation = DonationService.cancel_payment(donation=self.get_object(), actor=request.user)
        return Response(self.get_serializer(donation).data)

    @action(detail=True, methods=["post"], permission_classes=[IsPlatformAdmin])
    def refund(self, request, pk=None):
        donation = DonationService.refund_payment(donation=self.get_object(), actor=request.user)
        return Response(self.get_serializer(donation).data)

    @action(detail=True, methods=["get"])
    def receipt(self, request, pk=None):
        donation = self.get_object()
        return Response(
            {
                "receipt_number": donation.receipt_number,
                "amount": donation.amount,
                "net_amount": donation.net_amount,
                "paid_at": donation.paid_at,
            }
        )

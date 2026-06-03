from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.subscriptions.filters import SubscriptionFilterSet
from apps.subscriptions.permissions import SubscriptionAccessPermission
from apps.subscriptions.selectors import get_subscriptions_for_actor
from apps.subscriptions.serializers import SubscriptionSerializer
from apps.subscriptions.services import SubscriptionService


class SubscriptionViewSet(viewsets.ModelViewSet):
    serializer_class = SubscriptionSerializer
    permission_classes = [SubscriptionAccessPermission]
    filterset_class = SubscriptionFilterSet
    search_fields = ["user__email", "provider_subscription_id"]
    ordering_fields = ["created_at", "next_charge_date", "amount"]

    def get_queryset(self):
        return get_subscriptions_for_actor(actor=self.request.user)

    def perform_create(self, serializer):
        serializer.instance = SubscriptionService.create_subscription(
            actor=self.request.user, **serializer.validated_data
        )

    def perform_update(self, serializer):
        serializer.instance = SubscriptionService.update_subscription(
            subscription=self.get_object(), actor=self.request.user, **serializer.validated_data
        )

    def perform_destroy(self, instance):
        SubscriptionService.cancel_subscription(subscription=instance, actor=self.request.user)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        subscription = SubscriptionService.cancel_subscription(subscription=self.get_object(), actor=request.user)
        return Response(self.get_serializer(subscription).data)

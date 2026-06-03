from rest_framework import serializers

from apps.subscriptions.models import Subscription


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = [
            "id",
            "user",
            "mosque",
            "project",
            "amount",
            "currency",
            "interval",
            "status",
            "next_charge_date",
            "last_charged_at",
            "cancelled_at",
            "provider_subscription_id",
            "payment_method",
            "provider",
            "is_public_anonymous",
            "metadata",
        ]
        read_only_fields = [
            "user",
            "currency",
            "status",
            "last_charged_at",
            "cancelled_at",
            "provider_subscription_id",
        ]

    def validate(self, attrs):
        project = attrs.get("project")
        mosque = attrs.get("mosque")
        if project and mosque and project.mosque_id != mosque.id:
            raise serializers.ValidationError("Project must belong to the selected mosque.")
        return attrs

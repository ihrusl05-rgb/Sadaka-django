from rest_framework import serializers

from apps.donations.models import Donation


class DonationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Donation
        fields = [
            "id",
            "user",
            "mosque",
            "project",
            "subscription",
            "amount",
            "currency",
            "platform_fee_amount",
            "net_amount",
            "status",
            "payment_method",
            "provider",
            "provider_payment_id",
            "receipt_number",
            "paid_at",
            "is_public_anonymous",
            "metadata",
            "external_reference",
        ]
        read_only_fields = [
            "user",
            "currency",
            "platform_fee_amount",
            "net_amount",
            "status",
            "provider_payment_id",
            "receipt_number",
            "paid_at",
            "external_reference",
        ]

    def validate(self, attrs):
        project = attrs.get("project")
        mosque = attrs.get("mosque")
        if project and mosque and project.mosque_id != mosque.id:
            raise serializers.ValidationError("Project must belong to the selected mosque.")
        return attrs

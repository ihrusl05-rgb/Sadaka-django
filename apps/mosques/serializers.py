from rest_framework import serializers

from apps.mosques.models import Mosque, MosqueMembership


class MosqueMembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = MosqueMembership
        fields = ["id", "user", "user_email", "is_primary"]


class MosqueSerializer(serializers.ModelSerializer):
    memberships = MosqueMembershipSerializer(many=True, read_only=True)

    class Meta:
        model = Mosque
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "public_story",
            "city",
            "address",
            "contact_email",
            "contact_phone",
            "cover_image",
            "featured_project",
            "legal_name",
            "inn",
            "kpp",
            "ogrn",
            "bank_account",
            "bank_name",
            "bik",
            "corr_account",
            "legal_address",
            "actual_address",
            "okpo",
            "oktmo",
            "okato",
            "verification_status",
            "moderation_status",
            "is_blocked",
            "blocked_reason",
            "published_at",
            "memberships",
        ]
        read_only_fields = ["slug", "verification_status", "moderation_status", "is_blocked", "published_at"]

    def validate(self, attrs):
        featured_project = attrs.get("featured_project", getattr(self.instance, "featured_project", None))
        mosque = self.instance
        if featured_project is not None and mosque is not None and featured_project.mosque_id != mosque.id:
            raise serializers.ValidationError({"featured_project": "Главный проект должен относиться к выбранной мечети."})
        return attrs

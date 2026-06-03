from rest_framework import serializers

from apps.content.models import ContentItem


class ContentItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentItem
        fields = [
            "id",
            "mosque",
            "title",
            "slug",
            "body",
            "type",
            "scope",
            "moderation_status",
            "is_published",
            "published_at",
            "is_blocked",
        ]
        read_only_fields = ["slug", "moderation_status", "is_published", "published_at", "is_blocked"]

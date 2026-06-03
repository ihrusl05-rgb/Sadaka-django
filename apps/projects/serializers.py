from rest_framework import serializers

from apps.projects.models import Project


class ProjectSerializer(serializers.ModelSerializer):
    progress = serializers.FloatField(read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "mosque",
            "title",
            "slug",
            "cover_image",
            "description",
            "status",
            "goal_amount",
            "current_amount",
            "progress",
            "start_date",
            "end_date",
            "published_at",
            "is_blocked",
        ]
        read_only_fields = ["slug", "current_amount", "published_at", "is_blocked"]

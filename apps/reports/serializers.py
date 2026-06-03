from rest_framework import serializers

from apps.reports.models import Report


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = [
            "id",
            "requested_by",
            "mosque",
            "project",
            "scope_type",
            "format",
            "period_start",
            "period_end",
            "status",
            "file",
            "error_message",
        ]
        read_only_fields = ["requested_by", "status", "file", "error_message"]

    def validate(self, attrs):
        scope_type = attrs.get("scope_type")
        mosque = attrs.get("mosque")
        project = attrs.get("project")
        if scope_type == Report.ScopeType.MOSQUE and not mosque:
            raise serializers.ValidationError("Mosque scope requires mosque.")
        if scope_type == Report.ScopeType.PROJECT and not project:
            raise serializers.ValidationError("Project scope requires project.")
        return attrs

from rest_framework import serializers

from apps.complaints.models import Complaint


class ComplaintSerializer(serializers.ModelSerializer):
    class Meta:
        model = Complaint
        fields = [
            "id",
            "user",
            "content_type",
            "object_id",
            "description",
            "status",
            "resolution_note",
            "handled_by",
            "handled_at",
        ]
        read_only_fields = ["user", "status", "resolution_note", "handled_by", "handled_at"]


class ComplaintHandleSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[Complaint.Status.RESOLVED, Complaint.Status.REJECTED, Complaint.Status.IN_REVIEW])
    resolution_note = serializers.CharField()

from rest_framework import serializers

from apps.notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    created_label = serializers.SerializerMethodField()
    type_label = serializers.CharField(source="get_notification_type_display", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "user",
            "title",
            "message",
            "notification_type",
            "type_label",
            "event",
            "link",
            "is_read",
            "is_sound_enabled",
            "sound_key",
            "payload",
            "created_at",
            "created_label",
            "read_at",
        ]
        read_only_fields = fields

    def get_created_label(self, obj):
        return obj.created_at.strftime("%d.%m.%Y %H:%M")

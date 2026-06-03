from rest_framework import serializers


class HealthcheckSerializer(serializers.Serializer):
    status = serializers.CharField()
    checks = serializers.DictField(child=serializers.CharField(), required=False)


class PlatformAnalyticsSerializer(serializers.Serializer):
    users = serializers.IntegerField()
    mosques = serializers.IntegerField()
    donations = serializers.IntegerField()
    complaints_by_status = serializers.ListField()

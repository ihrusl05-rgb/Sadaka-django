from django.contrib.auth.password_validation import validate_password
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.users.models import MaxAccount, TelegramAccount, User


class UserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    photo = serializers.ImageField(required=False, allow_null=True)
    telegram_id = serializers.SerializerMethodField()
    telegram_chat_id = serializers.SerializerMethodField()
    telegram_username = serializers.SerializerMethodField()
    telegram_first_name = serializers.SerializerMethodField()
    telegram_last_name = serializers.SerializerMethodField()
    telegram_photo_url = serializers.SerializerMethodField()
    telegram_linked = serializers.SerializerMethodField()
    telegram_linked_at = serializers.SerializerMethodField()
    max_user_id = serializers.SerializerMethodField()
    max_chat_id = serializers.SerializerMethodField()
    max_username = serializers.SerializerMethodField()
    max_first_name = serializers.SerializerMethodField()
    max_last_name = serializers.SerializerMethodField()
    max_photo_url = serializers.SerializerMethodField()
    max_linked = serializers.SerializerMethodField()
    max_linked_at = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "first_name",
            "last_name",
            "middle_name",
            "phone",
            "photo",
            "role",
            "telegram_id",
            "telegram_chat_id",
            "telegram_username",
            "telegram_first_name",
            "telegram_last_name",
            "telegram_photo_url",
            "telegram_linked",
            "telegram_linked_at",
            "max_user_id",
            "max_chat_id",
            "max_username",
            "max_first_name",
            "max_last_name",
            "max_photo_url",
            "max_linked",
            "max_linked_at",
            "is_email_verified",
            "is_phone_verified",
            "is_blocked",
            "last_activity_at",
            "date_joined",
        ]
        read_only_fields = ["id", "role", "is_email_verified", "is_phone_verified", "is_blocked", "last_activity_at", "date_joined"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["email"] = instance.profile_email
        return data

    def _telegram_account(self, instance):
        try:
            return instance.telegram_account
        except TelegramAccount.DoesNotExist:
            return None

    def _max_account(self, instance):
        try:
            return instance.max_account
        except MaxAccount.DoesNotExist:
            return None

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_telegram_id(self, instance) -> int | None:
        account = self._telegram_account(instance)
        return account.telegram_id if account else None

    def get_telegram_chat_id(self, instance):
        account = self._telegram_account(instance)
        return account.chat_id if account else None

    @extend_schema_field(serializers.CharField())
    def get_telegram_username(self, instance) -> str:
        account = self._telegram_account(instance)
        return account.username if account else ""

    @extend_schema_field(serializers.CharField())
    def get_telegram_first_name(self, instance) -> str:
        account = self._telegram_account(instance)
        return account.first_name if account else ""

    @extend_schema_field(serializers.CharField())
    def get_telegram_last_name(self, instance) -> str:
        account = self._telegram_account(instance)
        return account.last_name if account else ""

    @extend_schema_field(serializers.CharField())
    def get_telegram_photo_url(self, instance) -> str:
        account = self._telegram_account(instance)
        return account.photo_url if account else ""

    def get_telegram_linked(self, instance):
        return self._telegram_account(instance) is not None

    def get_telegram_linked_at(self, instance):
        account = self._telegram_account(instance)
        return account.linked_at if account else None

    def get_max_user_id(self, instance):
        account = self._max_account(instance)
        return account.max_user_id if account else None

    def get_max_chat_id(self, instance):
        account = self._max_account(instance)
        return account.chat_id if account else None

    def get_max_username(self, instance):
        account = self._max_account(instance)
        return account.username if account else ""

    def get_max_first_name(self, instance):
        account = self._max_account(instance)
        return account.first_name if account else ""

    def get_max_last_name(self, instance):
        account = self._max_account(instance)
        return account.last_name if account else ""

    def get_max_photo_url(self, instance):
        account = self._max_account(instance)
        return account.photo_url if account else ""

    def get_max_linked(self, instance):
        return self._max_account(instance) is not None

    def get_max_linked_at(self, instance):
        account = self._max_account(instance)
        return account.linked_at if account else None


class UserCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=255)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, validators=[validate_password])


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class TelegramLoginTokenSerializer(serializers.Serializer):
    token = serializers.CharField(read_only=True)
    telegram_url = serializers.URLField(read_only=True)


class TelegramConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    telegram_id = serializers.IntegerField(min_value=1)
    chat_id = serializers.IntegerField(required=False)
    username = serializers.CharField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    photo_url = serializers.URLField(required=False, allow_blank=True)


class TelegramRequestCodeSerializer(serializers.Serializer):
    token = serializers.CharField(required=False, allow_blank=True)
    telegram_id = serializers.IntegerField(required=False, min_value=1)

    def validate(self, attrs):
        if not attrs.get("token") and not attrs.get("telegram_id"):
            raise serializers.ValidationError("Передайте token или telegram_id.")
        return attrs


class TelegramVerifyCodeSerializer(serializers.Serializer):
    token = serializers.CharField()
    code = serializers.RegexField(r"^\d{6}$")


class MaxLoginTokenSerializer(serializers.Serializer):
    token = serializers.CharField(read_only=True)
    max_url = serializers.URLField(read_only=True)


class MaxRequestCodeSerializer(serializers.Serializer):
    token = serializers.CharField(required=False, allow_blank=True)
    max_user_id = serializers.IntegerField(required=False, min_value=1)

    def validate(self, attrs):
        if not attrs.get("token") and not attrs.get("max_user_id"):
            raise serializers.ValidationError("Передайте token или max_user_id.")
        return attrs


class MaxVerifyCodeSerializer(serializers.Serializer):
    token = serializers.CharField()
    code = serializers.RegexField(r"^\d{6}$")


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, validators=[validate_password])


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()

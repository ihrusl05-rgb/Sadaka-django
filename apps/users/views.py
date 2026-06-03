import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.filters import UserFilterSet
from apps.users.permissions import IsSelfOrPlatformAdmin
from apps.users.selectors import get_users_for_actor
from apps.users.serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    MaxLoginTokenSerializer,
    MaxRequestCodeSerializer,
    MaxVerifyCodeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetSerializer,
    TelegramConfirmSerializer,
    TelegramLoginTokenSerializer,
    TelegramRequestCodeSerializer,
    TelegramVerifyCodeSerializer,
    TokenPairSerializer,
    UserCreateSerializer,
    UserSerializer,
)
from apps.users.max_auth import MaxAuthService, MaxBotClient
from apps.users.services import UserService
from apps.users.telegram_auth import TelegramAuthService
from common.api.throttles import AuthBurstRateThrottle, TelegramStatusRateThrottle
from common.permissions import IsPlatformAdmin

User = get_user_model()


@extend_schema_view(
    list=extend_schema(tags=["Users"]),
    retrieve=extend_schema(tags=["Users"]),
    me=extend_schema(tags=["Users"]),
)
class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    filterset_class = UserFilterSet
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    search_fields = ["email", "full_name", "last_name", "first_name", "middle_name", "phone"]
    ordering_fields = ["date_joined", "full_name", "last_name", "first_name"]

    def get_permissions(self):
        if self.action == "me":
            return [IsAuthenticated()]
        if self.action in {"list", "create", "destroy"}:
            return [IsPlatformAdmin()]
        return [IsAuthenticated(), IsSelfOrPlatformAdmin()]

    def get_queryset(self):
        return get_users_for_actor(actor=self.request.user)

    @action(detail=False, methods=["get", "patch"], permission_classes=[IsAuthenticated])
    def me(self, request):
        if request.method == "PATCH":
            serializer = self.get_serializer(request.user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            user = UserService.update_profile(user=request.user, **serializer.validated_data)
            return Response(self.get_serializer(user).data)
        return Response(self.get_serializer(request.user).data)

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated])
    def change_password(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        UserService.change_password(user=request.user, **serializer.validated_data)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AuthViewSet(viewsets.ViewSet):
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action in {
            "register",
            "login",
            "refresh",
            "password_reset",
            "password_reset_confirm",
            "telegram_login_token",
            "telegram_login_status",
            "telegram_request_code",
            "telegram_verify_code",
            "telegram_confirm",
            "max_login_token",
            "max_login_status",
            "max_request_code",
            "max_verify_code",
        }:
            return [AllowAny()]
        return [IsAuthenticated()]

    @extend_schema(request=UserCreateSerializer, responses=UserSerializer, tags=["Auth"])
    @action(detail=False, methods=["post"], throttle_classes=[AuthBurstRateThrottle])
    def register(self, request):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = UserService.register_user(**serializer.validated_data)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=LoginSerializer, responses=TokenPairSerializer, tags=["Auth"])
    @action(detail=False, methods=["post"], throttle_classes=[AuthBurstRateThrottle])
    def login(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _, tokens = UserService.login(**serializer.validated_data)
        return Response(tokens)

    @extend_schema(request=None, responses=TelegramLoginTokenSerializer, tags=["Auth"])
    @action(detail=False, methods=["post"], url_path="telegram/login-token", throttle_classes=[AuthBurstRateThrottle])
    def telegram_login_token(self, request):
        result = TelegramAuthService.create_login_token(
            request_ip=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT"),
        )
        return Response(
            {
                "token": result.login_token.token,
                "telegram_url": result.telegram_url,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        tags=["Auth"],
        parameters=[
            OpenApiParameter(
                name="token",
                location=OpenApiParameter.PATH,
                required=True,
                type=str,
                description="Telegram login token",
            )
        ],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path=r"telegram/login-status/(?P<token>[^/.]+)",
        throttle_classes=[TelegramStatusRateThrottle],
    )
    def telegram_login_status(self, request, token: str = None):
        try:
            result = TelegramAuthService.get_login_status(token=token or "")
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.message)

        payload = {
            "status": result.status,
            "telegram_url": result.telegram_url,
        }
        if result.display_name:
            payload["display_name"] = result.display_name
        if result.debug_code:
            payload["debug_code"] = result.debug_code
        return Response(payload)

    @extend_schema(request=TelegramConfirmSerializer, tags=["Auth"])
    @action(detail=False, methods=["post"], url_path="telegram/confirm", throttle_classes=[AuthBurstRateThrottle])
    def telegram_confirm(self, request):
        serializer = TelegramConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        header_token = (request.headers.get("X-Telegram-Bot-Token") or "").strip()
        configured_token = (getattr(settings, "TELEGRAM_AUTH_BOT_TOKEN", "") or "").strip()
        if not configured_token or header_token != configured_token:
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        try:
            login_token = TelegramAuthService.confirm_login_token(**serializer.validated_data)
            result = TelegramAuthService.issue_code(login_token=login_token)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.message)

        payload = {"ok": True, "message": "Telegram подтвержден."}
        if result.debug_code:
            payload["debug_code"] = result.debug_code
        return Response(payload)

    @extend_schema(request=TelegramRequestCodeSerializer, tags=["Auth"])
    @action(detail=False, methods=["post"], url_path="telegram/request-code", throttle_classes=[AuthBurstRateThrottle])
    def telegram_request_code(self, request):
        serializer = TelegramRequestCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = TelegramAuthService.issue_code(
                token=serializer.validated_data.get("token") or None,
                telegram_id=serializer.validated_data.get("telegram_id"),
                request_ip=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT"),
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.message)

        payload = {"ok": True, "message": "Код отправлен в Telegram."}
        if result.debug_code:
            payload["debug_code"] = result.debug_code
        return Response(payload, status=status.HTTP_201_CREATED)

    @extend_schema(request=TelegramVerifyCodeSerializer, tags=["Auth"])
    @action(detail=False, methods=["post"], url_path="telegram/verify-code", throttle_classes=[AuthBurstRateThrottle])
    def telegram_verify_code(self, request):
        serializer = TelegramVerifyCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user, tokens = TelegramAuthService.verify_code(**serializer.validated_data)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.message)
        return Response(
            {
                "ok": True,
                "user": UserSerializer(user).data,
                "tokens": tokens,
            }
        )

    @extend_schema(request=None, responses=MaxLoginTokenSerializer, tags=["Auth"])
    @action(detail=False, methods=["post"], url_path="max/login-token")
    def max_login_token(self, request):
        result = MaxAuthService.create_login_token(
            request_ip=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT"),
        )
        return Response(
            {
                "token": result.login_token.token,
                "max_url": result.max_url,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(tags=["Auth"])
    @action(detail=False, methods=["get"], url_path=r"max/login-status/(?P<token>[^/.]+)")
    def max_login_status(self, request, token=None):
        try:
            result = MaxAuthService.get_login_status(token=token or "")
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.message)

        payload = {
            "status": result.status,
            "max_url": result.max_url,
        }
        if result.display_name:
            payload["display_name"] = result.display_name
        if result.debug_code:
            payload["debug_code"] = result.debug_code
        return Response(payload)

    @extend_schema(request=MaxRequestCodeSerializer, tags=["Auth"])
    @action(detail=False, methods=["post"], url_path="max/request-code")
    def max_request_code(self, request):
        serializer = MaxRequestCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = MaxAuthService.issue_code(
                token=serializer.validated_data.get("token") or None,
                max_user_id=serializer.validated_data.get("max_user_id"),
                request_ip=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT"),
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.message)

        payload = {"ok": True, "message": "Код отправлен в MAX."}
        if result.debug_code:
            payload["debug_code"] = result.debug_code
        return Response(payload, status=status.HTTP_201_CREATED)

    @extend_schema(request=MaxVerifyCodeSerializer, tags=["Auth"])
    @action(detail=False, methods=["post"], url_path="max/verify-code")
    def max_verify_code(self, request):
        serializer = MaxVerifyCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user, tokens = MaxAuthService.verify_code(**serializer.validated_data)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.message)
        return Response(
            {
                "ok": True,
                "user": UserSerializer(user).data,
                "tokens": tokens,
            }
        )

    @extend_schema(tags=["Auth"])
    @action(detail=False, methods=["post"], throttle_classes=[AuthBurstRateThrottle])
    def refresh(self, request):
        refresh = RefreshToken(request.data.get("refresh"))
        return Response({"access": str(refresh.access_token)})

    @extend_schema(request=LogoutSerializer, tags=["Auth"])
    @action(detail=False, methods=["post"])
    def logout(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        UserService.logout(refresh_token=serializer.validated_data["refresh"], actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=PasswordResetSerializer, tags=["Auth"])
    @action(detail=False, methods=["post"], throttle_classes=[AuthBurstRateThrottle])
    def password_reset(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = UserService.initiate_password_reset(**serializer.validated_data)
        return Response(payload or {"detail": "If the account exists, reset instructions were sent."})

    @extend_schema(request=PasswordResetConfirmSerializer, tags=["Auth"])
    @action(detail=False, methods=["post"], throttle_classes=[AuthBurstRateThrottle])
    def password_reset_confirm(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        UserService.confirm_password_reset(**serializer.validated_data)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(tags=["Auth"], responses=UserSerializer)
    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def me(self, request):
        return Response(UserSerializer(request.user).data)


@method_decorator(csrf_exempt, name="dispatch")
class MaxWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        configured_secret = (getattr(settings, "MAX_AUTH_WEBHOOK_SECRET", "") or "").strip()
        request_secret = (request.headers.get("X-Max-Bot-Api-Secret") or "").strip()
        if configured_secret and request_secret != configured_secret:
            return HttpResponse(status=403)

        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return HttpResponse(status=200)

        self._handle_update(payload, request)
        return HttpResponse(status=200)

    def _handle_update(self, payload, request):
        if not isinstance(payload, dict):
            return

        update_type = payload.get("update_type")
        if update_type == "bot_started":
            self._handle_bot_started(payload, request)
        elif update_type == "message_created":
            self._handle_message_created(payload, request)

    def _handle_bot_started(self, payload, request):
        user_payload = payload.get("user") or {}
        chat_payload = payload.get("chat") or {}
        start_payload = (payload.get("payload") or "").strip()
        if not start_payload.startswith("login_"):
            return

        token = start_payload.removeprefix("login_").strip()
        max_user_id = self._extract_user_id(payload, user_payload)
        chat_id = self._extract_chat_id(payload, chat_payload)
        if not token or not max_user_id:
            return

        try:
            login_token = MaxAuthService.confirm_login_token(
                token=token,
                max_user_id=max_user_id,
                chat_id=chat_id,
                username=user_payload.get("username", "") or "",
                first_name=user_payload.get("first_name", "") or "",
                last_name=user_payload.get("last_name", "") or "",
                photo_url=user_payload.get("photo_url", "") or "",
                auth_date=parse_datetime(user_payload.get("auth_date") or "") if user_payload.get("auth_date") else None,
            )
            MaxAuthService.issue_code(
                login_token=login_token,
                request_ip=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT"),
            )
        except DjangoValidationError as exc:
            self._send_error_message(
                user_id=max_user_id,
                chat_id=chat_id,
                message=exc.message,
            )

    def _handle_message_created(self, payload, request):
        message = payload.get("message") or {}
        sender = payload.get("sender") or payload.get("user") or {}
        chat_payload = payload.get("chat") or {}
        text = ((message.get("text") or (message.get("body") or {}).get("text") or "")).strip().lower()
        if text not in {"/login", "login", "вход"}:
            return

        max_user_id = self._extract_user_id(payload, sender)
        chat_id = self._extract_chat_id(payload, chat_payload)
        if not max_user_id:
            return

        try:
            MaxAuthService.issue_code_for_pending_login(
                max_user_id=max_user_id,
                chat_id=chat_id,
                request_ip=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT"),
            )
        except DjangoValidationError as exc:
            self._send_error_message(
                user_id=max_user_id,
                chat_id=chat_id,
                message=exc.message,
            )

    @staticmethod
    def _coerce_int(value):
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def _extract_chat_id(cls, payload, chat_payload):
        return cls._coerce_int(
            payload.get("chat_id")
            or chat_payload.get("chat_id")
            or chat_payload.get("id")
        )

    @classmethod
    def _extract_user_id(cls, payload, user_payload):
        return cls._coerce_int(
            payload.get("user_id")
            or user_payload.get("user_id")
            or user_payload.get("id")
            or (payload.get("sender") or {}).get("user_id")
            or (payload.get("sender") or {}).get("id")
        )

    @staticmethod
    def _send_error_message(*, user_id, chat_id, message):
        if not message or (not user_id and not chat_id):
            return
        try:
            MaxBotClient.send_text(chat_id=chat_id, user_id=user_id, text=message)
        except DjangoValidationError:
            return

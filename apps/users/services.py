import re
from math import ceil

from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework_simplejwt.tokens import RefreshToken

from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.platform.services import AuditLogService
from apps.users.models import User
from common.services.email import send_platform_email


class UserService:
    @staticmethod
    def normalize_phone(phone: str) -> str:
        digits = re.sub(r"\D", "", phone or "")

        if len(digits) == 10:
            digits = f"7{digits}"
        elif len(digits) == 11 and digits.startswith("8"):
            digits = f"7{digits[1:]}"
        elif len(digits) == 11 and digits.startswith("7"):
            pass
        else:
            raise ValidationError("Номер должен быть в формате +7XXXXXXXXXX")

        return f"+{digits}"

    @staticmethod
    def mask_phone(phone: str) -> str:
        normalized_phone = UserService.normalize_phone(phone)
        local_digits = normalized_phone[2:]
        last_four_digits = local_digits[-4:]
        return f"+7 •• ••• •{last_four_digits[:2]} {last_four_digits[2:]}"

    @staticmethod
    def seconds_until(dt) -> int:
        if not dt:
            return 0
        return max(0, ceil((dt - timezone.now()).total_seconds()))

    @staticmethod
    def format_seconds_mmss(total_seconds: int) -> str:
        seconds = max(0, int(total_seconds))
        minutes = seconds // 60
        rest_seconds = seconds % 60
        return f"{minutes:02d}:{rest_seconds:02d}"

    @staticmethod
    def _validate_phone_uniqueness(*, phone: str, exclude_user_id: int | None = None) -> None:
        queryset = User.all_objects.filter(phone=phone)
        if exclude_user_id is not None:
            queryset = queryset.exclude(pk=exclude_user_id)
        if queryset.exists():
            raise ValidationError("Этот номер телефона уже используется другим пользователем.")

    @staticmethod
    def _touch_last_activity(user: User) -> None:
        user.last_activity_at = timezone.now()
        user.save(update_fields=["last_activity_at", "updated_at"])

    @staticmethod
    def bind_inviter(*, user: User, inviter: User | None) -> User:
        if inviter is None or user.invited_by_id or user.pk == inviter.pk:
            return user
        user.invited_by = inviter
        user.save(update_fields=["invited_by", "updated_at"])
        AuditLogService.log(action="user.inviter_bound", obj=user, metadata={"inviter_id": inviter.pk})
        return user

    @staticmethod
    def register_user(*, email: str, password: str, full_name: str, phone: str = "") -> User:
        normalized_phone = UserService.normalize_phone(phone) if phone else ""
        if normalized_phone:
            UserService._validate_phone_uniqueness(phone=normalized_phone)
        user = User.objects.create_user(email=email, password=password, full_name=full_name, phone=normalized_phone)
        AuditLogService.log(action="user.registered", obj=user, metadata={"email": user.email})
        NotificationService.notify_platform_admins(
            title="Новый пользователь зарегистрирован",
            message=f"На платформе зарегистрировался новый пользователь: {user.email}.",
            event=Notification.Event.NEW_USER_REGISTERED,
            notification_type=Notification.NotificationType.INFO,
            link="/admin/users/user/",
            payload={"user_id": user.id},
        )
        return user

    @staticmethod
    def issue_tokens(*, user: User) -> dict[str, str]:
        refresh = RefreshToken.for_user(user)
        return {"access": str(refresh.access_token), "refresh": str(refresh)}

    @staticmethod
    def login(*, email: str, password: str) -> tuple[User, dict[str, str]]:
        user = authenticate(email=email, password=password)
        if not user:
            raise ValidationError("Invalid credentials.")
        if user.is_blocked:
            raise ValidationError("User is blocked.")
        UserService._touch_last_activity(user)
        AuditLogService.log(action="user.logged_in", obj=user, metadata={"email": user.email})
        return user, UserService.issue_tokens(user=user)

    @staticmethod
    def logout(*, refresh_token: str, actor: User | None = None) -> None:
        token = RefreshToken(refresh_token)
        token.blacklist()
        AuditLogService.log(action="user.logged_out", obj=actor, metadata={"refresh": refresh_token[-8:]})

    @staticmethod
    def update_profile(*, user: User, **payload) -> User:
        update_fields = ["updated_at"]
        if "full_name" in payload and not any(key in payload for key in ("first_name", "last_name", "middle_name")):
            last_name, first_name, middle_name = User.split_full_name(payload["full_name"])
            payload["last_name"] = last_name
            payload["first_name"] = first_name
            payload["middle_name"] = middle_name

        for field in ("first_name", "last_name", "middle_name"):
            if field in payload:
                setattr(user, field, (payload[field] or "").strip())
                update_fields.append(field)

        if any(field in payload for field in ("first_name", "last_name", "middle_name", "full_name")):
            user.full_name = User.build_full_name(
                last_name=user.last_name,
                first_name=user.first_name,
                middle_name=user.middle_name,
            )
            update_fields.append("full_name")

        if "phone" in payload:
            normalized_phone = UserService.normalize_phone(payload["phone"]) if payload["phone"] else ""
            if normalized_phone:
                UserService._validate_phone_uniqueness(phone=normalized_phone, exclude_user_id=user.id)
            user.phone = normalized_phone
            update_fields.append("phone")
        if "email" in payload:
            raw_email = (payload["email"] or "").strip()
            if raw_email:
                normalized_email = User.objects.normalize_email(raw_email)
                if User.all_objects.exclude(pk=user.pk).filter(email__iexact=normalized_email).exists():
                    raise ValidationError("Пользователь с таким email уже существует.")
                user.email = normalized_email
                update_fields.append("email")
        if "photo" in payload:
            user.photo = payload["photo"]
            update_fields.append("photo")
        user.save(update_fields=update_fields)
        AuditLogService.log(action="user.profile_updated", obj=user)
        NotificationService.notify_user(
            user,
            title="Профиль обновлен",
            message="Ваши данные в личном кабинете успешно сохранены.",
            event=Notification.Event.PROFILE_UPDATED,
            notification_type=Notification.NotificationType.SUCCESS,
            link="/profile/",
            payload={"user_id": user.id},
        )
        return user

    @staticmethod
    def change_password(*, user: User, current_password: str, new_password: str) -> None:
        if not user.check_password(current_password):
            raise ValidationError("Current password is invalid.")
        user.set_password(new_password)
        user.save(update_fields=["password"])
        AuditLogService.log(action="user.password_changed", obj=user)
        NotificationService.notify_user(
            user,
            title="Пароль изменен",
            message="Пароль вашего аккаунта был успешно изменен.",
            event=Notification.Event.PASSWORD_CHANGED,
            notification_type=Notification.NotificationType.SUCCESS,
            link="/profile/",
            payload={"user_id": user.id},
            telegram=True,
        )

    @staticmethod
    def set_password(*, user: User, new_password: str) -> None:
        user.set_password(new_password)
        user.save(update_fields=["password"])
        AuditLogService.log(action="user.password_changed", obj=user)
        NotificationService.notify_user(
            user,
            title="Пароль установлен",
            message="Для вашего аккаунта задан пароль, и теперь вы можете использовать его для входа, если этот сценарий будет доступен.",
            event=Notification.Event.PASSWORD_CHANGED,
            notification_type=Notification.NotificationType.SUCCESS,
            link="/profile/settings/",
            payload={"user_id": user.id},
            telegram=True,
        )

    @staticmethod
    def initiate_password_reset(*, email: str) -> dict[str, str] | None:
        user = User.objects.filter(email=email).first()
        if not user:
            return None
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        send_platform_email(
            subject="Password reset",
            message=f"Use uid={uid} and token={token} to reset your password.",
            recipient_list=[user.email],
        )
        AuditLogService.log(action="user.password_reset_requested", obj=user)
        return {"uid": uid, "token": token}

    @staticmethod
    def confirm_password_reset(*, uid: str, token: str, password: str) -> User:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id)
        if not default_token_generator.check_token(user, token):
            raise ValidationError("Invalid reset token.")
        user.set_password(password)
        user.save(update_fields=["password"])
        AuditLogService.log(action="user.password_reset_confirmed", obj=user)
        return user

    @staticmethod
    def block_user(*, user: User, reason: str = "") -> User:
        user.is_blocked = True
        user.is_active = False
        user.blocked_at = timezone.now()
        user.save(update_fields=["is_blocked", "is_active", "blocked_at", "updated_at"])
        AuditLogService.log(action="user.blocked", obj=user, metadata={"reason": reason})
        return user
